# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A RAG chatbot that answers questions about course materials. FastAPI backend + vanilla HTML/JS frontend, ChromaDB for vectors, `sentence-transformers` (`all-MiniLM-L6-v2`, runs locally) for embeddings, an Ollama Cloud model (default `gemma4:31b`) for generation. The LLM client is the `ollama` Python package pointed at `https://ollama.com`, with the API key sent as an `Authorization: Bearer` header. Python 3.13, managed with `uv`.

## Commands

```bash
uv sync                                              # install dependencies
./run.sh                                             # start the app (on Windows, run via Git Bash)
cd backend && uv run uvicorn app:app --reload --port 8000   # manual start
```

- Web UI: http://localhost:8000 — API docs: http://localhost:8000/docs
- Requires `OLLAMA_API_KEY` in a root-level `.env` (see `.env.example`). `OLLAMA_MODEL` and `OLLAMA_BASE_URL` are optional overrides. The model must support tools; see https://ollama.com/api/tags for the cloud models available.
- Tool definitions use Ollama's function-calling shape (`{"type": "function", "function": {name, description, parameters}}`). `ToolManager.register_tool` reads the name from `function.name`.
- `./scripts/format.sh` formats Python code with black; `./scripts/check.sh` verifies formatting without changing files (run before committing). Black config is in `pyproject.toml`.
- Always use `uv run` / `uv add` rather than `pip`.
- There is no linter configured (black handles formatting). `main.py` at the root is an unused placeholder.

## Architecture

**The server must be started from `backend/`.** Paths are relative to that directory: `../docs` (course documents loaded at startup), `../frontend` (mounted as static files at `/`), and `./chroma_db` (persistent vector store, created at `backend/chroma_db`). Backend modules import each other as top-level modules (`from config import config`), not as a package.

### Query flow (tool-based RAG, not retrieve-then-generate)

1. `frontend/script.js` POSTs `{query, session_id}` to `/api/query` (`backend/app.py`). A session is created if none is supplied.
2. `RAGSystem.query` (`rag_system.py`) fetches conversation history from `SessionManager` and calls `AIGenerator.generate_response` with the tool definitions from `ToolManager`.
3. `AIGenerator` (`ai_generator.py`) makes one `client.chat` call with tools. If the reply has `message.tool_calls`, it executes them via `ToolManager` and appends each result as a `role: "tool"` message, then makes **one** follow-up call *without* tools to get the final answer. Only a single round of tool use is supported. Conversation history is injected into the system prompt as text, not as message turns.
4. `CourseSearchTool` (`search_tools.py`, tool name `search_course_content`) calls `VectorStore.search` and stores UI source labels in `last_sources`. `RAGSystem` reads them via `ToolManager.get_last_sources()` and then resets them — this side channel is how sources reach the API response.

### Vector store (`vector_store.py`)

Two ChromaDB collections:
- `course_catalog` — one doc per course (the title, which is also the ID). Lesson metadata is stored as a JSON string in `lessons_json`, since Chroma metadata can't hold lists.
- `course_content` — text chunks with `course_title`, `lesson_number`, and `chunk_index` metadata.

`search()` first resolves a fuzzy `course_name` to an exact title through a semantic search on `course_catalog`, then queries `course_content` with a `where` filter on title and/or lesson number.

### Document ingestion (`document_processor.py`)

Course files in `docs/` (`.txt`/`.pdf`/`.docx` by extension, but everything is read as UTF-8 text) must follow this format:

```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 0: <lesson title>
Lesson Link: <url>
<content...>
Lesson 1: ...
```

Content is split into sentence-based chunks (`CHUNK_SIZE`=800 chars, `CHUNK_OVERLAP`=100 chars). Chunk context prefixes are inconsistent: the first chunk of each lesson gets `"Lesson N content: "`, while every chunk of the *last* lesson gets `"Course <title> Lesson N content: "`.

At startup, `add_course_folder` skips any course whose title already exists in Chroma. Editing a document already in `docs/` therefore has **no effect** until `backend/chroma_db` is deleted (or `clear_existing=True` is passed).

### Other notes

- All tunables (model, chunk sizes, `MAX_RESULTS`, `MAX_HISTORY`) live in `backend/config.py`.
- Sessions are in-memory only (lost on restart). `MAX_HISTORY` counts exchanges, so the stored history is `MAX_HISTORY * 2` messages.
- `DevStaticFiles` (no-cache static handler) is defined in `app.py` but unused; the mount uses plain `StaticFiles`.
- To add a new tool, subclass `Tool` in `search_tools.py` and register it with `ToolManager` in `RAGSystem.__init__`. Note that `AIGenerator`'s system prompt limits the model to one search per query.

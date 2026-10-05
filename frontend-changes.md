# Code quality tooling changes

> Note: this feature (black formatting + quality scripts) is Python/dev-workflow tooling, not a
> front-end change. No files under `frontend/` were modified.

## What was added
- **black** added as a dev dependency (`[dependency-groups] dev` in `pyproject.toml`).
- **`[tool.black]` config** in `pyproject.toml` (line length 88, py313, excludes `chroma_db`, `.trees`, `.venv`).
- **`scripts/format.sh`** – auto-formats `backend/` and `main.py` with black.
- **`scripts/check.sh`** – runs all quality checks without modifying files (currently `black --check --diff`); exits non-zero on failure, so it is CI-friendly. Add future checks (linters, tests) here.
- **Codebase reformatted** with black: 13 Python files under `backend/` (including tests) were reformatted; behaviour is unchanged (formatting only).
- `CLAUDE.md` updated with the new commands.

## Usage
```bash
./scripts/format.sh   # format code
./scripts/check.sh    # verify formatting (run before committing)
```
(On Windows, run via Git Bash.)

---

# Testing infrastructure changes

None. This task (API tests, pytest config, shared fixtures) touched no frontend files (`frontend/`).

Note: the `/implement-feature` instructions say to implement front-end features only; this request was backend test infrastructure, and was implemented as explicitly requested.

## What changed (backend/test tooling only)
- `pyproject.toml`: added `[tool.pytest.ini_options]` (testpaths, pythonpath, markers, addopts) and a `dev` dependency group (`pytest`, `httpx`).
- `backend/tests/conftest.py`: shared fixtures (`mock_rag_system`, `client`, `sample_sources`, `sample_analytics`) and a standalone test FastAPI app mirroring `app.py` endpoints without the static mount or real `RAGSystem`.
- `backend/tests/test_api.py`: 11 tests for `/api/query`, `/api/courses`, `/api/session/{id}` and `/`.

Run with `uv run pytest` (or `-m api` for API tests only).

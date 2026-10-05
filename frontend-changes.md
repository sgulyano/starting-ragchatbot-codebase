# Frontend changes

None. This task (API tests, pytest config, shared fixtures) touched no frontend files (`frontend/`).

Note: the `/implement-feature` instructions say to implement front-end features only; this request was backend test infrastructure, and was implemented as explicitly requested.

## What changed (backend/test tooling only)
- `pyproject.toml`: added `[tool.pytest.ini_options]` (testpaths, pythonpath, markers, addopts) and a `dev` dependency group (`pytest`, `httpx`).
- `backend/tests/conftest.py`: shared fixtures (`mock_rag_system`, `client`, `sample_sources`, `sample_analytics`) and a standalone test FastAPI app mirroring `app.py` endpoints without the static mount or real `RAGSystem`.
- `backend/tests/test_api.py`: 11 tests for `/api/query`, `/api/courses`, `/api/session/{id}` and `/`.

Run with `uv run pytest` (or `-m api` for API tests only).

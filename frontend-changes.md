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

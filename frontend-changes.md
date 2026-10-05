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

---

# Frontend changes: dark/light theme toggle

## `frontend/index.html`
- Added a `#themeToggle` button (fixed, top-right) containing inline sun and moon SVG icons. Its `aria-label` is updated by JS to describe the action ("Switch to light/dark theme"); the icons are `aria-hidden`.
- Added a small inline `<script>` in `<head>` that reads `localStorage.theme` and sets `data-theme` on `<html>` before first paint, to prevent a flash of the wrong theme.
- Bumped the CSS/JS cache-busting query strings to `?v=11`.

## `frontend/style.css`
- Added a `:root[data-theme="light"]` block that overrides the existing CSS variables (background, surface, text, borders, primary, focus ring, welcome colors). Primary `#1d4ed8` on white and text `#0f172a` / `#475569` on light surfaces meet WCAG AA contrast.
- Moved previously hardcoded colors into new variables so both themes can set them: source-link colors, code/pre background, welcome shadow, error/success text, toggle icon color.
- Added `.theme-toggle` styles: 44px circular button matching the surface/border look, hover lift, visible `:focus-visible` ring, and a sun-to-moon rotate/fade icon animation.
- Added a `.theme-transition` rule that animates background, text, border and shadow colors for ~0.35s. It is disabled under `prefers-reduced-motion`.

## `frontend/script.js`
- Added `setupThemeToggle()` (called on `DOMContentLoaded`): toggles `data-theme` between `dark` (default) and `light` on `<html>`, persists the choice in `localStorage`, updates the button's `aria-label`, and adds `theme-transition` to `<html>` only for the duration of the switch.

## Accessibility
- The toggle is a native `<button>`, so it is keyboard-operable with Tab, Enter and Space, and has a visible focus ring.

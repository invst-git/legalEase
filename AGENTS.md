# Repository Guidelines

## Project Structure & Module Organization
- `app/` FastAPI backend: `main.py` (routes), `models.py` (SQLAlchemy), `schemas.py` (Pydantic), `services.py` (AI/OCR + logic), `database.py` (SQLite), `utils.py` (PDF/text helpers).
- `index.html`, `main.js` Static frontend calling `http://127.0.0.1:8000`.
- `scripts/` Utility tasks (e.g., `scripts/setup_benchmark_db.py`).
- `data/` Sample PDFs for local testing (do not commit large files).
- `requirements.txt` dependencies; `chimera_app.db` local SQLite (generated).

## Build, Test, and Development Commands
- Create venv (Windows): `python -m venv venv && .\venv\Scripts\activate`
- Create venv (Unix): `python -m venv venv && source venv/bin/activate`
- Install deps: `pip install -r requirements.txt`
- Run API: `uvicorn app.main:app --reload --port 8000`
- Serve UI: `python -m http.server 8080` then open `http://localhost:8080`
- Seed benchmark data: `python scripts/setup_benchmark_db.py`
- Tests (if added): `pytest -q`

## Coding Style & Naming Conventions
- Python: PEP 8, 4‑space indents, type hints where practical.
- Naming: `snake_case` for functions/vars, `PascalCase` for Pydantic/ORM models, modules/files in lower_snake_case.
- Separation: request/response models in `schemas.py`; DB models in `models.py`; route handlers in `app/main.py`; shared logic in `services.py`/`utils.py`.
- JavaScript: `camelCase`, prefer `async/await`, keep DOM/query logic in `main.js`.

## Testing Guidelines
- Framework: `pytest`; HTTP clients like `httpx` for API tests.
- Layout: mirror `app/` under `tests/` (e.g., `tests/test_main.py`).
- Scope: cover API endpoints (FastAPI TestClient/HTTPX) and pure functions in `services.py`/`utils.py`.
- Run: `pip install pytest httpx` then `pytest -q`.

## Commit & Pull Request Guidelines
- Commits: imperative, concise subject (≤50 chars). Examples: `Add file upload endpoint`, `Improve OCR error handling`.
- PRs: clear description, link issues, include screenshots for UI changes, reproduction steps, and any env var/DB implications. Keep diffs focused.

## Security & Configuration Tips
- Secrets: use `.env` (e.g., `GOOGLE_API_KEY`); do not commit real keys.
- Artifacts: avoid committing generated SQLite DBs; review `.gitignore` before pushing.
- CORS/UI: serve `index.html` over HTTP (not `file://`). If API host/port changes, update `BASE_URL` in `main.js`.


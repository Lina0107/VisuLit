# AGENTS.md

## Cursor Cloud specific instructions

**VisuLit** is a two-service app: Flask backend (Python) + Next.js frontend (TypeScript/React).

### Services

| Service | Command | Port | Notes |
|---------|---------|------|-------|
| Flask backend | `python3 app.py` (from repo root) | 5000 | Needs `.env` with `AITUNNEL_API_KEY` for LLM/image features; health check at `/api/health` works without it |
| Next.js frontend | `npm run dev` (from `frontend/`) | 3000 | Proxies `/api/*` to Flask via `next.config.ts` rewrites |

### Quick reference

- **Lint**: `cd frontend && npx eslint .`
- **TypeScript check**: `cd frontend && npx tsc --noEmit`
- **Backend deps**: `pip install -r requirements.txt` (from repo root)
- **Frontend deps**: `cd frontend && npm install`
- See `README.md` for full local development instructions.

### Non-obvious caveats

- No database — all data is stored in JSON files under `data/`. The seed data (`books.json`, `curated_books.json`) is already committed.
- The `.env` file must exist in the repo root for the Flask backend to read `AITUNNEL_*` vars. Without `AITUNNEL_API_KEY`, `prepare_book` and `generate` endpoints will fail, but all other endpoints (health, books, characters, usage, history) work fine.
- `import_books.py` is a one-time script to fetch books from Gutendex into `data/books.json` — only run if the file is missing or needs refreshing.
- The frontend uses `package-lock.json` (npm), not pnpm or yarn.
- Pre-existing ESLint errors (19 `@typescript-eslint/no-explicit-any` and `react/no-unescaped-entities`) are in the codebase; TypeScript compiles cleanly.

# VisuLit

**VisuLit** generates **AI portraits of literary characters** grounded in **real quotes** from public-domain books. The UI is a **Next.js** app; the API is **Flask** (Gutendex search, quote extraction, image generation via compatible LLM APIs).

## Features

- Search **public-domain** books (Gutendex) and **prepare** a book: character list + appearance-focused quotes.
- **Generate** a portrait for a selected character or a **custom** character from your own description.
- **History** and usage limits (daily free tier) stored in local JSON under `data/` (see `app.py`).

## Stack

| Layer    | Technology                          |
| -------- | ----------------------------------- |
| Frontend | Next.js (App Router), React, Tailwind |
| Backend  | Flask, CORS, `requests`             |
| Proxy    | Dev: Next rewrites `/api/*` → Flask |
| Deploy   | Docker Compose + Caddy (optional)   |

## Prerequisites

- **Python 3.10+**
- **Node.js 20+** (for the frontend)
- An **API key** for your LLM provider (env: `AITUNNEL_*` or compatible OpenAI-style base URL)

## Local development

### 1. Backend (Flask)

From the repository root:

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```

Create a `.env` file in the repo root (do **not** commit it):

```env
AITUNNEL_API_KEY=your_key_here
AITUNNEL_BASE_URL=https://api.example.com/v1
AITUNNEL_MODEL=gpt-4o-mini
```

Start Flask:

```bash
python app.py
```

API: `http://127.0.0.1:5000` — try `GET /api/health`.

### 2. Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

App: `http://localhost:3000` — requests to `/api/*` are proxied to Flask (see `frontend/next.config.ts`).

Optional: `frontend/.env.local`

```env
NEXT_PUBLIC_SUPPORT_EMAIL=you@example.com
```

### 3. Docker (production-style)

See [DEPLOY_BUDGET.md](./DEPLOY_BUDGET.md) for VPS, `.env`, and `docker compose up`.

## Project layout

```
├── app.py              # Flask API + legacy HTML templates
├── templates/          # Optional Flask-only UI
├── frontend/           # Next.js (main UI)
├── data/               # JSON cache (books, characters, history, …)
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
└── Caddyfile
```

## Security

- Never commit `.env` or API keys.
- Review `data/` before exposing a server — it may contain generated paths and cache.

## License

This project is licensed under the **MIT License** — see [LICENSE](./LICENSE).

Book texts are sourced from public-domain catalogs; respect the terms of **Project Gutenberg**, **Gutendex**, and your **image/LLM provider**.

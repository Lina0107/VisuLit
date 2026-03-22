# Budget VPS + Domain Deploy (Next.js + Flask + Caddy)

This repo is set up for a 3-container production deployment:
- `frontend` (Next.js) on port `3000`
- `flask` (Flask API) on port `5000`
- `caddy` (HTTPS reverse proxy) on ports `80/443`

## 1) Buy a domain
You need a domain like `yourdomain.com`.
Cheapest options are usually:
- Porkbun
- Namecheap
- Cloudflare Registrar (also works well with Caddy + DNS)

You will point the domain to your VPS IP via DNS.

## 2) Create a VPS (recommended minimal setup)
Pick a low-cost VPS provider, e.g. Hetzner Cloud.
Suggested size:
- 2 vCPU
- 2 GB RAM
Small instances are often enough for this MVP.

On the VPS, ensure ports `80` and `443` are open in firewall/security group.

## 3) Install Docker
On the VPS:
1. Install Docker Engine + Docker Compose plugin (provider instructions).
2. Verify:
   - `docker --version`
   - `docker compose version`

## 4) Prepare your project on the VPS
Copy this whole folder to the VPS so that these files/folders exist:
- `docker-compose.yml`
- `Caddyfile`
- `Dockerfile.backend`
- `Dockerfile.frontend`
- `frontend/`
- `app.py`
- `requirements.txt`
- `templates/`
- `data/`  (IMPORTANT: contains `books.json`, `curated_books.json`, `characters.json`, `history.json`, `usage.json`)

If your local `data/` folder is present, copy it too.

## 5) Configure environment variables
In the project root on the VPS, create a `.env` file and set:
- `AITUNNEL_API_KEY=...`
- `AITUNNEL_BASE_URL=...` (example: `https://neuroapi.host/v1/`)
- `AITUNNEL_MODEL=gemini-...` (for text is your chosen model)
- `DOMAIN=yourdomain.com`
- `CADDY_EMAIL=you@example.com`

Optional:
- `IMAGE_MODEL=gemini-3-pro-image-preview`
- `IMAGE_SIZE=1024x1536`

For the Next.js build (shown in the UI footer and error hints), set one of:
- Root `.env` next to `docker-compose.yml`: `NEXT_PUBLIC_SUPPORT_EMAIL=you@yourdomain.com` (used as a Docker build arg), or
- `frontend/.env.production` when building locally.

If unset, the app uses `hello@visulit.com`.

Then restart:
- `docker compose up -d --build`

## 6) Point DNS to VPS
In your DNS provider:
- Create an `A` record:
  - Host: `@` (or your root)
  - Value: VPS public IP

Wait a few minutes for DNS propagation.

## 7) Run and verify
Run:
- `docker compose up -d --build`

Then open in browser:
- `https://yourdomain.com`

API health should work:
- `https://yourdomain.com/api/health`

## 8) If something fails
Check logs:
- `docker compose logs -f caddy`
- `docker compose logs -f frontend`
- `docker compose logs -f flask`

Most common issues:
- DNS not pointed to the VPS IP yet
- Ports 80/443 blocked on VPS firewall
- Missing/incorrect `.env` values


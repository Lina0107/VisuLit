#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/deploy_vps.sh
# Requires: .env file in project root

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Copy .env.example to .env and fill values."
  exit 1
fi

echo "[1/4] Pull latest code (if git repo)"
if command -v git >/dev/null 2>&1 && [ -d .git ]; then
  git pull --ff-only || true
fi

echo "[2/4] Build and start containers"
docker compose up -d --build

echo "[3/4] Show container status"
docker compose ps

echo "[4/4] Health check"
sleep 5
curl -fsS "https://${DOMAIN}/api/health" || curl -fsS "http://127.0.0.1:5000/api/health"

echo "Deploy finished."

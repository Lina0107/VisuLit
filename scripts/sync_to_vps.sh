#!/usr/bin/env bash
set -euo pipefail

# Copy current project to VPS via rsync
# Usage:
#   ./scripts/sync_to_vps.sh user@server_ip /opt/visulit

TARGET_HOST="${1:-}"
TARGET_DIR="${2:-/opt/visulit}"

if [ -z "$TARGET_HOST" ]; then
  echo "Usage: $0 user@server_ip [target_dir]"
  exit 1
fi

rsync -avz --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude 'frontend/node_modules' \
  --exclude 'frontend/.next' \
  --exclude '.env' \
  ./ "$TARGET_HOST:$TARGET_DIR/"

echo "Sync complete: $TARGET_HOST:$TARGET_DIR"

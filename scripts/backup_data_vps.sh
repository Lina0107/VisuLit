#!/usr/bin/env bash
# Backup VisuLit data/ on the VPS (characters, portraits, usage, history).
#
# Usage:
#   cd /opt/visulit && bash scripts/backup_data_vps.sh
#   bash scripts/backup_data_vps.sh /opt/visulit/data /opt/visulit/backups
#
# Cron example (daily at 03:15 UTC):
#   15 3 * * * cd /opt/visulit && bash scripts/backup_data_vps.sh >> /var/log/visulit-backup.log 2>&1

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="${1:-${REPO_ROOT}/data}"
BACKUP_DIR="${2:-${REPO_ROOT}/backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"

if [[ ! -d "${DATA_DIR}" ]]; then
  echo "ERROR: data directory not found: ${DATA_DIR}"
  exit 1
fi

mkdir -p "${BACKUP_DIR}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
ARCHIVE="${BACKUP_DIR}/visulit-data-${STAMP}.tar.gz"

tar -czf "${ARCHIVE}" -C "$(dirname "${DATA_DIR}")" "$(basename "${DATA_DIR}")"
echo "Created ${ARCHIVE} ($(du -h "${ARCHIVE}" | awk '{print $1}'))"

if command -v find >/dev/null 2>&1; then
  find "${BACKUP_DIR}" -name 'visulit-data-*.tar.gz' -mtime +"${KEEP_DAYS}" -delete 2>/dev/null || true
fi

#!/usr/bin/env bash
# Scheduled Postgres backup (pg_dump) with offsite copy.
# Usage: ./scripts/backup.sh [backup_dir]
set -euo pipefail

BACKUP_DIR="${1:-./backups}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
FILE="${BACKUP_DIR}/app-${TIMESTAMP}.dump"

mkdir -p "${BACKUP_DIR}"

: "${POSTGRES_SERVER:=db}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_USER:=postgres}"
: "${POSTGRES_PASSWORD:=}"
: "${POSTGRES_DB:=app}"

export PGPASSWORD="${POSTGRES_PASSWORD}"
pg_dump \
  -h "${POSTGRES_SERVER}" -p "${POSTGRES_PORT}" \
  -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
  --format=custom --file="${FILE}"

echo "Backup written to ${FILE}"

# Offsite copy (optional). Set BACKUP_S3_URL to enable.
if [[ -n "${BACKUP_S3_URL:-}" ]]; then
  echo "Uploading ${FILE} to ${BACKUP_S3_URL}"
  aws s3 cp "${FILE}" "${BACKUP_S3_URL%/}/" --only-show-errors
fi

# Retention: keep 7 daily dumps
find "${BACKUP_DIR}" -name 'app-*.dump' -mtime +7 -delete
echo "Backup complete"

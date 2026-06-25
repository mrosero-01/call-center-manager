#!/usr/bin/env bash
set -eu

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${PROJECT_DIR}/.env"

if [ -f "${ENV_FILE}" ]; then
  set -a
  # shellcheck disable=SC1090
  . "${ENV_FILE}"
  set +a
fi

if [ "${DB_ENGINE:-sqlite}" != "postgresql" ]; then
  echo "DB_ENGINE no es postgresql; backup omitido."
  exit 0
fi

BACKUP_DIR="${BACKUP_DIR:-${PROJECT_DIR}/backups/postgres}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
OUTPUT_FILE="${BACKUP_DIR}/${DB_NAME}-${TIMESTAMP}.dump"

mkdir -p "${BACKUP_DIR}"

export PGPASSWORD="${DB_PASSWORD:-}"

pg_dump \
  --host="${DB_HOST:-127.0.0.1}" \
  --port="${DB_PORT:-5432}" \
  --username="${DB_USER:-call_center_manager}" \
  --dbname="${DB_NAME:-call_center_manager}" \
  --format=custom \
  --file="${OUTPUT_FILE}"

find "${BACKUP_DIR}" -type f -name "*.dump" -mtime "+${BACKUP_RETENTION_DAYS}" -delete

echo "Backup creado: ${OUTPUT_FILE}"

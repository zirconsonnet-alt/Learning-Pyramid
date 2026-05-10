#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SQL_FILE="${SCRIPT_DIR}/postgres_optional_tables_hotfix.sql"

cd "$APP_DIR"

if [ ! -f .env ]; then
  echo "missing .env in ${APP_DIR}" >&2
  exit 1
fi

if [ ! -f "$SQL_FILE" ]; then
  echo "missing SQL file: ${SQL_FILE}" >&2
  exit 1
fi

PGUSER="$(grep '^LEARNINGPYRAMID_POSTGRES_USER=' .env | head -n1 | cut -d= -f2- || true)"
PGDB="$(grep '^LEARNINGPYRAMID_POSTGRES_DB=' .env | head -n1 | cut -d= -f2- || true)"

[ -n "$PGUSER" ] || PGUSER="learningpyramid"
[ -n "$PGDB" ] || PGDB="learningpyramid"

docker compose \
  -f docker-compose.selfhost.yml \
  -f docker-compose.selfhost.postgres.yml \
  --env-file .env \
  exec -T postgres \
  psql -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$PGDB" \
  < "$SQL_FILE"

docker compose \
  -f docker-compose.selfhost.yml \
  -f docker-compose.selfhost.postgres.yml \
  --env-file .env \
  exec -T postgres \
  psql -U "$PGUSER" -d "$PGDB" \
  -c "SELECT to_regclass('public.global_settings_index') AS global_settings_index, to_regclass('public.user_cloud_accounts') AS user_cloud_accounts, to_regclass('public.instance_media_binding_index') AS instance_media_binding_index;"

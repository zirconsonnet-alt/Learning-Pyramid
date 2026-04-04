#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "$APP_DIR"

if [ -f "${SCRIPT_DIR}/apply_postgres_optional_tables_hotfix.sh" ]; then
  bash "${SCRIPT_DIR}/apply_postgres_optional_tables_hotfix.sh"
fi

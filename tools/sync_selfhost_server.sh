#!/usr/bin/env bash
set -euo pipefail

REMOTE_ROOT="${REMOTE_ROOT:-/opt/learningpyramid}"
APP_DIR="$REMOTE_ROOT/app"
SRC_DIR="${1:-}"

if [ -z "$SRC_DIR" ]; then
  echo "usage: tools/sync_selfhost_server.sh <source-dir>" >&2
  exit 2
fi

RSYNC_ARGS=(-a --delete --filter 'P frontend/dist/assets/***' --filter 'P data/***' --filter 'P /data/***' --exclude '.env' --exclude 'data/' --exclude 'release/')
rsync "${RSYNC_ARGS[@]}" "$SRC_DIR"/ "$APP_DIR"/

# LearningPyramid v1beta

LearningPyramid 是一个本地优先的学习系统，用于围绕你自己的视频或音频材料构建复述点、复习链，以及 ASR 转写产物。

## Release mode

This repository now supports a production-style local launch:

1. Install Python 3.12+
2. Install backend dependencies

```powershell
pip install -r requirements.txt
```

3. Build the frontend once

```powershell
cd frontend
pnpm install
pnpm build
cd ..
```

4. Start LearningPyramid

```powershell
LearningPyramid.bat
```

The release launcher starts a single backend process on `http://127.0.0.1:8001/` and serves the built frontend directly from FastAPI. It does not use Vite dev server and does not kill unrelated local processes.

## Build release bundle

To assemble a portable release folder and zip:

```powershell
python tools/build_release_bundle.py
```

If you want the script to rebuild the frontend first:

```powershell
python tools/build_release_bundle.py --build-frontend
```

## Build standalone Windows executables

To produce `LearningPyramid.exe`, `LearningPyramid-server.exe`, and `LearningPyramid-stop.exe`:

```powershell
python tools/build_windows_standalone.py
```

To build them in a clean packaging venv, which avoids bundling unrelated Python packages from your current environment:

```powershell
python tools/build_windows_standalone.py --bootstrap-packaging-venv
```

If you want to recreate that packaging venv from scratch:

```powershell
python tools/build_windows_standalone.py --bootstrap-packaging-venv --refresh-packaging-venv
```

## Build Windows installer package

To generate an installable bundle with `Install-LearningPyramid.bat`:

```powershell
python tools/build_windows_installer.py --bootstrap-packaging-venv
```

If Inno Setup 6 is installed, the same script also emits a `LearningPyramid-...-Setup.exe`. Otherwise it still produces a script-based installer zip.

## Stop

```powershell
LearningPyramid-stop.bat
```

## Self-host with Docker

Hosted deployment now treats PostgreSQL as the recommended production path. Start from the self-host example env file:

```bash
cp .env.selfhost.example .env
# edit .env and replace every change-me secret / host value first
docker compose \
  -f docker-compose.selfhost.yml \
  -f docker-compose.selfhost.postgres.yml \
  --env-file .env \
  up --build
```

See [docs/self-host.md](docs/self-host.md) for the runtime shape and deployment notes.

If you need a simple local fallback or a compatibility path, SQLite is still supported:

```bash
PLM_SQL_BACKEND=sqlite
docker compose -f docker-compose.selfhost.yml --env-file .env up --build
```

Project data is stored in normalized SQL tables; `project_snapshots.snapshot_json` remains only a compatibility/export shell.

If you want TLS on a public domain, there is also a Caddy reverse-proxy overlay:

```bash
docker compose \
  -f docker-compose.selfhost.yml \
  -f docker-compose.selfhost.postgres.yml \
  -f docker-compose.selfhost.proxy.yml \
  --env-file .env \
  up --build
```

The hosted stack now expects `PLM_MEDIA_ACCESS_TOKEN_SECRET` to be set to a real secret in `.env`. The shipped self-host example also defaults to `PLM_ALLOW_SIGNUP=false` and `PLM_SECURE_COOKIES=true`; flip those only when you intentionally need a less strict local test setup.

For Windows server sync, the normal helper flow is just:

```powershell
Sync-Selfhost-Server.bat
```

`Sync-Selfhost-Server.bat` now auto-prepares the project deploy key. If `~/.ssh/learningpyramid_selfhost_ed25519` is missing, locked behind a forgotten passphrase, or not yet installed on the server, the sync script repairs that first and may ask for the server password once so future syncs can stay key-based.

If you want to manage or rotate the key explicitly, use:

```powershell
Install-Selfhost-Server-SshKey.bat -ReplaceExistingKey -NoKeyPassphrase
```

`Sync-Selfhost-Server.bat` now prefers the default SSH key, prompts before deploying a dirty git worktree, validates the remote `.env`, and runs readiness plus a public smoke check after deploy.

## Dev mode

If you still need hot reload and Vite dev server:

```powershell
LearningPyramid.dev.bat
```

## Data location

By default, user data is stored under:

- Windows: `%LOCALAPPDATA%\LearningPyramid\plm_store.sqlite3`
- macOS: `~/Library/Application Support/LearningPyramid/plm_store.sqlite3`
- Linux: `~/.local/share/learningpyramid/plm_store.sqlite3`

Overrides:

- `PLM_SQL_BACKEND`: `sqlite` or `postgres`
- `PLM_STORE_DB_PATH`: full path to the SQLite store file
- `PLM_AUTH_DB_PATH`: full path to the SQLite auth file
- `PLM_POSTGRES_DSN`: PostgreSQL DSN used when `PLM_SQL_BACKEND=postgres`
- `PLM_STORE_POSTGRES_DSN`: optional override for the core store DSN
- `PLM_AUTH_POSTGRES_DSN`: optional override for the auth store DSN
- `PLM_LOG_LEVEL`: application log level, default `INFO`
- `PLM_POSTGRES_CONNECT_TIMEOUT`: connect timeout in seconds
- `PLM_POSTGRES_POOL_ACQUIRE_TIMEOUT`: pool acquire timeout in seconds
- `PLM_POSTGRES_POOL_MIN_SIZE`: pool warm size
- `PLM_POSTGRES_POOL_MAX_SIZE`: pool max size
- `PLM_POSTGRES_STATEMENT_TIMEOUT_MS`: PostgreSQL statement timeout
- `PLM_POSTGRES_LOCK_TIMEOUT_MS`: PostgreSQL lock timeout
- `PLM_POSTGRES_IDLE_IN_TX_TIMEOUT_MS`: PostgreSQL idle-in-transaction timeout
- `PLM_LEGACY_STORE_PATH`: optional legacy JSON import source; `PLM_STORE_PATH` is still accepted as a legacy alias
- `PLM_DATA_DIR`: base directory for LearningPyramid runtime data
- `PLM_PROJECTS_ROOT`: root directory used when creating new projects; default is `LearningPyramid/data`
- `PLM3_WHISPER_PYTHON`: legacy override for the Python interpreter used by the local Whisper runtime

When `PLM_SQL_BACKEND=sqlite`, an older repo-local `.plm_store.json`, `%LOCALAPPDATA%\LearningPyramid\plm_store.json`, `%LOCALAPPDATA%\PLM3\plm_store.json`, or `%LOCALAPPDATA%\学习金字塔\plm_store.json` is imported on first start and then archived as `*.imported.bak`. The same legacy import path also works when the runtime backend is PostgreSQL.

If you need to seed PostgreSQL from the current SQLite runtime store, you can export a runtime-compatible SQL script with:

```powershell
python tools/export_sqlite_to_postgres.py --output learningpyramid-postgres.sql
```

Or export and apply it in one step:

```powershell
python tools/migrate_sqlite_to_postgres.py --postgres-dsn postgresql://user:pass@localhost:5432/learningpyramid
```

PostgreSQL runtime schema is now versioned through `schema_migrations`. To apply schema changes without importing data:

```powershell
python tools/apply_postgres_migrations.py --postgres-dsn postgresql://user:pass@localhost:5432/learningpyramid
```

To inspect migration state or fail CI/CD when migrations are still pending:

```powershell
python tools/apply_postgres_migrations.py --postgres-dsn postgresql://user:pass@localhost:5432/learningpyramid --status
python tools/apply_postgres_migrations.py --postgres-dsn postgresql://user:pass@localhost:5432/learningpyramid --check
```

If you only need a schema bundle or only the data insert bundle, the export tool supports:

```powershell
python tools/export_sqlite_to_postgres.py --schema-only --output learningpyramid-schema.sql
python tools/export_sqlite_to_postgres.py --data-only --output learningpyramid-data.sql
```

For PostgreSQL integration tests, start a disposable database and point `PLM_TEST_POSTGRES_DSN` at it:

```bash
docker compose -f docker-compose.postgres.yml --env-file .env up -d
PLM_TEST_POSTGRES_DSN=postgresql://learningpyramid:learningpyramid@127.0.0.1:15432/learningpyramid_test python -m pytest tests/test_postgres_runtime.py tests/test_postgres_hosted_api.py -q
```

## Runtime health and observability

Hosted mode now exposes:

- `GET /api/health/live`: liveness probe, only checks the process is serving HTTP
- `GET /api/health`: readiness probe, checks runtime mode, SQL backend, store health, auth health, and returns `503` when degraded
- `GET /api/system/runtime`: structured runtime status for backend/auth/pool inspection; requires authentication when `PLM_ENABLE_AUTH=true`

Every API response now includes `X-Request-ID`, and request logs include request path, status, and latency.

## Backup, restore, and rollback

Before switching a runtime to PostgreSQL or doing a risky migration, capture a runtime bundle:

```powershell
python tools/backup_runtime_bundle.py runtime-backup.json
```

To restore that bundle into the currently configured runtime:

```powershell
python tools/restore_runtime_bundle.py runtime-backup.json
```

Recommended rollback flow:

1. Create a runtime backup bundle from the current source runtime.
2. Run `tools/migrate_sqlite_to_postgres.py` against an empty PostgreSQL database.
3. Start the app with `PLM_SQL_BACKEND=postgres` and verify `/api/health`, login, and project access.
4. If verification fails, point the app back to the previous runtime or restore the backup bundle into a clean target runtime.

## Whisper

ASR service selection works like this:

1. If `ProjectConfig.external_services.asr` is configured, LearningPyramid uses that service first.
2. If no ASR service is configured, LearningPyramid tries to auto-discover and launch a local Whisper runtime.
3. If neither an explicit service nor a local Whisper runtime is available, ASR requests fail with a precondition error.

The current Windows default search path for local Whisper includes:

- `H:\whisper\.venv\Scripts\python.exe`

You can override local Whisper detection with:

```powershell
set PLM3_WHISPER_PYTHON=H:\whisper\.venv\Scripts\python.exe
```

`ffmpeg` must also be available in `PATH`.

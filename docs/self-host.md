# Self-host

## Start

Recommended production startup uses PostgreSQL:

```bash
cp .env.selfhost.example .env
# edit .env and replace every change-me secret / host value first
docker compose \
  -f docker-compose.selfhost.yml \
  -f docker-compose.selfhost.postgres.yml \
  --env-file .env \
  up --build
```

Open `http://localhost:8001`.

## Backend selection

PostgreSQL is the recommended hosted backend:

```bash
PLM_SQL_BACKEND=postgres
docker compose \
  -f docker-compose.selfhost.yml \
  -f docker-compose.selfhost.postgres.yml \
  --env-file .env \
  up --build
```

SQLite remains available for local fallback, compatibility testing, or migration staging:

```bash
PLM_SQL_BACKEND=sqlite
docker compose -f docker-compose.selfhost.yml --env-file .env up --build
```

If you use an external managed PostgreSQL instead of the included container, keep the same overlay and only replace `PLM_POSTGRES_DSN`.

Before first public deploy, update at least:

- `PLM_POSTGRES_PASSWORD`
- `PLM_POSTGRES_DSN`
- `PLM_MEDIA_ACCESS_TOKEN_SECRET`
- `PLM_PUBLIC_ORIGIN`
- `PLM_TRUSTED_HOSTS`

If you plan to enable paid membership, also read [membership-selfhost-launch-checklist.md](/i:/Projects/LearningPyramid/docs/membership-selfhost-launch-checklist.md) before public launch.

## Runtime shape

- FastAPI serves the built frontend and the API from one container.
- When `PLM_SQL_BACKEND=sqlite`, auth users, sessions, and project memberships are stored in `/data/plm_auth.sqlite3`.
- When `PLM_SQL_BACKEND=sqlite`, core LearningPyramid business data is stored in `/data/plm_store.sqlite3` as normalized SQL tables plus one compatibility snapshot row per project.
- When `PLM_SQL_BACKEND=postgres`, auth and project data live in the configured PostgreSQL database.
- Legacy `plm_store.json` files are import-only. If one is detected on first start, it is migrated into the active SQL backend and archived.
- Project structure and server-side sync still come from the server's own project directory.
- Browser local folder authorization is only used when the web client needs to read media files directly from the same device.

## PostgreSQL runtime knobs

The hosted stack now supports these PostgreSQL runtime controls:

- `PLM_POSTGRES_CONNECT_TIMEOUT`
- `PLM_POSTGRES_POOL_ACQUIRE_TIMEOUT`
- `PLM_POSTGRES_POOL_MIN_SIZE`
- `PLM_POSTGRES_POOL_MAX_SIZE`
- `PLM_POSTGRES_STATEMENT_TIMEOUT_MS`
- `PLM_POSTGRES_LOCK_TIMEOUT_MS`
- `PLM_POSTGRES_IDLE_IN_TX_TIMEOUT_MS`
- `PLM_LOG_LEVEL`

These values are already wired in `.env.selfhost.example` and `docker-compose.selfhost.yml`.

## PostgreSQL migration export

PostgreSQL schema initialization now uses versioned migrations tracked in `schema_migrations`.

To apply the current runtime schema without importing SQLite data:

```bash
python tools/apply_postgres_migrations.py --postgres-dsn postgresql://user:pass@localhost:5432/learningpyramid
```

To inspect the expected/applied migration state or make automation fail when migrations are pending:

```bash
python tools/apply_postgres_migrations.py --postgres-dsn postgresql://user:pass@localhost:5432/learningpyramid --status
python tools/apply_postgres_migrations.py --postgres-dsn postgresql://user:pass@localhost:5432/learningpyramid --check
```

If you want to move the current SQLite data into PostgreSQL, export a SQL script with:

```bash
python tools/export_sqlite_to_postgres.py --output learningpyramid-postgres.sql
```

By default the script reads `plm_store.sqlite3` and `plm_auth.sqlite3` from the current runtime data dir and emits runtime-compatible PostgreSQL DDL, migration metadata, and `INSERT` statements.

You can also split schema and data:

```bash
python tools/export_sqlite_to_postgres.py --schema-only --output learningpyramid-schema.sql
python tools/export_sqlite_to_postgres.py --data-only --output learningpyramid-data.sql
```

To apply the migration directly:

```bash
python tools/migrate_sqlite_to_postgres.py --postgres-dsn postgresql://user:pass@localhost:5432/learningpyramid
```

The migration script now applies versioned PostgreSQL migrations first, then imports the exported data rows. It expects an empty target database and optionally writes out the applied data-only SQL with `--sql-output`.

## PostgreSQL integration tests

Bring up a disposable PostgreSQL for local verification with:

```bash
docker compose -f docker-compose.postgres.yml --env-file .env up -d
```

Then run:

```bash
PLM_TEST_POSTGRES_DSN=postgresql://learningpyramid:learningpyramid@127.0.0.1:15432/learningpyramid_test \
python -m pytest tests/test_postgres_runtime.py tests/test_postgres_hosted_api.py -q
```

`tests/test_postgres_hosted_api.py` exercises the hosted app path: auth, project lifecycle, runtime health, migration import, and backup/restore round trip.

## Health probes and observability

Use these endpoints in deployment:

- `GET /api/health/live`: process liveness
- `GET /api/health`: readiness including store/auth/backend health
- `GET /api/system/runtime`: detailed runtime payload, including PostgreSQL pool stats. When `PLM_ENABLE_AUTH=true`, this endpoint requires an authenticated session.

Readiness returns `503` when the configured store or auth backend is degraded. API responses include `X-Request-ID`, and request logs include request id, path, status, and latency.

The default self-host compose now uses `/api/health` as the container healthcheck target.

## Membership payment operations

The current hosted build supports `wechat_native` membership payment, async notify, refund notify, admin payment sync, and pending-order reconciliation.

Run a one-shot reconciliation sweep with:

```bash
python tools/reconcile_membership_payments.py
```

The script inspects stale pending `wechat_native` membership orders, confirms remotely paid orders, and closes remotely terminated orders. Default behavior can be tuned with:

- `PLM_MEMBERSHIP_PENDING_PAYMENT_RECONCILE_MIN_AGE_MINUTES`
- `PLM_MEMBERSHIP_PENDING_PAYMENT_RECONCILE_LIMIT`

Recommended production setup is to schedule this script every 5 minutes with the same runtime `.env` used by the hosted server.

## Backup, restore, and rollback

Create a runtime bundle before major schema or backend changes:

```bash
python tools/backup_runtime_bundle.py runtime-backup.json
```

Restore that bundle into the currently configured runtime with:

```bash
python tools/restore_runtime_bundle.py runtime-backup.json
```

Recommended migration/rollback workflow:

1. Keep the existing SQLite runtime intact and generate a backup bundle.
2. Run `python tools/migrate_sqlite_to_postgres.py --postgres-dsn ...` into an empty PostgreSQL database.
3. Start the hosted stack on PostgreSQL and verify `/api/health`, authenticated `/api/system/runtime`, login, and core project flows.
4. If anything fails, stop the PostgreSQL deployment and either switch the app back to SQLite or restore the saved bundle into a clean target runtime.

## Recommended settings

- Keep `PLM_ENABLE_ASR=false` for public deployments.
- Keep `PLM_ALLOW_SIGNUP=false` unless you intentionally want open self-registration.
- Set `PLM_SECURE_COOKIES=true` when serving behind HTTPS.
- If you expose the app on a public domain, put it behind a reverse proxy that terminates TLS.
- The shipped `.env.selfhost.example` now uses `change-me` placeholders for secrets; replace them before booting the hosted app.

If you only need a one-off localhost smoke test over plain HTTP, you can temporarily set `PLM_SECURE_COOKIES=false`.

## Server sync workflow

The Windows helper scripts now default to a one-command sync flow:

```powershell
Sync-Selfhost-Server.bat
```

`Sync-Selfhost-Server.bat` automatically makes sure the project key at `~/.ssh/learningpyramid_selfhost_ed25519` exists locally, is usable without a forgotten local passphrase prompt, and is installed on the server. When it has to create, rotate, or reinstall that key, it may ask for the server password once during the repair step.

If you want to manage the project key explicitly or force a rotation, run:

```powershell
Install-Selfhost-Server-SshKey.bat -ReplaceExistingKey -NoKeyPassphrase
```

That backs up the old key files locally, creates a fresh project key without a passphrase, and reinstalls the new public key on the server so future deploys do not stop for a local key passphrase prompt.

`Sync-Selfhost-Server.bat` and `tools/sync_selfhost_server.ps1` now:

- prefer `~/.ssh/learningpyramid_selfhost_ed25519` when present
- auto-create, rotate, or reinstall that project key during sync when needed
- open and reuse one SSH session before upload so password auth happens once up front instead of again after a long transfer
- prompt before deploying a dirty git worktree from `Sync-Selfhost-Server.bat`, while `tools/sync_selfhost_server.ps1` still supports `-AllowDirtyWorktree` for non-interactive runs
- verify the remote `.env` still has non-placeholder PostgreSQL and media token secrets
- run readiness plus a public `/api/system/capabilities` smoke check after deploy

## With Caddy reverse proxy

Set these values in `.env`:

```bash
PLM_PUBLIC_HOST=your.domain.example
PLM_PUBLIC_ORIGIN=https://your.domain.example
PLM_TRUSTED_HOSTS=your.domain.example
PLM_SECURE_COOKIES=true
```

Then start both the app and Caddy:

```bash
docker compose \
  -f docker-compose.selfhost.yml \
  -f docker-compose.selfhost.postgres.yml \
  -f docker-compose.selfhost.proxy.yml \
  --env-file .env \
  up --build
```

If you stay on SQLite, omit `docker-compose.selfhost.postgres.yml`. In both modes, Caddy terminates TLS and forwards requests to the internal app container.

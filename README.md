# LearningPyramid v1beta

LearningPyramid 是一个本地优先的学习系统，用于围绕你自己的视频或音频材料构建复述点、复习链，并在存在时直接利用视频同目录同名字幕文件作为播放器字幕与 AI 文本上下文。工作台视频助手还会在提问时附带当前复述点内容和当前视频帧；桌宠可在用户发送问题后整理上下文，回复内提供“复制文本”和“复制图片”，把这轮问题对应的上下文和当前帧放进剪贴板，且不会调用 LLM。

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

## Windows desktop client preview

The Windows desktop client uses Tauri and reuses the existing React frontend. The current preview lives in `desktop/` and includes desktop runtime detection, native local folder import, a local media service for `NATIVE_LOCAL` file playback, and same-directory same-stem subtitle reading for local desktop videos. Baidu Netdisk import and playback are currently hidden in the product UI; the existing lower-level API and Tauri bridge code are retained. Offline cache and cloud-hosted video are not implemented in this stage.

```powershell
pnpm --dir frontend install
pnpm --dir desktop install
rustup toolchain install 1.88.0
$env:VITE_API_BASE_URL = "https://plm.xuebao.chat/api"
pnpm --dir desktop dev
```

See [docs/desktop-client.md](docs/desktop-client.md) for the current desktop boundary and follow-up plan.

## Mobile app preview

The Android and iPhone client uses Expo-managed React Native and lives in `mobile/`. The current MVP connects to the existing API, uses the scoped project routes, and covers login, subject/project center management, global settings, a native workbench aligned with the desktop workbench flow, existing local/server media playback descriptors, imported instance subtitles, learning task submission, inline queue-head review, and roll-up controls. Baidu Netdisk material import and playback are not exposed inside the mobile client.

```powershell
pnpm --dir mobile install
$env:EXPO_PUBLIC_API_BASE_URL = "https://plm.xuebao.chat/api"
pnpm --dir mobile start
```

For local verification:

```powershell
pnpm --dir mobile test
pnpm --dir mobile typecheck
```

See [docs/mobile-client.md](docs/mobile-client.md) for the current mobile boundary, unsupported media sources, and validation notes.

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

See [docs/deployment.md](docs/deployment.md) for the backend runtime shape and deployment notes.

### Membership WeChat payouts

The membership invite commission flow now supports unattended refund-window settlement and WeChat Pay merchant transfer reconciliation. Production payout setup requires:

- WeChat Pay native payment credentials plus merchant transfer capability.
- `LEARNINGPYRAMID_PUBLIC_ORIGIN` and public HTTPS callbacks for `/api/payments/wechat/notify`, `/api/payments/wechat/refund-notify`, and `/api/payments/wechat/transfer-notify`.
- `LEARNINGPYRAMID_WECHAT_PAY_TRANSFER_SCENE_ID` and, when required by the transfer scene, `LEARNINGPYRAMID_WECHAT_PAY_TRANSFER_SCENE_REPORT_INFOS_JSON`.
- `LEARNINGPYRAMID_WECHAT_PAY_APP_SECRET` for the mobile WeChat authorization step used by the desktop QR withdrawal confirmation flow.
- A real WeChat withdrawal confirmation flow with public HTTPS access to `/membership/wechat-payout-confirm`; local tests can use `manual_test` when `LEARNINGPYRAMID_ENABLE_MANUAL_TEST_PAYMENT=true`.

Run these scheduler jobs every few minutes in self-hosted production:

```bash
python tools/reconcile_membership_payments.py --min-age-minutes 5 --limit 100
python tools/settle_membership_commissions.py --limit 200
python tools/reconcile_commission_withdrawals.py --min-age-minutes 2 --limit 100
```

See [docs/membership-selfhost-launch-checklist.md](docs/membership-selfhost-launch-checklist.md) for the full launch checklist and verification flow.

If you need a simple local fallback or a compatibility path, SQLite is still supported:

```bash
LEARNINGPYRAMID_SQL_BACKEND=sqlite
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

The hosted stack now expects `LEARNINGPYRAMID_MEDIA_ACCESS_TOKEN_SECRET` to be set to a real secret in `.env`. Hosted runtime defaults to `LEARNINGPYRAMID_ALLOW_SIGNUP=false`, `LEARNINGPYRAMID_REQUIRE_SIGNUP_INVITE=true`, and the shipped self-host example also defaults to `LEARNINGPYRAMID_SECURE_COOKIES=true`; if you intentionally enable sign-up, fresh deployments should set `LEARNINGPYRAMID_BOOTSTRAP_SUPER_ADMIN_EMAILS` first so the initial admin can register without an invite, clear that allowlist afterward if you do not want it to remain a break-glass `super_admin` mapping, and truly free public registration should also turn on `LEARNINGPYRAMID_ENABLE_PASSWORD_RESET=true`, `LEARNINGPYRAMID_ENABLE_EMAIL_VERIFICATION=true`, and `LEARNINGPYRAMID_ENABLE_SIGNUP_HUMAN_CHECK=true` with `LEARNINGPYRAMID_SMTP_*`, `LEARNINGPYRAMID_PUBLIC_ORIGIN`, and `LEARNINGPYRAMID_ALTCHA_HMAC_SECRET` configured.

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

## Frontend automation

Rendered frontend automation is documented in [docs/frontend-automation.md](docs/frontend-automation.md). The required local gate is:

```powershell
pnpm --dir frontend install
pnpm --dir frontend exec playwright install chromium
pnpm --dir frontend build
pnpm --dir frontend test:e2e
```

The existing `tests/test_frontend_*.py` checks remain supplemental static guards; they are not a substitute for the rendered Playwright journeys.

## Data location

By default, user data is stored under:

- Windows: `%LOCALAPPDATA%\LearningPyramid\learningpyramid_store.sqlite3`
- macOS: `~/Library/Application Support/LearningPyramid/learningpyramid_store.sqlite3`
- Linux: `~/.local/share/learningpyramid/learningpyramid_store.sqlite3`

Overrides:

- `LEARNINGPYRAMID_SQL_BACKEND`: `sqlite` or `postgres`
- `LEARNINGPYRAMID_STORE_DB_PATH`: full path to the SQLite store file
- `LEARNINGPYRAMID_AUTH_DB_PATH`: full path to the SQLite auth file
- `LEARNINGPYRAMID_REQUIRE_SIGNUP_INVITE`: keep hosted sign-up invite-only unless you intentionally want free public registration
- `LEARNINGPYRAMID_BOOTSTRAP_SUPER_ADMIN_EMAILS`: comma-separated bootstrap admin emails that may register without an invite code and will retain `super_admin` on startup while listed
- `LEARNINGPYRAMID_ENABLE_PASSWORD_RESET`: enables SMTP-backed password recovery for hosted auth
- `LEARNINGPYRAMID_PASSWORD_RESET_TOKEN_TTL_MINUTES`: password reset link lifetime in minutes
- `LEARNINGPYRAMID_ENABLE_EMAIL_VERIFICATION`: sends a verification email after sign-up and blocks login until the mailbox is confirmed
- `LEARNINGPYRAMID_EMAIL_VERIFICATION_TOKEN_TTL_MINUTES`: email verification link lifetime in minutes
- `LEARNINGPYRAMID_ENABLE_SIGNUP_HUMAN_CHECK`: requires an ALTCHA proof-of-work challenge before hosted sign-up
- `LEARNINGPYRAMID_ALTCHA_HMAC_SECRET`: server-side secret used to sign and validate ALTCHA sign-up challenges
- `LEARNINGPYRAMID_ALTCHA_CHALLENGE_URL`: optional public challenge endpoint URL; defaults to `/api/auth/human-check/challenge`
- `LEARNINGPYRAMID_ALTCHA_ALGORITHM`: optional ALTCHA algorithm override; defaults to `SHA-256`
- `LEARNINGPYRAMID_ALTCHA_COST`: optional proof-of-work cost; defaults to `1000`
- `LEARNINGPYRAMID_ALTCHA_CHALLENGE_TTL_SECONDS`: optional challenge lifetime in seconds; defaults to `600`
- `LEARNINGPYRAMID_SMTP_HOST`: SMTP host used for password reset and email verification mail
- `LEARNINGPYRAMID_SMTP_PORT`: SMTP port used for password reset mail
- `LEARNINGPYRAMID_SMTP_USERNAME`: optional SMTP username
- `LEARNINGPYRAMID_SMTP_PASSWORD`: optional SMTP password
- `LEARNINGPYRAMID_SMTP_USE_SSL`: connect with implicit SSL
- `LEARNINGPYRAMID_SMTP_USE_STARTTLS`: upgrade plaintext SMTP with STARTTLS
- `LEARNINGPYRAMID_SMTP_FROM_EMAIL`: sender address for password reset and email verification mail
- `LEARNINGPYRAMID_SMTP_FROM_NAME`: optional sender display name for password reset and email verification mail
- `LEARNINGPYRAMID_SMTP_TIMEOUT_SECONDS`: SMTP connect/send timeout in seconds
- `LEARNINGPYRAMID_POSTGRES_DSN`: PostgreSQL DSN used when `LEARNINGPYRAMID_SQL_BACKEND=postgres`
- `LEARNINGPYRAMID_STORE_POSTGRES_DSN`: optional override for the core store DSN
- `LEARNINGPYRAMID_AUTH_POSTGRES_DSN`: optional override for the auth store DSN
- `LEARNINGPYRAMID_LOG_LEVEL`: application log level, default `INFO`
- `LEARNINGPYRAMID_POSTGRES_CONNECT_TIMEOUT`: connect timeout in seconds
- `LEARNINGPYRAMID_POSTGRES_POOL_ACQUIRE_TIMEOUT`: pool acquire timeout in seconds
- `LEARNINGPYRAMID_POSTGRES_POOL_MIN_SIZE`: pool warm size
- `LEARNINGPYRAMID_POSTGRES_POOL_MAX_SIZE`: pool max size
- `LEARNINGPYRAMID_POSTGRES_STATEMENT_TIMEOUT_MS`: PostgreSQL statement timeout
- `LEARNINGPYRAMID_POSTGRES_LOCK_TIMEOUT_MS`: PostgreSQL lock timeout
- `LEARNINGPYRAMID_POSTGRES_IDLE_IN_TX_TIMEOUT_MS`: PostgreSQL idle-in-transaction timeout
- `LEARNINGPYRAMID_DATA_DIR`: base directory for LearningPyramid runtime data
- `LEARNINGPYRAMID_PROJECTS_ROOT`: root directory used when creating new projects; default is `LearningPyramid/data`
- Self-host compose mounts `./data/selfhost` at both `/data` and `/app/data` so runtime databases, existing project roots, and uploaded recall-point images stay persistent across container rebuilds.

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

For PostgreSQL integration tests, start a disposable database and point `LEARNINGPYRAMID_TEST_POSTGRES_DSN` at it:

```bash
docker compose -f docker-compose.postgres.yml --env-file .env up -d
LEARNINGPYRAMID_TEST_POSTGRES_DSN=postgresql://learningpyramid:learningpyramid@127.0.0.1:15432/learningpyramid_test python -m pytest tests/test_postgres_runtime.py tests/test_postgres_hosted_api.py -q
```

## Runtime health and observability

Hosted mode now exposes:

- `GET /api/health/live`: liveness probe, only checks the process is serving HTTP
- `GET /api/health`: readiness probe, checks runtime mode, SQL backend, store health, auth health, and returns `503` when degraded
- `GET /api/system/runtime`: structured runtime status for backend/auth/pool inspection; requires authentication when `LEARNINGPYRAMID_ENABLE_AUTH=true`

Every API response now includes `X-Request-ID`, and request logs include request path, status, and latency.

## Backup, restore, and rollback

Before switching a runtime to PostgreSQL or doing a risky migration, capture a runtime bundle:

```powershell
python tools/backup_runtime_bundle.py runtime-backup.json --include-media --media-root ./data/selfhost --verify
```

To restore that bundle into the currently configured runtime:

```powershell
python tools/restore_runtime_bundle.py runtime-backup.json --dry-run
python tools/restore_runtime_bundle.py runtime-backup.json --confirm-replace --target-media-root ./data/selfhost
```

Recommended rollback flow:

1. Create a runtime backup bundle from the current source runtime.
2. Run `tools/migrate_sqlite_to_postgres.py` against an empty PostgreSQL database.
3. Start the app with `LEARNINGPYRAMID_SQL_BACKEND=postgres` and verify `/api/health`, login, and project access.
4. If verification fails, point the app back to the previous runtime or restore the backup bundle into a clean target runtime.

## Subtitle Files

播放器字幕和 AI 文本上下文现在优先且仅使用视频同目录下的同名字幕文件，例如 `lesson.mp4` 会匹配 `lesson.srt`。工作台视频助手可以额外附带当前复述点内容和当前视频帧；如果当前大模型服务不支持图片输入，会明确提示本轮未使用视频帧并改用文本上下文回答。这不改变字幕文件的查找规则。

当前建议至少准备以下格式之一：

- `.srt`
- `.vtt`
- `.ass`
- `.ssa`

如果没有找到同目录同名字幕文件，产品不会再自动回退到后端 `ffmpeg` 或浏览器 `ffmpeg.wasm` 生成转写。

## Public Subtitle Tool

如果你想给公开视频目录批量补字幕，可以构建独立的 Windows 下载工具：

```powershell
python tools/build_subtitle_tool_windows.py --bootstrap-packaging-venv
```

构建完成后会在仓库根目录的 `public-downloads/` 下生成：

- `LearningPyramid-subtitle-tool-...-windows-x64.zip`
- `catalog.json`

公网版首页会通过 `GET /api/system/public-downloads` 读取这份清单，并把 ZIP 暴露到 `/downloads/...`。默认服务端会优先查找：

- `LEARNINGPYRAMID_PUBLIC_DOWNLOADS_DIR`
- `public-downloads/`
- `release/public-downloads/`

自托管同步脚本默认不会重复上传 `public-downloads/`，但会保留服务器上已经存在的这份目录；当你想首次发布或刷新字幕工具下载包时，再使用 `Sync-Selfhost-Server.bat -IncludePublicDownloads`。

这个小工具本身会内置 `ffmpeg`、`whisper.cpp` 和默认 `ggml-base.bin` 模型。当前公开入口只引导本地目录字幕生成：工具离线扫描本机视频目录，并在视频旁边生成同名 `.srt` 字幕文件。百度网盘项目模式相关底层参数仍保留在工具代码里，但当前产品 UI 和公开使用说明不暴露该路径。

字幕工具支持为本地课程目录生成手机离线课程包。手机端通过“离线课程包”入口连接电脑端临时局域网服务，主动下载视频、字幕和 manifest 到 App 私有课程库。该能力不扫描手机系统文件，不写公共目录，不做公网中继，课程包必须绑定线上学科和 scoped project。

# 后端部署与运行

更新时间：2026-05-13

本文记录当前后端运行、部署、数据位置和运维入口。更细的命令示例仍可参考仓库根目录 `README.md`。

## 本地 release 模式

release 模式使用单个 FastAPI 后端进程：

- 默认地址：`http://127.0.0.1:8001/`
- 后端入口：`adapter.main:app`
- 启动脚本：`LearningPyramid.bat`
- 停止脚本：`LearningPyramid-stop.bat`
- 前端来源：已构建的 `frontend/dist`

准备步骤：

```powershell
pip install -r requirements.txt
pnpm --dir frontend install
pnpm --dir frontend build
LearningPyramid.bat
```

## 开发模式

需要前端热更新和 Vite dev server 时使用：

```powershell
LearningPyramid.dev.bat
```

开发模式不等同于 release / self-host 运行形态。涉及部署、静态前端服务、健康检查、认证 cookie、反向代理等问题时，应以 release / self-host 形态验证。

## 自托管 Docker

自托管入口文件：

- `Dockerfile.selfhost`
- `docker-compose.selfhost.yml`
- `docker-compose.selfhost.postgres.yml`
- `docker-compose.selfhost.proxy.yml`
- `Caddyfile.selfhost`
- `.env.selfhost.example`

PostgreSQL 是当前推荐的自托管生产路径：

```bash
cp .env.selfhost.example .env
docker compose \
  -f docker-compose.selfhost.yml \
  -f docker-compose.selfhost.postgres.yml \
  --env-file .env \
  up --build
```

如果需要 Caddy 反向代理和 TLS：

```bash
docker compose \
  -f docker-compose.selfhost.yml \
  -f docker-compose.selfhost.postgres.yml \
  -f docker-compose.selfhost.proxy.yml \
  --env-file .env \
  up --build
```

SQLite 仍支持本地或简单单机运行：

```bash
LEARNINGPYRAMID_SQL_BACKEND=sqlite
docker compose -f docker-compose.selfhost.yml --env-file .env up --build
```

## 端口、代理与健康检查

容器内服务监听 `8001`。

常用环境变量：

- `LEARNINGPYRAMID_PORT`
- `LEARNINGPYRAMID_BIND_HOST`
- `LEARNINGPYRAMID_PUBLIC_HOST`
- `LEARNINGPYRAMID_PUBLIC_ORIGIN`
- `LEARNINGPYRAMID_ALLOWED_ORIGINS`
- `LEARNINGPYRAMID_TRUSTED_HOSTS`
- `LEARNINGPYRAMID_PROXY_HEADERS`
- `LEARNINGPYRAMID_FORWARDED_ALLOW_IPS`
- `LEARNINGPYRAMID_ENABLE_API_DOCS`：生产默认关闭；设为 `true` 时暴露 `/api/docs`、`/api/openapi.json` 和 `/api/redoc`。
- `LEARNINGPYRAMID_MEMBERSHIP_REFUND_WINDOW_MINUTES`：会员订单可发起退款窗口，默认 1440 分钟。
- `LEARNINGPYRAMID_MEMBERSHIP_COMMISSION_REFUND_WINDOW_MINUTES`：邀请佣金退款等待窗口，默认 1440 分钟。

健康检查：

- `GET /api/health/live`：进程存活。
- `GET /api/health`：运行时就绪状态。
- `GET /api/system/runtime`：运行时详情，认证开启时需要登录。

## 数据与持久化

SQLite 默认数据位置：

- Windows：`%LOCALAPPDATA%\LearningPyramid\learningpyramid_store.sqlite3`
- macOS：`~/Library/Application Support/LearningPyramid/learningpyramid_store.sqlite3`
- Linux：`~/.local/share/learningpyramid/learningpyramid_store.sqlite3`

主要数据环境变量：

- `LEARNINGPYRAMID_SQL_BACKEND`：`sqlite` 或 `postgres`。
- `LEARNINGPYRAMID_STORE_DB_PATH`：SQLite store 路径。
- `LEARNINGPYRAMID_AUTH_DB_PATH`：SQLite auth 路径。
- `LEARNINGPYRAMID_POSTGRES_DSN`：PostgreSQL DSN。
- `LEARNINGPYRAMID_STORE_POSTGRES_DSN`：core store PostgreSQL DSN 覆盖。
- `LEARNINGPYRAMID_AUTH_POSTGRES_DSN`：auth store PostgreSQL DSN 覆盖。
- `LEARNINGPYRAMID_DATA_DIR`：运行时数据根目录。
- `LEARNINGPYRAMID_PROJECTS_ROOT`：新项目根目录。

self-host compose 当前把 `./data/selfhost` 同时挂载到 `/data` 和 `/app/data`，把 `./data/postgres` 挂载为 PostgreSQL 数据目录。

## 会员支付、佣金与提现调度

生产环境不能只依赖前端轮询刷新支付状态。会员资金链路需要后台调度任务持续推进：

- `tools/reconcile_membership_payments.py`：对账待确认会员支付。
- `tools/settle_membership_commissions.py`：佣金退款等待窗口结束后，把符合条件的邀请佣金从 `pending` 结算为 `settled`。
- `tools/reconcile_commission_withdrawals.py`：对账微信提现中的转账状态。

self-host 线上环境应通过 cron、systemd timer 或等价调度器定期运行：

```bash
python tools/reconcile_membership_payments.py --min-age-minutes 5 --limit 100
python tools/settle_membership_commissions.py --limit 200
python tools/reconcile_commission_withdrawals.py --min-age-minutes 2 --limit 100
```

## 数据库迁移

PostgreSQL schema 通过 `schema_migrations` 记录版本。

应用迁移：

```powershell
python tools/apply_postgres_migrations.py --postgres-dsn postgresql://user:pass@localhost:5432/learningpyramid
```

查看或检查迁移状态：

```powershell
python tools/apply_postgres_migrations.py --postgres-dsn postgresql://user:pass@localhost:5432/learningpyramid --status
python tools/apply_postgres_migrations.py --postgres-dsn postgresql://user:pass@localhost:5432/learningpyramid --check
```

当前 store 迁移会补齐学科材料关系表、把 `subject_material_collection_index.initialized` 规范为 BOOLEAN，并确保 `project_snapshots.snapshot_json` 非空壳列存在。迁移 12 会对已应用早期 relationship migration 的数据库再次幂等规范 `initialized`。迁移前仍必须备份目标 PostgreSQL。

从 SQLite 导出或迁移到 PostgreSQL：

```powershell
python tools/export_sqlite_to_postgres.py --output learningpyramid-postgres.sql
python tools/migrate_sqlite_to_postgres.py --postgres-dsn postgresql://user:pass@localhost:5432/learningpyramid
```

检查或修复 PostgreSQL 学科材料关系：

```powershell
python tools/repair_subject_material_relationship_index.py --postgres-dsn postgresql://user:pass@localhost:5432/learningpyramid
python tools/repair_subject_material_relationship_index.py --postgres-dsn postgresql://user:pass@localhost:5432/learningpyramid --apply
```

该脚本默认只输出 dry-run 计划和完整性问题；执行 `--apply` 前必须先完成运行时备份。它只恢复可由 active subject、active material project、`subject_id`、`scoped_project_id` 和受支持 `projectType` 确定的数据，不在请求期猜测关系。

## 备份、恢复与回滚

创建运行时备份：

```powershell
python tools/backup_runtime_bundle.py runtime-backup.json --include-media --media-root ./data/selfhost --verify
```

恢复前预检查：

```powershell
python tools/restore_runtime_bundle.py runtime-backup.json --dry-run
```

确认替换当前运行时数据：

```powershell
python tools/restore_runtime_bundle.py runtime-backup.json --confirm-replace --target-media-root ./data/selfhost
```

切换数据库后至少验证：

- `GET /api/health`
- 登录流程
- 项目列表和项目访问

## 自托管同步

Windows 服务器同步入口：

```powershell
Sync-Selfhost-Server.bat
```

部署 key 显式管理入口：

```powershell
Install-Selfhost-Server-SshKey.bat -ReplaceExistingKey -NoKeyPassphrase
```

同步脚本会检查远端 `.env`、部署当前构建，并运行 readiness / public smoke check。

## 后端验证命令

后端 release gate：

```powershell
python tools/verify_backend_release_gate.py --scope restart
python tools/verify_backend_release_gate.py --scope identity
python tools/verify_backend_release_gate.py --scope storage --postgres-dsn postgresql://user:pass@localhost:5432/learningpyramid_test
```

`restart` 会创建学科材料工作台、保存、重新构造后端运行时，并确认同一 `{subjectId, scopedProjectId}` 能重新解析到同一个内部项目。`identity` 会创建本地 scoped workspace 样本，复用 scoped route、scoped id 和 backend boundary 检查，并报告 `subjectId`、`scopedProjectId`、`internalProjectId` 诊断字段是否可用；如果没有任何 scoped project 样本被验证，该 gate 必须失败。`storage` 是真实 PostgreSQL 迁移与重启 smoke；如果没有传入 DSN，也没有设置 `LEARNINGPYRAMID_TEST_POSTGRES_DSN`、`LEARNINGPYRAMID_STORE_POSTGRES_DSN` 或 `LEARNINGPYRAMID_POSTGRES_DSN`，该 gate 必须失败并报告未完成，不能算通过。

GitHub Actions 的 `Backend CI` workflow 现在也会在 PostgreSQL job 里强制跑这三个 scope，避免只靠本地记忆执行。

后端边界检查：

```powershell
python tools/verify_backend_boundaries.py
```

记录既有边界风险而不隐藏输出：

```powershell
python tools/verify_backend_boundaries.py --report-only
```

基础编译检查：

```powershell
python -m compileall -q backend adapter tests tools
```

如果运行 `compileall` 生成了 `__pycache__`，清理生成物后再提交。

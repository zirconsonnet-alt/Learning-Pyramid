# Current Change

更新时间：2026-05-11

## 1. 当前用户要求

- 工作区全部提交。
- 同步线上服务器。
- 删除或确认线上测试账号 `3873207721@qq.com` 不再占用注册邮箱。
- 修复自托管同步时 Windows CRLF env overlay 污染远端 `.env` 的问题。
- 修复自托管 Docker 构建缓存边界，避免前端 fingerprint 变化触发 Python 依赖重装。
- 修正本机部署 overlay 中 PyPI 包源变量命名，使用现行 `LEARNINGPYRAMID_PIP_*`。

## 2. 本次实际修改文件

- `AGENTS.md`
- `backend/repositories/postgres_persistence.py`
- `Dockerfile.selfhost`
- `docker-compose.selfhost.yml`
- `docs/api.md`（删除）
- `docs/auth-and-permissions.md`
- `docs/current-change.md`
- `docs/data-model.md`
- `docs/deployment.md`
- `docs/domain-model.md`
- `docs/observability.md`
- `docs/state-machines.md`
- `frontend/src/shell/AppShell.tsx`
- `frontend/src/views/auth/AuthPage.tsx`
- `frontend/src/views/home/ShowcaseChrome.tsx`
- `frontend/tests/e2e/ai-chat.spec.ts`
- `frontend/tests/e2e/auth-membership-admin.spec.ts`
- `frontend/tests/e2e/workbench-review.spec.ts`
- `frontend/tests/fixtures/mock-api.ts`
- `tests/test_postgres_persistence_system_state.py`
- `tests/test_repair_project_material_source_binding_index.py`
- `tools/sync_selfhost_server.ps1`
- `tools/repair_project_material_source_binding_index.py`

## 3. 每个文件为什么修改

- `AGENTS.md`：明确 `docs/current-change.md` 是当前任务滚动工作单，移除对长期 `docs/api.md` 的硬性依赖。
- `backend/repositories/postgres_persistence.py`：PostgreSQL project snapshot upsert 写入稳定空 JSON 壳，满足旧 `snapshot_json` 非空列。
- `docker-compose.selfhost.yml`、`docs/deployment.md`：补充 `LEARNINGPYRAMID_ENABLE_API_DOCS` 自托管配置入口和说明。
- `Dockerfile.selfhost`：把 `LEARNINGPYRAMID_FRONTEND_DIST_FINGERPRINT` build arg 移到 Python 依赖安装层之后，避免前端产物变化使依赖安装缓存失效。
- `docs/*`：重组长期后端文档，新增认证权限、数据模型、领域模型、可观测性、状态机文档，删除独立 API 文档。
- `frontend/*`：调整应用壳路由上下文、注册页辅助文案和 logo 加载属性，并同步 e2e mock 与断言。
- `tests/*`、`tools/repair_project_material_source_binding_index.py`：补充 PostgreSQL normalized 数据修复入口和相关单元测试。
- `tools/sync_selfhost_server.ps1`：合并远端 `.env` 与 `.env.selfhost.sync` 时去掉输入行尾 `\r`，防止 Windows CRLF 写入容器环境变量。

## 4. 行为语义是否变化

是。PostgreSQL snapshot 写入会保留 `snapshot_json` 的最小非空壳；自托管 API docs 默认关闭但可用环境变量显式打开；注册页不再显示注册后的辅助说明文案。

部署脚本行为也有变化：Windows CRLF 格式的 `.env.selfhost.sync` 不再把 `\r` 写入远端 `.env`。

Docker 构建缓存语义也有变化：前端 fingerprint 只影响最终前端 dist 层，不再影响 Python 依赖安装层。

部署 overlay 使用现行 `LEARNINGPYRAMID_PIP_*` 后，Docker build 能收到配置的 PyPI 镜像参数；不在代码中新增 `PLM_*` 兼容路径。

## 5. 是否做了重构，以及为什么

做了文档结构整理。原因是长期 API 明细改以运行时 OpenAPI 为准，仓库长期文档改为维护领域、数据、权限、状态机、部署与可观测性边界。

## 6. 未修改哪些相关内容，以及为什么

- 未新增 PostgreSQL schema migration：本次只修正 repository 写入旧列的值，不改变 schema。
- 未改变公开 API 参数和返回结构：API 明细以运行时 OpenAPI 为准。
- 未硬编码生产 API docs 开关：通过既有环境变量配置路径暴露。
- 未手工绕过远端 `.env`：同步失败根因在脚本合并边界，修脚本后重新同步。
- 未修改 Python 依赖版本或使用临时包源：第二次同步失败根因是缓存边界错误叠加线上网络慢，修 Dockerfile 缓存边界。
- 未提交 `.env.selfhost.sync`：该文件含生产密钥且被 `.gitignore` 忽略，只作为本机同步 overlay 使用。
- 未移除同步脚本里的 Docker `--no-cache`：这会改变自托管部署的强制干净构建策略，需要单独确认。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：无已知接口契约变更；API docs 暴露受配置影响。
- 架构：文档边界更新，运行时模块边界不变。
- 部署：自托管 compose 新增 `LEARNINGPYRAMID_ENABLE_API_DOCS` 传递。
- 部署脚本：env overlay 合并会归一化 CRLF 行尾。
- Docker 构建：Python 依赖层不再受前端 fingerprint 影响。
- 本机部署 overlay：使用 `LEARNINGPYRAMID_PIP_*` 变量把 PyPI 镜像传入 Docker build。
- 数据结构：schema 不变；PostgreSQL 写入语义更新。
- UI：注册页辅助文案减少，应用壳上下文匹配调整。
- 测试：新增/更新后端单元测试和前端 e2e 断言。

## 8. 当前风险点和不确定项

- 工作区包含较多已存在改动，本轮按用户要求全部提交。
- 删除 `docs/api.md` 后，API 细节维护依赖运行时 OpenAPI；长期文档不再保存接口明细。
- 已确认一次同步失败根因：CRLF overlay 经 `awk` 合并后污染远端 `.env`，导致 PostgreSQL 角色名带 `\r`。已按用户确认修脚本。
- 已确认第二次同步失败根因：Dockerfile 中前端 fingerprint ARG 位于 pip 安装层之前，导致前端变动触发 Python 依赖重装；线上 PyPI 下载慢/不稳定时部署卡住。
- 补充发现：远端 `.env` 里已有旧 `PLM_PIP_*` 包源配置，但 compose 只读取现行 `LEARNINGPYRAMID_PIP_*`；本机 overlay 已补现行变量，不新增旧命名兼容。
- `3873207721@qq.com` 在线上 `users` 表中计数为 0，未执行删除语句。
- 补充发现：`tools/sync_selfhost_server.ps1` 当前使用 `compose build --no-cache`，因此 Dockerfile 缓存层调整不会减少同步脚本路径下的 pip 安装次数；若要启用缓存，需要确认部署策略。

## 9. 仍需用户确认的问题

无。用户已明确要求全部提交并同步线上服务器。

## 10. 验证结果

- `python tools/verify_backend_boundaries.py`：通过，输出 `backend boundary guards verified`。
- `python -m compileall -q backend adapter tests tools`：通过。
- `python -m unittest tests.test_postgres_persistence_system_state tests.test_repair_project_material_source_binding_index`：通过，9 tests。
- `pnpm --dir frontend build`：通过；Vite 输出 chunk size warning。
- `python -m unittest discover -s tests`：通过，77 tests。
- `pnpm --dir frontend test:e2e`：通过，26 tests。
- `git diff --check`：通过；仅提示多个文件下次 Git 触碰时 LF 会替换为 CRLF。
- 首次线上同步失败：远端 `psql` 报 `role "learningpyramid\r" does not exist`。
- CRLF 修复验证：远端临时样本合并后 `cr_count=0`，输出变量无 `\r`。
- `tools/sync_selfhost_server.ps1` PowerShell 解析：通过。
- 修复后 `python tools/verify_backend_boundaries.py`：通过，输出 `backend boundary guards verified`。
- 修复后 `git diff --check`：通过；仅提示换行符。
- 修复后 `pnpm --dir frontend build`：通过；Vite 输出 chunk size warning。
- 第二次线上同步失败：远端 Docker build 在 `pip install -r requirements.txt` 阶段失败/卡住；旧 app 容器仍健康运行。
- 本地 Docker build 未运行成功：Docker Desktop 未启动，无法连接 `dockerDesktopLinuxEngine`。
- Dockerfile 修复后 `python tools/verify_backend_boundaries.py`：通过。
- Dockerfile 修复后 `python -m unittest tests.test_backend_legacy_cleanup tests.test_postgres_persistence_system_state tests.test_repair_project_material_source_binding_index`：通过，43 tests。
- Dockerfile 修复后 `git diff --check`：通过；仅提示换行符。
- Dockerfile 修复后 `python -m unittest discover -s tests`：通过，77 tests。
- Dockerfile 修复后 `pnpm --dir frontend build`：通过；Vite 输出 chunk size warning。
- 线上同步：通过；Docker build 收到 `LEARNINGPYRAMID_PIP_*` 参数并使用配置的 PyPI 镜像。
- 同步脚本当前仍使用 `--no-cache`，因此同步路径的远端 Docker build 仍会重新执行 pip 安装；是否改为缓存构建需单独确认。
- 同步脚本 smoke check：`/api/system/capabilities`、`/api/system/public-downloads`、服务器目录前端 asset、运行容器前端 asset、公开站点前端 asset 均通过。
- 独立线上健康检查：`https://plm.xuebao.chat/api/health` 返回 `ok`。
- 独立远端状态检查：远端 `.env` 的 `env_cr_count=0`，app 与 postgres 容器均为 `healthy`。
- 线上测试账号确认：`users.email = '3873207721@qq.com'` 计数为 0，未执行删除。

## 11. 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

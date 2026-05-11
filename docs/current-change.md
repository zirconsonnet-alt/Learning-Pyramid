# Current Change

更新时间：2026-05-11

## 1. 当前用户要求

- 工作区全部提交。
- 同步线上服务器。

## 2. 本次实际修改文件

- `AGENTS.md`
- `backend/repositories/postgres_persistence.py`
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
- `tools/repair_project_material_source_binding_index.py`

## 3. 每个文件为什么修改

- `AGENTS.md`：明确 `docs/current-change.md` 是当前任务滚动工作单，移除对长期 `docs/api.md` 的硬性依赖。
- `backend/repositories/postgres_persistence.py`：PostgreSQL project snapshot upsert 写入稳定空 JSON 壳，满足旧 `snapshot_json` 非空列。
- `docker-compose.selfhost.yml`、`docs/deployment.md`：补充 `LEARNINGPYRAMID_ENABLE_API_DOCS` 自托管配置入口和说明。
- `docs/*`：重组长期后端文档，新增认证权限、数据模型、领域模型、可观测性、状态机文档，删除独立 API 文档。
- `frontend/*`：调整应用壳路由上下文、注册页辅助文案和 logo 加载属性，并同步 e2e mock 与断言。
- `tests/*`、`tools/repair_project_material_source_binding_index.py`：补充 PostgreSQL normalized 数据修复入口和相关单元测试。

## 4. 行为语义是否变化

是。PostgreSQL snapshot 写入会保留 `snapshot_json` 的最小非空壳；自托管 API docs 默认关闭但可用环境变量显式打开；注册页不再显示注册后的辅助说明文案。

## 5. 是否做了重构，以及为什么

做了文档结构整理。原因是长期 API 明细改以运行时 OpenAPI 为准，仓库长期文档改为维护领域、数据、权限、状态机、部署与可观测性边界。

## 6. 未修改哪些相关内容，以及为什么

- 未新增 PostgreSQL schema migration：本次只修正 repository 写入旧列的值，不改变 schema。
- 未改变公开 API 参数和返回结构：API 明细以运行时 OpenAPI 为准。
- 未硬编码生产 API docs 开关：通过既有环境变量配置路径暴露。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：无已知接口契约变更；API docs 暴露受配置影响。
- 架构：文档边界更新，运行时模块边界不变。
- 部署：自托管 compose 新增 `LEARNINGPYRAMID_ENABLE_API_DOCS` 传递。
- 数据结构：schema 不变；PostgreSQL 写入语义更新。
- UI：注册页辅助文案减少，应用壳上下文匹配调整。
- 测试：新增/更新后端单元测试和前端 e2e 断言。

## 8. 当前风险点和不确定项

- 工作区包含较多已存在改动，本轮按用户要求全部提交。
- 删除 `docs/api.md` 后，API 细节维护依赖运行时 OpenAPI；长期文档不再保存接口明细。

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
- 线上同步和健康检查：待执行。

## 11. 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

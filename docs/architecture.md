# 后端架构

更新时间：2026-05-13

本文只记录当前仓库可验证的后端结构和边界。未确认的重构方向、兼容策略和未来计划不写入本文。

## 运行形态

后端由 `adapter/main.py` 创建 FastAPI 应用：

- 所有业务 API 挂在 `/api` 前缀下。
- `adapter/main.py` 注册请求 ID、日志、认证、CORS、TrustedHost 和异常处理。
- release / self-host 模式下，FastAPI 同时提供 `frontend/dist` 静态前端和 `/downloads/...` 公共下载文件。
- `GET /api/health/live` 是存活检查，`GET /api/health` 是就绪检查。

依赖入口在 `adapter/deps.py`：

- `get_api()` 创建并缓存 `SystemAPI`。
- `SystemAPI` 包装 `InMemorySystem`。
- `InMemorySystem` 使用 `create_persist_store()` 选择 SQLite 或 PostgreSQL 持久化实现。
- auth、membership、commission、payment 等运行时 store/service 也在该文件集中创建并缓存。

## 模块职责

`adapter/`

- HTTP 适配层。
- `adapter/main.py` 负责应用装配、中间件、路由挂载和前端静态文件服务。
- `adapter/routers/` 负责请求参数、请求体、依赖注入和响应 DTO 适配。
- `adapter/scoped_projects.py` 是 scoped project identity 的适配边界，负责把公开的 `{subjectId, scopedProjectId}` 解析为后端内部 project id。

`backend/models/`

- 领域模型、枚举、错误、ID 类型和结构化数据对象。
- 不负责 HTTP 请求处理。

`backend/system/`

- 后端行为层和运行时能力。
- `backend/system/api.py` 暴露 `SystemAPI`，是路由调用后端行为的主要入口。
- `backend/system/inmemory_system.py` 承载当前核心运行时状态和领域操作。
- `backend/system/sql_backend.py` 根据 `LEARNINGPYRAMID_SQL_BACKEND` 选择 SQLite 或 PostgreSQL。
- `backend/system/subject_material_recovery.py` 负责学科材料关系的确定性恢复计划和完整性问题建模，不参与请求期兜底解析。
- auth、membership、media、ASR、LLM、public downloads、runtime feature/config 等运行时能力位于该目录下。

`backend/repositories/`

- 持久化接口与 SQLite / PostgreSQL 实现。
- `persistence_interfaces.py` 定义持久化边界。
- `sqlite_persistence.py` 和 `postgres_persistence.py` 是具体存储实现。
- subject-material relationship repository 是学科材料身份的持久化边界，SQLite/PostgreSQL native load 都从该关系表恢复 `studyMaterials` 和 `subjectMaterialLink`。

`tools/`

- 本地运行、构建、自托管同步、数据库迁移、备份恢复、边界验证等运维脚本。

## 请求数据流

典型业务请求路径：

1. FastAPI app 接收请求。
2. `request_context_middleware` 生成或传播 `X-Request-ID`，并记录请求日志。
3. `auth_middleware` 根据 `LEARNINGPYRAMID_ENABLE_AUTH` 和公开路径规则决定是否要求认证。
4. router 解析请求并调用公开的 `SystemAPI` 方法。
5. scoped project 路由通过 `resolve_scoped_project()` 把公开 scoped project id 解析成内部 project id。
6. `SystemAPI` 执行业务行为并读写当前持久化 store。
7. router 把结果映射成 HTTP 响应。

## 边界规则

当前后端边界规则以 `specs/014-backend-boundaries-guards/contracts/backend-boundary-guards.md` 为准：

- `BBG001 Transport Boundary`：router 只做 HTTP 适配，不直接访问后端存储内部或私有 helper。
- `BBG002 Scoped Identity Boundary`：公开 scoped project id 必须通过 `adapter/scoped_projects.py` 解析后才能作为内部 project id 使用。
- `BBG003 Authorization Ownership Boundary`：用户 ownership 绑定 subject 级资源，不绑定 storage-only project id。
- `BBG004 Atomic Mutation Boundary`：跨 project 生命周期写入必须由 approved atomic behavior owner 统一处理。
- `BBG005 Migration Risk Containment`：已有 migration / compatibility 行为必须被记录和限制，不能扩散成新功能模式。

## 已知边界风险

`specs/014-backend-boundaries-guards/research.md` 记录了当前仓库中仍需后续决策的边界风险，包括：

- 部分 media / materials router 仍直接调用 `SystemAPI` 私有 helper 或访问 `api.sys`。
- 一个 scoped subject-context route 尚未使用 `resolve_scoped_project`。
- 一个 friends router 注释中仍提到历史 study-day 记录的 fallback 行为。

这些风险不是本文批准的架构模式。后续修改相关路径时，应先处理或确认对应边界决策。

## 维护约束

- 新 router 只能调用公开 `SystemAPI` 方法或已批准的 adapter boundary helper。
- 新 scoped project API 必须使用 `resolve_scoped_project()`。
- 新业务行为不应绕过 `SystemAPI` 直接读写 repository 或 store。
- 新后端改动应运行 `python tools/verify_backend_boundaries.py`，需要记录既有风险时使用 `--report-only`。

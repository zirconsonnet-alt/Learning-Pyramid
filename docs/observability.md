# 可观测性

更新时间：2026-05-10

本文记录当前系统健康检查、日志、请求追踪和排障入口。接口字段以运行时 OpenAPI 为准，本文不维护 API 明细。

## 健康检查

当前后端暴露两个主要健康检查：

- `GET /api/health/live`：进程存活检查，只确认 HTTP 服务正在响应。
- `GET /api/health`：就绪检查，聚合 runtime、store、auth 等状态；不可用时返回 `503`。

`/api/health` 返回的主要信息包括：

- app 名称和版本。
- runtime mode。
- public origin、allowed origins、trusted hosts。
- runtime features。
- SQL backend。
- core store health。
- auth store health。
- LLM / story generation 配置状态。
- 总体 `status`：`ok` 或 `degraded`。

## Runtime Status

`GET /api/system/runtime` 提供结构化运行时详情。认证开启时，该接口需要登录。

runtime status 的数据来源是 `adapter/runtime_status.py`，核心检查包括：

- `current_runtime_features()`
- `current_sql_runtime_config()`
- `SystemAPI.get_store_health()`
- `AuthStore.healthcheck()`
- 用户级 LLM 配置状态

## Request ID

每个请求都会生成或传播 `X-Request-ID`：

- 如果请求头已有 `X-Request-ID`，后端会使用该值。
- 如果没有，后端生成新的 UUID hex。
- 响应头会返回 `X-Request-ID`。
- 错误响应会尽量带上同一个 request id。

排障时应优先用 request id 关联客户端错误、服务端日志和 provider 回调。

## HTTP 日志

后端 HTTP logger 名称为 `learningpyramid.http`。

启动时会记录：

- app 名称和版本。
- ready 状态。
- app mode。
- SQL backend。
- auth 是否启用。
- ASR 是否启用。
- public origin。

每个请求会记录：

- request id。
- method。
- path。
- status。
- duration_ms。

异常请求会记录 `request_failed` 并输出异常堆栈。

日志等级由 `LEARNINGPYRAMID_LOG_LEVEL` 控制，默认 `INFO`。

## Hosted Runtime Warnings

hosted 模式启动时会进行部署安全检查。

blocker 会阻止启动，例如：

- hosted 模式使用占位 `LEARNINGPYRAMID_MEDIA_ACCESS_TOKEN_SECRET`。
- 启用受保护数据目录检查时发现危险或异常数据路径。

warning 会写入日志，例如：

- 开启公开注册但未配置密码恢复、邮箱验证或人机校验。
- 关闭登录/注册限流。
- hosted 模式开启 manual test payment。
- 关闭 secure cookies。
- 缺少 public origin 或 trusted hosts。
- hosted 模式开启 API docs。
- PostgreSQL 密码仍像示例值。
- WeChat Pay 配置不完整。

## Store Health

core store health 由 `SystemAPI.get_store_health()` 返回。

auth store health 由 `AuthStore.healthcheck()` 返回：

- SQLite auth 检查本地数据库可访问。
- PostgreSQL auth 检查连接池、迁移状态和关键表。

PostgreSQL health 会包含预期迁移、已应用迁移、pending 和 conflict 信息。pending 或 conflict 应视为部署风险，不应隐藏。

## 对账与业务可观测性

会员佣金和提现域有专门的运行记录：

- `payout_provider_events`：provider 回调或同步事件。
- `reconciliation_runs`：对账任务运行结果。
- `reconciliation_warnings`：需要人工处理的对账告警。
- `admin_action_logs`：管理员操作记录。

这些记录是会员支付、退款、提现排障的事实来源，不应被前端展示状态替代。

## 部署验证入口

常用验证命令记录在 `docs/deployment.md`。当前关键入口包括：

```powershell
python tools/verify_backend_boundaries.py
python -m compileall -q backend adapter tests tools
```

自托管同步脚本会运行 readiness / public smoke check。失败时应保留原始输出，不要把失败包装成成功。

## 维护约束

- 新健康检查或 runtime status 字段必须同步更新本文。
- 新日志字段应保持稳定命名，避免排障脚本和日志检索失效。
- 新 provider 回调必须有 request id 或 provider event id 可追踪。
- 新后台任务应记录运行结果、失败原因和可复查标识。
- 不允许通过隐藏错误输出制造“验证通过”的假象。

# 认证与权限

更新时间：2026-05-10

本文记录当前认证、授权、公开路径和会员门禁规则。接口字段以运行时 OpenAPI 为准，本文不维护 API 明细。

## 运行模式

认证是否启用由 runtime feature 决定：

- `LEARNINGPYRAMID_APP_MODE=hosted` 时默认启用认证。
- local 模式默认不启用认证。
- `LEARNINGPYRAMID_ENABLE_AUTH` 可显式覆盖。

认证开启后，所有 `/api` 请求默认需要 session，除非路径被列为公开 API。

## Session

当前 session 使用 cookie：

- cookie 名称：`plm_session`
- 默认 TTL：`LEARNINGPYRAMID_SESSION_TTL_DAYS`，默认 30 天。
- `HttpOnly`、`SameSite=Lax`。
- `Secure` 由 `LEARNINGPYRAMID_SECURE_COOKIES` 控制。

服务端持久化 session token 哈希，不应把明文 token 当作长期数据记录。

邮箱验证等待态使用 `plm_pending_email_verification` cookie。

## 公开 API 路径

认证开启时，以下路径公开：

- `/api/health`
- `/api/health/live`
- `/api/openapi.json`
- `/api/docs`
- `/api/redoc`
- `/api/system/capabilities`
- `/api/system/public-downloads`
- `/api/guide/demo-media/study-review`
- `/api/payments/wechat/notify`
- `/api/payments/wechat/refund-notify`
- `/api/payments/wechat/transfer-notify`
- `/api/commissions/payout-identity/wechat/mobile-bind`
- `/api/commissions/payout-identity/wechat/bind`
- `/api/commissions/withdrawals/{id}/wechat-confirmation`
- `/api/public/asr-bridge/...`
- `/api/auth/...`

其中 `/api/system/capabilities` 与 `/api/commissions/payout-identity/wechat/bind` 支持可选认证：有合法 session 时会写入 `request.state.auth_user`，没有 session 时仍可继续处理。

## 用户状态

用户状态当前包括：

- `active`
- `suspended`
- `deleted`

用户状态由 auth store 维护，管理端可变更。涉及登录、资料展示和管理查询时，应以 auth store 当前实现为准。

## 全局角色

当前全局角色包括：

- `super_admin`
- `admin`

管理员访问规则：

- `require_admin_user()` 允许 `super_admin` 或 `admin`。
- `require_super_admin_user()` 只允许 `super_admin`。
- 管理端修改用户全局角色需要 `super_admin`。

`LEARNINGPYRAMID_BOOTSTRAP_SUPER_ADMIN_EMAILS` 可把指定邮箱作为启动期超级管理员来源。公开部署后是否保留该 allowlist 属于部署决策。

## 项目访问

项目访问关系存储在 `project_memberships`：

- 当前项目 owner 通过 `AuthStore.add_project_owner(project_id, user_id)` 写入。
- 删除项目相关关系通过 `remove_project_memberships(project_id)` 清理。
- 访问检查通过 `user_has_project_access(user_id, project_id)` 或项目列表过滤完成。

scoped project 路由中，`resolve_scoped_project()` 在认证开启时先确认当前用户能访问 `subjectId`，再把公开 `{subjectId, projectId}` 解析为内部 project id。

权限边界：

- 用户 ownership 绑定 subject 级资源，不应直接绑定 storage-only project id。
- router 不应绕过 scoped project resolver 直接把公开 project id 当内部 id 用。

## 会员门禁

会员门禁由 `require_active_membership()` 表达：

- 先要求当前请求已认证。
- 再通过 membership store 查询当前用户会员摘要。
- `summary.is_active` 为 false 时抛出业务错误。

当前已有部分个人配置、系统能力或付费功能入口使用会员门禁。新增会员功能时，应复用该门禁，不要在前端或 router 中复制会员判断。

## 注册与安全开关

注册相关 runtime feature：

- `LEARNINGPYRAMID_ALLOW_SIGNUP`
- `LEARNINGPYRAMID_REQUIRE_SIGNUP_INVITE`
- `LEARNINGPYRAMID_ENABLE_PASSWORD_RESET`
- `LEARNINGPYRAMID_ENABLE_EMAIL_VERIFICATION`
- `LEARNINGPYRAMID_ENABLE_SIGNUP_HUMAN_CHECK`
- `LEARNINGPYRAMID_ENABLE_AUTH_RATE_LIMITS`

hosted 模式会对明显不安全或未完成配置给出 blocker / warning，例如占位密钥、公开注册缺少邮箱验证、缺少人机校验、关闭安全 cookie、打开 API docs 等。

## 好友与用户关系

好友请求状态当前包括：

- `pending`
- `accepted`
- `rejected`
- `cancelled`

好友关系由 `friend_requests` 和 `friendships` 维护，不属于项目 ownership，也不能替代项目访问授权。

## 维护约束

- 新受保护 API 默认走全局认证中间件，不应在 router 中自建 session 解析。
- 新公开 API 必须显式加入公开路径判断，并说明为什么可公开。
- 新管理员能力必须明确使用 admin 还是 super_admin。
- 新项目级 API 必须使用 scoped project resolver 或等价的已批准边界。
- 新会员能力必须复用 membership store 的 active summary，不应创建前端专用权限分支。

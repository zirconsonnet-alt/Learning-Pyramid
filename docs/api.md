# 后端 API

更新时间：2026-05-10

本文是当前后端 API 的维护索引，不替代运行时 OpenAPI schema。启用 API 文档时，运行中的后端会暴露：

- `GET /api/openapi.json`
- `GET /api/docs`
- `GET /api/redoc`

## 通用规则

- API 根路径是 `/api`。
- 所有 API 响应都会带 `X-Request-ID`。
- 请求日志记录 method、path、status 和 duration。
- `LEARNINGPYRAMID_ENABLE_AUTH=true` 时，除公开路径外的 `/api` 请求必须有有效登录态。
- scoped project API 使用路径形态 `/api/subjects/{subjectId}/projects/{projectId}/...`。
- scoped project API 应通过 `adapter.scoped_projects.resolve_scoped_project` 解析公开 id。

## 公开路径

认证开启时，以下路径仍可公开访问：

- `GET /api/health/live`
- `GET /api/health`
- `GET /api/openapi.json`
- `GET /api/docs`
- `GET /api/redoc`
- `GET /api/system/capabilities`
- `GET /api/system/public-downloads`
- `GET /api/guide/demo-media/study-review`
- `/api/auth/...`
- `POST /api/payments/wechat/notify`
- `POST /api/payments/wechat/refund-notify`
- `POST /api/payments/wechat/transfer-notify`
- `GET /api/commissions/payout-identity/wechat/mobile-bind`
- `POST /api/commissions/payout-identity/wechat/bind`
- `GET /api/commissions/withdrawals/{withdrawalId}/wechat-confirmation`
- `/api/public/asr-bridge/...`

`/api/system/capabilities` 和 `/api/commissions/payout-identity/wechat/bind` 支持可选认证：有登录态时会读取当前用户，没有登录态时仍允许进入对应公开处理。

## 健康与运行时

- `GET /api/health/live`：存活检查，只确认 HTTP 进程可响应。
- `GET /api/health`：就绪检查，返回 runtime、SQL backend、store、auth 等状态；后端降级时返回 `503`。
- `GET /api/system/runtime`：结构化运行时状态；认证开启时需要登录。
- `GET /api/system/data-safety`：读取数据安全状态。
- `POST /api/system/data-safety/check`：触发数据安全检查。

## 认证与用户资料

`adapter/routers/auth.py`

- `GET /api/auth/human-check/challenge`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `POST /api/auth/password-reset/request`
- `POST /api/auth/password-reset/confirm`
- `POST /api/auth/email-verification/request`
- `POST /api/auth/email-verification/confirm`
- `GET /api/auth/email-verification/status`
- `GET /api/auth/baidu-netdisk/callback`

`adapter/routers/profile.py`

- `GET/PATCH /api/profile/me`
- `POST /api/profile/me/password`
- `GET/PUT /api/profile/me/llm-settings`
- `GET/PUT /api/profile/me/asr-settings`
- `GET/PUT /api/profile/me/global-settings`
- `GET/PUT /api/profile/me/learning-plans`
- `GET /api/profile/me/cloud-accounts/baidu-netdisk`
- `POST /api/profile/me/cloud-accounts/baidu-netdisk/connect`
- `DELETE /api/profile/me/cloud-accounts/baidu-netdisk/{accountId}`
- `PUT /api/profile/me/avatar`
- `GET /api/profile/avatar/{userId}`
- `GET /api/users/by-uid/{publicUid}`
- `POST /api/profile/me/study-metrics/sync`

## 项目与素材

`adapter/routers/projects.py`

- `GET/POST /api/subjects`
- `PATCH/DELETE /api/subjects/{subjectId}`
- `GET/POST /api/subjects/{subjectId}/materials`
- `PATCH/DELETE /api/subjects/{subjectId}/materials/{materialId}`
- `GET /api/subjects/{subjectId}/projects/{projectId}/subject-context`
- `GET /api/subjects/{subjectId}/projects/{projectId}/project-config`
- `POST /api/subjects/{subjectId}/projects/{projectId}/roll-up-strategy`
- `POST /api/subjects/{subjectId}/projects/{projectId}/review-recommendation-config`
- `GET /api/subjects/{subjectId}/projects/{projectId}/project-storage-config`
- `GET/POST /api/subjects/{subjectId}/projects/{projectId}/material-source-binding`
- `GET /api/subjects/{subjectId}/projects/{projectId}/audit-log-events`

`adapter/routers/materials.py`

- instance、missing-instance、video-watch-progress API。
- learning object root / node / container / leaf API。
- recall point by instance / learning object API。
- browser local import、filesystem sync、Baidu Netdisk import API。
- learning object export recall-points / ASR API。

## 学习任务、复习与层级

`adapter/routers/learning_tasks.py`

- learning task 创建、读取、编辑。
- learning task node 读取、编辑、binding、recall-points、exports。

`adapter/routers/review.py`

- queue、review task、convergence、review chain、range snapshot。
- recall point 列表、搜索、读取、编辑、删除、review projection。
- review task commit。

`adapter/routers/layers.py`

- layers、aggregation queue、manual roll-up、aggregation events、layer config。

`adapter/routers/push.py`

- review recommendations。
- push candidates。

`adapter/routers/validation.py`

- material reachability validation。
- range recall point resolvability validation。

## 媒体、字幕与 ASR

`adapter/routers/media.py`

- guide demo media。
- media asset upload / stream。
- instance media stream / playback / HLS manifest / HLS segments。
- instance subtitle file。

`adapter/routers/asr.py`

- public ASR bridge asset。
- project / instance ASR。
- audio ASR。
- ASR artifact 读取。

## 系统、LLM、好友、会员与后台

`adapter/routers/system.py`

- capabilities、runtime、data safety、public downloads。
- Pomodoro TTS preview。
- global LLM settings。
- system / scoped project LLM ask、chat completions、debug latest、stream。

`adapter/routers/friends.py`

- friends、friend requests、leaderboard、friend profile。

`adapter/routers/membership.py`

- membership summary、orders、payment callbacks、invite/coupon/commission。
- WeChat payout identity binding、withdrawals、transfer notifications。

`adapter/routers/admin.py`

- admin overview、membership admin、orders、grants、refunds。
- invites、coupons、commissions、payout identities、withdrawals。
- users、user status/roles、activity、audit logs。

## API 维护要求

- 新增公开路径必须同步更新 `adapter/main.py` 的公开路径规则和本文。
- 新增 scoped project route 必须确认是否需要 `resolve_scoped_project()`。
- 新增路由分组时应更新本文的路由索引。
- API 参数、返回值、错误码或鉴权语义发生变化时，必须同步更新本文。

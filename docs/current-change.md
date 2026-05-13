# Current Change

更新时间：2026-05-13

## 1. 当前用户要求

- 微信提现以后没有单独绑定微信流程。
- 只有申请提现时扫码确认收款。
- 删除 `/membership/wechat-payout-bind`，只保留 `/membership/wechat-payout-confirm`。
- 不保留旧路由 redirect、兼容页、0 元纯绑定分支或 legacy API path。

## 2. 本次实际修改文件

- `frontend/src/router.tsx`
- `frontend/src/views/membership/WechatPayoutBindingPage.tsx`
- `frontend/src/views/membership/WechatWithdrawalConfirmationPage.tsx`
- `frontend/src/views/membership/MembershipPage.tsx`
- `frontend/src/ui/api/membership.ts`
- `frontend/src/ui/queries/membership.ts`
- `adapter/main.py`
- `adapter/routers/admin.py`
- `adapter/routers/membership.py`
- `adapter/schemas.py`
- `README.md`
- `docs/auth-and-permissions.md`
- `docs/data-model.md`
- `docs/current-change.md`
- `tests/test_membership_payment_service.py`
- `tests/test_scoped_project_api_boundaries.py`

## 3. 每个文件为什么修改

- `router.tsx`：删除 `/membership/wechat-payout-bind` 路由和旧页面 lazy import，只保留 `/membership/wechat-payout-confirm`。
- `WechatPayoutBindingPage.tsx`：旧单独绑定页面删除，不再作为产品入口。
- `WechatWithdrawalConfirmationPage.tsx`：承接扫码 attempt 参数，负责读取微信授权、完成提现确认 attempt，并创建本次提现。
- `MembershipPage.tsx`：申请提现时启动 withdrawal confirmation attempt；不再启动单独 payout binding。
- `membership.ts` / `queries/membership.ts`：前端 API 和 query 命名改为 withdrawal confirmation attempt；请求体使用 `withdrawalConfirmationAttemptId`。
- `adapter/main.py`：公开 API 白名单改为提现确认 mobile / complete 新路径。
- `adapter/routers/admin.py`：管理后台收款身份 DTO 字段改为 `latestWithdrawalConfirmationAttemptId`，避免对外继续暴露 binding 语义。
- `adapter/routers/membership.py`：二维码、mobile entry、complete path 迁到 withdrawal confirmation 语义；拒绝非正数金额，禁止纯绑定成功返回。
- `adapter/schemas.py`：请求 schema 改成 withdrawal confirmation attempt 命名，`amountCent >= 1`。
- `README.md` / `docs/auth-and-permissions.md`：同步新的提现扫码确认入口和公开 API path。
- `docs/data-model.md`：说明底层 `payout_binding_attempts` 表记录的是微信提现确认扫码 attempt，表名只是早期命名遗留。
- `test_membership_payment_service.py` / `test_scoped_project_api_boundaries.py`：新增边界测试，防止旧 bind 路由、旧 API path、0 元绑定和错误请求体字段回归。

## 4. 行为语义是否变化

- 是。
- 用户不能再单独绑定微信收款身份。
- 只有发起提现时，系统生成扫码确认入口；手机端确认后创建并继续处理这笔提现。
- `/membership/wechat-payout-bind` 不再存在。
- `/membership/wechat-payout-confirm` 同时承接既有提现确认 token 和新扫码 attempt。

## 5. 是否做了重构，以及为什么

- 做了当前提现流程范围内的局部命名重构。
- 目的是把公开路由、API、前端状态和用户文案从 `binding` 收敛为 `withdrawal confirmation`，避免继续误导维护者。
- 未重命名底层 `payout_binding_attempts` 表和 store 类型，因为那会引入数据库迁移；本轮只清理产品入口、公共协议和对外 DTO。

## 6. 未修改哪些相关内容，以及为什么

- 未删除 `payout_identities` / `payout_binding_attempts` 数据表：提现仍需要记录经过微信确认的收款身份和扫码 attempt，直接改表名会扩大为数据迁移。
- 未删除管理后台收款身份展示：后台仍需要展示最终收款身份事实。
- 未保留旧 `/membership/wechat-payout-bind` redirect：用户已确认不要兼容层。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：是，旧 `/commissions/payout-identity/wechat/mobile-bind`、`/bind`、`/binding-attempts` 不再作为公共 path；改为 withdrawal confirmation path。
- 架构：否，仍使用 membership commission store 记录提现确认 attempt 和收款身份。
- 部署：是，生产回调/前端 public origin 需要使用 `/membership/wechat-payout-confirm`。
- 数据结构：否，本轮不改表结构。
- UI：是，删除单独绑定页，手机扫码确认提现统一进入 confirm 页面。
- 测试：是，新增路由/API/金额/request body 边界测试。

## 8. 当前风险点和不确定项

- 已存在的旧 `/membership/wechat-payout-bind` 外部链接会失效，这是按用户要求不保留兼容入口。
- 底层 store/table 名仍包含 binding 命名；这是刻意避免数据库迁移的内部遗留命名，已在 `docs/data-model.md` 明确其当前语义。

## 9. 仍需用户确认的问题

- 无。

## 10. 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：低风险；底层表名仍有 binding 字样，但长期数据模型文档已记录未迁移原因和当前语义。

## 11. 验证状态

- 已先运行红灯：`python -m pytest tests/test_scoped_project_api_boundaries.py -q -k "withdrawal_confirmation_request_body"`，失败点为前端 complete 请求体仍发 `bindingAttemptId`。
- 修复后运行：`python -m pytest tests/test_scoped_project_api_boundaries.py -q -k "withdrawal_confirmation_request_body or wechat_payout"`，3 passed, 18 deselected。
- `python -m pytest tests/test_membership_payment_service.py -q`：3 passed。
- `python -m compileall adapter backend tests -q`：通过。
- `pnpm -C frontend build`：通过；仍有既有大 chunk warning。

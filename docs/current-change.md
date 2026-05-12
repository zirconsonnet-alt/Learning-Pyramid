# Current Change

更新时间：2026-05-12

## 1. 当前用户要求

- 全部提交本地工作区改动。
- 同步上线服务器。
- 给 `3125049051@qq.com` 账号准备 5 元可提现佣金用于测试提现体验。

## 2. 本次实际修改文件

- `adapter/routers/membership.py`
- `backend/system/membership_commission_store.py`
- `backend/system/membership_payment_service.py`
- `docs/current-change.md`
- `docs/deployment.md`
- `frontend/src/ui/api/membership.ts`
- `frontend/src/ui/queries/membership.ts`
- `frontend/src/views/membership/MembershipPage.tsx`
- `frontend/src/views/membership/WechatPayoutBindingPage.tsx`
- `frontend/src/views/membership/WechatWithdrawalConfirmationPage.tsx`
- `frontend/src/views/membership/components/MembershipPurchaseDialog.tsx`
- `frontend/src/views/profile/ProfilePage.tsx`
- `frontend/tests/e2e/app-load.spec.ts`
- `frontend/tests/e2e/auth-membership-admin.spec.ts`
- `frontend/tests/fixtures/mock-api.ts`
- `tests/test_membership_commission_store.py`
- `tests/test_membership_payment_service.py`

## 3. 每个文件为什么修改

- `adapter/routers/membership.py`：微信提现绑定手机页返回可读账号标签，不再直接暴露不可读 user id。
- `backend/system/membership_commission_store.py`：佣金记录和结算运行改用真实唯一 ID，并支持按分钟读取佣金退款等待窗口。
- `backend/system/membership_payment_service.py`：微信支付提示移除手动同步文案，前端轮询间隔缩短为 2 秒。
- `docs/deployment.md`：补充会员支付、佣金结算、微信提现对账调度说明。
- `frontend/src/ui/api/membership.ts`、`frontend/src/ui/queries/membership.ts`：补齐前端需要的会员/提现字段与自动刷新参数。
- `frontend/src/views/membership/MembershipPage.tsx`：移除手动“同步状态”按钮，改为支付/提现相关状态自动刷新；提现吗弹窗进入处理中后不再继续展示二维码和确认链接；会员权益与优惠券区域样式一致性调整；移除套餐卡片当前预估行。
- `frontend/src/views/membership/WechatPayoutBindingPage.tsx`、`frontend/src/views/membership/WechatWithdrawalConfirmationPage.tsx`：手机端发起微信提现确认后切换为已提交状态，避免重复点击。
- `frontend/src/views/membership/components/MembershipPurchaseDialog.tsx`：删除订单说明里的“当前价格”行。
- `frontend/src/views/profile/ProfilePage.tsx`：删除个人中心账户卡片里的“进入会员中心”孤立入口。
- `frontend/tests/e2e/app-load.spec.ts`、`frontend/tests/e2e/auth-membership-admin.spec.ts`、`frontend/tests/fixtures/mock-api.ts`：覆盖上述 UI 和状态刷新行为。
- `tests/test_membership_commission_store.py`、`tests/test_membership_payment_service.py`：覆盖佣金退款窗口分钟配置和微信支付轮询/文案语义。
- `docs/current-change.md`：记录本次提交与同步批次。

## 4. 行为语义是否变化

变化：
- 会员微信支付弹窗不再提供手动同步按钮，依赖自动轮询刷新。
- 微信支付自动刷新间隔为 2 秒。
- 微信提现确认进入处理中后，桌面弹窗不再继续展示二维码或确认链接；手机页提交确认后不再保留重复确认按钮。
- 佣金退款等待窗口支持按分钟配置；线上测试可设为 1 分钟。
- 个人中心不再提供“进入会员中心”按钮。

## 5. 是否做了重构，以及为什么

未做跨模块重构。改动集中在会员支付/佣金/提现链路和对应 UI，保持现有 store、router、query、页面边界。

## 6. 未修改哪些相关内容，以及为什么

- 不新增后端推送通道：本批次仍使用已有查询接口和前端轮询。
- 不改会员中心路由和全局导航：本次只删除个人中心孤立入口。
- 不改数据库结构：5 元测试佣金通过现有 `commission_records` 语义写入线上数据。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：会员/佣金 DTO 返回字段有补充。
- 架构：无边界变化。
- 部署：需要构建并同步到 self-host 服务器。
- 数据结构：无 schema 变化。
- UI：会员中心、购买弹窗、微信提现确认页、个人中心有变化。
- 测试：新增/扩展后端单测和前端 e2e。

## 8. 当前风险点和不确定项

- 生产环境支付和提现最终状态仍依赖微信通知或后台对账任务；前端轮询只负责页面刷新。
- 线上给 `3125049051@qq.com` 注入 5 元可提现佣金是测试数据操作，应只写入一条可识别的 settled 测试佣金。

## 9. 仍需用户确认的问题

无。

## 10. 验证结果

- `python -m pytest tests/test_membership_commission_store.py tests/test_membership_payment_service.py`：通过 2 条。
- `pnpm --dir frontend exec eslint src/ui/api/membership.ts src/ui/queries/membership.ts src/views/membership/MembershipPage.tsx src/views/membership/WechatPayoutBindingPage.tsx src/views/membership/WechatWithdrawalConfirmationPage.tsx src/views/membership/components/MembershipPurchaseDialog.tsx src/views/profile/ProfilePage.tsx tests/e2e/app-load.spec.ts tests/e2e/auth-membership-admin.spec.ts tests/fixtures/mock-api.ts`：通过。
- `git diff --check`：通过；仅有工作区 LF/CRLF 提示。
- `pnpm --dir frontend build`：通过；Vite 仍提示既有 chunk size warning。
- `pnpm --dir frontend exec playwright test tests/e2e/app-load.spec.ts -g "profile learning view uses scoped audit log endpoint"`：通过 1 条。
- `pnpm --dir frontend exec playwright test tests/e2e/auth-membership-admin.spec.ts -g "membership WeChat payment dialog relies on automatic status refresh|membership withdrawal confirmation dialog closes after payout becomes terminal|membership withdrawal confirmation dialog stops showing QR after WeChat confirmation starts|wechat payout binding page shows a readable account label|wechat payout binding page disables repeated withdrawal confirmation after invoking WeChat|wechat withdrawal confirmation page disables repeated confirmation after invoking WeChat"`：通过 6 条。
- `python -m compileall -q backend adapter tests tools`：通过。
- `python tools/verify_backend_boundaries.py --report-only`：通过，输出 `backend boundary guards verified`。

## 11. 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

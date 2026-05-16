# 当前变更：考研套餐禁用优惠券

## 当前用户要求

- 将优惠券规则改为不能用于考研套餐。
- 已确认采用“考研套餐禁用所有优惠券”，不是只限制 7.5 折邀请码券。

## 根因

- 会员订单预览和创建流程只按 `couponId`、用户、券状态、最低消费和订单金额计算优惠券抵扣。
- 原逻辑没有套餐适用规则，导致考研套餐也可以叠加优惠券，压低专项价格。

## 本次实际修改文件

- `backend/system/membership_store.py`
  - 增加考研套餐不支持优惠券的业务规则和统一错误文案。
  - 在订单预览、创建复用预览、支付确认入口阻止带券考研套餐订单。
- `adapter/routers/membership.py`
  - 在会员预览/创建的券感知预览入口提前拒绝考研套餐带券请求，返回准确错误。
- `frontend/src/views/membership/MembershipPage.tsx`
  - 考研套餐下清空已选优惠券。
  - 考研套餐预览和创建订单时不提交 `couponId`。
  - 购买弹窗收到的可选券在考研套餐下为空。
- `frontend/src/views/membership/components/MembershipPurchaseDialog.tsx`
  - 考研套餐下不展示优惠券选择区。
  - 增加短提示：考研套餐为专项价格，不参与优惠券折扣。
- `tests/test_membership_coupon_plan_rules.py`
  - 新增会员套餐与优惠券适用规则测试。
- `docs/guide-faq.md`
  - 增加考研套餐不能使用优惠券的用户说明。
- `docs/current-change.md`
  - 覆盖为当前变更工作单。

## 行为语义变化

- 考研套餐不能使用任何优惠券。
- 月会员仍可正常使用可用优惠券。
- 已存在的带券考研套餐待支付订单不会被继续确认支付。
- 订单接口、DTO 和数据库结构不变。

## 重构说明

- 未做跨模块重构。
- 仅增加套餐优惠券适用判断，保持规则源头在 `MembershipStore`，路由和前端只做提前拦截与体验同步。

## 未修改内容

- 未修改优惠券发放、券状态、券过期、券退款恢复逻辑。
- 未修改考研套餐定价、有效期和购买截止日计算。
- 未修改支付 provider、佣金、提现或退款窗口逻辑。

## 影响范围

- 后端业务：会员订单预览、创建、支付确认。
- 前端 UI：会员购买弹窗的券选择区和提交参数。
- 文档：FAQ 中的考研套餐优惠券说明。
- 不影响 API 结构、数据库结构、部署配置或公共路由。

## 当前风险与不确定项

- 无当前阻塞风险。

## 验证记录

- 已运行：`python -m pytest tests/test_membership_coupon_plan_rules.py -q`，5 个测试通过。
- 已运行：`pnpm -C frontend exec eslint src/views/membership/MembershipPage.tsx src/views/membership/components/MembershipPurchaseDialog.tsx`，通过。
- 已运行：`pnpm -C frontend build`，通过；仍有既有 chunk size warning。
- 已运行：`git diff --check -- adapter/routers/membership.py backend/system/membership_store.py frontend/src/views/membership/MembershipPage.tsx frontend/src/views/membership/components/MembershipPurchaseDialog.tsx tests/test_membership_coupon_plan_rules.py docs/guide-faq.md docs/current-change.md`，通过；仅提示这些工作区文件后续可能被 Git 转换为 CRLF。

## 仍需用户确认的问题

- 无。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

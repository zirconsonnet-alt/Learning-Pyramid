# Current Change

更新时间：2026-05-13

## 1. 当前用户要求

- 把会员页已绑定邀请码前面的 `已绑定` 三个字加回来。
- 去掉复习卡片里的 `查看复述点详情` 可见标签。
- 修改后提交并同步线上。

## 2. 本次实际修改文件

- `frontend/src/views/membership/MembershipPage.tsx`
- `frontend/src/views/membership/components/MembershipProfilePanel.tsx`
- `frontend/src/views/workbench/components/ReviewPane.tsx`
- `frontend/src/views/recommendations/ReviewRecommendationsPage.tsx`
- `frontend/tests/e2e/auth-membership-admin.spec.ts`
- `frontend/tests/e2e/workbench-review.spec.ts`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `MembershipPage.tsx`：会员中心主卡片的已绑定邀请码行恢复 `已绑定` 状态词，但不恢复 `上级邀请码` 标签。
- `MembershipProfilePanel.tsx`：同步复用会员概览面板的同类展示，避免同一会员信息两种文案规则。
- `ReviewPane.tsx`：删除工作台复习卡片题干下方的 `查看复述点详情` 可见标签和箭头图标，保留题干链接。
- `ReviewRecommendationsPage.tsx`：同步删除推荐复习页同类复习卡片题干下方的 `查看复述点详情` 可见标签和箭头图标，避免同类界面规则不一致。
- `auth-membership-admin.spec.ts`：在会员中心旅程里补充局部断言，确认展示 `已绑定 {邀请码}`，且 `上级邀请码` 和 `有效期至` 不回归。
- `workbench-review.spec.ts`：给推荐复习旅程补充断言，防止 `查看复述点详情` 可见标签回归。
- `docs/current-change.md`：覆盖为本次 UI 文案调整工作单。

## 4. 行为语义是否变化

- UI 展示语义变化：会员邀请码绑定状态重新显示 `已绑定`；复习卡片不再显示 `查看复述点详情` 辅助标签。
- 业务行为不变：会员状态、到期时间、邀请码值、复制邀请码、订单、复述点详情路由和题干链接跳转不变。

## 5. 是否做了重构，以及为什么

- 否。
- 这次只做直接相关展示点的文案调整，不调整组件结构和数据流。

## 6. 未修改哪些相关内容，以及为什么

- 未改会员 API、邀请码绑定逻辑、会员有效期计算和复制邀请码逻辑，因为需求只要求恢复绑定状态词。
- 未改后台管理页里的运营说明和表格文案，因为截图和需求指向用户侧会员展示，不涉及后台运营语义。
- 未改套餐价格卡里的 `有效期至12月21日`，因为它是套餐说明，不是截图红框中的会员状态字段标签。
- 未恢复 `上级邀请码`，因为用户只要求加回 `已绑定` 三个字。
- 未移除复述点题干链接本身，因为用户要求去掉的是可见标签，不是取消跳转能力。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，会员页和会员概览面板的已绑定邀请码行显示为 `已绑定 {邀请码}`；复习卡片题干下方不再显示 `查看复述点详情`。
- 测试：是，更新会员页文案回归断言，并补充推荐复习页标签删除断言。

## 8. 当前风险点和不确定项

- 无。

## 9. 仍需用户确认的问题

- 无。

## 10. 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

## 11. 验证状态

- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=5177 pnpm --dir frontend test:e2e -- auth-membership-admin.spec.ts:53`：1 passed。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=5178 pnpm --dir frontend test:e2e -- workbench-review.spec.ts:117`：1 passed。
- `pnpm --dir frontend build`：通过；仍有既有 `hls` chunk 大于 500 kB 的 warning。
- `git diff --check`：通过；仅输出 Git 将 LF 转 CRLF 的工作区提示。

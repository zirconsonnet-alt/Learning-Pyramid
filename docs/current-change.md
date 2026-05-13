# Current Change

更新时间：2026-05-13

## 1. 当前用户要求

- 删除会员页截图红框里的 `有效期至` 和 `上级邀请码` 标签文案。
- 删除后提交并同步线上。

## 2. 本次实际修改文件

- `frontend/src/views/membership/MembershipPage.tsx`
- `frontend/src/views/membership/components/MembershipProfilePanel.tsx`
- `frontend/tests/fixtures/mock-api.ts`
- `frontend/tests/e2e/auth-membership-admin.spec.ts`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `MembershipPage.tsx`：会员中心主卡片只保留会员到期时间值和已绑定邀请码值，移除红框标签文案。
- `MembershipProfilePanel.tsx`：同步复用会员概览面板的同类展示，避免同一会员信息两种文案规则。
- `mock-api.ts`：给会员页测试增加可选的已绑定上级邀请码数据状态，避免只测无值分支。
- `auth-membership-admin.spec.ts`：在会员中心旅程里补充局部断言，防止红框位置的 `有效期至` 和 `上级邀请码` 文案回归。
- `docs/current-change.md`：覆盖为本次会员页文案删除工作单。

## 4. 行为语义是否变化

- 否。
- 只删除展示标签文案，会员状态、到期时间、邀请码值、复制邀请码、订单和接口行为不变。

## 5. 是否做了重构，以及为什么

- 否。
- 这次只做两个直接相关会员展示点的文案删除，不调整组件结构和数据流。

## 6. 未修改哪些相关内容，以及为什么

- 未改会员 API、邀请码绑定逻辑、会员有效期计算和复制邀请码逻辑，因为需求只要求删页面文字标签。
- 未改后台管理页里的运营说明和表格文案，因为截图和需求指向用户侧会员展示，不涉及后台运营语义。
- 未改套餐价格卡里的 `有效期至12月21日`，因为它是套餐说明，不是截图红框中的会员状态字段标签。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，会员页和会员概览面板少两个标签词，只展示对应值。
- 测试：是，补充会员页文案删除回归断言。

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

- `pnpm --dir frontend build`：通过；仍有既有 `hls` chunk 大于 500 kB 的 warning。
- `git diff --check`：通过；仅输出 Git 将 LF 转 CRLF 的工作区提示。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=5177 pnpm --dir frontend test:e2e -- auth-membership-admin.spec.ts:53`：1 passed。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=5177 pnpm --dir frontend test:e2e -- auth-membership-admin.spec.ts -g "membership"`：会员页相关用例通过；同文件内 2 个微信提现确认用例失败，失败点是确认页既有 mock/按钮状态，不影响本次会员页文案删除。

# Current Change

更新时间：2026-05-13

## 1. 当前用户要求

- 去掉复习卡片顶部的“已标记为记得 / 已标记为不记得”标签。
- 把“记得”和“不记得”按钮分别染成绿色和红色。

## 2. 本次实际修改文件

- `frontend/src/views/workbench/components/ReviewPane.tsx`
- `frontend/src/views/recommendations/ReviewRecommendationsPage.tsx`
- `frontend/tests/e2e/workbench-review.spec.ts`
- `frontend/tests/fixtures/mock-api.ts`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `ReviewPane.tsx`：删除工作台复习卡片顶部的状态标签，并把记忆选择按钮改成绿色 / 红色语义样式。
- `ReviewRecommendationsPage.tsx`：同步删除推荐复习页的顶部状态标签，并把记忆选择按钮改成绿色 / 红色语义样式。
- `workbench-review.spec.ts`：补充两个回归场景，覆盖推荐复习页和工作台复习页，防止状态标签和按钮语义样式回退。
- `mock-api.ts`：给复习工作台测试增加可注入的 `queueHeadId`，让 e2e 能稳定进入工作台复习面。
- `docs/current-change.md`：覆盖为本次任务工作单。

## 4. 行为语义是否变化

- UI 语义变化：顶部状态标签去掉，记忆选择按钮从中性色改为绿色 / 红色语义色。
- 复习流程语义不变：提交答案、跳过、展开答案、选择记得 / 不记得、提交本轮复习都不变。

## 5. 是否做了重构，以及为什么

- 否。
- 这次只做局部展示修正和测试支撑，不改组件边界和数据流。

## 6. 未修改哪些相关内容，以及为什么

- 未改复习提交逻辑、推荐算法、答案展开逻辑和回调签名，因为需求只涉及视觉语义。
- 未改长期文档，因为没有新增稳定业务规则，只是现有复习界面的展示调整。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，复习卡片顶部状态展示和记忆按钮样式变化。
- 测试：是，补充工作台与推荐复习两条回归。

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

- `$env:LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER='1'; $env:LEARNINGPYRAMID_FRONTEND_E2E_PORT='5183'; pnpm --dir frontend test:e2e -- workbench-review.spec.ts`：6 passed。
- `pnpm --dir frontend build`：通过；仍有既有 `hls` chunk 大于 500 kB 的 warning。
- `git diff --check`：通过；仅输出 Git 将 LF 转 CRLF 的工作区提示。

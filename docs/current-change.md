# Current Change

更新时间：2026-05-13

## 1. 当前用户要求

- 删除复习提交后红框里的状态提示文案。
- 标准答案区域拆成类似 `你的答案` 的外部标题加具体内容卡片。
- 删除答案卡片内部的 `答案` 二字。
- 删除单独的 `回到锚点` 按钮。
- 把实例名加锚点名的入口改成承担原 `回到锚点` 功能。
- 把 `追加理解` 按钮移动到锚点入口同一行后面。

## 2. 本次实际修改文件

- `frontend/src/views/workbench/components/ReviewPane.tsx`
- `frontend/src/views/recommendations/ReviewRecommendationsPage.tsx`
- `frontend/tests/e2e/workbench-review.spec.ts`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `ReviewPane.tsx`：工作台复习卡片删除提交/跳过后的状态提示行，把标准答案标题移到卡片外；删除单独的 `回到锚点` 按钮，让锚点 pill 调用原播放器定位回调，并把 `追加理解` 放到同一行。
- `ReviewRecommendationsPage.tsx`：推荐复习页同步同类展示结构，删除单独 `回到锚点` 链接，让锚点 pill 承担现有实例跳转入口，并把 `追加理解` 放到同一行。
- `workbench-review.spec.ts`：补充推荐复习旅程断言，防止状态提示、卡片内标题、单独 `回到锚点` 和错位的 `追加理解` 回归。
- `docs/current-change.md`：覆盖为本次复习答案 UI 清理工作单。

## 4. 行为语义是否变化

- UI 展示语义变化：提交/跳过后不再显示额外状态提示；标准答案区显示为外部标题 `答案` 加内容卡片；锚点和追加理解操作并入同一行。
- 行为变化：工作台复习卡片中锚点 pill 承担原 `回到锚点` 的播放器定位行为；推荐复习页锚点 pill 承担原 `回到锚点` 链接的实例跳转行为。
- 其他业务行为不变：提交答案、跳过、展开答案、判断记忆状态和复习提交逻辑不变。

## 5. 是否做了重构，以及为什么

- 否。
- 这次只调整两个同类复习界面的局部展示结构和既有点击入口位置，不改组件边界和数据流。

## 6. 未修改哪些相关内容，以及为什么

- 未改复习 API、复习 session store、提交/跳过状态和记忆判断逻辑，因为需求只涉及 UI 展示。
- 未改复述点详情页和录入页答案编辑结构，因为截图指向复习过程里的标准答案展示。
- 未移除 `答案` 这个区域标题，因为用户要求的是删除卡片内的 `答案`，同时保留类似 `你的答案` 的外部标题。
- 未给推荐复习页新增播放器定位回调，因为该页面当前没有播放器上下文；它只能把原 `回到锚点` 链接能力迁移到锚点 pill。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，复习答案区域展示结构变化，锚点入口和追加理解按钮布局变化。
- 测试：是，补充推荐复习页 UI 回归断言。

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

- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=5179 pnpm --dir frontend test:e2e -- workbench-review.spec.ts:117`：先按测试先行确认旧答案区实现失败在 `已提交答案` 仍存在；实现后 1 passed。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=5180 pnpm --dir frontend test:e2e -- workbench-review.spec.ts:117`：先按测试先行确认旧锚点布局失败在 `回到锚点` 链接仍存在；实现后 1 passed。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=5181 pnpm --dir frontend test:e2e -- workbench-review.spec.ts:117`：复跑当前目标用例，1 passed。
- `pnpm --dir frontend build`：通过；仍有既有 `hls` chunk 大于 500 kB 的 warning。
- `git diff --check`：通过；仅输出 Git 将 LF 转 CRLF 的工作区提示。
- `rg -n "已提交答案|已跳过，已展开答案|已提交，已展开答案|先提交自己的答案或跳过|已展开答案，可判断记忆状态" frontend\src\views\workbench\components\ReviewPane.tsx frontend\src\views\recommendations\ReviewRecommendationsPage.tsx`：无匹配。
- `pnpm --dir frontend build`（最新复跑）：通过；仍有既有 `hls` chunk 大于 500 kB 的 warning。
- `git diff --check`（最新复跑）：通过；仅输出 Git 将 LF 转 CRLF 的工作区提示。

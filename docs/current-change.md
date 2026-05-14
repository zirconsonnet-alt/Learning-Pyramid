# Current Change

更新时间：2026-05-15

## 1. 当前用户要求

- 在工作台复述点录入表单中，给“问题”和“答案”后面加“预览”。
- 鼠标放到“预览”上时显示当前内容的 Markdown / LaTeX 渲染效果。
- 鼠标移开后预览失效。
- 同样的预览能力也要加到复述点详情页的内容编辑区。

## 2. 本次实际修改文件

- `frontend/src/ui/components/RichContentFieldPreview.tsx`
- `frontend/src/views/workbench/components/ComposePane.tsx`
- `frontend/src/views/recallPoints/RecallPointPage.tsx`
- `frontend/tests/e2e/workbench-review.spec.ts`
- `frontend/tests/e2e/detail-summary-cards.spec.ts`
- `docs/how-to-study-review.md`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `frontend/src/ui/components/RichContentFieldPreview.tsx`：抽出共享 hover/focus 预览组件，统一复用现有 `RichContentRenderer` 渲染当前富文本内容。
- `frontend/src/views/workbench/components/ComposePane.tsx`：把工作台录入表单的“问题”“答案”预览切换为共享组件。
- `frontend/src/views/recallPoints/RecallPointPage.tsx`：在复述点详情页“当前内容”的编辑态，为“题面”“答案”增加同样的预览入口。
- `frontend/tests/e2e/workbench-review.spec.ts`：新增 e2e 回归，覆盖输入 Markdown / LaTeX 后 hover 预览显示、切换字段预览和移开隐藏。
- `frontend/tests/e2e/detail-summary-cards.spec.ts`：新增详情页 e2e 回归，覆盖“修改内容”后题面/答案 hover 预览。
- `docs/how-to-study-review.md`：更新用户指南，说明录入和详情编辑时可通过字段后的“预览”临时查看渲染效果。
- `docs/current-change.md`：覆盖为当前任务工作单。

## 4. 行为语义是否变化

- 是。工作台复述点录入表单、复述点详情页内容编辑态新增临时渲染预览入口。
- 否。不改变复述点 `question` / `answer` 的保存格式，编辑框仍保存并展示原始 Markdown / LaTeX 文本。
- 否。不改变复习、详情、推荐复习等只读展示场景的既有渲染语义。

## 5. 是否做了重构，以及为什么

- 是，做了当前需求范围内的局部抽取。
- 将上一轮 `ComposePane.tsx` 内的预览组件抽到 `RichContentFieldPreview.tsx`，避免在详情页复制同一套 hover/focus、空内容和 `RichContentRenderer` 逻辑。

## 6. 未修改哪些相关内容，以及为什么

- 不修改后端模型、DTO、API 或持久化，因为本次只是前端录入体验增强。
- 不修改 `RichContentRenderer` / `MarkdownRichText`，因为现有 Markdown / LaTeX 渲染链路已满足需求。
- 不给复习作答框、视频全屏捕获框等其它编辑入口增加预览，因为当前用户只要求工作台录入和复述点详情编辑两处。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，工作台复述点录入表单和复述点详情页内容编辑态字段标题旁新增“预览”。
- 测试：是，新增工作台和详情页 hover 预览 e2e。

## 8. 当前风险点和不确定项

- 预览浮层使用当前字段容器定位；极窄屏上主要依赖最大宽度和滚动区域避免溢出。
- 空内容时预览显示“暂无内容”，不影响提交校验。

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

- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4231; pnpm exec playwright test tests/e2e/workbench-review.spec.ts -g "previews markdown and latex" --reporter=line`：失败，确认实现前缺少“问题预览”按钮。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4232; pnpm exec playwright test tests/e2e/workbench-review.spec.ts -g "previews markdown and latex" --reporter=line`：1 passed。
- `pnpm exec tsc -b --noEmit`：通过。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4233; pnpm exec playwright test tests/e2e/workbench-review.spec.ts --reporter=line`：7 passed / 1 failed；失败发生在公共入口 `gotoWorkbench` 等待“工作状态”时，失败截图中页面最终已显示“工作状态”，未指向本次预览实现。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4234; pnpm exec playwright test tests/e2e/workbench-review.spec.ts --workers=1 --reporter=line`：8 passed。
- `pnpm build`：通过，保留既有 chunk size warning。
- `git diff --check`：通过，仅有 LF/CRLF 提示。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4235; pnpm exec playwright test tests/e2e/detail-summary-cards.spec.ts -g "detail editor previews" --reporter=line`：失败，确认实现前缺少“题面预览”按钮。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4236; pnpm exec playwright test tests/e2e/detail-summary-cards.spec.ts -g "detail editor previews" --reporter=line`：1 passed。
- `pnpm exec tsc -b --noEmit`：先失败于 `RecallPointPage.tsx` 的未使用 `Label` 导入；移除后通过。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4237; pnpm exec playwright test tests/e2e/workbench-review.spec.ts -g "previews markdown and latex" --reporter=line`：1 passed。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4238; pnpm exec playwright test tests/e2e/detail-summary-cards.spec.ts -g "detail editor previews" --reporter=line`：1 passed。
- `pnpm exec tsc -b --noEmit`：通过。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4239; pnpm exec playwright test tests/e2e/workbench-review.spec.ts -g "previews markdown and latex" --reporter=line`：1 passed。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4240; pnpm exec playwright test tests/e2e/detail-summary-cards.spec.ts -g "detail editor previews" --reporter=line`：1 passed。
- `pnpm build`：通过，保留既有 chunk size warning。
- `git diff --check`：通过，仅有 LF/CRLF 提示。

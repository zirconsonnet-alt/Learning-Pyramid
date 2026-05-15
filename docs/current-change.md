# 当前变更：学习复习引导第 4/5 步自动填写

## 当前用户要求

- “如何学习复习”引导第 4 步、第 5 步自动填写问题和答案。
- 自动填写后显示“下一步”按钮。
- 只有这两个步骤显式显示“下一步”。
- 引导中不出现“上一步”按钮。

## 根因

- 学习复习引导的 `fill-recall-question`、`fill-recall-answer` 原本使用 `completion-event`，依赖用户手动输入触发完成。
- 导引控制器缺少“普通步骤由下一步按钮推进”的显式模式。
- 虚拟学习复习工作台没有在导引步骤进入时写入示例问题/答案。

## 本次实际修改文件

- `frontend/src/ui/guideWalkthrough/guideWalkthroughSteps.ts`
  - 新增 `next-button` 推进模式。
  - 只把学习复习导引的 `fill-recall-question`、`fill-recall-answer` 改为 `next-button`。
- `frontend/src/ui/guideWalkthrough/guideWalkthroughController.ts`
  - `manual` 与 `next-button` 步骤只显示 `next` 按钮。
  - 全局默认按钮只保留 `close`，避免 driver.js 默认带出 `previous`。
  - 新增导引步骤高亮事件，供虚拟工作台在步骤进入时执行自动填充。
  - 完成事件只推进 `completion-event` 和既有 `target-click` 步骤，不推进 `next-button` 步骤。
- `frontend/src/ui/guideWalkthrough/virtualStudyReviewProject.ts`
  - 提取学习复习引导示例问题、答案常量。
- `frontend/src/views/workbench/components/ComposePane.tsx`
  - 仅在虚拟学习复习项目中监听导引高亮事件。
  - 第 4 步写入示例问题，第 5 步写入示例答案。
- `frontend/tests/e2e/subject-project.spec.ts`
  - 新增学习复习导引 e2e，覆盖自动填充、第 4/5 步显示“下一步”、无“上一步”、completion-event 不会绕过 next-button。
- `docs/how-to-study-review.md`
  - 同步第 4/5 步导引文案，说明问题和答案由引导自动填写后点击“下一步”。
- `docs/current-change.md`
  - 覆盖为当前任务工作单。

## 行为语义变化

- 学习复习导引第 4/5 步由“用户手动填写后自动进入下一步”改为“系统自动填示例内容，用户点击下一步继续”。
- 导引弹窗不再出现“上一步”按钮。

## 重构说明

- 做了小范围抽象补充：新增 `next-button` 推进模式，避免在控制器里硬编码具体 step id。
- 未改公共 API、数据库、协议、部署配置或后端行为。

## 未修改内容

- 未改变真实项目普通复述点录入流程。
- 未改变学习任务提交、复习提交的数据结构和接口。
- 未增加 fallback / shim / legacy 兼容层。

## 影响范围

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，仅导引弹窗按钮和虚拟学习复习引导自动填充。
- 文档：是，同步 `docs/how-to-study-review.md`。
- 测试：是，新增 e2e 回归。

## 验证记录

- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4259; pnpm exec playwright test tests/e2e/subject-project.spec.ts -g "study review guide auto-fills" --reporter=line`：失败，确认修复前第 4 步问题输入框为空。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4265; pnpm exec playwright test tests/e2e/subject-project.spec.ts -g "study review guide auto-fills" --reporter=line`：失败，确认修复前 completion-event 可绕过 next-button。
- `pnpm exec tsc -b --noEmit`：通过。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4268; pnpm exec playwright test tests/e2e/subject-project.spec.ts -g "create subject guide enters workbench|study review guide auto-fills" --workers=1 --reporter=line`：2 passed。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4269; pnpm exec playwright test tests/e2e/subject-project.spec.ts --workers=1 --reporter=line`：8 passed。
- `git diff --check`：通过，仅有仓库换行符提示。

## 当前风险与不确定项

- 未发现影响本次改动正确性的未解决风险。

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

# 当前变更：学习复习导引不污染当前学科项目

## 当前用户要求

- 第 6 步“填写复习答案”不应该同时框住文本框和“提交答案”按钮。
- 用户做完学习复习导引后，顶部当前学科/项目不应该变成导引示范学科/项目。
- 学科中心找不到的虚拟导引学科/项目不应该让用户看到。

## 根因

- `review-answer-editor` 导引锚点曾放在“你的答案”整块外层容器上，按钮被包含进高亮边界。
- 学习复习导引的虚拟路由会被 `AppShell` 当成真实项目路由，同步写入 `selectedSubjectId` 和 `selectedWorkbenchProjectRef`。
- `startVirtualStudyReviewProjectSession` 也主动写入了虚拟 subject/project 选择。
- 清理时只处理了部分虚拟 ID 组合，无法移除路由同步写入的 `guide-virtual-study-review:guide-virtual-study-review` 组合，导致顶部当前学科/项目残留。

## 本次实际修改文件

- `frontend/src/views/workbench/components/ReviewPane.tsx`
  - 将 `review-answer-editor` 导引锚点从“你的答案”整块外层容器下移到 `RichContentEditor` 的直接包裹层。
  - 将“提交答案 / 跳过”按钮行间距从 `mt-2` 调整为 `mt-4`，给 driver 的 8px 高亮 padding 留出明确断开距离。
- `frontend/src/shell/AppShell.tsx`
  - 路由同步当前学科、当前项目时跳过学习复习导引虚拟 subject/project。
  - 避免 `/subjects/guide-virtual-study-review/projects/guide-virtual-study-review/workbench` 被写入真实当前学科/项目状态。
- `frontend/src/ui/guideWalkthrough/virtualStudyReviewProject.ts`
  - `startVirtualStudyReviewProjectSession` 不再主动写入全局当前学科/项目。
  - `clearVirtualStudyReviewProjectSession` 清理所有虚拟导引 subject/project ID 组合，包括历史上已经写入过的组合。
- `frontend/tests/e2e/subject-project.spec.ts`
  - 增加第 6 步高亮边界断言。
  - 扩展学习复习导引用例到提交本轮复习结束，断言回到学科中心后不显示虚拟导引学科/项目，并且 `plm-app` 持久化状态不残留虚拟 ID。
- `docs/current-change.md`
  - 覆盖为当前任务工作单。

## 行为语义变化

- 第 6 步“填写复习答案”的高亮范围收窄到答案编辑器本体。
- 学习复习导引使用虚拟项目时，不再进入真实的当前学科/项目选择和最近使用状态。
- 已经残留在本地状态里的虚拟导引 subject/project 会被清理。
- 不改变真实复习提交、跳过、答案校验、导引推进、API、数据库或后端行为。

## 重构说明

- 做了局部状态边界整理，不做跨模块重构。
- 未改公共 API、数据库、协议、部署配置或后端行为。

## 未修改内容

- 不修改学科中心真实数据查询。
- 不修改 `submit-review-answer` 步骤。
- 不修改真实项目的当前学科/项目同步语义。

## 验证记录

- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4286; pnpm exec playwright test tests/e2e/subject-project.spec.ts -g "study review guide auto-fills" --reporter=line`：1 passed。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4287; pnpm exec playwright test tests/e2e/subject-project.spec.ts -g "create subject guide enters workbench|study review guide auto-fills" --workers=1 --reporter=line`：2 passed。
- `pnpm exec tsc -b --noEmit`：通过。
- `pnpm exec eslint src/shell/AppShell.tsx src/ui/guideWalkthrough/virtualStudyReviewProject.ts src/views/workbench/components/ReviewPane.tsx tests/e2e/subject-project.spec.ts`：0 errors，1 warning；warning 为 `AppShell.tsx:578` 既有 `react-hooks/exhaustive-deps`，不在本次修改的 effect 内。
- `git diff --check`：通过，仅有仓库换行符提示。
- `rg -n "from __future__ import annotations" -g "*.py"`：无匹配。

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

# 当前变更：学习复习引导补齐复习答案填写

## 当前用户要求

- “如何学习复习”导引进入做复习时，在提交答案之前应先自动填写“你的答案”。
- 这个复习答案填写步骤和录入复述点的问题、答案步骤一样，自动填写后显示“下一步”。
- 引导文本中不要出现“系统会”“引导会”这类运行说明性质文字。

## 根因

- 学习复习导引从提交学习后直接进入 `submit-review-answer` 步骤。
- 真实复习提交按钮依赖“你的答案”有内容；导引没有先填内容，导致按钮禁用。
- 当前文档句子包含“系统会”“引导会”这类说明口吻，并被导引弹窗复用。

## 本次实际修改文件

- `frontend/src/ui/guideWalkthrough/guideWalkthroughSteps.ts`
  - 在提交答案前新增 `fill-review-answer` 导引步骤。
  - 该步骤高亮“你的答案”编辑区，并使用 `next-button` 推进。
- `frontend/src/ui/guideWalkthrough/virtualStudyReviewProject.ts`
  - 新增虚拟学习复习导引用的复习答案示例常量。
- `frontend/src/views/workbench/components/ReviewPane.tsx`
  - 给“你的答案”区域补充导引锚点。
  - 仅在虚拟学习复习项目中监听导引高亮事件，进入 `fill-review-answer` 时写入示例答案。
  - 将本组件的 session 更新函数局部收敛为 `useCallback`，让新增 effect 依赖明确。
- `frontend/tests/e2e/subject-project.spec.ts`
  - 扩展学习复习导引回归用例，覆盖复习答案自动填写、下一步按钮、无上一步按钮、提交答案按钮可用、导引文案不出现“系统会 / 引导会”。
- `docs/how-to-study-review.md`
  - 同步第 6 步复习流程文案。
  - 去掉导引相关文案中的运行说明口吻。
- `docs/current-change.md`
  - 覆盖为当前任务工作单。

## 行为语义变化

- 学习复习导引提交学习后，会先高亮“你的答案”输入区并自动填入一条回忆答案。
- 用户点击“下一步”后，再进入“提交答案”步骤。
- 真实项目普通复习流程不变。

## 重构说明

- 做了小范围局部整理：`ReviewPane` 的 `updateSessionState` 改为 `useCallback`，原因是新增导引高亮监听需要稳定、明确的 hook 依赖。
- 未改公共 API、数据库、协议、部署配置或后端行为。
- 不新增 fallback / shim / legacy 兼容层。

## 未修改内容

- 未改变真实项目普通复习校验：提交答案仍然需要“你的答案”有内容。
- 未改变后端复习任务提交接口。
- 未改变导引控制器的推进语义。

## 验证记录

- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4274; pnpm exec playwright test tests/e2e/subject-project.spec.ts -g "study review guide auto-fills" --reporter=line`：1 passed。
- `pnpm exec tsc -b --noEmit`：通过。
- `pnpm exec eslint src/views/workbench/components/ReviewPane.tsx src/ui/guideWalkthrough/guideWalkthroughSteps.ts src/ui/guideWalkthrough/virtualStudyReviewProject.ts tests/e2e/subject-project.spec.ts`：通过。
- `rg -n "系统|引导会|系统会" docs/how-to-study-review.md frontend/src/ui/guideWalkthrough`：无匹配。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4276; pnpm exec playwright test tests/e2e/subject-project.spec.ts -g "create subject guide enters workbench|study review guide auto-fills" --workers=1 --reporter=line`：2 passed。
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

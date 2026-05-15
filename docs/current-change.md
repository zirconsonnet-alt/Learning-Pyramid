# 当前变更：AI 问答与番茄钟导引可用化

## 当前用户要求

- AI 问答导引和番茄钟导引不能继续停留在空泛说明或已经完成的入口动作上。
- 这两个导引应参考“创建学科”和“学习复习”导引：进入可控场景、自动准备必要上下文，只让用户执行当前真正有意义的动作。
- 引导文案不要出现“确保满足以下条件”“系统会怎样”等运行说明性质内容。

## 根因

- AI 问答导引在会员和 LLM 可用后仍进入真实项目 AI 页，只提示选择节点和发送问题，没有准备可问内容，也没有把“查看回答”作为导引结果。
- 番茄钟导引仍绑定真实番茄钟状态，并把最后一步写成离线/登录提醒，导致用户在已经打开番茄钟页面时看到不可操作的说明。
- 两者都没有按既有好案例使用隔离演示场景承载导引闭环。

## 本次实际修改文件

- `frontend/src/ui/guideWalkthrough/guideWalkthroughSteps.ts`
  - AI 问答导引改为“选择提问对象 -> 确认问题 -> 发送问题 -> 查看回答”。
  - 番茄钟导引改为“开启番茄钟 -> 新建番茄计划 -> 绑定学习项目 -> 进入工作台学习 -> 查看学习状态”。
  - 两套可用状态导引都指向隔离演示页。
- `frontend/src/ui/guideWalkthrough/guideWalkthroughController.ts`
  - 会员和 LLM 检查仍保留。
  - AI 问答通过检查后进入 `/guide/demo/ai-chat`。
  - 番茄钟通过会员检查后进入 `/guide/demo/pomodoro`。
  - 移除番茄钟导引按真实计时状态裁剪步骤的逻辑。
- `frontend/src/views/guide/AiChatGuideDemoPage.tsx`
  - 改成可操作的 AI 问答演示：选择学习对象、确认预填问题、发送后展示确定性回答。
- `frontend/src/views/guide/PomodoroGuideDemoPage.tsx`
  - 改成可操作的番茄钟演示：开启、建计划、绑定项目、进入工作台、查看当前学习状态。
- `frontend/tests/e2e/guide-walkthrough.spec.ts`
  - 新增/更新 AI 问答和番茄钟导引的可用闭环测试。
- `docs/how-to-use-ai-chat.md`
  - 同步 AI 问答导引步骤和短文案。
- `docs/how-to-use-pomodoro.md`
  - 同步番茄钟导引步骤，移除离线/登录提醒式步骤。
- `docs/current-change.md`
  - 覆盖为当前任务工作单。

## 行为语义变化

- AI 问答在会员有效、LLM 已接通且存在项目时，导引进入隔离演示页完成最小问答闭环。
- 番茄钟在会员有效时，导引进入隔离演示页完成最小番茄闭环。
- 会员门禁和 LLM 配置门禁不变。
- AI 问答真实业务、番茄钟计时算法、后端 API、数据库和部署方式不变。

## 重构说明

- 做了导引编排层的局部整理。
- 移除番茄钟导引旧的真实状态裁剪逻辑，因为当前导引已改为固定隔离演示流程。
- 未做跨模块重构。

## 未修改内容

- 不绕过会员门禁。
- 不绕过 LLM 配置要求。
- 不修改真实 AI 问答发送逻辑。
- 不修改真实番茄钟排程、计时、工作台限制逻辑。
- 不修改后端接口、数据库、部署配置。

## 验证记录

- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4311; pnpm exec playwright test tests/e2e/guide-walkthrough.spec.ts -g "AI chat guide walks through a usable isolated question flow|pomodoro guide walks through a usable isolated focus flow" --workers=1 --reporter=line`：红灯，当前实现仍进入真实 AI 问答页和真实番茄钟页。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4314; pnpm exec playwright test tests/e2e/guide-walkthrough.spec.ts -g "AI chat guide walks through a usable isolated question flow|pomodoro guide walks through a usable isolated focus flow" --workers=1 --reporter=line`：2 passed。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4315; pnpm exec playwright test tests/e2e/guide-walkthrough.spec.ts --workers=1 --reporter=line`：5 passed。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4316; pnpm exec playwright test tests/e2e/subject-project.spec.ts -g "create subject guide enters workbench after directory sync|study review guide auto-fills recall question learning answer and review answer" --workers=1 --reporter=line`：2 passed。
- `pnpm exec tsc -b --noEmit`：通过。
- `pnpm exec eslint src/ui/guideWalkthrough/guideWalkthroughSteps.ts src/ui/guideWalkthrough/guideWalkthroughController.ts src/views/guide/AiChatGuideDemoPage.tsx src/views/guide/PomodoroGuideDemoPage.tsx tests/e2e/guide-walkthrough.spec.ts`：通过。
- `git diff --check`：通过，仅有工作区换行符提示。
- `rg -n "from __future__ import annotations" -g "*.py"`：无匹配。

## 当前风险与不确定项

- 暂无。

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

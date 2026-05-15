# 当前变更：AI 问答导引首步对齐当前页面

## 当前用户要求

- AI 问答导引已经把用户带到 AI 问答页时，不应该再提示“点击左侧导航里的 AI问答”。
- 当前页面已经提示“先选择一个节点开始提问”，导引首步应该直接引导选择左侧节点。

## 根因

- AI 问答导引控制器已经自动跳转到项目 AI 问答页。
- `USE_AI_CHAT_GUIDE_STEPS` 仍保留“进入项目 AI 问答”作为第一步，导致导引文案要求用户点击已经打开的入口。
- 这一步和当前页面状态冲突，对用户没有可执行意义。

## 本次实际修改文件

- `frontend/src/ui/guideWalkthrough/guideWalkthroughSteps.ts`
  - 移除 AI 可用状态下的 `ai-open-chat` 步骤。
  - 将 AI 问答导引步骤调整为“选择提问上下文 -> 发送问题”。
- `docs/how-to-use-ai-chat.md`
  - 删除独立“进入项目 AI 问答”步骤，让文档和导引都从当前 AI 问答页内的选择节点开始。
- `frontend/src/views/guide/AiChatGuideDemoPage.tsx`
  - 去掉演示页对已移除 `ai-open-chat` 步骤的完成事件派发。
- `frontend/tests/e2e/guide-walkthrough.spec.ts`
  - 更新 AI 问答可用状态用例，要求首步为选择节点，并断言不出现旧入口文案。
- `docs/current-change.md`
  - 覆盖为当前任务工作单。

## 行为语义变化

- AI 问答可用时，导引进入 AI 问答页后从“选择提问上下文”开始。
- 不改变会员判定、LLM 配置、AI 问答发送逻辑、后端 API、数据库或部署方式。

## 重构说明

- 做了局部导引步骤整理，不做跨模块重构。
- 不改公共 API、数据库、协议、部署配置或后端行为。

## 未修改内容

- 不绕过会员门禁。
- 不绕过 LLM 配置要求。
- 不修改 AI 问答业务能力本身。
- 不修改番茄钟导引。

## 验证记录

- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4298; pnpm exec playwright test tests/e2e/guide-walkthrough.spec.ts -g "AI chat guide starts from selecting a node" --workers=1 --reporter=line`：红灯，当前实现仍显示旧的进入 AI 问答步骤。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4299; pnpm exec playwright test tests/e2e/guide-walkthrough.spec.ts -g "AI chat guide starts from selecting a node" --workers=1 --reporter=line`：1 passed。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4300; pnpm exec playwright test tests/e2e/guide-walkthrough.spec.ts --workers=1 --reporter=line`：5 passed。
- `pnpm exec tsc -b --noEmit`：通过。
- `pnpm exec eslint src/ui/guideWalkthrough/guideWalkthroughSteps.ts src/views/guide/AiChatGuideDemoPage.tsx tests/e2e/guide-walkthrough.spec.ts`：通过。

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

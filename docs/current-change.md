# 当前变更：AI 问答与番茄钟引导按真实状态分流

## 当前用户要求

- AI 问答引导和番茄钟引导要与当前实现一致。
- 引导不要出现泛化条件清单这类系统运行说明。
- 引导要根据用户当前条件给明确内容：没有会员就说明会员限制，没有配置 LLM 就引导去配置。

## 根因

- AI 问答引导仍从静态文档抽取泛化条件清单，没有读取会员、LLM 和项目状态。
- 番茄钟引导仍按旧流程先指向“番茄钟设置”，但当前页面已在番茄钟首页提供开启入口和计划入口。
- 引导控制器只对番茄钟做了部分状态裁剪，没有统一的会员 / LLM / 项目预检。

## 本次实际修改文件

- `frontend/src/ui/guideWalkthrough/guideWalkthroughController.ts`
  - 增加导引运行时上下文，启动 AI 问答和番茄钟导引前读取系统能力、会员状态、当前项目和项目目录。
  - AI 问答导引在无会员时进入会员中心并停止，在无 LLM 时进入全局配置并停止，在无项目时停在学科中心说明。
  - AI 问答可用时直接进入真实项目 AI 问答路由。
  - 番茄钟导引在无会员时进入会员中心并停止，可用时从番茄钟页真实开关开始。
- `frontend/src/ui/guideWalkthrough/guideWalkthroughSteps.ts`
  - 移除 AI 问答的旧“确认条件”步骤。
  - 移除番茄钟旧“打开设置”步骤。
  - 将 AI 问答和番茄钟步骤标题同步到当前真实流程。
- `frontend/src/shell/AppShell.tsx`
  - 为导引控制器传入系统能力、会员状态、当前项目和项目目录状态。
- `frontend/src/views/settings/GlobalSettingsPage.tsx`
  - 保留 LLM 配置区域锚点，移除已经不存在的 AI 确认步骤派发。
- `frontend/src/views/guide/AiChatGuideDemoPage.tsx`
  - 演示页同步为进入 AI 问答、选择节点、发送问题三步。
- `frontend/src/views/guide/PomodoroGuideDemoPage.tsx`
  - 演示页同步为从开启番茄钟开始，不再展示打开设置步骤。
- `frontend/src/views/home/HomePage.tsx`
  - 更新首页 AI 问答和番茄钟导引入口摘要。
- `frontend/src/views/guide/GuidePage.tsx`
  - 更新指南页 AI 问答和番茄钟摘要。
- `docs/how-to-use-ai-chat.md`
  - 改为会员状态、LLM 配置、项目上下文和真实三步使用路径。
- `docs/how-to-use-pomodoro.md`
  - 改为会员状态、开启番茄钟、设定计划、进入工作台学习。
- `frontend/tests/fixtures/mock-api.ts`
  - 增加 e2e 中覆盖会员状态的 mock 入口。
- `frontend/tests/e2e/guide-walkthrough.spec.ts`
  - 增加 AI 问答和番茄钟状态感知引导用例。
- `docs/current-change.md`
  - 覆盖为当前任务工作单。

## 行为语义变化

- AI 问答引导先按会员、LLM、项目状态分流，再进入真实项目 AI 问答。
- 番茄钟引导先按会员状态分流，正常情况下从首页“开启番茄钟”开始。
- 条件不足的引导只显示一个“完成”按钮，不出现“上一步”。
- 不改变会员判定、LLM 配置保存、番茄钟开关、计划保存、后端 API、数据库或部署方式。

## 重构说明

- 做了局部引导控制器整理，把运行时条件判断集中在导引启动入口。
- 不改公共 API、数据库、协议、部署配置或后端行为。

## 未修改内容

- 不绕过会员门禁。
- 不绕过 LLM 配置要求。
- 不把静态文档当成运行时状态来源。
- 不修改 AI 问答、番茄钟、会员中心的业务能力本身。

## 验证记录

- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4291; pnpm exec playwright test tests/e2e/guide-walkthrough.spec.ts --reporter=line`：红灯，5 个用例按旧流程失败。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4293; pnpm exec playwright test tests/e2e/guide-walkthrough.spec.ts --workers=1 --reporter=line`：5 passed。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4296; pnpm exec playwright test tests/e2e/guide-walkthrough.spec.ts --workers=1 --reporter=line`：5 passed。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4297; pnpm exec playwright test tests/e2e/subject-project.spec.ts -g "create subject guide enters workbench|study review guide auto-fills" --workers=1 --reporter=line`：2 passed。
- `pnpm exec tsc -b --noEmit`：通过。
- `pnpm exec eslint src/shell/AppShell.tsx src/ui/guideWalkthrough/guideWalkthroughController.ts src/ui/guideWalkthrough/guideWalkthroughSteps.ts src/views/settings/GlobalSettingsPage.tsx src/views/guide/AiChatGuideDemoPage.tsx src/views/guide/PomodoroGuideDemoPage.tsx src/views/home/HomePage.tsx src/views/guide/GuidePage.tsx tests/e2e/guide-walkthrough.spec.ts tests/fixtures/mock-api.ts`：0 errors，1 warning；warning 为 `AppShell.tsx` 既有番茄 effect 依赖问题。
- `git diff --check`：通过，仅有仓库换行符提示。
- `rg -n "from __future__ import annotations" -g "*.py"`：无匹配。

## 当前风险与不确定项

- `AppShell.tsx` 仍有一个既有 `react-hooks/exhaustive-deps` warning：番茄 effect 缺少 `hasAccessiblePomodoroProjectRef` 依赖。该问题不在本次导引改动范围内，本次未扩展修复。

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

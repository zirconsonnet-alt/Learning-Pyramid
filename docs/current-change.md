# 当前变更：AI 问答与番茄钟导引回到真实页面

## 当前用户要求

- AI 问答和番茄钟导引不能使用 `/guide/demo/*` 假页面。
- 两个导引应和“创建学科”“学习复习”一样，在真实业务页面完成真实动作。

## 根因

- 上一轮把 AI 问答、番茄钟可用状态导引改到 demo route，绕过了真实业务页面。
- 真实 AI 页缺少导引用的发送按钮锚点、回答结果锚点和自动填充问题。
- 真实番茄钟页缺少导引用的保存按钮锚点，也没有在导引步骤里先准备一个可立即开启的真实计划草稿。

## 本次实际修改文件

- `frontend/src/ui/guideWalkthrough/guideWalkthroughController.ts`
  - AI 问答通过会员和 LLM 检查后进入真实项目 AI 页。
  - 番茄钟通过会员检查并确认存在可绑定项目后进入真实 `/pomodoro`。
  - 增加无项目时的番茄钟终止提示。
- `frontend/src/ui/guideWalkthrough/guideWalkthroughSteps.ts`
  - AI 问答步骤 route 改回真实项目 AI 页。
  - 番茄钟步骤改为真实流程：新建计划、绑定项目、保存计划、开启番茄钟、查看工作台。
- `frontend/src/views/ai/AiChatPage.tsx`
  - 导引确认问题时自动填入一个简短问题。
  - 给真实输入框、发送按钮和最新回答补齐导引锚点。
- `frontend/src/views/pomodoro/PomodoroPage.tsx`
  - 导引绑定项目步骤高亮时，在真实计划草稿中准备当天当前时间、1 个番茄和默认学科。
  - 给真实保存按钮补齐导引锚点。
  - 保存计划时触发导引步骤完成。
- `frontend/tests/e2e/guide-walkthrough.spec.ts`
  - AI 问答和番茄钟用例改为断言真实 route，禁止回到 demo 页。
- `docs/how-to-use-ai-chat.md`
  - 同步真实发送按钮文案。
- `docs/how-to-use-pomodoro.md`
  - 同步真实番茄钟导引路径。
- `docs/current-change.md`
  - 覆盖为当前任务工作单。

## 行为语义变化

- AI 问答导引不再进入 `/guide/demo/ai-chat`。
- 番茄钟导引不再进入 `/guide/demo/pomodoro`。
- 可用状态导引会操作真实项目 AI 页、真实番茄钟计划页和真实项目工作台。
- 会员门禁和 LLM 配置门禁保持不变。

## 重构说明

- 只做导引编排和真实页面导引辅助的局部调整。
- 未做跨模块重构。

## 未修改内容

- 未删除已有 demo route，避免在未确认外部入口的情况下做删除类改动。
- 未修改后端接口、数据库结构、部署配置。
- 未修改番茄钟计时算法或工作台门禁规则。

## 当前风险与不确定项

- 暂无已知影响本次改动正确性的风险。

## 仍需用户确认的问题

- 是否需要彻底删除 AI 问答和番茄钟 demo 页面及路由。删除涉及路由入口清理，本次未擅自处理。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

# 当前变更：桌宠导出上下文 HTML

## 当前用户要求

- 桌宠左下角增加“获取上下文”模式。
- 开启该模式后发送问题不调用 LLM。
- 桌宠回复一个可下载的文件，用户可以交给更强模型使用。
- 用户确认导出格式使用自包含 HTML，并要求文件内可内嵌当前视频帧。

## 根因

- 桌宠当前提交路径只有调用 `askCourseAgent` 生成回答这一条。
- 课程助手已经能组织当前复述点、字幕、播放时间和当前帧，但这套上下文构造逻辑没有独立导出入口。
- 若在桌宠组件内重新拼字幕与复述点，会产生重复逻辑和未来维护分叉。

## 本次实际修改文件

- `frontend/src/ui/llm/courseAgent.ts`
  - 抽出 `buildCourseAgentContextPackage`，复用课程助手已有字幕、复述点、时间、当前帧和历史对话组织逻辑。
  - 新增 `buildCourseAgentContextHtml`，生成自包含 HTML，上下文包内包含用户问题、复述点、字幕片段、引用片段、可复制提示词和内嵌当前视频帧。
  - `askCourseAgent` 改为先构建同一个上下文包，再调用项目 LLM stream。
- `frontend/src/views/workbench/components/WorkbenchPetAssistant.tsx`
  - 左下角新增“获取上下文”模式按钮。
  - 模式开启后提交问题只整理上下文并生成 HTML 下载，不调用 LLM。
  - 助手消息支持一个 HTML 下载附件。
- `tests/test_course_agent_static.py`
  - 增加静态防护，确保桌宠存在获取上下文模式、HTML 下载入口，并复用课程上下文包生成函数。
- `README.md`
  - 更新桌宠可导出上下文 HTML 的长期能力说明。
- `docs/domain-model.md`
  - 记录获取上下文模式复用课程上下文选择逻辑，且生成过程不调用 LLM。
- `docs/current-change.md`
  - 覆盖为当前任务工作单。

## 行为语义变化

- 桌宠底部左侧新增“获取上下文”模式。
- 开启后点击提交按钮会生成一条助手回复，内容为“已整理当前上下文，未调用 LLM”，并提供 HTML 下载按钮。
- 生成的 HTML 内嵌当前视频帧 data URL；若无法截帧，则 HTML 明确说明没有视频帧。
- 普通问答模式仍调用课程助手与项目 LLM。
- 获取上下文模式仍沿用桌宠面板原有可用性门禁，不新增独立未授权入口。

## 重构说明

- 做了当前需求范围内的局部重构。
- 将课程上下文构造从 `askCourseAgent` 中抽出，避免桌宠导出模式复制字幕选择和复述点拼接逻辑。
- 未改变项目 LLM API、会员门禁、字幕文件查找路径或视频帧截取工具。

## 未修改内容

- 未新增后端导出接口。
- 未修改数据库结构、部署脚本、LLM 配置或模型选择策略。
- 未改变全屏视频助手和 AI 问答页行为。
- 未把获取上下文做成绕过桌宠功能门禁的独立入口。

## 影响范围

- UI：桌宠底部操作区新增获取上下文模式与 HTML 下载附件。
- AI：普通问答仍调用 LLM；获取上下文模式不调用 LLM。
- 架构：课程上下文构造能力变成前端可复用函数。
- 文档：README、领域模型和当前工作单已更新。
- 不影响后端 API、部署、数据库结构。

## 当前风险与不确定项

- HTML 内嵌图片以 data URL 保存，文件体积会随当前帧大小增加。
- 外部模型是否能直接理解上传的 HTML 内嵌图片，取决于外部模型平台；HTML 文件本身能打开并显示图片。

## 验证记录

- 已运行：`python -m pytest tests/test_course_agent_static.py -q`，新增测试先失败，修复后 7 个测试通过。
- 已运行：`pnpm --dir frontend exec eslint src/ui/llm/courseAgent.ts src/views/workbench/components/WorkbenchPetAssistant.tsx`，结果通过。
- 已运行：`pnpm --dir frontend build`，结果通过；保留既有大 chunk 警告。

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

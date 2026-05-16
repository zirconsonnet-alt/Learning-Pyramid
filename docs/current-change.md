# 当前变更：视频助手提示与桌宠证据标签

## 当前用户要求

- 视频助手底部提示写了 `Shift+Enter / Ctrl+Enter 换行`，但实际 `Ctrl+Enter` 不能换行，属于误导。
- 视频助手底部提示不要被“当前模型不支持图片”等运行状态替换；这类提示已经在回答文本里出现。
- 桌宠回答里有依据片段按钮，但没有“依据片段”标签，和视频助手不一致。
- 将全部待提交改动提交，并同步到线上服务器。

## 根因

- 视频助手输入框实际只拦截纯 `Enter` 提交，`Shift+Enter` 走 textarea 默认换行；`Ctrl+Enter` 不是已实现的换行路径。
- 视频助手底部提示复用了 `assistantStatus`，导致运行状态会覆盖固定帮助提示，并和回答文本里的模型能力提示重复。
- 桌宠复用同类 `evidence` 数据，但只渲染按钮列表，没有像视频助手一样渲染“依据片段”标题。
- 这些都是展示层问题，不是证据生成、字幕选择、视频截帧或 LLM 调用链路问题。

## 本次实际修改文件

- `frontend/src/views/workbench/components/VideoPane.tsx`
  - 将视频助手提示改为 `Enter 提交问题，Shift+Enter 换行。视频助手会读取当前画面和附近字幕。`
  - 视频助手底部固定提示不再显示 `assistantStatus`；加载状态仍显示在原回答加载区域。
- `frontend/src/views/workbench/components/WorkbenchPetAssistant.tsx`
  - 在桌宠 `turn.evidence` 按钮列表上方增加“依据片段”标签。
  - 保留原有证据按钮、时间范围、标题和点击跳转逻辑。
- `tests/test_course_agent_static.py`
  - 增加视频助手快捷键提示静态检查。
  - 增加视频助手和桌宠证据区标签一致性静态检查。
- `docs/current-change.md`
  - 覆盖为当前待提交变更工作单。

## 行为语义变化

- 视频助手底部提示不再承诺未实现的 `Ctrl+Enter` 换行。
- 视频助手底部提示保持固定帮助文案，不再被运行状态覆盖。
- 桌宠证据区新增可见标签“依据片段”。
- 不改变快捷键处理、证据数据结构、证据数量、排序、点击跳转、字幕检索、视频截帧或 LLM 调用。

## 重构说明

- 未做重构。
- 本次是两个单点 UI 展示修正。

## 未修改内容

- 未修改快捷键处理逻辑。
- 未修改桌宠回答、复制上下文、提问提交或状态展示逻辑。
- 未修改 AI 问答页、后端 API、数据库、部署配置或字幕解析逻辑。

## 影响范围

- UI：视频助手底部帮助提示；桌宠回答中的证据片段区域。
- 测试：静态检查新增两条约束。
- 不影响 AI、后端 API、部署、数据库结构。

## 当前风险与不确定项

- 如果未来要支持 `Ctrl+Enter` 换行，需要单独确认键盘语义后改输入逻辑和提示。
- 无当前阻塞风险。

## 验证记录

- 已运行：`python -m pytest tests/test_course_agent_static.py::CourseAgentStaticTest::test_workbench_course_evidence_sections_use_consistent_label -q`，新增证据标签测试在生产代码修改前按预期失败。
- 已运行：`python -m pytest tests/test_course_agent_static.py -q`，10 个测试通过。
- 已运行：`pnpm --dir frontend exec eslint src/views/workbench/components/WorkbenchPetAssistant.tsx src/views/workbench/components/VideoPane.tsx`，通过。
- 已运行：`pnpm --dir frontend build`，通过；仍有既有 chunk size warning。
- 已运行：`git diff --check`，通过；仅提示工作区文件后续可能被 Git 转换为 CRLF。

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

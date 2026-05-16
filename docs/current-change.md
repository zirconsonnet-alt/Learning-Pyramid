# 当前变更：桌宠上下文复制按钮

## 当前用户要求

- 不再做成 HTML 导出。
- 桌宠改成两个按钮：`复制文本` 和 `复制图片`。
- 用户直接把文本和图片复制到剪贴板即可。

## 根因

- 之前的桌宠“获取上下文”方案把上下文导出成 HTML 文件，和用户现在想要的“直接复制到剪贴板”目标不一致。
- 课程助手已经有统一的上下文组装逻辑，复用它可以避免桌宠自己重新拼字幕、复述点和播放信息。

## 本次实际修改文件

- `frontend/src/ui/llm/courseAgent.ts`
  - 新增 `buildCourseAgentContextText`，把课程上下文整理成可复制的纯文本。
  - 移除 `buildCourseAgentContextHtml` 和相关 HTML 生成逻辑。
- `frontend/src/views/workbench/components/WorkbenchPetAssistant.tsx`
  - 去掉“获取上下文”模式和 HTML 下载附件。
  - 新增 `复制文本` 按钮，整理当前问题和上下文后写入剪贴板。
  - 新增 `复制图片` 按钮，把当前视频帧直接写入剪贴板。
- `tests/test_course_agent_static.py`
  - 更新静态检查，覆盖“复制文本 / 复制图片”新行为，并确认 HTML 导出入口已移除。
- `README.md`
  - 更新桌宠能力说明，从 HTML 导出改为剪贴板复制。
- `docs/domain-model.md`
  - 更新桌宠上下文能力说明，改为文本和图片剪贴板动作。

## 行为语义变化

- 桌宠不再生成 HTML 文件。
- `复制文本` 会把任务说明、用户问题、基本信息、当前视频帧信息、复述点上下文和相关字幕整理成纯文本后复制。
- `复制图片` 会把当前帧直接复制到剪贴板。
- 两个动作都不会调用 LLM。
- 普通问答模式不变，仍然走课程助手和项目 LLM。

## 重构说明

- 做了局部重构。
- 将桌宠上下文出口从 HTML 文件改成纯文本剪贴板输出，避免新增一条文件导出链路。
- 复用课程上下文选择逻辑，没有重复拼字幕和复述点。

## 未修改内容

- 未新增后端接口。
- 未改数据库、部署、模型配置或字幕查找规则。
- 未改全屏视频助手和 AI 问答页的回答链路。

## 影响范围

- UI：桌宠底部操作区从 HTML 导出改成两个剪贴板按钮。
- AI：普通问答仍调用 LLM；复制动作不调用 LLM。
- 文档：README、领域模型、当前工作单已更新。

## 当前风险与不确定项

- 图片复制依赖浏览器对 `ClipboardItem` 的支持；不支持时会明确报错。
- 当前帧复制前需要浏览器允许读写剪贴板。

## 验证记录

- 已运行：`python -m pytest tests/test_course_agent_static.py -q`，8 个测试通过。
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

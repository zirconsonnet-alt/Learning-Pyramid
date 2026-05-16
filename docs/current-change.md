# 当前变更：统一视频 AI 助手上下文

## 当前用户要求

- 桌宠和全屏视频助手统一为一套功能。
- 统一能力需要知道当前复述点内容、截取当前视频帧，并获取需要知道的字幕文本。
- 不再让全屏视频助手走 scoped raw LLM chat completions。
- 桌宠和全屏视频助手需要知道自己叫“雪豹”，与界面“问雪豹”文案一致。
- AI 问答页在课程视频上下文中也需要拿到对应时间点视频帧，并与字幕一起使用统一课程助手能力。
- 文本模型也要能使用课程助手，但必须明确显示本轮未使用视频帧。

## 根因

- 全屏视频助手原先走 scoped raw `/llm/chat-completions`，该入口已被后端边界拒绝。
- 桌宠和全屏视频助手对“视频学习助手”的语义一致，但入口和上下文组织分叉，导致全屏下无法使用同一套项目 AI 问答能力。
- 统一课程助手参数里已有调用方 `systemPrompt`，但请求项目 LLM 时未合并该参数，导致桌宠传入的身份与工作台状态提示没有进入 LLM；全屏视频助手也没有声明“雪豹”身份。
- AI 问答页虽可在课程视频节点调用统一课程助手选取字幕，但没有可复用的视频帧截取入口；原截帧逻辑只存在于播放器组件内部。
- AI 问答页课程助手失败后会静默退回项目级问答，导致用户无法确认本轮是否真正使用视频帧和课程字幕。
- 当前外部 LLM 服务明确拒绝 `image_url` 多模态消息，只接受 `text` 片段；课程助手原先把视频帧作为硬输入发送，导致桌宠和视频助手直接 400。

## 本次实际修改文件

- `adapter/schemas.py`
  - 为项目 LLM ask 请求增加 `imageInputs` DTO。
- `adapter/routers/system.py`
  - 将 `imageInputs` 透传到项目 LLM ask 与 stream 行为。
- `backend/system/api.py`
  - 让项目 LLM ask/stream 支持多模态图片消息，并在 debug 中脱敏图片 data URL。
- `frontend/src/ui/api/system.ts`
  - 为 `askProjectLlm` / `askProjectLlmStream` 增加 `imageInputs` 类型与请求字段，移除前端 raw chat completion 调用函数。
- `frontend/src/ui/llm/courseAgent.ts`
  - 将课程助手收敛到项目 `ask/stream`，统一组织复述点、字幕、当前帧和对话上下文。
  - 合并调用方传入的 `systemPrompt`，确保桌宠和全屏助手的身份与场景提示进入 LLM。
  - 当外部模型明确不支持 `image_url` 图片输入时，显式改用文本模式重试，并把“本轮未使用视频帧”写入回答。
- `frontend/src/ui/media/videoFrameCapture.ts`
  - 新增共享视频截帧工具，支持截取已显示视频帧或按视频源与时间点后台截帧。
- `frontend/src/views/ai/AiChatPage.tsx`
  - 适配新的课程助手参数。
  - 课程视频上下文中先按用户显式时间或复述点锚点截取视频帧，再把帧交给统一课程助手。
  - 课程视频上下文不再在课程助手失败后静默退回项目级问答。
- `frontend/src/views/workbench/WorkbenchPage.tsx`
  - 连接播放器截帧能力、录入草稿上下文、复习复述点上下文与桌宠。
- `frontend/src/views/workbench/workbenchAiContext.ts`
  - 新增工作台 AI 上下文类型。
- `frontend/src/views/workbench/components/VideoPane.tsx`
  - 暴露当前帧截取句柄，并把全屏录入草稿上下文传给课程助手。
  - 移除全屏视频助手问题区右侧的当前帧展示框。
  - 全屏视频助手调用课程助手时声明“你叫雪豹”。
  - 改用共享视频截帧工具，避免播放器与 AI 问答页重复截帧实现。
- `frontend/src/views/workbench/components/ReviewPane.tsx`
  - 上报当前复习复述点题面、已显示答案和引用。
- `frontend/src/views/workbench/components/WorkbenchPetAssistant.tsx`
  - 改为调用统一课程助手，并附带当前帧与当前复述点上下文。
  - 让桌宠对话内容在弹窗内滚动，不再撑开弹窗。
  - 桌宠系统提示声明“你叫雪豹”。
- `frontend/src/index.css`
  - 为桌宠问答弹窗增加视口高度约束和内部 flex 布局。
- `tests/test_project_llm_multimodal.py`
  - 覆盖项目 LLM ask/stream 图片输入与 debug 脱敏。
- `tests/test_course_agent_static.py`
  - 静态防护课程助手不再调用 scoped raw chat completion。
  - 静态防护课程助手会合并调用方系统提示，且桌宠和全屏视频助手都声明“雪豹”身份。
  - 静态防护视频截帧工具共享、AI 问答页传入 `initialFrame`，且课程视频上下文不静默 fallback。
  - 静态防护图片输入不被支持时必须显式文本模式重试并提示未使用视频帧。
- `README.md`
  - 更新字幕与 AI 上下文说明。
- `docs/domain-model.md`
  - 更新媒体与 AI 上下文长期语义。
- `docs/architecture.md`
  - 记录项目 LLM ask 的多模态入口边界。
- `docs/current-change.md`
  - 覆盖为当前任务工作单。

## 行为语义变化

- 项目 LLM ask/stream 可以接收最多 4 个图片 data URL 输入。
- 桌宠和全屏视频助手都通过课程助手调用项目 LLM ask/stream。
- 全屏视频助手会附带当前录入草稿上下文和当前视频帧；桌宠会按当前是否处于复习任务附带复习复述点或录入草稿上下文。
- 全屏视频助手不再额外展示“当前视频帧”预览框；用户直接看当前视频画面。
- 桌宠问答弹窗高度受浏览器视口限制，对话内容超长时在弹窗内滚动。
- 桌宠和全屏视频助手发起问题时会把“你叫雪豹”的身份提示传给 LLM。
- AI 问答页处于课程视频节点时，会在后台按用户显式时间或复述点锚点截取视频帧，并随字幕一起发送给统一课程助手。
- AI 问答页课程视频上下文若无法读取视频帧或课程助手失败，会直接报错，不再悄悄降级成普通项目问答。
- 若外部模型明确拒绝 `image_url` 图片输入，课程助手会重试文本模式，并在回答顶部提示本轮未使用视频帧。
- scoped raw `/llm/chat-completions` 仍保持拒绝，不作为前端功能入口。

## 重构说明

- 做了当前需求范围内的局部重构。
- 删除课程助手内部 raw chat completion、工具调用、OCR 分支和桌宠项目问答切换分支，避免两套 AI 管线继续并存。
- 将视频帧 canvas 截图逻辑从播放器组件抽到共享前端工具，供播放器、桌宠和 AI 问答页复用。
- 未改变项目身份解析、会员门禁、LLM 全局配置或字幕文件查找主路径。

## 未修改内容

- 未修改 LLM 服务配置字段、模型选择策略或 API Key 存储。
- 未修改字幕文件匹配规则；同目录同名字幕仍是播放器字幕和文本上下文主路径。
- 未改动数据库结构、部署脚本或认证权限策略。
- 未让 scoped raw chat completion 重新可用。
- 未新增后端按帧抽取 API；AI 问答页使用前端隐藏视频元素读取可访问视频源。
- 未对网络、鉴权、超时或其他模型错误做降级重试；只有外部模型明确拒绝图片输入时才进入文本模式。

## 影响范围

- API：项目 LLM ask/stream 请求体新增可选 `imageInputs`。
- 架构：视频 AI 能力收敛到项目 ask 管线。
- UI：桌宠和全屏视频助手的 AI 提问上下文增强；全屏助手去掉冗余当前帧展示框，桌宠弹窗改为视口内滚动。
- AI 问答页：课程视频上下文会先截取视频帧；帧读取失败会使本轮问答失败；模型不支持图片输入时会显式文本模式回答。
- 测试：新增后端多模态与前端静态防护测试。
- 不影响部署、数据库结构。

## 当前风险与不确定项

- 图片输入需要底层 LLM 服务支持 OpenAI 风格多模态 `image_url` 消息；如果模型不支持图片，课程助手会明确提示并改用文本上下文。
- 当前不绕回 raw chat completion，也不对图片以外的错误做降级重试。
- AI 问答页后台截帧依赖当前浏览器可访问视频源；本地目录未授权、视频源不可播放、画布受源策略限制时会直接失败并提示。

## 验证记录

- 已运行：`python -m pytest tests/test_project_llm_multimodal.py tests/test_course_agent_static.py tests/test_scoped_project_api_boundaries.py::RawLlmScopedRouteTest -q`，结果 5 个测试通过。
- 已运行：`python -m pytest tests/test_course_agent_static.py -q`，结果 3 个测试通过。
- 已运行：`python -m pytest tests/test_course_agent_static.py -q`，新增防护后先失败，修复后结果 5 个测试通过。
- 已运行：`python -m pytest tests/test_course_agent_static.py -q`，文本模型显式重试防护先失败，修复后结果 6 个测试通过。
- 已运行：`pnpm --dir frontend exec eslint src/ui/api/system.ts src/ui/llm/courseAgent.ts src/views/ai/AiChatPage.tsx src/views/workbench/WorkbenchPage.tsx src/views/workbench/components/ReviewPane.tsx src/views/workbench/components/VideoPane.tsx src/views/workbench/components/WorkbenchPetAssistant.tsx`，结果通过。
- 已运行：`pnpm --dir frontend exec eslint src/ui/llm/courseAgent.ts src/views/workbench/components/VideoPane.tsx src/views/workbench/components/WorkbenchPetAssistant.tsx`，结果通过。
- 已运行：`pnpm --dir frontend exec eslint src/ui/media/videoFrameCapture.ts src/views/ai/AiChatPage.tsx src/views/workbench/components/VideoPane.tsx src/ui/llm/courseAgent.ts`，结果通过。
- 已运行：`pnpm --dir frontend exec eslint src/ui/llm/courseAgent.ts src/views/workbench/components/VideoPane.tsx src/views/workbench/components/WorkbenchPetAssistant.tsx src/views/ai/AiChatPage.tsx`，结果通过。
- 已运行：`pnpm --dir frontend exec eslint tests/e2e/workbench-review.spec.ts tests/fixtures/mock-api.ts src/views/workbench/components/VideoPane.tsx src/views/workbench/components/WorkbenchPetAssistant.tsx`，结果通过。
- 已运行：`pnpm --dir frontend exec playwright test tests/e2e/workbench-review.spec.ts -g "workbench pet assistant stays above the video control bar" --workers=1`，结果 1 个测试通过。
- 已运行：`pnpm --dir frontend build`，结果通过；保留既有大 chunk 警告。
- 已运行：`pnpm --dir frontend build`，AI 问答页截帧改动后结果通过；保留既有大 chunk 警告。
- 已运行：`pnpm --dir frontend build`，文本模型显式重试改动后结果通过；保留既有大 chunk 警告。
- 已运行：`git diff --check`，结果无空白错误；Git 提示工作区文件下一次触碰时 LF 会转 CRLF。
- 已运行：`python tools/verify_backend_boundaries.py`，结果通过。
- 已运行：`python tools/verify_backend_boundaries.py`，文本模型显式重试改动后结果通过。

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

# 移动端 App MVP 设计

## 背景

LearningPyramid 当前已有 FastAPI 后端、React Web 前端和 Windows Tauri 桌面端。用户已确认下一步要做 Android 和 iPhone 上可安装的 App 软件，不是移动端网页适配。技术路线已确认使用 Expo-managed React Native。

## 目标

- 创建第一版 Android 和 iPhone 移动端 App 基础。
- 使用 Expo-managed React Native。
- 移动端客户端与现有 Web/Tauri 前端保持工程边界独立。
- 默认连接线上 API：`https://plm.xuebao.chat/api`。
- 覆盖第一版学习闭环：登录、学科/材料列表、进入 scoped project、浏览学习对象、播放已有媒体、查看复述点、提交基础复习结果。

## 非目标

- 不做 WebView 包壳。
- 不做仅面向移动浏览器的响应式改造。
- 不做手机本机文件导入。
- 不做离线缓存。
- 不迁移 Windows Tauri `NATIVE_LOCAL` 数据流。
- 不新增移动端专用后端协议。
- 当前阶段不处理 App Store、TestFlight、Android release 签名或应用商店发布流程。

## 推荐方案

新增 `mobile/` Expo-managed React Native 应用。该应用拥有自己的导航、页面、移动端 UI 和移动端 API client，只通过现有公开 FastAPI API 与后端通信。

这条路径避免把现有 React DOM UI 强行塞进移动端，也避免把移动 App 做成临时 WebView 包壳。

## 架构

```text
mobile/
  app 入口和导航
  screens/
  ui/
  api/
  state/
  tests/

backend/
  现有 FastAPI API

frontend/
  现有 Web 和 Tauri React DOM UI
```

移动端客户端不应从 `frontend/` 直接引用 React DOM 组件、Vite 专用模块或 Tauri runtime helper。后续如果需要共享 API 类型，应先确认共享包边界，再引入显式 shared package。

## API 数据流

```text
Expo React Native App -> HTTPS -> /api -> adapter routers -> SystemAPI -> persistence store
```

MVP 使用以下现有 API 家族：

- `/api/auth/*`
- `/api/subjects`
- `/api/subjects/{subjectId}/materials`
- `/api/subjects/{subjectId}/projects/{scopedProjectId}/learning-object-nodes`
- `/api/subjects/{subjectId}/projects/{scopedProjectId}/media/instances/{instanceId}/playback`
- `/api/subjects/{subjectId}/projects/{scopedProjectId}/recall-points`
- `/api/subjects/{subjectId}/projects/{scopedProjectId}/review-recommendations`
- `/api/subjects/{subjectId}/projects/{scopedProjectId}/review-tasks/{reviewTaskId}/commit`

所有 project-scoped 请求必须继续使用 `{subjectId, scopedProjectId}`。移动端不能发明或持久化后端内部 project id。

## 认证

第一版实现应调用现有登录、当前用户和退出接口。移动端只保存维持会话可用所需的客户端状态，不引入新的认证协议。

如果 React Native 无法干净承载当前基于浏览器 cookie 的会话语义，实施必须暂停，先确认认证策略。增加 token 或自定义 header 会影响后端 API、安全边界和部署配置，不能作为隐式兼容层直接加入。

## 媒体播放

MVP 只播放后端已支持的 playback descriptor。移动端播放器消费后端返回的描述符，并只支持 React Native/Expo 默认媒体能力可以承载的媒体类型。

不支持的 descriptor 必须显示为明确的“不支持”状态。不能在前端新增 fallback proxy、隐藏转码路径或移动端特殊 URL 改写，除非后续单独确认。

## UI 形态

移动端 UI 应保持克制、任务优先：

- 登录页。
- 学科列表。
- 学科内材料列表。
- 项目学习对象树。
- 学习对象详情，包含媒体播放和复述点。
- 复习队列或复习详情，用于基础复习提交。

UI 内容应极简，结构应浅，不自动增加装饰性卡片或解释文案，除非这些元素承载独立状态或操作。

## 测试

初始实现应包含：

- API envelope 解析测试。
- 如果新增本地会话状态，则覆盖认证状态测试。
- 可行时覆盖导航或页面 smoke 测试。
- 移动端 TypeScript 校验。
- 环境支持时通过 Expo 做 Android 本地启动 smoke。

## 风险

- React Native 的 cookie/session 行为可能不同于浏览器，这是主要潜在阻塞；如需后端认证变更，必须暂停确认。
- 部分 playback descriptor 可能无法被 Expo 默认媒体栈播放；这应作为明确的媒体能力缺口暴露，不能用 fallback 隐藏。
- 直接复用 Web 前端代码会把移动端耦合到 React DOM 和 Vite 假设；移动端应从独立 API client 和 UI 开始。

## 已确认决策

- 技术路线：React Native。
- 运行基座：Expo-managed。
- 第一后端目标：`https://plm.xuebao.chat/api`。
- MVP 不包含手机本机文件导入和离线缓存。
- MVP 是真实移动 App，不是 WebView 包壳。

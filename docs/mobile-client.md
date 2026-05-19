# 移动端客户端

本文记录 Android 和 iPhone App 的当前确认边界。移动端客户端采用 React Native，不是移动端网页适配，也不是 WebView 包壳。

## 当前阶段

当前阶段目标是创建第一版移动端 MVP：

- 使用 Expo-managed React Native。
- 新增独立移动端工程 `mobile/`。
- 默认连接线上 API：`https://plm.xuebao.chat/api`。
- 复用现有 FastAPI API envelope、认证语义和 scoped project 语义。
- 使用移动端原生 UI 重新实现核心学习流程。

当前仓库已包含 `mobile/` Expo 应用预览。当前实现包含：

- 登录、会话恢复和退出。
- 学科列表和材料列表。
- scoped project 原生移动工作台：默认进入当前学习对象，支持目录切换、已有复述点查看、文本复述点草稿和 `learning task` 提交。
- 后端 playback descriptor 媒体播放；当前移动端明确不支持 `NATIVE_LOCAL`、`BROWSER_LOCAL` 和 `MANUAL` 播放来源。
- 队列头复习任务展示和基础 `canRecall` 提交。
- 移动端 API client、认证状态、领域 API、导航、工作台、媒体、草稿和复习队列测试。

当前阶段不包含：

- 手机本机文件导入。
- 离线缓存。
- Windows Tauri `NATIVE_LOCAL` 数据流迁移。
- WebView 包壳。
- Android / iOS 原生裸工程维护。
- 移动端专用后端协议。

## 功能边界

第一版移动端工作台按桌面/网页工作台语义实现学习主流程：

- 登录、获取当前用户、退出。
- 学科和材料项目列表。
- 进入学科材料对应的 scoped project。
- 在项目内默认进入学习优先工作台，而不是只停留在对象列表。
- 通过目录切换当前学习对象。
- 获取已有课程视频或音频播放描述符并播放。
- 查看当前学习对象已有复述点。
- 新建文本复述点草稿，并按当前播放时间生成 `t=<毫秒>` 锚点。
- 将当前学习对象的草稿提交为一个 `learning task`。
- 队列非空时先进入复习门禁，提交基础复习结果。

移动端不负责创建本机材料源，也不扫描手机文件系统。涉及材料导入、百度网盘账号连接、离线缓存、推送提醒、支付和发布渠道的能力，需要后续单独确认边界后再实现。

## 数据流

移动端请求数据流固定为：

```text
React Native App -> HTTPS -> FastAPI /api -> SystemAPI -> 持久化 store
```

移动端必须使用现有公开 HTTP API：

- `/api/auth/*` 用于认证。
- `/api/subjects` 和 `/api/subjects/{subjectId}/materials` 用于学科和材料列表。
- `/api/subjects/{subjectId}/projects/{scopedProjectId}/...` 用于项目内学习对象、媒体播放、复述和复习。

移动端不直接访问后端 repository、内部 project id 或私有 helper。公开 scoped project id 仍必须由后端 `resolve_scoped_project()` 边界解析。

## 认证边界

第一版移动端沿用现有登录 API。移动端本地会保存会话所需的认证状态，但不引入新的认证协议。

如果实现阶段发现浏览器 cookie 会话不能在 React Native 中稳定承载移动端登录态，必须暂停确认认证策略。可选方向包括继续 cookie 会话、增加明确的移动端 token 会话，或调整后端 cookie 策略；不能通过隐式 header、特殊分支或临时兼容层绕过认证边界。

## 媒体边界

移动端只播放后端返回的已有播放描述符。第一版不实现：

- 手机本机路径播放。
- 手机本机字幕扫描。
- 百度网盘本机代理。
- 离线缓存。

如果某类 `PlaybackDescriptor` 的 `url` 或 `playbackKind` 在移动端播放器中不可用，应上报为媒体能力缺口，不应在前端添加未确认的 fallback 播放路径。

当前移动端播放器使用 `expo-video`。支持路径仅限后端 descriptor 能直接给出的 `SERVER_FS` / `BAIDU_NETDISK` URL；`NATIVE_LOCAL`、`BROWSER_LOCAL` 和 `MANUAL` 会显示明确不可播放状态。原生播放器请求会携带当前 `plm_session` Cookie header。

真实 Android/iOS 环境中，受保护 HLS/文件资源是否能稳定通过原生播放器 header 访问，仍需要 emulator 或真机 smoke 验证。

## 本地运行

```powershell
pnpm --dir mobile install
$env:EXPO_PUBLIC_API_BASE_URL = "https://plm.xuebao.chat/api"
pnpm --dir mobile start
```

常用验证：

```powershell
pnpm --dir mobile test
pnpm --dir mobile typecheck
```

## 工程边界

移动端工程应保持独立：

- `mobile/` 承载 Expo 应用、移动端页面、移动端 API client 和移动端测试。
- `frontend/` 继续承载 Web/Tauri 复用的 React DOM UI。
- 后续如要共享类型或 API schema，应先确认共享包边界，不能从移动端直接引用 Web 专用组件或 Vite 专用模块。

移动端原生工作台不从 `frontend/` 复用 React DOM 工作台组件，但功能语义以桌面/网页工作台为准：目录选内容、播放器学习、复述点草稿、提交 `learning task`、复习门禁。移动端只改变交互布局，不新增移动端专用学习协议。

## 验证边界

第一版移动端最小验证应覆盖：

- TypeScript 类型检查。
- API client envelope 解析测试。
- 登录态状态机或认证存储测试。
- Android 本地启动 smoke。

iPhone 真机、TestFlight、App Store、Android release 签名和应用商店发布不属于当前阶段验收。

# 当前变更：移动端播放器播放时间回传

## 当前用户要求

- 当前执行 mobile native workbench Task 3：给移动端播放器增加播放时间回调。
- `LearningMediaPlayer` 需要在实际可播放视频内部监听 `expo-video` 的 `timeUpdate`，通过可选 `onPlaybackTimeChange` 回传当前播放时间毫秒数。
- 该时间用于后续工作台复述点草稿生成 `t=<毫秒>` 锚点。
- 不修改播放来源、媒体 URL/cookie 语义、后端 API、数据库、部署、Web 或 `LearningObjectScreen` 行为。

## 根因

- 当前 `LearningMediaPlayer` 只渲染 `expo-video`，没有对外暴露播放时间回调。
- 当前 `PlayableVideo` 没有设置 `timeUpdateEventInterval`，也没有订阅 `timeUpdate` 事件。

## 本次实际修改文件

- `mobile/__tests__/learning-object-detail.test.tsx`
  - 新增播放器播放时间回调用例，验证可播放 descriptor 会设置 `timeUpdateEventInterval = 0.5`、订阅 `timeUpdate`，并将秒转换为毫秒回调。
  - 将测试中的复述点锚点更新为 `t=10000`，匹配移动端复述点草稿锚点格式。
- `mobile/src/screens/LearningMediaPlayer.tsx`
  - 新增可选 prop `onPlaybackTimeChange?: (currentMs: number) => void`。
  - 在 `PlayableVideo` 内通过 `useEffect` 订阅 `timeUpdate`，忽略非有限时间，并以 `Math.max(0, Math.floor(currentTime * 1000))` 回传毫秒数。
  - 清理订阅时调用 `remove()`，并把 `timeUpdateEventInterval` 重置为 `0`。
- `docs/current-change.md`
  - 更新为当前 Task 3 工作单。

## 行为语义是否变化

- 是。支持播放的移动端 `PlaybackDescriptor` 现在可以通过可选 `onPlaybackTimeChange` 回传当前播放时间毫秒数。
- 未传入该回调时，播放器行为保持不变。
- 不支持播放的 descriptor 仍显示既有明确不可播放状态。
- 原生播放器请求的 URL 解析和 Cookie header 行为不变。

## 重构说明

- 无跨模块重构。
- 仅在现有播放器组件内部增加必要事件订阅，保持组件职责和媒体边界不变。

## 未修改内容

- 未修改播放来源选择。
- 未修改媒体 URL 或 session cookie 语义。
- 未修改后端 API、数据库结构、部署配置、Web/Tauri 代码或 `LearningObjectScreen` 行为。
- 未新增草稿持久化。
- 未修改测试去适配错误实现。
- 未新增 fallback、shim、legacy、临时兼容逻辑或特殊分支。

## 影响范围

- API：无后端 API 变化。
- 架构：无跨层架构变化。
- 部署：无影响。
- 数据结构：无数据库或协议结构变化。
- UI：无可见 UI 变化。
- 测试：补充移动端播放器播放时间回传测试。

## 当前风险点和不确定项

- 无已知风险点。

## 仍需用户确认的问题

- 无。

## 验证记录

- RED 已运行：`pnpm --dir mobile test -- learning-object-detail.test.tsx`
  - 结果：失败，符合预期；新增测试 `reports playback time updates in milliseconds` 失败，原因为当前实现未设置 `timeUpdateEventInterval`，收到值仍为 `0`。
- GREEN 已运行：`pnpm --dir mobile test -- learning-object-detail.test.tsx`
  - 结果：通过，1 个测试套件、5 个测试通过。
- GREEN 已运行：`pnpm --dir mobile typecheck`
  - 结果：通过。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

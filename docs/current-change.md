# 当前变更：移动端学习对象详情与媒体播放

## 当前用户要求

- 继续 React Native 移动端 App MVP。
- 当前执行 Task 7：实现学习对象详情、媒体播放和节点复述点查看。
- 继续只使用现有公开 API，不迁移 Windows Tauri `NATIVE_LOCAL` 数据流。

## 根因

- 移动端已能浏览学习对象列表，但节点点击尚未进入详情。
- 移动端 API client 缺少节点详情和节点级复述点方法。
- 媒体播放不能复用 Web/Tauri 的 DOM、HLS.js、本地目录或 Tauri 代理能力，需要只消费后端 playback descriptor，并对不支持来源给出明确状态。

## 本次实际修改文件

- `mobile/__tests__/learning-object-detail.test.tsx`
  - 新增学习对象详情、播放器和 API runtime RED/GREEN 测试。
- `mobile/__tests__/domain-api.test.ts`
  - 覆盖节点详情和节点复述点公开 scoped API 路径。
- `mobile/src/api/ApiProvider.tsx`
  - 在移动端 API context 中增加 `apiBaseUrl` 和当前 session cookie reader，供媒体请求构建原生播放器 headers。
- `mobile/src/api/config.ts`
  - 集中移动端 API base URL 默认值。
- `mobile/src/api/http.ts`
  - 新增 playback descriptor URL 解析 helper。
- `mobile/src/api/learningObjects.ts`
  - 新增 `getNode` 和 `listRecallPointsByNode`。
- `mobile/src/api/richContent.ts`
  - 新增移动端复述点富文本 schema 与纯文本展示 helper。
- `mobile/src/api/review.ts`
  - 将 `RecallPoint` 的 question/answer 收紧为结构化富文本。
- `mobile/src/screens/LearningMediaPlayer.tsx`
  - 新增基于 `expo-video` 的移动端媒体播放器。
  - 对 `NATIVE_LOCAL`、`BROWSER_LOCAL`、`MANUAL` 显示明确不支持或不可播放状态。
- `mobile/src/screens/LearningObjectScreen.tsx`
  - 新增学习对象详情页，展示标题、媒体和复述点。
- `mobile/src/app/learning-object/[subjectId]/[scopedProjectId]/[nodeId].tsx`
  - 新增学习对象详情路由。
- `mobile/src/app/project/[subjectId]/[scopedProjectId].tsx`
  - 将学习对象列表点击接入详情路由。
- `mobile/src/app/_layout.tsx`
  - 向 `ApiProvider` 注入 API base URL 和 session cookie reader。
- `docs/current-change.md`
  - 覆盖为当前 Task 7 工作单。

## 行为语义是否变化

- 移动端学习对象列表点击后进入对象详情。
- leaf 节点详情会加载后端 playback descriptor，并通过 `expo-video` 播放支持的 `SERVER_FS` / `BAIDU_NETDISK` descriptor URL。
- 原生播放器请求会携带当前 `plm_session` Cookie header。
- `NATIVE_LOCAL` 不迁移到移动端，显示“移动端不支持桌面本地媒体”。
- 详情页显示节点级复述点问题和答案。
- 不改变后端 API、部署、数据库结构或 Web/Tauri 行为。

## 重构说明

- 做了当前需求范围内的局部结构整理。
- `apiBaseUrl` 从 `_layout` 局部常量迁移到 `mobile/src/api/config.ts`，避免路由和播放器重复配置。
- `ApiProvider` 增加运行时信息，是为了避免媒体播放器依赖全局状态或重复创建 session 边界。

## 未修改内容

- 未修改后端 API、认证协议、部署或数据结构。
- 未新增移动端专用媒体协议。
- 未新增本地代理、转码、WebView、Tauri bridge 或手机本机文件导入。
- 未实现复习提交；Task 8 处理。
- 未更新长期文档；移动端 MVP 预览整体完成后统一同步。

## 影响范围

- API：仅移动端 client 新增对现有公开 scoped endpoints 的调用。
- 架构：移动端内部 API context 增加运行时信息。
- 部署：无影响。
- 数据结构：无影响。
- UI：新增移动端学习对象详情与媒体/复述点展示。
- 测试：新增详情页与播放器测试，扩展领域 API 路径测试。

## 当前风险点和不确定项

- 真实 Android/iOS 原生播放器是否能稳定携带 Cookie header 访问受保护 HLS/文件资源，仍需后续 emulator/device smoke 验证。
- Expo 默认媒体能力之外的 descriptor 会显示不支持，不做隐藏 fallback。

## 仍需用户确认的问题

- 无。

## 验证记录

- RED：`pnpm --dir mobile test -- learning-object-detail.test.tsx` 失败，摘要：`../src/screens/LearningMediaPlayer` 不存在。
- RED：`pnpm --dir mobile test -- domain-api.test.ts` 失败，摘要：`api.learningObjects.getNode is not a function`。
- GREEN：`pnpm --dir mobile test -- learning-object-detail.test.tsx` 通过，1 个测试套件、4 个测试通过。
- GREEN：`pnpm --dir mobile test -- domain-api.test.ts` 通过，1 个测试套件、1 个测试通过。
- 已运行：`pnpm --dir mobile test`，通过，8 个测试套件、25 个测试通过。
- 已运行：`pnpm --dir mobile typecheck`，通过。
- 已运行：`git diff --check -- docs/current-change.md mobile/__tests__/learning-object-detail.test.tsx mobile/__tests__/domain-api.test.ts mobile/src/api/ApiProvider.tsx mobile/src/api/config.ts mobile/src/api/http.ts mobile/src/api/learningObjects.ts mobile/src/api/richContent.ts mobile/src/api/review.ts mobile/src/screens/LearningMediaPlayer.tsx mobile/src/screens/LearningObjectScreen.tsx mobile/src/app/_layout.tsx mobile/src/app/project mobile/src/app/learning-object`，通过；仅有 Git 换行转换 warning，无 whitespace error。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

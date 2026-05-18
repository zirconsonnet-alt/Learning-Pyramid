# 当前变更：移动端原生工作台

## 当前用户要求

- Expo Go Android 原生移动端补齐学习主流程，继续 React Native 路线，并按桌面/网页工作台语义实现学习优先工作台。
- 本轮最终验证记录自动化检查结果；不修改代码、测试、配置、锁文件、后端/API/部署/Web/Tauri 语义。

## 本次实际修改文件

- `mobile/src/api/learningTasks.ts`
  - 新增移动端 `POST /learning-tasks` client，复用 scoped project 路径和既有后端 API。
- `mobile/src/api/types.ts`
  - 将 `learningTasks` 纳入移动端聚合 API。
- `mobile/__tests__/domain-api.test.ts`
  - 覆盖移动端领域 API 路径、方法和 `learning task` 提交 body。
- `mobile/src/workbench/recallDrafts.ts`
  - 新增纯函数草稿模型、校验和提交 payload 构造。
- `mobile/__tests__/workbench-drafts.test.ts`
  - 覆盖草稿创建、校验、锚点和提交 payload。
- `mobile/src/screens/LearningMediaPlayer.tsx`
  - 将播放器当前时间以毫秒回传给工作台。
- `mobile/__tests__/learning-object-detail.test.tsx`
  - 覆盖播放器 `timeUpdate` 到毫秒回调的连接。
- `mobile/src/screens/MobileWorkbenchScreen.tsx`
  - 新增原生移动工作台 presentational screen，展示当前学习对象、目录、媒体、已有复述点、草稿和复习门禁。
- `mobile/__tests__/mobile-workbench-screen.test.tsx`
  - 覆盖工作台渲染、目录选择、草稿交互、提交门禁和复习入口。
- `mobile/src/app/project/[subjectId]/[scopedProjectId].tsx`
  - 将项目路由接到 query-driven 移动工作台，处理 active leaf、播放时间、草稿提交、query invalidation 和 queue gate。
- `mobile/__tests__/project-route-workbench.test.tsx`
  - 覆盖 route 层草稿提交、当前节点草稿清理、query invalidation、提交门禁和 active leaf reconcile。
- `docs/mobile-client.md`
  - 同步移动端原生工作台能力、功能边界和工程边界。
- `docs/current-change.md`
  - 覆盖为本次移动端原生工作台最终状态，并记录最终验证结果。
- `mobile/__tests__/learning-navigation.test.tsx`
  - 未修改；学科和材料导航相关覆盖保留，项目路由行为由工作台 screen/API/route 测试覆盖。

## 行为语义是否变化

- 是。移动端项目入口从只浏览学习对象列表，变为默认进入学习优先的原生工作台。
- 是。移动端支持目录切换当前学习对象、查看已有复述点、基于当前播放时间创建文本复述点草稿，并提交为一个 `learning task`。
- 是。移动端工作台在 review queue 有队列头、加载、刷新、错误、无 active leaf、无草稿或提交中时阻止草稿提交。
- 是。移动端播放器继续只播放后端 playback descriptor 支持的来源；`NATIVE_LOCAL`、`BROWSER_LOCAL` 和 `MANUAL` 明确不可播放。
- 否。后端 API、数据库结构、部署方式、认证协议、Web/Tauri 工作台语义未变化。

## 重构说明

- 做了移动端范围内的局部结构补齐：新增 `recallDrafts` 纯函数模块承载草稿与 payload 构造，避免将草稿校验和提交体拼装散落在 screen 或 route 中。
- 做了 route container 内部状态整理：统一提交门禁、review queue 阻断状态和 active leaf reconcile。
- 未做跨模块重构，未改变公共后端接口、共享协议或 Web/Tauri 边界。

## 未修改内容

- 未修改后端 API、数据库、部署配置、认证协议。
- 未修改 Web/Tauri 工作台实现或语义。
- 未新增移动端专用学习协议。
- 未从 `frontend/` 复用 React DOM 工作台组件。
- 未实现手机本机文件导入、离线缓存、移动端本机路径播放、推送、支付或发布渠道能力。
- 未修改 `mobile/__tests__/learning-navigation.test.tsx`，其导航覆盖保留。

## 影响范围

- API：移动端 client 新增对既有 `POST /learning-tasks` 的调用；不新增后端 API。
- 架构：`mobile/` 仍是独立 Expo-managed React Native 应用；不引入共享包或 Web 组件依赖。
- 部署：无影响。
- 数据结构：无影响。
- UI：移动端项目入口升级为学习优先工作台，交互布局为原生移动端实现。
- 测试：新增和更新移动端 API、草稿、媒体、工作台、项目路由相关测试；导航覆盖保留。

## 当前风险点和不确定项

- Expo 原生播放器携带 Cookie header 播放受保护媒体仍需 Android/iOS 真机或 emulator smoke 验证。
- 未运行 Android 启动 smoke，原因：当前环境没有可用 `adb` 命令，无法确认连接的 Android 设备或模拟器。

## 仍需用户确认的问题

- 无。

## 验证记录

- Tasks 1-5 已运行并通过目标 mobile test suites，覆盖 mobile domain API、workbench drafts、media time update、mobile workbench screen、project route workbench 和保留的 learning navigation。
- Tasks 1-5 已运行并通过 `pnpm --dir mobile typecheck`。
- Task 6 已运行：`git diff --check -- docs/mobile-client.md docs/current-change.md`
  - 结果：通过。
- Task 7 已运行：`pnpm --dir mobile test`
  - 结果：通过，12 个测试套件、44 个测试通过。
- Task 7 已运行：`pnpm --dir mobile typecheck`
  - 结果：通过。
- Task 7 已运行：`pnpm --dir mobile exec expo --version`
  - 结果：通过，输出 `55.0.30`。
- Task 7 已运行：`git diff --check -- docs/mobile-client.md docs/current-change.md mobile`
  - 结果：通过。
- Task 7 已运行：`adb devices`
  - 结果：失败，当前环境未识别 `adb` 命令；未运行 Android 启动 smoke。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

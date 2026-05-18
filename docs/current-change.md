# 当前变更：Task 5 移动端项目路由接入原生工作台

## 当前用户要求

- 将移动端 project route 从旧 `ProjectScreen` 列表页替换为 query-driven native workbench container。
- 保留 `ProjectScreen` 组件级覆盖。
- 新增 route 集成测试，覆盖默认首个 leaf、草稿创建、提交 learning task、提交后清空草稿与 query invalidation。
- 不修改后端 API、数据库、部署、Web/Tauri，不新增协议或持久化。

## 根因

- `mobile/src/app/project/[subjectId]/[scopedProjectId].tsx` 仍渲染旧 `ProjectScreen` 列表页，并通过 `openNode` 跳转到 learning-object 详情页。
- 已有 `MobileWorkbenchScreen`、draft builder、learning task API 和播放器时间回调，但项目入口没有把它们接到移动端学习主流程。

## 本次实际修改文件

- `mobile/src/app/project/[subjectId]/[scopedProjectId].tsx`
  - 替换为 query-driven native workbench container。
  - 读取 scoped route params，加载 learning object nodes、review queue、active leaf playback 和 active node recall points。
  - 默认选择首个 leaf，支持目录切换 leaf、播放时间回调、本地草稿创建/编辑/删除和提交 learning task。
  - 提交成功后清除当前 instance 草稿，并 invalidate review queue、active node recall points、project recall points 和 nodes。
- `mobile/__tests__/project-route-workbench.test.tsx`
  - 新增 project route 集成测试，mock `expo-router` 参数和 `MobileWorkbenchScreen`，验证 workbench 容器提交当前学习对象草稿并 invalidates 相关 query。
  - 测试 QueryClient 显式关闭测试期 GC timer，并在断言后卸载和清理，避免测试进程残留异步句柄。
- `mobile/__tests__/learning-navigation.test.tsx`
  - 已确认保留 `ProjectScreen` 学习对象标题和加载错误覆盖；文件无需实际修改。
- `docs/current-change.md`
  - 覆盖为当前 Task 5 工作单和验证记录。

## 行为语义是否变化

- 是。进入移动端项目 route 现在直接进入 native workbench，而不是旧学习对象列表页。
- project route 默认选择首个 leaf 作为 active learning object。
- 当前 active leaf 支持本地草稿、按播放时间生成 `t=<ms>` 锚点、提交 `learningTasks.submitLearningTask`。
- review queue loading 或存在 `headId` 时，route 容器会阻止提交草稿。

## 重构说明

- 仅做 route 内部容器替换，没有跨模块重构。
- 未改变 `MobileWorkbenchScreen` presentational 边界、API client、后端 API 或数据结构。

## 未修改内容

- 未修改 `MobileWorkbenchScreen` presentational 实现。
- 未修改 API client、后端 API、数据库、部署、Web/Tauri 工作台。
- 未保留旧 `openNode` learning-object detail navigation 入口。
- 未新增持久化、fallback、shim、legacy、临时兼容逻辑或特殊分支。
- 未修改测试去适配错误实现。
- 未更新长期文档；本任务文件范围限定为 route/tests/current-change，长期移动端文档更新应在后续文档任务中处理。

## 影响范围

- API：无变化。
- 架构：仅移动端 route 容器接线变化。
- 部署：无影响。
- 数据结构：无影响。
- UI：移动端项目入口改为原生工作台。
- 测试：新增 project route 集成覆盖；保留 ProjectScreen 覆盖。

## 当前风险点和不确定项

- 无已知影响本次改动正确性的风险。

## 仍需用户确认的问题

- 无。

## 验证记录

- RED 已运行：`pnpm --dir mobile test -- learning-navigation.test.tsx project-route-workbench.test.tsx mobile-workbench-screen.test.tsx workbench-drafts.test.ts domain-api.test.ts`
  - 结果：失败符合预期。关键错误：`Unable to find an element with text: active:第一课`，实际渲染旧 `ProjectScreen` 的“学习对象”列表。
- GREEN 已运行：`pnpm --dir mobile test -- learning-navigation.test.tsx project-route-workbench.test.tsx mobile-workbench-screen.test.tsx workbench-drafts.test.ts domain-api.test.ts`
  - 结果：通过，5 个测试套件、16 个测试通过。
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

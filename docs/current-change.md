# 当前变更：Task 5 移动端工作台 route review 修复

## 当前用户要求

- 修复 Task 5 代码质量 review 指出的两个 route container 缺口。
- `submitDrafts` 的提交门禁必须不弱于 UI 状态，直接调用 route callback 时也要阻止 queue refetch、queue error、已有 head、无 active leaf、无草稿和提交中重复提交。
- active selected leaf 从节点列表消失后，route 必须显式切到当前首个剩余 leaf，并在 active instance 改变时重置 `currentMs`。
- 按 TDD 先补失败测试，再改实现。
- 不修改后端 API、数据库、部署、Web/Tauri、API client 或 `MobileWorkbenchScreen` presentational 语义。

## 根因

- `mobile/src/app/project/[subjectId]/[scopedProjectId].tsx` 中 `submitDrafts` 只检查 `queueQ.isLoading` 和 `queueQ.data?.headId`，没有复用一个包含 fetching、error 和 mutation pending 的统一提交条件。
- `activeNode` 会在 `activeNodeId` 指向的 leaf 消失后派生为 `firstLeaf(nodes)`，但 `activeNodeId` 和 `currentMs` 没有同步到这个 resolved active leaf，导致新草稿可能使用旧播放时间。

## 本次实际修改文件

- `mobile/__tests__/project-route-workbench.test.tsx`
  - 新增 route callback 级提交门禁覆盖：queue refetch/fetching 和 stale queue error 状态下，直接调用 mocked screen 的 `onSubmitDrafts` 不会调用 `submitLearningTask`。
  - 新增 active selection reconcile 覆盖：当前 selected leaf 从 nodes 中消失后，route 切到首个剩余 leaf，下一次新增草稿使用新 leaf 的 instance/title 和重置后的 `t=0` 锚点。
- `mobile/src/app/project/[subjectId]/[scopedProjectId].tsx`
  - 新增统一 `canSubmitDrafts`，并让 `submitDrafts` 使用同一个 boolean。
  - 显式 reconcile resolved active leaf：当 `activeNode` 与 `activeNodeId` 不一致时同步 `activeNodeId`；当 active instance 改变或 active leaf 消失时重置 `currentMs`。
- `docs/current-change.md`
  - 覆盖为本次 review fix 工作单和验证记录。

## 行为语义是否变化

- 是。route callback 现在会在 review queue 正在 fetching、处于 error、已有 head、提交中、无 active leaf 或无草稿时拒绝提交草稿。
- 是。当前 selected leaf 失效后，route 会同步选择当前首个可用 leaf；active instance 变化后新草稿锚点从 `t=0` 开始。

## 重构说明

- 仅做 route container 内部状态与门禁整理。
- 未改变 `MobileWorkbenchScreen` props/API、presentational 语义、API client、后端 API、数据结构或部署方式。

## 未修改内容

- 未修改 `MobileWorkbenchScreen`。
- 未修改 API client、后端 API、数据库、部署、Web/Tauri。
- 未修改测试去适配错误实现；新增测试先 RED 后实现。
- 未更新长期文档；本次是 Task 5 review fix，长期移动端能力边界没有新增。

## 影响范围

- API：无变化。
- 架构：无跨模块变化，仅 route container 内部状态 reconcile。
- 部署：无影响。
- 数据结构：无影响。
- UI：无 presentational API 或文案变化。
- 测试：扩展 project route 集成测试覆盖 review fix。

## 当前风险点和不确定项

- 无已知影响本次改动正确性的风险。

## 仍需用户确认的问题

- 无。

## 验证记录

- RED 已运行：`pnpm --dir mobile test -- project-route-workbench.test.tsx`
  - 结果：失败符合预期。关键失败包括 queue fetching/error 时仍调用 `submitLearningTask`，以及 leaf 切换后新草稿 anchor 仍为旧 `t=12000`。
- GREEN 已运行：`pnpm --dir mobile test -- project-route-workbench.test.tsx`
  - 结果：通过，1 个测试套件、4 个测试通过。
- GREEN 已运行：`pnpm --dir mobile test -- learning-navigation.test.tsx project-route-workbench.test.tsx mobile-workbench-screen.test.tsx workbench-drafts.test.ts domain-api.test.ts`
  - 结果：通过，5 个测试套件、19 个测试通过。
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

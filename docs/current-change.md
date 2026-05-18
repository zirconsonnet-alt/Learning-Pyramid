# 当前变更：移动端复述点草稿模型

## 当前用户要求

- 当前执行 mobile native workbench Task 2：新增 recall draft model。
- 只新增移动端本地纯函数草稿模型和测试。
- 不修改 UI、路由、后端 API、数据库、部署或草稿持久化。

## 根因

- 移动端后续工作台需要新增复述点草稿。
- 当前没有纯草稿模型；如果后续在 UI 或 route 中直接拼提交 payload，会产生重复逻辑和错误边界。

## 本次实际修改文件

- `mobile/__tests__/workbench-drafts.test.ts`
  - 新增复述点草稿模型测试，覆盖创建草稿、完整草稿转提交 items、不完整草稿拒绝提交、文本转 `RichContent` 时 trim。
- `mobile/src/workbench/recallDrafts.ts`
  - 新增 `MobileRecallDraft`、`CreateRecallDraftInput` 类型。
  - 新增 `createRecallDraft`、`recallDraftTextToRichContent`、`getIncompleteDraftReason`、`buildSubmitLearningTaskItems` 纯函数。
- `docs/current-change.md`
  - 覆盖为当前 Task 2 工作单。

## 行为语义是否变化

- 是。移动端现在具备本地文本复述点草稿模型：
  - 草稿可用当前播放毫秒生成 `t=<毫秒>` 锚点。
  - 完整草稿可转换为 `SubmitLearningTaskItem`。
  - 不完整草稿会在生成提交 payload 前返回或抛出明确原因。
- 后端 API 语义未变化。
- 数据库结构未变化。
- 部署语义未变化。
- Web/Tauri 工作台语义未变化。
- UI 和路由未变化。

## 重构说明

- 无跨模块重构。
- 新增独立 `mobile/src/workbench/recallDrafts.ts`，把草稿到提交 payload 的转换集中在移动端 workbench 边界内，避免后续 UI/route 重复拼装。

## 未修改内容

- 未修改 UI、路由、后端 API、数据库结构、部署配置、Web/Tauri 工作台代码。
- 未新增草稿持久化。
- 未修改测试去适配错误实现。
- 未新增 fallback、shim、legacy 或临时兼容逻辑。

## 影响范围

- API：无后端 API 变化；仅复用移动端已有 `SubmitLearningTaskItem` 类型。
- 架构：无跨层架构变化。
- 部署：无影响。
- 数据结构：无数据库或协议结构变化；新增移动端本地草稿类型。
- UI：无影响。
- 测试：新增移动端 workbench draft 单元测试。

## 当前风险点和不确定项

- 无已知风险点。

## 仍需用户确认的问题

- 无。

## 验证记录

- RED 已运行：`pnpm --dir mobile test -- workbench-drafts.test.ts`
  - 结果：失败，符合预期；失败原因为 `../src/workbench/recallDrafts` 模块不存在。
- GREEN 已运行：`pnpm --dir mobile test -- workbench-drafts.test.ts`
  - 结果：通过，1 个测试套件、4 个测试通过。
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

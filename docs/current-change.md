# 当前变更：移动端复述点草稿播放时间校验

## 当前用户要求

- 当前执行 mobile native workbench Task 2 review 修复：补齐 recall draft model 的非法播放时间校验。
- `createRecallDraft` 必须拒绝 `NaN` / `Infinity` 等非有限播放时间，避免生成 `t=NaN` 或 `t=Infinity` 锚点。
- 不修改 UI、路由、后端 API、数据库、部署或草稿持久化。

## 根因

- `createRecallDraft` 原先只对 `currentMs` 做 `Math.floor` 和 `Math.max(0, ...)`。
- `NaN` / `Infinity` 不是有效播放时间，但会被拼成非空 `position` 字符串。
- `getIncompleteDraftReason` 只检查锚点非空，因此非法锚点可能进入提交 payload。

## 本次实际修改文件

- `mobile/__tests__/workbench-drafts.test.ts`
  - 新增非法播放时间测试，覆盖 `Number.NaN` 和 `Number.POSITIVE_INFINITY` 必须在创建草稿前抛出“播放时间无效”。
- `mobile/src/workbench/recallDrafts.ts`
  - 在 `createRecallDraft` 中使用 `Number.isFinite(input.currentMs)` 显式拒绝非有限播放时间。
- `docs/current-change.md`
  - 更新为当前 Task 2 review 修复工作单。

## 行为语义是否变化

- 是。移动端创建复述点草稿时现在会拒绝非有限播放时间：
  - `NaN`、`Infinity` 等输入会抛出“播放时间无效”。
  - 有限播放时间仍按既有语义取整、下限截到 0，并生成 `t=<毫秒>` 锚点。
- 后端 API 语义未变化。
- 数据库结构未变化。
- 部署语义未变化。
- Web/Tauri 工作台语义未变化。
- UI 和路由未变化。

## 重构说明

- 无跨模块重构。
- 仅在现有 `createRecallDraft` 入口增加必要校验，保持草稿模型边界不变。

## 未修改内容

- 未修改 UI、路由、后端 API、数据库结构、部署配置、Web/Tauri 工作台代码。
- 未新增草稿持久化。
- 未修改测试去适配错误实现。
- 未新增 fallback、shim、legacy 或临时兼容逻辑。

## 影响范围

- API：无后端 API 变化；仅复用移动端已有 `SubmitLearningTaskItem` 类型。
- 架构：无跨层架构变化。
- 部署：无影响。
- 数据结构：无数据库或协议结构变化；未新增或修改公开协议类型。
- UI：无影响。
- 测试：补充移动端 workbench draft 非法播放时间单元测试。

## 当前风险点和不确定项

- 无已知风险点。

## 仍需用户确认的问题

- 无。

## 验证记录

- RED 已运行：`pnpm --dir mobile test -- workbench-drafts.test.ts`
  - 结果：失败，符合预期；新增测试 `rejects non-finite playback time before creating a draft` 失败，原因为当前实现未抛出“播放时间无效”。
- GREEN 已运行：`pnpm --dir mobile test -- workbench-drafts.test.ts`
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

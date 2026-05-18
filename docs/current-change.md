# 当前变更：移动端工作台测试覆盖修复

## 当前用户要求

- 修复 Task 4 代码质量 review 未通过的问题。
- 给 `MobileWorkbenchScreen` 补充草稿编辑、草稿删除和完整草稿提交主路径测试。
- 若当前实现已经满足新增测试，不强行修改生产代码。

## 根因

- `mobile/__tests__/mobile-workbench-screen.test.tsx` 已覆盖工作台展示、目录选择、复习门禁、播放时间回调、添加草稿和提交阻止路径。
- 测试缺少对草稿输入 `onUpdateDraft`、删除 `onRemoveDraft` 和可提交主路径 `onSubmitDrafts` 的直接断言。
- 现有 `MobileWorkbenchScreen` 实现已具备这些行为，本次问题是测试覆盖缺口，不是生产实现缺陷。

## 本次实际修改文件

- `mobile/__tests__/mobile-workbench-screen.test.tsx`
  - 新增草稿控件测试，验证题面和答案输入变更会以 `draft_1` 调用 `onUpdateDraft`，删除按钮会以 `draft_1` 调用 `onRemoveDraft`。
  - 新增完整草稿提交主路径测试，验证无复习门禁、复习队列未加载、非提交中时点击 `提交学习` 会调用 `onSubmitDrafts`。
- `docs/current-change.md`
  - 更新为当前 Task 4 review 修复工作单。

## 行为语义是否变化

- 无。仅补充测试覆盖。

## 重构说明

- 无。

## 未修改内容

- 未修改 `mobile/src/screens/MobileWorkbenchScreen.tsx`，因为新增测试在当前实现下自然通过。
- 未修改 API client、后端 API、数据库、部署、Web/Tauri 工作台或移动端路由。
- 未新增持久化、网络请求、fallback、shim、legacy、临时兼容逻辑或特殊分支。
- 未修改测试去适配错误实现。

## 影响范围

- API：无变化。
- 架构：无变化。
- 部署：无影响。
- 数据结构：无影响。
- UI：无变化。
- 测试：补充移动端工作台草稿更新、删除和提交主路径测试。

## 当前风险点和不确定项

- 新增测试自然通过，无法提供新增测试先失败的 RED 证据；按用户要求需回报 `DONE_WITH_CONCERNS`。

## 仍需用户确认的问题

- 无。

## 验证记录

- RED 尝试已运行：`pnpm --dir mobile test -- mobile-workbench-screen.test.tsx`
  - 结果：通过，1 个测试套件、7 个测试通过；新增测试在当前实现下自然通过，未形成 RED。
- GREEN 已运行：`pnpm --dir mobile test -- mobile-workbench-screen.test.tsx`
  - 结果：通过，1 个测试套件、7 个测试通过。
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

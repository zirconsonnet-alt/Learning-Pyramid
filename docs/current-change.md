# Current Change

更新时间：2026-05-14

## 1. 当前用户要求

- 删除工作台复述点录入面板截图红框中的两处提示文案：
  - 锚点位置下方的“网课锚点可编辑，提交时会保存为可跳转的视频时间点。”
  - 底部的“已准备好提交，共 1 个复述点，已完成 1 个。”

## 2. 本次实际修改文件

- `frontend/src/views/workbench/components/ComposePane.tsx`
- `frontend/tests/e2e/workbench-review.spec.ts`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `ComposePane.tsx`：移除红框对应的两段提示渲染；保留锚点输入、题目/答案输入、任务标题、提交按钮和原有提交判断。
- `workbench-review.spec.ts`：新增回归测试，确认录入复述点时不会再显示这两段冗余提示。
- `docs/current-change.md`：覆盖为本次任务工作单。

## 4. 行为语义是否变化

- UI 语义变化：两段辅助提示不再显示。
- 业务语义不变：复述点创建、锚点解析、问题/答案填写、提交可用性和提交接口调用不变。

## 5. 是否做了重构，以及为什么

- 没有做重构。
- 本次是定点删除 UI 文案，不需要调整组件结构或数据流。

## 6. 未修改哪些相关内容，以及为什么

- 未删除锚点输入框，因为用户只标红了说明文案，锚点仍是课程项目提交所需字段。
- 未删除“提交前还需要把每条复述点的锚点位置补完整。”等错误/阻断提示，因为截图未要求删除，且它们表达真实阻断状态。
- 未修改复述点提交逻辑，因为问题只在冗余显示文案。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，减少复述点录入面板中的冗余提示。
- 测试：是，新增 e2e 回归断言。

## 8. 当前风险点和不确定项

- 无。

## 9. 仍需用户确认的问题

- 无。

## 10. 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

## 11. 验证状态

- 已先运行新增 e2e，确认旧实现会因锚点提示仍存在而失败。
- `pnpm --dir frontend build`：通过；仍有既有 `hls` chunk 大于 500 kB 的 warning。
- `pnpm --dir frontend exec playwright test frontend/tests/e2e/workbench-review.spec.ts -g "workbench compose pane hides redundant helper copy"`：通过。
- `pnpm --dir frontend exec playwright test frontend/tests/e2e/workbench-review.spec.ts`：通过，7 个用例全部通过。
- `git diff --check`：通过；仅有既有 LF/CRLF 提示。

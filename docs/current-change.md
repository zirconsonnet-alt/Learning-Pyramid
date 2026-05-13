# Current Change

更新时间：2026-05-14

## 1. 当前用户要求

- 番茄钟设置页和番茄计划详情页的返回文案要和实际返回页面一致。

## 2. 本次实际修改文件

- `frontend/src/views/pomodoro/PomodoroPage.tsx`
- `frontend/tests/e2e/pomodoro-settings.spec.ts`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `PomodoroPage.tsx`：把番茄计划详情页的返回按钮文案从“返回番茄计划”改成“返回番茄钟”，与实际跳转目标一致。
- `pomodoro-settings.spec.ts`：补充 e2e 断言，确认番茄计划详情页和番茄钟设置页的返回按钮都显示“返回番茄钟”。
- `docs/current-change.md`：覆盖为本次任务工作单。

## 4. 行为语义是否变化

- UI 文案变化：番茄计划详情页的返回按钮文案改为“返回番茄钟”。
- 路由语义不变：两个页面仍然都返回 `/pomodoro`。
- 功能语义不变：只改文案，不改导航和业务行为。

## 5. 是否做了重构，以及为什么

- 没有做重构。
- 这是一个纯文案对齐修正，不需要调整结构。

## 6. 未修改哪些相关内容，以及为什么

- 未修改番茄钟设置页，因为它的返回文案本来就和实际跳转一致。
- 未修改番茄钟主页面和计划详情页内部业务内容，因为问题只在返回按钮文案。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，计划详情页返回按钮文案更准确。
- 测试：是，新增返回按钮文案回归断言。

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

- `pnpm --dir frontend exec playwright test frontend/tests/e2e/pomodoro-settings.spec.ts -g "pomodoro settings shares"`：通过。
- `pnpm --dir frontend build`：通过；仍有既有 `hls` chunk 大于 500 kB 的 warning。

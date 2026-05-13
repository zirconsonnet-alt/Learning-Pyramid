# Current Change

更新时间：2026-05-14

## 1. 当前用户要求

- 修复选择工作台时被番茄钟拦截后，当前项目没有切到刚选择项目的问题。
- 被番茄钟拦到番茄钟页面可以接受，但不能吞掉用户选择当前项目的意图。

## 2. 本次实际修改文件

- `frontend/src/shell/AppShell.tsx`
- `frontend/src/views/workbench/WorkbenchPage.tsx`
- `frontend/tests/e2e/pomodoro-settings.spec.ts`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `AppShell.tsx`：把项目路由参数同步为完整 `selectedWorkbenchProjectRef`，让当前项目选择发生在页面门禁之前。
- `WorkbenchPage.tsx`：移除页面内重复写当前项目的逻辑，避免路由层和页面层同时承担同一状态同步职责。
- `pomodoro-settings.spec.ts`：补充番茄门禁场景下的 e2e 断言，确认被重定向到番茄钟后当前项目仍切到用户访问的项目。
- `docs/current-change.md`：覆盖为本次任务工作单。

## 4. 行为语义是否变化

- 是。
- 以前访问项目工作台被番茄钟门禁拦截时，只可能同步旧的 `selectedWorkbenchProjectId`，`selectedWorkbenchProjectRef` 仍可能停留在旧项目。
- 现在只要路由进入具体学科项目范围，当前项目引用会先同步到该路由对应项目，再由番茄门禁决定是否允许进入工作台内容。

## 5. 是否做了重构，以及为什么

- 做了当前范围内的局部边界调整。
- 目的是让“选择当前项目”归属于路由层状态同步，而不是依赖 `WorkbenchPage` 是否成功渲染；同时移除工作台页面内的重复写入路径。

## 6. 未修改哪些相关内容，以及为什么

- 未修改 `PomodoroWorkbenchGate` 的访问控制语义，因为拦截到番茄钟页本身是允许的。
- 未修改 API、数据结构或番茄计划逻辑，因为问题是前端路由状态同步边界。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：间接影响，当前项目菜单会在被番茄钟拦截后仍反映用户刚选择的项目。
- 测试：是，补充 e2e 断言。

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

- 已先运行新增 e2e 断言，旧实现会保持旧 `selectedWorkbenchProjectRef` 而失败。
- `pnpm --dir frontend build`：通过；仍有既有 `hls` chunk 大于 500 kB 的 warning。
- `pnpm --dir frontend exec playwright test frontend/tests/e2e/pomodoro-settings.spec.ts -g "blocks workbench when enabled"`：通过。
- `pnpm --dir frontend exec playwright test frontend/tests/e2e/pomodoro-settings.spec.ts`：通过，14 个用例全部通过。
- `pnpm --dir frontend exec playwright test frontend/tests/e2e/navigation.spec.ts frontend/tests/e2e/subject-project.spec.ts`：通过，7 个用例全部通过。

# Current Change

更新时间：2026-05-14

## 1. 当前用户要求

- 新建小番茄时，如果预计 25 分钟学习时间会和已有番茄计划冲突，应禁止新建。
- 使用已确认规则：小番茄预计区间与今天已启用番茄计划任一区间重叠即判定冲突。

## 2. 本次实际修改文件

- `frontend/src/ui/store/pomodoroStore.ts`
- `frontend/src/views/pomodoro/PomodoroPage.tsx`
- `frontend/tests/e2e/pomodoro-settings.spec.ts`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `pomodoroStore.ts`：补充小番茄与当日启用计划的时间重叠判断，供页面入口复用。
- `PomodoroPage.tsx`：在打开新建小番茄弹窗和最终创建前拦截冲突，避免创建会覆盖排程语义的小番茄。
- `pomodoro-settings.spec.ts`：增加 e2e 用例，覆盖小番茄预计区间与已有计划重叠时必须阻止创建。
- `docs/current-change.md`：覆盖为本次任务工作单。

## 4. 行为语义是否变化

- 是。
- 以前只禁止当前处于学习阶段时新建小番茄。
- 现在小番茄预计学习区间只要与今天已启用计划重叠，就禁止新建并提示冲突。

## 5. 是否做了重构，以及为什么

- 仅做当前范围内的局部整理。
- 目的是把时间区间判断放在番茄 store 的纯函数中，避免页面层复制排程计算逻辑。

## 6. 未修改哪些相关内容，以及为什么

- 未修改番茄计划数据结构，因为冲突判断可由现有 schedule 推导。
- 未修改后端 API，因为该行为目前发生在前端本地番茄状态。
- 未做自动顺延、覆盖或二次确认，因为这些会引入未确认的优先级语义。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，新增冲突提示。
- 测试：是，新增 e2e 覆盖。

## 8. 当前风险点和不确定项

- 冲突范围限定为今天的启用计划，不跨天检查。

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

- 已先运行新增 e2e，旧实现因缺少“小番茄时间冲突”提示而失败。
- 已补充“排程关闭时保存计划不阻止小番茄”的 e2e，确认初版实现会误拦后修正。
- `pnpm --dir frontend build`：通过；仍有既有 `hls` chunk 大于 500 kB 的 warning。
- `pnpm --dir frontend exec playwright test frontend/tests/e2e/pomodoro-settings.spec.ts -g "overlaps an enabled plan"`：实现后通过。
- `pnpm --dir frontend exec playwright test frontend/tests/e2e/pomodoro-settings.spec.ts -g "overlaps an enabled plan|ignores saved plans"`：通过，2 个用例全部通过。
- `pnpm --dir frontend exec playwright test frontend/tests/e2e/pomodoro-settings.spec.ts`：通过，14 个用例全部通过。
- `git diff --check -- frontend/src/ui/store/pomodoroStore.ts frontend/src/views/pomodoro/PomodoroPage.tsx frontend/tests/e2e/pomodoro-settings.spec.ts docs/current-change.md`：通过；仅有 Windows 换行提示。

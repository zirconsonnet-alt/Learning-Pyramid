# Current Change

更新时间：2026-05-14

## 1. 当前用户要求

- 删除推荐复习页顶部外层标题区。
- 删除推荐复习页顶部“返回工作台”按钮。
- 把“更新推荐阈值”按钮移动到复习任务卡片右上角，放在“已完成”信息右侧。

## 2. 本次实际修改文件

- `frontend/src/views/recommendations/ReviewRecommendationsPage.tsx`
- `frontend/tests/e2e/subject-project.spec.ts`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `ReviewRecommendationsPage.tsx`：调整推荐复习页信息层级，删除外层标题与返回按钮，把阈值操作并入复习任务卡片头部。
- `subject-project.spec.ts`：补充推荐复习页 UI 断言，避免按钮再次漂到卡片外。
- `docs/current-change.md`：覆盖为本次任务工作单。

## 4. 行为语义是否变化

- 是。
- 页面不再提供推荐复习页内的“返回工作台”按钮。
- “更新推荐阈值”仍打开同一个阈值弹窗，只是位置从页面外层操作区移动到复习任务卡片头部。

## 5. 是否做了重构，以及为什么

- 否。
- 本次是局部 UI 结构调整，不改变数据流或组件边界。

## 6. 未修改哪些相关内容，以及为什么

- 未修改推荐阈值弹窗逻辑，因为用户只要求移动入口按钮。
- 未修改推荐复习计算和复习作答流程，因为本次问题是页面布局层级。
- 未新增替代返回入口，因为用户明确要求删除红框里的返回工作台按钮。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，推荐复习页顶部区域和卡片头部按钮位置变化。
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

- 已先运行新增 e2e，旧实现因页面外仍有“推荐复习”标题而失败。
- `pnpm --dir frontend build`：通过；仍有既有 `hls` chunk 大于 500 kB 的 warning。
- `pnpm --dir frontend exec playwright test frontend/tests/e2e/subject-project.spec.ts -g "recommended review actions"`：通过。
- `pnpm --dir frontend exec playwright test frontend/tests/e2e/subject-project.spec.ts`：通过，6 个用例全部通过。
- `pnpm --dir frontend exec playwright test frontend/tests/e2e/navigation.spec.ts`：通过，2 个用例全部通过。

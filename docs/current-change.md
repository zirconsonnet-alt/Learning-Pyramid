# Current Change

更新时间：2026-05-14

## 1. 当前用户要求

- 工作台右侧“工作状态”区域看起来太乱。
- 删除“推进判断”四个字。
- 只保留三个同级小标题：
  - 预计剩余学习时长
  - 观看覆盖
  - 今日回看
- “预计剩余学习时长”和“观看覆盖”的标题样式要和“今日回看”一致。

## 2. 本次实际修改文件

- `frontend/src/views/workbench/WorkbenchPage.tsx`
- `frontend/tests/e2e/workbench-review.spec.ts`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `WorkbenchPage.tsx`：移除右侧侧栏中的“推进判断”分组标题；把“预计剩余学习时长”“观看覆盖”“今日回看”改为同级 section，并统一使用 `SidebarSectionTitle`。
- `workbench-review.spec.ts`：补充 e2e 断言，确认“推进判断”不再显示，三个同级标题仍可见。
- `docs/current-change.md`：覆盖为本次任务工作单。

## 4. 行为语义是否变化

- UI 语义变化：右侧工作状态区从“推进判断”分组改为三个同级统计项。
- 业务语义不变：预计时长、观看覆盖和今日回看数据来源、计算逻辑、刷新逻辑均不变。

## 5. 是否做了重构，以及为什么

- 做了当前范围内的极小 JSX 结构整理。
- 目的是消除多余父级分组，让三个用户可见标题同级，不改变数据流或组件边界。

## 6. 未修改哪些相关内容，以及为什么

- 未修改 `TodayReviewStatsChart` 饼图结构，因为用户只要求标题层级和“推进判断”文案。
- 未修改学习时长估算和观看覆盖计算，因为问题只在右侧侧栏呈现层级。
- 未修改工作状态卡片标题和当前状态文案，因为它们不属于本次指定的三个统计项。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，调整工作状态侧栏的标题层级和样式一致性。
- 测试：是，新增/更新 e2e 断言。

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

- 已先运行工作台 e2e，确认旧实现会因“推进判断”仍存在而失败。
- `pnpm --dir frontend build`：通过；仍有既有 `hls` chunk 大于 500 kB 的 warning。
- `pnpm --dir frontend exec playwright test frontend/tests/e2e/workbench-review.spec.ts -g "workbench$"`：通过。
- `pnpm --dir frontend exec playwright test frontend/tests/e2e/workbench-review.spec.ts`：通过，7 个用例全部通过。

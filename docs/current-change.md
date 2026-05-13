# Current Change

更新时间：2026-05-13

## 1. 当前用户要求

- 项目卡片也保留和学科卡片同样的当前标签。

## 2. 本次实际修改文件

- `frontend/src/views/subjects/SubjectDashboardPage.tsx`
- `frontend/tests/e2e/subject-project.spec.ts`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `SubjectDashboardPage.tsx`：在 active 项目卡片右侧显示 `当前项目` 标签，位置和样式与学科卡片的 `当前学科` 保持一致。
- `subject-project.spec.ts`：在既有卡片一致性回归里补充 `当前项目` 标签断言。
- `docs/current-change.md`：覆盖为当前标签一致性修复的工作单。

## 4. 行为语义是否变化

- 否。
- 只增加 active 项目卡片的视觉标签，按钮、跳转、删除和数据流都不变。

## 5. 是否做了重构，以及为什么

- 否。
- 这次只做项目卡片头部的局部布局对齐，不抽公共卡片组件，不扩大作用域。

## 6. 未修改哪些相关内容，以及为什么

- 未改学科卡片，因为它已经有 `当前学科` 标签。
- 未改选中状态计算、删除弹窗、创建弹窗、排序和路由逻辑，因为需求只针对当前标签展示。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，active 项目卡片会显示 `当前项目` 标签。
- 测试：是，补充 e2e 回归断言。

## 8. 当前风险点和不确定项

- 仅是视觉标签增加，风险主要在窄屏换行；项目卡片头部已按学科卡片改为可换行结构。

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

- 已先跑红灯：`LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=5177 pnpm --dir frontend test:e2e -- subject-project.spec.ts -g "subject and project cards share title meta and selected styles"`，当前因为项目卡片缺少 `当前项目` 标签而失败。
- 修复后同一用例绿灯：`LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=5177 pnpm --dir frontend test:e2e -- subject-project.spec.ts -g "subject and project cards share title meta and selected styles"`，1 passed。
- `pnpm --dir frontend build`：通过；仍有既有 `hls` chunk 大于 500 kB 的 warning。
- `pnpm --dir frontend test:e2e -- subject-project.spec.ts`：5 passed。
- 已用已构建前端的临时 preview 和 mock 数据做渲染截图验证，截图位于 `%TEMP%\learningpyramid-current-project-label.png`。

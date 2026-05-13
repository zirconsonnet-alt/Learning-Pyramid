# Current Change

更新时间：2026-05-13

## 1. 当前用户要求

- 统一学科卡片和项目卡片的标题字号、meta 样式和选中态。

## 2. 本次实际修改文件

- `frontend/src/views/projects/ProjectsPage.tsx`
- `frontend/src/views/subjects/SubjectDashboardPage.tsx`
- `frontend/tests/e2e/subject-project.spec.ts`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `ProjectsPage.tsx`：把学科卡片标题字号和项目数 meta 对齐，并补稳定测试钩子。
- `SubjectDashboardPage.tsx`：把项目卡片的选中态对齐到学科卡片，并补稳定测试钩子。
- `subject-project.spec.ts`：新增回归断言，防止标题字号、meta 和选中态再次分叉。
- `docs/current-change.md`：覆盖为当前 UI 一致性修复的工作单。

## 4. 行为语义是否变化

- 否。
- 只统一卡片视觉样式和测试钩子，按钮、跳转、删除和数据流都不变。

## 5. 是否做了重构，以及为什么

- 否。
- 这次只做局部样式对齐，不抽公共卡片组件，不扩大作用域。

## 6. 未修改哪些相关内容，以及为什么

- 未改删除弹窗、创建弹窗、排序和路由逻辑，因为需求只针对卡片头部和选中态。
- 未给项目卡片新增“当前项目”文案，因为用户没有要求，只统一视觉状态。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，两个卡片现在在标题字号、meta 语义和 active 态上保持一致。
- 测试：是，新增 e2e 回归断言。

## 8. 当前风险点和不确定项

- 仅是视觉类名对齐，风险主要在样式回归；已用 e2e 兜住。

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

- 已先跑红灯：`pnpm --dir frontend test:e2e -- subject-project.spec.ts -g "subject and project cards share title meta and selected styles"`，当前因为学科卡片标题字号仍是 `text-xl` 而失败。
- 已跑绿灯：`LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=5177 pnpm --dir frontend test:e2e -- subject-project.spec.ts -g "subject and project cards share title meta and selected styles"`，1 passed。
- `pnpm --dir frontend build`：通过；仍有既有 `hls` chunk 大于 500 kB 的 warning。
- `pnpm --dir frontend test:e2e -- subject-project.spec.ts`：5 passed。

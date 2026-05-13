# Current Change

更新时间：2026-05-13

## 1. 当前用户要求

- 学科卡片前面也要像项目卡片一样有图标。

## 2. 本次实际修改文件

- `frontend/src/views/projects/ProjectsPage.tsx`
- `frontend/tests/e2e/subject-project.spec.ts`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `ProjectsPage.tsx`：给学科卡片头部补上语义图标，并加稳定测试钩子。
- `subject-project.spec.ts`：新增回归断言，防止学科卡片头部图标再次缺失。
- `docs/current-change.md`：覆盖为当前 UI 一致性修复的工作单。

## 4. 行为语义是否变化

- 否。
- 只是在学科卡片标题前补充了视觉图标，按钮、跳转、删除和数据流都不变。

## 5. 是否做了重构，以及为什么

- 否。
- 不抽公共卡片，不改项目卡片，不扩大到全局样式层。

## 6. 未修改哪些相关内容，以及为什么

- 未改项目卡片，因为项目卡片本来就有图标。
- 未改删除弹窗、创建弹窗和其他页面，因为需求只针对学科卡片头部。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，学科卡片现在与项目卡片在卡头层级上更一致。
- 测试：是，新增 e2e 回归断言。

## 8. 当前风险点和不确定项

- 图标语义选择为 `BookOpen`，与现有“学科”示例保持一致。

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

- 已先跑红灯：`pnpm --dir frontend test:e2e -- subject-project.spec.ts -g "subject cards show a leading icon like project cards"`，当前因为学科卡片缺少图标而失败。
- 修复后运行源码 dev server 版 e2e：`LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=5177 pnpm --dir frontend test:e2e -- subject-project.spec.ts -g "subject cards show a leading icon like project cards"`，1 passed。
- `pnpm --dir frontend build`：通过；仍有既有大 chunk warning。
- `pnpm --dir frontend test:e2e -- subject-project.spec.ts`：4 passed。

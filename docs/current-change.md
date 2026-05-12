# Current Change

更新时间：2026-05-12

## 1. 当前用户要求

- 删除复习链模板中“这个步骤没有额外参数”提示。
- 将收敛步骤说明改为“推送上次复习时不记得的重点”。
- 工作台视频空状态只保留一行“请先在左侧选择一个视频实例。”，不再显示“当前视频还未进入可播放状态”。

## 2. 本次实际修改文件

- `frontend/src/views/settings/ProjectSettingsPage.tsx`
- `frontend/src/views/workbench/components/VideoPane.tsx`
- `frontend/tests/e2e/subject-project.spec.ts`
- `frontend/tests/e2e/workbench-review.spec.ts`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `frontend/src/views/settings/ProjectSettingsPage.tsx`：复习链模板的收敛步骤不需要展示空参数说明，删除该提示；同时按当前产品文案替换收敛步骤说明。
- `frontend/src/views/workbench/components/VideoPane.tsx`：未选择视频实例时，空状态标题和说明重复占位；改为只展示操作提示这一行。
- `frontend/tests/e2e/subject-project.spec.ts`：补充项目设置页复习链模板文案回归断言。
- `frontend/tests/e2e/workbench-review.spec.ts`：补充工作台视频空状态单行提示回归断言。
- `docs/current-change.md`：覆盖记录当前这次 UI 文案清理。

## 4. 行为语义是否变化

不改变复习链模板的数据结构、保存逻辑、收敛步骤语义、视频实例选择逻辑或播放状态判断；只改变项目设置页和工作台视频空状态的可见文案。

## 5. 是否做了重构，以及为什么

未做重构。当前需求只需要修改两个页面组件的展示分支。

## 6. 未修改哪些相关内容，以及为什么

- 不修改模板 item 的 `kind` 和 `count` 数据结构：本次只改 UI 文案。
- 不修改后端复习链生成逻辑：用户要求的是设置页展示。
- 不修改素材导入、实例选择和播放资源准备逻辑：用户要求的是未选择实例时的空状态文案。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：无影响。
- 架构：无影响。
- 部署：无配置影响；如需线上生效，需要重新构建并同步。
- 数据结构：无影响。
- UI：项目设置页复习链模板和工作台视频空状态文案变化。
- 测试：新增两条 e2e 文案断言。

## 8. 当前风险点和不确定项

- 无已知不确定项。

## 9. 仍需用户确认的问题

无。

## 10. 验证结果

- 已先运行项目设置页新增 e2e 断言，旧实现下失败，失败原因是找不到“推送上次复习时不记得的重点”。
- 已先运行工作台视频空状态新增 e2e 断言，旧实现下失败，失败原因是“当前视频还未进入可播放状态”仍存在。
- `pnpm --dir frontend exec eslint src/views/settings/ProjectSettingsPage.tsx src/views/workbench/components/VideoPane.tsx tests/e2e/subject-project.spec.ts tests/e2e/workbench-review.spec.ts`：无错误；`VideoPane.tsx` 有 3 个既有 React Hooks 依赖警告，未在本次文案改动中扩大处理。
- `pnpm --dir frontend build`：通过，主入口产物为 `assets/index-CrHoLcpj.js`；Vite 仍有既有大 chunk warning。
- `$env:LEARNINGPYRAMID_FRONTEND_E2E_PORT='4176'; pnpm --dir frontend exec playwright test tests/e2e/subject-project.spec.ts tests/e2e/workbench-review.spec.ts -g "project settings shows concise convergence template copy|workbench video pane keeps the empty selection prompt to one line"`：通过 2 条。

## 11. 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

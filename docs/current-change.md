# Current Change

更新时间：2026-05-15

## 1. 当前用户要求

- 创建学科导引在项目设置页同步完目录后，不应停在当前页。
- 同步完成后应跳转到工作台，并展示导入后的学习对象效果。

## 2. 本次实际修改文件

- `frontend/tests/e2e/subject-project.spec.ts`
- `frontend/tests/fixtures/mock-api.ts`
- `frontend/src/ui/guideWalkthrough/guideWalkthroughController.ts`
- `frontend/src/ui/guideWalkthrough/guideWalkthroughSteps.ts`
- `frontend/src/views/settings/ProjectSettingsPage.tsx`
- `frontend/src/views/projects/ProjectsPage.tsx`
- `frontend/src/views/subjects/SubjectDashboardPage.tsx`
- `docs/how-to-create-subject-project.md`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `frontend/tests/e2e/subject-project.spec.ts`：新增回归用例，覆盖创建学科导引从“同步目录内容”进入工作台并看到导入学习对象。
- `frontend/tests/fixtures/mock-api.ts`：让 e2e mock 的目录导入接口返回结构化结果，并在导入后把内容状态切到可展示。
- `frontend/src/ui/guideWalkthrough/guideWalkthroughController.ts`：补齐 `:scopedProjectId` route hint 解析，让学科材料项目导引步骤能从当前 scoped project 路由继续导航；支持步骤级弹窗正文覆盖，避免把长期文档说明直接当作短弹窗文案；导引结束步只显示“完成”，不再暴露没有业务撤销语义的“上一步”。
- `frontend/src/ui/guideWalkthrough/guideWalkthroughSteps.ts`：把“同步目录内容”改为等待同步完成事件推进，并新增“查看导入结果”工作台步骤；第 6 步正文改为“左侧是刚导入的内容目录。”。
- `frontend/src/views/settings/ProjectSettingsPage.tsx`：目录同步成功或已是最新后通知创建学科导引推进；失败时不推进。
- `frontend/src/views/projects/ProjectsPage.tsx`：为创建学科弹窗补充 `DialogDescription`，消除该导引路径暴露的可访问性 warning。
- `frontend/src/views/subjects/SubjectDashboardPage.tsx`：为创建项目弹窗补充 `DialogDescription`，保持创建类弹窗结构一致。
- `docs/how-to-create-subject-project.md`：同步创建学科导引完成后的工作台展示语义。
- `docs/current-change.md`：覆盖为当前任务工作单。

## 4. 行为语义是否变化

- 是。创建学科导引在目录同步成功后会继续进入当前项目工作台，并高亮内容目录，让用户看到导入结果。
- 是。第 6 步弹窗正文改为更短的结果说明：“左侧是刚导入的内容目录。”。
- 是。导引结束步只保留“完成”按钮，不提供“上一步”。
- 普通手动同步目录流程不应被强制跳转。

## 5. 是否做了重构，以及为什么

- 否。仅调整既有导引步骤配置、route hint 解析和同步成功后的既有导引事件调用。

## 6. 未修改哪些相关内容，以及为什么

- 未修改后端 API、持久化和数据结构，因为根因位于前端导引步骤定义与同步成功推进方式。
- 未给普通同步按钮直接加导航，因为跳转语义只属于创建学科导引。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，创建学科导引会多走一步工作台展示。
- UI：是，创建学科/项目弹窗增加屏幕阅读器描述，不新增可见操作。
- 测试：是，新增 e2e 回归，并断言第 6 步弹窗正文和结束步按钮。

## 8. 当前风险点和不确定项

- 无已知未解决风险。

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

- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4241; pnpm exec playwright test tests/e2e/subject-project.spec.ts -g "create subject guide enters workbench" --reporter=line`：失败，确认修复前同步目录后仍停在项目设置页。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4252; pnpm exec playwright test tests/e2e/subject-project.spec.ts -g "create subject guide enters workbench" --reporter=line`：1 passed。
- `pnpm exec tsc -b --noEmit`：通过。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4253; pnpm exec playwright test tests/e2e/subject-project.spec.ts --workers=1 --reporter=line`：7 passed。
- `pnpm build`：通过，保留既有 Vite chunk size warning。
- `git diff --check`：通过，仅有 LF/CRLF 提示。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4254; pnpm exec playwright test tests/e2e/subject-project.spec.ts -g "create subject guide enters workbench" --reporter=line`：失败，确认第 6 步旧正文不满足新文案要求。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4255; pnpm exec playwright test tests/e2e/subject-project.spec.ts -g "create subject guide enters workbench" --reporter=line`：1 passed。
- `pnpm exec tsc -b --noEmit`：通过。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4256; pnpm exec playwright test tests/e2e/subject-project.spec.ts -g "create subject guide enters workbench" --reporter=line`：失败，确认第 6 步旧按钮组仍显示“上一步”。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4257; pnpm exec playwright test tests/e2e/subject-project.spec.ts -g "create subject guide enters workbench" --reporter=line`：1 passed。
- `pnpm exec tsc -b --noEmit`：通过。
- `git diff --check`：通过，仅有 LF/CRLF 提示。
- `pnpm build`：通过，刷新 `frontend/dist`，确认静态服务不再使用旧前端 bundle。

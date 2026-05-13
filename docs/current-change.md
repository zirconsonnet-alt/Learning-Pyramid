# Current Change

更新时间：2026-05-13

## 1. 当前用户要求

- 删除学科弹窗减少文字轰炸。
- 删除截图中标出的输入框上方说明和下方说明。
- 把“请输入标题完成确认”的提示移到输入框 placeholder。
- 项目删除弹窗也做同样处理。
- 两个删除弹窗顶部说明只保留第一段，不再展示后半段解释。

## 2. 本次实际修改文件

- `frontend/src/views/projects/ProjectsPage.tsx`
- `frontend/src/views/subjects/SubjectDashboardPage.tsx`
- `frontend/tests/e2e/subject-project.spec.ts`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `ProjectsPage.tsx`：删除学科删除弹窗中输入框上方 label、下方辅助说明和冗长删除建议；输入框 placeholder 改为确认文案。
- `SubjectDashboardPage.tsx`：删除项目删除弹窗中输入框上方 label、下方辅助说明和冗长删除建议；输入框 placeholder 改为确认文案。
- `subject-project.spec.ts`：增加回归断言，防止删除确认弹窗重新出现重复可见说明或冗长顶部说明。
- `docs/current-change.md`：覆盖为当前 UI 精简任务的工作单。

## 4. 行为语义是否变化

- 否。
- 删除仍要求输入完整学科标题或项目名称后才能确认。
- 只改变删除确认弹窗的文案呈现位置和可见密度。

## 5. 是否做了重构，以及为什么

- 否。
- 两个弹窗当前分别位于各自页面中，本轮只做局部 UI 文案收敛，不抽公共组件。

## 6. 未修改哪些相关内容，以及为什么

- 未修改删除 API、mutation、缓存清理、按钮禁用规则和删除成功/失败反馈，避免扩大行为范围。
- 未改创建弹窗和其他非删除弹窗，因为用户只要求删除确认弹窗。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，删除确认弹窗更短。
- 测试：是，新增前端 e2e 回归断言。

## 8. 当前风险点和不确定项

- 无关键不确定项。

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

- 已运行红灯：`pnpm --dir frontend test:e2e -- subject-project.spec.ts -g "delete confirmation dialogs keep confirmation copy inside the input"`，失败点为删除学科弹窗仍显示上方说明。
- 本轮追加红灯：`pnpm --dir frontend test:e2e -- subject-project.spec.ts -g "delete confirmation dialogs keep confirmation copy inside the input"`，失败点为删除学科弹窗找不到精确短句 `这会移除“自动化测试学科”的当前学科入口。`，说明当前顶部说明仍是长句。
- 修复后运行当前源码 dev server：`LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=5177 pnpm --dir frontend test:e2e -- subject-project.spec.ts -g "delete confirmation dialogs keep confirmation copy inside the input"`，1 passed。
- `pnpm --dir frontend build`：通过；仍有既有大 chunk warning。
- 构建后运行默认 preview：`pnpm --dir frontend test:e2e -- subject-project.spec.ts -g "delete confirmation dialogs keep confirmation copy inside the input"`，1 passed。

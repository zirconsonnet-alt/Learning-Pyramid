# Current Change

更新时间：2026-05-14

## 1. 当前用户要求

- 修复“当前学科 / 当前项目”上下文只跟随 URL 的问题。
- 正确语义：
  - 只有用户明确切换学科或项目时，右上角当前上下文才变化。
  - 点击项目“进入工作台”即使被番茄钟拦截到 `/pomodoro`，右上角仍保留刚选中的学科和项目。
  - 从项目页跳到全局页（如用户指南、个人中心）后，右上角仍保留当前学科和项目。
- 头像下拉菜单里的 `个人中心 / 好友中心 / 会员中心` 统一复用“英文眉题 + 中文标题”的页面标题设计。
- 其他页面不跟进，不把这套设计推广成全站规则。

## 2. 本次实际修改文件

- `frontend/src/shell/AppShell.tsx`
- `frontend/tests/e2e/navigation.spec.ts`
- `frontend/src/views/shared/AccountMenuPageTitle.tsx`
- `frontend/src/views/profile/ProfilePage.tsx`
- `frontend/src/views/friends/FriendsPage.tsx`
- `frontend/src/views/membership/MembershipPage.tsx`
- `frontend/tests/e2e/app-load.spec.ts`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `frontend/src/shell/AppShell.tsx`：把头部上下文从“只看当前路由”调整为“优先路由，缺失时回退到用户当前选择”，并约束项目上下文不能跨学科串用。
- `frontend/tests/e2e/navigation.spec.ts`：把全局页保留当前学科/项目上下文写成验收用例，并覆盖从项目页跳到用户指南的场景。
- `frontend/src/views/shared/AccountMenuPageTitle.tsx`：抽出仅供头像菜单三页复用的小标题组件，避免三处各写一套。
- `frontend/src/views/profile/ProfilePage.tsx`：让“账户信息”标题改为复用共享组件，保留现有语法。
- `frontend/src/views/friends/FriendsPage.tsx`：把“好友中心”接入同一套标题语法。
- `frontend/src/views/membership/MembershipPage.tsx`：把“会员中心”接入同一套标题语法，并保留页面主标题的 heading 语义。
- `frontend/tests/e2e/app-load.spec.ts`：补充头像菜单三个入口页标题一致性的前端验收。
- `docs/current-change.md`：记录这次整批提交的实际范围。

## 4. 行为语义是否变化

- 是。`/pomodoro`、`/guide` 等全局页现在会保留右上角当前学科/项目上下文，而不是因为 URL 不带参数就丢失展示。
- 否。番茄钟门禁仍然拦截非学习时段进入工作台；这次不改变门禁语义。
- 否。不改变学科、项目的真实切换入口，仍以用户明确选择或显式项目路由为准。
- 是。好友中心和会员中心现在也会显示英文眉题 + 中文标题，和个人中心入口组保持一致。
- 否。不改变三个头像菜单页面的功能、数据流、交互入口。

## 5. 是否做了重构，以及为什么

- 做了当前范围内的局部整理。
- `AppShell` 内部把“页面位置”和“当前选择”拆开，原因是头部 UI 之前把两者耦合在一起，导致全局页丢失项目上下文。
- 抽了一个头像菜单三页共享的小标题组件，原因是三页属于同一入口组，继续复制样式会留下分叉。

## 6. 未修改哪些相关内容，以及为什么

- 不修改 `PomodoroWorkbenchGate` 拦截逻辑，因为用户已确认“拦到番茄钟页”本身是合理的。
- 不修改 `SubjectDashboardPage` 的项目按钮行为，因为当前选择写入动作本来就已经存在。
- 不新增新的全局上下文 store 字段，因为现有 `selectedSubjectId` / `selectedWorkbenchProjectRef` 足以承载正确语义。
- 不修改学科中心、用户指南、全局设置等其他页面标题，因为用户只要求头像菜单三个入口页复用这套设计。
- 不改个人中心右侧“学习视图”的现有标题语法，因为这次只针对头像菜单入口页的大标题区域。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，右上角头部在全局页会继续显示当前学科/项目；好友中心和会员中心标题样式与个人中心入口组统一。
- 测试：是，新增并更新 e2e 覆盖全局页上下文和头像菜单三页标题语法。

## 8. 当前风险点和不确定项

- 头部现在会在全局页展示上次明确选择的学科/项目；这是刻意语义变化，不再把“全局页无项目路由”解释成“当前项目为空”。

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

- `pnpm exec tsc -b --noEmit`（在 `frontend/` 下运行）：通过。
- `pnpm build`（在 `frontend/` 下运行）：通过。
- `pnpm exec playwright test tests/e2e/navigation.spec.ts --reporter=line`（preview 形态，端口 `4201`）：3 passed。
- `pnpm exec playwright test tests/e2e/app-load.spec.ts -g "account menu entry pages share the eyebrow title pattern" --reporter=line`（preview 形态，端口 `4202`）：1 passed。
- `pnpm exec playwright test tests/e2e/pomodoro-settings.spec.ts -g "blocks workbench when enabled" --reporter=line`（preview 形态，端口 `4203`）：1 passed。
- `git diff --check`：通过，仅有 LF/CRLF 提示。

# 当前变更：手机端工作台播放器下方紧凑状态与折叠目录

## 当前用户要求

- 手机端工作台不要沿用桌面三列顺序导致目录先占第一屏。
- 手机端播放器/书本定位区后先显示紧凑工作状态，再显示默认折叠的内容目录，随后是复述点录入与层推进区域。
- 桌面端三列布局保持不变。
- 目录仍属于工作台页面层，不放进全局顶栏，也不塞进 `VideoPane`。
- 不动后端、API、数据结构，不用横向隐藏掩盖溢出。

## 根因

- 工作台原布局主要服务桌面三列，在手机端按 DOM 顺序堆叠时，内容目录和完整工作状态区域会占据播放器后的大量空间。
- 内容目录是树形结构，深层缩进与 grid 子项最小宽度若不受约束，会在手机端撑出视口。

## 本次实际修改文件

- `frontend/src/views/workbench/WorkbenchPage.tsx`
  - 手机端重排工作台内容顺序为：播放器/书本定位、紧凑工作状态、默认折叠目录、主工作区。
  - 手机端工作状态只展示一行摘要，详情默认折叠，点击后展开。
  - 手机端内容目录默认折叠，点击后展开；选择目录节点后自动收起。
  - 桌面端继续保持目录 / 主工作区 / 工作状态三列，并保留桌面目录与状态详情常驻显示。
  - 为工作台关键区域补充稳定 DOM id，用于 e2e 验证布局顺序和折叠状态。
- `frontend/src/views/workbench/components/LearningObjectTree.tsx`
  - 为目录树缩进增加上限，只保留有限层级的视觉缩进。
  - 移除递归子容器额外左缩进，保留左侧层级线。
  - 为树节点和标题文本增加 `min-w-0`，长标题截断而不是撑宽页面。
- `frontend/tests/fixtures/mock-api.ts`
  - 允许 e2e 按需注入学习对象树节点，用于构造深层目录测试数据。
- `frontend/tests/e2e/app-load.spec.ts`
  - 新增手机端工作台顺序、默认折叠、展开、选择后收起、无横向溢出的 e2e。
  - 调整深层目录测试：先确认手机端目录默认折叠，再展开目录验证深层节点不会越界。
- `docs/current-change.md`
  - 覆盖为当前变更工作单。

## 行为语义变化

- 手机端工作台首屏优先展示播放器/书本定位区。
- 手机端工作状态详情和内容目录默认折叠，需要用户点击展开。
- 手机端选择内容目录节点后，目录会自动收起，让用户回到播放器和主工作流。
- 桌面端工作台布局和内容常驻语义不变。
- 目录选择、实例切换、复述点录入、复习、层推进、AI 助手、后端数据语义不变。

## 重构说明

- 做了当前需求范围内的局部结构整理：把工作台页面中的目录、播放器、状态、主工作区分成响应式顺序明确的兄弟区域。
- 没有跨模块重构，没有改变 `VideoPane` 职责，没有修改公共接口。

## 未修改内容

- 未修改全局顶栏。
- 未修改 `VideoPane` 内部逻辑。
- 未修改后端、API、数据库、数据结构、部署配置。
- 未用 `overflow-x: hidden` 掩盖横向溢出。
- 未修改无关页面的 UI 行为。

## 影响范围

- UI：仅影响工作台页面的响应式布局与目录树宽度约束。
- 测试：补充工作台手机端 e2e 覆盖。
- 文档：更新当前变更工作单。
- 不影响 API、架构、部署、后端数据结构。

## 当前风险与不确定项

- 手机端工作状态详情默认折叠后，用户需要点击才能看到今日回看统计图和详细覆盖数据；这是为了把工作状态提前到播放器下方且减少第一屏占用。
- 第 4 层之后目录不再继续增加视觉缩进，深层结构主要依靠左侧层级线、展开图标和节点顺序表达。
- 当前工作区还包含同一轮手机端优化的首页、顶栏、个人中心、排行榜等未提交改动；本次没有回滚或扩大这些改动。

## 本次发现但未自动修复的问题

- `frontend/src/shell/AppShell.tsx:712`：`eslint` 报告既有 `react-hooks/exhaustive-deps` warning，提示 `hasAccessiblePomodoroProjectRef` 未列入依赖。
- 风险等级：低。
- 是否影响本次改动：否。

## 验证记录

- 已运行：`pnpm -C frontend exec eslint src/views/workbench/WorkbenchPage.tsx tests/e2e/app-load.spec.ts`，通过。
- 已运行：`LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=4216 pnpm -C frontend exec playwright test tests/e2e/app-load.spec.ts --project=chromium --grep "workbench mobile"`，通过，2 个用例全部通过。
- 已运行：`pnpm -C frontend exec eslint src/views/workbench/WorkbenchPage.tsx src/views/workbench/components/LearningObjectTree.tsx tests/fixtures/mock-api.ts tests/e2e/app-load.spec.ts`，通过。
- 已运行：`git diff --check -- docs/current-change.md frontend/src/index.css frontend/src/shell/AppShell.tsx frontend/src/views/workbench/WorkbenchPage.tsx frontend/src/views/workbench/components/LearningObjectTree.tsx frontend/tests/e2e/app-load.spec.ts frontend/tests/fixtures/mock-api.ts`，通过；仅提示这些工作区文件后续可能被 Git 转换为 CRLF。
- 已运行：`pnpm -C frontend exec eslint src/shell/AppShell.tsx src/views/workbench/WorkbenchPage.tsx src/views/workbench/components/LearningObjectTree.tsx tests/fixtures/mock-api.ts tests/e2e/app-load.spec.ts`，无错误；存在既有 `react-hooks/exhaustive-deps` warning，未修改。
- 已运行：`pnpm -C frontend build`，通过；仍有既有 chunk size warning。

## 仍需用户确认的问题

- 无。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

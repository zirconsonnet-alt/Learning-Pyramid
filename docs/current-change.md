# 当前变更：移动端工作台 final review 修复

## 当前用户要求

- 在隔离 worktree `C:\Users\Bylou\.config\superpowers\worktrees\LearningPyramid\mobile-native-workbench` 修复 final reviewer findings。
- 文件所有权仅限：
  - `mobile/src/app/project/[subjectId]/[scopedProjectId].tsx`
  - `mobile/__tests__/project-route-workbench.test.tsx`
  - `docs/current-change.md`
- 遵守 TDD：先新增失败测试并运行 RED，再改实现。
- 不新增 fallback、shim、legacy、特殊分支、隐式状态、重复逻辑。
- 不修改后端 API、数据库、部署、Web/Tauri、API client、`MobileWorkbenchScreen` presentational 语义。

## 本次实际修改文件

- `mobile/__tests__/project-route-workbench.test.tsx`
  - 新增 pending 提交期间继续新增同 active instance 草稿的回归测试，要求提交成功后只删除本次提交的旧草稿，新草稿保留且未进入提交请求。
  - 新增 route callback 直调不完整草稿时不得创建提交 mutation、不得调用 `submitLearningTask`、不得产生错误态的测试。
  - 新增 `crypto.randomUUID` 必需路径测试，确认新增草稿调用 `globalThis.crypto.randomUUID()`。
- `mobile/src/app/project/[subjectId]/[scopedProjectId].tsx`
  - `createLocalId` 改为单一路径 `globalThis.crypto.randomUUID()`，删除 `Date.now()`/`Math.random()` fallback。
  - route 层复用 `getIncompleteDraftReason` 计算 `firstIncompleteDraftReason`，并纳入 `canSubmitDrafts`。
  - 提交变量保存本次提交的 `submittedLocalIds`，提交成功后只按该集合删除草稿，不再按 `instanceId` 删除。
- `docs/current-change.md`
  - 覆盖为本次 final review 修复工作单，记录 RED/GREEN、影响范围和污染风险检查。

## 行为语义是否变化

- 是。提交成功后的本地草稿清理语义从“清掉同 instance 的全部草稿”改为“只清掉本次提交快照内的 localId 草稿”。
- 是。route 层与 UI 层一致，会在不完整草稿存在时阻止提交回调进入 mutation。
- 是。移动端 route 本地草稿 ID 生成要求运行环境提供 `globalThis.crypto.randomUUID()`；缺失会暴露为环境问题。
- 否。后端 API、数据库、部署、Web/Tauri、API client、`MobileWorkbenchScreen` presentational 语义未变化。

## 重构说明

- 未做跨模块重构。
- 仅做 route 层局部整理：复用既有草稿完整性校验函数，并把提交成功清理边界收敛到本次提交快照。

## 未修改内容

- 未修改后端 API、数据库、部署配置、认证协议。
- 未修改 Web/Tauri 工作台实现或语义。
- 未修改移动端 API client。
- 未修改 `MobileWorkbenchScreen` presentational 组件语义。
- 未通过禁用 pending 期间新增、编辑或删除草稿来绕过提交状态问题。

## 影响范围

- API：无影响。
- 架构：无跨模块边界变化。
- 部署：无影响。
- 数据结构：无影响。
- UI：无 presentational 语义变化；route 层提交门禁更严格。
- 测试：补充 project route workbench 回归覆盖。

## 当前风险点和不确定项

- 无已知影响本次修复正确性的风险点。

## 仍需用户确认的问题

- 无。

## 验证记录

- RED 已运行：`pnpm --dir mobile test -- project-route-workbench.test.tsx`
  - 结果：失败，2 个测试失败。
  - 对应问题：
    - pending 提交成功后新增草稿被清空，期望 `drafts:1`，实际 `drafts:0`。
    - 不完整草稿直调 route callback 创建了 mutation cache 记录，错误为 `题面不能为空`。
- GREEN 已运行：`pnpm --dir mobile test -- project-route-workbench.test.tsx`
  - 结果：通过，1 个测试套件、7 个测试通过。
- GREEN 已运行：`pnpm --dir mobile test`
  - 结果：通过，12 个测试套件、47 个测试通过。
- GREEN 已运行：`pnpm --dir mobile typecheck`
  - 结果：通过，`tsc --noEmit` 退出码为 0。
- GREEN 已运行：`git diff --check -- docs/current-change.md mobile/__tests__/project-route-workbench.test.tsx 'mobile/src/app/project/[subjectId]/[scopedProjectId].tsx'`
  - 结果：通过，退出码为 0；仅输出工作区 LF 将被 Git 触碰时替换为 CRLF 的提示。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

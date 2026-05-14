# Current Change

更新时间：2026-05-14

## 1. 当前用户要求

- 修复右上角学科 / 项目上下文错误显示内部裸 ID（如 `proj_000022`、`proj_000066`）的问题。
- 当前用户已经明确表示这个显示结果不可接受。
- 同一工作区里还包含本次尚未提交的 FAQ 精简改动，需要一起保留。

## 2. 本次实际修改文件

- `frontend/src/shell/AppShell.tsx`
- `frontend/tests/e2e/navigation.spec.ts`
- `docs/guide-faq.md`
- `frontend/src/views/home/HomePage.tsx`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `frontend/src/shell/AppShell.tsx`：修正头部上下文标题生成逻辑。全局页保留当前上下文时，只能展示已解析到的学科/项目名称，不能把原始 `subjectId` / `scopedProjectId` 直接当标题显示。
- `frontend/tests/e2e/navigation.spec.ts`：补充一个回归用例，覆盖“本地持久化里残留无效上下文时，头部不能外露内部 ID”。
- `docs/guide-faq.md`：删除“购买会员立刻就能使用AI功能吗？”这一条 FAQ。
- `frontend/src/views/home/HomePage.tsx`：删除首页 FAQ 中对应的 AI 条目，使首页只保留四条。
- `docs/current-change.md`：切换为当前真实任务组合，并记录验证状态。

## 4. 行为语义是否变化

- 是。右上角在全局页保留上下文时，不再用内部 ID 顶替学科名或项目名。
- 是。当当前上下文只能解析到 ID、解析不到可读名称时，相关头部下拉入口不会继续拿裸 ID 展示给用户。
- 是。首页 FAQ 从 5 条变为 4 条，指南 FAQ 文档同步删除同一条 AI 说明。
- 否。不改变学科/项目真实选择语义，不改变番茄钟拦截语义，不改变 API 或数据结构。

## 5. 是否做了重构，以及为什么

- 否。
- 这次是局部修正 `AppShell` 的标题回退逻辑，并补充回归测试；没有改 store 结构，也没有抽新抽象。

## 6. 未修改哪些相关内容，以及为什么

- 不修改 `useAppStore` 持久化结构，因为当前根因不是存储 schema，而是显示层把未解析 ID 当成了标题。
- 不修改项目/学科真实跳转路径，因为目前没有证据表明 URL 参数顺序被写反。
- 不修改会员页或 AI 使用文档，因为 FAQ 删除不等于功能说明失效。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，右上角上下文不再暴露内部裸 ID；首页 FAQ 少一条卡片。
- 测试：是，新增一个导航回归测试。

## 8. 当前风险点和不确定项

- FAQ 内容仍然是文档和首页前端各维护一份；这次只同步删除，不在本次任务里收敛成单一数据源。
- 这次修的是“显示层不能暴露未解析 ID”；如果后续发现某处确实把 `subjectId` / `projectId` 写反，那是另一个独立数据污染问题，需要单独追根。

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

- `pnpm exec playwright test tests/e2e/navigation.spec.ts -g "global pages do not expose unresolved project identifiers" --reporter=line`（dev server，端口 `4210`）：通过。
- `pnpm build`：通过。
- `pnpm exec playwright test tests/e2e/navigation.spec.ts --reporter=line`（preview 形态，新端口 `4211`）：4 passed。
- `pnpm exec tsc -b --noEmit`：通过。
- `git diff --check`：通过，仅有 LF/CRLF 提示。

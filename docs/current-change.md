# Current Change

更新时间：2026-05-14

## 1. 当前用户要求

- 统一以下详情页左侧概览卡：
  - 复习任务详情页
  - 复习链详情页
  - 收敛详情页
  - 学习任务详情页
  - 复述点详情页
  - 实例详情页
  - 学习对象详情页
- 左侧概览卡内删除“返回 xxx”类按钮。
- 左侧概览卡一级标题统一为“图标 + 名字”，下方加横杠。
- 名字规则：
  - 复习任务、复习链、收敛、复述点没有具体名字，分别显示固定名称。
  - 学习任务、实例、学习对象显示具体名字。
- 删除这些详情页概览卡内类似“项目：网课材料”的项目归属文案。

## 2. 本次实际修改文件

- `frontend/src/views/shared/DetailSummaryCard.tsx`
- `frontend/src/views/reviewTasks/ReviewTaskPage.tsx`
- `frontend/src/views/reviewChains/ReviewChainPage.tsx`
- `frontend/src/views/convergences/ConvergencePage.tsx`
- `frontend/src/views/learningTasks/LearningTaskNodePage.tsx`
- `frontend/src/views/recallPoints/RecallPointPage.tsx`
- `frontend/src/views/instances/InstancePage.tsx`
- `frontend/src/views/learningObjects/LearningObjectNodePage.tsx`
- `frontend/tests/e2e/detail-summary-cards.spec.ts`
- `frontend/tests/fixtures/test-data.ts`
- `frontend/tests/fixtures/mock-api.ts`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `DetailSummaryCard.tsx`：把详情页左卡标题统一为“图标 + 名字 + 下方横杠”，并保留原有统计项卡片结构。
- `ReviewTaskPage.tsx`：复习任务左卡改用共享标题，删除左卡返回按钮和项目归属文案。
- `ReviewChainPage.tsx`：复习链左卡改用共享标题，删除左卡返回按钮和项目归属文案。
- `ConvergencePage.tsx`：收敛左卡改用共享标题，标题从“收敛详情”统一为“收敛”，删除左卡返回按钮和项目归属文案。
- `LearningTaskNodePage.tsx`：学习任务左卡改用共享标题，保留原有名称编辑能力，删除左卡返回按钮。
- `RecallPointPage.tsx`：复述点左卡改用共享标题，标题从“复述点详情”统一为“复述点”，删除左卡返回按钮。
- `InstancePage.tsx`：实例左卡改用共享标题，删除左卡返回按钮和说明文案。
- `LearningObjectNodePage.tsx`：学习对象左卡改用共享标题，删除左卡返回按钮。
- `detail-summary-cards.spec.ts`：新增 7 个详情页左卡 e2e，覆盖统一标题、图标、横杠、无左卡返回按钮、无项目归属文案。
- `test-data.ts`：补齐复习链、收敛、学习任务节点等 e2e 确定性数据。
- `mock-api.ts`：补齐上述详情页会访问的 mock API。
- `docs/current-change.md`：覆盖为本次任务工作单。

## 4. 行为语义是否变化

- 是，详情页左侧概览卡的可见 UI 层级变化。
- 不改变详情页路由、API、数据读取或业务行为。

## 5. 是否做了重构，以及为什么

- 是，做了局部共享组件抽取。
- 原因：7 个详情页左卡标题结构分散实现，如果继续逐页手写会保留重复逻辑和未来分叉风险。

## 6. 未修改哪些相关内容，以及为什么

- 不修改详情页右侧主体内容，因为用户只要求左侧概览卡。
- 不修改缺少上下文、未找到数据等空状态里的返回按钮，因为用户限定的是详情页左边卡片。
- 不修改路由、API、数据结构、部署配置。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，详情页左侧概览卡标题和局部操作入口变化。
- 测试：是，新增 e2e 覆盖 7 个详情页左卡，并补齐 e2e mock 数据。

## 8. 当前风险点和不确定项

- 无。

## 9. 仍需用户确认的问题

- 无。用户已确认执行。

## 10. 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

## 11. 验证状态

- 已先运行新增 e2e，旧实现中 7 个页面均因找不到统一左卡测试标识而失败。
- `pnpm --dir frontend build`：通过；仍有既有 `hls` chunk 大于 500 kB 的 warning。
- `pnpm --dir frontend exec playwright test frontend/tests/e2e/detail-summary-cards.spec.ts`：通过，7 个用例全部通过。
- `pnpm --dir frontend exec playwright test frontend/tests/e2e/subject-project.spec.ts`：通过，6 个用例全部通过。
- `pnpm --dir frontend exec playwright test frontend/tests/e2e/navigation.spec.ts`：通过，2 个用例全部通过。
- `pnpm --dir frontend exec playwright test frontend/tests/e2e/workbench-review.spec.ts`：通过，7 个用例全部通过。

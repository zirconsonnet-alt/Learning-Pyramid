# Current Change

更新时间：2026-05-14

## 1. 当前用户要求

- 复习任务、复习链、收敛、学习任务四个详情页左侧概览卡的相关项排序保持一致。
- 把“关联内容”统一改为“关联入口”，并做成可点击蓝链。
- 收敛详情页的关联入口指向所属复习链。
- 复习任务详情页的关联入口指向所属收敛；如果不是收敛生成的复习任务，则指向所属复习链。
- 删除收敛详情、复习任务详情、复习链右侧队列中对用户不可读的裸 ID 引用。
- 删除实例详情页左卡中“当前引用”“内容引用”暴露的不可读裸 ID。
- 调整实例详情页左侧卡片结构，避免对象树入口挤在概览卡里导致左栏视觉上和其他详情页不统一。
- 让实例详情页内的视频卡使用详情页 surface，不再沿用工作台主卡壳。
- 删除复习任务详情页“复习结果详情”下方说明文案。

## 2. 本次实际修改文件

- `backend/models/review_item_binding.py`
- `backend/models/__init__.py`
- `backend/system/api.py`
- `backend/system/persistence_store.py`
- `backend/system/postgres_store.py`
- `adapter/mappers.py`
- `adapter/routers/review.py`
- `frontend/src/ui/api/review.ts`
- `frontend/src/ui/queries/reviewTasks.ts`
- `frontend/src/ui/queries/reviewChains.ts`
- `frontend/src/views/reviewTasks/ReviewTaskPage.tsx`
- `frontend/src/views/reviewChains/ReviewChainPage.tsx`
- `frontend/src/views/convergences/ConvergencePage.tsx`
- `frontend/src/views/learningTasks/LearningTaskNodePage.tsx`
- `frontend/src/views/instances/InstancePage.tsx`
- `frontend/src/views/workbench/components/VideoPane.tsx`
- `frontend/src/views/recallPoints/components/RecallPointListCard.tsx`
- `frontend/tests/fixtures/mock-api.ts`
- `frontend/tests/e2e/review-detail-entry-links.spec.ts`
- `tests/test_review_item_bindings.py`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `review_item_binding.py` / `backend/models/__init__.py`：新增只读绑定结果模型，表达“复习任务/收敛属于哪个上级入口”。
- `backend/system/api.py`：新增 `get_convergence_binding`、`get_review_task_binding`，在后端按真实复习链/收敛关系反查入口。
- `persistence_store.py` / `postgres_store.py`：给 SQLite/PostgreSQL snapshot store 增加复习链和收敛的项目内只读列表查询，供绑定反查使用。
- `adapter/mappers.py` / `adapter/routers/review.py`：暴露两个 scoped project 只读接口，并把领域模型映射为前端 DTO。
- `frontend/src/ui/api/review.ts`：新增绑定 DTO schema 和请求函数。
- `frontend/src/ui/queries/reviewTasks.ts` / `reviewChains.ts`：接入绑定查询。
- `ReviewTaskPage.tsx`：左卡新增“关联入口”蓝链，删除当前引用、范围 ID 和结果详情说明文案；逐题结果不再显示复述点/实例裸 ID。
- `ReviewChainPage.tsx`：左卡排序统一；右侧队列不再显示复习任务、收敛步骤和范围裸 ID。
- `ConvergencePage.tsx`：左卡新增“关联入口”蓝链，删除当前引用和种子范围裸 ID；轮次列表不再显示复习任务和范围裸 ID。
- `LearningTaskNodePage.tsx`：把叶子学习任务左卡“关联内容”改为“关联入口”，实例入口显示为可点击蓝链。
- `InstancePage.tsx`：删除实例详情页左卡里的“当前引用”和“内容引用”，避免向用户暴露内容实例/内容裸 ID。
- `InstancePage.tsx`：把对象节点入口移出概览卡，作为左栏独立操作，概览卡只保留实例状态、复述点、最近看到三项。
- `VideoPane.tsx`：新增显式 `surface` 参数，工作台默认保持 `workbench`，实例详情页传入 `detail` 后使用详情页卡片外壳。
- `RecallPointListCard.tsx`：把缺省锚点标签文案从“关联内容”同步为“关联入口”。
- `mock-api.ts`：补齐新绑定接口的 e2e mock。
- `review-detail-entry-links.spec.ts`：覆盖四个详情页左卡顺序、蓝链和裸 ID 清理。
- `test_review_item_bindings.py`：覆盖后端只读绑定语义，确保复习任务优先归属收敛，否则归属复习链。

## 4. 行为语义是否变化

- 是，新增两个只读 API，用于读取复习任务/收敛的上级关联入口。
- 是，复习任务、复习链、收敛、学习任务、实例详情页左卡的可见字段、顺序和链接行为变化。
- 是，实例详情页播放器外层视觉 surface 变化；工作台播放器默认行为不变。
- 否，不改变复习链、收敛、复习任务的生成、推进、存储结构或调度语义。

## 5. 是否做了重构，以及为什么

- 做了局部模型和查询整理。
- 原因：前端无法可靠从已有详情响应中得知复习任务或收敛的上级入口；如果在前端扫全量数据反查，会留下隐式关系和重复逻辑。
- 做了局部组件参数化。
- 原因：实例详情页需要复用播放器能力，但不能复用工作台页面壳；`surface` 是显式调用语义，避免通过隐式 CSS 覆盖修视觉问题。

## 6. 未修改哪些相关内容，以及为什么

- 不修改数据库 schema，因为所需关系已经存在于 `review_chain_index.queue_json` 和 `convergence_index.review_task_ids_json`。
- 不修改调度推进逻辑，因为本次只读展示关联入口。
- 不删除或改名已有详情 API，避免无关公共接口变更。
- 不清理工作台、设置页等非详情页主路径内的 ID 文案。
- 不新增实例专属 AI 问答上下文，因为现有 AI 路由只支持 task/object/recall，强行接入实例会留下隐式约定。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：是，新增两个 scoped project 只读接口。
- 架构：否，仍由 router 调用公开 `SystemAPI`，不绕过边界。
- 部署：否。
- 数据结构：否。
- UI：是，复习任务、复习链、收敛、学习任务、实例详情页左卡和复习链/收敛/复习任务右侧详情展示变化；实例详情页视频卡 surface 变化。
- 测试：是，新增后端单测和前端 e2e。

## 8. 当前风险点和不确定项

- `pnpm --dir frontend build` 仍有既有 `hls` chunk 大于 500 kB warning，非本次引入。
- Browser 插件未暴露可调用 Node REPL/browser 工具，本轮渲染验证使用项目内 Playwright。

## 9. 仍需用户确认的问题

- 无。用户已确认“继续”实现该语义。

## 10. 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

## 11. 验证状态

- `python -m pytest tests/test_review_item_bindings.py -q`：通过。
- `pnpm --dir frontend build`：通过；仍有既有 `hls` chunk warning。
- `CI=1 LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=4195 pnpm --dir frontend exec playwright test frontend/tests/e2e/review-detail-entry-links.spec.ts frontend/tests/e2e/detail-summary-cards.spec.ts --reporter=line`：通过，12 passed。
- `python tools/verify_backend_boundaries.py --report-only`：通过。
- `git diff --check`：通过。

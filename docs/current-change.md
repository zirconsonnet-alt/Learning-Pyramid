# Current Change

更新时间：2026-05-15

## 1. 当前用户要求

- 调整实例详情页结构。
- 实例详情页不要再展示复述点列表。
- 去掉左侧单独的“查看对象节点”按钮，改为左侧摘要卡里的“关联节点”蓝链入口。

## 2. 本次实际修改文件

- `frontend/src/views/instances/InstancePage.tsx`
- `frontend/tests/e2e/review-detail-entry-links.spec.ts`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `frontend/src/views/instances/InstancePage.tsx`：移除实例页底部复述点列表和左侧独立按钮，把对象节点入口收进摘要卡的“关联节点”字段。
- `frontend/tests/e2e/review-detail-entry-links.spec.ts`：更新实例详情页回归断言，要求存在“关联节点”蓝链，且不再出现复述点列表和独立按钮。
- `docs/current-change.md`：切换为当前任务，并记录验证状态。

## 4. 行为语义是否变化

- 是。实例详情页不再承担复述点列表入口，只保留实例摘要和关联对象节点入口。
- 是。对象节点查看入口从独立按钮改为摘要卡字段中的蓝链。
- 否。不改变对象节点绑定关系、视频播放、API 或数据结构。

## 5. 是否做了重构，以及为什么

- 否。
- 这次是实例详情页的局部裁剪，没有引入新抽象，也没有跨模块重构。

## 6. 未修改哪些相关内容，以及为什么

- 不修改学习对象节点详情页的复述点列表，因为用户明确表示那一页承担复述点展示。
- 不修改实例页视频面板，因为这次只调整关联入口和重复内容区。
- 不修改后端查询，因为当前问题是实例页布局职责重复，不是数据接口问题。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，实例详情页移除复述点列表，摘要卡新增“关联节点”蓝链。
- 测试：是，更新实例详情页 e2e 回归断言。

## 8. 当前风险点和不确定项

- 如果实例当前没有绑定对象节点，摘要卡里的“关联节点”需要给出稳定的不可点击占位文案。
- 这次删除的是实例页重复展示，不影响从对象节点页进入复述点详情的主路径。

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

- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4218; pnpm exec playwright test tests/e2e/review-detail-entry-links.spec.ts -g "instance detail removes opaque ids from the summary card" --reporter=line`：失败，确认当前页面还没有“关联节点”字段。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4220; pnpm exec playwright test tests/e2e/review-detail-entry-links.spec.ts -g "instance detail removes opaque ids from the summary card" --reporter=line`：1 passed。
- `pnpm exec tsc -b --noEmit`：通过。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4221; pnpm exec playwright test tests/e2e/review-detail-entry-links.spec.ts tests/e2e/detail-summary-cards.spec.ts --reporter=line`：12 passed。
- `pnpm build`：通过，保留既有 chunk size warning。
- `git diff --check`：通过，仅有 LF/CRLF 提示。

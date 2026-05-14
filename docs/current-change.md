# Current Change

更新时间：2026-05-14

## 1. 当前用户要求

- 修复推荐复习页锚点文案和工作台复习卡片不一致的问题。
- 推荐复习页不能显示 `内容实例 #...` 或 `t=...` 这类用户不可读的内部引用。
- 推荐复习页应和工作台一样展示“实例 / 视频可读名称 + 可读时间”。

## 2. 本次实际修改文件

- `frontend/src/ui/displayIdentifiers.ts`
- `frontend/src/views/recommendations/ReviewRecommendationsPage.tsx`
- `frontend/src/views/workbench/components/ReviewPane.tsx`
- `frontend/tests/e2e/workbench-review.spec.ts`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `frontend/src/ui/displayIdentifiers.ts`：新增共享锚点展示函数，统一把视频锚点格式化为可读实例名和可读时间。
- `frontend/src/views/recommendations/ReviewRecommendationsPage.tsx`：加载项目实例列表，用实例名解析推荐复习项的锚点文案。
- `frontend/src/views/workbench/components/ReviewPane.tsx`：删除本地重复的锚点格式化逻辑，改用共享函数。
- `frontend/tests/e2e/workbench-review.spec.ts`：把推荐复习页回归测试从接受裸 ID 改为要求显示可读锚点。
- `docs/current-change.md`：切换为当前任务，并记录修改范围和验证状态。

## 4. 行为语义是否变化

- 是。推荐复习页锚点从内部引用展示改为用户可读展示。
- 是。工作台和推荐复习页现在共用同一套锚点文案规则。
- 否。不改变推荐复习算法、题目顺序、锚点跳转目标、API 或数据结构。

## 5. 是否做了重构，以及为什么

- 是，做了局部重构。
- 原因是推荐复习页和工作台此前各自维护一套锚点文案逻辑，已经导致 UI 行为分叉；抽到共享展示函数可以消除重复逻辑。

## 6. 未修改哪些相关内容，以及为什么

- 不修改后端推荐复习接口，因为前端已有实例列表查询能力，根因不在后端响应结构。
- 不修改工作台复习流程、提交答案流程或推荐阈值逻辑，因为它们不影响本次裸 ID 展示问题。
- 不修改详情页引用展示，因为本次问题出现在推荐复习页和工作台复习卡片的锚点文案分叉。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，推荐复习页锚点文案改为用户可读显示。
- 测试：是，更新推荐复习页 e2e 回归断言。

## 8. 当前风险点和不确定项

- 如果实例列表中暂时没有对应实例，页面会显示通用的“内容实例”文案，不再暴露内部 ID。
- 推荐复习页新增一次已有的实例列表查询；该查询也是工作台现有数据流，不新增 API。

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

- 已先运行 `pnpm exec playwright test tests/e2e/workbench-review.spec.ts --reporter=line`，新增断言在推荐复习页失败，确认能复现当前裸 ID 分叉。
- `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1; LEARNINGPYRAMID_FRONTEND_E2E_PORT=4215; pnpm exec playwright test tests/e2e/workbench-review.spec.ts --reporter=line`：7 passed。
- `pnpm exec tsc -b --noEmit`：通过。
- `pnpm build`：通过，保留既有 chunk size warning。
- `LEARNINGPYRAMID_FRONTEND_E2E_PORT=4216; pnpm exec playwright test tests/e2e/workbench-review.spec.ts --reporter=line`（preview 形态）：7 passed。
- `git diff --check`：通过，仅有 LF/CRLF 提示。

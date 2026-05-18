# 当前变更：移动端复习队列提交

## 当前用户要求

- 继续 React Native 移动端 App MVP。
- 当前执行 Task 8：实现基础复习队列查看与复习结果提交。
- 不能伪造 `reviewTaskId`，不能从推荐复习项隐式推导提交入口。

## 根因

- 移动端已有学习对象详情和复述点查看，但还不能执行复习闭环。
- `/review-recommendations` 返回的是推荐复述点，不包含当前可提交的 `reviewTaskId`。
- 现有公开 `/queue` 能返回严格 FIFO 队列头 `headId`，可作为干净的复习任务提交入口。

## 本次实际修改文件

- `mobile/__tests__/review-queue.test.tsx`
  - 新增复习队列提交 RED/GREEN 测试，覆盖 `canRecall` 按 range 顺序提交和无 queue head 时不暴露提交。
- `mobile/__tests__/domain-api.test.ts`
  - 覆盖 `/queue`、`/review-tasks/{reviewTaskId}`、`/ranges/{rangeId}` 公开 scoped API 路径。
- `mobile/src/api/review.ts`
  - 新增 `Queue`、`ReviewTask`、`RangeSnapshot` schema 和 `getQueue`、`getReviewTask`、`getRangeSnapshot`。
- `mobile/src/screens/ReviewQueueScreen.tsx`
  - 新增移动端复习队列屏，按 range 顺序作答并提交 `canRecall`。
- `mobile/src/app/review/[subjectId]/[scopedProjectId].tsx`
  - 新增复习路由：读取队列头、任务、范围和复述点，并提交队列头复习任务。
- `mobile/src/screens/ProjectScreen.tsx`
  - 在学习对象列表页增加复习入口。
- `mobile/src/app/project/[subjectId]/[scopedProjectId].tsx`
  - 将复习入口接入 `/review/[subjectId]/[scopedProjectId]`。
- `docs/current-change.md`
  - 覆盖为当前 Task 8 工作单。

## 行为语义是否变化

- 移动端项目页可进入复习。
- 如果队列为空，显示“暂无复习任务”，不允许提交。
- 如果存在 queue head，移动端按该 review task 的 input range 展示复述点。
- 用户逐题选择“记得 / 不记得”后，提交 `canRecall` 数组，顺序严格跟随 range 的 `recallPointIds`。
- 不使用 `/review-recommendations` 作为提交来源，不伪造 `reviewTaskId`。
- 不改变后端 API、部署、数据库结构或 Web/Tauri 行为。

## 重构说明

- 未做跨模块重构。
- 仅在移动端 review API client 中补齐当前任务必需的公开 endpoints。

## 未修改内容

- 未修改后端复习协议。
- 未新增移动端专用复习协议。
- 未实现推荐复习的独立移动端界面。
- 未实现追加理解 `appendedInsights`；当前只提交基础 `canRecall`。
- 未更新长期文档；移动端 MVP 预览整体完成后统一同步。

## 影响范围

- API：仅移动端 client 调用现有公开 scoped endpoints。
- 架构：无跨模块架构变化。
- 部署：无影响。
- 数据结构：无影响。
- UI：新增移动端复习队列和项目页复习入口。
- 测试：新增复习队列测试，扩展领域 API 路径测试。

## 当前风险点和不确定项

- 真实数据中如果 range 的 `recallPointIds` 与复述点列表不一致，移动端会显示“复习内容加载不完整”并阻止提交。
- 当前只覆盖基础 `canRecall` 提交，不覆盖追加理解。

## 仍需用户确认的问题

- 无。

## 验证记录

- RED：`pnpm --dir mobile test -- review-queue.test.tsx` 失败，摘要：`../src/screens/ReviewQueueScreen` 不存在。
- RED：`pnpm --dir mobile test -- domain-api.test.ts` 失败，摘要：`api.review.getQueue is not a function`。
- GREEN：`pnpm --dir mobile test -- review-queue.test.tsx` 通过，1 个测试套件、2 个测试通过。
- GREEN：`pnpm --dir mobile test -- domain-api.test.ts` 通过，1 个测试套件、1 个测试通过。
- 已运行：`pnpm --dir mobile test -- review-queue.test.tsx domain-api.test.ts`，通过，2 个测试套件、3 个测试通过。
- 已运行：`pnpm --dir mobile test`，通过，9 个测试套件、27 个测试通过。
- 已运行：`pnpm --dir mobile typecheck`，通过。
- 已运行：`git diff --check -- docs/current-change.md mobile/__tests__/review-queue.test.tsx mobile/__tests__/domain-api.test.ts mobile/src/api/review.ts mobile/src/screens/ReviewQueueScreen.tsx mobile/src/screens/ProjectScreen.tsx mobile/src/app/project mobile/src/app/review`，通过；仅有 Git 换行转换 warning，无 whitespace error。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

# 当前变更：Task 4 移动端领域 API client

## 当前用户要求

- 实现移动端领域 API client。
- 只能封装现有公开 HTTP API。
- 继续使用 `{subjectId, scopedProjectId}`，不能发明或持久化内部 backend project id。
- 按 TDD 先写失败测试并记录 RED，再实现生产代码。
- 只修改 Task 4 允许文件，并提交 `feat: add mobile domain api`。

## 根因

- 移动端目前只有通用 `createApiClient`，缺少面向现有公开 HTTP API 的领域 client。
- scoped project 路径如果由调用方散落拼接，容易误用内部 project id 或产生路径不一致。

## 本次实际修改文件

- `mobile/__tests__/domain-api.test.ts`
  - 新增 RED 测试，要求 `learningObjects.listNodes` 使用公开 scoped project 路径。
- `mobile/src/api/types.ts`
  - 新增 `ScopedProjectRef`、`ApiRequester`、`projectApiPath` 和 `createLearningPyramidApi` 聚合入口。
- `mobile/src/api/auth.ts`
  - 新增 `AuthUserSchema` 和 `/auth/me`、`/auth/login`、`/auth/logout` client。
- `mobile/src/api/subjects.ts`
  - 新增 `SubjectSchema`、`StudyMaterialSchema` 和 `/subjects`、`/subjects/{subjectId}/materials` client。
- `mobile/src/api/learningObjects.ts`
  - 新增 `LearningObjectNodeSchema` discriminated union 和 `listNodes(scope)`。
- `mobile/src/api/media.ts`
  - 新增 `PlaybackDescriptorSchema` 和 `getPlayback(scope, instanceId)`。
- `mobile/src/api/review.ts`
  - 新增 `RecallPointSchema`、`ReviewRecommendationItemSchema`、`ReviewRecommendationPageSchema` 和复习相关 client。
- `docs/current-change.md`
  - 覆盖为 Task 4 工作单并记录 RED/GREEN。

## 行为语义是否变化

- 移动端新增领域 API client 封装。
- 不新增移动端专用协议。
- 不使用、发明或持久化内部 backend project id。
- `question` / `answer` 当前保持 `z.unknown()`，不在本任务发明 rich content 模型。

## 重构说明

- 做了当前需求范围内的局部模块拆分。
- 原因是按领域文件隔离 schema 和 endpoint，避免调用方重复拼接 scoped project 路径。

## 未修改内容

- 未修改后端 API、认证策略、部署配置或移动端 HTTP envelope 处理。
- 未修改无关工作区改动。
- 未新增移动端专用协议、内部 backend project id 字段或持久化逻辑。
- 未更新长期文档；本次只新增移动端 client 封装，不改变后端公开 API 或长期部署/架构事实。

## 影响范围

- API：移动端新增公开 HTTP API 封装；后端 API 无变化。
- 架构：不改变现有后端 scoped project 边界。
- 部署：无影响。
- 数据结构：无影响。
- UI：无影响。
- 测试：新增移动端领域 API 路径测试。

## 当前风险点和不确定项

- 风险低；schema 只按现有后端 DTO 字段建模。
- 本次只验证了聚合入口的 scoped path 行为，没有为每个领域方法补独立路径测试。

## 仍需用户确认的问题

- 无。

## 验证记录

- RED：`pnpm --dir mobile test -- domain-api.test.ts` 失败，摘要：`Cannot find module '../src/api/types' from '__tests__/domain-api.test.ts'`。
- GREEN：`pnpm --dir mobile test -- domain-api.test.ts` 通过，1 个测试套件、1 个测试通过。
- GREEN：`pnpm --dir mobile typecheck` 通过。
- GREEN：`git diff --check -- mobile/src/api/types.ts mobile/src/api/auth.ts mobile/src/api/subjects.ts mobile/src/api/learningObjects.ts mobile/src/api/media.ts mobile/src/api/review.ts mobile/__tests__/domain-api.test.ts docs/current-change.md` 通过；仅有 Git 换行转换 warning，无 whitespace error。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

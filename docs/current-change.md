# 当前变更：移动端学习任务 API client

## 当前用户要求

- Expo Go Android 原生移动端需要补齐项目内学习主流程。
- 已确认继续 React Native 路线。
- 当前执行 Task 1：为 mobile API 增加 `POST /learning-tasks` client。
- 不修改后端 API、数据库、Web/Tauri 工作台语义。

## 根因

- `createLearningPyramidApi` 当前聚合了认证、学科、学习对象、媒体和复习 API。
- 移动端缺少 `learningTasks` 子客户端，因此无法通过现有 scoped project endpoint 提交学习任务。

## 本次实际修改文件

- `mobile/__tests__/domain-api.test.ts`
  - 增加 `api.learningTasks.submitLearningTask` 的路径、方法和请求体断言。
- `mobile/src/api/learningTasks.ts`
  - 新增学习任务提交 API client、输入类型和响应 schema。
- `mobile/src/api/types.ts`
  - 在 `createLearningPyramidApi` 中注册 `learningTasks` client。
- `docs/current-change.md`
  - 覆盖为当前 Task 1 工作单。

## 行为语义是否变化

- 是。移动端 API 现在可以通过既有公开 scoped project endpoint 提交学习任务：
  - `POST /subjects/{subjectId}/projects/{scopedProjectId}/learning-tasks`
- 后端 API 语义未变化。
- Web/Tauri 工作台语义未变化。

## 重构说明

- 无跨模块重构。
- 仅按现有 `mobile/src/api/*` 模块边界新增一个同级 API client，并在聚合入口注册。

## 未修改内容

- 未修改后端 API、数据库结构、部署配置、Web/Tauri 工作台代码。
- 未修改测试去适配错误实现。
- 未新增 fallback、shim、legacy 或临时兼容逻辑。

## 影响范围

- API：仅移动端 API client 暴露新增 `learningTasks.submitLearningTask`。
- 架构：无影响。
- 部署：无影响。
- 数据结构：无影响。
- UI：无影响。
- 测试：更新移动端 domain API 路径测试。

## 当前风险点和不确定项

- 无已知风险点。

## 仍需用户确认的问题

- 无。

## 验证记录

- RED 已运行：`pnpm --dir mobile test -- domain-api.test.ts`
  - 结果：失败，符合预期；失败原因为 `api.learningTasks` 不存在。
- GREEN 已运行：`pnpm --dir mobile test -- domain-api.test.ts`
  - 结果：通过，1 个测试套件、1 个测试通过。
- GREEN 已运行：`pnpm --dir mobile typecheck`
  - 结果：通过。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

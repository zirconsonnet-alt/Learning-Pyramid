# 当前变更：移动端领域 API client 契约收紧

## 当前用户要求

- 继续 React Native 移动端 App MVP。
- 当前处于 Task 4 质量审查修复。
- 收紧移动端领域 API client schema，使其对齐现有 Web API / 后端 DTO。
- 补全 auth、subjects、learningObjects、media、review 的公开路径测试。

## 根因

- Task 4 初始领域 API client 为快速接入放宽了部分字段类型，例如时间字段使用 `z.unknown()`、枚举字段使用 `z.string()`。
- 这会把真实 API 契约变成隐式约定，后续 UI 可能误判字段形状。
- `subjects` 列表方法命名为 `list`，不如 `listSubjects` 清晰，容易在后续页面实现中造成误用。

## 本次实际修改文件

- `mobile/src/api/auth.ts`
  - 对齐现有 AuthUser DTO，将时间、昵称、简介等字段收紧为实际字符串/nullable 语义。
- `mobile/src/api/subjects.ts`
  - 对齐现有 Subject/StudyMaterial DTO，新增 `StudyMaterialTypeSchema`，收紧时间、标题和材料类型字段。
  - 将 `subjects.list` 改为 `subjects.listSubjects`。
- `mobile/src/api/media.ts`
  - 对齐现有 playback descriptor，收紧 source/playback 枚举和 duration 非负整数。
- `mobile/src/api/review.ts`
  - 对齐现有 recall/review recommendation DTO，收紧状态、时间、计数字段。
  - `question` / `answer` 仍保持 `z.unknown()`，不发明 rich content 模型。
- `mobile/__tests__/domain-api.test.ts`
  - 补全 auth、subjects、learningObjects、media、review 的公开 API 路径和提交 body 测试。
- `docs/current-change.md`
  - 更新当前工作单。

## 行为语义是否变化

- 移动端领域 API client 的解析语义更严格，会更早暴露与现有 API DTO 不一致的问题。
- 不改变后端 API、部署、数据结构或 Web/Tauri 运行行为。
- 不新增移动端专用协议。
- 不使用、发明或持久化内部 backend project id。

## 重构说明

- 未做跨模块重构。
- 仅在移动端 API client 内部做当前任务范围内的 schema 收紧和测试补强。

## 未修改内容

- 未修改后端 API。
- 未修改移动端 HTTP envelope 和 cookie helper。
- 未发明移动端 rich content 模型。
- 未修改 Web、桌面端、部署或数据结构。
- 未更新长期文档；本次是移动端内部 API client 契约收紧，长期边界仍与 `docs/mobile-client.md` 一致。

## 影响范围

- API：不改变后端 API，仅收紧移动端解析契约。
- 架构：无影响。
- 部署：无影响。
- 数据结构：无影响。
- UI：无影响。
- 测试：补全移动端领域 API 路径和 body 测试。

## 当前风险点和不确定项

- `question` / `answer` 暂用 `z.unknown()` 是已确认边界；后续如要移动端编辑 rich content，需单独确认模型。
- Task 8 复习提交仍可能受后端 review task id 可获取性影响；不能伪造 task id。

## 仍需用户确认的问题

- 无。

## 验证记录

- 已运行：`pnpm --dir mobile test -- domain-api.test.ts`，通过，1 个测试套件、1 个测试通过。
- 已运行：`pnpm --dir mobile typecheck`，通过。
- 已运行：`git diff --check -- mobile/src/api/auth.ts mobile/src/api/subjects.ts mobile/src/api/media.ts mobile/src/api/review.ts mobile/__tests__/domain-api.test.ts docs/current-change.md`，通过；仅有 Git 换行转换 warning，无 whitespace error。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

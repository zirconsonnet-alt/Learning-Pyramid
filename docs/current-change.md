# 当前变更：移动端 MVP 文档同步

## 当前用户要求

- 继续 React Native 移动端 App MVP。
- 当前执行 Task 9：同步 README、移动端长期文档和当前工作单。

## 根因

- 移动端 MVP 已完成基础工程、认证、学科/材料/学习对象、媒体详情和复习队列提交。
- 长期文档仍停留在设计边界，需要补充当前实现、运行命令、媒体限制和验证方式。

## 本次实际修改文件

- `README.md`
  - 新增移动端 App 预览说明、启动命令、验证命令和 `docs/mobile-client.md` 链接。
- `docs/mobile-client.md`
  - 补充当前已实现功能、媒体支持边界、本地运行命令和验证命令。
- `docs/current-change.md`
  - 覆盖为当前 Task 9 工作单。

## 行为语义是否变化

- 无。仅文档同步。

## 重构说明

- 无。

## 未修改内容

- 未修改代码、测试、后端 API、部署、数据库结构或构建配置。
- 未更新 `docs/architecture.md` 和 `docs/deployment.md`；本次没有改变系统架构或部署方式。

## 影响范围

- API：无影响。
- 架构：无影响。
- 部署：无影响。
- 数据结构：无影响。
- UI：无影响。
- 测试：无测试代码变化。

## 当前风险点和不确定项

- README 在本次开始前已有未提交的 Windows desktop client 说明；本次只新增移动端段落，提交时需要避免把既有无关 README 改动混入。
- 真实 Android/iOS 媒体播放 smoke 仍未运行。

## 仍需用户确认的问题

- 无。

## 验证记录

- 已运行：`pnpm --dir mobile test`，通过，9 个测试套件、27 个测试通过。
- 已运行：`pnpm --dir mobile typecheck`，通过。
- 已运行：`git diff --check -- README.md docs/mobile-client.md docs/current-change.md`，通过；仅有 Git 换行转换 warning，无 whitespace error。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

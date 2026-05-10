# Current Change

更新时间：2026-05-10

## 1. 本轮用户要求

- 建立后端对应的长期文档。
- `README.md` 不再提到 `docs/self-host.md`。

## 2. 实际修改文件

- `README.md`
- `docs/architecture.md`
- `docs/api.md`
- `docs/deployment.md`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `README.md`：把不存在的 `docs/self-host.md` 链接改为新建的 `docs/deployment.md`。
- `docs/architecture.md`：记录当前后端运行形态、模块职责、数据流、边界规则和已知边界风险。
- `docs/api.md`：记录当前 API 根路径、认证公开路径、健康检查和主要路由分组索引。
- `docs/deployment.md`：记录 release、dev、自托管 Docker、数据持久化、迁移、备份恢复和验证入口。
- `docs/current-change.md`：记录本轮文档变更与污染风险检查。

## 4. 行为语义是否变化

否。只修改文档和 README 链接，不改变代码、API 行为、部署脚本或运行时配置。

## 5. 是否做了重构，以及为什么

否。没有代码重构，也没有移动、删除或改名现有模块。

## 6. 未修改哪些相关内容，以及为什么

- 未修改后端代码：本轮需求是建立文档和清理 README 失效链接。
- 未创建 `docs/self-host.md`：用户明确要求 README 不再提到该文档，且新的部署说明已放入 `docs/deployment.md`。
- 未补写 membership 或 frontend automation 长期文档：这两个 README 引用也指向当前不存在的文件，但不属于本轮明确要求，且需要单独确认文档范围。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：无行为影响；新增 `docs/api.md` 作为维护索引。
- 架构：无行为影响；新增 `docs/architecture.md` 记录当前边界。
- 部署：无行为影响；新增 `docs/deployment.md` 并让 README 指向它。
- 数据结构：无影响。
- UI：无影响。
- 测试：无测试语义变化。

## 8. 风险点和不确定项

- `docs/api.md` 是维护索引，不替代运行时 OpenAPI schema。
- 当前仓库已有大量未提交改动，本轮只触碰上述文档和 README 链接。
- 现有 specs 记录了若干后端边界风险，本文没有把这些风险标记为已解决。

## 9. 需要用户确认的问题

无当前阻塞项。

后续如需处理 README 中其它不存在的文档链接，应单独确认是否创建对应文档或移除链接。

## 10. 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

## 11. 部署目标修正

2026-05-10 追加：

- 问题：`Sync-Selfhost-Server.bat` 的 `SERVER_HOST` 在本轮提交中从既有可用目标 `plm.xuebao.chat` 变成了占位值 `learningpyramid.example.com`。
- 根因：提交整个工作区时没有拦截这处部署目标漂移，导致同步脚本使用了不可解析的占位域名。
- 修正：恢复 `SERVER_HOST=plm.xuebao.chat`。
- 行为语义：恢复既有部署目标；不改变同步脚本流程、SSH 用户、端口或远端部署逻辑。
- 风险：低。该改动只还原已知可用的线上目标。

# 当前变更：桌面端离线课程包临时服务

## 当前用户要求

- 实现 Task 2：Desktop Temporary Package Server。
- 新增 token-gated 临时 HTTP server，服务 Task 1 生成的真实 `course-package/` 目录。
- `OfflineCoursePackageSession.root` 必须指向 materialized package root，不是原始视频输入目录。
- 只修改 `tools/offline_course_package_server.py`、`tests/test_offline_course_package_server.py`、`docs/current-change.md`。
- 按 TDD 执行、运行指定测试并提交。

## 根因判断

- 移动端需要从桌面端下载已物化课程包中的 manifest 声明文件。
- 临时服务不能信任任意 URL path 或目录中文件，必须以 manifest 声明路径作为下载白名单。
- manifest 本身仍需启动前调用 `validate_course_package_manifest()`，避免无效包绕过 Task 1 校验。
- `session.root` 必须和 manifest 声明文件闭合；缺文件时应启动失败，而不是等下载时才 404。
- Range 请求需要确定性返回 206 或 416，不能把解析错误暴露为未处理异常。
- 非 Range 视频下载不能一次性读入内存，需要按固定 chunk 流式写出。

## 修改前判断

- 本任务新增 `tools/` 下独立桌面临时服务，不改变现有后端 FastAPI、包生成接口、移动端、UI、部署配置或数据库。
- 最小干净路径：复用 `validate_course_package_manifest()`，从 manifest 生成允许下载路径集合，再用 `root.resolve()` 和 `relative_to()` 确认文件位于包根目录内。
- 不应做：二维码、UI、字幕工具入口、移动端下载、兼容旧目录结构、直接服务目录中所有文件。
- 不需要跨模块重构。

## 本次实际修改文件

- `tools/offline_course_package_server.py`：新增 `OfflineCoursePackageSession`、`OfflineCoursePackageServer`、`start_offline_course_package_server()`、metadata/manifest/files GET endpoint、token 校验、过期校验、manifest path 白名单、root 边界检查、声明文件启动校验和 chunked 文件下载处理。
- `tests/test_offline_course_package_server.py`：新增临时服务行为测试，使用 `build_course_package()` 生成真实课程包目录后验证 metadata、manifest、Range 下载、完整文件下载、缺 token、过期 session、未声明文件、路径穿越、无效 Range 和缺失声明文件启动失败。
- `docs/current-change.md`：覆盖为当前 Task 2 工作单。

## 行为语义是否变化

- 新增 Python 桌面端临时 HTTP 服务能力。
- 所有 endpoint 都要求 `Authorization: Bearer <token>`。
- session 过期后返回 410。
- manifest 未声明的文件路径返回 404。
- Range 合法时返回 206 和 `Content-Range`；无效 Range 返回 416。
- 完整文件下载和 Range 下载都按固定 chunk 写出，不一次性读取整段视频文件。
- 启动时会校验 manifest 声明文件在 `session.root` 下真实存在。
- 未改变现有课程包生成、后端 API、移动端、UI、部署或数据库语义。

## 重构说明

- 未做跨模块重构。
- 仅在新增模块内提取 manifest 文件路径、总字节数、安全路径和 Range 解析 helper，避免 handler 中重复安全逻辑。

## 未修改内容

- 未修改 `tools/offline_course_package.py`，因为 Task 1 已提供真实课程包目录和 manifest 校验能力。
- 未实现二维码、UI、字幕工具入口或移动端。
- 未修改现有后端、前端、移动端、构建或部署文件。
- 未修改其它已有脏工作区文件。

## 影响范围

- 影响范围限定为 Python 离线课程包临时服务及其测试。
- 不影响公共 API、架构、部署、数据结构或 UI。
- 新增测试文件覆盖本任务服务行为。

## 当前风险点和不确定项

- 当前实现只使用 stdlib HTTP server，适合桌面端临时局域网传输，不作为生产公网服务。
- `base_url` 在默认 `0.0.0.0` 启动时使用 `127.0.0.1` 表示本机访问地址；局域网展示地址后续应由字幕工具入口按网卡地址生成，本任务未实现。

## 仍需用户确认的问题

- 无。

## 验证记录

- 已按 TDD 先运行 `python -m pytest tests/test_offline_course_package_server.py -q`，在生产模块不存在时失败，符合预期 RED。
- 已重新运行：`python -m pytest tests/test_offline_course_package_server.py -q`
  - 结果：12 passed。
- 已重新运行：`python -m pytest tests/test_offline_course_package.py tests/test_offline_course_package_server.py -q`
  - 结果：32 passed, 1 skipped。skip 为既有 Task 1 symlink 测试在当前 Windows 环境不允许创建 symlink。
- 已重新运行：`git diff --check -- tools/offline_course_package_server.py tests/test_offline_course_package_server.py docs/current-change.md`
  - 结果：通过；仅有 Git LF/CRLF 转换提示。
- 已运行：`rg "from __future__ import annotations" tools/offline_course_package_server.py tests/test_offline_course_package_server.py`
  - 结果：无命中。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

# 当前变更：React Native 移动端 App MVP

## 当前用户要求

- 开始做 Android 和 iPhone 上的 App 软件。
- 技术路线已确认使用 React Native。
- React Native 基座已确认使用 Expo-managed。
- 第一版 MVP 已确认只连接线上后端，先做登录、项目列表、学习/复习、视频播放。
- 第一版不做手机本机文件导入，也不做离线缓存。

## 根因

- 当前仓库已有 FastAPI 后端、React Web 前端和 Windows Tauri 桌面端，但没有 Android / iOS 移动端工程。
- 移动端是新客户端边界，不能把现有 Web UI 当作 WebView 包壳，也不能把 Windows Tauri 的 `NATIVE_LOCAL` 本机路径语义直接迁移到手机端。
- 移动端 MVP 应复用现有公开 API 语义，而不是新增临时移动端专用协议或兼容层。

## 本次实际修改文件

- `docs/mobile-client.md`
  - 新增移动端客户端长期边界文档，记录当前阶段、功能边界、数据流、认证边界、媒体边界、工程边界和验证边界。
- `docs/superpowers/specs/2026-05-18-mobile-client-design.md`
  - 新增已确认的移动端 MVP 设计文档，用于后续实施计划。
- `docs/superpowers/plans/2026-05-18-mobile-client-mvp.md`
  - 新增移动端 MVP 实施计划，明确 `mobile/` 工程、API client、认证、页面、媒体播放、复习和验证任务。
- `docs/current-change.md`
  - 覆盖并维护当前移动端任务工作单。

## 行为语义是否变化

- 当前只修改文档，不改变运行时代码行为。
- 已确认未来移动端 MVP 的产品边界：真实 React Native App，默认连接 `https://plm.xuebao.chat/api`，不做 WebView 包壳。
- 已生成实施计划，但尚未创建 `mobile/` 工程。

## 重构说明

- 当前未做代码重构。
- 文档层面把移动端与 Web/Tauri 客户端边界分开，避免后续实现时引入错误复用或隐式兼容。

## 未修改内容

- 未创建 `mobile/` 工程；需要用户选择执行方式后再进入脚手架。
- 未修改后端 API；当前 MVP 应先尝试复用现有公开 API。
- 未修改 `frontend/`；移动端不直接复用 React DOM UI。
- 未修改 Windows Tauri 桌面端；桌面端 `NATIVE_LOCAL` 语义不迁移到手机端。
- 未修改 README；当前阶段尚未新增可运行移动端工程，README 入口应在工程创建后同步。

## 影响范围

- API：无当前代码影响。
- 架构：新增已确认的移动端客户端边界文档。
- 部署：无当前代码影响。
- 数据结构：无影响。
- UI：无当前代码影响。
- 测试：无当前代码影响。

## 当前风险点和不确定项

- React Native 对现有 cookie 会话的承载方式可能与浏览器不同；如果实现阶段发现阻塞，必须暂停确认认证策略。
- Expo 默认媒体能力可能无法覆盖所有现有播放描述符；不能用未确认 fallback 隐藏该限制。
- 未来如果要共享 Web API 类型，需要先确认共享包边界，不能直接从移动端引用 Vite 或 React DOM 专用模块。

## 仍需用户确认的问题

- 请用户选择实施计划执行方式：Subagent-Driven 或 Inline Execution。

## 验证记录

- 已运行未决占位扫描，未发现需要补齐的占位内容。
- 已运行 `git diff --check` 检查文档变更，未发现 whitespace error。
- 当前只做文档变更，尚未运行构建或测试。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

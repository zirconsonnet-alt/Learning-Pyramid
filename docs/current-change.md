# 当前变更：Android 移动端预检与 smoke 清单

## 当前用户要求

- 在 Android Studio 下载完成前，先做移动端预检和 Android smoke 测试清单。

## 根因

- 移动端 MVP 已可运行，但真实 Android 模拟器/真机 smoke 尚未执行。
- 当前机器还没有可用 `adb`，因此只能先完成本地工程预检、Metro 状态确认和测试清单准备。

## 本次实际修改文件

- `docs/mobile-android-smoke-checklist.md`
  - 新增 Android 模拟器 smoke 清单、预检结果、启动方式、风险观察和结果记录项。
- `docs/current-change.md`
  - 覆盖为当前预检任务工作单。

## 行为语义是否变化

- 无。仅文档和预检记录。

## 重构说明

- 无。

## 未修改内容

- 未修改代码、依赖、测试、后端 API、部署、数据库结构或移动端构建配置。
- `pnpm --dir mobile lint` 曾触发 Expo 自动安装 ESLint，但该副作用已撤销；未保留 lint 依赖或配置。

## 影响范围

- API：无影响。
- 架构：无影响。
- 部署：无影响。
- 数据结构：无影响。
- UI：无影响。
- 测试：无测试代码变化。

## 当前风险点和不确定项

- `adb` 当前不可用，需 Android Studio 安装完成后复查。
- 真实 Android 原生播放器是否能稳定携带 Cookie header 播放受保护媒体，仍需模拟器 smoke 验证。

## 仍需用户确认的问题

- 无。

## 验证记录

- 已运行：`pnpm --dir mobile test`，通过，9 个测试套件、27 个测试通过。
- 已运行：`pnpm --dir mobile typecheck`，通过。
- 已运行：`pnpm --dir mobile exec expo --version`，结果 `55.0.30`。
- 已运行：`pnpm --dir mobile exec expo install --check`，通过，输出 `Dependencies are up to date`。
- 已运行：`git diff --check -- docs/mobile-android-smoke-checklist.md docs/current-change.md mobile/package.json mobile/pnpm-lock.yaml`，通过；仅有 Git 换行转换 warning，无 whitespace error。
- 已运行：`adb devices` 探测，结果 `adb: not found`。
- 已运行：`http://localhost:8081/status` 探测，结果 `packager-status:running`。
- 已运行：`pnpm --dir mobile lint`，未通过；Expo 尝试自动安装 ESLint 后仍报 `Cannot find module 'eslint'`。该命令不作为当前验收项，自动依赖改动已撤销。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

# 当前变更：移动端 Expo 工程骨架

## 当前用户要求

- 在 `mobile/` 创建 Expo-managed React Native 移动端工程骨架。
- 默认后端为 `https://plm.xuebao.chat/api`，但本任务只创建骨架。
- 第一版不做手机本机文件导入、离线缓存、WebView 包壳。
- 本任务只允许修改或创建 `mobile/`、`.gitignore`、`docs/current-change.md`。
- 完成后只暂存并提交上述允许范围。

## 根因

- 仓库已有后端、Web 前端和 Windows Tauri 桌面端，但缺少独立 Android / iOS 移动端工程。
- 移动端 MVP 需要独立 React Native 客户端边界，不能复用 WebView 包壳或桌面端本机文件语义。

## 本次实际修改文件

- `mobile/`
  - 使用 `npx create-expo-app@latest mobile --template default@sdk-55 --no-install --no-agents-md` 创建 Expo SDK 55 默认工程骨架。
  - 通过 pnpm 安装模板依赖、移动端运行时依赖和测试依赖。
  - 新增 `mobile/global.d.ts`，为模板中的 CSS module 引用提供 TypeScript 声明。
- `.gitignore`
  - 只追加缺失的移动端忽略项：`mobile/node_modules/`、`mobile/.expo/`、`mobile/dist/`、`mobile/coverage/`、`mobile/*.tsbuildinfo`。
- `docs/current-change.md`
  - 覆盖为当前 Task 1 工作单，记录本次修改范围、行为语义、验证结果和风险。

## 行为语义是否变化

- 当前只新增移动端工程骨架和忽略规则，不改变现有后端、Web 前端、桌面端或部署行为。
- 未实现登录、API client、视频播放、离线缓存、本机文件导入或 WebView 包壳。
- `mobile/global.d.ts` 只影响 TypeScript 对 `*.module.css` 的类型识别，不改变运行时行为。

## 重构说明

- 未做代码重构。
- 本任务是新增独立移动端工程边界，不改变现有模块抽象。

## 未修改内容

- 未修改后端、`frontend/`、`desktop/`、测试文件、部署配置或长期文档。
- 未更新 README 和 `docs/mobile-client.md`，因为用户本轮明确限制只允许修改 `mobile/`、`.gitignore`、`docs/current-change.md`。

## 影响范围

- API：无影响。
- 架构：新增 `mobile/` 独立 Expo 工程骨架。
- 部署：无影响。
- 数据结构：无影响。
- UI：仅包含 Expo 模板默认移动端 UI 骨架，未做业务 UI。
- 测试：安装测试依赖，未新增测试用例。

## 当前风险点和不确定项

- `pnpm --dir mobile add -D ...` 成功但输出 peer dependency 警告：
  - `react-test-renderer 19.2.6` 期望 `react@^19.2.6`，模板当前为 `react 19.2.0`。
  - `jest-expo` 的子依赖 `jest-watch-typeahead` 提示 peer 范围不包含当前安装的 `jest 30.4.2`。
- 上述警告来自指定安装命令和 Expo SDK 55 当前依赖解析结果，本任务未自行替换技术路线或引入兼容层。
- 首次运行 `pnpm --dir mobile exec tsc --noEmit` 时，模板内 `src/components/animated-icon.web.tsx` 无法识别已有 `animated-icon.module.css` 的类型声明；已用 `mobile/global.d.ts` 做最小类型配置修复。

## 仍需用户确认的问题

- 无。

## 验证记录

- `Test-Path mobile`：输出 `False`。
- `npx create-expo-app@latest mobile --template default@sdk-55 --no-install --no-agents-md`：成功创建工程；未生成嵌套 `.git`，未生成 `mobile/AGENTS.md`。
- `pnpm --dir mobile install`：成功。
- `pnpm --dir mobile add zod @tanstack/react-query`：成功。
- `pnpm --dir mobile exec expo install expo-secure-store expo-video`：成功。
- `pnpm --dir mobile add -D jest jest-expo @types/jest @testing-library/react-native react-test-renderer`：成功，带 peer dependency 警告。
- `pnpm --dir mobile exec expo --version`：成功，输出 `55.0.30`。
- `pnpm --dir mobile exec tsc --noEmit`：首次失败，报错 `Cannot find module './animated-icon.module.css' or its corresponding type declarations.`；新增 `mobile/global.d.ts` 后重新运行成功。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

# 当前变更：移动端测试与基础组件

## 当前用户要求

- 执行移动端 MVP 计划 Task 2。
- 为 `mobile/` 配置 Jest 测试入口和 `test` / `typecheck` 脚本。
- 先写失败测试并确认因基础组件不存在而失败。
- 实现基础 React Native 组件和最小 `renderWithProviders` 测试入口。
- 只修改 Task 2 允许范围内文件，不触碰工作区无关改动。
- 运行指定验证并只暂存 Task 2 文件提交。

## 根因

- Task 1 只创建了 Expo 工程和测试依赖，尚未配置 Jest、测试脚本、基础组件和移动端测试工具入口。
- 组件测试引用的 `AppButton`、`EmptyState`、`LoadingState` 还不存在，因此 RED 测试应先失败。

## 本次实际修改文件

- `mobile/package.json`
  - 保留现有脚本，新增 `test` 为 `jest --runInBand`。
  - 新增 `typecheck` 为 `tsc --noEmit`。
- `mobile/jest.config.js`
  - 使用 `jest-expo` preset。
  - 限定 `__tests__/**/*.test.ts(x)` 作为测试匹配范围。
- `mobile/__tests__/components.test.tsx`
  - 新增基础组件 smoke 测试，验证 loading、empty、button 文案可渲染。
- `mobile/src/components/Screen.tsx`
  - 新增移动端页面容器，基于 `SafeAreaView`、`ScrollView`、`View`。
- `mobile/src/components/LoadingState.tsx`
  - 新增简洁 loading 状态，基于 `ActivityIndicator` 和 `Text`。
- `mobile/src/components/EmptyState.tsx`
  - 新增简洁 empty 状态。
- `mobile/src/components/AppButton.tsx`
  - 新增基础按钮，使用 `Pressable`，不使用 Web DOM。
- `mobile/src/components/AppTextInput.tsx`
  - 新增基础输入框，使用 React Native `TextInput`。
- `mobile/src/test/renderWithProviders.tsx`
  - 新增最小测试渲染入口，当前不引入 provider。
- `docs/current-change.md`
  - 覆盖为当前 Task 2 工作单，记录红绿测试、影响范围和污染风险。

## 行为语义是否变化

- 移动端新增测试运行入口和基础 UI 组件。
- 不改变后端、Web 前端、桌面端、部署、数据结构或 API 行为。
- 不新增移动端业务流程、认证策略、媒体策略或路由语义。

## 重构说明

- 未做重构。
- 本次是新增 Task 2 基础设施和组件，没有调整已有模板组件或现有抽象边界。

## 未修改内容

- 未修改 `.gitignore`、`README.md`、`docs/mobile-client.md`、`mobile/pnpm-lock.yaml`、`mobile/scripts/reset-project.js`。
- 未修改现有 Expo 模板组件、页面、hooks、assets 或其他无关文件。
- 未删除 `reset-project` 脚本；它是已知中风险项，但本任务明确不处理删除生成文件相关内容。

## 影响范围

- API：无影响。
- 架构：无影响，保持 `mobile/` 独立客户端边界。
- 部署：无影响。
- 数据结构：无影响。
- UI：新增移动端基础组件，不接入现有页面。
- 测试：新增移动端组件测试、Jest 配置和测试辅助入口。

## 当前风险点和不确定项

- 当前未接入 provider，`renderWithProviders` 仅封装 `@testing-library/react-native` 的 `render`；后续任务如引入 Query/Auth provider，应在对应任务中显式扩展。
- 工作区存在大量与本任务无关的未提交改动，本任务不触碰、不暂存、不回滚。

## 仍需用户确认的问题

- 无。

## 验证记录

- RED：`pnpm --dir mobile test -- components.test.tsx` 失败，原因是 `Cannot find module '../src/components/AppButton'`。
- GREEN：`pnpm --dir mobile test -- components.test.tsx` 通过，2 个测试通过。
- GREEN：`pnpm --dir mobile typecheck` 通过。
- GREEN：`git diff --check -- mobile/package.json mobile/jest.config.js mobile/src/components mobile/src/test mobile/__tests__/components.test.tsx docs/current-change.md` 通过；仅有 Git 换行提示，无 whitespace error。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

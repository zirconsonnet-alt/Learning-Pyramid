# 当前变更：移动端认证状态与登录页

## 当前用户要求

- 继续 React Native 移动端 App MVP。
- 当前执行 Task 5：实现认证状态、session cookie 存储桥和登录页。
- 不修改后端认证策略，不新增 token/custom header。

## 根因

- 移动端已有通用 API client 和领域 API client，但还没有本地认证状态边界。
- React Native 需要把内存中的 `plm_session` 与 `expo-secure-store` 持久化连接起来，否则登录态无法在 App 重启后恢复。
- Expo 模板首页仍是示例入口，不是 LearningPyramid 移动端登录入口。

## 本次实际修改文件

- `mobile/__tests__/auth-provider.test.tsx`
  - 新增认证状态测试，覆盖无 session 恢复为 signedOut，以及登录后持久化 session cookie。
- `mobile/__tests__/login-screen.test.tsx`
  - 新增登录页提交邮箱和密码的测试。
- `mobile/src/auth/sessionStorage.ts`
  - 新增 `expo-secure-store` session cookie 持久化边界。
- `mobile/src/auth/sessionCookieStore.ts`
  - 新增内存 session cookie store，供同步 API client 读取。
- `mobile/src/auth/AuthProvider.tsx`
  - 新增认证上下文，负责恢复 session、登录、退出和持久化 cookie。
  - 恢复 `/auth/me` 请求失败时回到 signedOut，不清除本地 cookie；明确返回 null 时清理失效 cookie。
- `mobile/src/screens/LoginScreen.tsx`
  - 新增移动端登录页。
- `mobile/src/components/Screen.tsx`
  - 改用 `react-native-safe-area-context` 的 `SafeAreaView`，避免登录页测试触发 React Native 弃用 warning。
- `mobile/src/app/_layout.tsx`
  - 将 Expo 根入口接入 `QueryClientProvider`、`AuthProvider` 和移动端 API client。
- `mobile/src/app/index.tsx`
  - 替换模板首页为登录/已登录入口。
- `docs/current-change.md`
  - 更新当前工作单。

## 行为语义是否变化

- 移动端新增认证状态管理和登录入口。
- 登录成功后必须拿到 `plm_session` 才会持久化并进入 signedIn，避免隐藏认证不可用问题。
- 已有 session 恢复失败不会卡在 loading。
- 不改变后端 API、认证协议、部署、数据结构或 Web/Tauri 行为。

## 重构说明

- 未做跨模块重构。
- 仅替换移动端模板入口，使 App 首屏进入 LearningPyramid 认证流。

## 未修改内容

- 未修改后端认证策略。
- 未新增 token、自定义认证 header 或移动端专用认证协议。
- 未删除 Expo 模板的 reset 脚本和其它模板文件。
- 未修改 Web、桌面端、部署或数据结构。
- 未更新长期文档；当前仍处实现阶段，长期文档将在移动端预览可运行后统一同步。

## 影响范围

- API：不改变后端 API，仅移动端开始调用 auth client。
- 架构：移动端新增认证上下文和 session 存储边界。
- 部署：无影响。
- 数据结构：无影响。
- UI：移动端首屏从 Expo 模板页变为 LearningPyramid 登录/已登录入口。
- 测试：新增认证和登录页测试。

## 当前风险点和不确定项

- 真实 React Native 运行环境是否稳定暴露 `Set-Cookie` 仍需后续登录/logout smoke 验证；如果不通，必须暂停确认认证策略。
- 当前 signedIn 首页只是认证入口占位，完整学科/材料列表在 Task 6 实现。

## 仍需用户确认的问题

- 无。

## 验证记录

- RED：`pnpm --dir mobile test -- auth-provider.test.tsx login-screen.test.tsx` 失败，摘要：`../src/auth/AuthProvider` 和 `../src/screens/LoginScreen` 不存在。
- GREEN：首次实现后 `pnpm --dir mobile test -- auth-provider.test.tsx login-screen.test.tsx` 失败，原因是测试未模拟 API client 登录后写入内存 cookie；同时登录页测试触发 `SafeAreaView` 弃用 warning。
- 已运行：`pnpm --dir mobile test -- auth-provider.test.tsx login-screen.test.tsx`，通过，2 个测试套件、3 个测试通过。
- 已运行：`pnpm --dir mobile typecheck`，通过。
- 已运行：`git diff --check -- mobile/src/auth mobile/src/screens/LoginScreen.tsx mobile/src/app/_layout.tsx mobile/src/app/index.tsx mobile/src/components/Screen.tsx mobile/__tests__/auth-provider.test.tsx mobile/__tests__/login-screen.test.tsx docs/current-change.md`，通过；仅有 Git 换行转换 warning，无 whitespace error。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

# 当前变更：放宽手机端个人中心卡片宽度

## 当前用户要求

- 手机端个人中心卡片视觉上太窄，需要让卡片更接近手机屏幕宽度。

## 根因

- App shell 使用 Tailwind `container`，项目配置里 `container.padding` 为 `2rem`。
- 手机端顶栏和正文主容器因此左右各保留 32px 外边距，个人中心卡片内部又有自己的内容留白，叠加后卡片视觉宽度被明显压窄。
- 这不是单个卡片组件宽度错误，而是手机端 shell 容器 gutter 过大。

## 本次实际修改文件

- `frontend/src/shell/AppShell.tsx`
  - 将 app 顶栏和正文主容器的手机端横向 padding 从默认 32px 覆盖为 16px。
  - `sm` 及以上仍保留原 32px padding，桌面端视觉不变。
- `frontend/tests/e2e/app-load.spec.ts`
  - 扩展个人中心手机端布局测试，断言 390px 视口下顶栏和正文卡片使用 16px gutter，并且不产生横向滚动。
- `docs/current-change.md`
  - 覆盖为当前变更工作单。

## 行为语义变化

- 手机端 app 内页面可用横向空间增加，个人中心卡片更接近铺满手机屏幕。
- 顶栏和正文仍保持左右对齐。
- 桌面端、平板 `sm` 及以上断点、导航结构、账号逻辑、学习统计数据和 API 不变。

## 重构说明

- 未做重构。
- 这是 App shell 手机端容器 gutter 的局部样式修正。

## 未修改内容

- 未修改 Tailwind 全局 `container.padding`，避免影响首页和其他独立布局。
- 未修改个人中心卡片内部业务结构、字段、账号编辑逻辑。
- 未通过 `overflow-x: hidden` 掩盖布局问题。
- 未改动后端、部署配置、数据结构或 API。

## 影响范围

- UI：app shell 内所有登录后页面的手机端顶栏和正文横向 gutter。
- 测试：`app-load.spec.ts` 中个人中心手机端布局断言。
- 不影响桌面端、API、架构、部署、数据结构或账号业务语义。

## 当前风险与不确定项

- 此调整作用于 app shell 内登录后页面的手机端公共容器，不只限个人中心；这是为了保持顶栏与正文所有页面一致对齐。

## 本次发现但未自动修复的问题

- 文件路径：`frontend/src/shell/AppShell.tsx`
- 问题：`eslint react-hooks/exhaustive-deps` 提示既有番茄钟记录 effect 缺少 `hasAccessiblePomodoroProjectRef` 依赖。
- 风险等级：低
- 是否影响本次改动：否

## 验证记录

- 已运行：`pnpm -C frontend exec eslint src/shell/AppShell.tsx tests/e2e/app-load.spec.ts`，0 个错误；仍有 1 个与本次改动无关的既有 hook dependency warning：`AppShell.tsx` 的番茄钟 effect 缺少 `hasAccessiblePomodoroProjectRef` 依赖。
- 已运行：`git diff --check -- docs/current-change.md frontend/src/shell/AppShell.tsx frontend/tests/e2e/app-load.spec.ts frontend/src/views/profile/ProfilePage.tsx frontend/src/views/profile/profileStats.ts`，通过；仅提示这些工作区文件后续可能被 Git 转换为 CRLF。
- 已运行：`LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=4201 pnpm -C frontend exec playwright test tests/e2e/app-load.spec.ts --project=chromium --grep "profile mobile layout"`，通过；验证 390px 手机视口下顶栏和个人中心卡片使用 16px gutter，且不产生横向滚动。
- 已运行：`pnpm -C frontend build`，通过；仍有既有 chunk size warning。
- 已运行：`LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=4202 pnpm -C frontend exec playwright test tests/e2e/app-load.spec.ts --project=chromium`，9 个测试通过。

## 仍需用户确认的问题

- 无。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

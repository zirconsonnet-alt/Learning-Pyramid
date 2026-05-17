# 当前变更：修复首页手机端轮播横滑

## 当前用户要求

- 手机端首页轮播左右箭头已经去掉，但实际没有相应的左右滑动切换。
- 需要让手机端通过左右滑动切换轮播内容。

## 根因

- 轮播组件虽然监听了 `pointerdown` / `pointermove` / `pointerup`，但轮播触控区域没有声明 `touch-action`。
- 真实手机浏览器会把横向手势作为默认触控滚动/导航候选处理，可能触发 `pointercancel` 或让组件拿不到完整的 move/up 序列。
- 原 e2e 测试通过手动派发 `PointerEvent` 验证，绕过了浏览器真实触屏事件调度，因此没有覆盖真实手机手势。

## 本次实际修改文件

- `frontend/src/views/home/HomePage.tsx`
  - 在非鼠标 pointer down 时捕获当前 pointer。
  - 在 pointer up / cancel 时释放 pointer capture。
  - 保持原有左右滑动阈值和切换方向不变。
- `frontend/src/index.css`
  - 为 `.lp-showcase-carousel-viewport` 增加 `touch-action: pan-y`，允许页面纵向滚动，同时把横向手势交给轮播组件处理。
- `frontend/tests/e2e/app-load.spec.ts`
  - 手机端首页轮播测试增加 `touch-action` 断言。
  - 将原先手动构造 `PointerEvent` 的测试改为通过 Chromium CDP 派发真实 touch start / move / end 事件。
- `docs/current-change.md`
  - 覆盖为当前变更工作单。

## 行为语义变化

- 手机端首页轮播在隐藏左右箭头后，可以通过横向滑动切换上一组/下一组内容。
- 手机端页面仍可纵向滚动。
- 桌面端鼠标悬停暂停、左右箭头、自动轮播和轮播内容不变。

## 重构说明

- 未做重构。
- 这是首页轮播手机端触控事件边界的局部修正。

## 未修改内容

- 未恢复手机端左右箭头。
- 未改为横向滚动容器。
- 未通过 `overflow-x: hidden` 掩盖布局问题。
- 未修改轮播数据、图片、文案、后端、API、部署配置或数据结构。
- 未修改长期架构文档，因为本次是局部前端 UI 交互修正，不改变架构、部署或数据模型。

## 影响范围

- UI：首页手机端轮播触控交互。
- 测试：`app-load.spec.ts` 首页手机端轮播断言。
- 不影响 API、架构、部署、后端数据结构或好友排行榜。

## 当前风险与不确定项

- `touch-action: pan-y` 会把轮播区域横向手势交给组件处理；纵向滚动保持浏览器默认行为。
- 真实设备的浏览器差异主要集中在 pointer/touch 事件调度，已通过真实 touch 事件测试覆盖 Chromium 行为。

## 本次发现但未自动修复的问题

- 暂无。

## 验证记录

- 已运行：`pnpm -C frontend exec eslint src/views/home/HomePage.tsx tests/e2e/app-load.spec.ts`，通过。
- 已运行：`git diff --check -- docs/current-change.md frontend/src/views/home/HomePage.tsx frontend/src/index.css frontend/tests/e2e/app-load.spec.ts`，通过；仅提示这些工作区文件后续可能被 Git 转换为 CRLF。
- 已运行：`LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=4207 pnpm -C frontend exec playwright test tests/e2e/app-load.spec.ts --project=chromium --grep "home mobile carousel"`，通过；覆盖真实 touch 左滑到下一组、右滑回上一组。
- 已运行：`pnpm -C frontend build`，通过；仍有既有 chunk size warning。
- 已运行：`LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=4208 pnpm -C frontend exec playwright test tests/e2e/app-load.spec.ts --project=chromium`，11 个测试通过。

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

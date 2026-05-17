# 当前变更：首页移除手机端提示框并修正移动导航弹层

## 当前用户要求

- 把手机端首页的“此产品推荐在电脑上使用 / 视频相关功能无法在手机端使用”提示框去掉。
- 修正手机端项目内三横线下拉框歪斜、导致页面可以左右滑动的问题。
- 修正手机端个人中心顶栏和正文卡片不对齐、页面可左右滑动的问题。

## 根因

- 首页 `HomePage` 单独渲染了 `lp-showcase-mobile-notice` 提示节点。
- `index.css` 在手机断点下把该节点显示为提示框，导致手机端首页顶栏下方出现额外提示。
- 项目内移动导航弹层定位在三横线按钮自身上，弹层宽度接近视口宽度；当按钮距离视口左边有偏移时，弹层向右溢出，造成视觉歪斜和横向滚动。
- 个人中心正文使用 CSS grid，grid item 默认最小尺寸会受内部内容影响；学习视图选择器、账户信息卡内头像/昵称/按钮行在手机端形成较大的最小内容宽度，把正文卡片撑到顶栏容器之外，导致横向滚动。

## 本次实际修改文件

- `frontend/src/views/home/HomePage.tsx`
  - 删除首页移动端电脑使用提示框节点。
- `frontend/src/index.css`
  - 删除 `lp-showcase-mobile-notice` 的基础和手机端样式。
- `frontend/tests/e2e/app-load.spec.ts`
  - 将首页移动端提示框测试更新为手机端和桌面端都不显示该提示。
  - 增加项目内手机端移动导航弹层边界测试，防止弹层再次导致横向滚动。
  - 增加个人中心手机端布局测试，覆盖正文卡片不超过顶栏边界且页面不产生横向滚动。
- `frontend/src/shell/AppShell.tsx`
  - 将项目内移动导航弹层改为相对整行 header 定位，宽度限制在 header 行内。
- `frontend/src/views/profile/ProfilePage.tsx`
  - 允许个人中心根 grid、section、aside 和卡片在手机端收缩。
  - 调整学习视图筛选 select 的最小宽度只在 `sm` 及以上生效。
  - 调整账户信息头像区在手机端改为纵向布局，并降低手机端头像固定尺寸。
- `docs/current-change.md`
  - 覆盖为当前变更工作单。

## 行为语义变化

- 手机端首页不再显示“此产品推荐在电脑上使用 / 视频相关功能无法在手机端使用”提示框。
- 手机端项目内三横线下拉框不再从按钮位置向右溢出。
- 手机端个人中心正文卡片和顶栏左右边界对齐，不再产生横向滚动。
- 桌面端原本不显示该框，行为不变。
- 首页导航、路由、认证、页面主体业务语义和后端行为不变。

## 重构说明

- 未做重构。
- 这是删除单一首页提示 UI、修正移动端布局边界的局部变更。

## 未修改内容

- 未修改 FAQ 文档中“建议电脑端使用”的长期说明。
- 未修改首页主体内容、导航、会员、字幕工具入口。
- 未通过 `overflow-x: hidden` 掩盖横向溢出问题。
- 未修改后端 API、数据结构、部署配置或公共路由。

## 影响范围

- UI：首页手机端。
- UI：项目内手机端顶栏移动导航弹层。
- UI：个人中心手机端正文卡片布局。
- 测试：首页加载 e2e 中关于该提示框、项目内移动导航弹层边界和个人中心手机端横向滚动的断言。
- 不影响 API、架构、部署、数据结构或页面主体业务内容。

## 当前风险与不确定项

- 无当前阻塞风险。

## 本次发现但未自动修复的问题

- 文件路径：`frontend/src/shell/AppShell.tsx`
- 问题：`eslint react-hooks/exhaustive-deps` 提示既有番茄钟记录 effect 缺少 `hasAccessiblePomodoroProjectRef` 依赖。
- 风险等级：低
- 是否影响本次改动：否

## 验证记录

- 已运行：`rg -n "此产品推荐在电脑上使用|电脑端使用提示|视频相关功能无法在手机端使用|lp-showcase-mobile-notice" frontend\src frontend\tests`，源码中不再存在首页提示节点或样式，测试中仅保留“不显示该提示”的断言。
- 已运行：`pnpm -C frontend exec eslint src/shell/AppShell.tsx src/views/home/HomePage.tsx src/views/profile/ProfilePage.tsx tests/e2e/app-load.spec.ts`，0 个错误；仍有 1 个与本次改动无关的既有 hook dependency warning。
- 已运行：`pnpm -C frontend build`，通过；仍有既有 chunk size warning。
- 已运行：`pnpm -C frontend exec playwright test tests/e2e/app-load.spec.ts --project=chromium`，8 个测试通过；新增测试覆盖 390px 手机视口下项目内移动导航弹层不越出视口、个人中心正文卡片不超过顶栏边界，且页面不产生横向滚动。
- 已运行：`LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=4183 pnpm -C frontend exec playwright test tests/e2e/app-load.spec.ts --project=chromium --grep "profile mobile layout"`，通过；验证 390px 手机视口下个人中心正文卡片不超过顶栏边界且页面 `scrollWidth` 不超过视口宽度。
- 已运行：`git diff --check -- docs/current-change.md frontend/src/index.css frontend/src/shell/AppShell.tsx frontend/src/views/home/HomePage.tsx frontend/src/views/profile/ProfilePage.tsx frontend/tests/e2e/app-load.spec.ts`，通过；仅提示这些工作区文件后续可能被 Git 转换为 CRLF。

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

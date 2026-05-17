# 当前变更：压缩首页手机端内容卡片

## 当前用户要求

- 手机端去掉 `ABC`、`1/2/3/4` 这些占位置且信息量低的标记。
- 手机端“方法”三张卡片压到同一行，并改成紧凑版。
- 手机端“改变，从现在开始”下面的引导入口压到两个一行。
- 手机端“会员”里的两个套餐卡压到同一行，减少套餐卡右侧空白和纵向浪费。

## 根因

- 首页多个内容区在 `max-width: 1080px` 断点统一退回单列，手机端没有为“方法”“引导”“会员套餐”提供更紧凑的信息密度。
- 方法卡的 `A/B/C` 和引导卡的 `1/2/3/4` 在手机端占用显著空间，但不增加实际信息量。
- 会员套餐卡默认是两列，但 `max-width: 760px` 断点又覆盖成单列，导致截图里的套餐区域纵向过高、右侧空间利用不足。

## 本次实际修改文件

- `frontend/src/views/home/HomePage.tsx`
  - 为方法区栅格增加 `lp-showcase-method-grid` class，便于手机端精确压缩，不影响其它三列区域。
  - 为引导区栅格增加 `lp-showcase-onboarding-grid` class，便于手机端两列展示。
- `frontend/src/index.css`
  - 手机端方法区改为三列紧凑卡片，隐藏 `A/B/C` 标记，压缩标题、正文、图片和内距。
  - 手机端引导区改为两列，隐藏 `1/2/3/4` 标记，压缩 ribbon、标题、正文和按钮。
  - 手机端会员套餐保持两列，压缩价格卡内距、字号和间距。
- `frontend/tests/e2e/app-load.spec.ts`
  - 新增手机端首页内容区布局测试，覆盖方法三列、引导两列、套餐两列、标记隐藏和无横向溢出。
- `docs/current-change.md`
  - 覆盖为当前变更工作单。

## 行为语义变化

- 手机端首页“方法”三张卡片同一行展示。
- 手机端首页“改变，从现在开始”四个入口每行两个。
- 手机端首页“会员”两个套餐卡同一行展示。
- 手机端隐藏方法卡 `A/B/C` 和引导卡 `1/2/3/4`。
- 桌面端布局和所有链接、文案、价格、会员入口逻辑不变。

## 重构说明

- 未做重构。
- 仅增加两个语义化 class 用于约束首页特定区域的手机端样式。

## 未修改内容

- 未修改首页数据、价格、文案、图片资产或链接。
- 未修改会员页、项目内页面、后端、API、部署配置或数据结构。
- 未通过 `overflow-x: hidden` 掩盖布局问题。
- 未修改长期架构文档，因为本次是局部前端响应式 UI 调整，不改变架构、部署或数据模型。

## 影响范围

- UI：首页手机端“方法”“改变，从现在开始”“会员套餐”区域。
- 测试：`app-load.spec.ts` 首页手机端布局断言。
- 不影响 API、架构、部署、后端数据结构。

## 当前风险与不确定项

- 方法三列在 390px 视口下单卡宽度约 114px，正文已限制为两行，长文案会被截断以换取更紧凑布局。
- 会员套餐两列在窄屏下价格区域更紧凑，仍保留套餐名、价格、单位和备注。

## 本次发现但未自动修复的问题

- 暂无。

## 验证记录

- 已运行：`pnpm -C frontend exec eslint src/views/home/HomePage.tsx tests/e2e/app-load.spec.ts`，通过。
- 已运行：`git diff --check -- docs/current-change.md frontend/src/views/home/HomePage.tsx frontend/src/index.css frontend/tests/e2e/app-load.spec.ts`，通过；仅提示这些工作区文件后续可能被 Git 转换为 CRLF。
- 已运行：`LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=4209 pnpm -C frontend exec playwright test tests/e2e/app-load.spec.ts --project=chromium --grep "home mobile content sections"`，通过；覆盖方法三列、引导两列、会员套餐两列、标记隐藏和无横向溢出。
- 已运行：`LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=4210 pnpm -C frontend exec playwright test tests/e2e/app-load.spec.ts --project=chromium --grep "home mobile carousel"`，通过。
- 已运行：`pnpm -C frontend build`，通过；仍有既有 chunk size warning。
- 已运行：`LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=4211 pnpm -C frontend exec playwright test tests/e2e/app-load.spec.ts --project=chromium`，12 个测试通过。

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

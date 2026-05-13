# Current Change

更新时间：2026-05-13

## 1. 当前用户要求

- 工作台里雪豹问答框上线后仍被视频底部控制栏遮挡，需要按真实根因修正并同步上线。

## 2. 本次实际修改文件

- `frontend/src/views/workbench/WorkbenchPage.tsx`
- `frontend/tests/e2e/workbench-review.spec.ts`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `WorkbenchPage.tsx`：把承载桌宠的右侧 `xl:sticky` 侧栏提升到同一父层级里的 `xl:z-30`，避免桌宠被 sticky 父级 stacking context 困住。
- `workbench-review.spec.ts`：把桌宠问答层级回归改成 1365px 桌面视口，并用真实重叠点 `elementFromPoint` 确认问答框在视频控制栏上方。
- `docs/current-change.md`：覆盖为本次线上遮挡回归修复工作单。

## 4. 行为语义是否变化

- 否。
- 只调整桌宠所在右侧 sticky 父级的层级顺序，按钮、视频控制栏、hover / focus-within 展开、固定展开、AI 问答和数据流都不变。

## 5. 是否做了重构，以及为什么

- 否。
- 这次只做父级 stacking context 的局部层级修复，不抽公共组件，不改变组件归属。

## 6. 未修改哪些相关内容，以及为什么

- 未继续提高 `.plm-desktop-pet` 的 `z-index`，因为真实根因不是子元素数值，而是它被右侧 sticky 父级 stacking context 限制。
- 未改视频底部控制栏结构，因为遮挡来自跨父层级排序，不是视频栏布局。
- 未改 `DesktopPet` 的 hover / pin 逻辑，因为交互行为本身没有问题。
- 未改工作台 AI 接口、会员 gating、LLM 配置 gating 和字幕上下文读取，因为这次问题只在视觉层级。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，桌面视口下雪豹问答框在真实重叠区域高于视频控制栏。
- 测试：是，补充真实重叠点 e2e 回归断言。

## 8. 当前风险点和不确定项

- 右侧 sticky 父级在桌面视口提升为 `xl:z-30`，会压过中间视频控制栏，但仍被外层 `main` 的 stacking context 限制在应用顶栏下方。

## 9. 仍需用户确认的问题

- 无。

## 10. 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

## 11. 验证状态

- 已先跑红灯：临时移除右侧 sticky 父级的 `xl:z-30` 后运行 `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=5177 pnpm --dir frontend test:e2e -- workbench-review.spec.ts -g "workbench pet assistant stays above the video control bar"`，用例在真实重叠点失败，顶部元素属于视频控制栏。
- 恢复修复后同一用例：`LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=5177 pnpm --dir frontend test:e2e -- workbench-review.spec.ts -g "workbench pet assistant stays above the video control bar"`，1 passed。
- 相关工作台 e2e：`LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=5177 pnpm --dir frontend test:e2e -- workbench-review.spec.ts`，5 passed。
- `pnpm --dir frontend build`：通过；仍有既有 `hls` chunk 大于 500 kB 的 warning。
- `git diff --check`：通过；仅输出 Git 将 LF 转 CRLF 的工作区提示。

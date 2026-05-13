# Current Change

更新时间：2026-05-13

## 1. 当前用户要求

- 学科卡片和项目卡片头部视觉不一致，需要统一标题/meta 间距。
- 工作台里雪豹问答框被视频底部控制栏遮挡，需要修正层级。

## 2. 本次实际修改文件

- `frontend/tests/e2e/subject-project.spec.ts`
- `frontend/src/views/subjects/SubjectDashboardPage.tsx`
- `frontend/tests/e2e/workbench-review.spec.ts`
- `frontend/src/index.css`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `subject-project.spec.ts`：在既有卡片一致性回归里补充标题栈间距和 meta 行外边距断言，防止项目卡片再次偏离学科卡片。
- `SubjectDashboardPage.tsx`：把项目卡片标题栈改成和学科卡片一致的 `space-y-2`，并移除 meta 行单独的 `mt-1`。
- `workbench-review.spec.ts`：补充桌宠问答层级回归，确认桌宠浮层高于视频控制栏。
- `index.css`：把桌宠浮层 `z-index` 提到视频 chrome 之上，并保留原来的 hover 展开语义。
- `docs/current-change.md`：覆盖为本次卡片样式和桌宠层级修复工作单。

## 4. 行为语义是否变化

- 否。
- 只调整项目卡片标题/meta 的视觉间距和桌宠浮层的层级顺序，按钮、跳转、删除、选中态和数据流都不变。
- 桌宠问答仍然保持 hover / focus-within 展开语义，AI 问答能力、LLM 配置判断和提问流程不变。

## 5. 是否做了重构，以及为什么

- 否。
- 这次只做项目卡片头部局部 class 对齐和桌宠浮层局部层级修复，不抽公共组件，不扩大作用域。

## 6. 未修改哪些相关内容，以及为什么

- 未改学科卡片，因为它已经是本次卡片样式基准。
- 未改图标语义，因为学科和项目类型使用不同图标是信息含义差异，不是样式分叉。
- 未改视频底部控制栏结构，因为问题是桌宠浮层层级，不是视频栏布局。
- 未改工作台 AI 接口、会员 gating、LLM 配置 gating 和字幕上下文读取，因为这次问题只在视觉层级。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，项目卡片标题与 meta 行间距和学科卡片一致；工作台桌宠问答浮层会高于视频控制栏。
- 测试：是，补充 e2e 回归断言。

## 8. 当前风险点和不确定项

- 胶囊宽度仍会随文案长度自然变化，例如 `1 个项目` 和 `网课` 不会强行等宽。
- 图标图形仍按实体语义不同展示：学科是书本，项目按项目类型展示。
- 桌宠浮层提到 `z-index: 25`，会压过视频控制栏，但仍低于应用顶栏的 `z-40`。

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

- 已先跑卡片红灯：`LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=5177 pnpm --dir frontend test:e2e -- subject-project.spec.ts -g "subject and project cards share title meta and selected styles"`，当前因为项目卡片标题栈缺少 `space-y-2` 而失败。
- 修复后卡片聚焦用例：`LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=5177 pnpm --dir frontend test:e2e -- subject-project.spec.ts -g "subject and project cards share title meta and selected styles"`，1 passed。
- 已先跑红灯：把桌宠 `z-index` 临时还原为 18 后运行 `LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=5177 pnpm --dir frontend test:e2e -- workbench-review.spec.ts -g "workbench pet assistant stays above the video control bar"`，用例因桌宠层级 18 未高于视频控制栏 20 而失败。
- 修复后同一用例：`LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=5177 pnpm --dir frontend test:e2e -- workbench-review.spec.ts -g "workbench pet assistant stays above the video control bar"`，1 passed。
- 相关 e2e 文件：`LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER=1 LEARNINGPYRAMID_FRONTEND_E2E_PORT=5177 pnpm --dir frontend test:e2e -- subject-project.spec.ts workbench-review.spec.ts`，10 passed。
- `pnpm --dir frontend build`：通过；仍有既有 `hls` chunk 大于 500 kB 的 warning。
- `git diff --check`：通过；仅输出 Git 将 LF 转 CRLF 的工作区提示。

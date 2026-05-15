# 当前变更：首页与用户指南 FAQ 调整

## 当前用户要求

- 首页 FAQ 和用户指南 FAQ 插入第一条：
  - 如何长期稳定使用？
  - 使用电脑浏览器访问即可
- 首页去掉“为什么佣金不立即生效？”这一条，并保持 4 条 FAQ。
- 用户指南左上角增加一个卡片，放首页的四个指引按钮。

## 根因

- 首页 FAQ 在 `frontend/src/views/home/HomePage.tsx` 中维护，当前 4 条里包含“为什么佣金不立即生效？”。
- 用户指南 FAQ 来自 `docs/guide-faq.md`。
- 首页四个指引按钮原本只定义在首页组件内部，用户指南无法干净复用。

## 本次实际修改文件

- `frontend/src/ui/guideWalkthrough/guideEntryLinks.ts`
  - 新增四个首页指引按钮的共享静态数据。
- `frontend/src/views/home/HomePage.tsx`
  - 首页指引按钮改为读取共享数据。
  - 首页 FAQ 新增“如何长期稳定使用？”并移除“为什么佣金不立即生效？”，保持 4 条。
- `frontend/src/views/guide/GuidePage.tsx`
  - 用户指南左侧顶部新增“快速开始”卡片，复用首页四个指引按钮。
- `docs/guide-faq.md`
  - 在 FAQ 正文第一条插入“如何长期稳定使用？”。
- `frontend/tests/e2e/app-load.spec.ts`
  - 新增 E2E 覆盖首页 FAQ 数量、首页佣金 FAQ 移除、指南 FAQ 首条和指南入口按钮。
- `docs/current-change.md`
  - 覆盖为当前任务工作单。

## 行为语义变化

- 首页 FAQ 用户可见内容变化：新增长期稳定使用说明，移除佣金生效说明，数量仍为 4。
- 用户指南 FAQ 第一条变为长期稳定使用说明。
- 用户指南左侧新增四个引导入口，跳转目标与首页四个指引按钮一致。

## 重构说明

- 做了局部重构：将首页四个指引按钮抽成共享静态数据，避免首页和用户指南重复维护同一组入口。
- 未改变引导流程、路由、API 或后端行为。

## 未修改内容

- 未修改会员、佣金、支付、提现业务逻辑。
- 未删除用户指南中既有 FAQ 条目。
- 未改动后端、数据库、部署配置。
- 未调整首页 FAQ 样式和整体布局结构。

## 影响范围

- UI：影响首页 FAQ 和用户指南左侧栏。
- 文档：影响用户指南 FAQ 和当前变更工作单。
- 测试：新增前端 E2E 断言。
- 不影响 API、架构、部署、数据结构。

## 当前风险与不确定项

- 四个指引入口仍指向原有 walkthrough 路由；本次不改变这些引导流程的权限或前置条件。
- `pnpm --dir frontend lint` 当前仍因本次未修改的 `frontend/src/views/pomodoro/PomodoroWallpaperBackdrop.tsx` 既有 lint error 失败。
- `app-load.spec.ts` / `navigation.spec.ts` 多 worker 并行运行时，`vite preview` 在本机出现 `insufficient memory` / heap out of memory；同一套测试串行通过。

## 验证记录

- 已运行：`pnpm --dir frontend exec playwright test tests/e2e/app-load.spec.ts -g "home and guide surface"`，结果通过。
- 已运行：`pnpm --dir frontend build`，结果通过；保留既有大 chunk 警告。
- 已运行：`pnpm --dir frontend exec playwright test tests/e2e/app-load.spec.ts --workers=1`，结果 5 个测试通过。
- 已运行：`pnpm --dir frontend exec playwright test tests/e2e/navigation.spec.ts --workers=1`，结果 4 个测试通过。
- 已运行：`pnpm --dir frontend lint`，结果失败；失败点在本次未修改的 `PomodoroWallpaperBackdrop.tsx` 既有 lint error，另有既有 hooks warning。
- 已运行：`pnpm --dir frontend exec playwright test tests/e2e/app-load.spec.ts` 和 `tests/e2e/navigation.spec.ts` 默认并行模式，结果失败；失败表现为预览服务内存崩溃，不是业务断言失败。

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

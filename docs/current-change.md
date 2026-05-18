# 当前变更：移动端工作台展示屏

## 当前用户要求

- 当前执行 mobile native workbench Task 4：新增移动端工作台 presentational screen。
- 展示层需要通过 props 渲染当前学习对象、媒体播放器、目录、已有复述点、复述点草稿、复习门禁和提交按钮。
- 不接 API、不做路由、不新增持久化、不修改后端协议。

## 根因

- 移动端已有学习对象详情、播放器、复习队列和草稿模型，但项目入口缺少学习优先工作台展示层。
- 需要一个只消费上层状态和回调的屏幕组件，把这些已存在能力组合成移动端工作台 UI。

## 本次实际修改文件

- `mobile/__tests__/mobile-workbench-screen.test.tsx`
  - 新增工作台展示屏行为测试，覆盖 active learning object、mocked media player、existing recall point、draft inputs、目录选择、复习门禁、播放时间回调、添加草稿回调和 review queue loading 提交保护。
- `mobile/src/screens/MobileWorkbenchScreen.tsx`
  - 新增 `MobileWorkbenchScreen` 和 `MobileWorkbenchScreenProps`。
  - 使用 `Screen`、`LoadingState`、`EmptyState`、`AppButton`、`AppTextInput`、`LearningMediaPlayer` 组合展示工作台。
  - 通过 props 注入所有数据和回调，提交前用 `getIncompleteDraftReason` 和复习门禁状态保护 `onSubmitDrafts`。
- `docs/current-change.md`
  - 更新为当前 Task 4 工作单。

## 行为语义是否变化

- 是。移动端现在有可复用的工作台展示屏，能渲染当前学习内容、媒体、目录、复述点、草稿、复习门禁和提交动作。
- UI 可以触发目录选择、打开复习入口、播放时间回传、添加草稿、删除草稿、编辑草稿和提交草稿回调。
- 提交学习会在无草稿、复习队列加载中、存在队列头复习任务、草稿不完整或提交中时被阻止。

## 重构说明

- 无跨模块重构。
- 仅新增展示屏组件，复用已有基础组件、播放器、富内容纯文本转换和草稿校验函数。

## 未修改内容

- 未修改 API client、后端 API、数据库、部署、Web/Tauri 工作台或移动端路由。
- 未新增持久化、网络请求、fallback、shim、legacy、临时兼容逻辑或特殊分支。
- 未修改既有测试去适配错误实现。

## 影响范围

- API：无变化。
- 架构：移动端仍独立于 `frontend/`，本次新增组件为 props-driven presentational screen。
- 部署：无影响。
- 数据结构：无影响。
- UI：新增移动端工作台展示层。
- 测试：新增 `mobile/__tests__/mobile-workbench-screen.test.tsx`。

## 当前风险点和不确定项

- 无已知风险点。

## 仍需用户确认的问题

- 无。

## 验证记录

- RED 已运行：`pnpm --dir mobile test -- mobile-workbench-screen.test.tsx`
  - 结果：失败，符合预期；原因为 `../src/screens/MobileWorkbenchScreen` 模块不存在。
- GREEN 已运行：`pnpm --dir mobile test -- mobile-workbench-screen.test.tsx`
  - 结果：通过，1 个测试套件、5 个测试通过。
- GREEN 已运行：`pnpm --dir mobile typecheck`
  - 结果：通过。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

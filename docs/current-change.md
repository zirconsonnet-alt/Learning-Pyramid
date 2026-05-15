# 当前变更：首页手机端使用提示

## 当前用户要求

- 手机端打开首页时提示用户：
  - 此产品推荐在电脑上使用。
  - 视频相关功能无法在手机端使用。

## 根因

- 首页当前没有针对手机端访问的能力边界提示。
- 产品的视频学习、目录绑定、快捷录入等核心路径依赖电脑浏览器体验，手机端直接访问首页时缺少明确预期。

## 本次实际修改文件

- `frontend/src/views/home/HomePage.tsx`
  - 在首页 header 后增加手机端使用提示。
- `frontend/src/index.css`
  - 通过小屏媒体查询显示提示条，桌面端隐藏。
- `frontend/tests/e2e/app-load.spec.ts`
  - 增加 E2E 覆盖手机尺寸显示提示、桌面尺寸不显示提示。
- `docs/guide-faq.md`
  - 同步 FAQ 中“如何长期稳定使用？”的说明。
- `docs/current-change.md`
  - 覆盖为当前任务工作单。

## 行为语义变化

- 手机尺寸访问首页时，会在首页顶部显示电脑端使用提示。
- 桌面尺寸访问首页不显示该提示。
- 不改变登录、注册、会员、FAQ、导览或项目入口行为。

## 重构说明

- 未做重构。
- 实现使用现有首页组件与全局样式，不新增设备检测状态或公共抽象。

## 未修改内容

- 未修改视频播放、目录绑定、字幕工具或学习工作台功能逻辑。
- 未在其他页面增加手机端提示。
- 未增加弹窗、强制拦截或跳转。

## 影响范围

- UI：影响首页小屏显示。
- 文档：影响用户指南 FAQ 和当前变更工作单。
- 测试：新增首页移动端 E2E 断言。
- 不影响 API、架构、部署、数据结构。

## 当前风险与不确定项

- 当前按 CSS 小屏宽度显示提示，不做 user agent 判断；平板或窄桌面窗口也会看到该提示。

## 验证记录

- 已运行：`pnpm --dir frontend exec playwright test tests/e2e/app-load.spec.ts -g "home shows a mobile device notice" --workers=1`，修复前失败，修复后通过。
- 已运行：`pnpm --dir frontend exec eslint src/views/home/HomePage.tsx tests/e2e/app-load.spec.ts`，结果通过。
- 已运行：`pnpm --dir frontend exec playwright test tests/e2e/app-load.spec.ts --workers=1`，结果 6 个测试通过。
- 已运行：`pnpm --dir frontend build`，结果通过；保留既有大 chunk 警告。
- 已运行：`pnpm --dir frontend lint`，结果失败；失败点为本次未修改的 `frontend/src/views/pomodoro/PomodoroWallpaperBackdrop.tsx` 既有 lint error，另有既有 hooks warning。

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

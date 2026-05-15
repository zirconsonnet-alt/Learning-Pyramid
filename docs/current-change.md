# 当前变更：复述点详情页引用标签改为题面文本

## 当前用户要求

- 复述点详情页里的引用按钮不要使用悬停展示。
- 按钮标签直接写对应复述点的题面文本。
- 题面超长时截断，并在末尾加 `...`。

## 根因

- `frontend/src/views/recallPoints/RecallPointPage.tsx` 的引用列表已经按引用 ID 查询了被引用复述点，但渲染标签仍硬编码为“引用 1 / 引用 2”。
- 现有页面没有把已查询到的引用复述点题面用于按钮可见文本。

## 本次实际修改文件

- `frontend/src/views/recallPoints/RecallPointPage.tsx`
  - 引用按钮标签改为引用复述点题面的纯文本。
  - 超过固定长度的题面文本截断为 `...` 结尾。
  - 图片题面不显示 asset id，只显示文本标签。
- `frontend/tests/fixtures/test-data.ts`
  - E2E mock 数据增加一条被引用复述点。
- `frontend/tests/fixtures/mock-api.ts`
  - E2E mock API 支持读取被引用复述点。
  - 增加测试选项，允许单条用例临时给主复述点挂引用关系。
- `frontend/tests/e2e/review-detail-entry-links.spec.ts`
  - 增加复述点详情页引用按钮显示题面文本的回归测试。
- `docs/how-to-study-review.md`
  - 同步说明引用链接会在详情页以被引用复述点题面显示。
- `docs/current-change.md`
  - 覆盖为当前任务工作单。

## 行为语义变化

- 复述点详情页“引用”区域的链接可见文本从序号标签变为被引用复述点题面摘要。
- 题面包含 Markdown 或 LaTeX 时，按钮显示原始纯文本，不做渲染。
- 题面只有图片时，按钮显示“图片题面”。

## 重构说明

- 未做跨模块重构。
- 只在详情页组件内新增局部格式化函数，因为该需求只影响该页面的引用链接标签。

## 未修改内容

- 未修改复述点引用的数据结构、API、后端查询逻辑。
- 未修改录入框和视频全屏录入里的引用选择器。
- 未增加悬停 tooltip、Markdown/LaTeX 渲染预览或图片缩略图。

## 影响范围

- UI：影响复述点详情页“引用”区域。
- 测试：影响前端 E2E mock 数据和一条详情页回归用例。
- 文档：影响学习复习文档和当前变更工作单。
- 不影响 API、架构、部署、数据结构。

## 当前风险与不确定项

- 按钮文本截断阈值当前由前端固定常量控制，用户只指定了超长截断，没有指定字符数。
- 引用复述点详情查询完成前，按钮会短暂显示“题面读取中...”；查询没有结果时显示“题面不可用”。

## 验证记录

- 已运行：`pnpm --dir frontend exec playwright test tests/e2e/review-detail-entry-links.spec.ts -g "recall point detail names reference links" --workers=1`，修复前失败，修复后通过。
- 已运行：`pnpm --dir frontend build`，结果通过；保留既有大 chunk 警告。
- 已运行：`pnpm --dir frontend exec eslint src/views/recallPoints/RecallPointPage.tsx tests/e2e/review-detail-entry-links.spec.ts tests/fixtures/test-data.ts tests/fixtures/mock-api.ts`，结果通过。
- 已运行：`pnpm --dir frontend exec playwright test tests/e2e/review-detail-entry-links.spec.ts --workers=1`，结果 6 个测试通过。
- 已运行：`$env:LEARNINGPYRAMID_FRONTEND_E2E_PORT='4174'; pnpm --dir frontend exec playwright test tests/e2e/detail-summary-cards.spec.ts --workers=1`，结果 8 个测试通过。
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

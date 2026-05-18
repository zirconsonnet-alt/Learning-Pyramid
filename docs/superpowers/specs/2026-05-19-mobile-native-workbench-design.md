# 移动端原生工作台设计

## 背景

当前 `mobile/` Expo App 已实现第一版独立 React Native MVP，但真实 Expo Go 测试显示学习主流程仍不可用。根因不是移动网页适配问题，而是当前移动端只覆盖了很窄的浏览闭环，没有把桌面/网页工作台的核心学习语义搬到原生移动端。

本阶段继续保持已确认的原生 React Native 路线，不改为 WebView。桌面/网页工作台是功能语义来源，移动端只做设备交互适配，不重新定义学习流程。

## 目标

- 让手机端进入材料项目后可以直接学习，而不是停留在学习对象列表。
- 用原生 React Native 实现“学习优先”的移动工作台。
- 复用现有后端 API、scoped project 语义和 `learning task` 提交语义。
- 支持看媒体、选目录、录入复述点草稿、提交学习任务、处理复习门禁。
- 保持第一批实现足够小，不把 Web 工作台全部面板一次搬进移动端。

## 非目标

- 不做 WebView 包壳。
- 不新增移动端专用后端协议。
- 不新增单条 `POST /recall-points` API。
- 不实现手机本机文件导入、离线缓存或本机字幕扫描。
- 不实现图片复述点、复述点引用、AI 助手、层推进、学习统计、已有复述点编辑/删除。
- 不改变 Web/Tauri 工作台行为。

## 设计原则

移动端原生工作台以桌面/网页工作台为权威语义：

- 目录用于选择当前学习对象。
- 当前学习对象决定播放器内容和复述点锚点。
- 新复述点先进入本地草稿。
- 多条草稿一起提交为一个 `learning task`。
- 队列非空时形成复习门禁，先完成复习再继续提交学习。

移动端只改变交互呈现：

- 主屏优先显示当前学习对象和媒体。
- 目录通过移动端入口展开，不常驻三栏。
- 复述点录入使用短表单和草稿列表，不复刻 Web 富文本编辑器。
- 第一批仅支持文本题面和文本答案。

## 页面结构

### 项目入口

当前 `mobile/src/app/project/[subjectId]/[scopedProjectId].tsx` 从学习对象列表页升级为移动工作台入口。

进入项目后：

- 加载学习对象节点。
- 选择一个当前 leaf 节点：
  - 优先使用用户本次会话已选节点。
  - 否则选择第一个 leaf 节点。
  - 如果没有 leaf 节点，显示空状态。
- 顶部显示当前节点标题。
- 当前节点下显示播放器。
- 目录入口用于切换当前节点。
- 复述点区域显示当前节点已有复述点和本地草稿。
- 复习入口用于处理当前 review queue。

### 目录

目录继续消费现有 `learning-object-nodes`。

第一批只需要：

- 展示容器和 leaf 的扁平顺序。
- leaf 可点击切换当前学习对象。
- 当前 leaf 有明确选中状态。
- container 只作为结构行，不提供树编辑能力。

### 播放器

播放器继续消费现有 playback descriptor。

第一批支持：

- `SERVER_FS` / `BAIDU_NETDISK` 且 URL 可由 Expo 播放器直接访问的媒体。
- `NATIVE_LOCAL`、`BROWSER_LOCAL`、`MANUAL` 显示明确不可播放状态。
- 播放器向工作台上报当前播放时间毫秒值。

不支持的媒体源不得用 fallback 或临时 URL 改写隐藏。

### 复述点草稿

新增复述点使用移动端本地草稿。

每条草稿包含：

- `localId`
- `questionText`
- `answerText`
- `instanceId`
- `position`
- `createdAt`
- `updatedAt`

点击“记复述点”时：

- 必须有当前 leaf 节点和 `instanceId`。
- 读取播放器当前时间。
- 生成 `position = t=<毫秒>`。
- 新建一条草稿。

提交前要求：

- 至少一条草稿。
- 每条草稿题面非空。
- 每条草稿答案非空。
- 每条草稿有 `instanceId` 和 `position`。
- 复习队列为空。

### 学习任务提交

移动端新增 API client 能力：

- `POST /subjects/{subjectId}/projects/{scopedProjectId}/learning-tasks`

请求体沿用 Web 工作台：

```json
{
  "title": "当前学习对象标题",
  "items": [
    {
      "question": [{ "kind": "TEXT", "text": "题面" }],
      "answer": [{ "kind": "TEXT", "text": "答案" }],
      "anchor": { "instanceId": "i1", "position": "t=12345" },
      "references": []
    }
  ]
}
```

实际 rich content 结构必须使用仓库现有 `RichContentSchema` 可解析的文本结构，不能发明移动端专用格式。

提交成功后：

- 清空当前学习对象草稿。
- 重新拉取 `review-queue`、当前 `learning-object-recall-points`、项目 `recall-points` 和 `learning-object-nodes` 查询。
- 保持当前学习对象不变。

### 复习门禁

工作台加载 review queue。

如果 `queue.headId` 存在：

- 复述点草稿可以保留，但禁止提交学习任务。
- 主操作提示用户先进入复习。
- 复习页面继续使用现有 `ReviewQueueScreen` 和 `review task` 提交流程。

本阶段不改变复习算法或后端队列语义。

## 数据流

```text
Mobile Workbench
  -> list learning object nodes
  -> select current leaf node
  -> get playback descriptor by instanceId
  -> list recall points by learning object node
  -> get review queue
  -> create local recall drafts
  -> submit drafts as learning task
  -> invalidate and refetch affected queries
```

所有 project-scoped 请求继续使用 `{subjectId, scopedProjectId}`。移动端不能保存或推断后端内部 project id。

## 状态边界

第一批移动端草稿状态只在 App 内存中保存。关闭 App 或刷新 Metro 后草稿丢失可以接受，因为本阶段目标是补齐学习主流程，不引入新的本地持久化协议。

如果后续要持久化草稿，需要单独确认：

- 存储介质；
- 跨账号隔离；
- 项目和节点 key；
- 过期和清理策略。

## UI 边界

移动端 UI 保持克制：

- 不使用桌面三栏布局。
- 不增加装饰性卡片、说明段落或复杂统计块。
- 主屏顺序为：当前学习对象、播放器、操作入口、复述点/草稿。
- 目录和复习入口是明确操作，不占据主学习空间。

卡片只用于独立实体，例如草稿项、已有复述点或不可播放状态。

## 测试策略

实施计划必须使用 TDD。

优先覆盖：

- `learning task` API client 使用正确 scoped path 和 body。
- 草稿创建时从当前播放时间生成 `t=<毫秒>`。
- 队列非空时禁止提交学习任务。
- 工作台渲染当前 leaf 标题、播放器和复述点入口。
- 提交成功后清空草稿，并触发 `review-queue`、当前 `learning-object-recall-points`、`recall-points`、`learning-object-nodes` 的 query invalidation。

验证命令至少包括：

```powershell
pnpm --dir mobile test
pnpm --dir mobile typecheck
```

有 Android 设备或模拟器时，再执行 Expo Go smoke。

## 文档同步

实施时必须同步维护：

- `docs/current-change.md`
- `docs/mobile-client.md`

如果实现中发现现有 API 不足以按桌面语义提交学习任务，必须暂停确认，不能新增 fallback、shim、legacy 或移动端特殊分支。

## 风险

- Expo 原生播放器能否稳定携带 Cookie header 播放受保护媒体仍需真机验证。
- 当前移动端 rich content 只能先做文本；图片和引用如果后续补齐，需要与 Web 富文本语义对齐。
- 内存草稿不会跨 App 重启保留，这是本阶段有意边界，不应被误解为长期设计。

## 已确认决策

- 继续原生 React Native 路线。
- 采用学习优先布局。
- 第一批支持新增复述点，不支持编辑/删除已有复述点。
- 新增复述点自动绑定当前播放时间，使用 `t=<毫秒>`。
- 新增复述点沿用桌面/网页工作台的 `learning task` 提交语义。

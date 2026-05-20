# 离线课程包导入设计

## 背景

当前移动端工作台只能播放后端返回的在线 playback descriptor。桌面/字幕工具可以访问用户电脑上的本地视频并生成同目录字幕，但手机端不能离线持有这些视频。用户已确认下一阶段不是做“字幕收件箱”，而是做“电脑端生成字幕后，把视频、字幕和课程元数据作为离线课程包导入手机 App 私有课程库”。

这会改变既有移动端边界：移动端仍不扫描手机系统文件，也不写公共目录，但允许通过电脑端配对接收 App 托管的离线课程包。

## 目标

- 支持电脑端字幕工具把本地课程视频、字幕和元数据导入手机。
- 手机端通过扫码与电脑端临时局域网服务配对，由手机主动下载课程包。
- 离线课程包保存到移动端 App 私有目录，不写入手机公共文件夹。
- 离线课程包绑定线上 LearningPyramid 学科和 scoped project。
- 手机离线播放包内视频和字幕，但学习数据主干仍沿用线上项目语义。
- 支持选择性导入、空间检查、文件 hash 校验、失败重试、暂停/继续和删除管理。

## 非目标

- 不扫描手机系统文件。
- 不写手机公共目录。
- 不做公网中继或云端同步。
- 不读取百度网盘 App 缓存。
- 不建立独立于线上学科/项目的第二套本地课程系统。
- 不自动按文件名猜测视频和字幕绑定关系。
- 不改变 Web/Tauri 工作台学习数据语义。

## 已确认决策

- 采用“绑定线上项目”的方案。
- 线上 `{subjectId, scopedProjectId}` 是学习数据主干。
- 离线课程包是该线上项目的移动端本地素材源。
- 移动端本地课程库只管理 App 私有目录内的课程包。

## 产品模型

核心关系：

```text
Subject
  -> Scoped Project
    -> Online learning data
    -> Mobile offline course packages
```

离线课程包不是独立课程系统。它必须绑定到一个线上 subject/project。复述点、学习任务、复习、结构和统计仍归属该线上项目；本地包只提供视频、字幕、封面和与学习对象绑定所需的 manifest 元数据。

## 用户流程

### 电脑端字幕工具

1. 用户选择本地课程目录或视频集合。
2. 工具生成或刷新字幕。
3. 用户点击“导入到手机”或“生成手机学习包”。
4. 工具让用户选择目标线上学科/项目，或使用项目模式下已配置的目标。
5. 工具生成课程包 manifest 和文件清单。
6. 工具启动临时局域网 HTTP 服务。
7. 工具显示二维码和过期倒计时。

### 手机端

1. 用户在当前项目的项目设置或本地课程库入口点击“连接电脑”。
2. 手机扫码读取临时连接信息。
3. App 请求电脑端临时服务，展示待导入课程包。
4. 用户选择要导入的视频条目。
5. App 检查剩余空间。
6. App 下载 manifest、视频、字幕和封面。
7. App 校验 size 和 sha256。
8. App 将文件提交到 App 私有课程库。
9. App 将课程包绑定到当前线上项目。
10. 后续手机工作台可使用本地包播放视频和字幕。

## 连接协议

二维码载荷使用 JSON，经 URL-safe 编码后放入二维码。第一版不使用公网中继。

```json
{
  "kind": "learningpyramid.offlineCoursePackage",
  "version": 1,
  "url": "http://192.168.1.8:23456/session/abc",
  "token": "one-time-token",
  "expiresAt": "2026-05-20T12:10:00Z"
}
```

安全边界：

- token 一次性使用。
- 默认 10 分钟过期。
- 临时服务只暴露当前 session 的包清单和文件下载。
- 临时服务不暴露用户选择目录的任意文件浏览能力。
- 手机端必须显示电脑端包名、文件数量、总大小和目标项目，用户确认后才下载。

## Course Package Manifest

manifest 是手机端绑定视频、字幕、封面和线上项目的唯一依据。

```json
{
  "manifestVersion": 1,
  "packageId": "pkg_20260520_abcdef",
  "title": "默认网课材料",
  "createdAt": "2026-05-20T12:00:00Z",
  "subjectId": "subj_xxx",
  "scopedProjectId": "proj_xxx",
  "source": {
    "tool": "LearningPyramid-SubtitleTool",
    "version": "1.0.0"
  },
  "items": [
    {
      "itemId": "lesson_01",
      "title": "01. 第一讲",
      "order": 1,
      "learningObjectKey": "lesson_01",
      "video": {
        "path": "videos/01.mp4",
        "sizeBytes": 123456789,
        "sha256": "..."
      },
      "subtitle": {
        "path": "subtitles/01.zh-CN.vtt",
        "language": "zh-CN",
        "sizeBytes": 12345,
        "sha256": "..."
      },
      "cover": {
        "path": "covers/01.jpg",
        "sizeBytes": 23456,
        "sha256": "..."
      }
    }
  ]
}
```

第一版要求：

- `subjectId` 和 `scopedProjectId` 必须存在，或手机导入时必须明确绑定当前项目后再保存。
- `items[].video` 必须存在。
- 字幕和封面可选。
- 字幕绑定只信 manifest，不靠同名文件猜测。
- 每个文件必须带 `sizeBytes` 和 `sha256`。

## 手机端存储

App 私有目录建议结构：

```text
AppData/
  courses/
    subject_<subjectId>/
      project_<scopedProjectId>/
        package_<packageId>/
          manifest.json
          videos/
          subtitles/
          covers/
          download-state.json
```

状态文件只记录下载任务和校验状态，不作为学习数据主存储。

删除策略：

- 删除本地包只删除 App 私有目录内的视频、字幕、封面和本地 manifest。
- 不删除线上项目、学习对象、复述点、学习任务或复习记录。
- 如果某个学习对象当前只剩线上不可播放来源，工作台显示明确的素材缺失状态。

## 播放器接入

移动端 playback 来源新增本地素材概念：

```text
LOCAL_COURSE_PACKAGE
```

该来源只在移动端内部使用。它不要求后端能访问手机文件，也不把手机本地路径上传给后端作为公共素材源。

播放选择顺序建议：

1. 如果当前项目和学习对象存在已导入且校验通过的本地包条目，优先使用本地文件播放。
2. 否则使用后端 playback descriptor。
3. 如果二者都不可用，显示明确不可播放状态。

这不是 fallback 兼容层，而是用户显式导入的本地素材源。实现时需要在数据模型中把它表达为明确来源，避免隐藏在播放器里猜测。

## 下载任务模型

第一版需要任务队列：

- queued
- downloading
- paused
- verifying
- completed
- failed

每个文件任务记录：

- remote URL
- local temp path
- final path
- expected size
- expected sha256
- downloaded bytes
- status
- last error

下载规则：

- 下载到临时文件，校验通过后原子移动到最终路径。
- 支持 HTTP range 时使用断点续传。
- 不支持 HTTP range 时允许从头重试，但必须在 UI 中显示该限制。
- 单个文件失败不应污染已完成文件。
- 包级状态必须能从 `download-state.json` 恢复。

## 空间检查

导入前计算所选条目总大小，并检查 App 可用存储空间。

如果 Expo-managed 环境无法可靠拿到剩余空间，必须在实现阶段暂停确认是否引入原生能力或开发构建。不能通过忽略空间检查假装满足需求。

## 电脑端临时服务

服务职责：

- 提供 session metadata。
- 提供 manifest。
- 提供文件列表。
- 提供文件下载，支持 Range 请求。
- 根据 token 限制访问。
- 超时或用户取消时关闭服务。

服务不负责主动推送文件到手机，也不写手机目录。

## UI 入口

手机端入口建议放在两个位置：

- 项目设置：`离线课程包`
- 项目 Shell 的上下文菜单或更多菜单：`连接电脑`

不建议放在学习页正文首屏。离线包导入是素材管理操作，不是当前学习内容本身。

手机端本地课程库页面应提供：

- 当前项目已导入课程包列表。
- 每个包的大小、视频数、下载状态。
- 继续下载、暂停、重试、删除。
- 进入工作台播放。

## 数据与同步边界

线上仍是学习数据主干：

- subject/project 身份来自线上。
- 复述点和学习任务仍提交到线上项目。
- 手机本地课程包不创建新的 subject/project。
- 本地播放进度可以先保存在移动端，后续是否同步到线上需要单独确认。

离线状态下的学习记录不是第一版目标。如果后续要支持完全离线复述点录入和稍后同步，需要单独设计冲突、认证、队列和合并语义。

## 测试策略

第一版实施应覆盖：

- manifest schema 校验。
- 电脑端临时服务 token、过期、manifest 和 Range 下载。
- 手机端下载任务状态机。
- 空间不足时阻止下载。
- hash 不匹配时标记失败且不提交最终文件。
- 暂停、继续、失败重试。
- 删除本地包不删除线上学习记录。
- 播放器优先选择已校验本地包。

验证命令至少包括：

```powershell
pnpm --dir mobile test
pnpm --dir mobile typecheck
python -m pytest <offline-course-package-tests>
```

如果加入原生能力或开发构建，必须增加 Android 真机或模拟器 smoke。

## 文档更新

实施时必须同步：

- `docs/current-change.md`
- `docs/mobile-client.md`
- `README.md` 的字幕工具或移动端说明
- 如新增工具协议，可补充 `docs/offline-course-package.md`

旧边界应改为：

```text
移动端不扫描系统文件；
移动端不写公共目录；
移动端允许通过电脑端配对导入 App 托管的离线课程包；
离线课程包绑定线上学科和 scoped project；
手机本地播放只使用 App 私有课程库内已校验文件。
```

## 风险

- Expo-managed 对剩余空间查询、后台下载、大文件断点续传和本地视频 URI 的支持可能不足；如不足，需要确认是否转 development build 或引入原生模块。
- 局域网服务受防火墙和网络隔离影响；第一版应把连接失败提示做清楚，但不做公网中继。
- 本地包和线上学习对象的对应关系必须由 manifest 明确表达；如果当前项目结构无法稳定映射，需要先补 manifest 绑定策略，而不是靠文件名猜测。
- 大视频文件会占用手机存储；删除和空间提示必须是第一版能力，不应延期。

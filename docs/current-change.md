# 当前变更：离线课程包导入实现

## 当前用户要求

- 实现局域网离线课程包导入。
- 电脑端字幕工具提供视频、字幕和 manifest。
- 手机端下载到 App 私有课程库并绑定线上学科/项目。
- 用户确认采用方案 1：桌面端生成真实 `course-package/` 目录，manifest path 必须指向包内真实文件。
- 当前正在执行 Task 1：Python 离线课程包 manifest 和真实课程包目录生成。

## 根因判断

- 手机端离线学习需要完整课程素材包，不是单独字幕文件。
- 线上 `{subjectId, scopedProjectId}` 必须继续作为学习数据主干。
- manifest 的 `source` 是后续信任电脑端包来源和工具版本的顶层元数据，缺失时不能通过校验。
- manifest 的文件路径会被后续临时 HTTP 服务和移动端存储使用，必须在校验层限制为包内相对路径。
- manifest path 必须和桌面端生成的真实课程包目录闭合；否则 Task 2 server 按 `root / path` 下载会 404。
- 同名视频位于不同子目录时不能生成重复包内路径，否则后续下载会覆盖或取错文件。

## 修改前判断

- 先实现 manifest 和真实课程包目录生成，再接临时服务和移动端下载。
- 不扫描手机系统文件，不写手机公共目录，不做公网中继。
- 不使用原始路径映射、fallback、shim 或隐式兼容逻辑。
- 课程包输出目录不能位于输入课程目录内，避免再次扫描时把已生成包当源素材。
- 本次只修改 Python manifest/包生成模块、测试、当前工作单和离线课程包实现计划。

## 本次实际修改文件

- `tools/offline_course_package.py`：新增离线课程包 manifest 构建、真实课程包目录生成、视频枚举、sidecar 字幕/封面识别、文件 sha256 和 manifest 校验；补充 `source.tool` / `source.version` 必填校验、包内相对路径校验、重复文件路径校验、重复视频名路径去重、symlink 拒绝和输出目录边界检查。
- `tests/test_offline_course_package.py`：新增 manifest 构建、真实课程包目录写入、输出目录非空拒绝、输出目录位于输入目录内拒绝、项目身份校验、source 元数据校验、包内相对路径校验、重复文件路径拒绝、重复视频名路径去重、symlink 拒绝和 sha256 测试。
- `docs/superpowers/plans/2026-05-20-offline-course-package-import.md`：同步方案 1，后续 Task 2/3 必须使用真实课程包目录作为 server root。
- `docs/current-change.md`：覆盖为当前离线课程包实现工作单。

## 行为语义是否变化

- 新增 Python 能力：生成并校验离线课程包 manifest。
- 新增 Python 能力：把输入目录中的视频、字幕、封面复制到真实 `course-package/videos|subtitles|covers` 目录，并写入 `manifest.json`。
- manifest 校验会拒绝缺少 `source`、`source.tool` 或 `source.version` 的包。
- manifest 校验会拒绝绝对路径、反斜杠路径、`.` / `..` 路径段、空路径段、目录形态路径、重复文件路径，以及文件类型和顶层目录不匹配的路径。
- manifest 构建会用唯一 `itemId` 生成视频、字幕和封面的包内路径，避免不同子目录的同名文件冲突。
- manifest 构建会拒绝 symlink 文件，避免读取课程目录外内容。
- 课程包输出目录必须为空，且不能位于输入课程目录内。
- 未改变现有运行时用户流程。

## 重构说明

- 未做跨模块重构。
- 新增模块职责仍限定在桌面端课程包 manifest 和文件物化，不负责 HTTP 服务、二维码、移动端下载或播放器。

## 未修改内容

- 未修改 Web/Tauri 工作台学习语义。
- 未修改移动端 UI、播放器、下载逻辑。
- 未修改字幕工具入口。
- 未修改 API、数据库、部署配置。
- 未修改其它已有脏工作区文件。

## 影响范围

- 当前影响 Python 离线课程包 manifest 生成、校验和课程包目录生成。
- 后续 Task 2 server 将以真实课程包目录作为 `session.root`。

## 当前风险点和不确定项

- 大文件复制耗时和磁盘空间占用需要在字幕工具入口任务中给出清晰提示。
- 当前 Windows 环境无法创建 symlink 时，symlink 安全测试会跳过；非 Windows 或具备权限的环境会执行。
- Expo-managed 大文件下载、空间检查和本地视频 URI 需要在后续移动端任务验证。

## 仍需用户确认的问题

- 无。用户已确认采用真实课程包目录方案。

## 验证记录

- 已运行：`python -m pytest tests/test_offline_course_package.py -q`
  - 结果：19 passed, 1 skipped。skip 为当前 Windows 环境不允许创建 symlink。
- 已运行：`git diff --check -- tools/offline_course_package.py tests/test_offline_course_package.py docs/current-change.md docs/superpowers/plans/2026-05-20-offline-course-package-import.md`
  - 结果：通过；仅有 Git LF/CRLF 转换提示。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

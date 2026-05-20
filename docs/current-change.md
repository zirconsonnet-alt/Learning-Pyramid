# 当前变更：离线课程包导入实现

## 当前用户要求

- 实现局域网离线课程包导入。
- 电脑端字幕工具提供视频、字幕和 manifest。
- 手机端下载到 App 私有课程库并绑定线上学科/项目。
- 当前正在执行 Task 1：Python 离线课程包 manifest 模型。

## 根因判断

- 手机端离线学习需要完整课程素材包，不是单独字幕文件。
- 线上 `{subjectId, scopedProjectId}` 必须继续作为学习数据主干。
- manifest 的 `source` 是后续信任电脑端包来源和工具版本的顶层元数据，缺失时不能通过校验。

## 修改前判断

- 先实现纯 manifest 和临时服务，再接移动端下载与播放。
- 不扫描手机系统文件，不写公共目录，不做公网中继。
- 本次只补 Task 1 spec review 发现的 `source` 校验漏项，不碰移动端、服务或字幕工具入口。

## 本次实际修改文件

- `tools/offline_course_package.py`：新增离线课程包 manifest 构建、视频枚举、sidecar 字幕/封面识别、文件 sha256 和 manifest 校验；补充 `source.tool` / `source.version` 必填校验。
- `tests/test_offline_course_package.py`：新增 manifest 构建、项目身份校验、source 元数据校验和 sha256 测试。
- `docs/current-change.md`：覆盖为当前离线课程包实现工作单。

## 行为语义是否变化

- 新增 Python 纯函数能力，用于生成和校验离线课程包 manifest。
- manifest 校验现在会拒绝缺少 `source`、`source.tool` 或 `source.version` 的包。
- 未改变现有运行时用户流程。

## 重构说明

- 未做跨模块重构。
- 新增模块职责单一：只负责课程包 manifest 和文件哈希，不负责 HTTP 服务、二维码、移动端下载或播放器。

## 未修改内容

- 未修改 Web/Tauri 工作台学习语义。
- 未修改移动端 UI、播放器、下载逻辑。
- 未修改字幕工具入口。
- 未修改 API、数据库、部署配置。

## 影响范围

- 当前影响 Python 离线课程包 manifest 生成与校验。
- 后续任务会在此基础上实现临时局域网服务和移动端导入。

## 当前风险点和不确定项

- Expo-managed 大文件下载、空间检查和本地视频 URI 需要在后续移动端任务验证。

## 仍需用户确认的问题

- 无。

## 验证记录

- 已运行：`python -m pytest tests/test_offline_course_package.py -q`
- 已运行：`git diff --check -- tools/offline_course_package.py tests/test_offline_course_package.py docs/current-change.md`

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

# 当前变更：离线课程包导入实现

## 当前用户要求

- 实现局域网离线课程包导入。
- 电脑端字幕工具提供视频、字幕和 manifest。
- 手机端下载到 App 私有课程库并绑定线上学科/项目。

## 根因判断

- 手机端离线学习需要完整课程素材包，不是单独字幕文件。
- 线上 `{subjectId, scopedProjectId}` 必须继续作为学习数据主干。

## 修改前判断

- 先实现纯 manifest 和临时服务，再接移动端下载与播放。
- 不扫描手机系统文件，不写公共目录，不做公网中继。

## 本次实际修改文件

- `tools/offline_course_package.py`：新增纯 Python 离线课程包 manifest 构建、校验、视频枚举和文件 sha256 计算。
- `tests/test_offline_course_package.py`：新增 manifest 构建、项目身份必填校验、分块 sha256 计算测试。
- `docs/current-change.md`：更新为当前 Task 1 工作单。

## 行为语义是否变化

- 新增离线课程包 manifest 模型能力。
- 不改变现有 Web/Tauri 工作台、后端 API、移动端或字幕工具入口行为。

## 重构说明

- 未做重构；本次为独立新增工具模块和对应测试。

## 未修改内容

- 不改变 Web/Tauri 工作台学习语义。

## 影响范围

- 字幕工具、移动端本地课程库、移动端播放器、文档。

## 当前风险点和不确定项

- Expo-managed 大文件下载、空间检查和本地视频 URI 需要验证。

## 仍需用户确认的问题

- 无。

## 验证记录

- 已运行：`python -m pytest tests/test_offline_course_package.py -q`
  - RED：首次运行因 `ModuleNotFoundError: No module named 'tools.offline_course_package'` 失败，符合预期。
  - GREEN：实现模块后通过，`3 passed in 0.08s`。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

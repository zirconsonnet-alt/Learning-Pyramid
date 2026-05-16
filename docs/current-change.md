# 当前变更：移除课程助手提示词内部材料标识

## 当前用户要求

- 继续完成上次要求：从 LLM 提示词中去掉以下三类无意义内容：
  - `实例 ID`
  - `材料 ID`
  - `材料来源`

## 根因

- `frontend/src/ui/llm/courseAgent.ts` 在课程助手上下文中仍输出内部实例标识、材料标识和材料来源类型。
- 中文上下文复制文本和英文 `supplementalContext` 都存在同类字段；前者已有静态测试约束，后者此前没有测试守卫。

## 本次实际修改文件

- `frontend/src/ui/llm/courseAgent.ts`
  - 从 `buildCourseAgentContextText()` 的“基本信息”中移除 `实例 ID`、`材料 ID`、`材料来源`。
  - 从 `buildSupplementalContext()` 的 `Video learning context` 中移除 `Instance ID`、`Material ID`、`Material source kind`。
  - 保留 `instance` 和 `sourceKind` 在上下文包中的内部数据用途，不改变字幕加载、证据生成或调用方传参。
- `tests/test_course_agent_static.py`
  - 在已有中文上下文静态检查基础上，增加英文 LLM supplemental context 字段的禁止断言。
- `docs/current-change.md`
  - 覆盖为当前变更工作单。

## 行为语义变化

- 课程助手发给 LLM 的补充上下文不再包含内部实例 ID、材料 ID、材料来源类型。
- 桌宠“获取上下文”生成的可复制文本不再包含这些内部定位字段。
- 不改变用户问题、节点标题、播放位置、当前帧、复述点上下文、相关字幕或证据片段。

## 重构说明

- 未做重构。
- 本次是 prompt 文本内容清理和静态守卫补齐，不改变模块边界。

## 未修改内容

- 未修改字幕选择、字幕搜索、证据生成、图片输入、LLM 请求接口或后端 API。
- 未修改 `CourseAgentContextPackage` 暴露的内部字段，避免牵动调用方和现有数据流。
- 未修改长期文档；本次只是移除无意义 prompt 字段，不改变架构、部署或用户文档中的稳定行为说明。

## 影响范围

- UI/LLM：课程助手的 LLM supplemental context 和桌宠上下文复制文本。
- 测试：课程助手静态测试新增英文字段守卫。
- 不影响后端 API、数据库、部署、数据结构或公共接口。

## 当前风险与不确定项

- 无当前阻塞风险。

## 验证记录

- 已运行：`rg -n "实例 ID|材料 ID|材料来源|Instance ID:|Material ID:|Material source kind:" frontend\src\ui\llm\courseAgent.ts tests\test_course_agent_static.py docs\current-change.md`，结果只剩测试断言和当前工作单说明，`courseAgent.ts` 无残留。
- 已运行：`python -m pytest tests/test_course_agent_static.py -q`，10 个测试通过。
- 已运行：`pnpm --dir frontend exec eslint src/ui/llm/courseAgent.ts`，通过。
- 已运行：`pnpm --dir frontend build`，通过；仍有既有 chunk size warning。
- 已运行：`git diff --check -- frontend/src/ui/llm/courseAgent.ts tests/test_course_agent_static.py docs/current-change.md`，通过；仅提示这些工作区文件后续可能被 Git 转换为 CRLF。

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

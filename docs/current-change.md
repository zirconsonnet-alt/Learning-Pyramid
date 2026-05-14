# Current Change

更新时间：2026-05-14

## 1. 当前用户要求

- 提交并同步当前工作区全部内容到线上。
- 当前工作区包含两项已确认变更：
  - 实例详情页右侧复述点区域统一为“复述点列表”，删除实例专属说明文案。
  - 随机微休息默认配置改为启用。

## 2. 本次实际修改文件

- `backend/system/auth_store.py`
- `frontend/src/ui/store/pomodoroStore.ts`
- `frontend/src/ui/api/profile.ts`
- `frontend/src/views/pomodoro/PomodoroSettingsPage.tsx`
- `frontend/tests/fixtures/mock-api.ts`
- `frontend/tests/e2e/pomodoro-settings.spec.ts`
- `tests/test_project_config_defaults.py`
- `frontend/src/views/instances/InstancePage.tsx`
- `frontend/tests/e2e/review-detail-entry-links.spec.ts`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `backend/system/auth_store.py`：后端用户全局设置默认随机微休息改为启用。
- `frontend/src/ui/store/pomodoroStore.ts`：前端本地番茄钟 store 默认随机微休息改为启用。
- `frontend/src/ui/api/profile.ts`：前端 profile 响应 schema 在缺失 `microBreaks` 时默认启用随机微休息。
- `frontend/src/views/pomodoro/PomodoroSettingsPage.tsx`：恢复默认提示文案同步改为“默认开启”。
- `frontend/tests/fixtures/mock-api.ts`：测试默认全局设置同步为随机微休息默认启用，避免测试环境与真实默认分叉。
- `frontend/tests/e2e/pomodoro-settings.spec.ts`：增加设置页默认勾选随机微休息的断言。
- `tests/test_project_config_defaults.py`：增加新用户默认随机微休息启用的后端测试。
- `frontend/src/views/instances/InstancePage.tsx`：实例详情页右侧复述点区域标题改为“复述点列表”，删除“所有锚定到这个实例的复述点都会显示在这里。”说明文案。
- `frontend/tests/e2e/review-detail-entry-links.spec.ts`：补充实例详情页断言，确认标题和说明文案已按要求变化。
- `docs/current-change.md`：记录当前提交同步批次的实际范围。

## 4. 行为语义是否变化

- 是。新账号、缺失随机微休息设置或初始化默认配置时，随机微休息默认启用。
- 否。已有明确保存为关闭的用户设置不会被强制覆盖。
- 是。实例详情页右侧复述点区域的可见标题和说明文案变化。
- 否。实例详情页复述点查询范围不变，仍显示所有锚定到当前实例的复述点。

## 5. 是否做了重构，以及为什么

- 否。本次只修改默认值、提示文案和实例详情页调用处的展示文案，没有调整番茄钟执行逻辑、API、存储结构或复述点查询逻辑。

## 6. 未修改哪些相关内容，以及为什么

- 不修改已保存用户数据，避免把用户主动关闭的随机微休息偏好改回开启。
- 不修改随机微休息调度逻辑，因为当前需求只要求默认配置启用。
- 不修改番茄钟总开关默认值，避免扩大行为范围。
- 不修改实例到复述点的查询逻辑，因为当前数据范围符合“所有锚定到这个实例的复述点”的语义。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：否。
- UI：是，影响随机微休息恢复默认提示文案，以及实例详情页右侧复述点区域标题/说明文案。
- 测试：是，新增后端默认值测试、前端设置页 e2e 默认值断言，并更新实例详情页 e2e 断言。

## 8. 当前风险点和不确定项

- 已保存为随机微休息关闭的用户不会被本次默认值改变影响，这是刻意保留用户显式偏好的结果。

## 9. 仍需用户确认的问题

- 无。

## 10. 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

## 11. 验证状态

- 已先运行新增后端测试，确认旧实现失败在随机微休息默认关闭。
- `python -m pytest tests/test_project_config_defaults.py -q`：通过，3 passed。
- `pnpm test --grep "pomodoro settings enables random micro breaks by default"`（在 `frontend/` 下运行）：通过，1 passed。
- `pnpm exec tsc -b --noEmit`（在 `frontend/` 下运行）：通过。

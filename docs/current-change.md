# 当前变更：移动端测试依赖对齐

## 当前用户要求

- 修复 Task 1 代码质量审查指出的移动端高风险依赖图问题。
- 将 `mobile/package.json` 中的 `react-test-renderer` 固定为 `19.2.0`，对齐 `react@19.2.0`。
- 将 `jest` 固定为 `29.7.0`，将 `@types/jest` 固定为 `29.5.14`。
- 更新 `mobile/pnpm-lock.yaml`。
- 不删除 `mobile/scripts/reset-project.js`，当前只记录为非阻塞关注点。

## 根因

- Task 1 首次安装测试依赖时使用宽松 semver 范围，导致顶层 `react-test-renderer` 解析为 `19.2.6`，与模板固定的 `react@19.2.0` peer 要求不一致。
- `jest@30.4.2` 超出 `jest-expo` 相关子依赖的 peer 范围，形成测试依赖图风险。

## 本次实际修改文件

- `mobile/package.json`
  - 固定 `jest` 为 `29.7.0`。
  - 固定 `@types/jest` 为 `29.5.14`。
  - 固定 `react-test-renderer` 为 `19.2.0`。
- `mobile/pnpm-lock.yaml`
  - 根据精确测试依赖版本刷新依赖锁定图。
- `docs/current-change.md`
  - 覆盖为当前依赖对齐工作单，记录根因、验证结果和剩余警告。

## 行为语义是否变化

- 当前只调整移动端测试依赖版本和 lockfile，不改变现有后端、Web 前端、桌面端、部署或移动端运行时业务行为。
- 未实现或改变登录、API client、视频播放、离线缓存、本机文件导入或 WebView 包壳。

## 重构说明

- 未做代码重构。
- 本任务是依赖图修复，不改变现有模块抽象。

## 未修改内容

- 未修改后端、`frontend/`、`desktop/`、测试文件、部署配置、`.gitignore` 或长期文档。
- 未删除 `mobile/scripts/reset-project.js`，因为用户明确要求当前不擅自删除模板 reset 脚本。

## 影响范围

- API：无影响。
- 架构：无影响。
- 部署：无影响。
- 数据结构：无影响。
- UI：无影响。
- 测试：对齐测试依赖版本，未新增测试用例。

## 当前风险点和不确定项

- peer warning 根因已处理：`react-test-renderer` 与 `react` 对齐为 `19.2.0`，`jest` 降为 `29.7.0`，`@types/jest` 降为 `29.5.14`，且三者均为精确版本。
- 当前仍有 pnpm deprecated subdependency 警告：`abab@2.0.6`、`domexception@4.0.0`、`glob@7.2.3`、`inflight@1.0.6`、`rimraf@3.0.2`。这不是 peer warning，本任务不通过替换上游依赖链处理。
- `mobile/scripts/reset-project.js` 仍存在；按用户要求不删除，记录为非阻塞关注点。

## 仍需用户确认的问题

- 无。

## 验证记录

- `pnpm --dir mobile add -D jest@29.7.0 @types/jest@29.5.14 react-test-renderer@19.2.0 --save-exact`：成功；未出现 peer dependency warning，仍有 deprecated subdependency warning。
- `pnpm --dir mobile install --lockfile-only`：首次刷新成功且仍有 deprecated subdependency warning；最终复跑成功，未输出 peer dependency warning 或 deprecated subdependency warning。
- `pnpm --dir mobile exec jest --version`：成功，输出 `29.7.0`。
- `pnpm --dir mobile exec tsc --noEmit`：成功。
- `git diff --check -- mobile/package.json mobile/pnpm-lock.yaml docs/current-change.md`：成功；仅有 Git 换行提示，无 whitespace error。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

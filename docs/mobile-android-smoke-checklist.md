# Android 移动端 Smoke 清单

本文用于 Android Studio / Android 模拟器安装完成后，验证 `mobile/` Expo App 的第一轮端到端可用性。

## 当前预检结果

- CPU：当前环境是 Intel x64，不是 Windows ARM。
- Expo CLI：`55.0.30`。
- 依赖检查：`pnpm --dir mobile exec expo install --check` 通过。
- 自动测试：`pnpm --dir mobile test` 通过，9 个测试套件、27 个测试通过。
- 类型检查：`pnpm --dir mobile typecheck` 通过。
- Metro：`http://localhost:8081/status` 返回 `packager-status:running`。
- ADB：当前未安装或未进入 PATH，`adb` 不可用；安装 Android Studio 后需要复查。
- Lint：未作为当前验收项。`pnpm --dir mobile lint` 会触发 Expo 自动配置 ESLint；本次没有引入 lint 依赖或配置。

## 模拟器准备

安装 Android Studio 后确认：

```powershell
adb devices
```

预期至少看到一个模拟器：

```text
emulator-5554    device
```

如果 `adb` 不存在，通常需要把 Android SDK platform-tools 加到 PATH，常见路径：

```text
%LOCALAPPDATA%\Android\Sdk\platform-tools
```

## 启动 App

如果 Metro 未运行：

```powershell
$env:EXPO_PUBLIC_API_BASE_URL = "https://plm.xuebao.chat/api"
pnpm --dir mobile android
```

如果 Metro 已运行，也可以在 Expo 控制台按 `a` 打开 Android。

## Smoke 步骤

| 步骤 | 操作 | 预期结果 |
| --- | --- | --- |
| 1 | 打开 App | 显示登录页或已登录后的学科页 |
| 2 | 输入测试账号并登录 | 登录成功后进入学科列表 |
| 3 | 关闭并重新打开 App | 会话恢复，不应重新要求登录 |
| 4 | 点击一个学科 | 进入材料列表 |
| 5 | 点击一个有 `scopedProjectId` 的材料 | 进入学习对象列表 |
| 6 | 点击一个学习对象 | 进入学习对象详情 |
| 7 | 如果是 leaf 节点且有支持的 playback descriptor | 视频区域出现原生播放器 |
| 8 | 如果媒体是 `NATIVE_LOCAL` / `BROWSER_LOCAL` / `MANUAL` | 显示明确不可播放状态，不应白屏 |
| 9 | 查看复述点区域 | 能看到该节点关联的题面和答案，或看到“暂无复述点” |
| 10 | 返回项目页，点击“复习” | 进入复习页 |
| 11 | 如果队列为空 | 显示“暂无复习任务”，不显示提交按钮 |
| 12 | 如果队列有任务 | 逐题显示答案，选择“记得 / 不记得” |
| 13 | 全部作答后提交复习 | 提交成功后显示“复习已提交” |
| 14 | 点击退出 | 返回登录页 |

## 重点风险观察

- 登录后如果仍回到登录页，优先检查 React Native 是否拿到并回传 `plm_session`。
- 媒体无法播放时，先区分 descriptor 是否属于当前移动端明确不支持的来源。
- 如果 HLS/文件在测试里可拿到 descriptor 但原生播放器报错，记录 descriptor 的 `sourceKind`、`playbackKind`、`mimeType` 和 URL 形态。
- 复习提交失败时，确认当前提交的 `reviewTaskId` 来自 `/queue.headId`，不要从推荐复习项推导。

## 需要记录的结果

每次 smoke 后记录：

- 模拟器型号和 Android 版本。
- 登录是否成功。
- 会话恢复是否成功。
- 媒体 descriptor 类型和播放结果。
- 复习队列是否为空。
- 复习提交是否成功。
- 控制台或设备日志中的错误摘要。

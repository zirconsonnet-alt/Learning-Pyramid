# Current Change

更新时间：2026-05-13

## 1. 当前用户要求

- 继续修完账号切换后的设置污染问题。
- 大模型配置页不能把旧账号邮箱填进模型名。
- 新账号未设置番茄钟壁纸时，不能使用旧账号或旧浏览器全局壁纸。

## 2. 本次实际修改文件

- `frontend/src/views/settings/components/LlmSettingsCards.tsx`
- `frontend/tests/e2e/settings-llm.spec.ts`
- `frontend/src/ui/pomodoroWallpaper.ts`
- `frontend/src/views/pomodoro/PomodoroWallpaperBackdrop.tsx`
- `frontend/src/views/pomodoro/PomodoroPage.tsx`
- `frontend/src/views/pomodoro/PomodoroSettingsPage.tsx`
- `frontend/tests/e2e/pomodoro-settings.spec.ts`
- `frontend/tests/fixtures/mock-api.ts`
- `docs/data-model.md`
- `docs/current-change.md`

## 3. 每个文件为什么修改

- `LlmSettingsCards.tsx`：给 LLM 配置输入框补明确的字段名；API Key 字段改用 `autocomplete="new-password"`，避免浏览器密码管理器把模型名和密钥识别成登录账号密码组合。
- `settings-llm.spec.ts`：新增回归用例，固定 LLM 配置字段不是登录凭据字段的前端契约，并确认模型名不应出现当前测试用户邮箱。
- `pomodoroWallpaper.ts`：新增壁纸 scope，启用账号系统时按当前 `userId` 读写 IndexedDB key；未启用账号系统时保留浏览器本地 key。
- `PomodoroWallpaperBackdrop.tsx`：壁纸读取 hook 接收 scope，账号未解析完成前不读取旧的全局记录。
- `PomodoroPage.tsx`：按系统能力和当前用户解析番茄钟壁纸 scope，让主页面和计划编辑页读取当前账号壁纸。
- `PomodoroSettingsPage.tsx`：设置页按当前账号读写壁纸；账号状态未解析完成前禁用壁纸操作。
- `pomodoro-settings.spec.ts`：新增回归用例，确认已登录账号忽略旧的浏览器全局 `current` 壁纸；同步把同账号三页共享壁纸测试改成账号级壁纸 key。
- `mock-api.ts`：补齐 `/profile/me/llm-settings` 的 e2e mock 响应，让设置页测试使用真实结构的空账号配置，而不是落到通用空数组响应。
- `data-model.md`：记录番茄钟壁纸属于客户端 IndexedDB 本地偏好，并说明账号启用时的账号级 key 边界。
- `docs/current-change.md`：覆盖为本次任务工作单。

## 4. 行为语义是否变化

- UI 字段语义变化：大模型配置页的 Base URL、模型名、API Key 输入框带有明确的非登录配置字段语义。
- 数据语义不变：新账号未配置时仍应显示空 LLM 配置，不会把账号邮箱当作模型名。
- 本地壁纸数据语义变化：启用账号系统时，番茄钟壁纸按账号隔离；旧的浏览器全局 `current` 壁纸不会再显示给已登录账号。
- 未启用账号系统时，番茄钟壁纸仍使用浏览器本地 key。

## 5. 是否做了重构，以及为什么

- 是，做了局部重构。
- 原因是壁纸读写原本只接受隐式全局 key，无法表达账号边界；引入显式 `PomodoroWallpaperScope` 后，读、写、删和页面预览都走同一条账号维度数据流。

## 6. 未修改哪些相关内容，以及为什么

- 未修改后端 LLM 设置接口，因为已确认接口按当前账号读取配置，未配置时不会返回邮箱作为模型名。
- 未修改登录、登出和账号切换逻辑，因为当前截图中的模型名邮箱更符合浏览器密码管理器自动填充，而不是 React Query 或后端缓存返回旧账号数据。
- 未迁移旧的浏览器全局 `current` 壁纸到任何账号，因为无法可靠判断它属于哪个账号；迁移会继续制造跨账号污染风险。
- 未删除旧的浏览器全局 `current` 记录，因为删除本地历史数据属于清理策略，不是修复当前读取边界的必要条件。

## 7. 是否影响 API、架构、部署、数据结构、UI、测试

- API：否。
- 架构：否。
- 部署：否。
- 数据结构：是，客户端 IndexedDB 壁纸 key 新增账号维度；后端数据库不变。
- UI：是，输入框的浏览器自动填充语义变化；启用账号系统后，新账号不会看到旧全局壁纸。
- 测试：是，新增 LLM 配置页和番茄钟壁纸账号隔离 e2e 回归，并补齐相关 mock API。

## 8. 当前风险点和不确定项

- 浏览器密码管理器属于浏览器侧启发式行为，标准字段语义能显著降低误填，但无法由应用完全控制第三方密码管理器插件。
- 已登录账号不再读取旧全局 `current` 壁纸；旧本地壁纸不会自动归属到任何账号，需要用户在对应账号下重新设置。

## 9. 仍需用户确认的问题

- 是否需要额外提供“清理旧浏览器全局壁纸记录”的工具入口；当前修复不读取也不删除旧记录。

## 10. 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

## 11. 验证状态

- 已完成红灯验证：新增 e2e 在旧实现上失败，原因是 LLM 配置输入框缺少明确 `name`，API Key 字段仍为 `autocomplete="off"`。
- 已完成红灯验证：新增番茄钟壁纸账号隔离 e2e 在旧实现上失败，原因是已登录账号仍读取浏览器全局 `current` 壁纸。
- `$env:LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER='1'; $env:LEARNINGPYRAMID_FRONTEND_E2E_PORT='5192'; pnpm --dir frontend exec playwright test frontend/tests/e2e/pomodoro-settings.spec.ts -g "pomodoro wallpaper ignores|pomodoro settings shares"`：2 passed。
- `$env:LEARNINGPYRAMID_FRONTEND_E2E_USE_DEV_SERVER='1'; $env:LEARNINGPYRAMID_FRONTEND_E2E_PORT='5192'; pnpm --dir frontend exec playwright test frontend/tests/e2e/settings-llm.spec.ts frontend/tests/e2e/pomodoro-settings.spec.ts`：13 passed。
- `pnpm --dir frontend build`：通过；仍有既有 `hls` chunk 大于 500 kB 的 warning。
- `git diff --check`：通过；仅输出 Git 将 LF 替换为 CRLF 的工作区提示。

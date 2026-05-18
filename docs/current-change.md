# 当前变更：Task 3 session cookie 审查修复

## 当前用户要求

- 修复 Task 3 代码质量审查问题。
- 只修改并提交白名单文件。
- 明确 session cookie 三态：未出现、设置、清除。
- `createApiClient` 收到清除态时清空本地 `plm_session`。
- `buildCookieHeader` 只发送精确 `plm_session=<非空值>`。
- 补充多 `Set-Cookie`、合并 header、清 cookie、非目标 cookie、URL + JSON body + `Content-Type` 测试。
- 不新增 token、custom header、fallback、shim、legacy。

## 根因

- 原 `extractSessionCookie` 只有 `string | null`，把未出现和明确清除都表示为 `null`。
- `createApiClient` 只在提取到 truthy cookie 时调用 `setSessionCookie`，因此后端 logout/delete_cookie 后本地旧 `plm_session` 会保留。
- 原 `buildCookieHeader` 会发送任意非空字符串，无法在 helper 边界拒绝 `plm_session_backup` 或其他污染值。

## 本次实际修改文件

- `mobile/src/auth/sessionCookie.ts`
  - 新增 `SessionCookieUpdate` 三态类型。
  - 新增 `extractSessionCookieUpdate`。
  - 用小扫描器拆分合并 `Set-Cookie` header，只在逗号后看起来是 `token=` 时分割，避免误切 `Expires` 日期。
  - 保留 `extractSessionCookie` 兼容测试可用语义：set 返回 cookie，missing/clear 返回 `null`。
  - 收窄 `buildCookieHeader`，只允许精确 `plm_session=<非空且不含空白、分号、逗号的值>`。
- `mobile/src/api/http.ts`
  - 改为消费 `extractSessionCookieUpdate`。
  - set 态写入新 cookie，clear 态调用 `setSessionCookie(null)`，missing 态不更新。
  - 收窄 `fetchImpl` 注入点类型为 client 实际使用的最小 `ApiFetch` 形状，去掉测试中的 `fetchImpl as never`。
- `mobile/__tests__/session-cookie.test.ts`
  - 补充合并 `Set-Cookie` 查找目标 cookie。
  - 补充不误匹配 `plm_session_backup`。
  - 补充 missing/set/clear 三态与 `extractSessionCookie` 兼容行为。
  - 补充 `buildCookieHeader` 拒绝污染值。
- `mobile/__tests__/api-http.test.ts`
  - 补充清除态会让 `storedCookie` 变为 `null`。
  - 补充 JSON POST URL 拼接、`Content-Type` 和 body。
  - 用 typed fetch mock helper 替代 `fetchImpl as never`。
- `docs/current-change.md`
  - 覆盖为当前修复工作单。

## 行为语义是否变化

- 移动端现在能区分响应未包含目标 cookie、设置新 session cookie、明确清除 session cookie。
- 后端返回清除 `plm_session` 的 `Set-Cookie` 后，移动端本地 session cookie 会同步清空。
- 移动端只会发送精确的 `plm_session=<非空值>` cookie header，不再转发任意非空字符串。
- `fetchImpl` 注入点的 TypeScript 类型变为 client 实际依赖的最小 fetch 子集；运行时请求语义不变。

## 重构说明

- 做了当前需求范围内的局部整理：`sessionCookie.ts` 内部新增三态解析入口，并让旧 `extractSessionCookie` 复用它。
- 未做跨模块重构，未改变后端 API、认证协议或公共认证策略。

## 未修改内容

- 未修改后端认证策略。
- 未新增 token/custom header 认证协议。
- 未新增 fallback、shim、legacy 或特殊认证分支。
- 未修改测试配置、构建配置或无关文件。
- 未更新长期文档；本次是移动端内部 helper/client 行为收窄，当前事实已记录在本工作单，未涉及 README、架构、部署等长期文档语义变化。

## 影响范围

- API：不改变后端 API；移动端本地 client 行为更严格。
- 架构：无跨模块架构变化。
- 部署：无影响。
- 数据结构：无影响。
- UI：无影响。
- 测试：补充移动端 session cookie 与 API client 单元测试。

## 当前风险点和不确定项

- 真实移动端运行环境是否能读取 `Set-Cookie` 仍依赖运行时 fetch/header 暴露能力，本次只修复 helper 与 client 的本地语义。
- 仍需后续真实登录/logout smoke 验证认证闭环。

## 仍需用户确认的问题

- 无。

## 验证记录

- RED：`pnpm --dir mobile test -- api-http.test.ts session-cookie.test.ts` 失败，原因是 `extractSessionCookieUpdate` 不存在、clear 态未清本地 cookie、`buildCookieHeader` 接受污染值，符合预期。
- GREEN：`pnpm --dir mobile test -- api-http.test.ts session-cookie.test.ts` 通过，2 个测试套件、11 个测试通过。
- TYPECHECK：`pnpm --dir mobile typecheck` 首次失败，原因是测试 mock 与原 `typeof fetch` 注入类型不匹配；已将注入点类型收窄为实际使用的 `ApiFetch` 形状。
- GREEN：`pnpm --dir mobile test -- api-http.test.ts session-cookie.test.ts` 通过，2 个测试套件、11 个测试通过。
- GREEN：`pnpm --dir mobile typecheck` 通过。
- GREEN：`git diff --check -- mobile/src/api/http.ts mobile/src/auth/sessionCookie.ts mobile/__tests__/api-http.test.ts mobile/__tests__/session-cookie.test.ts docs/current-change.md` 通过；仅有 Git 换行转换 warning，无 whitespace error。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否

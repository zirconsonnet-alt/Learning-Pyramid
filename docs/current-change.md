# 当前变更：Task 3 移动端 API client

## 当前用户要求

- 实现移动端 API envelope、session cookie helper 和 HTTP client。
- 严格 TDD：先写失败测试，确认 RED，再写生产代码并验证 GREEN。
- 不修改后端认证策略，不新增 token/custom header 协议。
- 只修改 Task 3 白名单文件。
- 完成后只暂存 Task 3 文件并提交 `feat: add mobile api client`。

## 根因

- 移动端目前没有 `mobile/src/api/http.ts`，无法解析后端统一 API envelope，也没有移动端 HTTP client。
- 移动端目前没有 `mobile/src/auth/sessionCookie.ts`，无法从响应 `Set-Cookie` 中提取 `plm_session`，也无法为后续请求构造 `Cookie` header。

## 本次实际修改文件

- `mobile/__tests__/api-http.test.ts`
  - 新增 `parseApiEnvelope` RED 测试。
  - 新增 `createApiClient` cookie 发送与更新 RED 测试。
- `mobile/__tests__/session-cookie.test.ts`
  - 新增 session cookie helper RED 测试。
- `mobile/src/api/http.ts`
  - 新增 `ApiError`。
  - 新增 `parseApiEnvelope<T>`，解析后端 `{ ok, data/error }` envelope，并用 zod schema 校验成功数据。
  - 新增 `createApiClient`，支持 base URL 拼接、JSON body、session cookie 请求头、响应 `Set-Cookie` 更新和 envelope 解析。
- `mobile/src/auth/sessionCookie.ts`
  - 新增 `SESSION_COOKIE_NAME = "plm_session"`。
  - 新增 `extractSessionCookie` 和 `buildCookieHeader`。
- `docs/current-change.md`
  - 覆盖为当前 Task 3 工作单。

## 行为语义是否变化

- 新增移动端 API envelope 解析能力。
- 错误 envelope 会抛出 `ApiError`。
- 成功 envelope 的 `data` 会按调用方传入的 zod schema 解析。
- 新增移动端从 `Set-Cookie` 提取 `plm_session` 和构造 `Cookie` header 的能力。
- 新增移动端 HTTP client 请求能力；继续使用现有 cookie session，不新增 token/custom header 认证协议。

## 重构说明

- 未做重构。

## 未修改内容

- 未修改后端认证策略。
- 未新增 token/header 认证协议。
- 未修改测试配置、构建配置或无关文件。
- 未更新长期文档；本任务只新增移动端内部 client/helper，且本轮写入范围被限制在 Task 3 白名单文件内。

## 影响范围

- API：新增移动端本地 API envelope 解析，不改变后端 API。
- 架构：不改变现有后端架构边界。
- 部署：无影响。
- 数据结构：无影响。
- UI：无影响。
- 测试：新增移动端 API client 单元测试。

## 当前风险点和不确定项

- 认证真实 smoke 不在本任务执行；登录接入后必须验证 `Set-Cookie` 暴露和后续 `Cookie: plm_session=...` 请求是否可用。
- 如果真实登录 smoke 发现 cookie 不通，必须暂停，不能新增 token/custom header、后端特殊分支或兼容层。

## 仍需用户确认的问题

- 无。

## 验证记录

- RED：`pnpm --dir mobile test -- api-http.test.ts` 失败，原因是 `../src/api/http` 模块不存在，符合预期。
- GREEN：`pnpm --dir mobile test -- api-http.test.ts` 通过，2 个测试通过。
- RED：`pnpm --dir mobile test -- session-cookie.test.ts` 失败，原因是 `../src/auth/sessionCookie` 模块不存在，符合预期。
- GREEN：`pnpm --dir mobile test -- session-cookie.test.ts` 通过，2 个测试通过。
- RED：`pnpm --dir mobile test -- api-http.test.ts` 失败，原因是 `createApiClient` 不是函数，符合预期。
- GREEN：`pnpm --dir mobile test -- api-http.test.ts session-cookie.test.ts` 通过，5 个测试通过。
- TYPECHECK：`pnpm --dir mobile typecheck` 首次失败，原因是测试 mock 未声明参数，TypeScript 将 `fetchImpl.mock.calls` 推断为空参数 tuple；该问题不影响生产行为，但会阻断 typecheck。
- GREEN：`pnpm --dir mobile test -- api-http.test.ts session-cookie.test.ts` 通过，2 个测试套件、5 个测试通过。
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

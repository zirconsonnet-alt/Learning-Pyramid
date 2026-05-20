# 移动端 App MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **2026-05-19 correction:** 已发现原计划后半段把移动端工作台拆成“学习对象详情 + 独立复习页”，与桌面端工作台事实不一致。当前移动端工作台应以桌面端 `WorkbenchPage` / `ComposePane` / `ReviewPane` / `RollupPane` 语义为准：工作台内完成复述点录入或复习任务，并提供层推进与学习任务模式。本文早期任务仍保留为执行记录，不再作为当前工作台语义来源；当前状态以 `docs/mobile-client.md` 和 `docs/current-change.md` 为准。

**Goal:** 创建 `mobile/` Expo-managed React Native App，实现 Android/iPhone 第一版学习闭环基础。

**Architecture:** `mobile/` 是独立客户端工程，拥有自己的导航、页面、API client、状态和测试。移动端只通过现有 FastAPI `/api` 访问后端，继续使用 `{subjectId, scopedProjectId}`，不引用 `frontend/` 的 React DOM、Vite 或 Tauri 专用模块。

**Tech Stack:** Expo-managed React Native, TypeScript, Expo Router, `zod`, `@tanstack/react-query`, `expo-secure-store`, `expo-video`, `jest-expo`, `@testing-library/react-native`。

---

## 官方资料

- Expo 创建项目：`https://docs.expo.dev/more/create-expo/`
- Expo video：`https://docs.expo.dev/versions/latest/sdk/video/`
- Expo 单元测试：`https://docs.expo.dev/develop/unit-testing/`

## 范围检查

本计划只覆盖移动端 MVP 客户端工程。若实施中发现需要新增移动端 token、后端认证协议、媒体代理、数据库结构或部署配置，必须暂停确认，不能把这些改动塞进本计划。

## 文件结构

- Create: `mobile/`
  - Expo-managed React Native 工程。
- Modify: `.gitignore`
  - 只追加 `mobile/` 构建产物忽略项，不修改已有规则。
- Modify: `README.md`
  - 新增移动端运行入口。
- Modify: `docs/mobile-client.md`
  - 记录实施后的工程入口、运行命令和当前能力。
- Modify: `docs/current-change.md`
  - 随实现滚动更新当前任务状态。

移动端内部结构：

```text
mobile/
  app/
    _layout.tsx
    index.tsx
    subject/[subjectId].tsx
    project/[subjectId]/[scopedProjectId].tsx
    learning-object/[subjectId]/[scopedProjectId]/[nodeId].tsx
    review/[subjectId]/[scopedProjectId].tsx
  src/
    api/
      auth.ts
      http.ts
      learningObjects.ts
      media.ts
      review.ts
      subjects.ts
      types.ts
    auth/
      AuthProvider.tsx
      sessionCookie.ts
      sessionCookieStore.ts
      sessionStorage.ts
    components/
      AppButton.tsx
      AppTextInput.tsx
      EmptyState.tsx
      LoadingState.tsx
      Screen.tsx
    media/
      LearningMediaPlayer.tsx
    screens/
      LearningObjectScreen.tsx
      LoginScreen.tsx
      ProjectScreen.tsx
      ReviewScreen.tsx
      SubjectMaterialsScreen.tsx
      SubjectsScreen.tsx
    test/
      fetchMock.ts
      renderWithProviders.tsx
  __tests__/
```

---

### Task 1: 创建 Expo 移动端工程骨架

**Files:**
- Create: `mobile/`
- Modify: `.gitignore`
- Modify: `docs/current-change.md`

- [ ] **Step 1: 预检查移动端目录**

Run:

```powershell
Test-Path mobile
```

Expected: `False`。如果输出是 `True`，停止并检查已有 `mobile/` 内容，不能覆盖。

- [ ] **Step 2: 创建 Expo 工程**

Run:

```powershell
npx create-expo-app@latest mobile --template default@sdk-55 --no-install --no-agents-md
```

Expected: 创建 `mobile/package.json`、`mobile/app.json` 或 `mobile/app.config.*`、`mobile/app/`，且没有生成新的 `AGENTS.md`。

- [ ] **Step 3: 安装依赖**

Run:

```powershell
pnpm --dir mobile install
pnpm --dir mobile add zod @tanstack/react-query
pnpm --dir mobile exec expo install expo-secure-store expo-video
pnpm --dir mobile add -D jest jest-expo @types/jest @testing-library/react-native react-test-renderer
```

Expected: `mobile/package.json` 和 `mobile/pnpm-lock.yaml` 更新，依赖安装完成。

- [ ] **Step 4: 更新 `.gitignore`**

Append only these lines if they are not already present:

```gitignore
mobile/node_modules/
mobile/.expo/
mobile/dist/
mobile/coverage/
mobile/*.tsbuildinfo
```

Expected: 只新增移动端忽略项，不改已有规则。

- [ ] **Step 5: 初始验证**

Run:

```powershell
pnpm --dir mobile exec expo --version
pnpm --dir mobile exec tsc --noEmit
```

Expected: Expo CLI 输出版本号；TypeScript 检查通过或只暴露模板内已知问题。若模板自身失败，先记录错误，不改业务代码掩盖。

- [ ] **Step 6: 提交骨架**

Run:

```powershell
git add .gitignore mobile docs/current-change.md
git commit -m "feat: scaffold mobile expo app"
```

Expected: 只提交移动端骨架、`.gitignore` 移动端忽略项和当前工作单。

---

### Task 2: 配置移动端测试与基础组件

**Files:**
- Modify: `mobile/package.json`
- Create: `mobile/jest.config.js`
- Create: `mobile/src/components/Screen.tsx`
- Create: `mobile/src/components/LoadingState.tsx`
- Create: `mobile/src/components/EmptyState.tsx`
- Create: `mobile/src/components/AppButton.tsx`
- Create: `mobile/src/components/AppTextInput.tsx`
- Create: `mobile/src/test/renderWithProviders.tsx`
- Test: `mobile/__tests__/components.test.tsx`

- [ ] **Step 1: 写失败测试**

Create `mobile/__tests__/components.test.tsx`:

```tsx
import { render } from "@testing-library/react-native"

import { AppButton } from "../src/components/AppButton"
import { EmptyState } from "../src/components/EmptyState"
import { LoadingState } from "../src/components/LoadingState"

describe("mobile base components", () => {
  it("renders concise loading and empty states", () => {
    const loading = render(<LoadingState label="加载中" />)
    expect(loading.getByText("加载中")).toBeTruthy()

    const empty = render(<EmptyState title="暂无内容" />)
    expect(empty.getByText("暂无内容")).toBeTruthy()
  })

  it("renders a button label without web-only elements", () => {
    const button = render(<AppButton label="进入" onPress={() => undefined} />)
    expect(button.getByText("进入")).toBeTruthy()
  })
})
```

- [ ] **Step 2: 配置 Jest 并确认失败**

Add to `mobile/package.json` scripts:

```json
{
  "scripts": {
    "test": "jest --runInBand",
    "typecheck": "tsc --noEmit"
  }
}
```

Create `mobile/jest.config.js`:

```js
module.exports = {
  preset: "jest-expo",
  testMatch: ["**/__tests__/**/*.test.ts", "**/__tests__/**/*.test.tsx"],
}
```

Run:

```powershell
pnpm --dir mobile test -- components.test.tsx
```

Expected: FAIL because `src/components/*` files do not exist.

- [ ] **Step 3: 实现基础组件**

Create `mobile/src/components/Screen.tsx`:

```tsx
import type { ReactNode } from "react"
import { SafeAreaView, ScrollView, StyleSheet, View } from "react-native"

export function Screen({ children, scroll = true }: { children: ReactNode; scroll?: boolean }) {
  if (!scroll) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <View style={styles.body}>{children}</View>
      </SafeAreaView>
    )
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">
        {children}
      </ScrollView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: "#f8fafc" },
  body: { flexGrow: 1, padding: 20, gap: 16 },
})
```

Create `mobile/src/components/LoadingState.tsx`:

```tsx
import { ActivityIndicator, StyleSheet, Text, View } from "react-native"

export function LoadingState({ label = "加载中" }: { label?: string }) {
  return (
    <View style={styles.root}>
      <ActivityIndicator />
      <Text style={styles.text}>{label}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  root: { alignItems: "center", gap: 10, padding: 24 },
  text: { color: "#475569", fontSize: 14 },
})
```

Create `mobile/src/components/EmptyState.tsx`:

```tsx
import { StyleSheet, Text, View } from "react-native"

export function EmptyState({ title }: { title: string }) {
  return (
    <View style={styles.root}>
      <Text style={styles.title}>{title}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  root: { paddingVertical: 24 },
  title: { color: "#475569", fontSize: 15, textAlign: "center" },
})
```

Create `mobile/src/components/AppButton.tsx`:

```tsx
import { Pressable, StyleSheet, Text } from "react-native"

export function AppButton({ label, onPress, disabled = false }: { label: string; onPress: () => void; disabled?: boolean }) {
  return (
    <Pressable accessibilityRole="button" disabled={disabled} onPress={onPress} style={[styles.root, disabled && styles.disabled]}>
      <Text style={styles.label}>{label}</Text>
    </Pressable>
  )
}

const styles = StyleSheet.create({
  root: { alignItems: "center", backgroundColor: "#0f172a", borderRadius: 8, paddingHorizontal: 16, paddingVertical: 12 },
  disabled: { opacity: 0.55 },
  label: { color: "#ffffff", fontSize: 15, fontWeight: "600" },
})
```

Create `mobile/src/components/AppTextInput.tsx`:

```tsx
import { StyleSheet, TextInput, type TextInputProps } from "react-native"

export function AppTextInput(props: TextInputProps) {
  return <TextInput placeholderTextColor="#94a3b8" {...props} style={[styles.input, props.style]} />
}

const styles = StyleSheet.create({
  input: {
    backgroundColor: "#ffffff",
    borderColor: "#cbd5e1",
    borderRadius: 8,
    borderWidth: 1,
    color: "#0f172a",
    fontSize: 16,
    paddingHorizontal: 12,
    paddingVertical: 12,
  },
})
```

- [ ] **Step 4: 验证组件测试通过**

Run:

```powershell
pnpm --dir mobile test -- components.test.tsx
pnpm --dir mobile typecheck
```

Expected: tests PASS；TypeScript PASS。

- [ ] **Step 5: 提交测试基础和组件**

Run:

```powershell
git add mobile
git commit -m "feat: add mobile test harness and base components"
```

---

### Task 3: 实现 API envelope、session cookie 和 HTTP client

**Files:**
- Create: `mobile/src/api/http.ts`
- Create: `mobile/src/auth/sessionCookie.ts`
- Test: `mobile/__tests__/api-http.test.ts`
- Test: `mobile/__tests__/session-cookie.test.ts`

- [ ] **Step 1: 写 API envelope 失败测试**

Create `mobile/__tests__/api-http.test.ts`:

```ts
import { z } from "zod"

import { ApiError, parseApiEnvelope } from "../src/api/http"

describe("parseApiEnvelope", () => {
  it("returns typed data from ok envelope", () => {
    const data = parseApiEnvelope({ ok: true, data: { userId: "u1" } }, z.object({ userId: z.string() }), 200)
    expect(data.userId).toBe("u1")
  })

  it("throws ApiError from error envelope", () => {
    expect(() =>
      parseApiEnvelope({ ok: false, error: { code: "AUTH", message: "Authentication required" } }, z.object({}), 401),
    ).toThrow(ApiError)
  })
})
```

Run:

```powershell
pnpm --dir mobile test -- api-http.test.ts
```

Expected: FAIL because `src/api/http.ts` does not exist.

- [ ] **Step 2: 实现 API envelope 解析**

Create `mobile/src/api/http.ts`:

```ts
import { z } from "zod"

const ApiOkEnvelopeSchema = z.object({ ok: z.literal(true), data: z.unknown() })
const ApiErrEnvelopeSchema = z.object({
  ok: z.literal(false),
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.unknown().optional(),
  }),
})
const ApiEnvelopeSchema = z.union([ApiOkEnvelopeSchema, ApiErrEnvelopeSchema])

export class ApiError extends Error {
  code: string
  status: number
  details?: unknown

  constructor(message: string, opts: { code: string; status: number; details?: unknown }) {
    super(message)
    this.code = opts.code
    this.status = opts.status
    this.details = opts.details
  }
}

export function parseApiEnvelope<T>(json: unknown, responseSchema: z.ZodType<T>, status: number): T {
  const env = ApiEnvelopeSchema.parse(json)
  if (!env.ok) {
    throw new ApiError(env.error.message, { code: env.error.code, status, details: env.error.details })
  }
  return responseSchema.parse(env.data)
}
```

Run:

```powershell
pnpm --dir mobile test -- api-http.test.ts
```

Expected: PASS。

- [ ] **Step 3: 写 session cookie 失败测试**

Create `mobile/__tests__/session-cookie.test.ts`:

```ts
import { buildCookieHeader, extractSessionCookie } from "../src/auth/sessionCookie"

describe("session cookie helpers", () => {
  it("extracts plm_session from Set-Cookie", () => {
    const cookie = extractSessionCookie("plm_session=abc123; Max-Age=2592000; Path=/; HttpOnly; SameSite=None; Secure")
    expect(cookie).toBe("plm_session=abc123")
  })

  it("builds Cookie header from a stored session cookie", () => {
    expect(buildCookieHeader("plm_session=abc123")).toBe("plm_session=abc123")
    expect(buildCookieHeader(null)).toBeUndefined()
  })
})
```

Run:

```powershell
pnpm --dir mobile test -- session-cookie.test.ts
```

Expected: FAIL because `src/auth/sessionCookie.ts` does not exist.

- [ ] **Step 4: 实现 session cookie helper**

Create `mobile/src/auth/sessionCookie.ts`:

```ts
export const SESSION_COOKIE_NAME = "plm_session"

export function extractSessionCookie(setCookieHeader: string | null | undefined): string | null {
  const raw = String(setCookieHeader ?? "").trim()
  if (!raw) return null
  const firstPart = raw.split(";")[0]?.trim()
  if (!firstPart) return null
  if (!firstPart.startsWith(`${SESSION_COOKIE_NAME}=`)) return null
  const value = firstPart.slice(SESSION_COOKIE_NAME.length + 1)
  return value ? `${SESSION_COOKIE_NAME}=${value}` : null
}

export function buildCookieHeader(sessionCookie: string | null | undefined): string | undefined {
  const raw = String(sessionCookie ?? "").trim()
  return raw ? raw : undefined
}
```

Run:

```powershell
pnpm --dir mobile test -- session-cookie.test.ts
```

Expected: PASS。

- [ ] **Step 5: 扩展 HTTP client 测试**

Append to `mobile/__tests__/api-http.test.ts`:

```ts
import { createApiClient } from "../src/api/http"

it("sends existing session cookie and stores new session cookie", async () => {
  let storedCookie: string | null = "plm_session=old"
  const fetchImpl = jest.fn(async () => ({
    status: 200,
    headers: { get: (name: string) => (name.toLowerCase() === "set-cookie" ? "plm_session=new; Path=/; HttpOnly" : null) },
    text: async () => JSON.stringify({ ok: true, data: { userId: "u1" } }),
  }))

  const client = createApiClient({
    baseUrl: "https://plm.xuebao.chat/api",
    fetchImpl: fetchImpl as never,
    getSessionCookie: () => storedCookie,
    setSessionCookie: (cookie) => {
      storedCookie = cookie
    },
  })

  const data = await client.request({ path: "/auth/me", responseSchema: z.object({ userId: z.string() }) })
  expect(data.userId).toBe("u1")
  expect(fetchImpl.mock.calls[0][1].headers.Cookie).toBe("plm_session=old")
  expect(storedCookie).toBe("plm_session=new")
})
```

Run:

```powershell
pnpm --dir mobile test -- api-http.test.ts
```

Expected: FAIL because `createApiClient` does not exist.

- [ ] **Step 6: 实现 HTTP client**

Extend `mobile/src/api/http.ts`:

```ts
import { buildCookieHeader, extractSessionCookie } from "../auth/sessionCookie"

export type ApiClientOptions = {
  baseUrl: string
  fetchImpl?: typeof fetch
  getSessionCookie?: () => string | null
  setSessionCookie?: (cookie: string | null) => void
}

export type ApiRequestOptions<T> = {
  path: string
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"
  body?: unknown
  responseSchema: z.ZodType<T>
}

export function createApiClient(options: ApiClientOptions) {
  const baseUrl = options.baseUrl.replace(/\/$/, "")
  const fetchImpl = options.fetchImpl ?? fetch

  async function request<T>({ path, method = "GET", body, responseSchema }: ApiRequestOptions<T>): Promise<T> {
    const headers: Record<string, string> = {}
    const cookieHeader = buildCookieHeader(options.getSessionCookie?.())
    if (cookieHeader) headers.Cookie = cookieHeader
    if (body !== undefined) headers["Content-Type"] = "application/json"

    const response = await fetchImpl(`${baseUrl}${path.startsWith("/") ? path : `/${path}`}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    const setCookieHeader = response.headers.get("set-cookie")
    const nextCookie = extractSessionCookie(setCookieHeader)
    if (nextCookie) options.setSessionCookie?.(nextCookie)

    const text = await response.text()
    const json = JSON.parse(text)
    return parseApiEnvelope(json, responseSchema, response.status)
  }

  return { request }
}
```

Run:

```powershell
pnpm --dir mobile test -- api-http.test.ts session-cookie.test.ts
pnpm --dir mobile typecheck
```

Expected: tests PASS；TypeScript PASS。

- [ ] **Step 7: 认证策略 gate**

实施登录页后必须在 Android 模拟器或真机执行一次登录 smoke。如果登录响应没有暴露 `Set-Cookie`，或者后续 `/auth/me` 不能通过 `Cookie: plm_session=...` 访问，停止并回报认证阻塞。不能新增 token、custom header、后端特殊分支或兼容层。

- [ ] **Step 8: 提交 API client**

Run:

```powershell
git add mobile
git commit -m "feat: add mobile api client"
```

---

### Task 4: 实现移动端领域 API client

**Files:**
- Create: `mobile/src/api/types.ts`
- Create: `mobile/src/api/auth.ts`
- Create: `mobile/src/api/subjects.ts`
- Create: `mobile/src/api/learningObjects.ts`
- Create: `mobile/src/api/media.ts`
- Create: `mobile/src/api/review.ts`
- Test: `mobile/__tests__/domain-api.test.ts`

- [ ] **Step 1: 写失败测试**

Create `mobile/__tests__/domain-api.test.ts`:

```ts
import { createLearningPyramidApi } from "../src/api/types"

describe("mobile domain api", () => {
  it("uses public scoped project paths", async () => {
    const calls: string[] = []
    const api = createLearningPyramidApi({
      request: async ({ path }) => {
        calls.push(path)
        return []
      },
    } as never)

    await api.learningObjects.listNodes({ subjectId: "subj_1", scopedProjectId: "proj_1" })
    expect(calls[0]).toBe("/subjects/subj_1/projects/proj_1/learning-object-nodes")
  })
})
```

Run:

```powershell
pnpm --dir mobile test -- domain-api.test.ts
```

Expected: FAIL because `src/api/types.ts` does not exist.

- [ ] **Step 2: 实现共享类型和聚合入口**

Create `mobile/src/api/types.ts`:

```ts
import type { z } from "zod"

import { createAuthApi } from "./auth"
import { createLearningObjectsApi } from "./learningObjects"
import { createMediaApi } from "./media"
import { createReviewApi } from "./review"
import { createSubjectsApi } from "./subjects"

export type ScopedProjectRef = {
  subjectId: string
  scopedProjectId: string
}

export type ApiRequester = {
  request<T>(options: { path: string; method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"; body?: unknown; responseSchema: z.ZodType<T> }): Promise<T>
}

export function projectApiPath(scope: ScopedProjectRef, suffix: string) {
  return `/subjects/${encodeURIComponent(scope.subjectId)}/projects/${encodeURIComponent(scope.scopedProjectId)}${suffix.startsWith("/") ? suffix : `/${suffix}`}`
}

export function createLearningPyramidApi(requester: ApiRequester) {
  return {
    auth: createAuthApi(requester),
    subjects: createSubjectsApi(requester),
    learningObjects: createLearningObjectsApi(requester),
    media: createMediaApi(requester),
    review: createReviewApi(requester),
  }
}
```

- [ ] **Step 3: 实现领域 API 文件**

Create `mobile/src/api/auth.ts`:

```ts
import { z } from "zod"

import type { ApiRequester } from "./types"

export const AuthUserSchema = z.object({
  userId: z.string(),
  email: z.string(),
  publicUid: z.string(),
  nickname: z.string(),
  avatarUrl: z.string().nullable(),
  roles: z.array(z.string()),
})
export type AuthUser = z.infer<typeof AuthUserSchema>

export function createAuthApi(api: ApiRequester) {
  return {
    me: () => api.request({ path: "/auth/me", responseSchema: AuthUserSchema.nullable() }),
    login: (params: { email: string; password: string }) =>
      api.request({ path: "/auth/login", method: "POST", body: params, responseSchema: AuthUserSchema }),
    logout: () => api.request({ path: "/auth/logout", method: "POST", responseSchema: z.null() }),
  }
}
```

Create `mobile/src/api/subjects.ts`:

```ts
import { z } from "zod"

import type { ApiRequester } from "./types"

export const SubjectSchema = z.object({
  subjectId: z.string(),
  title: z.string(),
  state: z.string(),
  createdAt: z.string(),
  deletedAt: z.string().nullable(),
})
export type Subject = z.infer<typeof SubjectSchema>

export const StudyMaterialSchema = z.object({
  subjectId: z.string(),
  materialId: z.string(),
  materialType: z.enum(["COURSE", "BOOK", "LOOSE_POINTS"]),
  title: z.string(),
  createdAt: z.string(),
  scopedProjectId: z.string().nullable(),
})
export type StudyMaterial = z.infer<typeof StudyMaterialSchema>

export function createSubjectsApi(api: ApiRequester) {
  return {
    listSubjects: () => api.request({ path: "/subjects", responseSchema: z.array(SubjectSchema) }),
    listMaterials: (subjectId: string) =>
      api.request({ path: `/subjects/${encodeURIComponent(subjectId)}/materials`, responseSchema: z.array(StudyMaterialSchema) }),
  }
}
```

Create `mobile/src/api/learningObjects.ts`:

```ts
import { z } from "zod"

import { projectApiPath, type ApiRequester, type ScopedProjectRef } from "./types"

export const LearningObjectNodeSchema = z.discriminatedUnion("kind", [
  z.object({
    kind: z.literal("leaf"),
    projectId: z.string(),
    nodeId: z.string(),
    parentId: z.string().nullable(),
    instanceId: z.string(),
    title: z.string(),
  }),
  z.object({
    kind: z.literal("container"),
    projectId: z.string(),
    nodeId: z.string(),
    parentId: z.string().nullable(),
    children: z.array(z.string()),
    title: z.string(),
  }),
])
export type LearningObjectNode = z.infer<typeof LearningObjectNodeSchema>

export function createLearningObjectsApi(api: ApiRequester) {
  return {
    listNodes: (scope: ScopedProjectRef) =>
      api.request({ path: projectApiPath(scope, "/learning-object-nodes"), responseSchema: z.array(LearningObjectNodeSchema) }),
  }
}
```

Create `mobile/src/api/media.ts`:

```ts
import { z } from "zod"

import { projectApiPath, type ApiRequester, type ScopedProjectRef } from "./types"

export const PlaybackDescriptorSchema = z.object({
  instanceId: z.string(),
  sourceKind: z.enum(["SERVER_FS", "BROWSER_LOCAL", "NATIVE_LOCAL", "MANUAL", "BAIDU_NETDISK"]),
  playbackKind: z.enum(["FILE", "HLS"]),
  url: z.string(),
  mimeType: z.string(),
  durationMs: z.number().int().nonnegative().nullable(),
  supportsFrameGrab: z.boolean(),
  supportsServerAsr: z.boolean(),
})
export type PlaybackDescriptor = z.infer<typeof PlaybackDescriptorSchema>

export function createMediaApi(api: ApiRequester) {
  return {
    getPlayback: (scope: ScopedProjectRef, instanceId: string) =>
      api.request({ path: projectApiPath(scope, `/media/instances/${encodeURIComponent(instanceId)}/playback`), responseSchema: PlaybackDescriptorSchema }),
  }
}
```

Create `mobile/src/api/review.ts`:

```ts
import { z } from "zod"

import { projectApiPath, type ApiRequester, type ScopedProjectRef } from "./types"

export const RecallPointSchema = z.object({
  projectId: z.string(),
  recallPointId: z.string(),
  createdAt: z.string(),
  state: z.enum(["ACTIVE", "DELETED"]),
  deletedAt: z.string().nullable(),
  question: z.unknown(),
  answer: z.unknown(),
  anchor: z.object({ instanceId: z.string(), position: z.string() }).nullable(),
  references: z.array(z.string()).default([]),
  insights: z.array(z.unknown()),
})

export const ReviewRecommendationItemSchema = z.object({
  recallPoint: RecallPointSchema,
  reviewRecommendationIndex: z.number(),
  estimatedMemoryStrength: z.number(),
  weightedSuccessRatio: z.number(),
  lastReviewedAt: z.string().nullable(),
  lastReviewResult: z.enum(["CAN_RECALL", "CANNOT_RECALL"]).nullable(),
  reviewCount: z.number().int(),
})

export const ReviewRecommendationPageSchema = z.object({
  items: z.array(ReviewRecommendationItemSchema),
  totalCount: z.number().int(),
  offset: z.number().int(),
  limit: z.number().int(),
  nextOffset: z.number().int().nullable(),
})

export function createReviewApi(api: ApiRequester) {
  return {
    listRecallPoints: (scope: ScopedProjectRef) =>
      api.request({ path: projectApiPath(scope, "/recall-points"), responseSchema: z.array(RecallPointSchema) }),
    listRecommendations: (scope: ScopedProjectRef) =>
      api.request({ path: projectApiPath(scope, "/review-recommendations?offset=0&limit=50"), responseSchema: ReviewRecommendationPageSchema }),
    commitReviewTask: (scope: ScopedProjectRef, reviewTaskId: string, canRecall: number[]) =>
      api.request({
        path: projectApiPath(scope, `/review-tasks/${encodeURIComponent(reviewTaskId)}/commit`),
        method: "POST",
        body: { canRecall },
        responseSchema: z.null(),
      }),
  }
}
```

- [ ] **Step 4: 验证领域 API**

Run:

```powershell
pnpm --dir mobile test -- domain-api.test.ts
pnpm --dir mobile typecheck
```

Expected: tests PASS；TypeScript PASS。

- [ ] **Step 5: 提交领域 API**

Run:

```powershell
git add mobile
git commit -m "feat: add mobile domain api"
```

---

### Task 5: 实现认证状态和登录页

**Files:**
- Create: `mobile/src/auth/sessionStorage.ts`
- Create: `mobile/src/auth/sessionCookieStore.ts`
- Create: `mobile/src/auth/AuthProvider.tsx`
- Create: `mobile/src/screens/LoginScreen.tsx`
- Modify: `mobile/app/_layout.tsx`
- Modify: `mobile/app/index.tsx`
- Test: `mobile/__tests__/auth-provider.test.tsx`
- Test: `mobile/__tests__/login-screen.test.tsx`

- [ ] **Step 1: 写认证状态失败测试**

Create `mobile/__tests__/auth-provider.test.tsx`:

```tsx
import { render, waitFor } from "@testing-library/react-native"
import { Text } from "react-native"

import { AuthProvider, useAuth } from "../src/auth/AuthProvider"

function Probe() {
  const auth = useAuth()
  return <Text>{auth.status}</Text>
}

it("restores unauthenticated state when no session exists", async () => {
  const storage = {
    getSessionCookie: async () => null,
    setSessionCookie: async () => undefined,
    clearSessionCookie: async () => undefined,
  }
  const cookieStore = {
    getSessionCookie: () => null,
    setSessionCookie: () => undefined,
    clearSessionCookie: () => undefined,
  }
  const api = { auth: { me: async () => null } }

  const screen = render(
    <AuthProvider api={api as never} cookieStore={cookieStore} storage={storage}>
      <Probe />
    </AuthProvider>,
  )

  await waitFor(() => expect(screen.getByText("signedOut")).toBeTruthy())
})
```

Run:

```powershell
pnpm --dir mobile test -- auth-provider.test.tsx
```

Expected: FAIL because `AuthProvider` does not exist.

- [ ] **Step 2: 实现认证状态**

Create `mobile/src/auth/sessionStorage.ts`:

```ts
import * as SecureStore from "expo-secure-store"

const SESSION_COOKIE_KEY = "learningpyramid.sessionCookie"

export type SessionStorage = {
  getSessionCookie(): Promise<string | null>
  setSessionCookie(cookie: string): Promise<void>
  clearSessionCookie(): Promise<void>
}

export const secureSessionStorage: SessionStorage = {
  getSessionCookie: () => SecureStore.getItemAsync(SESSION_COOKIE_KEY),
  setSessionCookie: (cookie) => SecureStore.setItemAsync(SESSION_COOKIE_KEY, cookie),
  clearSessionCookie: () => SecureStore.deleteItemAsync(SESSION_COOKIE_KEY),
}
```

Create `mobile/src/auth/sessionCookieStore.ts`:

```ts
export type SessionCookieStore = {
  getSessionCookie(): string | null
  setSessionCookie(cookie: string | null): void
  clearSessionCookie(): void
}

export function createSessionCookieStore(initialCookie: string | null = null): SessionCookieStore {
  let sessionCookie = initialCookie
  return {
    getSessionCookie: () => sessionCookie,
    setSessionCookie: (cookie) => {
      sessionCookie = cookie
    },
    clearSessionCookie: () => {
      sessionCookie = null
    },
  }
}
```

Create `mobile/src/auth/AuthProvider.tsx`:

```tsx
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react"

import type { AuthUser } from "../api/auth"
import type { createLearningPyramidApi } from "../api/types"
import type { SessionCookieStore } from "./sessionCookieStore"
import type { SessionStorage } from "./sessionStorage"

type AuthStatus = "loading" | "signedOut" | "signedIn"

type AuthContextValue = {
  status: AuthStatus
  user: AuthUser | null
  signIn(email: string, password: string): Promise<void>
  signOut(): Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({
  api,
  cookieStore,
  storage,
  children,
}: {
  api: ReturnType<typeof createLearningPyramidApi>
  cookieStore: SessionCookieStore
  storage: SessionStorage
  children: ReactNode
}) {
  const [status, setStatus] = useState<AuthStatus>("loading")
  const [user, setUser] = useState<AuthUser | null>(null)

  useEffect(() => {
    let active = true
    async function restore() {
      const sessionCookie = await storage.getSessionCookie()
      cookieStore.setSessionCookie(sessionCookie)
      if (!sessionCookie) {
        if (active) setStatus("signedOut")
        return
      }
      const currentUser = await api.auth.me()
      if (!active) return
      setUser(currentUser)
      setStatus(currentUser ? "signedIn" : "signedOut")
    }
    void restore()
    return () => {
      active = false
    }
  }, [api, storage])

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      signIn: async (email, password) => {
        const nextUser = await api.auth.login({ email, password })
        const nextCookie = cookieStore.getSessionCookie()
        if (nextCookie) await storage.setSessionCookie(nextCookie)
        setUser(nextUser)
        setStatus("signedIn")
      },
      signOut: async () => {
        await api.auth.logout()
        cookieStore.clearSessionCookie()
        await storage.clearSessionCookie()
        setUser(null)
        setStatus("signedOut")
      },
    }),
    [api, cookieStore, status, storage, user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error("useAuth must be used within AuthProvider")
  return value
}
```

Run:

```powershell
pnpm --dir mobile test -- auth-provider.test.tsx
```

Expected: PASS。

- [ ] **Step 3: 写登录页测试**

Create `mobile/__tests__/login-screen.test.tsx`:

```tsx
import { fireEvent, render } from "@testing-library/react-native"

import { LoginScreen } from "../src/screens/LoginScreen"

it("submits email and password", () => {
  const signIn = jest.fn()
  const screen = render(<LoginScreen signIn={signIn} loading={false} errorMessage={null} />)

  fireEvent.changeText(screen.getByPlaceholderText("邮箱"), "me@example.com")
  fireEvent.changeText(screen.getByPlaceholderText("密码"), "secret")
  fireEvent.press(screen.getByText("登录"))

  expect(signIn).toHaveBeenCalledWith("me@example.com", "secret")
})
```

Run:

```powershell
pnpm --dir mobile test -- login-screen.test.tsx
```

Expected: FAIL because `LoginScreen` does not exist.

- [ ] **Step 4: 实现登录页**

Create `mobile/src/screens/LoginScreen.tsx`:

```tsx
import { useState } from "react"
import { StyleSheet, Text, View } from "react-native"

import { AppButton } from "../components/AppButton"
import { AppTextInput } from "../components/AppTextInput"
import { Screen } from "../components/Screen"

export function LoginScreen({
  signIn,
  loading,
  errorMessage,
}: {
  signIn: (email: string, password: string) => void
  loading: boolean
  errorMessage: string | null
}) {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")

  return (
    <Screen>
      <View style={styles.header}>
        <Text style={styles.title}>LearningPyramid</Text>
      </View>
      <View style={styles.form}>
        <AppTextInput autoCapitalize="none" keyboardType="email-address" onChangeText={setEmail} placeholder="邮箱" value={email} />
        <AppTextInput onChangeText={setPassword} placeholder="密码" secureTextEntry value={password} />
        {errorMessage ? <Text style={styles.error}>{errorMessage}</Text> : null}
        <AppButton disabled={loading} label={loading ? "登录中" : "登录"} onPress={() => signIn(email.trim(), password)} />
      </View>
    </Screen>
  )
}

const styles = StyleSheet.create({
  header: { paddingTop: 28 },
  title: { color: "#0f172a", fontSize: 28, fontWeight: "700" },
  form: { gap: 12 },
  error: { color: "#b91c1c", fontSize: 14 },
})
```

Run:

```powershell
pnpm --dir mobile test -- login-screen.test.tsx
pnpm --dir mobile typecheck
```

Expected: tests PASS；TypeScript PASS。

- [ ] **Step 5: 接入 App 根入口**

Modify `mobile/app/_layout.tsx` so it creates one `QueryClient`, one `SessionCookieStore`, one API client, and wraps routes with `AuthProvider`.

The API base URL must be a single constant:

```ts
const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? "https://plm.xuebao.chat/api"
```

The concrete bridge is `createSessionCookieStore()`: `createApiClient` receives its synchronous `getSessionCookie` / `setSessionCookie`, and `AuthProvider` restores/persists it through `secureSessionStorage`.

- [ ] **Step 6: 提交认证入口**

Run:

```powershell
git add mobile
git commit -m "feat: add mobile authentication flow"
```

---

### Task 6: 实现学科、材料和学习对象浏览

**Files:**
- Create: `mobile/src/screens/SubjectsScreen.tsx`
- Create: `mobile/src/screens/SubjectMaterialsScreen.tsx`
- Create: `mobile/src/screens/ProjectScreen.tsx`
- Modify: `mobile/app/index.tsx`
- Create: `mobile/app/subject/[subjectId].tsx`
- Create: `mobile/app/project/[subjectId]/[scopedProjectId].tsx`
- Test: `mobile/__tests__/learning-navigation.test.tsx`

- [ ] **Step 1: 写失败测试**

Create `mobile/__tests__/learning-navigation.test.tsx`:

```tsx
import { render } from "@testing-library/react-native"

import { ProjectScreen } from "../src/screens/ProjectScreen"

it("renders learning object titles", () => {
  const screen = render(
    <ProjectScreen
      loading={false}
      nodes={[
        { kind: "container", projectId: "p1", nodeId: "root", parentId: null, children: ["leaf"], title: "课程" },
        { kind: "leaf", projectId: "p1", nodeId: "leaf", parentId: "root", instanceId: "i1", title: "第一课" },
      ]}
      openNode={() => undefined}
    />,
  )

  expect(screen.getByText("课程")).toBeTruthy()
  expect(screen.getByText("第一课")).toBeTruthy()
})
```

Run:

```powershell
pnpm --dir mobile test -- learning-navigation.test.tsx
```

Expected: FAIL because `ProjectScreen` does not exist.

- [ ] **Step 2: 实现浏览页面**

Create screens that render lists with `FlatList` or `ScrollView` and only show essential text:

```tsx
export type ListAction<T> = {
  item: T
  onPress: () => void
}
```

For `ProjectScreen`, render containers and leaves in the order returned by the API. Do not invent a new tree mutation model.

- [ ] **Step 3: 接入路由和查询**

Use Expo Router pages:

- `app/index.tsx`: signed-in users see `SubjectsScreen`; signed-out users see `LoginScreen`。
- `app/subject/[subjectId].tsx`: calls `api.subjects.listMaterials(subjectId)`。
- `app/project/[subjectId]/[scopedProjectId].tsx`: calls `api.learningObjects.listNodes(scope)`。

All queries should use `@tanstack/react-query` and show `LoadingState` / `EmptyState` rather than extra explanatory UI.

- [ ] **Step 4: 验证浏览流程**

Run:

```powershell
pnpm --dir mobile test -- learning-navigation.test.tsx
pnpm --dir mobile typecheck
```

Expected: tests PASS；TypeScript PASS。

- [ ] **Step 5: 提交浏览功能**

Run:

```powershell
git add mobile
git commit -m "feat: add mobile learning navigation"
```

---

### Task 7: 实现学习对象详情、媒体播放和复述点展示

**Files:**
- Create: `mobile/src/media/LearningMediaPlayer.tsx`
- Create: `mobile/src/screens/LearningObjectScreen.tsx`
- Create: `mobile/app/learning-object/[subjectId]/[scopedProjectId]/[nodeId].tsx`
- Test: `mobile/__tests__/media-player.test.tsx`

- [ ] **Step 1: 写失败测试**

Create `mobile/__tests__/media-player.test.tsx`:

```tsx
import { render } from "@testing-library/react-native"

import { LearningMediaPlayer } from "../src/media/LearningMediaPlayer"

it("shows unsupported state for non-playable descriptors", () => {
  const screen = render(
    <LearningMediaPlayer
      descriptor={{
        instanceId: "i1",
        sourceKind: "NATIVE_LOCAL",
        playbackKind: "FILE",
        url: "native-only",
        mimeType: "video/mp4",
        durationMs: null,
        supportsFrameGrab: false,
        supportsServerAsr: false,
      }}
    />,
  )

  expect(screen.getByText("当前 App 暂不支持此素材播放")).toBeTruthy()
})
```

Run:

```powershell
pnpm --dir mobile test -- media-player.test.tsx
```

Expected: FAIL because `LearningMediaPlayer` does not exist.

- [ ] **Step 2: 实现媒体播放器边界**

Create `mobile/src/media/LearningMediaPlayer.tsx`:

```tsx
import { StyleSheet, Text, View } from "react-native"
import { useVideoPlayer, VideoView } from "expo-video"

import type { PlaybackDescriptor } from "../api/media"

function isPlayableOnMobile(descriptor: PlaybackDescriptor) {
  return descriptor.sourceKind !== "NATIVE_LOCAL" && /^https?:\/\//i.test(descriptor.url)
}

export function LearningMediaPlayer({ descriptor }: { descriptor: PlaybackDescriptor }) {
  if (!isPlayableOnMobile(descriptor)) {
    return (
      <View style={styles.unsupported}>
        <Text style={styles.unsupportedText}>当前 App 暂不支持此素材播放</Text>
      </View>
    )
  }

  const player = useVideoPlayer(descriptor.url, (playerInstance) => {
    playerInstance.loop = false
  })

  return <VideoView player={player} style={styles.video} />
}

const styles = StyleSheet.create({
  unsupported: { backgroundColor: "#e2e8f0", borderRadius: 8, padding: 18 },
  unsupportedText: { color: "#475569", fontSize: 14, textAlign: "center" },
  video: { aspectRatio: 16 / 9, backgroundColor: "#020617", borderRadius: 8, width: "100%" },
})
```

If `expo-video` test environment needs a Jest mock, create `mobile/__mocks__/expo-video.ts` with a simple `VideoView` component. Do not change runtime code to satisfy Jest.

- [ ] **Step 3: 实现学习对象详情**

`LearningObjectScreen` should:

- Receive the selected leaf node.
- Request `api.media.getPlayback(scope, instanceId)` only for leaf nodes.
- Request `api.review.listRecallPoints(scope)` and filter recall points by anchor `instanceId` in the screen.
- Render media first, then recall point question/answer text using compact rows.

- [ ] **Step 4: 验证媒体和详情**

Run:

```powershell
pnpm --dir mobile test -- media-player.test.tsx
pnpm --dir mobile typecheck
```

Expected: tests PASS；TypeScript PASS。

- [ ] **Step 5: 提交媒体与详情**

Run:

```powershell
git add mobile
git commit -m "feat: add mobile learning object detail"
```

---

### Task 8: 实现基础复习队列和提交

**Files:**
- Create: `mobile/src/screens/ReviewScreen.tsx`
- Create: `mobile/app/review/[subjectId]/[scopedProjectId].tsx`
- Test: `mobile/__tests__/review-screen.test.tsx`

- [ ] **Step 1: 写失败测试**

Create `mobile/__tests__/review-screen.test.tsx`:

```tsx
import { fireEvent, render } from "@testing-library/react-native"

import { ReviewScreen } from "../src/screens/ReviewScreen"

it("submits a can-recall decision", () => {
  const submit = jest.fn()
  const screen = render(
    <ReviewScreen
      item={{
        recallPoint: {
          projectId: "p1",
          recallPointId: "r1",
          createdAt: "2026-05-18T00:00:00Z",
          state: "ACTIVE",
          deletedAt: null,
          question: { text: "问题" },
          answer: { text: "答案" },
          anchor: null,
          references: [],
          insights: [],
        },
        reviewRecommendationIndex: 0,
        estimatedMemoryStrength: 0.5,
        weightedSuccessRatio: 0.5,
        lastReviewedAt: null,
        lastReviewResult: null,
        reviewCount: 0,
      }}
      submit={submit}
    />,
  )

  fireEvent.press(screen.getByText("能回忆"))
  expect(submit).toHaveBeenCalledWith(true)
})
```

Run:

```powershell
pnpm --dir mobile test -- review-screen.test.tsx
```

Expected: FAIL because `ReviewScreen` does not exist.

- [ ] **Step 2: 实现复习页面**

Create `ReviewScreen` with two actions: `能回忆` and `不能回忆`。如果当前后端提交需要 `reviewTaskId` 而 recommendation 没有直接给出任务 id，页面必须显示“暂无可提交复习任务”，不能伪造 `reviewTaskId`。

This is an intentional gate: if current API shape cannot support mobile review submission from recommendations, pause and report the API gap. Do not add a fake task id, hidden mapping, or fallback commit path.

- [ ] **Step 3: 验证复习页面**

Run:

```powershell
pnpm --dir mobile test -- review-screen.test.tsx
pnpm --dir mobile typecheck
```

Expected: tests PASS；TypeScript PASS。如果发现 API 缺少可提交任务 id，记录为阻塞并暂停实现提交动作。

- [ ] **Step 4: 提交复习功能或阻塞报告**

If implementation succeeds:

```powershell
git add mobile docs/current-change.md
git commit -m "feat: add mobile review flow"
```

If blocked by API shape:

```powershell
git add docs/current-change.md
git commit -m "docs: record mobile review api blocker"
```

---

### Task 9: 文档、README 和最终验证

**Files:**
- Modify: `README.md`
- Modify: `docs/mobile-client.md`
- Modify: `docs/current-change.md`

- [ ] **Step 1: 更新 README**

Add a concise mobile section:

```markdown
## Mobile app preview

The Android/iPhone app preview lives in `mobile/` and uses Expo-managed React Native.

```powershell
pnpm --dir mobile install
$env:EXPO_PUBLIC_API_BASE_URL = "https://plm.xuebao.chat/api"
pnpm --dir mobile start
```

The first MVP connects to the hosted API and does not implement phone local file import or offline cache.
```

- [ ] **Step 2: 更新 `docs/mobile-client.md`**

Add:

- 工程入口：`mobile/`
- 运行命令：`pnpm --dir mobile start`
- 测试命令：`pnpm --dir mobile test`、`pnpm --dir mobile typecheck`
- 当前已实现页面列表
- 已知阻塞或不支持能力

- [ ] **Step 3: 更新 `docs/current-change.md`**

Record:

- 本次实际修改文件。
- 行为语义变化。
- 是否做重构。
- 未修改内容。
- 验证记录。
- 污染风险检查。

- [ ] **Step 4: 最终验证**

Run:

```powershell
pnpm --dir mobile test
pnpm --dir mobile typecheck
pnpm --dir mobile exec expo --version
git diff --check -- .gitignore README.md docs/mobile-client.md docs/current-change.md mobile
```

Expected:

- Jest tests PASS。
- TypeScript PASS。
- Expo CLI prints a version。
- `git diff --check` exits 0。

If an Android emulator or Expo Go device is available, run:

```powershell
$env:EXPO_PUBLIC_API_BASE_URL = "https://plm.xuebao.chat/api"
pnpm --dir mobile start
```

Expected: Expo starts and prints a QR / local dev URL. If no emulator or device is available, record “未运行 Android/iPhone 启动 smoke，原因：当前环境没有可用设备或模拟器”。

- [ ] **Step 5: 提交文档和验证结果**

Run:

```powershell
git add README.md docs/mobile-client.md docs/current-change.md mobile
git commit -m "docs: document mobile app preview"
```

Expected: commit contains only mobile MVP, README, and related docs.

---

## 完成条件

- `mobile/` Expo-managed React Native 工程存在。
- 登录、学科列表、材料列表、学习对象浏览、学习对象详情、媒体播放边界和基础复习入口按计划实现。
- 没有新增后端特殊分支、fallback、shim、legacy 或移动端专用协议。
- `pnpm --dir mobile test` 通过。
- `pnpm --dir mobile typecheck` 通过。
- `README.md`、`docs/mobile-client.md`、`docs/current-change.md` 已同步。
- 如认证或复习提交 API 存在真实阻塞，已暂停并记录阻塞，而不是用脏实现绕过。

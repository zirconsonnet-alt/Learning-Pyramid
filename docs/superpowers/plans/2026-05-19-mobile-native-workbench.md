# Mobile Native Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first useful native mobile workbench so Expo Go users can select course content, play supported media, write text recall-point drafts, submit them as a `learning task`, and respect the review gate.

**Architecture:** Keep `mobile/` as an independent Expo-managed React Native app. Reuse the existing FastAPI scoped project API and the desktop/web workbench semantic model: current learning object, playback descriptor, local recall drafts, `POST /learning-tasks`, and review queue gate. Do not modify backend API, Web/Tauri workbench behavior, database schema, deployment, or auth protocol.

**Tech Stack:** Expo-managed React Native, Expo Router, TypeScript, `@tanstack/react-query`, `expo-video`, `zod`, `jest-expo`, `@testing-library/react-native`.

---

## Source Design

Implement against:

- `docs/superpowers/specs/2026-05-19-mobile-native-workbench-design.md`

## File Structure

- Create: `mobile/src/api/learningTasks.ts`
  - Mobile API client for `POST /learning-tasks`.
- Modify: `mobile/src/api/types.ts`
  - Add `learningTasks` to the aggregate API.
- Modify: `mobile/__tests__/domain-api.test.ts`
  - Cover the new scoped learning task path and body.
- Create: `mobile/src/workbench/recallDrafts.ts`
  - Pure draft model and submit payload builders.
- Create: `mobile/__tests__/workbench-drafts.test.ts`
  - TDD coverage for draft creation, validation, and submit payloads.
- Modify: `mobile/src/screens/LearningMediaPlayer.tsx`
  - Report playback time in milliseconds through a callback.
- Modify: `mobile/__tests__/learning-object-detail.test.tsx`
  - Cover `timeUpdate` wiring without changing runtime code for Jest.
- Create: `mobile/src/screens/MobileWorkbenchScreen.tsx`
  - Presentational mobile workbench: active learning object, media, directory picker, existing recall points, drafts, review gate.
- Create: `mobile/__tests__/mobile-workbench-screen.test.tsx`
  - Screen behavior tests.
- Modify: `mobile/src/app/project/[subjectId]/[scopedProjectId].tsx`
  - Replace project list page with query-driven mobile workbench route.
- Modify: `mobile/__tests__/learning-navigation.test.tsx`
  - Preserve list component coverage; route behavior is covered through the workbench screen and API tests.
- Create: `mobile/__tests__/project-route-workbench.test.tsx`
  - Cover route-level draft submit, current-node draft clearing, and required query invalidation.
- Modify: `docs/current-change.md`
  - Must be updated in every code-changing task before the task commit.
- Modify: `docs/mobile-client.md`
  - Document the native workbench boundary after implementation.

## Required Current-Change Discipline

Every task that modifies code must update `docs/current-change.md` in the same commit. Use this rolling structure and keep it under 300 lines:

```markdown
# 当前变更：移动端原生工作台

## 当前用户要求

- Expo Go Android 原生移动端需要补齐学习主流程，继续 React Native 路线，并按桌面/网页工作台语义实现学习优先工作台。

## 本次实际修改文件

- 在执行任务时写入本任务实际修改的文件路径。
- 每个文件下一行写明修改原因。

## 行为语义是否变化

- 在执行任务时写入本任务带来的行为变化；如果没有行为变化，写“无”。

## 重构说明

- 在执行任务时写入本任务是否做了局部重构；如果没有重构，写“无”。

## 未修改内容

- 未修改后端 API、数据库、部署、Web/Tauri 工作台语义。

## 影响范围

- API：仅移动端 client 调用既有 API；不新增后端 API。
- 架构：移动端仍独立于 `frontend/`。
- 部署：无影响。
- 数据结构：无影响。
- UI：移动端项目入口升级为学习优先工作台。
- 测试：记录本任务新增或更新的测试。

## 当前风险点和不确定项

- Expo 原生播放器携带 Cookie header 播放受保护媒体仍需真机 smoke。

## 仍需用户确认的问题

- 无。

## 验证记录

- 在执行任务时写入实际运行的验证命令和结果。

## 污染风险检查

- 是否新增特殊分支：否
- 是否新增隐式约定：否
- 是否新增重复逻辑：否
- 是否新增 fallback / shim / legacy：否
- 是否修改无关代码：否
- 是否破坏现有抽象边界：否
- 是否可能误导未来维护：否
```

When filling this document during execution, replace the instructional lines with concrete task facts before committing. Do not leave template-only descriptions in the committed file.

---

### Task 1: Add Mobile Learning Task API Client

**Files:**
- Create: `mobile/src/api/learningTasks.ts`
- Modify: `mobile/src/api/types.ts`
- Modify: `mobile/__tests__/domain-api.test.ts`
- Modify: `docs/current-change.md`

- [ ] **Step 1: Write the failing API test**

Replace `mobile/__tests__/domain-api.test.ts` with:

```ts
import { createLearningPyramidApi, type ApiRequester } from "../src/api/types"

describe("mobile domain api", () => {
  it("uses public scoped project paths", async () => {
    const calls: Array<{ path: string; method?: string; body?: unknown }> = []
    const requester: ApiRequester = {
      request: async <T,>({ path, method, body }: Parameters<ApiRequester["request"]>[0]) => {
        calls.push({ path, method, body })
        return [] as T
      },
    }
    const api = createLearningPyramidApi(requester)
    const scope = { subjectId: "subj_1", scopedProjectId: "proj_1" }

    await api.auth.me()
    await api.auth.login({ email: "me@example.com", password: "secret" })
    await api.auth.logout()
    await api.subjects.listSubjects()
    await api.subjects.listMaterials("subj_1")
    await api.learningObjects.listNodes(scope)
    await api.learningObjects.getNode(scope, "node_1")
    await api.learningObjects.listRecallPointsByNode(scope, "node_1")
    await api.media.getPlayback(scope, "inst_1")
    await api.review.getQueue(scope)
    await api.review.getReviewTask(scope, "task_1")
    await api.review.getRangeSnapshot(scope, "range_1")
    await api.review.listRecallPoints(scope)
    await api.review.listRecommendations(scope, { offset: 10, limit: 20 })
    await api.review.commitReviewTask(scope, "task_1", { canRecall: [0] })
    await api.learningTasks.submitLearningTask(scope, {
      title: "第一课",
      items: [
        {
          question: [{ kind: "TEXT", text: "题面" }],
          answer: [{ kind: "TEXT", text: "答案" }],
          anchor: { instanceId: "inst_1", position: "t=12000" },
          references: [],
        },
      ],
    })

    expect(calls).toEqual([
      { path: "/auth/me", method: undefined, body: undefined },
      { path: "/auth/login", method: "POST", body: { email: "me@example.com", password: "secret" } },
      { path: "/auth/logout", method: "POST", body: undefined },
      { path: "/subjects", method: undefined, body: undefined },
      { path: "/subjects/subj_1/materials", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/learning-object-nodes", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/learning-objects/node_1", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/learning-objects/node_1/recall-points", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/media/instances/inst_1/playback", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/queue", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/review-tasks/task_1", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/ranges/range_1", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/recall-points", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/review-recommendations?offset=10&limit=20", method: undefined, body: undefined },
      { path: "/subjects/subj_1/projects/proj_1/review-tasks/task_1/commit", method: "POST", body: { canRecall: [0] } },
      {
        path: "/subjects/subj_1/projects/proj_1/learning-tasks",
        method: "POST",
        body: {
          title: "第一课",
          items: [
            {
              question: [{ kind: "TEXT", text: "题面" }],
              answer: [{ kind: "TEXT", text: "答案" }],
              anchor: { instanceId: "inst_1", position: "t=12000" },
              references: [],
            },
          ],
        },
      },
    ])
  })
})
```

- [ ] **Step 2: Verify the test fails**

Run:

```powershell
pnpm --dir mobile test -- domain-api.test.ts
```

Expected: FAIL because `api.learningTasks` does not exist.

- [ ] **Step 3: Add the learning task API client**

Create `mobile/src/api/learningTasks.ts`:

```ts
import { z } from "zod"

import { RichContentSchema, type RichContent } from "./richContent"
import { projectApiPath, type ApiRequester, type ScopedProjectRef } from "./types"

const SubmitLearningTaskResultSchema = z.object({ entryNodeId: z.string() })

export type SubmitLearningTaskItem = {
  question: RichContent
  answer: RichContent
  anchor: { instanceId: string; position: string } | null
  references: string[]
}

export type SubmitLearningTaskInput = {
  title: string
  items: SubmitLearningTaskItem[]
}

export type SubmitLearningTaskResult = z.infer<typeof SubmitLearningTaskResultSchema>

export function createLearningTasksApi(api: ApiRequester) {
  return {
    submitLearningTask: (scope: ScopedProjectRef, input: SubmitLearningTaskInput) =>
      api.request({
        path: projectApiPath(scope, "/learning-tasks"),
        method: "POST",
        body: {
          title: input.title,
          items: input.items.map((item) => ({
            question: RichContentSchema.parse(item.question),
            answer: RichContentSchema.parse(item.answer),
            anchor: item.anchor,
            references: item.references,
          })),
        },
        responseSchema: SubmitLearningTaskResultSchema,
      }),
  }
}
```

- [ ] **Step 4: Register the API client**

Update `mobile/src/api/types.ts` to import and expose learning tasks:

```ts
import { z } from "zod"

import { createAuthApi } from "./auth"
import { createLearningObjectsApi } from "./learningObjects"
import { createLearningTasksApi } from "./learningTasks"
import { createMediaApi } from "./media"
import { createReviewApi } from "./review"
import { createSubjectsApi } from "./subjects"

export type ScopedProjectRef = {
  subjectId: string
  scopedProjectId: string
}

export type ApiRequestOptions<T> = {
  path: string
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"
  body?: unknown
  responseSchema: z.ZodType<T>
}

export type ApiRequester = {
  request: <T>(options: ApiRequestOptions<T>) => Promise<T>
}

export function projectApiPath(scope: ScopedProjectRef, suffix: string) {
  const cleanSuffix = suffix.startsWith("/") ? suffix : `/${suffix}`
  return `/subjects/${encodeURIComponent(scope.subjectId)}/projects/${encodeURIComponent(
    scope.scopedProjectId,
  )}${cleanSuffix}`
}

export function createLearningPyramidApi(requester: ApiRequester) {
  return {
    auth: createAuthApi(requester),
    subjects: createSubjectsApi(requester),
    learningObjects: createLearningObjectsApi(requester),
    learningTasks: createLearningTasksApi(requester),
    media: createMediaApi(requester),
    review: createReviewApi(requester),
  }
}
```

- [ ] **Step 5: Update current-change**

Update `docs/current-change.md` with this task's files and verification result. The committed file must not contain angle-bracket placeholders.

- [ ] **Step 6: Verify green**

Run:

```powershell
pnpm --dir mobile test -- domain-api.test.ts
pnpm --dir mobile typecheck
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```powershell
git add mobile/src/api/learningTasks.ts mobile/src/api/types.ts mobile/__tests__/domain-api.test.ts docs/current-change.md
git commit -m "feat: add mobile learning task api"
```

---

### Task 2: Add Recall Draft Model

**Files:**
- Create: `mobile/src/workbench/recallDrafts.ts`
- Create: `mobile/__tests__/workbench-drafts.test.ts`
- Modify: `docs/current-change.md`

- [ ] **Step 1: Write the failing draft tests**

Create `mobile/__tests__/workbench-drafts.test.ts`:

```ts
import {
  buildSubmitLearningTaskItems,
  createRecallDraft,
  getIncompleteDraftReason,
  recallDraftTextToRichContent,
} from "../src/workbench/recallDrafts"

describe("mobile workbench recall drafts", () => {
  it("creates a draft anchored to the current playback time", () => {
    const draft = createRecallDraft({
      instanceId: "inst_1",
      currentMs: 12750,
      localId: "draft_1",
      now: 1710000000000,
    })

    expect(draft).toEqual({
      localId: "draft_1",
      instanceId: "inst_1",
      position: "t=12750",
      questionText: "",
      answerText: "",
      createdAt: 1710000000000,
      updatedAt: 1710000000000,
    })
  })

  it("builds learning task items from complete text drafts", () => {
    const draft = {
      localId: "draft_1",
      instanceId: "inst_1",
      position: "t=12000",
      questionText: "问题",
      answerText: "答案",
      createdAt: 1710000000000,
      updatedAt: 1710000001000,
    }

    expect(getIncompleteDraftReason(draft)).toBeNull()
    expect(buildSubmitLearningTaskItems([draft])).toEqual([
      {
        question: [{ kind: "TEXT", text: "问题" }],
        answer: [{ kind: "TEXT", text: "答案" }],
        anchor: { instanceId: "inst_1", position: "t=12000" },
        references: [],
      },
    ])
  })

  it("rejects incomplete drafts before submit payload creation", () => {
    const draft = createRecallDraft({
      instanceId: "inst_1",
      currentMs: 0,
      localId: "draft_1",
      now: 1710000000000,
    })

    expect(getIncompleteDraftReason(draft)).toBe("题面不能为空")
    expect(() => buildSubmitLearningTaskItems([draft])).toThrow("题面不能为空")
  })

  it("trims text before creating rich content", () => {
    expect(recallDraftTextToRichContent("  题面  ")).toEqual([{ kind: "TEXT", text: "题面" }])
  })
})
```

- [ ] **Step 2: Verify the tests fail**

Run:

```powershell
pnpm --dir mobile test -- workbench-drafts.test.ts
```

Expected: FAIL because `src/workbench/recallDrafts.ts` does not exist.

- [ ] **Step 3: Add the draft model**

Create `mobile/src/workbench/recallDrafts.ts`:

```ts
import type { SubmitLearningTaskItem } from "../api/learningTasks"
import type { RichContent } from "../api/richContent"

export type MobileRecallDraft = {
  localId: string
  questionText: string
  answerText: string
  instanceId: string
  position: string
  createdAt: number
  updatedAt: number
}

export type CreateRecallDraftInput = {
  instanceId: string
  currentMs: number
  localId: string
  now: number
}

export function createRecallDraft(input: CreateRecallDraftInput): MobileRecallDraft {
  const anchorMs = Math.max(0, Math.floor(input.currentMs))
  return {
    localId: input.localId,
    instanceId: input.instanceId,
    position: `t=${anchorMs}`,
    questionText: "",
    answerText: "",
    createdAt: input.now,
    updatedAt: input.now,
  }
}

export function recallDraftTextToRichContent(text: string): RichContent {
  const trimmed = text.trim()
  if (!trimmed) throw new Error("文本不能为空")
  return [{ kind: "TEXT", text: trimmed }]
}

export function getIncompleteDraftReason(draft: MobileRecallDraft): string | null {
  if (!draft.questionText.trim()) return "题面不能为空"
  if (!draft.answerText.trim()) return "答案不能为空"
  if (!draft.instanceId.trim()) return "缺少学习对象"
  if (!draft.position.trim()) return "缺少锚点"
  return null
}

export function buildSubmitLearningTaskItems(drafts: MobileRecallDraft[]): SubmitLearningTaskItem[] {
  return drafts.map((draft) => {
    const reason = getIncompleteDraftReason(draft)
    if (reason) throw new Error(reason)
    return {
      question: recallDraftTextToRichContent(draft.questionText),
      answer: recallDraftTextToRichContent(draft.answerText),
      anchor: { instanceId: draft.instanceId, position: draft.position },
      references: [],
    }
  })
}
```

- [ ] **Step 4: Update current-change**

Update `docs/current-change.md` with this task's files and verification result. The committed file must not contain angle-bracket placeholders.

- [ ] **Step 5: Verify green**

Run:

```powershell
pnpm --dir mobile test -- workbench-drafts.test.ts
pnpm --dir mobile typecheck
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add mobile/src/workbench/recallDrafts.ts mobile/__tests__/workbench-drafts.test.ts docs/current-change.md
git commit -m "feat: add mobile recall draft model"
```

---

### Task 3: Report Playback Time From Mobile Player

**Files:**
- Modify: `mobile/src/screens/LearningMediaPlayer.tsx`
- Modify: `mobile/__tests__/learning-object-detail.test.tsx`
- Modify: `docs/current-change.md`

- [ ] **Step 1: Add failing playback time test**

Replace `mobile/__tests__/learning-object-detail.test.tsx` with:

```tsx
import { render } from "@testing-library/react-native"
import { useVideoPlayer } from "expo-video"
import { Text } from "react-native"

import { ApiProvider, useApiRuntime } from "../src/api/ApiProvider"
import type { LearningObjectNode } from "../src/api/learningObjects"
import type { PlaybackDescriptor } from "../src/api/media"
import type { RecallPoint } from "../src/api/review"
import type { createLearningPyramidApi } from "../src/api/types"
import { LearningMediaPlayer } from "../src/screens/LearningMediaPlayer"
import { LearningObjectScreen } from "../src/screens/LearningObjectScreen"

type TimeUpdateHandler = (payload: { currentTime: number }) => void

const playerMock = {
  id: "player",
  timeUpdateEventInterval: 0,
  addListener: jest.fn((_eventName: "timeUpdate", handler: TimeUpdateHandler) => {
    playerMock.timeUpdateHandler = handler
    return { remove: jest.fn() }
  }),
  timeUpdateHandler: null as TimeUpdateHandler | null,
}

jest.mock("expo-video", () => {
  const React = require("react")
  const { Text } = require("react-native")
  return {
    useVideoPlayer: jest.fn(() => playerMock),
    VideoView: () => React.createElement(Text, null, "VideoView"),
  }
})

const playableDescriptor: PlaybackDescriptor = {
  instanceId: "inst_1",
  sourceKind: "SERVER_FS",
  playbackKind: "FILE",
  url: "/api/subjects/subj_1/projects/proj_1/media/instances/inst_1",
  mimeType: "video/mp4",
  durationMs: 120000,
  supportsFrameGrab: true,
  supportsServerAsr: true,
}

const leafNode: LearningObjectNode = {
  kind: "leaf",
  projectId: "proj_1",
  nodeId: "node_1",
  parentId: null,
  instanceId: "inst_1",
  title: "第一课",
}

const recallPoint: RecallPoint = {
  projectId: "proj_1",
  recallPointId: "rp_1",
  createdAt: "2026-05-18T00:00:00Z",
  state: "ACTIVE",
  deletedAt: null,
  question: [{ kind: "TEXT", text: "学习金字塔强调什么？" }],
  answer: [{ kind: "TEXT", text: "主动回忆和应用。" }],
  anchor: { instanceId: "inst_1", position: "t=10000" },
  references: [],
  insights: [],
}

describe("LearningMediaPlayer", () => {
  beforeEach(() => {
    jest.clearAllMocks()
    playerMock.timeUpdateEventInterval = 0
    playerMock.timeUpdateHandler = null
  })

  it("passes resolved URL and session cookie header to expo-video for supported playback", () => {
    const screen = render(
      <LearningMediaPlayer
        apiBaseUrl="https://plm.xuebao.chat/api"
        descriptor={playableDescriptor}
        loading={false}
        sessionCookie="plm_session=abc"
        title="第一课"
      />,
    )

    expect(screen.getByText("VideoView")).toBeTruthy()
    expect(useVideoPlayer).toHaveBeenCalledWith(
      expect.objectContaining({
        contentType: "progressive",
        headers: { Cookie: "plm_session=abc" },
        metadata: { title: "第一课" },
        uri: "https://plm.xuebao.chat/api/subjects/subj_1/projects/proj_1/media/instances/inst_1",
      }),
    )
  })

  it("reports playback time updates in milliseconds", () => {
    const onPlaybackTimeChange = jest.fn()
    render(
      <LearningMediaPlayer
        apiBaseUrl="https://plm.xuebao.chat/api"
        descriptor={playableDescriptor}
        loading={false}
        onPlaybackTimeChange={onPlaybackTimeChange}
        sessionCookie="plm_session=abc"
        title="第一课"
      />,
    )

    expect(playerMock.timeUpdateEventInterval).toBe(0.5)
    expect(playerMock.addListener).toHaveBeenCalledWith("timeUpdate", expect.any(Function))

    playerMock.timeUpdateHandler?.({ currentTime: 12.345 })
    expect(onPlaybackTimeChange).toHaveBeenCalledWith(12345)
  })

  it("shows an explicit unsupported state for desktop native media", () => {
    const screen = render(
      <LearningMediaPlayer
        apiBaseUrl="https://plm.xuebao.chat/api"
        descriptor={{ ...playableDescriptor, sourceKind: "NATIVE_LOCAL" }}
        loading={false}
        sessionCookie="plm_session=abc"
        title="第一课"
      />,
    )

    expect(screen.getByText("移动端不支持桌面本地媒体")).toBeTruthy()
    expect(useVideoPlayer).not.toHaveBeenCalled()
  })
})

describe("ApiProvider", () => {
  it("exposes API base URL and the current session cookie reader", () => {
    const api = {} as ReturnType<typeof createLearningPyramidApi>

    function Probe() {
      const runtime = useApiRuntime()
      return <Text>{`${runtime.apiBaseUrl}|${runtime.getSessionCookie()}`}</Text>
    }

    const screen = render(
      <ApiProvider api={api} apiBaseUrl="https://plm.xuebao.chat/api" getSessionCookie={() => "plm_session=abc"}>
        <Probe />
      </ApiProvider>,
    )

    expect(screen.getByText("https://plm.xuebao.chat/api|plm_session=abc")).toBeTruthy()
  })
})

describe("LearningObjectScreen", () => {
  it("renders learning object title, media, and recall points", () => {
    const screen = render(
      <LearningObjectScreen
        apiBaseUrl="https://plm.xuebao.chat/api"
        node={leafNode}
        nodeErrorMessage={null}
        nodeLoading={false}
        playback={playableDescriptor}
        playbackErrorMessage={null}
        playbackLoading={false}
        recallPoints={[recallPoint]}
        recallPointsErrorMessage={null}
        recallPointsLoading={false}
        sessionCookie="plm_session=abc"
      />,
    )

    expect(screen.getByText("第一课")).toBeTruthy()
    expect(screen.getByText("VideoView")).toBeTruthy()
    expect(screen.getByText("学习金字塔强调什么？")).toBeTruthy()
    expect(screen.getByText("主动回忆和应用。")).toBeTruthy()
  })
})
```

- [ ] **Step 2: Verify the test fails**

Run:

```powershell
pnpm --dir mobile test -- learning-object-detail.test.tsx
```

Expected: FAIL because `LearningMediaPlayer` does not accept or call `onPlaybackTimeChange`.

- [ ] **Step 3: Update the player**

Replace `mobile/src/screens/LearningMediaPlayer.tsx` with:

```tsx
import { useEffect } from "react"
import { StyleSheet, View } from "react-native"
import { VideoView, useVideoPlayer, type ContentType, type VideoSource } from "expo-video"

import { buildCookieHeader } from "../auth/sessionCookie"
import { EmptyState } from "../components/EmptyState"
import { LoadingState } from "../components/LoadingState"
import { resolveApiResourceUrl } from "../api/http"
import type { PlaybackDescriptor } from "../api/media"

export function LearningMediaPlayer({
  apiBaseUrl,
  descriptor,
  errorMessage,
  loading,
  onPlaybackTimeChange,
  sessionCookie,
  title,
}: {
  apiBaseUrl: string
  descriptor: PlaybackDescriptor | null
  errorMessage?: string | null
  loading: boolean
  onPlaybackTimeChange?: (currentMs: number) => void
  sessionCookie?: string | null
  title: string
}) {
  if (loading) return <LoadingState label="加载媒体" />
  if (errorMessage) return <EmptyState title={errorMessage} />
  if (!descriptor) return <EmptyState title="暂无媒体" />

  const unsupportedMessage = getUnsupportedPlaybackMessage(descriptor)
  if (unsupportedMessage) return <EmptyState title={unsupportedMessage} />

  const cookieHeader = buildCookieHeader(sessionCookie)
  const source: VideoSource = {
    uri: resolveApiResourceUrl(apiBaseUrl, descriptor.url),
    contentType: descriptor.playbackKind === "HLS" ? ("hls" satisfies ContentType) : ("progressive" satisfies ContentType),
    headers: cookieHeader ? { Cookie: cookieHeader } : undefined,
    metadata: { title },
  }

  return <PlayableVideo onPlaybackTimeChange={onPlaybackTimeChange} source={source} />
}

function getUnsupportedPlaybackMessage(descriptor: PlaybackDescriptor) {
  if (descriptor.sourceKind === "NATIVE_LOCAL") return "移动端不支持桌面本地媒体"
  if (descriptor.sourceKind === "BROWSER_LOCAL") return "移动端不支持浏览器本地媒体"
  if (descriptor.sourceKind === "MANUAL") return "当前媒体没有可播放文件"
  if (!descriptor.url.trim()) return "当前媒体没有可播放地址"
  return null
}

function PlayableVideo({
  onPlaybackTimeChange,
  source,
}: {
  onPlaybackTimeChange?: (currentMs: number) => void
  source: VideoSource
}) {
  const player = useVideoPlayer(source)

  useEffect(() => {
    if (!onPlaybackTimeChange) return undefined
    player.timeUpdateEventInterval = 0.5
    const subscription = player.addListener("timeUpdate", ({ currentTime }) => {
      if (!Number.isFinite(currentTime)) return
      onPlaybackTimeChange(Math.max(0, Math.floor(currentTime * 1000)))
    })
    return () => {
      subscription.remove()
      player.timeUpdateEventInterval = 0
    }
  }, [onPlaybackTimeChange, player])

  return (
    <View style={styles.shell}>
      <VideoView contentFit="contain" nativeControls player={player} style={styles.video} />
    </View>
  )
}

const styles = StyleSheet.create({
  shell: { backgroundColor: "#020617", borderRadius: 8, overflow: "hidden" },
  video: { aspectRatio: 16 / 9, width: "100%" },
})
```

- [ ] **Step 4: Update current-change**

Update `docs/current-change.md` with this task's files and verification result. The committed file must not contain angle-bracket placeholders.

- [ ] **Step 5: Verify green**

Run:

```powershell
pnpm --dir mobile test -- learning-object-detail.test.tsx
pnpm --dir mobile typecheck
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add mobile/src/screens/LearningMediaPlayer.tsx mobile/__tests__/learning-object-detail.test.tsx docs/current-change.md
git commit -m "feat: report mobile playback time"
```

---

### Task 4: Build Mobile Workbench Presentational Screen

**Files:**
- Create: `mobile/src/screens/MobileWorkbenchScreen.tsx`
- Create: `mobile/__tests__/mobile-workbench-screen.test.tsx`
- Modify: `docs/current-change.md`

- [ ] **Step 1: Write failing screen tests**

Create `mobile/__tests__/mobile-workbench-screen.test.tsx`:

```tsx
import { fireEvent, render } from "@testing-library/react-native"

import type { LearningObjectNode } from "../src/api/learningObjects"
import type { PlaybackDescriptor } from "../src/api/media"
import type { RecallPoint } from "../src/api/review"
import { MobileWorkbenchScreen } from "../src/screens/MobileWorkbenchScreen"
import type { MobileRecallDraft } from "../src/workbench/recallDrafts"

jest.mock("../src/screens/LearningMediaPlayer", () => {
  const React = require("react")
  const { Text } = require("react-native")
  return {
    LearningMediaPlayer: ({ onPlaybackTimeChange }: { onPlaybackTimeChange?: (currentMs: number) => void }) =>
      React.createElement(Text, { onPress: () => onPlaybackTimeChange?.(15000) }, "MockPlayer"),
  }
})

const nodes: LearningObjectNode[] = [
  { kind: "container", projectId: "proj_1", nodeId: "root", parentId: null, children: ["node_1"], title: "课程" },
  { kind: "leaf", projectId: "proj_1", nodeId: "node_1", parentId: "root", instanceId: "inst_1", title: "第一课" },
  { kind: "leaf", projectId: "proj_1", nodeId: "node_2", parentId: "root", instanceId: "inst_2", title: "第二课" },
]

const playback: PlaybackDescriptor = {
  instanceId: "inst_1",
  sourceKind: "SERVER_FS",
  playbackKind: "FILE",
  url: "/media",
  mimeType: "video/mp4",
  durationMs: null,
  supportsFrameGrab: false,
  supportsServerAsr: false,
}

const recallPoint: RecallPoint = {
  projectId: "proj_1",
  recallPointId: "rp_1",
  createdAt: "2026-05-18T00:00:00Z",
  state: "ACTIVE",
  deletedAt: null,
  question: [{ kind: "TEXT", text: "题面" }],
  answer: [{ kind: "TEXT", text: "答案" }],
  anchor: { instanceId: "inst_1", position: "t=1000" },
  references: [],
  insights: [],
}

const draft: MobileRecallDraft = {
  localId: "draft_1",
  instanceId: "inst_1",
  position: "t=15000",
  questionText: "草稿题面",
  answerText: "草稿答案",
  createdAt: 1710000000000,
  updatedAt: 1710000000000,
}

describe("MobileWorkbenchScreen", () => {
  it("renders the active learning object, media, recall points, and drafts", () => {
    const screen = render(
      <MobileWorkbenchScreen
        activeNode={nodes[1]}
        apiBaseUrl="https://plm.xuebao.chat/api"
        currentMs={15000}
        drafts={[draft]}
        errorMessage={null}
        loading={false}
        nodes={nodes}
        onAddDraft={() => undefined}
        onPlaybackTimeChange={() => undefined}
        onRemoveDraft={() => undefined}
        onSelectNode={() => undefined}
        onSubmitDrafts={() => undefined}
        onUpdateDraft={() => undefined}
        openReviewQueue={() => undefined}
        playback={playback}
        playbackErrorMessage={null}
        playbackLoading={false}
        recallPoints={[recallPoint]}
        recallPointsErrorMessage={null}
        recallPointsLoading={false}
        reviewHeadId={null}
        reviewQueueLoading={false}
        sessionCookie="plm_session=abc"
        submitting={false}
      />,
    )

    expect(screen.getByText("第一课")).toBeTruthy()
    expect(screen.getByText("MockPlayer")).toBeTruthy()
    expect(screen.getByText("题面")).toBeTruthy()
    expect(screen.getByDisplayValue("草稿题面")).toBeTruthy()
    expect(screen.getByDisplayValue("草稿答案")).toBeTruthy()
  })

  it("opens the directory and selects a leaf node", () => {
    const onSelectNode = jest.fn()
    const screen = render(
      <MobileWorkbenchScreen
        activeNode={nodes[1]}
        apiBaseUrl="https://plm.xuebao.chat/api"
        currentMs={0}
        drafts={[]}
        errorMessage={null}
        loading={false}
        nodes={nodes}
        onAddDraft={() => undefined}
        onPlaybackTimeChange={() => undefined}
        onRemoveDraft={() => undefined}
        onSelectNode={onSelectNode}
        onSubmitDrafts={() => undefined}
        onUpdateDraft={() => undefined}
        openReviewQueue={() => undefined}
        playback={playback}
        playbackErrorMessage={null}
        playbackLoading={false}
        recallPoints={[]}
        recallPointsErrorMessage={null}
        recallPointsLoading={false}
        reviewHeadId={null}
        reviewQueueLoading={false}
        sessionCookie={null}
        submitting={false}
      />,
    )

    fireEvent.press(screen.getByText("目录"))
    fireEvent.press(screen.getByText("第二课"))

    expect(onSelectNode).toHaveBeenCalledWith(nodes[2])
  })

  it("keeps drafts but blocks submit when review gate is active", () => {
    const onSubmitDrafts = jest.fn()
    const screen = render(
      <MobileWorkbenchScreen
        activeNode={nodes[1]}
        apiBaseUrl="https://plm.xuebao.chat/api"
        currentMs={0}
        drafts={[draft]}
        errorMessage={null}
        loading={false}
        nodes={nodes}
        onAddDraft={() => undefined}
        onPlaybackTimeChange={() => undefined}
        onRemoveDraft={() => undefined}
        onSelectNode={() => undefined}
        onSubmitDrafts={onSubmitDrafts}
        onUpdateDraft={() => undefined}
        openReviewQueue={() => undefined}
        playback={playback}
        playbackErrorMessage={null}
        playbackLoading={false}
        recallPoints={[]}
        recallPointsErrorMessage={null}
        recallPointsLoading={false}
        reviewHeadId="task_1"
        reviewQueueLoading={false}
        sessionCookie={null}
        submitting={false}
      />,
    )

    expect(screen.getByText("先完成复习")).toBeTruthy()
    fireEvent.press(screen.getByText("提交学习"))

    expect(onSubmitDrafts).not.toHaveBeenCalled()
  })

  it("exposes add draft and playback time callbacks", () => {
    const onAddDraft = jest.fn()
    const onPlaybackTimeChange = jest.fn()
    const screen = render(
      <MobileWorkbenchScreen
        activeNode={nodes[1]}
        apiBaseUrl="https://plm.xuebao.chat/api"
        currentMs={0}
        drafts={[]}
        errorMessage={null}
        loading={false}
        nodes={nodes}
        onAddDraft={onAddDraft}
        onPlaybackTimeChange={onPlaybackTimeChange}
        onRemoveDraft={() => undefined}
        onSelectNode={() => undefined}
        onSubmitDrafts={() => undefined}
        onUpdateDraft={() => undefined}
        openReviewQueue={() => undefined}
        playback={playback}
        playbackErrorMessage={null}
        playbackLoading={false}
        recallPoints={[]}
        recallPointsErrorMessage={null}
        recallPointsLoading={false}
        reviewHeadId={null}
        reviewQueueLoading={false}
        sessionCookie={null}
        submitting={false}
      />,
    )

    fireEvent.press(screen.getByText("MockPlayer"))
    fireEvent.press(screen.getByText("记复述点"))

    expect(onPlaybackTimeChange).toHaveBeenCalledWith(15000)
    expect(onAddDraft).toHaveBeenCalled()
  })

  it("blocks submit while the review gate is still loading", () => {
    const onSubmitDrafts = jest.fn()
    const screen = render(
      <MobileWorkbenchScreen
        activeNode={nodes[1]}
        apiBaseUrl="https://plm.xuebao.chat/api"
        currentMs={15000}
        drafts={[draft]}
        errorMessage={null}
        loading={false}
        nodes={nodes}
        onAddDraft={() => undefined}
        onPlaybackTimeChange={() => undefined}
        onRemoveDraft={() => undefined}
        onSelectNode={() => undefined}
        onSubmitDrafts={onSubmitDrafts}
        onUpdateDraft={() => undefined}
        openReviewQueue={() => undefined}
        playback={playback}
        playbackErrorMessage={null}
        playbackLoading={false}
        recallPoints={[]}
        recallPointsErrorMessage={null}
        recallPointsLoading={false}
        reviewHeadId={null}
        reviewQueueLoading={true}
        sessionCookie={null}
        submitting={false}
      />,
    )

    fireEvent.press(screen.getByText("提交学习"))

    expect(onSubmitDrafts).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Verify the tests fail**

Run:

```powershell
pnpm --dir mobile test -- mobile-workbench-screen.test.tsx
```

Expected: FAIL because `MobileWorkbenchScreen` does not exist.

- [ ] **Step 3: Add the presentational screen**

Create `mobile/src/screens/MobileWorkbenchScreen.tsx`:

```tsx
import { useMemo, useState } from "react"
import { Pressable, StyleSheet, Text, View } from "react-native"

import type { LearningObjectNode } from "../api/learningObjects"
import type { PlaybackDescriptor } from "../api/media"
import { richContentToPlainText } from "../api/richContent"
import type { RecallPoint } from "../api/review"
import { AppButton } from "../components/AppButton"
import { AppTextInput } from "../components/AppTextInput"
import { EmptyState } from "../components/EmptyState"
import { LoadingState } from "../components/LoadingState"
import { Screen } from "../components/Screen"
import type { MobileRecallDraft } from "../workbench/recallDrafts"
import { getIncompleteDraftReason } from "../workbench/recallDrafts"
import { LearningMediaPlayer } from "./LearningMediaPlayer"

export type MobileWorkbenchScreenProps = {
  activeNode: LearningObjectNode | null
  apiBaseUrl: string
  currentMs: number
  drafts: MobileRecallDraft[]
  errorMessage?: string | null
  loading: boolean
  nodes: LearningObjectNode[]
  onAddDraft: () => void
  onPlaybackTimeChange: (currentMs: number) => void
  onRemoveDraft: (localId: string) => void
  onSelectNode: (node: LearningObjectNode) => void
  onSubmitDrafts: () => void
  onUpdateDraft: (localId: string, patch: Partial<Pick<MobileRecallDraft, "answerText" | "questionText">>) => void
  openReviewQueue: () => void
  playback: PlaybackDescriptor | null
  playbackErrorMessage?: string | null
  playbackLoading: boolean
  recallPoints: RecallPoint[]
  recallPointsErrorMessage?: string | null
  recallPointsLoading: boolean
  reviewHeadId: string | null
  reviewQueueLoading: boolean
  sessionCookie?: string | null
  submitting: boolean
}

export function MobileWorkbenchScreen(props: MobileWorkbenchScreenProps) {
  const [directoryOpen, setDirectoryOpen] = useState(false)
  const leafNodes = useMemo(() => props.nodes.filter((node) => node.kind === "leaf"), [props.nodes])
  const activeLeaf = props.activeNode?.kind === "leaf" ? props.activeNode : null
  const firstIncompleteReason = props.drafts.map(getIncompleteDraftReason).find((reason): reason is string => Boolean(reason))
  const canSubmit =
    props.drafts.length > 0 &&
    !props.reviewQueueLoading &&
    !props.reviewHeadId &&
    !firstIncompleteReason &&
    !props.submitting

  if (props.loading) {
    return (
      <Screen scroll={false}>
        <LoadingState label="加载工作台" />
      </Screen>
    )
  }

  if (props.errorMessage) {
    return (
      <Screen>
        <EmptyState title={props.errorMessage} />
      </Screen>
    )
  }

  if (!activeLeaf) {
    return (
      <Screen>
        <Text style={styles.title}>工作台</Text>
        <EmptyState title={leafNodes.length === 0 ? "暂无可学习内容" : "请选择学习内容"} />
        {leafNodes.length > 0 ? (
          <DirectoryList activeNodeId={null} nodes={props.nodes} onSelectNode={props.onSelectNode} />
        ) : null}
      </Screen>
    )
  }

  function submitDrafts() {
    if (!canSubmit) return
    props.onSubmitDrafts()
  }

  return (
    <Screen>
      <View style={styles.header}>
        <Text style={styles.title}>{activeLeaf.title}</Text>
        <Text style={styles.meta}>当前锚点 {formatMs(props.currentMs)}</Text>
      </View>

      <LearningMediaPlayer
        apiBaseUrl={props.apiBaseUrl}
        descriptor={props.playback}
        errorMessage={props.playbackErrorMessage}
        loading={props.playbackLoading}
        onPlaybackTimeChange={props.onPlaybackTimeChange}
        sessionCookie={props.sessionCookie}
        title={activeLeaf.title}
      />

      <View style={styles.actions}>
        <AppButton label="目录" onPress={() => setDirectoryOpen((current) => !current)} />
        <AppButton label="复习" onPress={props.openReviewQueue} />
      </View>

      {directoryOpen ? (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>目录</Text>
          <DirectoryList activeNodeId={activeLeaf.nodeId} nodes={props.nodes} onSelectNode={props.onSelectNode} />
        </View>
      ) : null}

      {props.reviewHeadId ? (
        <View style={styles.notice}>
          <Text style={styles.noticeText}>先完成复习</Text>
        </View>
      ) : null}

      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>复述点</Text>
          <AppButton label="记复述点" onPress={props.onAddDraft} />
        </View>
        {props.recallPointsLoading ? <LoadingState label="加载复述点" /> : null}
        {props.recallPointsErrorMessage ? <EmptyState title={props.recallPointsErrorMessage} /> : null}
        {!props.recallPointsLoading && !props.recallPointsErrorMessage && props.recallPoints.length === 0 ? (
          <EmptyState title="暂无复述点" />
        ) : null}
        {!props.recallPointsLoading && !props.recallPointsErrorMessage ? (
          <View style={styles.list}>
            {props.recallPoints.map((item) => (
              <View key={item.recallPointId} style={styles.row}>
                <Text style={styles.question}>{richContentToPlainText(item.question) || "题面为空"}</Text>
                <Text style={styles.answer}>{richContentToPlainText(item.answer) || "答案为空"}</Text>
              </View>
            ))}
          </View>
        ) : null}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>草稿</Text>
        {props.drafts.length === 0 ? <EmptyState title="暂无草稿" /> : null}
        <View style={styles.list}>
          {props.drafts.map((draft, index) => (
            <View key={draft.localId} style={styles.draft}>
              <View style={styles.draftHeader}>
                <Text style={styles.draftTitle}>草稿 {index + 1}</Text>
                <Pressable accessibilityRole="button" onPress={() => props.onRemoveDraft(draft.localId)}>
                  <Text style={styles.removeText}>删除</Text>
                </Pressable>
              </View>
              <Text style={styles.meta}>{draft.position}</Text>
              <AppTextInput
                multiline
                onChangeText={(text) => props.onUpdateDraft(draft.localId, { questionText: text })}
                placeholder="题面"
                value={draft.questionText}
              />
              <AppTextInput
                multiline
                onChangeText={(text) => props.onUpdateDraft(draft.localId, { answerText: text })}
                placeholder="答案"
                value={draft.answerText}
              />
            </View>
          ))}
        </View>
        {firstIncompleteReason ? <Text style={styles.meta}>{firstIncompleteReason}</Text> : null}
        <AppButton disabled={!canSubmit} label={props.submitting ? "提交中" : "提交学习"} onPress={submitDrafts} />
      </View>
    </Screen>
  )
}

function DirectoryList({
  activeNodeId,
  nodes,
  onSelectNode,
}: {
  activeNodeId: string | null
  nodes: LearningObjectNode[]
  onSelectNode: (node: LearningObjectNode) => void
}) {
  return (
    <View style={styles.list}>
      {nodes.map((node) => {
        const isLeaf = node.kind === "leaf"
        const active = node.nodeId === activeNodeId
        return (
          <Pressable
            disabled={!isLeaf}
            key={node.nodeId}
            onPress={() => onSelectNode(node)}
            style={[styles.row, !isLeaf && styles.containerRow, active && styles.activeRow]}
          >
            <Text style={[styles.rowTitle, active && styles.activeText]}>{node.title}</Text>
            <Text style={styles.meta}>{isLeaf ? "内容" : "目录"}</Text>
          </Pressable>
        )
      })}
    </View>
  )
}

function formatMs(ms: number) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${String(seconds).padStart(2, "0")}`
}

const styles = StyleSheet.create({
  actions: { flexDirection: "row", gap: 10 },
  activeRow: { backgroundColor: "#e0f2fe" },
  activeText: { color: "#0369a1", fontWeight: "700" },
  answer: { color: "#475569", fontSize: 13, lineHeight: 19 },
  containerRow: { opacity: 0.62 },
  draft: { backgroundColor: "#ffffff", borderColor: "#e2e8f0", borderRadius: 8, borderWidth: 1, gap: 10, padding: 12 },
  draftHeader: { alignItems: "center", flexDirection: "row", justifyContent: "space-between" },
  draftTitle: { color: "#0f172a", fontSize: 15, fontWeight: "700" },
  header: { gap: 4 },
  list: { gap: 0 },
  meta: { color: "#64748b", fontSize: 12 },
  notice: { backgroundColor: "#fff7ed", borderColor: "#fed7aa", borderRadius: 8, borderWidth: 1, padding: 12 },
  noticeText: { color: "#9a3412", fontSize: 14, fontWeight: "700" },
  question: { color: "#0f172a", fontSize: 15 },
  removeText: { color: "#b91c1c", fontSize: 13, fontWeight: "700" },
  row: { borderBottomColor: "#e2e8f0", borderBottomWidth: 1, gap: 4, paddingHorizontal: 8, paddingVertical: 14 },
  rowTitle: { color: "#0f172a", fontSize: 16 },
  section: { gap: 10 },
  sectionHeader: { gap: 10 },
  sectionTitle: { color: "#0f172a", fontSize: 18, fontWeight: "700" },
  title: { color: "#0f172a", fontSize: 24, fontWeight: "700" },
})
```

- [ ] **Step 4: Update current-change**

Update `docs/current-change.md` with this task's files and verification result. The committed file must not contain angle-bracket placeholders.

- [ ] **Step 5: Verify green**

Run:

```powershell
pnpm --dir mobile test -- mobile-workbench-screen.test.tsx
pnpm --dir mobile typecheck
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add mobile/src/screens/MobileWorkbenchScreen.tsx mobile/__tests__/mobile-workbench-screen.test.tsx docs/current-change.md
git commit -m "feat: add mobile workbench screen"
```

---

### Task 5: Wire Project Route To Native Workbench

**Files:**
- Modify: `mobile/src/app/project/[subjectId]/[scopedProjectId].tsx`
- Modify: `mobile/__tests__/learning-navigation.test.tsx`
- Create: `mobile/__tests__/project-route-workbench.test.tsx`
- Modify: `docs/current-change.md`

- [ ] **Step 1: Add route-supporting navigation test**

Replace `mobile/__tests__/learning-navigation.test.tsx` with:

```tsx
import { render } from "@testing-library/react-native"

import { ProjectScreen } from "../src/screens/ProjectScreen"

describe("ProjectScreen", () => {
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

  it("renders a load error instead of an empty list", () => {
    const screen = render(<ProjectScreen errorMessage="加载失败" loading={false} nodes={[]} openNode={() => undefined} />)

    expect(screen.getByText("加载失败")).toBeTruthy()
  })
})
```

This keeps the old list component covered. The actual route integration is verified by `project-route-workbench.test.tsx`.

- [ ] **Step 2: Add failing route integration test**

Create `mobile/__tests__/project-route-workbench.test.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { fireEvent, render, waitFor } from "@testing-library/react-native"
import type { ReactNode } from "react"

import { ApiProvider } from "../src/api/ApiProvider"
import type { LearningObjectNode } from "../src/api/learningObjects"
import type { PlaybackDescriptor } from "../src/api/media"
import type { RecallPoint } from "../src/api/review"
import type { createLearningPyramidApi } from "../src/api/types"
import ProjectRoute from "../src/app/project/[subjectId]/[scopedProjectId]"

const mockRouterPush = jest.fn()

jest.mock("expo-router", () => ({
  router: { push: (...args: unknown[]) => mockRouterPush(...args) },
  useLocalSearchParams: () => ({ subjectId: "subj_1", scopedProjectId: "proj_1" }),
}))

jest.mock("../src/screens/MobileWorkbenchScreen", () => {
  const React = require("react")
  const { Text, TextInput, View } = require("react-native")

  return {
    MobileWorkbenchScreen: (props: {
      activeNode: LearningObjectNode | null
      drafts: Array<{ localId: string; questionText: string; answerText: string }>
      onAddDraft: () => void
      onPlaybackTimeChange: (currentMs: number) => void
      onSubmitDrafts: () => void
      onUpdateDraft: (localId: string, patch: { questionText?: string; answerText?: string }) => void
      reviewHeadId: string | null
      reviewQueueLoading: boolean
    }) =>
      React.createElement(
        View,
        null,
        React.createElement(Text, null, `active:${props.activeNode?.title ?? "none"}`),
        React.createElement(Text, null, `drafts:${props.drafts.length}`),
        React.createElement(Text, null, `review:${props.reviewQueueLoading ? "loading" : props.reviewHeadId ?? "none"}`),
        React.createElement(Text, { onPress: () => props.onPlaybackTimeChange(12000) }, "set time"),
        React.createElement(Text, { onPress: props.onAddDraft }, "add draft"),
        props.drafts.map((draft) =>
          React.createElement(
            View,
            { key: draft.localId },
            React.createElement(TextInput, {
              accessibilityLabel: `question-${draft.localId}`,
              onChangeText: (text: string) => props.onUpdateDraft(draft.localId, { questionText: text }),
              value: draft.questionText,
            }),
            React.createElement(TextInput, {
              accessibilityLabel: `answer-${draft.localId}`,
              onChangeText: (text: string) => props.onUpdateDraft(draft.localId, { answerText: text }),
              value: draft.answerText,
            }),
          ),
        ),
        React.createElement(Text, { onPress: props.onSubmitDrafts }, "submit drafts"),
      ),
  }
})

const nodes: LearningObjectNode[] = [
  { kind: "container", projectId: "proj_1", nodeId: "root", parentId: null, children: ["node_1"], title: "课程" },
  { kind: "leaf", projectId: "proj_1", nodeId: "node_1", parentId: "root", instanceId: "inst_1", title: "第一课" },
]

const playback: PlaybackDescriptor = {
  instanceId: "inst_1",
  sourceKind: "SERVER_FS",
  playbackKind: "FILE",
  url: "/media",
  mimeType: "video/mp4",
  durationMs: null,
  supportsFrameGrab: false,
  supportsServerAsr: false,
}

function createApi() {
  return {
    auth: {},
    learningObjects: {
      getNode: jest.fn(),
      listNodes: jest.fn(async () => nodes),
      listRecallPointsByNode: jest.fn(async () => [] as RecallPoint[]),
    },
    learningTasks: {
      submitLearningTask: jest.fn(async () => ({ entryNodeId: "entry_1" })),
    },
    media: {
      getPlayback: jest.fn(async () => playback),
    },
    review: {
      commitReviewTask: jest.fn(),
      getQueue: jest.fn(async () => ({ headId: null, ids: [] })),
      getRangeSnapshot: jest.fn(),
      getReviewTask: jest.fn(),
      listRecallPoints: jest.fn(),
      listRecommendations: jest.fn(),
    },
    subjects: {},
  } as unknown as ReturnType<typeof createLearningPyramidApi>
}

function renderRoute(api = createApi()) {
  const queryClient = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
      queries: { retry: false },
    },
  })
  const invalidateQueries = jest.spyOn(queryClient, "invalidateQueries")

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <ApiProvider api={api} apiBaseUrl="https://plm.xuebao.chat/api" getSessionCookie={() => "plm_session=abc"}>
          {children}
        </ApiProvider>
      </QueryClientProvider>
    )
  }

  return { api, invalidateQueries, ...render(<ProjectRoute />, { wrapper: Wrapper }) }
}

describe("ProjectRoute mobile workbench", () => {
  beforeEach(() => {
    jest.clearAllMocks()
  })

  it("submits current learning object drafts and invalidates affected queries", async () => {
    const screen = renderRoute()

    await waitFor(() => expect(screen.getByText("active:第一课")).toBeTruthy())
    await waitFor(() => expect(screen.getByText("review:none")).toBeTruthy())

    fireEvent.press(screen.getByText("set time"))
    fireEvent.press(screen.getByText("add draft"))
    await waitFor(() => expect(screen.getByText("drafts:1")).toBeTruthy())

    fireEvent.changeText(screen.getByLabelText(/question-/), "题面")
    fireEvent.changeText(screen.getByLabelText(/answer-/), "答案")
    fireEvent.press(screen.getByText("submit drafts"))

    await waitFor(() =>
      expect(screen.api.learningTasks.submitLearningTask).toHaveBeenCalledWith(
        { subjectId: "subj_1", scopedProjectId: "proj_1" },
        {
          title: "第一课",
          items: [
            {
              question: [{ kind: "TEXT", text: "题面" }],
              answer: [{ kind: "TEXT", text: "答案" }],
              anchor: { instanceId: "inst_1", position: "t=12000" },
              references: [],
            },
          ],
        },
      ),
    )
    await waitFor(() => expect(screen.getByText("drafts:0")).toBeTruthy())
    expect(screen.invalidateQueries).toHaveBeenCalledWith({ queryKey: ["review-queue", "subj_1", "proj_1"] })
    expect(screen.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["learning-object-recall-points", "subj_1", "proj_1", "node_1"],
    })
    expect(screen.invalidateQueries).toHaveBeenCalledWith({ queryKey: ["review-recall-points", "subj_1", "proj_1"] })
    expect(screen.invalidateQueries).toHaveBeenCalledWith({ queryKey: ["learning-object-nodes", "subj_1", "proj_1"] })
  })
})
```

- [ ] **Step 3: Verify route test fails before route wiring**

Run:

```powershell
pnpm --dir mobile test -- learning-navigation.test.tsx project-route-workbench.test.tsx mobile-workbench-screen.test.tsx workbench-drafts.test.ts domain-api.test.ts
```

Expected: FAIL because the project route still renders `ProjectScreen` and does not expose the mocked `MobileWorkbenchScreen` flow.

- [ ] **Step 4: Replace the project route**

Replace `mobile/src/app/project/[subjectId]/[scopedProjectId].tsx` with:

```tsx
import { useEffect, useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { router, useLocalSearchParams } from "expo-router"

import { useApiRuntime, useLearningPyramidApi } from "../../../api/ApiProvider"
import { toErrorMessage } from "../../../api/errorMessage"
import type { LearningObjectNode } from "../../../api/learningObjects"
import { firstRouteParam } from "../../../routing/params"
import { MobileWorkbenchScreen } from "../../../screens/MobileWorkbenchScreen"
import {
  buildSubmitLearningTaskItems,
  createRecallDraft,
  type MobileRecallDraft,
} from "../../../workbench/recallDrafts"

function createLocalId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}_${Math.random().toString(16).slice(2)}`
}

function firstLeaf(nodes: LearningObjectNode[]) {
  return nodes.find((node) => node.kind === "leaf") ?? null
}

export default function ProjectRoute() {
  const api = useLearningPyramidApi()
  const runtime = useApiRuntime()
  const queryClient = useQueryClient()
  const params = useLocalSearchParams<{ subjectId: string; scopedProjectId: string }>()
  const subjectId = firstRouteParam(params.subjectId) ?? ""
  const scopedProjectId = firstRouteParam(params.scopedProjectId) ?? ""
  const scope = useMemo(() => ({ subjectId, scopedProjectId }), [scopedProjectId, subjectId])
  const hasScope = Boolean(subjectId && scopedProjectId)
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null)
  const [currentMs, setCurrentMs] = useState(0)
  const [drafts, setDrafts] = useState<MobileRecallDraft[]>([])

  const nodesQ = useQuery({
    queryKey: ["learning-object-nodes", subjectId, scopedProjectId],
    queryFn: () => api.learningObjects.listNodes(scope),
    enabled: hasScope,
  })

  const nodes = nodesQ.data ?? []
  const activeNode = useMemo(() => {
    if (activeNodeId) {
      const selected = nodes.find((node) => node.nodeId === activeNodeId)
      if (selected?.kind === "leaf") return selected
    }
    return firstLeaf(nodes)
  }, [activeNodeId, nodes])
  const activeInstanceId = activeNode?.kind === "leaf" ? activeNode.instanceId : ""

  useEffect(() => {
    if (!activeNodeId && activeNode?.kind === "leaf") setActiveNodeId(activeNode.nodeId)
  }, [activeNode, activeNodeId])

  const queueQ = useQuery({
    queryKey: ["review-queue", subjectId, scopedProjectId],
    queryFn: () => api.review.getQueue(scope),
    enabled: hasScope,
  })

  const playbackQ = useQuery({
    queryKey: ["learning-object-playback", subjectId, scopedProjectId, activeInstanceId],
    queryFn: () => api.media.getPlayback(scope, activeInstanceId),
    enabled: hasScope && Boolean(activeInstanceId),
  })

  const recallPointsQ = useQuery({
    queryKey: ["learning-object-recall-points", subjectId, scopedProjectId, activeNode?.nodeId ?? ""],
    queryFn: () => api.learningObjects.listRecallPointsByNode(scope, activeNode?.nodeId ?? ""),
    enabled: hasScope && Boolean(activeNode?.nodeId),
  })

  const submitLearningTask = useMutation({
    mutationFn: (input: { nodeId: string; instanceId: string; title: string; drafts: MobileRecallDraft[] }) =>
      api.learningTasks.submitLearningTask(scope, {
        title: input.title,
        items: buildSubmitLearningTaskItems(input.drafts),
      }),
    onSuccess: async (_result, variables) => {
      setDrafts((current) => current.filter((draft) => draft.instanceId !== variables.instanceId))
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["review-queue", subjectId, scopedProjectId] }),
        queryClient.invalidateQueries({ queryKey: ["learning-object-recall-points", subjectId, scopedProjectId, variables.nodeId] }),
        queryClient.invalidateQueries({ queryKey: ["review-recall-points", subjectId, scopedProjectId] }),
        queryClient.invalidateQueries({ queryKey: ["learning-object-nodes", subjectId, scopedProjectId] }),
      ])
    },
  })

  const activeDrafts = drafts.filter((draft) => draft.instanceId === activeInstanceId)
  const loading = nodesQ.isLoading
  const errorMessage =
    (nodesQ.isError ? toErrorMessage(nodesQ.error, "学习对象加载失败") : null) ??
    (queueQ.isError ? toErrorMessage(queueQ.error, "复习队列加载失败") : null) ??
    (submitLearningTask.isError ? toErrorMessage(submitLearningTask.error, "学习提交失败") : null)

  function addDraft() {
    if (!activeInstanceId) return
    const now = Date.now()
    setDrafts((current) => [
      ...current,
      createRecallDraft({
        instanceId: activeInstanceId,
        currentMs,
        localId: createLocalId(),
        now,
      }),
    ])
  }

  function updateDraft(localId: string, patch: Partial<Pick<MobileRecallDraft, "answerText" | "questionText">>) {
    setDrafts((current) =>
      current.map((draft) =>
        draft.localId === localId
          ? {
              ...draft,
              ...patch,
              updatedAt: Date.now(),
            }
          : draft,
      ),
    )
  }

  function removeDraft(localId: string) {
    setDrafts((current) => current.filter((draft) => draft.localId !== localId))
  }

  function submitDrafts() {
    if (!activeNode || activeNode.kind !== "leaf" || activeDrafts.length === 0 || queueQ.isLoading || queueQ.data?.headId) return
    submitLearningTask.mutate({
      nodeId: activeNode.nodeId,
      instanceId: activeNode.instanceId,
      title: activeNode.title,
      drafts: activeDrafts,
    })
  }

  return (
    <MobileWorkbenchScreen
      activeNode={activeNode}
      apiBaseUrl={runtime.apiBaseUrl}
      currentMs={currentMs}
      drafts={activeDrafts}
      errorMessage={errorMessage}
      loading={loading}
      nodes={nodes}
      onAddDraft={addDraft}
      onPlaybackTimeChange={setCurrentMs}
      onRemoveDraft={removeDraft}
      onSelectNode={(node) => {
        if (node.kind !== "leaf") return
        setActiveNodeId(node.nodeId)
        setCurrentMs(0)
      }}
      onSubmitDrafts={submitDrafts}
      onUpdateDraft={updateDraft}
      openReviewQueue={() =>
        router.push({
          pathname: "/review/[subjectId]/[scopedProjectId]",
          params: { subjectId, scopedProjectId },
        })
      }
      playback={playbackQ.data ?? null}
      playbackErrorMessage={playbackQ.isError ? toErrorMessage(playbackQ.error, "媒体加载失败") : null}
      playbackLoading={playbackQ.isLoading}
      recallPoints={recallPointsQ.data ?? []}
      recallPointsErrorMessage={recallPointsQ.isError ? toErrorMessage(recallPointsQ.error, "复述点加载失败") : null}
      recallPointsLoading={recallPointsQ.isLoading}
      reviewHeadId={queueQ.data?.headId ?? null}
      reviewQueueLoading={queueQ.isLoading}
      sessionCookie={runtime.getSessionCookie()}
      submitting={submitLearningTask.isPending}
    />
  )
}
```

- [ ] **Step 5: Update current-change**

Update `docs/current-change.md` with this task's files and verification result. The committed file must not contain angle-bracket placeholders.

- [ ] **Step 6: Verify green**

Run:

```powershell
pnpm --dir mobile test -- learning-navigation.test.tsx project-route-workbench.test.tsx mobile-workbench-screen.test.tsx workbench-drafts.test.ts domain-api.test.ts
pnpm --dir mobile typecheck
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```powershell
git add 'mobile/src/app/project/[subjectId]/[scopedProjectId].tsx' mobile/__tests__/learning-navigation.test.tsx mobile/__tests__/project-route-workbench.test.tsx docs/current-change.md
git commit -m "feat: wire mobile project route to workbench"
```

---

### Task 6: Update Mobile Documentation

**Files:**
- Modify: `docs/mobile-client.md`
- Modify: `docs/current-change.md`

- [ ] **Step 1: Update `docs/mobile-client.md`**

Edit the "当前仓库已包含 `mobile/` Expo 应用预览。当前实现包含：" list so it contains:

```markdown
- 登录、会话恢复和退出。
- 学科列表和材料列表。
- scoped project 原生移动工作台：默认进入当前学习对象，支持目录切换、已有复述点查看、文本复述点草稿和 `learning task` 提交。
- 后端 playback descriptor 媒体播放；当前移动端明确不支持 `NATIVE_LOCAL`、`BROWSER_LOCAL` 和 `MANUAL` 播放来源。
- 队列头复习任务展示和基础 `canRecall` 提交。
- 移动端 API client、认证状态、领域 API、导航、工作台、媒体、草稿和复习队列测试。
```

Edit "功能边界" so it includes:

```markdown
第一版移动端工作台按桌面/网页工作台语义实现学习主流程：

- 登录、获取当前用户、退出。
- 学科和材料项目列表。
- 进入学科材料对应的 scoped project。
- 在项目内默认进入学习优先工作台，而不是只停留在对象列表。
- 通过目录切换当前学习对象。
- 获取已有课程视频或音频播放描述符并播放。
- 查看当前学习对象已有复述点。
- 新建文本复述点草稿，并按当前播放时间生成 `t=<毫秒>` 锚点。
- 将当前学习对象的草稿提交为一个 `learning task`。
- 队列非空时先进入复习门禁，提交基础复习结果。
```

Add this paragraph under "工程边界":

```markdown
移动端原生工作台不从 `frontend/` 复用 React DOM 工作台组件，但功能语义以桌面/网页工作台为准：目录选内容、播放器学习、复述点草稿、提交 `learning task`、复习门禁。移动端只改变交互布局，不新增移动端专用学习协议。
```

- [ ] **Step 2: Finalize `docs/current-change.md`**

Replace `docs/current-change.md` with a concise final state for this implementation. It must list all files changed across Tasks 1-6, behavior changes, verification results, known risks, and pollution risk checks. Do not include task-by-task logs.

- [ ] **Step 3: Verify docs formatting**

Run:

```powershell
git diff --check -- docs/mobile-client.md docs/current-change.md
```

Expected: PASS.

- [ ] **Step 4: Commit**

Run:

```powershell
git add docs/mobile-client.md docs/current-change.md
git commit -m "docs: update mobile workbench docs"
```

---

### Task 7: Final Verification

**Files:**
- Modify only if verification exposes a real issue in files changed by Tasks 1-6.

- [ ] **Step 1: Run full mobile automated checks**

Run:

```powershell
pnpm --dir mobile test
pnpm --dir mobile typecheck
pnpm --dir mobile exec expo --version
git diff --check -- docs/mobile-client.md docs/current-change.md mobile
```

Expected:

- Jest PASS.
- TypeScript PASS.
- Expo CLI prints a version.
- `git diff --check` exits 0.

- [ ] **Step 2: Run Android smoke when a device is available**

Run:

```powershell
adb devices
```

If a device or emulator is listed, run:

```powershell
$env:EXPO_PUBLIC_API_BASE_URL = "https://plm.xuebao.chat/api"
pnpm --dir mobile android
```

Smoke expected:

- App opens to login or restored session.
- Login works.
- Opening a material enters the native workbench.
- Current learning object title and player area render.
- Directory can switch to another leaf node.
- "记复述点" creates a text draft anchored to current playback time.
- Completed draft submits as a learning task when review queue is empty.
- When review queue is non-empty, submit is blocked and review entry remains available.

If `adb` is not available, record in `docs/current-change.md`:

```markdown
- 未运行 Android 启动 smoke，原因：当前环境没有可用 `adb` 设备或模拟器。
```

- [ ] **Step 3: Update `docs/current-change.md` with final verification**

Record exact commands and results. Do not claim Android smoke was run unless it was actually run.

- [ ] **Step 4: Commit verification record if changed**

Run:

```powershell
git add docs/current-change.md
git commit -m "docs: record mobile workbench verification"
```

If `docs/current-change.md` already contains the final verification from Task 6 and no file changed, do not create an empty commit.

## Completion Criteria

- `mobile/` project route opens the native mobile workbench.
- Workbench defaults to a leaf learning object when available.
- Directory switching works without changing backend identity semantics.
- Supported playback descriptors still render through `expo-video`.
- Player reports current time in milliseconds.
- Text recall drafts are created with `t=<毫秒>` anchors.
- Drafts submit through existing `POST /learning-tasks`.
- Review queue gate blocks learning task submit when `headId` exists.
- No backend API, database, deployment, Web/Tauri workbench, fallback, shim, legacy path, or mobile-only protocol is introduced.
- `docs/current-change.md` and `docs/mobile-client.md` reflect the final behavior.

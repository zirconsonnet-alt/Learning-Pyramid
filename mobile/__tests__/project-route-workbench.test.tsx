import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, fireEvent, render, waitFor } from "@testing-library/react-native"
import type { ReactNode } from "react"

import { ApiProvider } from "../src/api/ApiProvider"
import type { LearningObjectNode } from "../src/api/learningObjects"
import type { PlaybackDescriptor } from "../src/api/media"
import type { RecallPoint } from "../src/api/review"
import type { createLearningPyramidApi } from "../src/api/types"
import ProjectRoute from "../src/app/project/[subjectId]/[scopedProjectId]"

const mockRouterPush = jest.fn()
let mockWorkbenchProps: { onSubmitDrafts: () => void } | null = null

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
      nodes: LearningObjectNode[]
      onAddDraft: () => void
      onPlaybackTimeChange: (currentMs: number) => void
      onSelectNode: (node: LearningObjectNode) => void
      onSubmitDrafts: () => void
      onUpdateDraft: (localId: string, patch: { questionText?: string; answerText?: string }) => void
      errorMessage: string | null
      reviewHeadId: string | null
      reviewQueueLoading: boolean
    }) => {
      mockWorkbenchProps = props
      return React.createElement(
        View,
        null,
        React.createElement(Text, null, `active:${props.activeNode?.title ?? "none"}`),
        React.createElement(Text, null, `drafts:${props.drafts.length}`),
        React.createElement(Text, null, `error:${props.errorMessage ?? "none"}`),
        React.createElement(
          Text,
          null,
          `review:${props.reviewQueueLoading ? "loading" : props.reviewHeadId ?? "none"}`,
        ),
        props.nodes.map((node) =>
          React.createElement(Text, { key: node.nodeId, onPress: () => props.onSelectNode(node) }, `node:${node.title}`),
        ),
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
      )
    },
  }
})

const nodes: LearningObjectNode[] = [
  { kind: "container", projectId: "proj_1", nodeId: "root", parentId: null, children: ["node_1"], title: "课程" },
  { kind: "leaf", projectId: "proj_1", nodeId: "node_1", parentId: "root", instanceId: "inst_1", title: "第一课" },
]

const switchedNodes: LearningObjectNode[] = [
  { kind: "container", projectId: "proj_1", nodeId: "root", parentId: null, children: ["node_2"], title: "课程" },
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
      mutations: { gcTime: Infinity, retry: false },
      queries: { gcTime: Infinity, retry: false },
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

  return { api, invalidateQueries, queryClient, ...render(<ProjectRoute />, { wrapper: Wrapper }) }
}

describe("ProjectRoute mobile workbench", () => {
  beforeEach(() => {
    jest.clearAllMocks()
    mockWorkbenchProps = null
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
    screen.unmount()
    screen.queryClient.clear()
  })

  it("does not submit drafts while review queue is refetching", async () => {
    const queueRefetch = { release: null as null | (() => void) }
    const api = createApi()
    ;(api.review.getQueue as jest.Mock)
      .mockResolvedValueOnce({ headId: null, ids: [] })
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            queueRefetch.release = () => resolve({ headId: null, ids: [] })
          }),
      )
    const screen = renderRoute(api)

    await waitFor(() => expect(screen.getByText("active:第一课")).toBeTruthy())
    await waitFor(() => expect(screen.getByText("review:none")).toBeTruthy())
    fireEvent.press(screen.getByText("add draft"))
    await waitFor(() => expect(screen.getByText("drafts:1")).toBeTruthy())
    fireEvent.changeText(screen.getByLabelText(/question-/), "题面")
    fireEvent.changeText(screen.getByLabelText(/answer-/), "答案")

    const submitBeforeRefetch = mockWorkbenchProps?.onSubmitDrafts
    screen.queryClient.invalidateQueries({ queryKey: ["review-queue", "subj_1", "proj_1"] })
    await waitFor(() => expect(api.review.getQueue).toHaveBeenCalledTimes(2))
    await waitFor(() =>
      expect(screen.queryClient.getQueryState(["review-queue", "subj_1", "proj_1"])?.fetchStatus).toBe("fetching"),
    )
    await waitFor(() => expect(mockWorkbenchProps?.onSubmitDrafts).not.toBe(submitBeforeRefetch))
    await act(async () => {
      mockWorkbenchProps?.onSubmitDrafts()
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(screen.api.learningTasks.submitLearningTask).not.toHaveBeenCalled()
    queueRefetch.release?.()
    await waitFor(() => expect(screen.getByText("review:none")).toBeTruthy())
    screen.unmount()
    screen.queryClient.clear()
  })

  it("does not submit drafts when review queue is in error state", async () => {
    const api = createApi()
    ;(api.review.getQueue as jest.Mock)
      .mockResolvedValueOnce({ headId: null, ids: [] })
      .mockRejectedValueOnce(new Error("queue failed"))
    const screen = renderRoute(api)

    await waitFor(() => expect(screen.getByText("active:第一课")).toBeTruthy())
    await waitFor(() => expect(screen.getByText("review:none")).toBeTruthy())
    fireEvent.press(screen.getByText("add draft"))
    await waitFor(() => expect(screen.getByText("drafts:1")).toBeTruthy())
    fireEvent.changeText(screen.getByLabelText(/question-/), "题面")
    fireEvent.changeText(screen.getByLabelText(/answer-/), "答案")

    screen.queryClient.invalidateQueries({ queryKey: ["review-queue", "subj_1", "proj_1"] })
    await waitFor(() => expect(screen.getByText("error:queue failed")).toBeTruthy())
    await act(async () => {
      mockWorkbenchProps?.onSubmitDrafts()
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(screen.api.learningTasks.submitLearningTask).not.toHaveBeenCalled()
    screen.unmount()
    screen.queryClient.clear()
  })

  it("reconciles a missing selected leaf and resets the draft anchor to the new active instance", async () => {
    const api = createApi()
    ;(api.learningObjects.listNodes as jest.Mock).mockResolvedValueOnce(nodes).mockResolvedValueOnce(switchedNodes)
    const screen = renderRoute(api)

    await waitFor(() => expect(screen.getByText("active:第一课")).toBeTruthy())
    fireEvent.press(screen.getByText("set time"))
    screen.queryClient.invalidateQueries({ queryKey: ["learning-object-nodes", "subj_1", "proj_1"] })
    await waitFor(() => expect(screen.getByText("active:第二课")).toBeTruthy())

    fireEvent.press(screen.getByText("add draft"))
    await waitFor(() => expect(screen.getByText("drafts:1")).toBeTruthy())
    fireEvent.changeText(screen.getByLabelText(/question-/), "新题")
    fireEvent.changeText(screen.getByLabelText(/answer-/), "新答")
    fireEvent.press(screen.getByText("submit drafts"))

    await waitFor(() =>
      expect(screen.api.learningTasks.submitLearningTask).toHaveBeenCalledWith(
        { subjectId: "subj_1", scopedProjectId: "proj_1" },
        {
          title: "第二课",
          items: [
            {
              question: [{ kind: "TEXT", text: "新题" }],
              answer: [{ kind: "TEXT", text: "新答" }],
              anchor: { instanceId: "inst_2", position: "t=0" },
              references: [],
            },
          ],
        },
      ),
    )
    screen.unmount()
    screen.queryClient.clear()
  })
})

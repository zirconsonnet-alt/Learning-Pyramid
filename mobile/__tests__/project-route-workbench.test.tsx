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
        React.createElement(
          Text,
          null,
          `review:${props.reviewQueueLoading ? "loading" : props.reviewHeadId ?? "none"}`,
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
})

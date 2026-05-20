import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, fireEvent, render, waitFor } from "@testing-library/react-native"
import type { ReactNode } from "react"

import { ApiProvider } from "../src/api/ApiProvider"
import type { Layer } from "../src/api/layers"
import type { LearningObjectNode } from "../src/api/learningObjects"
import type { LearningTaskNode } from "../src/api/learningTaskNodes"
import type { PlaybackDescriptor } from "../src/api/media"
import type { ProjectConfig } from "../src/api/projectConfig"
import type { RecallPoint, ReviewRecommendationPage } from "../src/api/review"
import type { createLearningPyramidApi } from "../src/api/types"
import ProjectRoute from "../src/app/project/[subjectId]/[scopedProjectId]"
import type { MobileWorkbenchScreenProps, ReviewCommitPayload } from "../src/screens/MobileWorkbenchScreen"

let mockWorkbenchProps: MobileWorkbenchScreenProps | null = null
const mockGetDocumentAsync = jest.fn()

jest.mock("expo-router", () => ({
  useLocalSearchParams: () => ({ subjectId: "subj_1", scopedProjectId: "proj_1" }),
}))

jest.mock("expo-document-picker", () => ({
  getDocumentAsync: (...args: unknown[]) => mockGetDocumentAsync(...args),
}))

jest.mock("../src/auth/AuthProvider", () => ({
  useAuth: () => ({
    signOut: jest.fn(async () => undefined),
    status: "signedIn",
    user: null,
  }),
}))

jest.mock("../src/screens/MobileWorkbenchScreen", () => {
  const React = require("react")
  const { Text, View } = require("react-native")

  return {
    MobileWorkbenchScreen: (props: MobileWorkbenchScreenProps) => {
      mockWorkbenchProps = props
      const firstDraft = props.drafts[0]
      return React.createElement(
        View,
        null,
        React.createElement(Text, null, `active:${props.activeNode?.title ?? "none"}`),
        React.createElement(Text, null, `drafts:${props.drafts.length}`),
        React.createElement(Text, null, `title:${props.taskTitle}`),
        React.createElement(Text, null, `review:${props.reviewTaskId ?? "none"}`),
        React.createElement(Text, null, `layers:${props.layers.length}`),
        React.createElement(Text, null, `queue:${props.aggregationQueuesByLayerIndex[1]?.currentNodeIds.length ?? 0}`),
        React.createElement(Text, { onPress: () => props.onPlaybackTimeChange(12000) }, "set time"),
        React.createElement(Text, { onPress: props.onAddDraft }, "add draft"),
        React.createElement(Text, { onPress: () => props.onTaskTitleChange("新任务") }, "set title"),
        React.createElement(Text, { onPress: props.onImportSubtitle }, "import subtitle"),
        firstDraft
          ? React.createElement(
              View,
              null,
              React.createElement(Text, { onPress: () => props.onUpdateDraftPosition(firstDraft.localId, "18:00") }, "set anchor"),
              React.createElement(Text, { onPress: () => props.onUpdateDraftText(firstDraft.localId, "question", "题面") }, "set question"),
              React.createElement(Text, { onPress: () => props.onUpdateDraftText(firstDraft.localId, "answer", "答案") }, "set answer"),
              React.createElement(Text, { onPress: () => props.onAddDraftReference(firstDraft.localId, "rp_ref") }, "add ref"),
            )
          : null,
        React.createElement(Text, { onPress: props.onSubmitDrafts }, "submit drafts"),
        React.createElement(
          Text,
          {
            onPress: () =>
              props.onCommitReview({
                reviewTaskId: "review_task_1",
                canRecall: [1],
                appendedInsights: [{ recallPointId: "rp_review", insight: [{ kind: "TEXT", text: "补充理解" }] }],
              } as ReviewCommitPayload),
          },
          "commit review",
        ),
        React.createElement(Text, { onPress: () => props.onRollUp(1) }, "roll up"),
      )
    },
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

const projectConfig: ProjectConfig = {
  projectId: "proj_1",
  projectType: "COURSE",
  rollUpStrategy: "LEARNING_OBJECT_ISOMORPHIC",
  updatedAt: "2026-05-18T00:00:00Z",
  layerConfigs: { "1": { reviewChainTemplate: [], aggregationKNode: 3, aggregationKPoint: 8, thresholdRollUpEnabled: true } },
  pushConfig: null,
}

const layer: Layer = {
  projectId: "proj_1",
  layerId: "layer_1",
  layerIndex: 1,
  layerMode: "REVIEW_CHAIN",
  orchestratorManagedReviewChainIds: [],
}

const taskNode: LearningTaskNode = {
  kind: "leaf",
  projectId: "proj_1",
  nodeId: "task_node_1",
  parentId: null,
  boundLearningTaskId: "task_1",
  title: "第一课任务",
  targetLayerIndex: 1,
}

const recallPoint: RecallPoint = {
  projectId: "proj_1",
  recallPointId: "rp_review",
  createdAt: "2026-05-18T00:00:00Z",
  state: "ACTIVE",
  deletedAt: null,
  question: [{ kind: "TEXT", text: "问题" }],
  answer: [{ kind: "TEXT", text: "答案" }],
  anchor: { instanceId: "inst_1", position: "t=1000" },
  references: [],
  insights: [],
}

const reviewRecommendations: ReviewRecommendationPage = {
  items: [
    {
      recallPoint,
      reviewRecommendationIndex: 12.5,
      estimatedMemoryStrength: 0.42,
      weightedSuccessRatio: 0.4,
      lastReviewedAt: null,
      lastReviewResult: null,
      reviewCount: 0,
    },
  ],
  totalCount: 1,
  offset: 0,
  limit: 20,
  nextOffset: null,
}

function createApi(overrides: Partial<ReturnType<typeof createLearningPyramidApi>> = {}) {
  return {
    auth: {},
    layers: {
      getAggregationQueue: jest.fn(async () => ({ currentNodeIds: ["task_node_1"] })),
      listLayers: jest.fn(async () => [layer]),
      manualRollUp: jest.fn(async () => ({ parentNodeId: "parent_1" })),
    },
    baiduNetdisk: {
      listProjectFiles: jest.fn(async () => {
        throw new Error("手机工作台不应读取百度网盘目录")
      }),
    },
    cloudAccounts: {
      listBaiduNetdiskAccounts: jest.fn(async () => {
        throw new Error("手机工作台不应读取百度网盘账号")
      }),
    },
    learningObjects: {
      getNode: jest.fn(),
      importFromBaiduNetdisk: jest.fn(async () => {
        throw new Error("手机工作台不应触发百度网盘导入")
      }),
      listNodes: jest.fn(async () => nodes),
      listRecallPointsByNode: jest.fn(),
    },
    learningTaskNodes: {
      listNodes: jest.fn(async () => [taskNode]),
      listRecallPointsByNode: jest.fn(),
    },
    learningTasks: {
      submitLearningTask: jest.fn(async () => ({ entryNodeId: "entry_1" })),
    },
    media: {
      getPlayback: jest.fn(async () => playback),
    },
    subtitles: {
      deleteInstanceSubtitleFile: jest.fn(async () => ({ deleted: true, instanceId: "inst_1" })),
      getInstanceSubtitleFile: jest.fn(async () => ({ found: false, instanceId: "inst_1" })),
      uploadInstanceSubtitleFile: jest.fn(async () => ({ found: false, instanceId: "inst_1" })),
    },
    projectConfig: {
      getProjectConfig: jest.fn(async () => projectConfig),
      setLayerConfig: jest.fn(async () => null),
    },
    system: {
      askProjectLlm: jest.fn(async () => ({ content: "AI 回答" })),
      getCapabilities: jest.fn(async () => ({
        appMode: "hosted",
        asrEnabled: true,
        serverMediaStreamEnabled: true,
        browserLocalMediaEnabled: false,
        baiduNetdiskEnabled: false,
        authEnabled: true,
        allowSignup: false,
        signupInviteRequired: true,
        passwordResetEnabled: true,
        emailVerificationEnabled: true,
        signupHumanCheckEnabled: false,
        signupHumanCheckProvider: null,
        signupHumanCheckChallengeUrl: null,
        llmConfigured: true,
        storyGenerationConfigured: false,
        llmSource: "user",
      })),
    },
    review: {
      commitReviewTask: jest.fn(async () => null),
      getQueue: jest.fn(async () => ({ headId: null, ids: [] })),
      getRangeSnapshot: jest.fn(),
      getReviewTask: jest.fn(),
      listRecallPoints: jest.fn(async () => []),
      listRecommendations: jest.fn(async () => reviewRecommendations),
      searchRecallPoints: jest.fn(async () => [recallPoint]),
    },
    subjects: {
      listMaterials: jest.fn(async () => [
        {
          createdAt: "2026-05-18T00:00:00Z",
          materialId: "mat_1",
          materialType: "COURSE",
          scopedProjectId: "proj_1",
          subjectId: "subj_1",
          title: "网课材料",
        },
      ]),
      listSubjects: jest.fn(async () => [
        {
          createdAt: "2026-05-18T00:00:00Z",
          deletedAt: null,
          state: "ACTIVE",
          subjectId: "subj_1",
          title: "高等数学",
        },
      ]),
    },
    ...overrides,
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
    mockGetDocumentAsync.mockReset()
    mockWorkbenchProps = null
  })

  it("submits compose drafts with task title, editable anchor, and references", async () => {
    const screen = renderRoute()

    await waitFor(() => expect(screen.getByText("active:第一课")).toBeTruthy())
    await waitFor(() => expect(screen.getByText("学习")).toBeTruthy())
    expect(screen.getByText("AI")).toBeTruthy()
    expect(screen.getByText("复习")).toBeTruthy()
    expect(screen.getByText("结构")).toBeTruthy()
    expect(screen.getByText("我的")).toBeTruthy()
    await waitFor(() => expect(screen.getByText("title:第一课")).toBeTruthy())
    fireEvent.press(screen.getByText("set time"))
    fireEvent.press(screen.getByText("add draft"))
    await waitFor(() => expect(screen.getByText("drafts:1")).toBeTruthy())
    fireEvent.press(screen.getByText("set title"))
    fireEvent.press(screen.getByText("set anchor"))
    fireEvent.press(screen.getByText("set question"))
    fireEvent.press(screen.getByText("set answer"))
    fireEvent.press(screen.getByText("add ref"))
    fireEvent.press(screen.getByText("submit drafts"))

    await waitFor(() =>
      expect(screen.api.learningTasks.submitLearningTask).toHaveBeenCalledWith(
        { subjectId: "subj_1", scopedProjectId: "proj_1" },
        {
          title: "新任务",
          items: [
            {
              question: [{ kind: "TEXT", text: "题面" }],
              answer: [{ kind: "TEXT", text: "答案" }],
              anchor: { instanceId: "inst_1", position: "t=1080000" },
              references: ["rp_ref"],
            },
          ],
        },
      ),
    )
    screen.unmount()
    screen.queryClient.clear()
  })

  it("loads queue head review data and commits inline review payload", async () => {
    const api = createApi({
      review: {
        ...createApi().review,
        getQueue: jest.fn(async () => ({ headId: "review_task_1", ids: ["review_task_1"] })),
        getReviewTask: jest.fn(async () => ({
          projectId: "proj_1",
          reviewTaskId: "review_task_1",
          inputRangeId: "range_1",
          createdAt: "2026-05-18T00:00:00Z",
          state: "PENDING",
          executedAt: null,
          resultRangeId: null,
        })),
        getRangeSnapshot: jest.fn(async () => ({ projectId: "proj_1", rangeId: "range_1", recallPointIds: ["rp_review"] })),
        listRecallPoints: jest.fn(async () => [recallPoint]),
        commitReviewTask: jest.fn(async () => null),
      } as never,
    })
    const screen = renderRoute(api)

    await waitFor(() => expect(screen.getByText("review:review_task_1")).toBeTruthy())
    fireEvent.press(screen.getByText("commit review"))

    await waitFor(() =>
      expect(screen.api.review.commitReviewTask).toHaveBeenCalledWith(
        { subjectId: "subj_1", scopedProjectId: "proj_1" },
        "review_task_1",
        {
          canRecall: [1],
          appendedInsights: [{ recallPointId: "rp_review", insight: [{ kind: "TEXT", text: "补充理解" }] }],
        },
      ),
    )
    screen.unmount()
    screen.queryClient.clear()
  })

  it("loads rollup data and triggers manual rollup through existing layer API", async () => {
    const screen = renderRoute()

    await waitFor(() => expect(screen.getByText("layers:1")).toBeTruthy())
    await waitFor(() => expect(screen.getByText("queue:1")).toBeTruthy())
    fireEvent.press(screen.getByText("roll up"))

    await waitFor(() =>
      expect(screen.api.layers.manualRollUp).toHaveBeenCalledWith(
        { subjectId: "subj_1", scopedProjectId: "proj_1" },
        1,
      ),
    )
    screen.unmount()
    screen.queryClient.clear()
  })

  it("does not load or import Baidu Netdisk content from the workbench route", async () => {
    const screen = renderRoute()

    await waitFor(() => expect(screen.getByText("active:第一课")).toBeTruthy())

    expect(screen.api.cloudAccounts.listBaiduNetdiskAccounts).not.toHaveBeenCalled()
    expect(screen.api.baiduNetdisk.listProjectFiles).not.toHaveBeenCalled()
    expect(screen.api.learningObjects.importFromBaiduNetdisk).not.toHaveBeenCalled()
    screen.unmount()
    screen.queryClient.clear()
  })

  it("renders project AI chat from the project shell and sends a scoped project question", async () => {
    const screen = renderRoute()

    await waitFor(() => expect(screen.getByText("active:第一课")).toBeTruthy())
    fireEvent.press(screen.getByText("AI"))

    await waitFor(() => expect(screen.getByText("AI问答")).toBeTruthy())
    expect(screen.queryByText("当前项目暂未开放 AI。")).toBeNull()
    fireEvent.changeText(screen.getByPlaceholderText("围绕当前节点提问"), "解释第一课")
    fireEvent.press(screen.getByText("发送"))

    await waitFor(() =>
      expect(screen.api.system.askProjectLlm).toHaveBeenCalledWith(
        { subjectId: "subj_1", scopedProjectId: "proj_1" },
        expect.objectContaining({
          learningObjectNodeId: "node_1",
          prompt: "解释第一课",
        }),
      ),
    )
    await waitFor(() => expect(screen.getByText("AI 回答")).toBeTruthy())
    screen.unmount()
    screen.queryClient.clear()
  })

  it("renders review recommendations from the project shell", async () => {
    const screen = renderRoute()

    await waitFor(() => expect(screen.getByText("active:第一课")).toBeTruthy())
    fireEvent.press(screen.getByText("复习"))

    await waitFor(() => expect(screen.getByText("复习推荐")).toBeTruthy())
    await waitFor(() =>
      expect(screen.api.review.listRecommendations).toHaveBeenCalledWith(
        { subjectId: "subj_1", scopedProjectId: "proj_1" },
        { limit: 20 },
      ),
    )
    expect(screen.getByText("问题")).toBeTruthy()
    expect(screen.queryByText("当前项目暂无独立复习入口。")).toBeNull()
    screen.unmount()
    screen.queryClient.clear()
  })

  it("renders the project structure view with task and object trees", async () => {
    const screen = renderRoute()

    await waitFor(() => expect(screen.getByText("active:第一课")).toBeTruthy())
    fireEvent.press(screen.getByText("结构"))

    await waitFor(() => expect(screen.getByText("结构视图")).toBeTruthy())
    expect(screen.getByText("学习任务树")).toBeTruthy()
    expect(screen.getByText("第一课任务")).toBeTruthy()
    expect(screen.queryByText("当前项目结构请先在学习页查看。")).toBeNull()

    fireEvent.press(screen.getByText("学习对象树"))
    expect(screen.getByText("第一课")).toBeTruthy()
    screen.unmount()
    screen.queryClient.clear()
  })

  it("picks a subtitle document and uploads it for the active instance", async () => {
    const api = createApi()
    mockGetDocumentAsync.mockResolvedValue({
      canceled: false,
      assets: [{ name: "lesson.srt", uri: "file:///cache/lesson.srt" }],
    })
    const originalFetch = globalThis.fetch
    globalThis.fetch = jest.fn(async () => ({ text: async () => "1\n00:00:01,000 --> 00:00:02,000\n字幕\n" })) as never
    const screen = renderRoute(api)

    await waitFor(() => expect(screen.getByText("active:第一课")).toBeTruthy())
    await act(async () => {
      fireEvent.press(screen.getByText("import subtitle"))
    })

    await waitFor(() =>
      expect(screen.api.subtitles.uploadInstanceSubtitleFile).toHaveBeenCalledWith(
        { subjectId: "subj_1", scopedProjectId: "proj_1" },
        "inst_1",
        {
          fileName: "lesson.srt",
          content: "1\n00:00:01,000 --> 00:00:02,000\n字幕\n",
        },
      ),
    )

    globalThis.fetch = originalFetch
    screen.unmount()
    screen.queryClient.clear()
  })

  it("does not submit when direct callback sees incomplete drafts", async () => {
    const screen = renderRoute()

    await waitFor(() => expect(screen.getByText("active:第一课")).toBeTruthy())
    fireEvent.press(screen.getByText("add draft"))
    await waitFor(() => expect(screen.getByText("drafts:1")).toBeTruthy())

    await act(async () => {
      mockWorkbenchProps?.onSubmitDrafts()
      await Promise.resolve()
    })

    expect(screen.api.learningTasks.submitLearningTask).not.toHaveBeenCalled()
    screen.unmount()
    screen.queryClient.clear()
  })
})

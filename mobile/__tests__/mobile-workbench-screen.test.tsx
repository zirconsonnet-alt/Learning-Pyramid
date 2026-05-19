import { fireEvent, render } from "@testing-library/react-native"

import type { LearningObjectNode } from "../src/api/learningObjects"
import type { PlaybackDescriptor } from "../src/api/media"
import type { RecallPoint } from "../src/api/review"
import { MobileWorkbenchScreen, type MobileWorkbenchScreenProps } from "../src/screens/MobileWorkbenchScreen"
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

function renderWorkbench(overrides: Partial<MobileWorkbenchScreenProps> = {}) {
  return render(
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
      {...overrides}
    />,
  )
}

describe("MobileWorkbenchScreen", () => {
  it("renders active learning object, mocked media player, existing recall point, and draft inputs", () => {
    const screen = renderWorkbench()

    expect(screen.getByText("第一课")).toBeTruthy()
    expect(screen.getByText("MockPlayer")).toBeTruthy()
    expect(screen.getByText("题面")).toBeTruthy()
    expect(screen.getByDisplayValue("草稿题面")).toBeTruthy()
    expect(screen.getByDisplayValue("草稿答案")).toBeTruthy()
  })

  it("opens directory and selecting 第二课 calls onSelectNode(nodes[2])", () => {
    const onSelectNode = jest.fn()
    const screen = renderWorkbench({
      currentMs: 0,
      drafts: [],
      onSelectNode,
      recallPoints: [],
      sessionCookie: null,
    })

    fireEvent.press(screen.getByText("目录"))
    fireEvent.press(screen.getByText("第二课"))

    expect(onSelectNode).toHaveBeenCalledWith(nodes[2])
  })

  it('when reviewHeadId="task_1", shows 先完成复习 and pressing 提交学习 does not call onSubmitDrafts', () => {
    const onSubmitDrafts = jest.fn()
    const screen = renderWorkbench({
      currentMs: 0,
      onSubmitDrafts,
      recallPoints: [],
      reviewHeadId: "task_1",
      sessionCookie: null,
    })

    expect(screen.getByText("先完成复习")).toBeTruthy()
    fireEvent.press(screen.getByText("提交学习"))

    expect(onSubmitDrafts).not.toHaveBeenCalled()
  })

  it("mocked player press calls onPlaybackTimeChange(15000) and 记复述点 calls onAddDraft", () => {
    const onAddDraft = jest.fn()
    const onPlaybackTimeChange = jest.fn()
    const screen = renderWorkbench({
      currentMs: 0,
      drafts: [],
      onAddDraft,
      onPlaybackTimeChange,
      recallPoints: [],
      sessionCookie: null,
    })

    fireEvent.press(screen.getByText("MockPlayer"))
    fireEvent.press(screen.getByText("记复述点"))

    expect(onPlaybackTimeChange).toHaveBeenCalledWith(15000)
    expect(onAddDraft).toHaveBeenCalled()
  })

  it("updates and removes draft through draft controls", () => {
    const onRemoveDraft = jest.fn()
    const onUpdateDraft = jest.fn()
    const screen = renderWorkbench({
      onRemoveDraft,
      onUpdateDraft,
    })

    fireEvent.changeText(screen.getByDisplayValue("草稿题面"), "新题面")
    expect(onUpdateDraft).toHaveBeenCalledWith("draft_1", { questionText: "新题面" })

    fireEvent.changeText(screen.getByDisplayValue("草稿答案"), "新答案")
    expect(onUpdateDraft).toHaveBeenCalledWith("draft_1", { answerText: "新答案" })

    fireEvent.press(screen.getByText("删除"))
    expect(onRemoveDraft).toHaveBeenCalledWith("draft_1")
  })

  it("submits complete drafts when review gate is clear", () => {
    const onSubmitDrafts = jest.fn()
    const screen = renderWorkbench({
      onSubmitDrafts,
      reviewHeadId: null,
      reviewQueueLoading: false,
      submitting: false,
    })

    fireEvent.press(screen.getByText("提交学习"))

    expect(onSubmitDrafts).toHaveBeenCalled()
  })

  it("when reviewQueueLoading={true}, pressing 提交学习 does not call onSubmitDrafts", () => {
    const onSubmitDrafts = jest.fn()
    const screen = renderWorkbench({
      onSubmitDrafts,
      recallPoints: [],
      reviewQueueLoading: true,
      sessionCookie: null,
    })

    fireEvent.press(screen.getByText("提交学习"))

    expect(onSubmitDrafts).not.toHaveBeenCalled()
  })
})

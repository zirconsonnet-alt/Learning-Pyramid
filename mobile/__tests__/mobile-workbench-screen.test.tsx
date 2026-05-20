import { fireEvent, render } from "@testing-library/react-native"
import { StyleSheet } from "react-native"

import type { Layer } from "../src/api/layers"
import type { LearningObjectNode } from "../src/api/learningObjects"
import type { LearningTaskNode } from "../src/api/learningTaskNodes"
import type { PlaybackDescriptor } from "../src/api/media"
import type { RecallPoint } from "../src/api/review"
import type { InstanceSubtitleFile } from "../src/api/subtitles"
import { MobileWorkbenchScreen, type MobileWorkbenchScreenProps } from "../src/screens/MobileWorkbenchScreen"
import type { MobileRecallDraft } from "../src/workbench/recallDrafts"

jest.mock("../src/screens/LearningMediaPlayer", () => {
  const React = require("react")
  const { Text } = require("react-native")
  return {
    LearningMediaPlayer: ({
      onPlaybackTimeChange,
      subtitleFile,
    }: {
      onPlaybackTimeChange?: (currentMs: number) => void
      subtitleFile?: { found: boolean } | null
    }) =>
      React.createElement(
        Text,
        { onPress: () => onPlaybackTimeChange?.(15000) },
        subtitleFile?.found ? "MockPlayer 字幕可用" : "MockPlayer",
      ),
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

const subtitleFile: InstanceSubtitleFile = {
  found: true,
  instanceId: "inst_1",
  fileName: "lesson.srt",
  format: "srt",
  source: "UPLOADED",
  segments: [{ startMs: 1000, endMs: 3000, text: "字幕文本" }],
}

const existingRecallPoint: RecallPoint = {
  projectId: "proj_1",
  recallPointId: "rp_old",
  createdAt: "2026-05-18T00:00:00Z",
  state: "ACTIVE",
  deletedAt: null,
  question: [{ kind: "TEXT", text: "旧复述点题面" }],
  answer: [{ kind: "TEXT", text: "旧复述点答案" }],
  anchor: { instanceId: "inst_1", position: "t=1000" },
  references: [],
  insights: [],
}

const reviewRecallPoint: RecallPoint = {
  projectId: "proj_1",
  recallPointId: "rp_review",
  createdAt: "2026-05-18T00:00:00Z",
  state: "ACTIVE",
  deletedAt: null,
  question: [{ kind: "TEXT", text: "复习题面" }],
  answer: [{ kind: "TEXT", text: "复习答案" }],
  anchor: { instanceId: "inst_1", position: "t=1000" },
  references: [],
  insights: [],
}

const referenceCandidate: RecallPoint = {
  projectId: "proj_1",
  recallPointId: "rp_candidate",
  createdAt: "2026-05-18T00:00:00Z",
  state: "ACTIVE",
  deletedAt: null,
  question: [{ kind: "TEXT", text: "引用候选题面" }],
  answer: [{ kind: "TEXT", text: "引用候选答案" }],
  anchor: { instanceId: "inst_1", position: "t=2000" },
  references: [],
  insights: [],
}

const draft: MobileRecallDraft = {
  localId: "draft_1",
  instanceId: "inst_1",
  position: "t=1077000",
  question: [{ kind: "TEXT", text: "草稿题面" }],
  answer: [{ kind: "TEXT", text: "草稿答案" }],
  references: ["rp_old"],
  createdAt: 1710000000000,
  updatedAt: 1710000000000,
}

const layers: Layer[] = [
  {
    projectId: "proj_1",
    layerId: "layer_1",
    layerIndex: 1,
    layerMode: "REVIEW_CHAIN",
    orchestratorManagedReviewChainIds: [],
  },
]

const learningTaskNode: LearningTaskNode = {
  kind: "leaf",
  projectId: "proj_1",
  nodeId: "task_node_1",
  parentId: null,
  boundLearningTaskId: "task_1",
  title: "第一课任务",
  targetLayerIndex: 1,
}

function renderWorkbench(overrides: Partial<MobileWorkbenchScreenProps> = {}) {
  return render(
    <MobileWorkbenchScreen
      activeNode={nodes[1]}
      aggregationQueuesByLayerIndex={{ 1: { currentNodeIds: ["task_node_1"] } }}
      apiBaseUrl="https://plm.xuebao.chat/api"
      currentMs={15000}
      drafts={[draft]}
      errorMessage={null}
      layers={layers}
      layersErrorMessage={null}
      layersLoading={false}
      learningTaskNodesById={{ task_node_1: learningTaskNode }}
      learningTaskNodesLoading={false}
      loading={false}
      nodes={nodes}
      onAddDraft={() => undefined}
      onAddDraftReference={() => undefined}
      onCommitReview={() => undefined}
      onImportSubtitle={() => undefined}
      onPlaybackTimeChange={() => undefined}
      onRemoveDraft={() => undefined}
      onRemoveDraftReference={() => undefined}
      onRollUp={() => undefined}
      onSelectNode={() => undefined}
      onSubmitDrafts={() => undefined}
      onTaskTitleChange={() => undefined}
      onToggleThresholdRollUp={() => undefined}
      onUpdateDraftPosition={() => undefined}
      onUpdateDraftText={() => undefined}
      playback={playback}
      playbackErrorMessage={null}
      playbackLoading={false}
      projectType="COURSE"
      referenceCandidates={[existingRecallPoint, referenceCandidate]}
      reviewCommitting={false}
      reviewErrorMessage={null}
      reviewLoading={false}
      reviewRecallPointIds={[]}
      reviewRecallPoints={[]}
      reviewTaskId={null}
      rollUpErrorMessage={null}
      rollUpStrategy="LEARNING_OBJECT_ISOMORPHIC"
      rollingUp={false}
      sessionCookie="plm_session=abc"
      subtitleErrorMessage={null}
      subtitleFile={null}
      subtitleImporting={false}
      subtitleLoading={false}
      submitting={false}
      taskTitle="第一课任务"
      thresholdRollUpEnabledByLayerIndex={{ 1: true }}
      thresholdRollUpUpdating={false}
      {...overrides}
    />,
  )
}

function collectText(node: unknown): string {
  if (typeof node === "string") return node
  if (Array.isArray(node)) return node.map(collectText).join("")
  if (node && typeof node === "object" && "props" in node) {
    const maybeNode = node as { children?: unknown; props?: { children?: unknown } }
    return collectText(maybeNode.children ?? maybeNode.props?.children)
  }
  return ""
}

function collectButtonNodes(node: unknown, result: unknown[] = []) {
  if (!node || typeof node !== "object") return result
  const maybeNode = node as { props?: { accessibilityRole?: string; children?: unknown }; children?: unknown }
  if (maybeNode.props?.accessibilityRole === "button") result.push(node)
  const children = maybeNode.children ?? maybeNode.props?.children
  if (Array.isArray(children)) {
    children.forEach((child) => collectButtonNodes(child, result))
  } else {
    collectButtonNodes(children, result)
  }
  return result
}

describe("MobileWorkbenchScreen", () => {
  it("renders desktop-aligned compose pane instead of an existing recall point list", () => {
    const screen = renderWorkbench()

    expect(screen.getByText("第一课")).toBeTruthy()
    expect(screen.getByText("MockPlayer")).toBeTruthy()
    expect(screen.getAllByText("复述点录入")).toHaveLength(2)
    expect(screen.getByDisplayValue("第一课任务")).toBeTruthy()
    expect(screen.getByText("1")).toBeTruthy()
    expect(screen.getByDisplayValue("17:57")).toBeTruthy()
    expect(screen.getByDisplayValue("草稿题面")).toBeTruthy()
    expect(screen.getByDisplayValue("草稿答案")).toBeTruthy()
    expect(screen.queryByText("旧复述点题面")).toBeNull()
  })

  it("uses the video title as the learning-object switcher and renders structured study stats inline", () => {
    const onSelectNode = jest.fn()
    const screen = renderWorkbench({ onSelectNode, playback: { ...playback, durationMs: 37 * 60_000 } })
    const buttonNodes = collectButtonNodes(screen.toJSON())
    const buttonLabels = buttonNodes.map((button) => collectText(button))

    expect(buttonLabels).not.toContain("内容目录")
    expect(buttonLabels).not.toContain("学习统计")
    expect(screen.getByText("学习统计")).toBeTruthy()
    expect(screen.getByText("未提交")).toBeTruthy()
    expect(screen.getByText("预计剩余学习时长")).toBeTruthy()
    expect(screen.getByText("继续学习后生成")).toBeTruthy()
    expect(screen.getByText("观看覆盖")).toBeTruthy()
    expect(screen.getByText("0m / 37m")).toBeTruthy()
    expect(screen.getByText("0%")).toBeTruthy()
    expect(screen.getByText("今日学习行为分布")).toBeTruthy()
    expect(screen.getByText("驻留时长")).toBeTruthy()
    expect(screen.getByText("学习时长")).toBeTruthy()
    expect(screen.getByText("走神时长")).toBeTruthy()
    expect(screen.getByText("暂无足够数据生成学习分解")).toBeTruthy()
    expect(screen.queryByText("第二课")).toBeNull()

    fireEvent.press(screen.getByLabelText("切换学习内容：第一课"))

    expect(screen.getByText("第二课")).toBeTruthy()
    fireEvent.press(screen.getByText("第二课"))
    expect(onSelectNode).toHaveBeenCalledWith(nodes[2])
  })

  it("keeps the workbench header compact on Android-sized screens", () => {
    const screen = renderWorkbench()
    const title = screen.getByText("第一课")
    const buttonNodes = collectButtonNodes(screen.toJSON())
    const addButton = buttonNodes.find((button) => collectText(button) === "添加") as
      | { props?: { style?: unknown }; children?: unknown }
      | undefined
    const addLabel = screen.getByText("添加")

    expect(StyleSheet.flatten(title.props.style)).toEqual(expect.objectContaining({ fontSize: 28 }))
    expect(StyleSheet.flatten(addButton?.props?.style)).toEqual(expect.objectContaining({ minHeight: 38 }))
    expect(addLabel.props.maxFontSizeMultiplier).toBeLessThanOrEqual(1.1)
  })

  it("places add inside the recall compose section header", () => {
    const screen = renderWorkbench()
    const buttonNodes = collectButtonNodes(screen.toJSON())
    const buttonLabels = buttonNodes.map((button) => collectText(button))
    const segmentIndex = buttonLabels.indexOf("复述点录入")
    const addIndex = buttonLabels.indexOf("添加")

    expect(screen.getAllByText("复述点录入")).toHaveLength(2)
    expect(addIndex).toBeGreaterThan(segmentIndex)
  })

  it("renders the reference-style empty recall panel without changing submit rules", () => {
    const onAddDraft = jest.fn()
    const onSubmitDrafts = jest.fn()
    const screen = renderWorkbench({ drafts: [], onAddDraft, onSubmitDrafts })

    expect(screen.getByText("还没有复述点")).toBeTruthy()
    expect(screen.getByText("播放视频时，遇到关键概念、易错点或需要回忆的内容，可以添加复述点。")).toBeTruthy()
    expect(screen.getByText("添加至少 1 个复述点后可提交")).toBeTruthy()

    fireEvent.press(screen.getByText("+ 添加第一个复述点"))
    const submitButton = collectButtonNodes(screen.toJSON()).find((button) => collectText(button) === "提交学习") as
      | { props?: { accessibilityState?: unknown } }
      | undefined

    expect(onAddDraft).toHaveBeenCalled()
    expect(submitButton?.props?.accessibilityState).toEqual({ disabled: true })
    expect(onSubmitDrafts).not.toHaveBeenCalled()
  })

  it("updates task title, active draft fields, references, and submits learning", () => {
    const onTaskTitleChange = jest.fn()
    const onUpdateDraftPosition = jest.fn()
    const onUpdateDraftText = jest.fn()
    const onAddDraftReference = jest.fn()
    const onRemoveDraftReference = jest.fn()
    const onSubmitDrafts = jest.fn()
    const screen = renderWorkbench({
      onAddDraftReference,
      onRemoveDraftReference,
      onSubmitDrafts,
      onTaskTitleChange,
      onUpdateDraftPosition,
      onUpdateDraftText,
    })

    fireEvent.changeText(screen.getByDisplayValue("第一课任务"), "新任务")
    fireEvent.changeText(screen.getByDisplayValue("17:57"), "18:00")
    fireEvent.changeText(screen.getByDisplayValue("草稿题面"), "新题面")
    fireEvent.changeText(screen.getByDisplayValue("草稿答案"), "新答案")
    fireEvent.press(screen.getByText("引用候选"))
    fireEvent.press(screen.getByText("移除引用 rp_old"))
    fireEvent.press(screen.getByText("提交学习"))

    expect(onTaskTitleChange).toHaveBeenCalledWith("新任务")
    expect(onUpdateDraftPosition).toHaveBeenCalledWith("draft_1", "18:00")
    expect(onUpdateDraftText).toHaveBeenCalledWith("draft_1", "question", "新题面")
    expect(onUpdateDraftText).toHaveBeenCalledWith("draft_1", "answer", "新答案")
    expect(onAddDraftReference).toHaveBeenCalledWith("draft_1", "rp_candidate")
    expect(onRemoveDraftReference).toHaveBeenCalledWith("draft_1", "rp_old")
    expect(onSubmitDrafts).toHaveBeenCalled()
  })

  it("renders queue review inside the workbench and commits after written answer is submitted", () => {
    const onCommitReview = jest.fn()
    const screen = renderWorkbench({
      onCommitReview,
      reviewRecallPointIds: ["rp_review"],
      reviewRecallPoints: [reviewRecallPoint],
      reviewTaskId: "review_task_1",
    })

    expect(screen.getAllByText("复习任务")).toHaveLength(2)
    expect(screen.getByText("复习题面")).toBeTruthy()
    fireEvent.changeText(screen.getByPlaceholderText("先写自己的答案"), "我的答案")
    fireEvent.press(screen.getByText("提交答案"))
    expect(screen.getByText("复习答案")).toBeTruthy()
    fireEvent.changeText(screen.getByPlaceholderText("追加理解"), "容易混淆")
    fireEvent.press(screen.getByText("记得"))
    fireEvent.press(screen.getByText("提交本轮复习"))

    expect(onCommitReview).toHaveBeenCalledWith({
      reviewTaskId: "review_task_1",
      canRecall: [1],
      appendedInsights: [{ recallPointId: "rp_review", insight: [{ kind: "TEXT", text: "容易混淆" }] }],
    })
  })

  it("renders rollup pane and calls rollup action for the selected layer", () => {
    const onRollUp = jest.fn()
    const screen = renderWorkbench({ onRollUp })

    fireEvent.press(screen.getByText("层推进与学习任务"))

    expect(screen.getByText("L1")).toBeTruthy()
    expect(screen.getByText("第一课任务")).toBeTruthy()
    fireEvent.press(screen.getByText("重新扫描对象树推进"))

    expect(onRollUp).toHaveBeenCalledWith(1)
  })

  it("does not expose Baidu Netdisk import inside the learning workbench", () => {
    const screen = renderWorkbench()

    expect(screen.queryByText("百度网盘导入")).toBeNull()
    expect(screen.queryByText("从百度网盘导入")).toBeNull()
  })

  it("passes loaded subtitles to the media player and exposes subtitle import", () => {
    const onImportSubtitle = jest.fn()
    const screen = renderWorkbench({
      onImportSubtitle,
      subtitleFile,
    })

    expect(screen.getByText("MockPlayer 字幕可用")).toBeTruthy()
    fireEvent.press(screen.getByText("替换字幕"))

    expect(onImportSubtitle).toHaveBeenCalled()
  })

})

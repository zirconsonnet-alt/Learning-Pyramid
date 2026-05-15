import type { Instance, VideoWatchProgress } from "@/ui/api/instances"
import { type Layer } from "@/ui/api/layers"
import type { LearningObjectNode } from "@/ui/api/learningObjects"
import type { LearningTaskNode } from "@/ui/api/learningTaskNodes"
import type { PlaybackDescriptor } from "@/ui/api/media"
import type { Project, ProjectMaterialSourceBinding } from "@/ui/api/projects"
import type { LayerConfig, ProjectConfig } from "@/ui/api/projectConfig"
import type { Queue } from "@/ui/api/queue"
import type { RecallPoint, RangeSnapshot, ReviewTask } from "@/ui/api/review"
import type { Subject, SubjectContext, StudyMaterial } from "@/ui/api/subjects"
import type { RichContent } from "@/ui/api/richContent"
import {
  VIRTUAL_STUDY_REVIEW_MATERIAL_ID,
  VIRTUAL_STUDY_REVIEW_PROJECT_ID,
  VIRTUAL_STUDY_REVIEW_SUBJECT_ID,
} from "@/ui/guideWalkthrough/guideVirtualProjectIds"
import { getBaseUrl } from "@/ui/api/http"
import { useAppStore } from "@/ui/store/appStore"
import { useWorkbenchStore } from "@/ui/store/workbenchStore"

type VirtualStudyReviewState = {
  initializedAt: string
  project: Project
  subject: Subject
  subjectMaterial: StudyMaterial
  subjectContext: SubjectContext
  projectBinding: ProjectMaterialSourceBinding
  projectConfig: ProjectConfig
  layers: Layer[]
  instances: Instance[]
  learningObjectNodes: LearningObjectNode[]
  learningTaskNodes: LearningTaskNode[]
  queue: Queue
  recallPointsById: Record<string, RecallPoint>
  recallPointIdsByInstanceId: Record<string, string[]>
  rangeSnapshotsById: Record<string, RangeSnapshot>
  reviewTasksById: Record<string, ReviewTask>
  learningTaskRecallPointIdsByNodeId: Record<string, string[]>
  playbackDescriptorByInstanceId: Record<string, PlaybackDescriptor>
  remoteVideoWatchProgressByInstanceId: Record<string, VideoWatchProgress>
}

type SubmitLearningTaskInput = {
  title: string
  items: { question: RichContent; answer: RichContent; anchor: { instanceId: string; position: string } | null; references: string[] }[]
}

type CommitReviewTaskInput = {
  reviewTaskId: string
  canRecall: number[]
  appendedInsights?: { recallPointId: string; insight: RichContent }[]
}

const VIRTUAL_STUDY_REVIEW_VIDEO_PATH = "/guide/demo-media/study-review"
const VIRTUAL_STUDY_REVIEW_VIDEO_URL = `${getBaseUrl()}${VIRTUAL_STUDY_REVIEW_VIDEO_PATH}`
export const VIRTUAL_STUDY_REVIEW_GUIDE_RECALL_QUESTION = "线性组合的目标是什么？"
export const VIRTUAL_STUDY_REVIEW_GUIDE_RECALL_ANSWER = "用一组基向量和对应系数表示目标向量。"
export const VIRTUAL_STUDY_REVIEW_GUIDE_WRITTEN_REVIEW_ANSWER = "线性组合可以用基向量和系数表示目标向量。"
const VIRTUAL_STUDY_REVIEW_STORAGE_PREFIXES = [
  `plm-review-session:${VIRTUAL_STUDY_REVIEW_PROJECT_ID}`,
  `plm-workbench-daily-stats:${VIRTUAL_STUDY_REVIEW_PROJECT_ID}:`,
  `plm-study-presence:${VIRTUAL_STUDY_REVIEW_PROJECT_ID}:`,
  `plm-video-duration:${VIRTUAL_STUDY_REVIEW_PROJECT_ID}:`,
  `plm-video-watch-coverage:${VIRTUAL_STUDY_REVIEW_PROJECT_ID}:`,
  `plm-playback-resume:${VIRTUAL_STUDY_REVIEW_PROJECT_ID}:`,
]

let virtualStudyReviewState: VirtualStudyReviewState | null = null

function nowIso() {
  return new Date().toISOString()
}

function createBaseVirtualStudyReviewState(): VirtualStudyReviewState {
  const createdAt = nowIso()
  const project: Project = {
    projectId: VIRTUAL_STUDY_REVIEW_PROJECT_ID,
    title: "学习复习引导示范项目",
    state: "ACTIVE",
    createdAt,
    deletedAt: null,
  }
  const subject: Subject = {
    subjectId: VIRTUAL_STUDY_REVIEW_SUBJECT_ID,
    title: "学习复习引导示范学科",
    state: "ACTIVE",
    createdAt,
    deletedAt: null,
  }
  const subjectMaterial: StudyMaterial = {
    subjectId: VIRTUAL_STUDY_REVIEW_SUBJECT_ID,
    materialId: VIRTUAL_STUDY_REVIEW_MATERIAL_ID,
    materialType: "COURSE",
    title: "线性代数导论示范视频",
    createdAt,
    scopedProjectId: VIRTUAL_STUDY_REVIEW_PROJECT_ID,
  }
  const projectBinding: ProjectMaterialSourceBinding = {
    projectId: VIRTUAL_STUDY_REVIEW_PROJECT_ID,
    sourceKind: "SERVER_FS",
    sourceRootLabel: "引导演示视频",
    updatedAt: createdAt,
  }
  const layerConfigs: Record<string, LayerConfig> = {
    "0": {
      reviewChainTemplate: [{ kind: "REVIEW_TASK", count: 1 }],
      aggregationKNode: 3,
      aggregationKPoint: 8,
      thresholdRollUpEnabled: true,
    },
  }
  const projectConfig: ProjectConfig = {
    projectId: VIRTUAL_STUDY_REVIEW_PROJECT_ID,
    projectType: "COURSE",
    rollUpStrategy: "THRESHOLD_AUTO",
    updatedAt: createdAt,
    layerConfigs,
    pushConfig: {
      minRecallPointsToEnable: 1,
      maxHistoryLen: 6,
      recommendedBatchSize: 6,
      forgettingCurveDecayPerDay: 0.18,
    },
  }
  const layers: Layer[] = [
    {
      projectId: VIRTUAL_STUDY_REVIEW_PROJECT_ID,
      layerId: "virtual-layer-0",
      layerIndex: 0,
      layerMode: "REVIEW",
      orchestratorManagedReviewChainIds: [],
    },
  ]
  const instances: Instance[] = [
    {
      instanceId: "guide-lesson-1",
      materialId: "guide/study-review/lesson-1.mp4",
      materialDisplayName: "01 向量与线性组合.mp4",
      presence: "PRESENT",
      lastSeenAt: createdAt,
      mediaSourceKind: "SERVER_FS",
      playbackKind: "FILE",
      durationMs: 428_000,
    },
    {
      instanceId: "guide-lesson-2",
      materialId: "guide/study-review/lesson-2.mp4",
      materialDisplayName: "02 基与维数.mp4",
      presence: "PRESENT",
      lastSeenAt: createdAt,
      mediaSourceKind: "SERVER_FS",
      playbackKind: "FILE",
      durationMs: 412_000,
    },
    {
      instanceId: "guide-lesson-3",
      materialId: "guide/study-review/lesson-3.mp4",
      materialDisplayName: "03 线性无关.mp4",
      presence: "PRESENT",
      lastSeenAt: createdAt,
      mediaSourceKind: "SERVER_FS",
      playbackKind: "FILE",
      durationMs: 395_000,
    },
  ]
  const learningObjectNodes: LearningObjectNode[] = [
    {
      kind: "container",
      projectId: VIRTUAL_STUDY_REVIEW_PROJECT_ID,
      nodeId: "guide-chapter-1",
      parentId: null,
      children: ["guide-lesson-1-node", "guide-lesson-2-node", "guide-lesson-3-node"],
      title: "第 1 章 向量空间",
      relativePath: "guide/study-review",
      source: "GUIDE_VIRTUAL",
    },
    {
      kind: "leaf",
      projectId: VIRTUAL_STUDY_REVIEW_PROJECT_ID,
      nodeId: "guide-lesson-1-node",
      parentId: "guide-chapter-1",
      instanceId: "guide-lesson-1",
      title: "01 向量与线性组合.mp4",
      relativePath: "guide/study-review/lesson-1.mp4",
      source: "GUIDE_VIRTUAL",
    },
    {
      kind: "leaf",
      projectId: VIRTUAL_STUDY_REVIEW_PROJECT_ID,
      nodeId: "guide-lesson-2-node",
      parentId: "guide-chapter-1",
      instanceId: "guide-lesson-2",
      title: "02 基与维数.mp4",
      relativePath: "guide/study-review/lesson-2.mp4",
      source: "GUIDE_VIRTUAL",
    },
    {
      kind: "leaf",
      projectId: VIRTUAL_STUDY_REVIEW_PROJECT_ID,
      nodeId: "guide-lesson-3-node",
      parentId: "guide-chapter-1",
      instanceId: "guide-lesson-3",
      title: "03 线性无关.mp4",
      relativePath: "guide/study-review/lesson-3.mp4",
      source: "GUIDE_VIRTUAL",
    },
  ]
  const playbackDescriptorByInstanceId = Object.fromEntries(
    instances.map((instance) => [
      instance.instanceId,
      {
        instanceId: instance.instanceId,
        sourceKind: "SERVER_FS",
        playbackKind: "FILE",
        url: VIRTUAL_STUDY_REVIEW_VIDEO_URL,
        mimeType: "video/mp4",
        durationMs: instance.durationMs ?? 420_000,
        supportsFrameGrab: false,
        supportsServerAsr: false,
      } satisfies PlaybackDescriptor,
    ]),
  ) as Record<string, PlaybackDescriptor>

  const subjectContext: SubjectContext = {
    subject,
    currentMaterial: subjectMaterial,
    materials: [subjectMaterial],
    currentScopedProjectId: VIRTUAL_STUDY_REVIEW_PROJECT_ID,
    currentInternalProjectId: VIRTUAL_STUDY_REVIEW_PROJECT_ID,
  }

  return {
    initializedAt: createdAt,
    project,
    subject,
    subjectMaterial,
    subjectContext,
    projectBinding,
    projectConfig,
    layers,
    instances,
    learningObjectNodes,
    learningTaskNodes: [],
    queue: {
      headId: null,
      ids: [],
    },
    recallPointsById: {},
    recallPointIdsByInstanceId: Object.fromEntries(instances.map((instance) => [instance.instanceId, []])),
    rangeSnapshotsById: {},
    reviewTasksById: {},
    learningTaskRecallPointIdsByNodeId: {},
    playbackDescriptorByInstanceId,
    remoteVideoWatchProgressByInstanceId: {},
  }
}

function removeVirtualStudyReviewLocalStorage() {
  if (typeof window === "undefined") return
  const keys: string[] = []
  for (let index = 0; index < window.localStorage.length; index += 1) {
    const key = window.localStorage.key(index)
    if (!key) continue
    if (VIRTUAL_STUDY_REVIEW_STORAGE_PREFIXES.some((prefix) => key.startsWith(prefix))) {
      keys.push(key)
    }
  }
  for (const key of keys) {
    window.localStorage.removeItem(key)
  }
}

function cloneVirtualStudyReviewState() {
  return structuredClone(virtualStudyReviewState ?? createBaseVirtualStudyReviewState())
}

export function startVirtualStudyReviewProjectSession() {
  virtualStudyReviewState = createBaseVirtualStudyReviewState()
  useAppStore.getState().setSelectedSubjectId(VIRTUAL_STUDY_REVIEW_SUBJECT_ID)
  useAppStore.getState().setSelectedWorkbenchProjectRef({
    subjectId: VIRTUAL_STUDY_REVIEW_SUBJECT_ID,
    scopedProjectId: VIRTUAL_STUDY_REVIEW_PROJECT_ID,
  })
  return virtualStudyReviewState
}

export function clearVirtualStudyReviewProjectSession() {
  virtualStudyReviewState = null
  useWorkbenchStore.getState().resetProject(VIRTUAL_STUDY_REVIEW_PROJECT_ID)
  useAppStore.getState().removeRecentWorkbenchProjectId(VIRTUAL_STUDY_REVIEW_PROJECT_ID)
  useAppStore.getState().removeRecentWorkbenchProjectRef({
    subjectId: VIRTUAL_STUDY_REVIEW_SUBJECT_ID,
    scopedProjectId: VIRTUAL_STUDY_REVIEW_PROJECT_ID,
  })
  if (useAppStore.getState().selectedSubjectId === VIRTUAL_STUDY_REVIEW_SUBJECT_ID) {
    useAppStore.getState().setSelectedSubjectId(null)
  }
  removeVirtualStudyReviewLocalStorage()
}

function ensureVirtualStudyReviewState() {
  if (!virtualStudyReviewState) {
    virtualStudyReviewState = createBaseVirtualStudyReviewState()
  }
  return virtualStudyReviewState
}

function buildRecallPointId(index: number) {
  return `guide-recall-point-${index}`
}

function buildRangeId(index: number) {
  return `guide-range-${index}`
}

function buildReviewTaskId(index: number) {
  return `guide-review-task-${index}`
}

function buildLearningTaskId(index: number) {
  return `guide-learning-task-${index}`
}

function buildLearningTaskNodeId(index: number) {
  return `guide-learning-task-node-${index}`
}

export function getVirtualStudyReviewProject() {
  return ensureVirtualStudyReviewState().project
}

export function getVirtualStudyReviewProjects() {
  return [ensureVirtualStudyReviewState().project]
}

export function getVirtualStudyReviewProjectMaterialSourceBinding() {
  return ensureVirtualStudyReviewState().projectBinding
}

export function getVirtualStudyReviewSubjectContext() {
  return ensureVirtualStudyReviewState().subjectContext
}

export function getVirtualStudyReviewProjectConfig() {
  return ensureVirtualStudyReviewState().projectConfig
}

export function getVirtualStudyReviewLayers() {
  return ensureVirtualStudyReviewState().layers
}

export function getVirtualStudyReviewInstances() {
  return ensureVirtualStudyReviewState().instances
}

export function getVirtualStudyReviewQueue() {
  return ensureVirtualStudyReviewState().queue
}

export function getVirtualStudyReviewRecallPointIdsByInstance(instanceId: string) {
  return {
    recallPointIds: [...(ensureVirtualStudyReviewState().recallPointIdsByInstanceId[instanceId] ?? [])],
  }
}

export function getVirtualStudyReviewRecallPointsForTaskNode(nodeId: string) {
  const state = ensureVirtualStudyReviewState()
  return (state.learningTaskRecallPointIdsByNodeId[nodeId] ?? [])
    .map((recallPointId) => state.recallPointsById[recallPointId])
    .filter((item): item is RecallPoint => Boolean(item))
}

export function searchVirtualStudyReviewRecallPoints(query: string) {
  const normalized = query.trim().toLowerCase()
  return Object.values(ensureVirtualStudyReviewState().recallPointsById).filter((item) => {
    if (!normalized) return true
    const text = `${item.question.map((block) => ("text" in block ? block.text : "")).join(" ")} ${
      item.answer.map((block) => ("text" in block ? block.text : "")).join(" ")
    }`.toLowerCase()
    return text.includes(normalized)
  })
}

export function getVirtualStudyReviewRecallPoint(recallPointId: string) {
  return ensureVirtualStudyReviewState().recallPointsById[recallPointId] ?? null
}

export function getVirtualStudyReviewRangeSnapshot(rangeId: string) {
  return ensureVirtualStudyReviewState().rangeSnapshotsById[rangeId] ?? null
}

export function getVirtualStudyReviewReviewTask(reviewTaskId: string) {
  return ensureVirtualStudyReviewState().reviewTasksById[reviewTaskId] ?? null
}

export function getVirtualStudyReviewLearningTaskNodes() {
  return ensureVirtualStudyReviewState().learningTaskNodes
}

export function getVirtualStudyReviewLearningObjectNodes() {
  return ensureVirtualStudyReviewState().learningObjectNodes
}

export function getVirtualStudyReviewPlaybackDescriptor(instanceId: string) {
  return ensureVirtualStudyReviewState().playbackDescriptorByInstanceId[instanceId] ?? null
}

export function getVirtualStudyReviewRemoteVideoWatchProgress(instanceIds: string[]) {
  const state = ensureVirtualStudyReviewState()
  return Object.fromEntries(
    instanceIds.flatMap((instanceId) =>
      state.remoteVideoWatchProgressByInstanceId[instanceId] ? [[instanceId, state.remoteVideoWatchProgressByInstanceId[instanceId]]] : [],
    ),
  ) as Record<string, VideoWatchProgress>
}

export function submitVirtualStudyReviewLearningTask(input: SubmitLearningTaskInput) {
  const state = ensureVirtualStudyReviewState()
  const nextLearningTaskIndex = state.learningTaskNodes.length + 1
  const learningTaskId = buildLearningTaskId(nextLearningTaskIndex)
  const learningTaskNodeId = buildLearningTaskNodeId(nextLearningTaskIndex)
  const reviewTaskId = buildReviewTaskId(nextLearningTaskIndex)
  const rangeId = buildRangeId(nextLearningTaskIndex)
  const createdAt = nowIso()
  const recallPointIds: string[] = []

  input.items.forEach((item, index) => {
    const recallPointId = buildRecallPointId(Object.keys(state.recallPointsById).length + 1)
    recallPointIds.push(recallPointId)
    state.recallPointsById[recallPointId] = {
      projectId: VIRTUAL_STUDY_REVIEW_PROJECT_ID,
      recallPointId,
      createdAt,
      state: "ACTIVE",
      deletedAt: null,
      question: item.question,
      answer: item.answer,
      anchor: item.anchor,
      references: [...item.references],
      insights: [],
    }
    const instanceId = item.anchor?.instanceId ?? state.instances[0]?.instanceId ?? ""
    const list = state.recallPointIdsByInstanceId[instanceId] ?? []
    state.recallPointIdsByInstanceId[instanceId] = [...list, recallPointId]
    if (index === 0) {
      state.reviewTasksById[reviewTaskId] = {
        projectId: VIRTUAL_STUDY_REVIEW_PROJECT_ID,
        reviewTaskId,
        inputRangeId: rangeId,
        createdAt,
        state: "PENDING",
        executedAt: null,
        resultRangeId: null,
      }
    }
  })

  state.rangeSnapshotsById[rangeId] = {
    projectId: VIRTUAL_STUDY_REVIEW_PROJECT_ID,
    rangeId,
    recallPointIds,
  }
  state.learningTaskNodes = [
    ...state.learningTaskNodes,
    {
      kind: "leaf",
      projectId: VIRTUAL_STUDY_REVIEW_PROJECT_ID,
      nodeId: learningTaskNodeId,
      parentId: null,
      boundLearningTaskId: learningTaskId,
      title: input.title.trim() || "示范学习任务",
      targetLayerIndex: 0,
    },
  ]
  state.learningTaskRecallPointIdsByNodeId[learningTaskNodeId] = recallPointIds
  state.queue = {
    headId: reviewTaskId,
    ids: [reviewTaskId],
  }
  return {
    entryNodeId: learningTaskNodeId,
  }
}

export function commitVirtualStudyReviewTask(input: CommitReviewTaskInput) {
  const state = ensureVirtualStudyReviewState()
  const reviewTask = state.reviewTasksById[input.reviewTaskId]
  if (!reviewTask) return null
  const rangeSnapshot = state.rangeSnapshotsById[reviewTask.inputRangeId]
  if (!rangeSnapshot) return null
  const updatedAt = nowIso()
  rangeSnapshot.recallPointIds.forEach((recallPointId, index) => {
    const recallPoint = state.recallPointsById[recallPointId]
    if (!recallPoint) return
    const appendedInsight = input.appendedInsights?.find((item) => item.recallPointId === recallPointId)?.insight
    const nextInsights = appendedInsight ? [...recallPoint.insights, appendedInsight] : recallPoint.insights
    state.recallPointsById[recallPointId] = {
      ...recallPoint,
      insights: nextInsights,
      references: recallPoint.references,
      answer: recallPoint.answer,
      question: recallPoint.question,
      anchor: recallPoint.anchor,
      deletedAt: recallPoint.deletedAt,
      state: recallPoint.state,
      createdAt: recallPoint.createdAt,
      projectId: recallPoint.projectId,
      recallPointId,
    }
    const reviewResult = input.canRecall[index] === 1 ? "CAN_RECALL" : "CANNOT_RECALL"
    state.remoteVideoWatchProgressByInstanceId[recallPoint.anchor?.instanceId ?? ""] = state.remoteVideoWatchProgressByInstanceId[recallPoint.anchor?.instanceId ?? ""] ?? {
      projectId: VIRTUAL_STUDY_REVIEW_PROJECT_ID,
      instanceId: recallPoint.anchor?.instanceId ?? "",
      durationMs: state.instances.find((item) => item.instanceId === recallPoint.anchor?.instanceId)?.durationMs ?? null,
      watchedMs: 0,
      ranges: [],
      completedAt: null,
      updatedAt,
    }
    void reviewResult
  })
  state.reviewTasksById[input.reviewTaskId] = {
    ...reviewTask,
    state: "COMPLETED",
    executedAt: nowIso(),
  }
  state.queue = {
    headId: null,
    ids: [],
  }
  return null
}

export function setVirtualStudyReviewVideoWatchProgress(instanceId: string, params: { watchedMs: number; durationMs?: number | null; completed?: boolean }) {
  const state = ensureVirtualStudyReviewState()
  const current = state.remoteVideoWatchProgressByInstanceId[instanceId]
  const durationMs = params.durationMs ?? current?.durationMs ?? state.instances.find((item) => item.instanceId === instanceId)?.durationMs ?? null
  state.remoteVideoWatchProgressByInstanceId[instanceId] = {
    projectId: VIRTUAL_STUDY_REVIEW_PROJECT_ID,
    instanceId,
    durationMs,
    watchedMs: Math.max(current?.watchedMs ?? 0, Math.max(0, Math.floor(params.watchedMs))),
    ranges: current?.ranges ?? [],
    completedAt: params.completed ? nowIso() : current?.completedAt ?? null,
    updatedAt: nowIso(),
  }
}

export function getClonedVirtualStudyReviewState() {
  return cloneVirtualStudyReviewState()
}

export { removeVirtualStudyReviewLocalStorage }

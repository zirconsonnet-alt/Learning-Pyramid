import type { Instance } from "@/ui/api/instances"
import type { LearningObjectNode } from "@/ui/api/learningObjects"
import type { LearningPlan, LearningPlanProgressSnapshot } from "@/ui/store/learningPlanStore"
import { diffDateKeysInclusive } from "@/ui/store/learningPlanStore"
import type { DailyStudyMetricEntry } from "@/ui/store/workbenchDailyStats"

export type LearningPlanFeasibility = "unknown" | "very_easy" | "on_track" | "hard" | "finished" | "overdue"

export type LearningPlanEvaluation = {
  plan: LearningPlan
  progressRatio: number
  expectedRatio: number
  todayDeltaRatio: number
  expectedDailyRatio: number
  totalLeafCount: number
  completedLeafCount: number
  totalVideoMs: number
  watchedVideoMs: number
  elapsedDays: number
  daysLeft: number
  recentActiveDays: number
  recentAverageEffectiveMs: number
  estimatedDaysRemaining: number | null
  feasibility: LearningPlanFeasibility
  summary: string
  dailySummary: string
}

type EvaluateInput = {
  plan: LearningPlan
  todayDateKey: string
  nodes: LearningObjectNode[]
  instances: Instance[]
  videoDurationByInstanceId: Record<string, number>
  videoWatchedMsByInstanceId: Record<string, number>
  recallPointCountByInstanceId: Record<string, number>
  entries: DailyStudyMetricEntry[]
  progressSnapshots: Record<string, LearningPlanProgressSnapshot> | undefined
}

function clampRatio(value: number) {
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.min(1, value))
}

function formatPercent(value: number) {
  return `${Math.round(clampRatio(value) * 100)}%`
}

function getPreviousDateKey(dateKey: string) {
  const [year, month, day] = dateKey.split("-").map((part) => Number(part))
  const date = new Date(year || 1970, (month || 1) - 1, day || 1)
  date.setDate(date.getDate() - 1)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`
}

function descendantLeafInstanceIds(nodes: LearningObjectNode[], selectedNodeIds: string[]) {
  const selected = new Set(selectedNodeIds)
  const nodesById = new Map(nodes.map((node) => [node.nodeId, node]))
  const childrenByParent = new Map<string, string[]>()
  for (const node of nodes) {
    if (!node.parentId) continue
    childrenByParent.set(node.parentId, [...(childrenByParent.get(node.parentId) ?? []), node.nodeId])
  }

  const leafInstanceIds = new Set<string>()
  const visit = (nodeId: string) => {
    const node = nodesById.get(nodeId)
    if (!node) return
    if (node.kind === "leaf") {
      leafInstanceIds.add(node.instanceId)
      return
    }
    for (const childId of childrenByParent.get(node.nodeId) ?? node.children ?? []) {
      visit(childId)
    }
  }

  if (selected.size === 0) {
    for (const node of nodes) {
      if (node.kind === "leaf") leafInstanceIds.add(node.instanceId)
    }
    return leafInstanceIds
  }

  for (const nodeId of selected) visit(nodeId)
  return leafInstanceIds
}

function getScopeInstanceIds(plan: LearningPlan, nodes: LearningObjectNode[], instances: Instance[]) {
  const nodeIds = plan.targetKind === "LEARNING_OBJECT_NODES" ? plan.learningObjectNodeIds : []
  const fromNodes = descendantLeafInstanceIds(nodes, nodeIds)
  if (fromNodes.size > 0) return fromNodes
  if (plan.targetKind === "PROJECT") return new Set(instances.map((instance) => instance.instanceId))
  return fromNodes
}

function recentStudyStats(entries: DailyStudyMetricEntry[], todayDateKey: string) {
  const recent = entries
    .filter((entry) => entry.dateKey <= todayDateKey)
    .sort((left, right) => right.dateKey.localeCompare(left.dateKey))
    .slice(0, 14)
  const active = recent.filter((entry) => entry.effectiveMs > 0)
  const totalMs = active.reduce((sum, entry) => sum + Math.max(0, entry.effectiveMs), 0)
  return {
    activeDays: active.length,
    averageEffectiveMs: active.length > 0 ? totalMs / active.length : 0,
  }
}

function buildSummary(params: {
  feasibility: LearningPlanFeasibility
  progressRatio: number
  expectedRatio: number
  daysLeft: number
  estimatedDaysRemaining: number | null
}) {
  const progress = formatPercent(params.progressRatio)
  const expected = formatPercent(params.expectedRatio)
  if (params.feasibility === "finished") return `计划已接近完成：当前 ${progress}。`
  if (params.feasibility === "overdue") return `计划已经到期：当前 ${progress}，原本今天应接近 ${expected}。`
  if (params.feasibility === "hard") {
    return params.estimatedDaysRemaining === null
      ? `当前 ${progress}，按计划今天应到 ${expected}。需要先积累一两天有效学习数据。`
      : `当前 ${progress}，按计划今天应到 ${expected}；按近期节奏估计还要 ${Math.ceil(params.estimatedDaysRemaining)} 天，压力偏大。`
  }
  if (params.feasibility === "very_easy") return `当前 ${progress}，领先计划 ${formatPercent(params.progressRatio - params.expectedRatio)}，有提前完成的潜力。`
  if (params.feasibility === "unknown") return `当前 ${progress}。继续学习并打开工作台后，系统会用进度快照和历史学习时间修正判断。`
  return `当前 ${progress}，计划进度约 ${expected}；剩余 ${Math.max(0, params.daysLeft)} 天。`
}

function buildDailySummary(todayDeltaRatio: number, expectedDailyRatio: number) {
  if (expectedDailyRatio <= 0) return "今天没有可比较的计划基准。"
  const ratio = todayDeltaRatio / expectedDailyRatio
  if (todayDeltaRatio <= 0) return `今天还没有推动这个计划；按均匀节奏，今天最好推进约 ${formatPercent(expectedDailyRatio)}。`
  if (ratio >= 1.25) return `今天推进 ${formatPercent(todayDeltaRatio)}，高于计划日均 ${formatPercent(expectedDailyRatio)}，有提前完成潜力。`
  if (ratio < 0.75) return `今天推进 ${formatPercent(todayDeltaRatio)}，低于计划日均 ${formatPercent(expectedDailyRatio)}，正在拖慢计划。`
  return `今天推进 ${formatPercent(todayDeltaRatio)}，接近计划日均 ${formatPercent(expectedDailyRatio)}。`
}

export function evaluateLearningPlan(input: EvaluateInput): LearningPlanEvaluation {
  const scopeInstanceIds = getScopeInstanceIds(input.plan, input.nodes, input.instances)
  const scopeIds = [...scopeInstanceIds]
  let totalVideoMs = 0
  let watchedVideoMs = 0
  let completedLeafCount = 0

  for (const instanceId of scopeIds) {
    const durationMs = Math.max(0, input.videoDurationByInstanceId[instanceId] ?? 0)
    const watchedMs = Math.max(0, input.videoWatchedMsByInstanceId[instanceId] ?? 0)
    const recallPointCount = Math.max(0, input.recallPointCountByInstanceId[instanceId] ?? 0)
    totalVideoMs += durationMs
    watchedVideoMs += durationMs > 0 ? Math.min(durationMs, watchedMs) : 0
    const enoughWatch = durationMs > 0 && watchedMs >= durationMs * 0.8
    if (recallPointCount > 0 || enoughWatch) completedLeafCount += 1
  }

  const leafRatio = scopeIds.length > 0 ? completedLeafCount / scopeIds.length : 0
  const videoRatio = totalVideoMs > 0 ? watchedVideoMs / totalVideoMs : 0
  const progressRatio = clampRatio(totalVideoMs > 0 ? Math.max(videoRatio, leafRatio * 0.6) : leafRatio)

  const totalDays = diffDateKeysInclusive(input.plan.createdDateKey, input.plan.dueDateKey)
  const elapsedDays = Math.min(totalDays, diffDateKeysInclusive(input.plan.createdDateKey, input.todayDateKey))
  const daysLeft = Math.max(0, diffDateKeysInclusive(input.todayDateKey, input.plan.dueDateKey) - 1)
  const expectedRatio = clampRatio(elapsedDays / totalDays)
  const expectedDailyRatio = totalDays > 0 ? 1 / totalDays : 1

  const previousSnapshot = input.progressSnapshots?.[getPreviousDateKey(input.todayDateKey)]
  const todayDeltaRatio = Math.max(0, progressRatio - (previousSnapshot?.progressRatio ?? progressRatio))
  const recent = recentStudyStats(input.entries, input.todayDateKey)
  const effectiveMsSoFar = input.entries.reduce((sum, entry) => sum + Math.max(0, entry.effectiveMs), 0)
  const progressPerEffectiveMs = effectiveMsSoFar > 0 && progressRatio > 0 ? progressRatio / effectiveMsSoFar : 0
  const recentDailyProgress = progressPerEffectiveMs * recent.averageEffectiveMs
  const estimatedDaysRemaining = recentDailyProgress > 0 ? (1 - progressRatio) / recentDailyProgress : null

  let feasibility: LearningPlanFeasibility = "unknown"
  if (progressRatio >= 0.98) feasibility = "finished"
  else if (input.todayDateKey > input.plan.dueDateKey) feasibility = "overdue"
  else if (recent.activeDays < 2 && progressRatio < 0.1) feasibility = "unknown"
  else if (estimatedDaysRemaining !== null && estimatedDaysRemaining > daysLeft + 1) feasibility = "hard"
  else if (progressRatio >= expectedRatio + expectedDailyRatio * 1.5) feasibility = "very_easy"
  else if (progressRatio + expectedDailyRatio < expectedRatio) feasibility = "hard"
  else feasibility = "on_track"

  return {
    plan: input.plan,
    progressRatio,
    expectedRatio,
    todayDeltaRatio,
    expectedDailyRatio,
    totalLeafCount: scopeIds.length,
    completedLeafCount,
    totalVideoMs,
    watchedVideoMs,
    elapsedDays,
    daysLeft,
    recentActiveDays: recent.activeDays,
    recentAverageEffectiveMs: recent.averageEffectiveMs,
    estimatedDaysRemaining,
    feasibility,
    summary: buildSummary({ feasibility, progressRatio, expectedRatio, daysLeft, estimatedDaysRemaining }),
    dailySummary: buildDailySummary(todayDeltaRatio, expectedDailyRatio),
  }
}

export function summarizeLearningPlanDaily(
  plan: LearningPlan,
  snapshots: Record<string, LearningPlanProgressSnapshot> | undefined,
  todayDateKey: string,
) {
  const today = snapshots?.[todayDateKey]?.progressRatio
  const yesterday = snapshots?.[getPreviousDateKey(todayDateKey)]?.progressRatio
  const totalDays = diffDateKeysInclusive(plan.createdDateKey, plan.dueDateKey)
  const expectedDailyRatio = totalDays > 0 ? 1 / totalDays : 1
  const todayDeltaRatio = Math.max(0, (today ?? yesterday ?? 0) - (yesterday ?? today ?? 0))
  return buildDailySummary(todayDeltaRatio, expectedDailyRatio)
}

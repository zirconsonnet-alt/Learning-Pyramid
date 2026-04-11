import { useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import { useQueries, useQuery } from "@tanstack/react-query"
import { FolderTree, RadioTower } from "lucide-react"
import { useNavigate, useParams, useSearchParams } from "react-router-dom"

import { getBaseUrl } from "@/ui/api/http"
import { ApiError } from "@/ui/api/http"
import { listRecallPointsByInstance } from "@/ui/api/instances"
import type { Instance } from "@/ui/api/instances"
import { listLearningObjectNodes, type LearningObjectNode } from "@/ui/api/learningObjects"
import { getInstancePlaybackDescriptor } from "@/ui/api/media"
import type { LearningTaskNode } from "@/ui/api/learningTaskNodes"
import type { ProjectType } from "@/ui/api/projects"
import type { SubjectContext } from "@/ui/api/subjects"
import { ContentNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { projectTypeRequiresLearningObjectTree, projectTypeUsesResolvableCourseAnchor } from "@/ui/projectTypes"
import { resolveProjectFile, useProjectDirectoryBinding } from "@/ui/localMedia/projectDirectory"
import { useAuditLogEvents } from "@/ui/queries/auditLog"
import { useLearningTaskNodes } from "@/ui/queries/learningTasks"
import { useSubjectContext } from "@/ui/queries/subjects"
import { useSystemCapabilities } from "@/ui/queries/system"
import {
  useInstances,
  useLayers,
  useManualRollUp,
  useProjectConfig,
  useQueue,
  useSetLayerConfig,
} from "@/ui/queries/workbench"
import { useAppStore } from "@/ui/store/appStore"
import { evaluateLearningPlan } from "@/ui/learningPlans/learningPlanEvaluation"
import { selectActiveLearningPlans, useLearningPlanStore } from "@/ui/store/learningPlanStore"
import { getLocalDateKey, listDailyStudyMetricEntries, loadDailyWorkbenchStats } from "@/ui/store/workbenchDailyStats"
import { showErrorFeedback, showInfoFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { syncStudyMetricsSnapshot } from "@/ui/studyMetricsSync"
import { createStudyPresenceTracker, loadDailyProjectStudyPresence } from "@/ui/store/studyPresenceStore"
import { loadVideoDurationMap, saveVideoDurationMs } from "@/ui/store/videoDurations"
import { loadVideoWatchCoverageMap } from "@/ui/store/videoWatchCoverage"
import { formatStudyMaterialTypeLabel } from "@/ui/subjects/studyMaterials"
import { useWorkbenchStore } from "@/ui/store/workbenchStore"
import { cn } from "@/ui/utils"
import { ComposePane } from "@/views/workbench/components/ComposePane"
import { LearningPlanCard } from "@/views/workbench/components/LearningPlanCard"
import { LearningObjectTree } from "@/views/workbench/components/LearningObjectTree"
import { ReviewPane } from "@/views/workbench/components/ReviewPane"
import { RollupPane } from "@/views/workbench/components/RollupPane"
import { VideoPane } from "@/views/workbench/components/VideoPane"
import { estimateProjectStudyTime } from "@/views/workbench/studyEstimate"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function parseAnchorMs(position: string): number | null {
  const m = position.match(/^t=(\d+)$/)
  if (!m) return null
  const n = Number(m[1])
  return Number.isFinite(n) ? n : null
}

function formatDurationCompact(ms: number) {
  if (!Number.isFinite(ms) || ms <= 0) return "0m"
  const totalMinutes = Math.floor(ms / 60000)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours <= 0) return `${Math.max(1, minutes)}m`
  if (minutes === 0) return `${hours}h`
  return `${hours}h ${minutes}m`
}

function formatPercent(value: number) {
  if (!Number.isFinite(value)) return "0%"
  return `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`
}

function getDateKeyDaysAgo(days: number, from = new Date()) {
  const next = new Date(from)
  next.setDate(next.getDate() - Math.max(0, Math.floor(days)))
  return getLocalDateKey(next)
}

function parseAuditPayloadCount(payload: string, key: string) {
  try {
    const parsed = JSON.parse(payload) as Record<string, unknown>
    const value = parsed[key]
    return typeof value === "number" && Number.isFinite(value) ? value : 0
  } catch {
    return 0
  }
}

function isRelativeMaterialId(materialId: string) {
  const normalized = String(materialId).replace(/\\/g, "/").trim()
  if (!normalized) return false
  if (normalized.startsWith("/")) return false
  if (/^[A-Za-z]:\//.test(normalized)) return false
  return !normalized.split("/").some((part) => part === "." || part === "..")
}

const DURATION_PROBE_CONCURRENCY = 4
const RECALL_POINT_PROBE_CONCURRENCY = 2

function readMediaDurationMs(src: string) {
  return new Promise<number>((resolve, reject) => {
    const video = document.createElement("video")
    let settled = false

    const cleanup = () => {
      video.removeEventListener("loadedmetadata", handleLoadedMetadata)
      video.removeEventListener("error", handleError)
      video.pause()
      video.removeAttribute("src")
      video.load()
    }

    const finish = (fn: () => void) => {
      if (settled) return
      settled = true
      cleanup()
      fn()
    }

    const handleLoadedMetadata = () => {
      const durationMs = Number.isFinite(video.duration) && video.duration > 0 ? Math.floor(video.duration * 1000) : 0
      finish(() => resolve(durationMs))
    }

    const handleError = () => finish(() => reject(new Error("读取媒体 metadata 失败")))

    video.preload = "metadata"
    video.addEventListener("loadedmetadata", handleLoadedMetadata, { once: true })
    video.addEventListener("error", handleError, { once: true })
    video.src = src
  })
}

async function resolveInstanceDurationMs(params: {
  projectId: string
  instance: Instance
  serverMediaStreamEnabled: boolean
  browserLocalMediaEnabled: boolean
  directoryPermission: "unsupported" | "missing" | "prompt" | "granted" | "denied"
}) {
  const { projectId, instance, serverMediaStreamEnabled, browserLocalMediaEnabled, directoryPermission } = params
  if (typeof instance.durationMs === "number" && instance.durationMs > 0) {
    return instance.durationMs
  }
  if (instance.playbackKind === "HLS" || instance.mediaSourceKind === "BAIDU_NETDISK") {
    const playback = await getInstancePlaybackDescriptor(projectId, instance.instanceId, { timeoutMs: 90_000 })
    if (typeof playback.durationMs === "number" && playback.durationMs > 0) {
      return playback.durationMs
    }
    return null
  }
  if (serverMediaStreamEnabled) {
    return await readMediaDurationMs(`${getBaseUrl()}/projects/${projectId}/media/instances/${instance.instanceId}`)
  }
  if (!browserLocalMediaEnabled || directoryPermission !== "granted") return null
  if (!isRelativeMaterialId(instance.materialId)) return null

  const file = await resolveProjectFile(projectId, instance.materialId)
  if (!file) return null

  const objectUrl = URL.createObjectURL(file)
  try {
    return await readMediaDurationMs(objectUrl)
  } finally {
    URL.revokeObjectURL(objectUrl)
  }
}

function StatusMetricRow(props: { label: string; value: string; emphasize?: boolean }) {
  const { label, value } = props
  return (
    <div className="flex items-center justify-between gap-4 py-2.5">
      <div className="text-[13px] font-medium text-muted-foreground">{label}</div>
      <div className={cn("text-[15px] font-semibold tracking-[-0.02em]", props.emphasize ? "text-foreground" : "text-[color:var(--theme-soft-text-strong)]")}>
        {value}
      </div>
    </div>
  )
}

function SidebarSectionTitle(props: { title: string; note?: string }) {
  const { title, note } = props
  return (
    <div className="flex items-start justify-between gap-3">
      <div>
        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">{title}</div>
        {note ? <div className="mt-1 text-[12px] leading-5 text-muted-foreground">{note}</div> : null}
      </div>
    </div>
  )
}

function SubjectContextCard(props: { context: SubjectContext; onOpenMaterial: (projectId: string, target: "workbench" | "settings") => void }) {
  const { context, onOpenMaterial } = props
  const [materialsExpanded, setMaterialsExpanded] = useState(false)
  const hasMultipleMaterials = context.materials.length > 1
  const shouldCollapseMaterials = context.materials.length > 3
  const visibleMaterials = shouldCollapseMaterials && !materialsExpanded ? context.materials.slice(0, 3) : context.materials
  const hiddenMaterialCount = Math.max(0, context.materials.length - visibleMaterials.length)

  return (
    <section className="rounded-[1.15rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-3.5">
      <div className="text-[12px] font-medium text-muted-foreground">{context.isSubjectRoot ? "当前学科" : "当前材料"}</div>
      <div className="mt-1 text-[17px] font-semibold tracking-[-0.02em] text-[color:var(--theme-soft-text-strong)]">
        {context.isSubjectRoot ? context.subject.title : context.currentMaterial.title}
      </div>
      {!context.isSubjectRoot ? <div className="mt-1 text-[12px] text-muted-foreground">所属学科：{context.subject.title}</div> : null}
      {hasMultipleMaterials ? (
        <div className="mt-3 space-y-2">
          <div className="flex items-center justify-between gap-3">
            <div className="text-[12px] font-medium text-muted-foreground">同学科材料</div>
            {shouldCollapseMaterials ? (
              <button
                type="button"
                className="text-xs font-medium text-primary transition-colors hover:text-primary/80"
                onClick={() => setMaterialsExpanded((current) => !current)}
              >
                {materialsExpanded ? "收起" : `查看其余 ${hiddenMaterialCount} 个`}
              </button>
            ) : null}
          </div>
          <div className="grid gap-2">
            {visibleMaterials.map((material) => {
              const compatibilityProjectId = material.compatibilityProjectId
              const active = compatibilityProjectId === context.currentProjectId
              return (
                <div key={material.materialId} className="rounded-xl border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] px-3 py-2.5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-foreground">{material.title}</div>
                      <div className="mt-1 text-[11px] text-muted-foreground">{formatStudyMaterialTypeLabel(material.materialType)}</div>
                    </div>
                    {active ? <span className="theme-meta-strong">当前</span> : null}
                  </div>
                  {compatibilityProjectId ? (
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Button type="button" size="sm" variant={active ? "secondary" : "outline"} onClick={() => onOpenMaterial(compatibilityProjectId, "workbench")}>
                        工作台
                      </Button>
                      <Button type="button" size="sm" variant="outline" onClick={() => onOpenMaterial(compatibilityProjectId, "settings")}>
                        设置
                      </Button>
                    </div>
                  ) : null}
                </div>
              )
            })}
          </div>
        </div>
      ) : null}
    </section>
  )
}

function StudyModePane({
  projectType,
  instance,
}: {
  projectType: ProjectType
  instance: Instance | null
}) {
  return (
    <Card className="theme-card-main">
      <CardHeader className="theme-card-header">
        <CardTitle>{projectType === "BOOK" ? "书本定位" : projectType === "MISTAKE_BOOK" ? "错题整理模式" : "零散知识点模式"}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 pt-5">
        <div className="rounded-[1.15rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] px-4 py-4 text-sm leading-6 text-[color:var(--theme-soft-text-strong)]">
          {projectType === "BOOK"
            ? instance
              ? `当前正在“${instance.materialDisplayName}”下录入复述点。请为每条复述点填写页码、章节、小节、题号或段落说明等文本锚点。`
              : "请先从左侧目录中选择一个章节、小节或条目，再开始录入书本复述点。"
            : projectType === "MISTAKE_BOOK"
              ? instance
                ? `当前正在“${instance.materialDisplayName}”下整理错题。你可以继续补充题面、答案、来源说明，并把它们纳入后续复习。`
                : "请先从左侧目录中选择一个错题条目或章节，再开始整理错题。"
            : "当前项目按零散知识点模式运行。你可以直接录入复述点，不需要选择学习对象，也不需要绑定锚点。"}
        </div>
      </CardContent>
    </Card>
  )
}

export function WorkbenchPage() {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const pid = projectId ?? ""

  const ensure = useWorkbenchStore((s) => s.ensure)
  const ps = useWorkbenchStore((s) => (pid ? s.byProjectId[pid] : undefined))
  const setSelectedInstanceId = useWorkbenchStore((s) => s.setSelectedInstanceId)

  const selectedProjectId = useAppStore((s) => s.selectedProjectId)

  const [currentMs, setCurrentMs] = useState(0)
  const [seekTo, setSeekTo] = useState<{ instanceId: string; ms: number; nonce: number } | null>(null)
  const [centerPanelMode, setCenterPanelMode] = useState<"main" | "rollup">("main")
  const [sidebarStatsExpanded, setSidebarStatsExpanded] = useState(false)
  const videoPaneRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!pid) return
    ensure(pid)
  }, [ensure, pid])

  useEffect(() => {
    if (pid && selectedProjectId !== pid) {
      useAppStore.getState().setSelectedProjectId(pid)
    }
  }, [pid, selectedProjectId])

  const instancesQ = useInstances(pid)
  const learningTaskNodesQ = useLearningTaskNodes(pid)
  const queueQ = useQueue(pid)
  const layersQ = useLayers(pid)
  const auditLogQ = useAuditLogEvents(pid)
  const rollUpM = useManualRollUp(pid)
  const projectConfigQ = useProjectConfig(pid)
  const subjectContextQ = useSubjectContext(pid, !!pid)
  const setLayerConfigM = useSetLayerConfig(pid)
  const capabilitiesQ = useSystemCapabilities()
  const directoryBinding = useProjectDirectoryBinding(pid)
  const projectType = projectConfigQ.data?.projectType ?? "COURSE"
  const currentRollUpStrategy = projectConfigQ.data?.rollUpStrategy ?? "THRESHOLD_AUTO"
  const requiresLearningObjectTree = projectTypeRequiresLearningObjectTree(projectType)
  const usesResolvableCourseAnchor = projectTypeUsesResolvableCourseAnchor(projectType)
  const learningObjectNodesQ = useQuery({
    queryKey: ["learningObjectNodes", pid],
    queryFn: () => listLearningObjectNodes(pid),
    enabled: !!pid && requiresLearningObjectTree,
  })

  const selectedInstanceId = ps?.selectedInstanceId ?? null
  const queueHasGate = !!queueQ.data?.headId
  const queueLength = queueQ.data?.ids.length ?? 0
  const serverMediaStreamEnabled = capabilitiesQ.data?.serverMediaStreamEnabled ?? false
  const browserLocalMediaEnabled = capabilitiesQ.data?.browserLocalMediaEnabled ?? false

  const instance: Instance | null = useMemo(() => {
    const items = instancesQ.data ?? []
    return selectedInstanceId ? items.find((i) => i.instanceId === selectedInstanceId) ?? null : null
  }, [instancesQ.data, selectedInstanceId])
  const missingInstances = useMemo(
    () => (instancesQ.data ?? []).filter((item) => item.presence === "MISSING"),
    [instancesQ.data],
  )
  const missingRecallPointQs = useQueries({
    queries: missingInstances.map((item) => ({
      queryKey: ["recallPointsByInstance", pid, item.instanceId],
      queryFn: () => listRecallPointsByInstance(pid, item.instanceId),
      enabled: !!pid,
    })),
  })
  const actionableMissingInstanceCount = useMemo(
    () =>
      missingInstances.filter((_, index) => {
        const query = missingRecallPointQs[index]
        if (!query || query.isLoading || query.error) return true
        return (query.data?.recallPointIds ?? []).length > 0
      }).length,
    [missingInstances, missingRecallPointQs],
  )
  const actionableMissingGate = actionableMissingInstanceCount > 0

  const learningTaskNodesById = useMemo(() => {
    const map: Record<string, LearningTaskNode> = {}
    for (const node of learningTaskNodesQ.data ?? []) map[node.nodeId] = node
    return map
  }, [learningTaskNodesQ.data])
  const [todayStats, setTodayStats] = useState(() => loadDailyWorkbenchStats(pid))
  const [todayPresenceStats, setTodayPresenceStats] = useState(() => loadDailyProjectStudyPresence(pid))
  const [studyEstimateRevision, setStudyEstimateRevision] = useState(0)
  const [videoDurationByInstanceId, setVideoDurationByInstanceId] = useState<Record<string, number>>({})
  const [videoWatchedMsByInstanceId, setVideoWatchedMsByInstanceId] = useState<Record<string, number>>({})
  const [durationProbeAttemptedByInstanceId, setDurationProbeAttemptedByInstanceId] = useState<Record<string, true>>({})
  const [durationProbeInFlightByInstanceId, setDurationProbeInFlightByInstanceId] = useState<Record<string, true>>({})
  const [recallPointCountByInstanceId, setRecallPointCountByInstanceId] = useState<Record<string, number>>({})
  const [recallPointProbeStatusByInstanceId, setRecallPointProbeStatusByInstanceId] = useState<Record<string, "ready" | "empty" | "failed">>({})
  const [recallPointProbeInFlightByInstanceId, setRecallPointProbeInFlightByInstanceId] = useState<Record<string, true>>({})
  const durationProbeSessionRef = useRef(0)
  const recallPointProbeSessionRef = useRef(0)
  const plansById = useLearningPlanStore((state) => state.plansById)
  const progressSnapshotsByPlanId = useLearningPlanStore((state) => state.progressSnapshotsByPlanId)
  const upsertLearningPlan = useLearningPlanStore((state) => state.upsertPlan)
  const archiveLearningPlan = useLearningPlanStore((state) => state.archivePlan)
  const recordLearningPlanProgressSnapshot = useLearningPlanStore((state) => state.recordProgressSnapshot)
  const activeLearningPlans = useMemo(() => selectActiveLearningPlans(plansById, pid), [pid, plansById])
  const activeLearningPlan = activeLearningPlans[0] ?? null

  useEffect(() => {
    if (!pid) return
    setTodayStats(loadDailyWorkbenchStats(pid))
    setTodayPresenceStats(loadDailyProjectStudyPresence(pid))
    const timer = window.setInterval(() => {
      setTodayStats(loadDailyWorkbenchStats(pid))
      setTodayPresenceStats(loadDailyProjectStudyPresence(pid))
    }, 1000)
    return () => window.clearInterval(timer)
  }, [pid])

  useEffect(() => {
    if (!pid) return
    const tracker = createStudyPresenceTracker(pid)
    const touch = () => tracker.touch()
    tracker.start()
    window.addEventListener("pointerdown", touch, { passive: true })
    window.addEventListener("keydown", touch)
    window.addEventListener("wheel", touch, { passive: true })
    window.addEventListener("scroll", touch, { passive: true })
    return () => {
      window.removeEventListener("pointerdown", touch)
      window.removeEventListener("keydown", touch)
      window.removeEventListener("wheel", touch)
      window.removeEventListener("scroll", touch)
      tracker.stop()
      setTodayPresenceStats(loadDailyProjectStudyPresence(pid))
    }
  }, [pid])

  const todayDateKey = getLocalDateKey()
  const estimateDateFrom = useMemo(() => getDateKeyDaysAgo(180), [todayDateKey])

  useEffect(() => {
    if (!pid) return
    if (!capabilitiesQ.data?.authEnabled) return

    let cancelled = false

    async function runStudyMetricsSync() {
      try {
        await syncStudyMetricsSnapshot({
          projectIds: [pid],
          dateFrom: todayDateKey,
          dateTo: todayDateKey,
        })
        if (!cancelled) {
          setTodayStats(loadDailyWorkbenchStats(pid))
        }
      } catch {
        // Keep the workbench usable even when the hosted sync request is unavailable.
      }
    }

    void runStudyMetricsSync()
    const timer = window.setInterval(() => {
      void runStudyMetricsSync()
    }, 30_000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [capabilitiesQ.data?.authEnabled, pid, todayDateKey])

  useEffect(() => {
    if (!pid) return
    if (!capabilitiesQ.data?.authEnabled) return

    let cancelled = false

    async function runHistoricalStudyMetricsSync() {
      try {
        await syncStudyMetricsSnapshot({
          projectIds: [pid],
          dateFrom: estimateDateFrom,
          dateTo: todayDateKey,
        })
        if (!cancelled) {
          setStudyEstimateRevision((current) => current + 1)
        }
      } catch {
        // Keep the page responsive even when historical sync is temporarily unavailable.
      }
    }

    void runHistoricalStudyMetricsSync()
    return () => {
      cancelled = true
    }
  }, [capabilitiesQ.data?.authEnabled, estimateDateFrom, pid, todayDateKey])

  const todayAuditStats = useMemo(() => {
    let submittedRecallPoints = 0
    let reviewedRecallPoints = 0
    for (const event of auditLogQ.data ?? []) {
      const occurredAt = new Date(event.occurredAt)
      if (Number.isNaN(occurredAt.getTime()) || getLocalDateKey(occurredAt) !== todayDateKey) continue
      if (event.kind === "SUBMIT_LEARNING_TASK") {
        submittedRecallPoints += parseAuditPayloadCount(event.payload, "itemsCount")
      }
      if (event.kind === "EXECUTOR_COMMIT_REVIEW_TASK") {
        reviewedRecallPoints += parseAuditPayloadCount(event.payload, "canRecallLen")
      }
    }
    return { submittedRecallPoints, reviewedRecallPoints }
  }, [auditLogQ.data, todayDateKey])

  useEffect(() => {
    if (!pid) return
    if (!instancesQ.data) return
    if (selectedInstanceId && !instancesQ.data.some((i) => i.instanceId === selectedInstanceId)) {
      setSelectedInstanceId(pid, null)
    }
  }, [instancesQ.data, pid, selectedInstanceId, setSelectedInstanceId])

  useEffect(() => {
    if (!pid) return
    const requestedInstanceId = searchParams.get("instanceId")?.trim() ?? ""
    if (!requestedInstanceId) return
    setSelectedInstanceId(pid, requestedInstanceId)

    const requestedPosition = searchParams.get("position")?.trim() ?? ""
    const requestedMs = parseAnchorMs(requestedPosition)
    if (requestedMs === null) return

    setSeekTo((current) => {
      if (current && current.instanceId === requestedInstanceId && current.ms === requestedMs) return current
      return { instanceId: requestedInstanceId, ms: requestedMs, nonce: Date.now() }
    })
  }, [pid, searchParams, setSelectedInstanceId])

  useEffect(() => {
    if (!pid) {
      setVideoDurationByInstanceId({})
      setVideoWatchedMsByInstanceId({})
      return
    }
    const instanceIds = (instancesQ.data ?? []).map((item) => item.instanceId)
    const stored = loadVideoDurationMap(pid, instanceIds)
    const fromInstances = Object.fromEntries(
      (instancesQ.data ?? [])
        .filter((item) => typeof item.durationMs === "number" && item.durationMs > 0)
        .map((item) => [item.instanceId, item.durationMs as number]),
    )
    const nextDurationByInstanceId = { ...stored, ...fromInstances }
    setVideoDurationByInstanceId(nextDurationByInstanceId)
    setVideoWatchedMsByInstanceId(loadVideoWatchCoverageMap(pid, instanceIds, nextDurationByInstanceId))
  }, [instancesQ.data, pid])

  useEffect(() => {
    if (!pid) return
    const instanceIds = (instancesQ.data ?? []).map((item) => item.instanceId)

    const refreshWatchCoverage = () => {
      setVideoWatchedMsByInstanceId(loadVideoWatchCoverageMap(pid, instanceIds, videoDurationByInstanceId))
    }

    refreshWatchCoverage()
    const timer = window.setInterval(refreshWatchCoverage, 1000)
    return () => window.clearInterval(timer)
  }, [instancesQ.data, pid, videoDurationByInstanceId])

  useEffect(() => {
    setDurationProbeAttemptedByInstanceId({})
    setDurationProbeInFlightByInstanceId({})
    durationProbeSessionRef.current += 1
  }, [browserLocalMediaEnabled, directoryBinding.permission, pid, serverMediaStreamEnabled, usesResolvableCourseAnchor])

  useEffect(() => {
    setRecallPointProbeStatusByInstanceId({})
    setRecallPointCountByInstanceId({})
    setRecallPointProbeInFlightByInstanceId({})
    recallPointProbeSessionRef.current += 1
  }, [pid, usesResolvableCourseAnchor])

  const pendingDurationProbeInstances = useMemo(() => {
    if (!usesResolvableCourseAnchor) return []
    const availableSlots = Math.max(0, DURATION_PROBE_CONCURRENCY - Object.keys(durationProbeInFlightByInstanceId).length)
    if (availableSlots <= 0) return []
    const pending: Instance[] = []
    for (const item of instancesQ.data ?? []) {
      if (videoDurationByInstanceId[item.instanceId]) continue
      if (durationProbeAttemptedByInstanceId[item.instanceId]) continue
      if (durationProbeInFlightByInstanceId[item.instanceId]) continue
      pending.push(item)
      if (pending.length >= availableSlots) break
    }
    return pending
  }, [durationProbeAttemptedByInstanceId, durationProbeInFlightByInstanceId, instancesQ.data, usesResolvableCourseAnchor, videoDurationByInstanceId])

  const pendingRecallPointProbeInstances = useMemo(() => {
    if (!usesResolvableCourseAnchor) return []
    const availableSlots = Math.max(0, RECALL_POINT_PROBE_CONCURRENCY - Object.keys(recallPointProbeInFlightByInstanceId).length)
    if (availableSlots <= 0) return []
    const pending: Instance[] = []
    for (const item of instancesQ.data ?? []) {
      if (recallPointProbeStatusByInstanceId[item.instanceId]) continue
      if (recallPointProbeInFlightByInstanceId[item.instanceId]) continue
      pending.push(item)
      if (pending.length >= availableSlots) break
    }
    return pending
  }, [instancesQ.data, recallPointProbeInFlightByInstanceId, recallPointProbeStatusByInstanceId, usesResolvableCourseAnchor])

  useEffect(() => {
    if (!pid || pendingDurationProbeInstances.length <= 0) return
    const probeSession = durationProbeSessionRef.current
    const pendingInstanceIds = pendingDurationProbeInstances.map((item) => item.instanceId)

    setDurationProbeAttemptedByInstanceId((current) => {
      let changed = false
      const next = { ...current }
      for (const instanceId of pendingInstanceIds) {
        if (next[instanceId]) continue
        next[instanceId] = true
        changed = true
      }
      return changed ? next : current
    })
    setDurationProbeInFlightByInstanceId((current) => {
      let changed = false
      const next = { ...current }
      for (const instanceId of pendingInstanceIds) {
        if (next[instanceId]) continue
        next[instanceId] = true
        changed = true
      }
      return changed ? next : current
    })

    for (const targetInstance of pendingDurationProbeInstances) {
      void (async () => {
        try {
          const durationMs = await resolveInstanceDurationMs({
            projectId: pid,
            instance: targetInstance,
            serverMediaStreamEnabled,
            browserLocalMediaEnabled,
            directoryPermission: directoryBinding.permission,
          })
          if (durationProbeSessionRef.current !== probeSession || !durationMs || durationMs <= 0) return
          saveVideoDurationMs(pid, targetInstance.instanceId, durationMs)
          setVideoDurationByInstanceId((current) =>
            current[targetInstance.instanceId] === durationMs ? current : { ...current, [targetInstance.instanceId]: durationMs },
          )
        } catch {
          // Ignore metadata probe failures and keep the dashboard responsive.
        } finally {
          if (durationProbeSessionRef.current === probeSession) {
            setDurationProbeInFlightByInstanceId((current) => {
              if (!current[targetInstance.instanceId]) return current
              const next = { ...current }
              delete next[targetInstance.instanceId]
              return next
            })
          }
        }
      })()
    }
  }, [browserLocalMediaEnabled, directoryBinding.permission, pendingDurationProbeInstances, pid, serverMediaStreamEnabled])

  useEffect(() => {
    if (!pid || pendingRecallPointProbeInstances.length <= 0) return
    const probeSession = recallPointProbeSessionRef.current
    const pendingInstanceIds = pendingRecallPointProbeInstances.map((item) => item.instanceId)

    setRecallPointProbeInFlightByInstanceId((current) => {
      let changed = false
      const next = { ...current }
      for (const instanceId of pendingInstanceIds) {
        if (next[instanceId]) continue
        next[instanceId] = true
        changed = true
      }
      return changed ? next : current
    })

    for (const targetInstance of pendingRecallPointProbeInstances) {
      void (async () => {
        try {
          const result = await listRecallPointsByInstance(pid, targetInstance.instanceId, { timeoutMs: 90_000 })
          if (recallPointProbeSessionRef.current !== probeSession) return
          setRecallPointCountByInstanceId((current) => ({
            ...current,
            [targetInstance.instanceId]: result.recallPointIds.length,
          }))
          setRecallPointProbeStatusByInstanceId((current) =>
            current[targetInstance.instanceId]
              ? current
              : {
                  ...current,
                  [targetInstance.instanceId]: result.recallPointIds.length > 0 ? "ready" : "empty",
                },
          )
        } catch {
          if (recallPointProbeSessionRef.current !== probeSession) return
          // This metric is advisory only; mark failures so the page stays responsive.
          setRecallPointProbeStatusByInstanceId((current) =>
            current[targetInstance.instanceId] ? current : { ...current, [targetInstance.instanceId]: "failed" },
          )
        } finally {
          if (recallPointProbeSessionRef.current === probeSession) {
            setRecallPointProbeInFlightByInstanceId((current) => {
              if (!current[targetInstance.instanceId]) return current
              const next = { ...current }
              delete next[targetInstance.instanceId]
              return next
            })
          }
        }
      })()
    }
  }, [pendingRecallPointProbeInstances, pid])

  const thresholdRollUpEnabledByLayerIndex = useMemo(
    () =>
      Object.fromEntries(
        (layersQ.data ?? []).map((layer) => [
          layer.layerIndex,
          projectConfigQ.data?.layerConfigs[String(layer.layerIndex)]?.thresholdRollUpEnabled ?? true,
        ]),
      ) as Record<number, boolean>,
    [layersQ.data, projectConfigQ.data?.layerConfigs],
  )

  const videoProgress = useMemo(() => {
    const items = instancesQ.data ?? []
    let totalMs = 0
    let watchedMs = 0
    for (const item of items) {
      const durationMs = videoDurationByInstanceId[item.instanceId] ?? 0
      totalMs += durationMs
      watchedMs += Math.min(durationMs, Math.max(0, videoWatchedMsByInstanceId[item.instanceId] ?? 0))
    }
    return { totalMs, watchedMs }
  }, [instancesQ.data, videoDurationByInstanceId, videoWatchedMsByInstanceId])

  const videoProgressPercent = videoProgress.totalMs > 0 ? Math.min(100, Math.max(0, (videoProgress.watchedMs / videoProgress.totalMs) * 100)) : 0
  const remainingDurationProbeCount = useMemo(
    () =>
      (instancesQ.data ?? []).filter(
        (item) =>
          !videoDurationByInstanceId[item.instanceId] &&
          (!durationProbeAttemptedByInstanceId[item.instanceId] || durationProbeInFlightByInstanceId[item.instanceId]),
      ).length,
    [durationProbeAttemptedByInstanceId, durationProbeInFlightByInstanceId, instancesQ.data, videoDurationByInstanceId],
  )
  const remainingRecallPointProbeCount = useMemo(
    () =>
      (instancesQ.data ?? []).filter(
        (item) => !recallPointProbeStatusByInstanceId[item.instanceId] || recallPointProbeInFlightByInstanceId[item.instanceId],
      ).length,
    [instancesQ.data, recallPointProbeInFlightByInstanceId, recallPointProbeStatusByInstanceId],
  )
  const projectStudyMetricEntries = useMemo(
    () => listDailyStudyMetricEntries([pid]),
    [pid, studyEstimateRevision, todayStats],
  )
  const projectRecallPointCount = useMemo(
    () => Object.values(recallPointCountByInstanceId).reduce((sum, count) => sum + Math.max(0, count), 0),
    [recallPointCountByInstanceId],
  )
  const projectCoveredVideoMs = useMemo(() => {
    return Object.values(videoWatchedMsByInstanceId).reduce((sum, watchedMs) => sum + Math.max(0, watchedMs), 0)
  }, [videoWatchedMsByInstanceId])
  const studyEstimate = useMemo(
    () =>
      estimateProjectStudyTime({
        totalVideoMs: videoProgress.totalMs,
        coveredVideoMs: projectCoveredVideoMs,
        recallPointCount: projectRecallPointCount,
        entries: projectStudyMetricEntries,
      }),
    [projectCoveredVideoMs, projectRecallPointCount, projectStudyMetricEntries, videoProgress.totalMs],
  )
  const learningPlanEvaluation = useMemo(() => {
    if (!activeLearningPlan) return null
    return evaluateLearningPlan({
      plan: activeLearningPlan,
      todayDateKey,
      nodes: learningObjectNodesQ.data ?? [],
      instances: instancesQ.data ?? [],
      videoDurationByInstanceId,
      videoWatchedMsByInstanceId,
      recallPointCountByInstanceId,
      entries: projectStudyMetricEntries,
      progressSnapshots: progressSnapshotsByPlanId[activeLearningPlan.planId],
    })
  }, [
    activeLearningPlan,
    instancesQ.data,
    learningObjectNodesQ.data,
    pid,
    progressSnapshotsByPlanId,
    projectStudyMetricEntries,
    recallPointCountByInstanceId,
    todayDateKey,
    videoDurationByInstanceId,
    videoWatchedMsByInstanceId,
  ])

  useEffect(() => {
    if (!learningPlanEvaluation) return
    recordLearningPlanProgressSnapshot(learningPlanEvaluation.plan.planId, todayDateKey, learningPlanEvaluation.progressRatio)
  }, [learningPlanEvaluation, recordLearningPlanProgressSnapshot, todayDateKey])

  const studyEstimatePresentation = useMemo(() => {
    if (!usesResolvableCourseAnchor) return null

    const pendingNotes: string[] = []
    if (remainingDurationProbeCount > 0) pendingNotes.push(`还有 ${remainingDurationProbeCount} 个视频时长在统计`)
    if (remainingRecallPointProbeCount > 0) pendingNotes.push(`还有 ${remainingRecallPointProbeCount} 个视频的复述点在扫描`)
    const pendingHint = pendingNotes.length > 0 ? `${pendingNotes.join("，")}，结果会继续修正。` : ""

    if (!studyEstimate) {
      return {
        value: "等待统计",
        detail: pendingHint || "当前项目的视频总时长还在建立中，完成后会开始推算剩余学习时长。",
      }
    }

    if (studyEstimate.status === "insufficient_data") {
      const sampleBits = [
        `已采样看 ${formatDurationCompact(studyEstimate.sampleWatchMs)}`,
        `构 ${studyEstimate.sampleRecallPointCount} 个复述点`,
      ]
      if (studyEstimate.sampleQaMs > 0) sampleBits.push(`问 ${formatDurationCompact(studyEstimate.sampleQaMs)}`)
      const reasonBits: string[] = []
      if (studyEstimate.sampleCompletedMs <= 0) reasonBits.push("历史有效学习区间还没累计起来")
      else if (studyEstimate.sampleWatchCoverageRatio < 0.35) reasonBits.push("观看样本偏低，暂时不足以代表当前项目节奏")
      const detail = `${sampleBits.join(" · ")}。${reasonBits[0] ?? "继续学习一段时间后，这里会给出更稳定的预计剩余时长。"}`
      return {
        value: "继续学习后生成",
        detail: pendingHint ? `${detail} ${pendingHint}` : detail,
      }
    }

    const completionPercent = Math.round(studyEstimate.completionRatio * 100)
    const confidenceLabel = studyEstimate.confidence === "high" ? "把握较高" : "持续修正中"
    const value = studyEstimate.remainingMs <= 60_000 && completionPercent >= 95 ? "接近完成" : formatDurationCompact(studyEstimate.remainingMs)
    const detail = `按当前节奏，完整学完约 ${formatDurationCompact(studyEstimate.predictedTotalMs)}，约 ${studyEstimate.predictedRecallPointCount} 个复述点，已完成约 ${completionPercent}%（${confidenceLabel}）。`
    return {
      value,
      detail: pendingHint ? `${detail} ${pendingHint}` : detail,
    }
  }, [remainingDurationProbeCount, remainingRecallPointProbeCount, studyEstimate, usesResolvableCourseAnchor])
  const todayStudyPresenceMs = Math.max(todayPresenceStats.presenceMs, todayStats.effectiveMs)
  const blankPresenceMs = Math.max(0, todayStudyPresenceMs - todayStats.effectiveMs)
  const focusRatio = todayStudyPresenceMs > 0 ? todayStats.effectiveMs / todayStudyPresenceMs : 0

  async function onManualRollUp(layerIndex: number) {
    if (queueHasGate) {
      showInfoFeedback("当前无法上推", "还有待完成的复习门禁，请先完成复习再继续层级推进。")
      return
    }
    if (actionableMissingGate) {
      showInfoFeedback("当前无法推进", `还有 ${actionableMissingInstanceCount} 个待迁移的缺失实例，请先在项目设置里完成修复。`)
      return
    }
    try {
      const result = await rollUpM.mutateAsync({ layerIndex })
      if (result.parentNodeId) {
        if (currentRollUpStrategy === "LEARNING_OBJECT_ISOMORPHIC") {
          showSuccessFeedback("对象树推进已完成", "系统已经按当前学习对象覆盖情况刷新对应层级。")
        } else {
          showSuccessFeedback("层级上推已完成", `L${layerIndex} 已生成新的聚合节点。`)
        }
      } else {
        showInfoFeedback(
          "层级状态已刷新",
          currentRollUpStrategy === "LEARNING_OBJECT_ISOMORPHIC"
            ? "当前对象树还没有新的可推进节点。"
            : `L${layerIndex} 目前没有新的聚合结果。`,
        )
      }
    } catch (err) {
      showErrorFeedback(currentRollUpStrategy === "LEARNING_OBJECT_ISOMORPHIC" ? "对象树推进失败" : "层级上推失败", formatApiError(err))
    }
  }

  async function onToggleThresholdRollUp(layerIndex: number, enabled: boolean) {
    try {
      await setLayerConfigM.mutateAsync({ layerIndex, thresholdRollUpEnabled: enabled })
      showSuccessFeedback(
        enabled ? "已恢复阈值上推" : "已禁止阈值上推",
        enabled
          ? `L${layerIndex} 达到阈值后会再次自动进入聚合周期。`
          : `L${layerIndex} 达到阈值后将不再自动上推，你仍然可以手动上推。`,
      )
    } catch (err) {
      showErrorFeedback(enabled ? "恢复阈值上推失败" : "禁止阈值上推失败", formatApiError(err))
    }
  }

  function onOpenAnchor(a: { instanceId: string; position: string }) {
    setCenterPanelMode("main")
    setSelectedInstanceId(pid, a.instanceId)
    window.requestAnimationFrame(() => {
      if (videoPaneRef.current) {
        videoPaneRef.current.scrollIntoView({ behavior: "smooth", block: "start" })
        return
      }
      window.scrollTo({ top: 0, behavior: "smooth" })
    })
    const ms = parseAnchorMs(a.position)
    if (ms === null) {
      setSeekTo(null)
      return
    }
    setSeekTo({ instanceId: a.instanceId, ms, nonce: Date.now() })
  }

  const workStatusDetail = queueQ.isLoading
    ? "正在同步状态"
    : queueLength > 0
      ? `${queueLength} 个任务待复习`
      : selectedInstanceId
        ? "正在学习"
        : projectType === "LOOSE_POINTS"
          ? "可直接录入"
          : projectType === "MISTAKE_BOOK"
            ? "等待整理"
          : "等待开始"

  function scrollToWorkbenchSection(sectionId: string) {
    const target = document.getElementById(sectionId)
    if (!target) return
    target.scrollIntoView({ behavior: "smooth", block: "start" })
  }

  if (!pid) {
    return (
      <div className="space-y-4">
        <ContentNotice
          title="当前工作台缺少项目上下文"
          message="当前链接缺少项目信息。请先返回项目列表，再重新进入工作台。"
          action={<Button onClick={() => navigate("/projects")}>返回项目列表</Button>}
        />
      </div>
    )
  }

  const courseContentPrepTitle =
    directoryBinding.permission === "missing"
      ? "先绑定并授权素材目录"
      : directoryBinding.permission === "prompt" || directoryBinding.permission === "denied"
        ? "先恢复目录权限"
        : "先导入内容目录"
  const courseContentPrepMessage =
    directoryBinding.permission === "missing"
      ? "还没有导入内容。先去项目设置绑定并授权素材目录，再导入内容；完成后回工作台选内容开始学习。"
      : directoryBinding.permission === "prompt"
        ? "浏览器还没拿到目录读取权限。先去项目设置继续授权，再导入内容；完成后回工作台选内容开始学习。"
        : directoryBinding.permission === "denied"
          ? "浏览器已经拒绝目录读取。先去项目设置重新授权，再导入内容；完成后回工作台选内容开始学习。"
          : "还没有导入内容。先去项目设置重新导入内容；完成后回工作台选内容开始学习。"

  let workbenchGuideNotice: ReactNode = null

  if (queueHasGate) {
    workbenchGuideNotice = (
      <ContentNotice
        title="当前先完成复习"
        message="系统已经排出了待复习内容。先完成这一轮复习，再继续录入新的复述点，节奏会更稳。"
        tone="info"
        action={
          <div className="flex flex-wrap gap-2">
            <Button
              onClick={() => {
                setCenterPanelMode("main")
                scrollToWorkbenchSection("workbench-review-pane")
              }}
            >
              去复习区
            </Button>
          </div>
        }
      />
    )
  } else if (actionableMissingGate) {
    workbenchGuideNotice = (
      <ContentNotice
        title="先修复缺失实例"
        message={`还有 ${actionableMissingInstanceCount} 个缺失实例会挡住继续学习。先去项目设置修复，修复后再回来继续。`}
        tone="info"
        action={
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => navigate(`/p/${pid}/settings`)}>去项目设置</Button>
          </div>
        }
      />
    )
  } else if (requiresLearningObjectTree && !instancesQ.isLoading && (instancesQ.data?.length ?? 0) === 0) {
    const noContentTitle =
      projectType === "BOOK" ? "先初始化书本目录" : projectType === "MISTAKE_BOOK" ? "先准备错题入口" : courseContentPrepTitle
    const noContentMessage =
      projectType === "BOOK"
        ? "还没有可用章节。先去项目设置初始化目录结构，完成后回工作台选章节开始学习。"
        : projectType === "MISTAKE_BOOK"
          ? "还没有可用错题条目。先去项目设置准备错题入口，完成后回工作台选条目开始整理。"
          : courseContentPrepMessage

    workbenchGuideNotice = (
      <ContentNotice
        title={noContentTitle}
        message={noContentMessage}
        tone="info"
        action={
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => navigate(`/p/${pid}/settings`)}>去项目设置</Button>
          </div>
        }
      />
    )
  } else if (requiresLearningObjectTree && !instancesQ.isLoading && (instancesQ.data?.length ?? 0) > 0 && !selectedInstanceId) {
    const selectContentTitle =
      projectType === "BOOK" ? "先从左侧选一个章节开始学习" : projectType === "MISTAKE_BOOK" ? "先从左侧选一个错题条目开始整理" : "先从左侧选一个视频开始学习"
    const selectContentMessage =
      projectType === "BOOK"
        ? "内容已准备好。先选中章节、小节或条目，再开始录入和回看。"
        : projectType === "MISTAKE_BOOK"
          ? "内容已准备好。先选中当前要整理的条目或章节，再继续录入和整理。"
          : "内容已准备好。先从左侧选中当前视频，再开始录入和复习。"

    workbenchGuideNotice = (
      <ContentNotice
        title={selectContentTitle}
        message={selectContentMessage}
        tone="info"
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => scrollToWorkbenchSection("workbench-content-tree")}>
              去左侧选内容
            </Button>
          </div>
        }
      />
    )
  }

  let sidebarPrimaryAction: ReactNode = null

  if (queueHasGate) {
    sidebarPrimaryAction = (
      <section className="theme-status-surface p-4">
        <SidebarSectionTitle title="当前主动作" note="先把系统已经排出的复习做完，再继续录入新的复述点。" />
        <div className="mt-3 text-[17px] font-semibold tracking-[-0.02em] text-[color:var(--theme-soft-text-strong)]">先完成复习任务</div>
        <p className="mt-2 text-[13px] leading-6 text-muted-foreground">当前还有 {queueLength} 个待复习任务。先回忆、再看答案、再判断会不会，系统节奏会更稳。</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            size="sm"
            onClick={() => {
              setCenterPanelMode("main")
              scrollToWorkbenchSection("workbench-review-pane")
            }}
          >
            去复习区
          </Button>
        </div>
      </section>
    )
  } else if (actionableMissingGate) {
    sidebarPrimaryAction = (
      <section className="theme-status-surface p-4">
        <SidebarSectionTitle title="当前主动作" note="先排除阻塞项，再继续推进学习和层级任务。" />
        <div className="mt-3 text-[17px] font-semibold tracking-[-0.02em] text-[color:var(--theme-soft-text-strong)]">先修复缺失实例</div>
        <p className="mt-2 text-[13px] leading-6 text-muted-foreground">还有 {actionableMissingInstanceCount} 个缺失实例会挡住继续学习，先去项目设置修复，修复后再回来继续。</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button size="sm" onClick={() => navigate(`/p/${pid}/settings`)}>
            去项目设置
          </Button>
        </div>
      </section>
    )
  } else if (requiresLearningObjectTree && !instancesQ.isLoading && (instancesQ.data?.length ?? 0) === 0) {
    sidebarPrimaryAction = (
      <section className="theme-status-surface p-4">
        <SidebarSectionTitle title="当前主动作" note="先把工作台真正需要的内容准备好。" />
        <div className="mt-3 text-[17px] font-semibold tracking-[-0.02em] text-[color:var(--theme-soft-text-strong)]">
          {projectType === "BOOK" ? "先初始化书本目录" : projectType === "MISTAKE_BOOK" ? "先准备错题入口" : courseContentPrepTitle}
        </div>
        <p className="mt-2 text-[13px] leading-6 text-muted-foreground">
          {projectType === "BOOK"
            ? "还没有可用章节。先初始化目录结构，再回工作台选章节开始学习。"
            : projectType === "MISTAKE_BOOK"
              ? "还没有可用错题条目。先准备错题入口，再回工作台选条目开始整理。"
              : courseContentPrepMessage}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button size="sm" onClick={() => navigate(`/p/${pid}/settings`)}>
            去项目设置
          </Button>
        </div>
      </section>
    )
  } else if (requiresLearningObjectTree && !selectedInstanceId) {
    sidebarPrimaryAction = (
      <section className="theme-status-surface p-4">
        <SidebarSectionTitle title="当前主动作" note="工作台已经准备好了，接下来只差选中你正在处理的内容。" />
        <div className="mt-3 text-[17px] font-semibold tracking-[-0.02em] text-[color:var(--theme-soft-text-strong)]">
          {projectType === "BOOK" ? "先选一个章节开始学习" : projectType === "MISTAKE_BOOK" ? "先选一个错题条目开始整理" : "先选一个视频开始学习"}
        </div>
        <p className="mt-2 text-[13px] leading-6 text-muted-foreground">
          {projectType === "BOOK"
            ? "内容已准备好。先选中章节、小节或条目，再开始录入和回看。"
            : projectType === "MISTAKE_BOOK"
              ? "内容已准备好。先选中当前要整理的条目，再继续录入和整理。"
              : "内容已准备好。先选中当前视频，再开始录入和复习。"}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={() => scrollToWorkbenchSection("workbench-content-tree")}>
            去左侧选内容
          </Button>
        </div>
      </section>
    )
  } else if (centerPanelMode === "rollup") {
    sidebarPrimaryAction = (
      <section className="theme-status-surface p-4">
        <SidebarSectionTitle title="当前主动作" note="你现在在看层推进和学习任务结构。" />
        <div className="mt-3 text-[17px] font-semibold tracking-[-0.02em] text-[color:var(--theme-soft-text-strong)]">继续判断是否要推进层级</div>
        <p className="mt-2 text-[13px] leading-6 text-muted-foreground">如果现在想回到学习主流程，可以直接切回录入区；如果要检查层状态，就继续看当前面板。</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={() => scrollToWorkbenchSection("workbench-rollup-pane")}>
            看层推进
          </Button>
          <Button
            size="sm"
            onClick={() => {
              setCenterPanelMode("main")
              scrollToWorkbenchSection(queueHasGate ? "workbench-review-pane" : "workbench-compose-pane")
            }}
          >
            回主流程
          </Button>
        </div>
      </section>
    )
  } else if (selectedInstanceId && instance) {
    sidebarPrimaryAction = (
      <section className="theme-status-surface p-4">
        <SidebarSectionTitle title="当前主动作" note="内容已经选定，可以直接继续学习动作。" />
        <div className="mt-3 text-[17px] font-semibold tracking-[-0.02em] text-[color:var(--theme-soft-text-strong)]">继续处理当前内容</div>
        <p className="mt-2 text-[13px] leading-6 text-muted-foreground">
          当前正在处理“{instance.materialDisplayName}”。可以继续看视频定位，或直接回到复述点录入区完成这一轮学习。
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {usesResolvableCourseAnchor ? (
            <Button size="sm" variant="outline" onClick={() => scrollToWorkbenchSection("workbench-video-pane")}>
              去视频区
            </Button>
          ) : null}
          <Button size="sm" onClick={() => scrollToWorkbenchSection("workbench-compose-pane")}>
            去录入区
          </Button>
        </div>
      </section>
    )
  } else {
    sidebarPrimaryAction = (
      <section className="theme-status-surface p-4">
        <SidebarSectionTitle title="当前主动作" note="当前项目不依赖左侧内容树，可以直接开始录入。" />
        <div className="mt-3 text-[17px] font-semibold tracking-[-0.02em] text-[color:var(--theme-soft-text-strong)]">直接开始录入复述点</div>
        <p className="mt-2 text-[13px] leading-6 text-muted-foreground">先写下问题和答案，再提交学习，系统就会开始积累你的节奏和后续复习依据。</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button size="sm" onClick={() => scrollToWorkbenchSection("workbench-compose-pane")}>
            去录入区
          </Button>
        </div>
      </section>
    )
  }

  return (
    <div className="space-y-5">
      {workbenchGuideNotice}
      <div
        className={cn(
          "grid gap-5 xl:items-start",
          requiresLearningObjectTree ? "xl:grid-cols-[300px_minmax(0,1.2fr)_320px]" : "xl:grid-cols-[minmax(0,1.2fr)_320px]",
        )}
      >
        {requiresLearningObjectTree ? (
          <aside className="xl:sticky xl:top-28 xl:self-start">
            <Card
              id="workbench-content-tree"
              className="theme-card-main xl:flex xl:max-h-[calc(100dvh-9rem)] xl:min-h-0 xl:flex-col xl:overflow-hidden"
            >
              <CardHeader className="theme-card-header">
                <div className="flex items-center gap-3">
                  <div className="theme-icon-surface h-10 w-10">
                    <FolderTree className="h-5 w-5" />
                  </div>
                  <div>
                    <CardTitle>内容目录</CardTitle>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-2 xl:min-h-0 xl:flex-1 xl:overflow-y-auto xl:overscroll-contain xl:pr-3">
                <LearningObjectTree
                  projectId={pid}
                  projectType={projectType}
                  selectedInstanceId={selectedInstanceId}
                  onSelectInstance={(instanceId) => {
                    setSelectedInstanceId(pid, instanceId)
                    setSeekTo(null)
                    setCurrentMs(0)
                  }}
                />
              </CardContent>
            </Card>
          </aside>
        ) : null}

        <section className="space-y-4 xl:min-w-0">
          <div ref={videoPaneRef} id="workbench-video-pane" className="shrink-0 scroll-mt-28">
            {usesResolvableCourseAnchor ? (
              <VideoPane
                key={instance?.instanceId ?? "none"}
                projectId={pid}
                instance={instance}
                setCurrentMs={setCurrentMs}
                seekTo={seekTo}
                onSeekApplied={(nonce) => setSeekTo((s) => (s && s.nonce === nonce ? null : s))}
                onDurationResolved={(instanceId, durationMs) =>
                  setVideoDurationByInstanceId((current) =>
                    current[instanceId] === durationMs ? current : { ...current, [instanceId]: durationMs },
                  )
                }
                queueHasGate={queueHasGate}
              />
            ) : (
              <StudyModePane projectType={projectType} instance={instance} />
            )}
          </div>
          <div className="theme-subtle-surface shrink-0 p-1">
            <div className="grid grid-cols-2 gap-1">
              <button
                type="button"
                className={cn(
                  "rounded-[1rem] border px-4 py-2.5 text-sm font-medium transition-colors",
                  centerPanelMode === "main"
                    ? "border-primary/20 bg-[var(--theme-card-main-bg)] text-primary shadow-[0_10px_22px_-20px_hsl(var(--primary)/0.28)]"
                    : "border-transparent bg-transparent text-[color:var(--theme-subtle-text)] hover:[border-color:var(--theme-soft-border)] hover:[background:var(--theme-soft-bg)]",
                )}
                onClick={() => setCenterPanelMode("main")}
              >
                {queueQ.data?.headId ? "复习任务" : "复述点录入"}
              </button>
              <button
                type="button"
                className={cn(
                  "rounded-[1rem] border px-4 py-2.5 text-sm font-medium transition-colors",
                  centerPanelMode === "rollup"
                    ? "border-primary/20 bg-[var(--theme-card-main-bg)] text-primary shadow-[0_10px_22px_-20px_hsl(var(--primary)/0.28)]"
                    : "border-transparent bg-transparent text-[color:var(--theme-subtle-text)] hover:[border-color:var(--theme-soft-border)] hover:[background:var(--theme-soft-bg)]",
                )}
                onClick={() => setCenterPanelMode("rollup")}
              >
                层推进与学习任务
              </button>
            </div>
          </div>

          {centerPanelMode === "main" ? (
            <div id={queueQ.data?.headId ? "workbench-review-pane" : "workbench-compose-pane"} className="shrink-0">
              {queueQ.data?.headId ? (
                <ReviewPane
                  key={queueQ.data.headId}
                  projectId={pid}
                  headId={queueQ.data.headId}
                  instances={instancesQ.data ?? []}
                  onOpenAnchor={onOpenAnchor}
                />
              ) : (
                <ComposePane
                  projectId={pid}
                  projectType={projectType}
                  selectedInstanceId={selectedInstanceId}
                  instance={instance}
                  currentMs={currentMs}
                  queueHasGate={queueHasGate}
                  actionableMissingGate={actionableMissingGate}
                  actionableMissingInstanceCount={actionableMissingInstanceCount}
                />
              )}
            </div>
          ) : (
            <RollupPane
              projectId={pid}
              layers={layersQ.data ?? []}
              layersLoading={layersQ.isLoading}
              layersError={layersQ.error}
              learningTaskNodesById={learningTaskNodesById}
              learningTaskNodesLoading={learningTaskNodesQ.isLoading}
              queueHasGate={queueHasGate}
              actionableMissingGate={actionableMissingGate}
              actionableMissingInstanceCount={actionableMissingInstanceCount}
              isRollingUp={rollUpM.isPending}
              isThresholdRollUpUpdating={setLayerConfigM.isPending}
              rollUpStrategy={currentRollUpStrategy}
              onRollUp={(layerIndex) => void onManualRollUp(layerIndex)}
              onToggleThresholdRollUp={(layerIndex, enabled) => void onToggleThresholdRollUp(layerIndex, enabled)}
              rollUpError={rollUpM.error}
              thresholdRollUpEnabledByLayerIndex={thresholdRollUpEnabledByLayerIndex}
            />
          )}
        </section>

        <aside className="xl:sticky xl:top-28 xl:self-start">
            <Card className="theme-card-main xl:flex xl:max-h-[calc(100dvh-9rem)] xl:min-h-0 xl:flex-col xl:overflow-hidden">
            <CardHeader className="theme-card-header">
              <div className="flex items-center gap-3">
                <div className="theme-icon-surface h-10 w-10">
                  <RadioTower className="h-5 w-5" />
                </div>
                <div>
                  <CardTitle>工作状态</CardTitle>
                  <div className="mt-1 text-[15px] font-medium text-[color:var(--theme-soft-text-strong)]">{workStatusDetail}</div>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-5 pt-4 text-sm xl:min-h-0 xl:flex-1 xl:overflow-y-auto xl:overscroll-contain xl:pr-3">
              {sidebarPrimaryAction}

              <section className="space-y-3">
                <SidebarSectionTitle title="推进判断" note="先看剩余量、计划节奏和覆盖情况，再决定今天往哪推进。" />

                {studyEstimatePresentation ? (
                  <section className="rounded-[1.15rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-3.5">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-[12px] font-medium text-muted-foreground">预计剩余学习时长</div>
                        <div className="mt-1 text-[17px] font-semibold tracking-[-0.02em] text-[color:var(--theme-soft-text-strong)]">
                          {studyEstimatePresentation.value}
                        </div>
                      </div>
                    </div>
                    <p className="mt-2 text-[12px] leading-6 text-muted-foreground">{studyEstimatePresentation.detail}</p>
                  </section>
                ) : null}

                <LearningPlanCard
                  projectId={pid}
                  todayDateKey={todayDateKey}
                  plan={activeLearningPlan}
                  evaluation={learningPlanEvaluation}
                  nodes={(learningObjectNodesQ.data ?? []) as LearningObjectNode[]}
                  onArchive={archiveLearningPlan}
                  onSave={upsertLearningPlan}
                />

                {usesResolvableCourseAnchor ? (
                  <section className="rounded-[1.15rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-3.5">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-[12px] font-medium text-muted-foreground">观看覆盖</div>
                        <div className="mt-1 text-[17px] font-semibold tracking-[-0.02em] text-[color:var(--theme-soft-text-strong)]">
                          {formatDurationCompact(videoProgress.watchedMs)} / {formatDurationCompact(videoProgress.totalMs)}
                        </div>
                      </div>
                      <div className="text-[13px] font-semibold text-[color:var(--theme-soft-text-strong)]">{Math.round(videoProgressPercent)}%</div>
                    </div>
                    <div className="theme-progress-track mt-3 h-2 overflow-hidden rounded-full">
                      <div
                        className="theme-progress-fill h-full rounded-full transition-[width] duration-500"
                        style={{ width: `${videoProgressPercent}%` }}
                      />
                    </div>
                    <div className="mt-2 text-[12px] text-muted-foreground">
                      {remainingDurationProbeCount > 0 ? `正在统计 ${remainingDurationProbeCount} 个视频时长` : "按当前设备实际观看过的片段估算"}
                    </div>
                  </section>
                ) : null}
              </section>

              <section className="space-y-3">
                <SidebarSectionTitle title="当前上下文" note="需要切换材料、确认所在位置时，再看这里。" />
                {subjectContextQ.isLoading ? (
                  <div className="rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-3 text-[12px] text-muted-foreground">
                    正在同步当前学科和材料位置...
                  </div>
                ) : null}
                {subjectContextQ.data ? (
                  <SubjectContextCard
                    context={subjectContextQ.data}
                    onOpenMaterial={(projectId, target) => navigate(target === "settings" ? `/p/${projectId}/settings` : `/p/${projectId}/workbench`)}
                  />
                ) : null}
                {subjectContextQ.error ? <p className="text-sm text-destructive">{formatApiError(subjectContextQ.error)}</p> : null}
              </section>

              <section className="theme-subtle-surface overflow-hidden">
                <button
                  type="button"
                  className="flex w-full items-start justify-between gap-4 px-4 py-3 text-left"
                  onClick={() => setSidebarStatsExpanded((current) => !current)}
                >
                  <div>
                    <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">今日回看</div>
                    <div className="mt-1 text-[15px] font-semibold text-[color:var(--theme-soft-text-strong)]">
                      有效学习 {formatDurationCompact(todayStats.effectiveMs)}
                    </div>
                    <div className="mt-1 text-[12px] text-muted-foreground">
                      {todayStudyPresenceMs > 0 ? `专注率 ${formatPercent(focusRatio)} · 复习 ${formatDurationCompact(todayStats.reviewMs)}` : "展开后查看今天的完整统计"}
                    </div>
                  </div>
                  <span className="text-xs font-medium text-primary">{sidebarStatsExpanded ? "收起" : "展开"}</span>
                </button>
                {sidebarStatsExpanded ? (
                  <div className="border-t border-border/60 px-4 pb-3">
                    <div className="divide-y divide-border/60">
                      <StatusMetricRow label="有效学习时长" value={formatDurationCompact(todayStats.effectiveMs)} emphasize />
                      <StatusMetricRow label="学习驻留" value={formatDurationCompact(todayStudyPresenceMs)} />
                      <StatusMetricRow label="走神时长" value={formatDurationCompact(blankPresenceMs)} />
                      <StatusMetricRow label="客观专注率" value={todayStudyPresenceMs > 0 ? formatPercent(focusRatio) : "继续学习后生成"} emphasize={todayStudyPresenceMs > 0} />
                      <StatusMetricRow label="材料接触" value={formatDurationCompact(todayStats.watchMs)} />
                      <StatusMetricRow label="复述点构建" value={formatDurationCompact(todayStats.composeMs)} />
                      <StatusMetricRow label="复习时长" value={formatDurationCompact(todayStats.reviewMs)} />
                      <StatusMetricRow label="AI 问答" value={formatDurationCompact(todayStats.qaMs)} />
                      <StatusMetricRow
                        label="录入复述点数"
                        value={auditLogQ.isLoading ? "..." : `${todayAuditStats.submittedRecallPoints}`}
                      />
                      <StatusMetricRow
                        label="复习复述点数"
                        value={auditLogQ.isLoading ? "..." : `${todayAuditStats.reviewedRecallPoints}`}
                      />
                    </div>
                  </div>
                ) : null}
              </section>
              {queueQ.error ? <p className="text-sm text-destructive">{formatApiError(queueQ.error)}</p> : null}
              {auditLogQ.error ? <p className="text-sm text-destructive">{formatApiError(auditLogQ.error)}</p> : null}
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  )
}

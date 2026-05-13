import { useEffect, useMemo, useRef, useState, type ReactNode } from "react"
import { useQueries } from "@tanstack/react-query"
import { FolderTree, RadioTower } from "lucide-react"
import { useNavigate, useParams, useSearchParams } from "react-router-dom"

import { apiUrl } from "@/ui/api/http"
import { ApiError } from "@/ui/api/http"
import { fetchVideoWatchProgressMap, listRecallPointsByInstance, type VideoWatchProgress } from "@/ui/api/instances"
import type { Instance } from "@/ui/api/instances"
import { getInstancePlaybackDescriptor } from "@/ui/api/media"
import { projectApiPath, type ScopedProjectRef } from "@/ui/api/projectScope"
import type { LearningTaskNode } from "@/ui/api/learningTaskNodes"
import type { ProjectType } from "@/ui/api/projects"
import { ContentNotice } from "@/ui/components/contentEmptyState"
import { DesktopPet } from "@/ui/components/DesktopPet"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { isVirtualStudyReviewProjectId } from "@/ui/guideWalkthrough/guideVirtualProjectIds"
import { projectTypeRequiresLearningObjectTree, projectTypeUsesResolvableCourseAnchor } from "@/ui/projectTypes"
import { buildProjectSettingsPath } from "@/ui/projectPaths"
import { resolveProjectFile, useProjectDirectoryBinding } from "@/ui/localMedia/projectDirectory"
import { useLearningTaskNodes } from "@/ui/queries/learningTasks"
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
import { getLocalDateKey, listDailyStudyMetricEntries, loadDailyWorkbenchStats, type DailyWorkbenchStats } from "@/ui/store/workbenchDailyStats"
import { showErrorFeedback, showInfoFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { syncStudyMetricsSnapshot } from "@/ui/studyMetricsSync"
import { createStudyPresenceTracker } from "@/ui/store/studyPresenceStore"
import { loadVideoDurationMap, saveVideoDurationMs } from "@/ui/store/videoDurations"
import { loadVideoWatchProgressMap } from "@/ui/store/videoWatchProgress"
import { useWorkbenchStore } from "@/ui/store/workbenchStore"
import { cn } from "@/ui/utils"
import { ComposePane } from "@/views/workbench/components/ComposePane"
import { LearningObjectTree } from "@/views/workbench/components/LearningObjectTree"
import { ReviewPane } from "@/views/workbench/components/ReviewPane"
import { RollupPane } from "@/views/workbench/components/RollupPane"
import { VideoPane } from "@/views/workbench/components/VideoPane"
import { WorkbenchPetAssistant } from "@/views/workbench/components/WorkbenchPetAssistant"
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

function getDateKeyDaysAgo(days: number, from = new Date()) {
  const next = new Date(from)
  next.setDate(next.getDate() - Math.max(0, Math.floor(days)))
  return getLocalDateKey(next)
}

function shallowRecordEqual<T>(left: Record<string, T>, right: Record<string, T>) {
  const leftKeys = Object.keys(left)
  const rightKeys = Object.keys(right)
  if (leftKeys.length !== rightKeys.length) return false
  return leftKeys.every((key) => left[key] === right[key])
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
  subjectId: string
  projectId: string
  instance: Instance
  serverMediaStreamEnabled: boolean
  browserLocalMediaEnabled: boolean
  directoryPermission: "unsupported" | "missing" | "prompt" | "granted" | "denied"
}) {
  const { subjectId, projectId, instance, serverMediaStreamEnabled, browserLocalMediaEnabled, directoryPermission } = params
  const scope = { subjectId, scopedProjectId: projectId }
  if (typeof instance.durationMs === "number" && instance.durationMs > 0) {
    return instance.durationMs
  }
  if (instance.playbackKind === "HLS" || instance.mediaSourceKind === "BAIDU_NETDISK") {
    const playback = await getInstancePlaybackDescriptor(scope, instance.instanceId, { timeoutMs: 90_000 })
    if (typeof playback.durationMs === "number" && playback.durationMs > 0) {
      return playback.durationMs
    }
    return null
  }
  if (serverMediaStreamEnabled) {
    return await readMediaDurationMs(apiUrl(projectApiPath(scope, `/media/instances/${instance.instanceId}`)))
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

type TodayReviewSlice = {
  label: string
  value: number
  color: string
}

function TodayReviewStatsChart(props: { stats: DailyWorkbenchStats }) {
  const { stats } = props
  const slices: TodayReviewSlice[] = [
    { label: "视频观看", value: stats.videoMs, color: "#2563eb" },
    { label: "复述点录入", value: stats.recallEntryMs, color: "#16a34a" },
    { label: "复习用时", value: stats.reviewMs, color: "#d97706" },
    { label: "AI 问答", value: stats.aiQaMs, color: "#7c3aed" },
    { label: "走神时间", value: stats.distractionMs, color: "#64748b" },
  ].filter((slice) => slice.value > 0)
  const total = slices.reduce((sum, slice) => sum + slice.value, 0)
  let cursor = 0
  const gradient =
    total <= 0
      ? "conic-gradient(hsl(var(--muted)) 0deg 360deg)"
      : `conic-gradient(${slices
          .map((slice) => {
            const start = (cursor / total) * 360
            cursor += slice.value
            const end = (cursor / total) * 360
            return `${slice.color} ${start}deg ${end}deg`
          })
          .join(", ")})`

  return (
    <div className="mt-3 border-t border-border/60 pt-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <div className="text-[12px] font-medium text-muted-foreground">网页驻留</div>
          <div className="mt-1 text-[17px] font-semibold tracking-[-0.02em] text-[color:var(--theme-soft-text-strong)]">
            {formatDurationCompact(stats.webPresenceMs)}
          </div>
        </div>
        <div
          aria-label="今日回看统计图"
          role="img"
          className="relative h-24 w-24 shrink-0 rounded-full"
          style={{ background: gradient }}
        />
      </div>
      <div className="mt-4 grid gap-2 text-xs text-muted-foreground">
        {slices.length === 0 ? (
          <div>暂无学习分解</div>
        ) : (
          slices.map((slice) => (
            <div key={slice.label} className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: slice.color }} />
                {slice.label}
              </span>
              <span>{formatDurationCompact(slice.value)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function SidebarSectionTitle(props: { title: string }) {
  const { title } = props
  return (
    <div className="flex items-start justify-between gap-3">
      <div>
        <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">{title}</div>
      </div>
    </div>
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
        <CardTitle>{projectType === "BOOK" ? "书本定位" : "零散知识点模式"}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 pt-5">
        <div className="rounded-[1.15rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] px-4 py-4 text-sm leading-6 text-[color:var(--theme-soft-text-strong)]">
          {projectType === "BOOK"
            ? instance
              ? `当前正在“${instance.materialDisplayName}”下录入复述点。请为每条复述点填写页码、章节、小节、题号或段落说明等文本锚点。`
              : "请先从左侧目录中选择一个章节、小节或条目，再开始录入书本复述点。"
            : "当前项目按零散知识点模式运行。你可以直接录入复述点，不需要选择学习对象，也不需要绑定锚点。"}
        </div>
      </CardContent>
    </Card>
  )
}

export function WorkbenchPage() {
  const { scopedProjectId: projectId, subjectId = "" } = useParams()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const pid = projectId ?? ""
  const projectScope: ScopedProjectRef | null = subjectId && pid ? { subjectId, scopedProjectId: pid } : null
  const isVirtualStudyReviewProject = isVirtualStudyReviewProjectId(pid)

  const ensure = useWorkbenchStore((s) => s.ensure)
  const ps = useWorkbenchStore((s) => (pid ? s.byProjectId[pid] : undefined))
  const setSelectedInstanceId = useWorkbenchStore((s) => s.setSelectedInstanceId)

  const selectedWorkbenchProjectId = useAppStore((s) => s.selectedWorkbenchProjectId)
  const selectedWorkbenchProjectRef = useAppStore((s) => s.selectedWorkbenchProjectRef)

  const [currentMs, setCurrentMs] = useState(0)
  const [seekTo, setSeekTo] = useState<{ instanceId: string; ms: number; nonce: number } | null>(null)
  const [centerPanelMode, setCenterPanelMode] = useState<"main" | "rollup">("main")
  const [petAssistantState, setPetAssistantState] = useState<"idle" | "thinking">("idle")
  const videoPaneRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!pid) return
    ensure(pid)
  }, [ensure, pid])

  useEffect(() => {
    if (subjectId && pid && (selectedWorkbenchProjectRef?.subjectId !== subjectId || selectedWorkbenchProjectRef?.scopedProjectId !== pid)) {
      useAppStore.getState().setSelectedWorkbenchProjectRef({ subjectId, scopedProjectId: pid })
      return
    }
    if (pid && selectedWorkbenchProjectId !== pid) {
      useAppStore.getState().setSelectedWorkbenchProjectId(pid)
    }
  }, [pid, selectedWorkbenchProjectId, selectedWorkbenchProjectRef?.scopedProjectId, selectedWorkbenchProjectRef?.subjectId, subjectId])

  const instancesQ = useInstances(projectScope)
  const learningTaskNodesQ = useLearningTaskNodes(projectScope)
  const queueQ = useQueue(projectScope)
  const layersQ = useLayers(projectScope)
  const rollUpM = useManualRollUp(projectScope)
  const projectConfigQ = useProjectConfig(projectScope)
  const setLayerConfigM = useSetLayerConfig(projectScope)
  const capabilitiesQ = useSystemCapabilities()
  const directoryBinding = useProjectDirectoryBinding(pid)
  const projectType = projectConfigQ.data?.projectType ?? "COURSE"
  const projectSettingsPath = buildProjectSettingsPath(subjectId, pid)
  const currentRollUpStrategy = projectConfigQ.data?.rollUpStrategy ?? "LEARNING_OBJECT_ISOMORPHIC"
  const requiresLearningObjectTree = projectTypeRequiresLearningObjectTree(projectType)
  const usesResolvableCourseAnchor = projectTypeUsesResolvableCourseAnchor(projectType)
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
      queryFn: () => listRecallPointsByInstance(projectScope as ScopedProjectRef, item.instanceId),
      enabled: !!projectScope && !isVirtualStudyReviewProject,
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
  const [studyEstimateRevision, setStudyEstimateRevision] = useState(0)
  const [videoDurationByInstanceId, setVideoDurationByInstanceId] = useState<Record<string, number>>({})
  const [videoWatchedMsByInstanceId, setVideoWatchedMsByInstanceId] = useState<Record<string, number>>({})
  const [remoteVideoWatchProgressByInstanceId, setRemoteVideoWatchProgressByInstanceId] = useState<Record<string, VideoWatchProgress>>({})
  const [durationProbeAttemptedByInstanceId, setDurationProbeAttemptedByInstanceId] = useState<Record<string, true>>({})
  const [durationProbeInFlightByInstanceId, setDurationProbeInFlightByInstanceId] = useState<Record<string, true>>({})
  const [recallPointCountByInstanceId, setRecallPointCountByInstanceId] = useState<Record<string, number>>({})
  const [recallPointProbeStatusByInstanceId, setRecallPointProbeStatusByInstanceId] = useState<Record<string, "ready" | "empty" | "failed">>({})
  const [recallPointProbeInFlightByInstanceId, setRecallPointProbeInFlightByInstanceId] = useState<Record<string, true>>({})
  const durationProbeSessionRef = useRef(0)
  const recallPointProbeSessionRef = useRef(0)

  useEffect(() => {
    if (!projectScope) return
    setTodayStats(loadDailyWorkbenchStats(pid))
    const timer = window.setInterval(() => {
      setTodayStats(loadDailyWorkbenchStats(pid))
    }, 1000)
    return () => window.clearInterval(timer)
  }, [pid])

  useEffect(() => {
    const scope = projectScope
    if (!pid || !scope) return
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
      setTodayStats(loadDailyWorkbenchStats(pid))
    }
  }, [pid])

  const todayDateKey = getLocalDateKey()
  const estimateDateFrom = useMemo(() => {
    void todayDateKey
    return getDateKeyDaysAgo(180)
  }, [todayDateKey])

  useEffect(() => {
    if (!pid || isVirtualStudyReviewProject) return
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
  }, [capabilitiesQ.data?.authEnabled, isVirtualStudyReviewProject, pid, todayDateKey])

  useEffect(() => {
    if (!pid || isVirtualStudyReviewProject) return
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
  }, [capabilitiesQ.data?.authEnabled, estimateDateFrom, isVirtualStudyReviewProject, pid, todayDateKey])

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
      setVideoDurationByInstanceId((current) => (Object.keys(current).length === 0 ? current : {}))
      setVideoWatchedMsByInstanceId((current) => (Object.keys(current).length === 0 ? current : {}))
      setRemoteVideoWatchProgressByInstanceId((current) => (Object.keys(current).length === 0 ? current : {}))
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
    setVideoDurationByInstanceId((current) =>
      shallowRecordEqual(current, nextDurationByInstanceId) ? current : nextDurationByInstanceId,
    )
    const nextWatchedMsByInstanceId = loadVideoWatchProgressMap(pid, instanceIds, nextDurationByInstanceId, remoteVideoWatchProgressByInstanceId)
    setVideoWatchedMsByInstanceId((current) =>
      shallowRecordEqual(current, nextWatchedMsByInstanceId) ? current : nextWatchedMsByInstanceId,
    )
  }, [instancesQ.data, pid, remoteVideoWatchProgressByInstanceId])

  useEffect(() => {
    if (!pid) return
    const instanceIds = (instancesQ.data ?? []).map((item) => item.instanceId)

    const refreshWatchCoverage = () => {
      const nextWatchedMsByInstanceId = loadVideoWatchProgressMap(pid, instanceIds, videoDurationByInstanceId, remoteVideoWatchProgressByInstanceId)
      setVideoWatchedMsByInstanceId((current) =>
        shallowRecordEqual(current, nextWatchedMsByInstanceId) ? current : nextWatchedMsByInstanceId,
      )
    }

    refreshWatchCoverage()
    const timer = window.setInterval(refreshWatchCoverage, 1000)
    return () => window.clearInterval(timer)
  }, [instancesQ.data, pid, remoteVideoWatchProgressByInstanceId, videoDurationByInstanceId])

  useEffect(() => {
    const scope = projectScope
    if (!pid || !scope) return
    const instanceIds = (instancesQ.data ?? []).map((item) => item.instanceId)
    if (instanceIds.length <= 0) {
      setRemoteVideoWatchProgressByInstanceId((current) => (Object.keys(current).length === 0 ? current : {}))
      return
    }
    const controller = new AbortController()
    void (async () => {
      try {
        const remoteProgress = await fetchVideoWatchProgressMap(scope, instanceIds, {
          signal: controller.signal,
          timeoutMs: 90_000,
        })
        if (controller.signal.aborted) return
        setRemoteVideoWatchProgressByInstanceId((current) =>
          shallowRecordEqual(current, remoteProgress) ? current : remoteProgress,
        )
        const nextWatchedMsByInstanceId = loadVideoWatchProgressMap(pid, instanceIds, videoDurationByInstanceId, remoteProgress)
        setVideoWatchedMsByInstanceId((current) =>
          shallowRecordEqual(current, nextWatchedMsByInstanceId) ? current : nextWatchedMsByInstanceId,
        )
      } catch {
        // Keep local watch coverage usable when remote progress sync is unavailable.
      }
    })()
    return () => controller.abort()
  }, [instancesQ.data, pid, projectScope, videoDurationByInstanceId])

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
            subjectId,
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
  }, [browserLocalMediaEnabled, directoryBinding.permission, pendingDurationProbeInstances, pid, serverMediaStreamEnabled, subjectId])

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
          const result = await listRecallPointsByInstance(projectScope as ScopedProjectRef, targetInstance.instanceId, { timeoutMs: 90_000 })
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
  }, [pendingRecallPointProbeInstances, pid, projectScope])

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
  const projectStudyMetricEntries = useMemo(
    () => {
      void studyEstimateRevision
      void todayStats
      return listDailyStudyMetricEntries([pid])
    },
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
  const studyEstimatePresentation = useMemo(() => {
    if (!usesResolvableCourseAnchor) return null

    if (!studyEstimate) {
      return {
        value: "等待统计",
      }
    }

    if (studyEstimate.status === "insufficient_data") {
      return {
        value: "继续学习后生成",
      }
    }

    const completionPercent = Math.round(studyEstimate.completionRatio * 100)
    const value = studyEstimate.remainingMs <= 60_000 && completionPercent >= 95 ? "接近完成" : formatDurationCompact(studyEstimate.remainingMs)
    return {
      value,
    }
  }, [studyEstimate, usesResolvableCourseAnchor])
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
          : "等待开始"

  if (!pid) {
    return (
      <div className="space-y-4">
        <ContentNotice
          title="当前工作台缺少项目上下文"
          message="当前链接缺少项目信息。请先返回项目列表，再重新进入工作台。"
          action={<Button onClick={() => navigate("/subjects")}>返回学科中心</Button>}
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

  if (actionableMissingGate) {
    workbenchGuideNotice = (
      <ContentNotice
        title="先修复缺失实例"
        message={`还有 ${actionableMissingInstanceCount} 个缺失实例会挡住继续学习。先去项目设置修复，修复后再回来继续。`}
        tone="info"
        action={
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => navigate(projectSettingsPath)}>去项目设置</Button>
          </div>
        }
      />
    )
  } else if (requiresLearningObjectTree && !instancesQ.isLoading && (instancesQ.data?.length ?? 0) === 0) {
    const noContentTitle = projectType === "BOOK" ? "先初始化书本目录" : courseContentPrepTitle
    const noContentMessage =
      projectType === "BOOK"
        ? "还没有可用章节。先去项目设置初始化目录结构，完成后回工作台选章节开始学习。"
        : courseContentPrepMessage

    workbenchGuideNotice = (
      <ContentNotice
        title={noContentTitle}
        message={noContentMessage}
        tone="info"
        action={
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => navigate(projectSettingsPath)}>去项目设置</Button>
          </div>
        }
      />
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
                  subjectId={subjectId}
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
                subjectId={subjectId}
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
                  subjectId={subjectId}
                  key={queueQ.data.headId}
                  projectId={pid}
                  headId={queueQ.data.headId}
                  instances={instancesQ.data ?? []}
                  onOpenAnchor={onOpenAnchor}
                />
              ) : (
                <ComposePane
                  subjectId={subjectId}
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
              subjectId={subjectId}
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

        <aside className="xl:sticky xl:top-28 xl:z-30 xl:self-start">
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
              <section className="space-y-3">
                <SidebarSectionTitle title="推进判断" />

                {studyEstimatePresentation ? (
                  <section>
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="text-[12px] font-medium text-muted-foreground">预计剩余学习时长</div>
                        <div className="mt-1 text-[17px] font-semibold tracking-[-0.02em] text-[color:var(--theme-soft-text-strong)]">
                          {studyEstimatePresentation.value}
                        </div>
                      </div>
                    </div>
                  </section>
                ) : null}

                {usesResolvableCourseAnchor ? (
                  <section>
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-[12px] font-medium text-muted-foreground">观看覆盖</div>
                        <div className="mt-1 text-[17px] font-semibold tracking-[-0.02em] text-[color:var(--theme-soft-text-strong)]">
                          {formatDurationCompact(videoProgress.watchedMs)} / {formatDurationCompact(videoProgress.totalMs)}
                        </div>
                      </div>
                      <div className="text-[13px] font-semibold text-[color:var(--theme-soft-text-strong)]">{Math.round(videoProgressPercent)}%</div>
                    </div>
                  </section>
                ) : null}
              </section>

              <section>
                <SidebarSectionTitle title="今日回看" />
                <TodayReviewStatsChart stats={todayStats} />
              </section>
              {queueQ.error ? <p className="text-sm text-destructive">{formatApiError(queueQ.error)}</p> : null}
            </CardContent>
          </Card>
          <DesktopPet page="workbench" assistantState={petAssistantState}>
            <WorkbenchPetAssistant
              subjectId={subjectId}
              projectId={pid}
              instance={instance}
              currentMs={currentMs}
              workStatusDetail={workStatusDetail}
              usesResolvableCourseAnchor={usesResolvableCourseAnchor}
              onAssistantStateChange={setPetAssistantState}
              onOpenEvidence={(evidence) => {
                onOpenAnchor({
                  instanceId: evidence.instanceId,
                  position: `t=${Math.max(0, Math.floor((evidence.startMs + evidence.endMs) / 2))}`,
                })
              }}
            />
          </DesktopPet>
        </aside>
      </div>
    </div>
  )
}

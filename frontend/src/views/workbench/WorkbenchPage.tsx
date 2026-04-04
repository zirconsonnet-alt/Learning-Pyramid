import { useEffect, useMemo, useRef, useState } from "react"
import { FolderTree, RadioTower } from "lucide-react"
import { useNavigate, useParams, useSearchParams } from "react-router-dom"

import { getBaseUrl } from "@/ui/api/http"
import { ApiError } from "@/ui/api/http"
import { listRecallPointsByInstance } from "@/ui/api/instances"
import type { Instance } from "@/ui/api/instances"
import { getInstancePlaybackDescriptor } from "@/ui/api/media"
import type { LearningTaskNode } from "@/ui/api/learningTaskNodes"
import type { ProjectType } from "@/ui/api/projects"
import { ContentNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { projectTypeRequiresLearningObjectTree, projectTypeUsesResolvableCourseAnchor } from "@/ui/projectTypes"
import { resolveProjectFile, useProjectDirectoryBinding } from "@/ui/localMedia/projectDirectory"
import { useAuditLogEvents } from "@/ui/queries/auditLog"
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
import { getLocalDateKey, loadDailyWorkbenchStats } from "@/ui/store/workbenchDailyStats"
import { showErrorFeedback, showInfoFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { loadVideoDurationMap, saveVideoDurationMs } from "@/ui/store/videoDurations"
import { useWorkbenchStore } from "@/ui/store/workbenchStore"
import { cn } from "@/ui/utils"
import { ComposePane } from "@/views/workbench/components/ComposePane"
import { LearningObjectTree } from "@/views/workbench/components/LearningObjectTree"
import { ReviewPane } from "@/views/workbench/components/ReviewPane"
import { RollupPane } from "@/views/workbench/components/RollupPane"
import { VideoPane } from "@/views/workbench/components/VideoPane"

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
const WATCHED_PROGRESS_PROBE_CONCURRENCY = 2

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
  const setLayerConfigM = useSetLayerConfig(pid)
  const capabilitiesQ = useSystemCapabilities()
  const directoryBinding = useProjectDirectoryBinding(pid)
  const projectType = projectConfigQ.data?.projectType ?? "COURSE"
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

  const learningTaskNodesById = useMemo(() => {
    const map: Record<string, LearningTaskNode> = {}
    for (const node of learningTaskNodesQ.data ?? []) map[node.nodeId] = node
    return map
  }, [learningTaskNodesQ.data])
  const [todayPlaybackMs, setTodayPlaybackMs] = useState(() => loadDailyWorkbenchStats(pid).playbackMs)
  const [videoDurationByInstanceId, setVideoDurationByInstanceId] = useState<Record<string, number>>({})
  const [durationProbeAttemptedByInstanceId, setDurationProbeAttemptedByInstanceId] = useState<Record<string, true>>({})
  const [durationProbeInFlightByInstanceId, setDurationProbeInFlightByInstanceId] = useState<Record<string, true>>({})
  const [watchedStatusByInstanceId, setWatchedStatusByInstanceId] = useState<Record<string, "watched" | "empty" | "failed">>({})
  const [watchedProbeInFlightByInstanceId, setWatchedProbeInFlightByInstanceId] = useState<Record<string, true>>({})
  const durationProbeSessionRef = useRef(0)
  const watchedProbeSessionRef = useRef(0)

  useEffect(() => {
    if (!pid) return
    setTodayPlaybackMs(loadDailyWorkbenchStats(pid).playbackMs)
    const timer = window.setInterval(() => {
      setTodayPlaybackMs(loadDailyWorkbenchStats(pid).playbackMs)
    }, 1000)
    return () => window.clearInterval(timer)
  }, [pid])

  const todayDateKey = getLocalDateKey()
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
      return
    }
    const instanceIds = (instancesQ.data ?? []).map((item) => item.instanceId)
    const stored = loadVideoDurationMap(pid, instanceIds)
    const fromInstances = Object.fromEntries(
      (instancesQ.data ?? [])
        .filter((item) => typeof item.durationMs === "number" && item.durationMs > 0)
        .map((item) => [item.instanceId, item.durationMs as number]),
    )
    setVideoDurationByInstanceId({ ...stored, ...fromInstances })
  }, [instancesQ.data, pid])

  useEffect(() => {
    setDurationProbeAttemptedByInstanceId({})
    setDurationProbeInFlightByInstanceId({})
    durationProbeSessionRef.current += 1
  }, [browserLocalMediaEnabled, directoryBinding.permission, pid, serverMediaStreamEnabled, usesResolvableCourseAnchor])

  useEffect(() => {
    setWatchedStatusByInstanceId({})
    setWatchedProbeInFlightByInstanceId({})
    watchedProbeSessionRef.current += 1
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

  const pendingWatchedProbeInstances = useMemo(() => {
    if (!usesResolvableCourseAnchor) return []
    const availableSlots = Math.max(0, WATCHED_PROGRESS_PROBE_CONCURRENCY - Object.keys(watchedProbeInFlightByInstanceId).length)
    if (availableSlots <= 0) return []
    const pending: Instance[] = []
    for (const item of instancesQ.data ?? []) {
      if (watchedStatusByInstanceId[item.instanceId]) continue
      if (watchedProbeInFlightByInstanceId[item.instanceId]) continue
      pending.push(item)
      if (pending.length >= availableSlots) break
    }
    return pending
  }, [instancesQ.data, usesResolvableCourseAnchor, watchedProbeInFlightByInstanceId, watchedStatusByInstanceId])

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
    if (!pid || pendingWatchedProbeInstances.length <= 0) return
    const probeSession = watchedProbeSessionRef.current
    const pendingInstanceIds = pendingWatchedProbeInstances.map((item) => item.instanceId)

    setWatchedProbeInFlightByInstanceId((current) => {
      let changed = false
      const next = { ...current }
      for (const instanceId of pendingInstanceIds) {
        if (next[instanceId]) continue
        next[instanceId] = true
        changed = true
      }
      return changed ? next : current
    })

    for (const targetInstance of pendingWatchedProbeInstances) {
      void (async () => {
        try {
          const result = await listRecallPointsByInstance(pid, targetInstance.instanceId, { timeoutMs: 90_000 })
          if (watchedProbeSessionRef.current !== probeSession) return
          setWatchedStatusByInstanceId((current) =>
            current[targetInstance.instanceId]
              ? current
              : {
                  ...current,
                  [targetInstance.instanceId]: result.recallPointIds.length > 0 ? "watched" : "empty",
                },
          )
        } catch {
          if (watchedProbeSessionRef.current !== probeSession) return
          // This metric is advisory only; mark failures so the page stays responsive.
          setWatchedStatusByInstanceId((current) =>
            current[targetInstance.instanceId] ? current : { ...current, [targetInstance.instanceId]: "failed" },
          )
        } finally {
          if (watchedProbeSessionRef.current === probeSession) {
            setWatchedProbeInFlightByInstanceId((current) => {
              if (!current[targetInstance.instanceId]) return current
              const next = { ...current }
              delete next[targetInstance.instanceId]
              return next
            })
          }
        }
      })()
    }
  }, [pendingWatchedProbeInstances, pid])

  const watchedInstanceIds = useMemo(() => {
    const out = new Set<string>()
    for (const [instanceId, status] of Object.entries(watchedStatusByInstanceId)) {
      if (status === "watched") {
        out.add(instanceId)
      }
    }
    return out
  }, [watchedStatusByInstanceId])

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
      if (watchedInstanceIds.has(item.instanceId)) {
        watchedMs += durationMs
      }
    }
    return { totalMs, watchedMs }
  }, [instancesQ.data, videoDurationByInstanceId, watchedInstanceIds])

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

  async function onManualRollUp(layerIndex: number) {
    if (queueHasGate) {
      showInfoFeedback("当前无法上推", "还有待完成的复习门禁，请先完成复习再继续层级推进。")
      return
    }
    try {
      const result = await rollUpM.mutateAsync({ layerIndex })
      if (result.parentNodeId) {
        showSuccessFeedback("层级上推已完成", `L${layerIndex} 已生成新的聚合节点。`)
      } else {
        showInfoFeedback("层级状态已刷新", `L${layerIndex} 目前没有新的聚合结果。`)
      }
    } catch (err) {
      showErrorFeedback("层级上推失败", formatApiError(err))
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
          action={<Button onClick={() => navigate("/projects")}>返回项目列表</Button>}
        />
      </div>
    )
  }

  return (
    <div className="space-y-5">
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
              isRollingUp={rollUpM.isPending}
              isThresholdRollUpUpdating={setLayerConfigM.isPending}
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
              {usesResolvableCourseAnchor ? (
                <>
                  <section className="space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="text-[12px] font-medium text-muted-foreground">视频进度</div>
                        <div className="mt-1 text-[17px] font-semibold tracking-[-0.02em] text-[color:var(--theme-soft-text-strong)]">
                          {formatDurationCompact(videoProgress.watchedMs)} / {formatDurationCompact(videoProgress.totalMs)}
                        </div>
                      </div>
                      <div className="text-[13px] font-semibold text-[color:var(--theme-soft-text-strong)]">
                        {Math.round(videoProgressPercent)}%
                      </div>
                    </div>
                    <div className="theme-progress-track h-2 overflow-hidden rounded-full">
                      <div
                        className="theme-progress-fill h-full rounded-full transition-[width] duration-500"
                        style={{ width: `${videoProgressPercent}%` }}
                      />
                    </div>
                    {remainingDurationProbeCount > 0 ? <div className="text-[12px] text-muted-foreground">正在统计 {remainingDurationProbeCount} 个视频时长</div> : null}
                  </section>
                </>
              ) : null}

              <div className="h-px bg-border/70" />

              <section>
                <div className="text-[12px] font-medium text-[#7b8ba0]">今日统计</div>
                <div className="mt-2 divide-y divide-border/60">
                  <StatusMetricRow label="学习时长" value={formatDurationCompact(todayPlaybackMs)} emphasize />
                  <StatusMetricRow
                    label="录入复述点数"
                    value={auditLogQ.isLoading ? "..." : `${todayAuditStats.submittedRecallPoints}`}
                  />
                  <StatusMetricRow
                    label="复习复述点数"
                    value={auditLogQ.isLoading ? "..." : `${todayAuditStats.reviewedRecallPoints}`}
                  />
                </div>
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

import { useEffect, useMemo, useRef, useState } from "react"
import { useQueries } from "@tanstack/react-query"
import { FolderTree, ListChecks, RadioTower, Sparkles } from "lucide-react"
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom"

import { getBaseUrl } from "@/ui/api/http"
import { ApiError } from "@/ui/api/http"
import { listRecallPointsByInstance } from "@/ui/api/instances"
import type { Layer } from "@/ui/api/layers"
import type { Instance } from "@/ui/api/instances"
import type { LearningTaskNode } from "@/ui/api/learningTaskNodes"
import { ContentNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { resolveProjectFile, useProjectDirectoryBinding } from "@/ui/localMedia/projectDirectory"
import { useAuditLogEvents } from "@/ui/queries/auditLog"
import { useLearningTaskNodes } from "@/ui/queries/learningTasks"
import { useSystemCapabilities } from "@/ui/queries/system"
import {
  useAggregationQueue,
  useInstances,
  useLayers,
  useManualRollUp,
  useQueue,
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
import { VideoPane } from "@/views/workbench/components/VideoPane"
import { formatLearningTaskNodeDisplayTitle } from "@/views/learningTasks/displayTitle"

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
      <div className="text-[13px] font-medium text-[#70839a]">{label}</div>
      <div className={cn("text-[15px] font-semibold tracking-[-0.02em]", props.emphasize ? "text-[#1f3952]" : "text-[#33495f]")}>
        {value}
      </div>
    </div>
  )
}

function LearningTaskNodeListItem(props: { projectId: string; node: LearningTaskNode; index: number; sourceLayerIndex?: number }) {
  const { projectId, node, index, sourceLayerIndex } = props
  const to = `/p/${projectId}/learning-task-nodes/${node.nodeId}`
  return (
    <Link
      to={to}
      className="group flex items-start gap-3 rounded-[1.1rem] border border-[#e3e9f1] bg-white px-4 py-3 text-left transition-colors hover:border-primary/20 hover:bg-[#fbfdff]"
    >
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-[#f3f7fc] text-sm font-semibold text-[#2f5d93]">
        {index}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[15px] font-medium text-[#21384d]">
          {formatLearningTaskNodeDisplayTitle(node.title, { sourceLayerIndex })}
        </span>
        <span className="mt-1 block text-xs text-[#70839a]">
          待推进 {sourceLayerIndex !== undefined ? `· 来源 L${sourceLayerIndex}` : ""}
        </span>
      </span>
    </Link>
  )
}

function LayerReviewChainCard(props: {
  projectId: string
  layer: Layer
  learningTaskNodesById: Record<string, LearningTaskNode>
  learningTaskNodesLoading: boolean
  queueHasGate: boolean
  isRollingUp: boolean
  onRollUp: (layerIndex: number) => void
}) {
  const { projectId, layer, learningTaskNodesById, learningTaskNodesLoading, queueHasGate, isRollingUp, onRollUp } = props
  const aggQ = useAggregationQueue(projectId, layer.layerIndex)
  const candidateCount = aggQ.data?.currentNodeIds.length ?? 0
  const currentNodeIds = aggQ.data?.currentNodeIds ?? []

  return (
    <div className="rounded-[1.2rem] border border-[#e2e8ef] bg-white p-4 sm:p-5">
      <div className="flex flex-col gap-3 sm:grid sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:items-center sm:gap-4">
        <div className="flex min-w-0 items-center">
          <div className="theme-meta shrink-0 px-4 py-1.5 text-sm font-semibold">
            L{layer.layerIndex}
          </div>
        </div>
        <div className="min-w-0">
          <div className="theme-meta max-w-full px-4 py-1.5 text-sm">
            <span className="truncate">
              {aggQ.isLoading ? "正在加载节点..." : `${candidateCount} 个待推进节点`}
            </span>
          </div>
        </div>
        <Button
          className="shrink-0"
          onClick={() => onRollUp(layer.layerIndex)}
          disabled={queueHasGate || isRollingUp || !aggQ.data || candidateCount === 0}
        >
          {isRollingUp ? "上推中..." : "上推"}
        </Button>
      </div>

      <div className="mt-4 space-y-3">
        {currentNodeIds.length > 0 ? (
          currentNodeIds.map((nodeId, index) => {
            const node = learningTaskNodesById[nodeId]
            if (!node) {
              return (
                <div key={nodeId} className="rounded-[1.1rem] border border-[#e3e9f1] bg-[#fbfcfe] px-4 py-3 text-sm text-[#6f7f93]">
                  {learningTaskNodesLoading ? "正在加载学习任务..." : "节点信息同步中..."}
                </div>
              )
            }
            return (
              <LearningTaskNodeListItem
                key={nodeId}
                projectId={projectId}
                node={node}
                index={index + 1}
                sourceLayerIndex={Math.max(0, layer.layerIndex - 1)}
              />
            )
          })
        ) : (
          <div className="rounded-[1.1rem] border border-dashed border-[#dbe3ec] bg-[#fbfcfe] px-4 py-4">
            <div className="text-sm font-medium text-[#21384d]">暂无待上推任务</div>
          </div>
        )}
      </div>
      {aggQ.error ? <div className="mt-2 text-xs text-destructive">{formatApiError(aggQ.error)}</div> : null}
    </div>
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
  const capabilitiesQ = useSystemCapabilities()
  const directoryBinding = useProjectDirectoryBinding(pid)

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
  const durationProbeSessionRef = useRef(0)

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
    setVideoDurationByInstanceId(loadVideoDurationMap(pid, instanceIds))
  }, [instancesQ.data, pid])

  useEffect(() => {
    setDurationProbeAttemptedByInstanceId({})
    setDurationProbeInFlightByInstanceId({})
    durationProbeSessionRef.current += 1
  }, [browserLocalMediaEnabled, directoryBinding.permission, pid, serverMediaStreamEnabled])

  const recallPointIdsByInstanceQs = useQueries({
    queries: (instancesQ.data ?? []).map((instance) => ({
      queryKey: ["recallPointsByInstance", pid, instance.instanceId],
      queryFn: () => listRecallPointsByInstance(pid, instance.instanceId),
      enabled: !!pid && !!instance.instanceId,
      staleTime: 30_000,
    })),
  })

  const watchedInstanceIds = useMemo(() => {
    const out = new Set<string>()
    for (let index = 0; index < (instancesQ.data ?? []).length; index += 1) {
      const instance = instancesQ.data?.[index]
      if (!instance) continue
      const recallPointIds = recallPointIdsByInstanceQs[index]?.data?.recallPointIds ?? []
      if (recallPointIds.length > 0) {
        out.add(instance.instanceId)
      }
    }
    return out
  }, [instancesQ.data, recallPointIdsByInstanceQs])

  const pendingDurationProbeInstances = useMemo(() => {
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
  }, [durationProbeAttemptedByInstanceId, durationProbeInFlightByInstanceId, instancesQ.data, videoDurationByInstanceId])

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
      <div className="grid gap-5 xl:items-start xl:grid-cols-[300px_minmax(0,1.2fr)_320px]">
        <aside className="xl:sticky xl:top-28 xl:self-start">
          <Card
            id="workbench-content-tree"
            className="theme-card-main xl:flex xl:max-h-[calc(100dvh-9rem)] xl:min-h-0 xl:flex-col xl:overflow-hidden"
          >
            <CardHeader className="theme-card-header">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-[#e2e8f0] bg-[#f5f7fa] text-primary">
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

        <section className="space-y-4 xl:min-w-0">
          <div ref={videoPaneRef} id="workbench-video-pane" className="shrink-0 scroll-mt-28">
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
          </div>
          <div className="shrink-0 rounded-[1.25rem] border border-[#dfe6ef] bg-[#f7f9fc] p-1">
            <div className="grid grid-cols-2 gap-1">
              <button
                type="button"
                className={cn(
                  "rounded-[1rem] border px-4 py-2.5 text-sm font-medium transition-colors",
                  centerPanelMode === "main"
                    ? "border-primary/20 bg-white text-primary shadow-[0_10px_22px_-20px_rgba(30,58,95,0.32)]"
                    : "border-transparent bg-transparent text-[#41566f] hover:border-[#dde5ef] hover:bg-white/80",
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
                    ? "border-primary/20 bg-white text-primary shadow-[0_10px_22px_-20px_rgba(30,58,95,0.32)]"
                    : "border-transparent bg-transparent text-[#41566f] hover:border-[#dde5ef] hover:bg-white/80",
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
                  selectedInstanceId={selectedInstanceId}
                  instance={instance}
                  currentMs={currentMs}
                  queueHasGate={queueHasGate}
                />
              )}
            </div>
          ) : (
            <Card className="theme-card-main shrink-0" id="workbench-rollup-pane">
              <CardHeader className="theme-card-header">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-[#e2e8f0] bg-[#f5f7fa] text-primary">
                    <ListChecks className="h-5 w-5" />
                  </div>
                  <div>
                    <CardTitle>层推进与学习任务</CardTitle>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4 pt-2 text-sm">
                {layersQ.isLoading ? <div className="rounded-[1.15rem] bg-[#f6f8fb] px-4 py-4 text-sm text-[#647589]">正在加载层级任务...</div> : null}
                {layersQ.error ? <p className="text-sm text-destructive">{formatApiError(layersQ.error)}</p> : null}
                {!layersQ.isLoading && !layersQ.error && (layersQ.data?.length ?? 0) === 0 ? (
                  <div className="flex items-start gap-3 rounded-[1.2rem] bg-[#f6f8fb] px-4 py-4">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[#eef5ff] text-primary">
                      <Sparkles className="h-4 w-4" />
                    </div>
                    <div className="text-sm font-medium text-foreground">当前还没有层配置</div>
                  </div>
                ) : null}
                <div className="space-y-2">
                  {(layersQ.data ?? []).map((l) => (
                    <LayerReviewChainCard
                      key={l.layerId}
                      projectId={pid}
                      layer={l}
                      learningTaskNodesById={learningTaskNodesById}
                      learningTaskNodesLoading={learningTaskNodesQ.isLoading}
                      queueHasGate={queueHasGate}
                      isRollingUp={rollUpM.isPending}
                      onRollUp={(layerIndex) => void onManualRollUp(layerIndex)}
                    />
                  ))}
                </div>
                {rollUpM.error ? <p className="text-sm text-destructive">{formatApiError(rollUpM.error)}</p> : null}
              </CardContent>
            </Card>
          )}
        </section>

        <aside className="xl:sticky xl:top-28 xl:self-start">
          <Card className="theme-card-main xl:flex xl:max-h-[calc(100dvh-9rem)] xl:min-h-0 xl:flex-col xl:overflow-hidden">
            <CardHeader className="theme-card-header">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-[#e2e8f0] bg-[#f5f7fa] text-primary">
                  <RadioTower className="h-5 w-5" />
                </div>
                <div>
                  <CardTitle>工作状态</CardTitle>
                  <div className="mt-1 text-[15px] font-medium text-[#314a63]">{workStatusDetail}</div>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-5 pt-4 text-sm xl:min-h-0 xl:flex-1 xl:overflow-y-auto xl:overscroll-contain xl:pr-3">
              <section className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-[12px] font-medium text-[#7b8ba0]">视频进度</div>
                    <div className="mt-1 text-[17px] font-semibold tracking-[-0.02em] text-[#314a63]">
                      {formatDurationCompact(videoProgress.watchedMs)} / {formatDurationCompact(videoProgress.totalMs)}
                    </div>
                  </div>
                  <div className="text-[13px] font-semibold text-[#49627c]">
                    {Math.round(videoProgressPercent)}%
                  </div>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-[#e7edf5]">
                  <div
                    className="h-full rounded-full bg-[linear-gradient(90deg,#245c96_0%,#5f9fda_100%)] transition-[width] duration-500"
                    style={{ width: `${videoProgressPercent}%` }}
                  />
                </div>
                {remainingDurationProbeCount > 0 ? (
                  <div className="text-[12px] text-[#7b8ba0]">正在统计 {remainingDurationProbeCount} 个视频时长</div>
                ) : null}
              </section>

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

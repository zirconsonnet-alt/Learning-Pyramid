import { useEffect, useMemo, useState } from "react"
import { useQueries } from "@tanstack/react-query"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { listRecallPointsByInstance } from "@/ui/api/instances"
import type { Layer } from "@/ui/api/layers"
import type { Instance } from "@/ui/api/instances"
import type { LearningTaskNode } from "@/ui/api/learningTaskNodes"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { useLearningTaskNodes } from "@/ui/queries/learningTasks"
import {
  useAggregationQueue,
  useInstances,
  useLayers,
  useManualRollUp,
  useQueue,
} from "@/ui/queries/workbench"
import { useAppStore } from "@/ui/store/appStore"
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

function LearningTaskNodeLink(props: { projectId: string; node: LearningTaskNode; sourceLayerIndex?: number }) {
  const { projectId, node, sourceLayerIndex } = props
  const to =
    node.kind === "leaf"
      ? `/p/${projectId}/learning-tasks/${node.boundLearningTaskId}`
      : `/p/${projectId}/learning-task-nodes/${node.nodeId}`
  return (
    <Button size="sm" variant="outline" asChild className="max-w-full justify-start rounded-full">
      <Link to={to}>{formatLearningTaskNodeDisplayTitle(node.title, { sourceLayerIndex })}</Link>
    </Button>
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
    <div className="theme-status-surface rounded-[1.2rem] border border-border/70 p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="theme-meta-strong">L{layer.layerIndex}</div>
          <div className="theme-meta">
            {aggQ.isLoading ? "加载中..." : `${candidateCount} 节点`}
          </div>
        </div>
        <Button
          size="sm"
          onClick={() => onRollUp(layer.layerIndex)}
          disabled={queueHasGate || isRollingUp || !aggQ.data || candidateCount === 0}
        >
          {isRollingUp ? "上推中..." : "上推"}
        </Button>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        {currentNodeIds.length > 0 ? (
          currentNodeIds.map((nodeId) => {
            const node = learningTaskNodesById[nodeId]
            if (!node) {
              return (
                <div key={nodeId} className="rounded-full border px-3 py-2 text-sm text-muted-foreground">
                  {learningTaskNodesLoading ? "加载学习任务中..." : "节点加载中..."}
                </div>
              )
            }
            return (
              <LearningTaskNodeLink
                key={nodeId}
                projectId={projectId}
                node={node}
                sourceLayerIndex={Math.max(0, layer.layerIndex - 1)}
              />
            )
          })
        ) : (
          <span className="text-xs text-muted-foreground">当前无学习任务</span>
        )}
      </div>
      {aggQ.error ? <div className="mt-2 text-xs text-destructive">{formatApiError(aggQ.error)}</div> : null}
    </div>
  )
}

export function WorkbenchPage() {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const pid = projectId ?? ""

  const ensure = useWorkbenchStore((s) => s.ensure)
  const ps = useWorkbenchStore((s) => (pid ? s.byProjectId[pid] : undefined))
  const setSelectedInstanceId = useWorkbenchStore((s) => s.setSelectedInstanceId)

  const selectedProjectId = useAppStore((s) => s.selectedProjectId)

  const [currentMs, setCurrentMs] = useState(0)
  const [seekTo, setSeekTo] = useState<{ instanceId: string; ms: number; nonce: number } | null>(null)

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
  const rollUpM = useManualRollUp(pid)

  const selectedInstanceId = ps?.selectedInstanceId ?? null
  const queueHasGate = !!queueQ.data?.headId

  const instance: Instance | null = useMemo(() => {
    const items = instancesQ.data ?? []
    return selectedInstanceId ? items.find((i) => i.instanceId === selectedInstanceId) ?? null : null
  }, [instancesQ.data, selectedInstanceId])

  const missingInstances = useMemo(
    () => (instancesQ.data ?? []).filter((item) => item.presence === "MISSING"),
    [instancesQ.data],
  )
  const missingRecallPointQs = useQueries({
    queries: missingInstances.map((instance) => ({
      queryKey: ["recallPointsByInstance", pid, instance.instanceId],
      queryFn: () => listRecallPointsByInstance(pid, instance.instanceId),
      enabled: !!pid,
    })),
  })
  const actionableMissingCount = useMemo(
    () => missingRecallPointQs.filter((query) => (query.data?.recallPointIds.length ?? 0) > 0).length,
    [missingRecallPointQs],
  )

  const learningTaskNodesById = useMemo(() => {
    const map: Record<string, LearningTaskNode> = {}
    for (const node of learningTaskNodesQ.data ?? []) map[node.nodeId] = node
    return map
  }, [learningTaskNodesQ.data])

  useEffect(() => {
    if (!pid) return
    if (!instancesQ.data) return
    if (selectedInstanceId && !instancesQ.data.some((i) => i.instanceId === selectedInstanceId)) {
      setSelectedInstanceId(pid, null)
    }
  }, [instancesQ.data, pid, selectedInstanceId, setSelectedInstanceId])

  async function onManualRollUp(layerIndex: number) {
    if (queueHasGate) return
    await rollUpM.mutateAsync({ layerIndex })
  }

  function onOpenAnchor(a: { instanceId: string; position: string }) {
    setSelectedInstanceId(pid, a.instanceId)
    const ms = parseAnchorMs(a.position)
    if (ms === null) {
      setSeekTo(null)
      return
    }
    setSeekTo({ instanceId: a.instanceId, ms, nonce: Date.now() })
  }

  if (!pid) {
    return (
      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">缺少 projectId。</p>
        <Button onClick={() => navigate("/projects")}>返回项目列表</Button>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      {actionableMissingCount > 0 ? (
        <Card className="theme-card border-amber-200/80 bg-amber-50/70">
          <CardContent className="flex flex-col gap-3 px-6 py-5 md:flex-row md:items-center md:justify-between">
            <div className="space-y-1">
              <div className="text-sm font-semibold text-slate-900">检测到 {actionableMissingCount} 个待修复失效实例</div>
              <div className="text-sm text-slate-600">
                这些旧实例仍被复述点锚点引用。请到项目设置完成手动重映射。
              </div>
            </div>
            <Button asChild>
              <Link to={`/p/${pid}/settings`}>前往修复</Link>
            </Button>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-5 xl:grid-cols-[300px_minmax(0,1.2fr)_320px]">
        <div className="space-y-4">
          <Card className="theme-card">
            <CardHeader className="theme-card-header">
              <CardTitle>学习对象</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="theme-canvas rounded-[1.1rem] border border-border/60 p-3">
                <LearningObjectTree
                  projectId={pid}
                  selectedInstanceId={selectedInstanceId}
                  onSelectInstance={(instanceId) => {
                    setSelectedInstanceId(pid, instanceId)
                    setSeekTo(null)
                    setCurrentMs(0)
                  }}
                />
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <VideoPane
            key={instance?.instanceId ?? "none"}
            projectId={pid}
            instance={instance}
            setCurrentMs={setCurrentMs}
            seekTo={seekTo}
            onSeekApplied={(nonce) => setSeekTo((s) => (s && s.nonce === nonce ? null : s))}
          />
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

        <div className="space-y-4">
          <Card className="theme-card">
            <CardHeader className="theme-card-header">
              <CardTitle>系统状态</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="theme-status-surface flex items-center justify-between px-4 py-3">
                <span className="text-muted-foreground">队列长度</span>
                <span className="theme-meta">{queueQ.data ? queueQ.data.ids.length : "-"}</span>
              </div>
              <div className="theme-status-surface flex items-center justify-between px-4 py-3">
                <span className="text-muted-foreground">当前状态</span>
                <span className={cn("theme-meta", queueHasGate && "border-destructive/20 bg-destructive/10 text-destructive")}>
                  {queueHasGate ? "待复习" : "空闲"}
                </span>
              </div>
            </CardContent>
          </Card>

          <Card className="theme-card">
            <CardHeader className="theme-card-header">
              <CardTitle>层与学习任务</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              {layersQ.isLoading ? <p className="text-sm text-muted-foreground">加载中...</p> : null}
              {layersQ.error ? <p className="text-sm text-destructive">{formatApiError(layersQ.error)}</p> : null}
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

        </div>
      </div>
    </div>
  )
}

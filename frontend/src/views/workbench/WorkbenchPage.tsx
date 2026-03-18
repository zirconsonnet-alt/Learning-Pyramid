import { useEffect, useMemo, useState } from "react"
import { FolderTree, ListChecks, RadioTower, Sparkles } from "lucide-react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import type { Layer } from "@/ui/api/layers"
import type { Instance } from "@/ui/api/instances"
import type { LearningTaskNode } from "@/ui/api/learningTaskNodes"
import { ContentEmptyState, ContentNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { useLearningTaskNodes } from "@/ui/queries/learningTasks"
import {
  useAggregationQueue,
  useInstances,
  useLayers,
  useManualRollUp,
  useQueue,
} from "@/ui/queries/workbench"
import { useAppStore } from "@/ui/store/appStore"
import { showErrorFeedback, showInfoFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
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

function StatusStrip(props: { label: string; value: string; hint?: string; warning?: boolean }) {
  const { label, value, hint, warning = false } = props
  return (
    <div
      className={cn(
        "theme-status-surface flex items-start justify-between gap-4 px-4 py-3",
        warning && "border-amber-200/70 bg-amber-50/80",
      )}
    >
      <div className="min-w-0">
        <div className="text-xs font-semibold uppercase tracking-[0.18em] text-[#73839a]">{label}</div>
        {hint ? <div className="mt-1 text-sm text-muted-foreground">{hint}</div> : null}
      </div>
      <div className={cn("theme-meta shrink-0", warning && "border-amber-300 bg-amber-100 text-amber-800")}>{value}</div>
    </div>
  )
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
          <ContentEmptyState
            title={`L${layer.layerIndex} 当前还没有待上推任务`}
            message="继续录入并提交学习任务，或先完成下游复习；出现可上推任务后会显示在这里。"
            className="w-full bg-white/60 px-3 py-3"
          />
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
      <div className="grid gap-5 xl:grid-cols-[300px_minmax(0,1.2fr)_320px]">
        <div className="space-y-4">
          <Card className="theme-card-main">
            <CardHeader className="theme-card-header space-y-2">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#edf4ff] text-primary">
                  <FolderTree className="h-5 w-5" />
                </div>
                <div>
                  <CardTitle>内容目录</CardTitle>
                  <CardDescription>从学习对象树选择一个视频实例，作为当前播放与录入上下文。</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
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
          <Card className="theme-card-main">
            <CardHeader className="theme-card-header space-y-2">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#edf4ff] text-primary">
                  <RadioTower className="h-5 w-5" />
                </div>
                <div>
                  <CardTitle>工作状态</CardTitle>
                  <CardDescription>观察当前队列和门禁状态，确保工作流保持连续。</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <StatusStrip label="队列长度" value={queueQ.data ? `${queueQ.data.ids.length}` : "-"} hint={queueHasGate ? "存在待复习项目，提交学习将暂时关闭。" : "当前没有待处理的复习门禁。"} warning={queueHasGate} />
              <StatusStrip label="当前操作" value={queueHasGate ? "复习" : "录入"} hint={queueHasGate ? "先完成复习再继续新增学习任务。" : "现在可以继续添加复述点并提交学习。"} />
            </CardContent>
          </Card>

          <Card className="theme-card-main">
            <CardHeader className="theme-card-header space-y-2">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#edf4ff] text-primary">
                  <ListChecks className="h-5 w-5" />
                </div>
                <div>
                  <CardTitle>层推进与学习任务</CardTitle>
                  <CardDescription>查看每一层待推进的学习任务节点，并在空闲时执行上推。</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              {layersQ.isLoading ? <p className="text-sm text-muted-foreground">加载中...</p> : null}
              {layersQ.error ? <p className="text-sm text-destructive">{formatApiError(layersQ.error)}</p> : null}
              {!layersQ.isLoading && !layersQ.error && (layersQ.data?.length ?? 0) === 0 ? (
                <div className="theme-status-surface flex items-start gap-3 px-4 py-4">
                  <Sparkles className="mt-0.5 h-4 w-4 text-primary" />
                  <div className="space-y-1">
                    <div className="text-sm font-medium text-foreground">当前还没有层配置</div>
                    <div className="text-sm text-muted-foreground">请先在项目设置里确认层配置；保存后会显示各层候选任务。</div>
                  </div>
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
        </div>
      </div>
    </div>
  )
}

import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { ChevronRight, Waypoints } from "lucide-react"
import { useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { listAggregationEvents, type AggregationEvent } from "@/ui/api/layers"
import { listLearningTaskNodes, type LearningTaskNode } from "@/ui/api/learningTaskNodes"
import { ContentEmptyState, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { useLearningTask, useLearningTaskNodeBinding } from "@/ui/queries/learningTasks"
import { formatLearningTaskNodeDisplayTitle, isDefaultAggregationTitle } from "@/views/learningTasks/displayTitle"
import { useConvergence, useReviewChain } from "@/ui/queries/reviewChains"
import { cn } from "@/ui/utils"
import { type LearningTaskTreeNode, LearningTaskTreeCanvas } from "@/views/trees/components/LearningTaskTreeCanvas"

type TaskTreeVisualType = "aggregation" | "chapter" | "task"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function deriveTaskNodeLayers(nodes: LearningTaskNode[], events: AggregationEvent[]) {
  const layerById: Record<string, number> = {}

  for (const node of nodes) {
    if (node.kind === "leaf") layerById[node.nodeId] = 0
  }

  const sortedEvents = [...events].sort((a, b) => {
    if (a.layerIndex !== b.layerIndex) return a.layerIndex - b.layerIndex
    return a.parentNodeId.localeCompare(b.parentNodeId)
  })

  for (const event of sortedEvents) {
    layerById[event.parentNodeId] = event.layerIndex + 1
    for (const childNodeId of event.childNodeIds) {
      layerById[childNodeId] = event.layerIndex
    }
  }

  let changed = true
  while (changed) {
    changed = false

    for (const node of nodes) {
      const current = layerById[node.nodeId]

      if (current === undefined && node.kind === "container") {
        const childLayers = (node.children ?? []).map((childId) => layerById[childId]).filter((value) => value !== undefined)
        if (childLayers.length === (node.children ?? []).length && childLayers.length > 0) {
          layerById[node.nodeId] = Math.max(...childLayers) + 1
          changed = true
          continue
        }
      }

      if (current === undefined && node.parentId && layerById[node.parentId] !== undefined) {
        layerById[node.nodeId] = Math.max(0, layerById[node.parentId] - 1)
        changed = true
      }
    }
  }

  for (const node of nodes) {
    if (layerById[node.nodeId] === undefined) layerById[node.nodeId] = 0
  }

  return layerById
}

function formatDisplayTitle(rawTitle: string, uiType: TaskTreeVisualType, _layerIndex: number) {
  const title = rawTitle.trim()
  return formatLearningTaskNodeDisplayTitle(title, {
    sourceLayerIndex: uiType === "aggregation" ? Math.max(0, _layerIndex - 1) : undefined,
  })
}

function classifyTaskNode(node: LearningTaskNode, event: AggregationEvent | undefined): TaskTreeVisualType {
  if (node.kind === "leaf") return "task"

  const title = node.title.trim()
  if (isDefaultAggregationTitle(title)) return "aggregation"
  if (isDefaultAggregationTitle(event?.title)) return "aggregation"
  if (!event?.title || !event.title.trim()) return "aggregation"
  return "chapter"
}

function getPathNodeIds(nodeId: string | null, parentById: Record<string, string | null>) {
  if (!nodeId) return []

  const path: string[] = []
  let current: string | null | undefined = nodeId
  while (current) {
    path.unshift(current)
    current = parentById[current]
  }
  return path
}

function getReviewStatus(binding: ReturnType<typeof useLearningTaskNodeBinding>["data"], convergence: ReturnType<typeof useConvergence>["data"]) {
  if (!binding?.reviewChainId) {
    return {
      label: "未建立复习链",
      className: "border-slate-200 bg-slate-50 text-slate-600",
    }
  }

  if (convergence?.state === "TERMINATED") {
    return {
      label: `已完成 ${convergence.roundCount} 轮收敛`,
      className: "border-emerald-200 bg-emerald-50 text-emerald-700",
    }
  }

  if (convergence?.state === "IN_PROGRESS") {
    return {
      label: `复习进行中 · 第 ${convergence.roundCount} 轮`,
      className: "border-amber-200 bg-amber-50 text-amber-700",
    }
  }

  return {
    label: "复习链已建立",
    className: "border-sky-200 bg-sky-50 text-sky-700",
  }
}

export function TaskTreePage() {
  const { projectId } = useParams()
  const pid = projectId ?? ""
  const nav = useNavigate()
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null)

  const q = useQuery({
    queryKey: ["learningTaskNodes", pid],
    queryFn: () => listLearningTaskNodes(pid),
    enabled: !!pid,
  })

  const eventsQ = useQuery({
    queryKey: ["aggregationEvents", pid],
    queryFn: () => listAggregationEvents(pid),
    enabled: !!pid,
  })

  const {
    defaultSelectedId,
    descendantLeafCountById,
    nodeById,
    nodeLayerById,
    parentById,
    rootIds,
  } = useMemo(() => {
    const rawNodes = q.data ?? []
    const events = eventsQ.data ?? []
    const rawNodeById: Record<string, LearningTaskNode> = {}
    const eventByParentId: Record<string, AggregationEvent> = {}
    const directParentById: Record<string, string | null> = {}

    for (const node of rawNodes) {
      rawNodeById[node.nodeId] = node
      directParentById[node.nodeId] = node.parentId
    }
    for (const event of events) {
      eventByParentId[event.parentNodeId] = event
    }

    const layerById = deriveTaskNodeLayers(rawNodes, events)
    const descendantCountById: Record<string, number> = {}

    function countLeafDescendants(nodeId: string): number {
      const cached = descendantCountById[nodeId]
      if (cached !== undefined) return cached

      const node = rawNodeById[nodeId]
      if (!node) return 0
      if (node.kind === "leaf") {
        descendantCountById[nodeId] = 1
        return 1
      }

      const total = (node.children ?? []).reduce((sum, childId) => sum + countLeafDescendants(childId), 0)
      descendantCountById[nodeId] = total
      return total
    }

    for (const nodeId of Object.keys(rawNodeById)) countLeafDescendants(nodeId)

    const map: Record<string, LearningTaskTreeNode> = {}

    for (const node of rawNodes) {
      const layerIndex = layerById[node.nodeId] ?? 0
      const uiType = classifyTaskNode(node, eventByParentId[node.nodeId])
      const taskSpan = descendantCountById[node.nodeId] ?? 0
      const childCount = node.kind === "container" ? (node.children?.length ?? 0) : 0

      map[node.nodeId] = {
        nodeId: node.nodeId,
        title: formatDisplayTitle(node.title, uiType, layerIndex),
        rawTitle: node.title,
        displayTitle: formatDisplayTitle(node.title, uiType, layerIndex),
        uiType,
        metaText:
          uiType === "task"
            ? "叶子任务"
            : uiType === "aggregation"
              ? `${taskSpan} 个任务 · ${childCount} 个分支`
              : `${taskSpan} 个任务`,
        kind: node.kind,
        children: node.kind === "container" ? node.children : undefined,
        learningTaskId: node.kind === "leaf" ? node.boundLearningTaskId : undefined,
      }
    }

    const roots = rawNodes
      .filter((node) => node.parentId === null)
      .map((node) => node.nodeId)
      .sort((a, b) => a.localeCompare(b))

    const defaultNodeId = roots[0] ?? Object.keys(map).sort((a, b) => a.localeCompare(b))[0] ?? null

    return {
      defaultSelectedId: defaultNodeId,
      descendantLeafCountById: descendantCountById,
      nodeById: map,
      nodeLayerById: layerById,
      parentById: directParentById,
      rootIds: roots,
    }
  }, [eventsQ.data, q.data])

  const effectiveSelectedNodeId = selectedNodeId && nodeById[selectedNodeId] ? selectedNodeId : defaultSelectedId
  const selectedNode = effectiveSelectedNodeId ? nodeById[effectiveSelectedNodeId] : null
  const selectedBindingQ = useLearningTaskNodeBinding(pid, effectiveSelectedNodeId ?? "")
  const selectedTaskId =
    selectedNode?.kind === "leaf" ? (selectedNode.learningTaskId ?? selectedBindingQ.data?.learningTaskId ?? "") : ""
  const selectedTaskQ = useLearningTask(pid, selectedTaskId)
  const selectedReviewChainId = selectedBindingQ.data?.reviewChainId ?? ""
  const selectedChainQ = useReviewChain(pid, selectedReviewChainId)
  const convergenceId = selectedChainQ.data?.queue.find((item) => item.kind === "CONVERGENCE")?.id ?? ""
  const selectedConvergenceQ = useConvergence(pid, convergenceId)

  const pathNodeIds = useMemo(
    () => getPathNodeIds(effectiveSelectedNodeId, parentById),
    [effectiveSelectedNodeId, parentById],
  )

  const selectedParent = selectedNode ? (parentById[selectedNode.nodeId] ? nodeById[parentById[selectedNode.nodeId] ?? ""] : null) : null
  const selectedChildren =
    selectedNode?.kind === "container"
      ? (selectedNode.children ?? []).map((childId) => nodeById[childId]).filter((node): node is LearningTaskTreeNode => !!node)
      : []

  const detailStatus = getReviewStatus(selectedBindingQ.data, selectedConvergenceQ.data)
  const canvasFocusNodeId = hoveredNodeId ?? effectiveSelectedNodeId
  const isLoading = q.isLoading || eventsQ.isLoading
  const hasData = (q.data ?? []).length > 0

  return (
    <div className="space-y-5">
      <section className="theme-card p-5 md:p-6">
        {selectedNode ? (
          <div className="space-y-5">
            <div className="flex flex-col gap-4 border-b border-border/60 pb-4 xl:flex-row xl:items-start xl:justify-between">
              <div className="space-y-3">
                <div className="flex flex-wrap gap-2">
                  <span className="theme-meta-strong">学习任务树</span>
                  <span className="theme-meta">进入页面默认定位根节点</span>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <TypeBadge uiType={selectedNode.uiType} />
                  <span className="inline-flex items-center rounded-full border border-[#d8e3ee] bg-[#f6f9fc] px-2.5 py-1 text-xs font-semibold text-[#5f7790]">
                    L{nodeLayerById[selectedNode.nodeId] ?? 0}
                  </span>
                  <span className={cn("inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold", detailStatus.className)}>
                    {detailStatus.label}
                  </span>
                </div>
                <div>
                  <h1 className="text-[1.7rem] font-semibold tracking-tight text-foreground">
                    {selectedNode.displayTitle ?? selectedNode.title}
                  </h1>
                  <p className="mt-2 text-sm text-[#647b93]">{selectedNode.metaText}</p>
                </div>
              </div>

              <div className="flex flex-wrap gap-3">
                <Button variant="outline" onClick={() => nav(`/p/${pid}/learning-task-nodes/${selectedNode.nodeId}`)}>
                  查看节点详情
                </Button>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <DetailMetric label="覆盖任务数" value={`${descendantLeafCountById[selectedNode.nodeId] ?? 0}`} />
              <DetailMetric
                label={selectedNode.kind === "container" ? "直接子节点" : "目标层"}
                value={
                  selectedNode.kind === "container"
                    ? `${selectedChildren.length}`
                    : selectedBindingQ.data?.targetLayerIndex === undefined || selectedBindingQ.data?.targetLayerIndex === null
                      ? "-"
                      : `L${selectedBindingQ.data.targetLayerIndex}`
                }
              />
              <DetailMetric label="绑定任务" value={selectedNode.kind === "leaf" && selectedNode.learningTaskId ? "已绑定" : "无"} />
              <DetailMetric
                label="复述点数"
                value={selectedTaskQ.data?.size === undefined || selectedTaskQ.data?.size === null ? "-" : `${selectedTaskQ.data.size}`}
              />
            </div>

            <div className="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,0.8fr)_minmax(0,1fr)]">
              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-[#688099]">路径</div>
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  {pathNodeIds.map((nodeId, index) => {
                    const node = nodeById[nodeId]
                    if (!node) return null
                    return (
                      <div key={nodeId} className="flex items-center gap-2">
                        <button
                          type="button"
                          className={cn(
                            "rounded-full border px-3 py-1.5 text-xs font-medium transition hover:border-primary/30 hover:bg-accent hover:text-foreground",
                            nodeId === selectedNode.nodeId
                              ? "border-[#9fbad6] bg-[#eef5fd] text-[#31567d]"
                              : "border-[#d6e0ea] bg-white text-[#607892]",
                          )}
                          onClick={() => setSelectedNodeId(nodeId)}
                        >
                          {node.displayTitle ?? node.title}
                        </button>
                        {index < pathNodeIds.length - 1 ? <ChevronRight className="size-3.5 text-[#8097ae]" /> : null}
                      </div>
                    )
                  })}
                </div>
              </div>

              {selectedParent ? (
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-[#688099]">上级节点</div>
                  <button
                    type="button"
                    className="mt-3 w-full rounded-2xl border border-[#d6e0ea] bg-white px-4 py-3 text-left text-sm font-medium text-[#31567d] transition hover:border-primary/20 hover:bg-accent"
                    onClick={() => setSelectedNodeId(selectedParent.nodeId)}
                  >
                    {selectedParent.displayTitle ?? selectedParent.title}
                  </button>
                </div>
              ) : (
                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.18em] text-[#688099]">上级节点</div>
                  <div className="mt-3 rounded-2xl border border-dashed border-[#d6e0ea] bg-white/60 px-4 py-3 text-sm text-[#7a91a9]">
                    当前已在根节点
                  </div>
                </div>
              )}

              <div>
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-[#688099]">下级节点</div>
                {selectedChildren.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {selectedChildren.map((child) => (
                      <button
                        key={child.nodeId}
                        type="button"
                        className="rounded-full border border-[#d6e0ea] bg-white px-3 py-1.5 text-xs font-medium text-[#5d7590] transition hover:border-primary/20 hover:bg-accent hover:text-foreground"
                        onClick={() => setSelectedNodeId(child.nodeId)}
                      >
                        {child.displayTitle ?? child.title}
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="mt-3 rounded-2xl border border-dashed border-[#d6e0ea] bg-white/60 px-4 py-3 text-sm text-[#7a91a9]">
                    当前节点没有下级节点
                  </div>
                )}
              </div>
            </div>

            {selectedBindingQ.error ? <ErrorNotice title="节点绑定加载失败" message={formatApiError(selectedBindingQ.error)} /> : null}
            {selectedTaskQ.error ? <ErrorNotice title="学习任务详情加载失败" message={formatApiError(selectedTaskQ.error)} /> : null}
            {selectedChainQ.error ? <ErrorNotice title="复习链摘要加载失败" message={formatApiError(selectedChainQ.error)} /> : null}
            {selectedConvergenceQ.error ? <ErrorNotice title="收敛状态加载失败" message={formatApiError(selectedConvergenceQ.error)} /> : null}
          </div>
        ) : (
          <ContentEmptyState
            title="先选择一个任务节点"
            message="从结构图里点击任意任务、章节或聚合节点，这里就会显示它的层级、复习状态和上下游关系。"
          />
        )}
      </section>

      <section className="theme-card-main overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-border/60 px-6 py-5 md:flex-row md:items-center md:justify-between">
          <h2 className="text-base font-semibold text-foreground">结构视图</h2>
          <div className="flex flex-wrap gap-2 text-xs text-[#688099]">
            <span className="theme-meta">组内紧，组间松</span>
            <span className="theme-meta">层标签仅作辅助定位</span>
          </div>
        </div>

        <div className="theme-canvas min-h-[36rem] overflow-auto p-4 md:p-5">
          {isLoading ? <LoadingNotice title="正在加载学习任务树" message="正在整理任务节点、聚合关系和层级布局。" /> : null}
          {q.error ? <ErrorNotice title="学习任务树加载失败" message={formatApiError(q.error)} /> : null}
          {eventsQ.error ? <ErrorNotice title="聚合事件加载失败" message={formatApiError(eventsQ.error)} /> : null}
          {!isLoading && !q.error && !eventsQ.error && !hasData ? (
            <ContentEmptyState
              icon={Waypoints}
              title="当前项目还没有学习任务树"
              message="先在工作台提交一批复述点并创建学习任务，任务结构就会显示在这里。"
            />
          ) : null}
          {!isLoading && !q.error && !eventsQ.error && hasData ? (
            <LearningTaskTreeCanvas
              rootIds={rootIds}
              nodeById={nodeById}
              nodeLayerById={nodeLayerById}
              selectedNodeId={effectiveSelectedNodeId}
              focusNodeId={canvasFocusNodeId}
              onNodeHover={setHoveredNodeId}
              onNodeSelect={(node) => setSelectedNodeId(node.nodeId)}
            />
          ) : null}
        </div>
      </section>
    </div>
  )
}

function DetailMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[1.2rem] border border-white/70 bg-white/82 px-4 py-3 shadow-[0_12px_32px_-28px_rgba(15,23,42,0.2)]">
      <div className="text-xs text-[#7088a1]">{label}</div>
      <div className="mt-1 text-lg font-semibold tracking-tight text-foreground">{value}</div>
    </div>
  )
}

function TypeBadge({ uiType }: { uiType?: TaskTreeVisualType }) {
  const labelByType: Record<TaskTreeVisualType, { className: string; label: string }> = {
    aggregation: {
      label: "聚合节点",
      className: "border-[#b9cee3] bg-[#f3f8ff] text-[#2f547b]",
    },
    chapter: {
      label: "章节节点",
      className: "border-[#a8c0da] bg-[#eef5fd] text-[#31567d]",
    },
    task: {
      label: "任务节点",
      className: "border-[#d3dde8] bg-white text-[#5f7892]",
    },
  }

  const config = labelByType[uiType ?? "task"]
  return <span className={cn("inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold", config.className)}>{config.label}</span>
}

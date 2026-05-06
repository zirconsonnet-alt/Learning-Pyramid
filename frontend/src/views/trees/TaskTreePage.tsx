import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Waypoints } from "lucide-react"
import { useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { listAggregationEvents, type AggregationEvent } from "@/ui/api/layers"
import { listLearningTaskNodes, type LearningTaskNode } from "@/ui/api/learningTaskNodes"
import { ContentEmptyState, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { formatLearningTaskNodeDisplayTitle, isDefaultAggregationTitle } from "@/views/learningTasks/displayTitle"
import { type LearningTaskTreeNode, LearningTaskTreeCanvas } from "@/views/trees/components/LearningTaskTreeCanvas"
import { TreeCanvasZoomControl } from "@/views/trees/components/TreeCanvasViewport"

type TaskTreeVisualType = "aggregation" | "chapter" | "task"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function deriveTaskNodeLayers(nodes: LearningTaskNode[], events: AggregationEvent[]) {
  const layerById: Record<string, number> = {}

  for (const node of nodes) {
    if (node.targetLayerIndex !== null) layerById[node.nodeId] = node.targetLayerIndex
    else if (node.kind === "leaf") layerById[node.nodeId] = 0
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
        const childIds = getTaskTreeChildIds(node)
        const childLayers = childIds.map((childId) => layerById[childId]).filter((value) => value !== undefined)
        if (childLayers.length === childIds.length && childLayers.length > 0) {
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

function getTaskTreeChildIds(node: LearningTaskNode) {
  if (node.kind !== "container") return []
  return node.children
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

export function TaskTreePage() {
  const { projectId } = useParams()
  const pid = projectId ?? ""
  const nav = useNavigate()
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null)
  const [zoomPercent, setZoomPercent] = useState(100)

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
    nodeById,
    nodeLayerById,
    rootIds,
  } = useMemo(() => {
    const rawNodes = q.data ?? []
    const events = eventsQ.data ?? []
    const rawNodeById: Record<string, LearningTaskNode> = {}
    const eventByParentId: Record<string, AggregationEvent> = {}
    const childIdsByParentId: Record<string, string[]> = {}

    for (const node of rawNodes) {
      rawNodeById[node.nodeId] = node
      if (node.parentId) {
        childIdsByParentId[node.parentId] ??= []
        childIdsByParentId[node.parentId].push(node.nodeId)
      }
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

      const total = getTaskTreeChildIds(node).reduce((sum, childId) => sum + countLeafDescendants(childId), 0)
      descendantCountById[nodeId] = total
      return total
    }

    for (const nodeId of Object.keys(rawNodeById)) countLeafDescendants(nodeId)

    const map: Record<string, LearningTaskTreeNode> = {}

    for (const node of rawNodes) {
      const layerIndex = layerById[node.nodeId] ?? 0
      const uiType = classifyTaskNode(node, eventByParentId[node.nodeId])
      const taskSpan = descendantCountById[node.nodeId] ?? 0
      const childIds =
        node.kind === "container"
          ? Array.from(new Set([...getTaskTreeChildIds(node), ...(childIdsByParentId[node.nodeId] ?? [])]))
          : []
      const childCount = node.kind === "container" ? childIds.length : 0

      map[node.nodeId] = {
        nodeId: node.nodeId,
        title: formatDisplayTitle(node.title, uiType, layerIndex),
        rawTitle: node.title,
        displayTitle: formatDisplayTitle(node.title, uiType, layerIndex),
        uiType,
        metaText:
          uiType === "aggregation"
              ? `${taskSpan} 个任务 · ${childCount} 个分支`
              : uiType === "chapter"
                ? `${taskSpan} 个任务`
                : undefined,
        kind: node.kind,
        children: node.kind === "container" ? childIds : undefined,
        learningTaskId: node.kind === "leaf" ? node.boundLearningTaskId : undefined,
      }
    }

    const roots = rawNodes
      .filter((node) => node.parentId === null)
      .map((node) => node.nodeId)
      .sort((a, b) => a.localeCompare(b))

    return {
      nodeById: map,
      nodeLayerById: layerById,
      rootIds: roots,
    }
  }, [eventsQ.data, q.data])

  const isLoading = q.isLoading || eventsQ.isLoading
  const hasData = (q.data ?? []).length > 0

  return (
    <section className="theme-card-main overflow-hidden">
      <div className="flex items-center justify-between gap-4 border-b border-border/60 px-6 py-5">
        <h2 className="text-base font-semibold text-foreground">结构视图</h2>
        <div className="rounded-full border border-white/70 bg-white/90 px-3 py-2 shadow-[0_18px_40px_-28px_rgba(15,23,42,0.45)] backdrop-blur">
          <TreeCanvasZoomControl zoomPercent={zoomPercent} onZoomPercentChange={setZoomPercent} />
        </div>
      </div>

      <div className="theme-canvas min-h-[36rem] p-4 md:p-5">
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
            zoomPercent={zoomPercent}
            focusNodeId={hoveredNodeId}
            onNodeHover={setHoveredNodeId}
            onNodeSelect={(node) => nav(`/p/${pid}/learning-task-nodes/${node.nodeId}`)}
          />
        ) : null}
      </div>
    </section>
  )
}

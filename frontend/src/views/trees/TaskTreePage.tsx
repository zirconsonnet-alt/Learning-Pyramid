import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Waypoints } from "lucide-react"
import { useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { listAggregationEvents, type AggregationEvent } from "@/ui/api/layers"
import { listLearningTaskNodes, type LearningTaskNode } from "@/ui/api/learningTaskNodes"
import { ContentEmptyState, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { formatLearningTaskNodeDisplayTitle, isDefaultAggregationTitle } from "@/views/learningTasks/displayTitle"
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
    nodeById,
    nodeLayerById,
    rootIds,
  } = useMemo(() => {
    const rawNodes = q.data ?? []
    const events = eventsQ.data ?? []
    const rawNodeById: Record<string, LearningTaskNode> = {}
    const eventByParentId: Record<string, AggregationEvent> = {}

    for (const node of rawNodes) {
      rawNodeById[node.nodeId] = node
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
      nodeById: map,
      nodeLayerById: layerById,
      rootIds: roots,
    }
  }, [eventsQ.data, q.data])

  const effectiveSelectedNodeId = selectedNodeId && nodeById[selectedNodeId] ? selectedNodeId : defaultSelectedId
  const selectedNode = effectiveSelectedNodeId ? nodeById[effectiveSelectedNodeId] : null
  const canvasFocusNodeId = hoveredNodeId ?? effectiveSelectedNodeId
  const isLoading = q.isLoading || eventsQ.isLoading
  const hasData = (q.data ?? []).length > 0

  return (
    <div className="space-y-5">
      <section className="theme-card p-5 md:p-6">
        {selectedNode ? (
          <div className="space-y-4">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div className="space-y-2">
                <h1 className="text-[1.7rem] font-semibold tracking-tight text-foreground">
                  {selectedNode.displayTitle ?? selectedNode.title}
                </h1>
              </div>

              <div className="flex flex-wrap gap-3">
                <Button variant="outline" onClick={() => nav(`/p/${pid}/learning-task-nodes/${selectedNode.nodeId}`)}>
                  查看节点详情
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <ContentEmptyState
            title="先选择一个任务节点"
            message="从结构图里点击任意任务、章节或聚合节点，这里会显示当前节点的简要信息。"
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

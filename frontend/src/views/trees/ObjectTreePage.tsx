import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { FolderTree } from "lucide-react"
import { useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { listInstances, type Instance } from "@/ui/api/instances"
import { listLearningObjectNodes, type LearningObjectNode } from "@/ui/api/learningObjects"
import { ContentEmptyState, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import {
  LearningObjectTreeCanvas,
  type LearningObjectTreeCanvasNode,
  type ObjectTreeVisualType,
} from "@/views/trees/components/LearningObjectTreeCanvas"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function formatObjectTitle(node: LearningObjectNode, depth: number) {
  const rawTitle = node.title.trim()
  if (!rawTitle && node.kind === "leaf") return "未命名材料"
  if (!rawTitle && node.kind === "container") return depth === 0 ? "学习对象根" : "未命名分组"
  if (depth === 0 && rawTitle === "Files") return "学习对象根"
  return rawTitle
}

function classifyObjectNode(node: LearningObjectNode, depth: number): ObjectTreeVisualType {
  if (node.kind === "leaf") return "material"
  if (depth === 0) return "root"
  return "group"
}

export function ObjectTreePage() {
  const { projectId } = useParams()
  const pid = projectId ?? ""
  const nav = useNavigate()
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null)

  const nodesQ = useQuery({
    queryKey: ["learningObjectNodes", pid],
    queryFn: () => listLearningObjectNodes(pid),
    enabled: !!pid,
  })

  const instancesQ = useQuery({
    queryKey: ["instances", pid],
    queryFn: () => listInstances(pid),
    enabled: !!pid,
  })

  const {
    defaultSelectedId,
    depthById,
    nodeById,
    rootIds,
  } = useMemo(() => {
    const rawNodes = nodesQ.data ?? []
    const instancesById: Record<string, Instance> = {}
    for (const instance of instancesQ.data ?? []) instancesById[instance.instanceId] = instance

    const rawNodeById: Record<string, LearningObjectNode> = {}
    const roots = rawNodes
      .filter((node) => node.parentId === null)
      .map((node) => node.nodeId)
      .sort((a, b) => a.localeCompare(b))

    for (const node of rawNodes) {
      rawNodeById[node.nodeId] = node
    }

    const depthMap: Record<string, number> = {}
    function getDepth(nodeId: string): number {
      const cached = depthMap[nodeId]
      if (cached !== undefined) return cached

      const node = rawNodeById[nodeId]
      if (!node || !node.parentId) {
        depthMap[nodeId] = 0
        return 0
      }

      const depth = getDepth(node.parentId) + 1
      depthMap[nodeId] = depth
      return depth
    }

    for (const node of rawNodes) getDepth(node.nodeId)

    const descendantCountById: Record<string, number> = {}
    function countMaterialDescendants(nodeId: string): number {
      const cached = descendantCountById[nodeId]
      if (cached !== undefined) return cached

      const node = rawNodeById[nodeId]
      if (!node) return 0
      if (node.kind === "leaf") {
        descendantCountById[nodeId] = 1
        return 1
      }

      const total = (node.children ?? []).reduce((sum, childId) => sum + countMaterialDescendants(childId), 0)
      descendantCountById[nodeId] = total
      return total
    }

    for (const nodeId of Object.keys(rawNodeById)) countMaterialDescendants(nodeId)

    const map: Record<string, LearningObjectTreeCanvasNode> = {}

    for (const node of rawNodes) {
      const depth = depthMap[node.nodeId] ?? 0
      const uiType = classifyObjectNode(node, depth)
      const displayTitle = formatObjectTitle(node, depth)
      const rawTitle = node.title.trim()
      const instance = node.kind === "leaf" ? instancesById[node.instanceId] : undefined
      const childCount = node.kind === "container" ? (node.children?.length ?? 0) : 0
      const materialSpan = descendantCountById[node.nodeId] ?? 0

      map[node.nodeId] = {
        nodeId: node.nodeId,
        title: node.title,
        rawTitle,
        displayTitle,
        uiType,
        metaText:
          node.kind === "container"
            ? `${materialSpan} 份材料 · ${childCount} 个子节点`
            : instance?.materialDisplayName || instance?.materialId || "已绑定学习材料",
        kind: node.kind,
        children: node.kind === "container" ? node.children : undefined,
        instanceId: node.kind === "leaf" ? node.instanceId : undefined,
      }
    }

    const defaultNodeId = roots[0] ?? Object.keys(map).sort((a, b) => a.localeCompare(b))[0] ?? null

    return {
      defaultSelectedId: defaultNodeId,
      depthById: depthMap,
      nodeById: map,
      rootIds: roots,
    }
  }, [instancesQ.data, nodesQ.data])

  const effectiveSelectedNodeId = selectedNodeId && nodeById[selectedNodeId] ? selectedNodeId : defaultSelectedId
  const selectedNode = effectiveSelectedNodeId ? nodeById[effectiveSelectedNodeId] : null

  const canvasFocusNodeId = hoveredNodeId ?? effectiveSelectedNodeId
  const isLoading = nodesQ.isLoading
  const hasData = (nodesQ.data ?? []).length > 0

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
                {selectedNode.kind === "leaf" ? <p className="text-sm text-[#647b93]">{selectedNode.metaText}</p> : null}
              </div>

              <div className="flex flex-wrap gap-3">
                <Button variant="outline" onClick={() => nav(`/p/${pid}/learning-object-nodes/${selectedNode.nodeId}`)}>
                  查看节点详情
                </Button>
              </div>
            </div>

            {instancesQ.error ? <ErrorNotice title="实例详情加载失败" message={formatApiError(instancesQ.error)} /> : null}
          </div>
        ) : (
          <ContentEmptyState
            title="先选择一个对象节点"
            message="从结构图里点击任意目录或材料节点，这里会显示当前节点的简要信息。"
          />
        )}
      </section>

      <section className="theme-card-main overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-border/60 px-6 py-5 md:flex-row md:items-center md:justify-between">
          <h2 className="text-base font-semibold text-foreground">结构视图</h2>
          <div className="flex flex-wrap gap-2 text-xs text-[#688099]">
            <span className="theme-meta">目录在上，材料在下</span>
            <span className="theme-meta">标题经过最小语义清洗</span>
          </div>
        </div>

        <div className="theme-canvas min-h-[36rem] overflow-auto p-4 md:p-5">
          {isLoading ? <LoadingNotice title="正在加载学习对象树" message="正在整理目录结构、材料节点和层级布局。" /> : null}
          {nodesQ.error ? <ErrorNotice title="学习对象树加载失败" message={formatApiError(nodesQ.error)} /> : null}
          {!isLoading && !nodesQ.error && !hasData ? (
            <ContentEmptyState
              icon={FolderTree}
              title="当前项目还没有学习对象树"
              message="先在项目设置里导入内容目录或补齐当前素材接入方式；完成后对象节点会显示在这里。"
            />
          ) : null}
          {!isLoading && !nodesQ.error && hasData ? (
            <LearningObjectTreeCanvas
              rootIds={rootIds}
              nodeById={nodeById}
              nodeDepthById={depthById}
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

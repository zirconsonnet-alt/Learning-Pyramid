import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { FolderTree } from "lucide-react"
import { useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { listInstances, type Instance } from "@/ui/api/instances"
import { listLearningObjectNodes, type LearningObjectNode } from "@/ui/api/learningObjects"
import type { ProjectScope } from "@/ui/api/projectScope"
import { ContentEmptyState, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import {
  isSyntheticFilesContainer,
  sortLearningObjectNodeIdsForDisplay,
} from "@/ui/learningObjectDisplayOrder"
import { buildScopedProjectPath } from "@/ui/projectPaths"
import { projectTypeRequiresLearningObjectTree } from "@/ui/projectTypes"
import { useProjectConfig } from "@/ui/queries/workbench"
import {
  LearningObjectTreeCanvas,
  type LearningObjectTreeCanvasNode,
  type ObjectTreeVisualType,
} from "@/views/trees/components/LearningObjectTreeCanvas"
import { TreeCanvasZoomControl } from "@/views/trees/components/TreeCanvasViewport"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function formatObjectTitle(node: LearningObjectNode, depth: number) {
  const rawTitle = node.title.trim()
  if (!rawTitle && node.kind === "leaf") return "未命名内容"
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
  const { subjectId = "", projectId } = useParams()
  const pid = projectId ?? ""
  const projectScope: ProjectScope | null = subjectId && pid ? { subjectId, projectId: pid } : null
  const nav = useNavigate()
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null)
  const [zoomPercent, setZoomPercent] = useState(100)
  const projectConfigQ = useProjectConfig(projectScope)
  const projectType = projectConfigQ.data?.projectType ?? "COURSE"
  const usesLearningObjectTree = projectTypeRequiresLearningObjectTree(projectType)

  const nodesQ = useQuery({
    queryKey: ["learningObjectNodes", subjectId, pid],
    queryFn: () => listLearningObjectNodes(projectScope as ProjectScope),
    enabled: !!projectScope,
  })

  const instancesQ = useQuery({
    queryKey: ["instances", subjectId, pid],
    queryFn: () => listInstances(projectScope as ProjectScope),
    enabled: !!projectScope,
  })

  const {
    depthById,
    nodeById,
    rootIds,
  } = useMemo(() => {
    const sourceNodes = nodesQ.data ?? []
    const instancesById: Record<string, Instance> = {}
    for (const instance of instancesQ.data ?? []) instancesById[instance.instanceId] = instance

    const syntheticFilesNodes = sourceNodes.filter((node) => isSyntheticFilesContainer(node))
    const syntheticFilesIds = new Set(syntheticFilesNodes.map((node) => node.nodeId))
    const syntheticFilesById = Object.fromEntries(syntheticFilesNodes.map((node) => [node.nodeId, node])) as Record<
      string,
      LearningObjectNode
    >
    const normalizedNodes = sourceNodes
      .filter((node) => !syntheticFilesIds.has(node.nodeId))
      .map((node) => {
        if (node.kind === "container") {
          return {
            ...node,
            children: node.children.flatMap((childId) => {
              if (!syntheticFilesIds.has(childId)) return [childId]
              const syntheticNode = syntheticFilesById[childId]
              return syntheticNode?.kind === "container" ? syntheticNode.children : []
            }),
          }
        }
        if (node.parentId && syntheticFilesIds.has(node.parentId)) {
          const syntheticParent = syntheticFilesById[node.parentId]
          return {
            ...node,
            parentId: syntheticParent?.parentId ?? null,
          }
        }
        return node
      })

    const rawNodeById: Record<string, LearningObjectNode> = {}
    const childIdsByParentId: Record<string, string[]> = {}

    for (const node of normalizedNodes) {
      rawNodeById[node.nodeId] = node
      if (node.parentId) {
        childIdsByParentId[node.parentId] ??= []
        childIdsByParentId[node.parentId].push(node.nodeId)
      }
    }

    for (const node of normalizedNodes) {
      if (node.kind !== "container") continue
      rawNodeById[node.nodeId] = {
        ...node,
        children: sortLearningObjectNodeIdsForDisplay(
          Array.from(new Set([...(node.children ?? []), ...(childIdsByParentId[node.nodeId] ?? [])])),
          rawNodeById,
        ),
      }
    }

    const roots = sortLearningObjectNodeIdsForDisplay(
      normalizedNodes.filter((node) => node.parentId === null).map((node) => node.nodeId),
      rawNodeById,
    )

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

    for (const node of normalizedNodes) getDepth(node.nodeId)

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

    for (const nodeId of Object.keys(rawNodeById)) {
      const node = rawNodeById[nodeId]
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
            ? `${materialSpan} 份内容 · ${childCount} 个子节点`
            : instance?.materialDisplayName || instance?.materialId || "已绑定内容实例",
        kind: node.kind,
        children: node.kind === "container" ? node.children : undefined,
        instanceId: node.kind === "leaf" ? node.instanceId : undefined,
      }
    }

    return {
      depthById: depthMap,
      nodeById: map,
      rootIds: roots,
    }
  }, [instancesQ.data, nodesQ.data])

  const isLoading = nodesQ.isLoading
  const hasData = (nodesQ.data ?? []).length > 0

  return (
    <section className="theme-card-main overflow-hidden">
      <div className="flex items-center justify-between gap-4 border-b border-border/60 px-6 py-5">
        <h2 className="text-base font-semibold text-foreground">结构视图</h2>
        <div className="rounded-full border border-white/70 bg-white/90 px-3 py-2 shadow-[0_18px_40px_-28px_rgba(15,23,42,0.45)] backdrop-blur">
          <TreeCanvasZoomControl zoomPercent={zoomPercent} onZoomPercentChange={setZoomPercent} />
        </div>
      </div>

      <div className="theme-canvas min-h-[36rem] p-4 md:p-5">
        {isLoading ? <LoadingNotice title="正在加载学习对象树" message="正在整理目录结构、内容节点和层级布局。" /> : null}
        {projectConfigQ.error ? <ErrorNotice title="项目配置加载失败" message={formatApiError(projectConfigQ.error)} /> : null}
        {nodesQ.error ? <ErrorNotice title="学习对象树加载失败" message={formatApiError(nodesQ.error)} /> : null}
        {instancesQ.error ? <ErrorNotice title="实例详情加载失败" message={formatApiError(instancesQ.error)} /> : null}
        {!projectConfigQ.isLoading && !projectConfigQ.error && !usesLearningObjectTree ? (
          <ContentEmptyState
            icon={FolderTree}
            title="当前项目不使用学习对象树"
            message="零散知识点项目不会维护对象树结构。你可以回到工作台直接录入项目级复述点。"
          />
        ) : null}
        {!isLoading && !projectConfigQ.error && usesLearningObjectTree && !nodesQ.error && !hasData ? (
          <ContentEmptyState
            icon={FolderTree}
            title="当前项目还没有学习对象树"
            message="先在项目设置里导入内容目录或补齐当前素材接入方式；完成后对象节点会显示在这里。"
          />
        ) : null}
        {!isLoading && !projectConfigQ.error && usesLearningObjectTree && !nodesQ.error && hasData ? (
          <LearningObjectTreeCanvas
            rootIds={rootIds}
            nodeById={nodeById}
            nodeDepthById={depthById}
            zoomPercent={zoomPercent}
            focusNodeId={hoveredNodeId}
            onNodeHover={setHoveredNodeId}
            onNodeSelect={(node) => nav(buildScopedProjectPath(subjectId, pid, `/learning-object-nodes/${node.nodeId}`))}
          />
        ) : null}
      </div>
    </section>
  )
}

import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { ChevronRight, FolderTree } from "lucide-react"
import { useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { listInstances, type Instance } from "@/ui/api/instances"
import { listLearningObjectNodes, listRecallPointsByLearningObjectNode, type LearningObjectNode } from "@/ui/api/learningObjects"
import { ContentEmptyState, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { cn } from "@/ui/utils"
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
    descendantMaterialCountById,
    depthById,
    groupCount,
    materialCount,
    maxDepth,
    nodeById,
    parentById,
    rootCount,
    rootIds,
  } = useMemo(() => {
    const rawNodes = nodesQ.data ?? []
    const instancesById: Record<string, Instance> = {}
    for (const instance of instancesQ.data ?? []) instancesById[instance.instanceId] = instance

    const rawNodeById: Record<string, LearningObjectNode> = {}
    const directParentById: Record<string, string | null> = {}
    const roots = rawNodes
      .filter((node) => node.parentId === null)
      .map((node) => node.nodeId)
      .sort((a, b) => a.localeCompare(b))

    for (const node of rawNodes) {
      rawNodeById[node.nodeId] = node
      directParentById[node.nodeId] = node.parentId
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

    let groups = 0
    let materials = 0
    let highestDepth = 0
    const map: Record<string, LearningObjectTreeCanvasNode> = {}

    for (const node of rawNodes) {
      const depth = depthMap[node.nodeId] ?? 0
      const uiType = classifyObjectNode(node, depth)
      const displayTitle = formatObjectTitle(node, depth)
      const rawTitle = node.title.trim()
      const instance = node.kind === "leaf" ? instancesById[node.instanceId] : undefined
      const childCount = node.kind === "container" ? (node.children?.length ?? 0) : 0
      const materialSpan = descendantCountById[node.nodeId] ?? 0

      if (node.kind === "container") groups += 1
      if (node.kind === "leaf") materials += 1
      highestDepth = Math.max(highestDepth, depth)

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
      descendantMaterialCountById: descendantCountById,
      depthById: depthMap,
      groupCount: groups,
      materialCount: materials,
      maxDepth: highestDepth,
      nodeById: map,
      parentById: directParentById,
      rootCount: roots.length,
      rootIds: roots,
    }
  }, [instancesQ.data, nodesQ.data])

  const effectiveSelectedNodeId = selectedNodeId && nodeById[selectedNodeId] ? selectedNodeId : defaultSelectedId
  const selectedNode = effectiveSelectedNodeId ? nodeById[effectiveSelectedNodeId] : null
  const selectedInstance =
    !selectedNode?.instanceId ? null : (instancesQ.data ?? []).find((instance) => instance.instanceId === selectedNode.instanceId) ?? null

  const selectedRecallPointsQ = useQuery({
    queryKey: ["recallPointsByObjectNode", pid, effectiveSelectedNodeId],
    queryFn: () => listRecallPointsByLearningObjectNode(pid, effectiveSelectedNodeId ?? ""),
    enabled: !!pid && !!effectiveSelectedNodeId,
  })

  const pathNodeIds = useMemo(
    () => getPathNodeIds(effectiveSelectedNodeId, parentById),
    [effectiveSelectedNodeId, parentById],
  )

  const selectedParent = selectedNode ? (parentById[selectedNode.nodeId] ? nodeById[parentById[selectedNode.nodeId] ?? ""] : null) : null
  const selectedChildren =
    selectedNode?.kind === "container"
      ? (selectedNode.children ?? []).map((childId) => nodeById[childId]).filter((node): node is LearningObjectTreeCanvasNode => !!node)
      : []

  const canvasFocusNodeId = hoveredNodeId ?? effectiveSelectedNodeId
  const isLoading = nodesQ.isLoading
  const hasData = (nodesQ.data ?? []).length > 0

  return (
    <div className="space-y-5">
      <section className="theme-card-main overflow-hidden">
        <div className="flex flex-col gap-5 p-6 md:p-7">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2">
                <span className="theme-meta-strong">对象树工作台</span>
                <span className="theme-meta">目录语义视图</span>
              </div>
              <h1 className="text-[1.9rem] font-semibold tracking-tight text-foreground">学习对象树</h1>
            </div>

          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <OverviewMetric label="材料节点" value={String(materialCount)} caption="叶子材料" />
            <OverviewMetric label="目录节点" value={String(groupCount)} caption="根与分组容器" />
            <OverviewMetric label="根节点" value={String(rootCount)} caption="顶层入口" />
            <OverviewMetric label="结构深度" value={`D0-D${maxDepth}`} caption={`${maxDepth + 1} 层目录`} />
          </div>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section className="theme-card-main overflow-hidden">
          <div className="flex flex-col gap-3 border-b border-border/60 px-6 py-5 md:flex-row md:items-center md:justify-between">
            <h2 className="text-base font-semibold text-foreground">结构视图</h2>
            <div className="flex flex-wrap gap-2 text-xs text-[#688099]">
              <span className="theme-meta">目录在上，材料在下</span>
              <span className="theme-meta">标题经过最小语义清洗</span>
            </div>
          </div>

          <div className="theme-canvas min-h-[32rem] overflow-auto p-4 md:p-5">
            {isLoading ? <LoadingNotice title="正在加载学习对象树" message="正在整理目录结构、材料节点和层级布局。" /> : null}
            {nodesQ.error ? <ErrorNotice title="学习对象树加载失败" message={formatApiError(nodesQ.error)} /> : null}
            {!isLoading && !nodesQ.error && !hasData ? (
              <ContentEmptyState
                icon={FolderTree}
                title="当前项目还没有学习对象树"
                message="先在项目设置里同步素材目录，或通过桌面连接器接入材料；完成后对象节点会显示在这里。"
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

        <aside className="space-y-4">
          <section className="theme-card p-5">
            {selectedNode ? (
              <div className="space-y-5">
                <div className="space-y-3 border-b border-border/60 pb-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <ObjectTypeBadge uiType={selectedNode.uiType} />
                    <span className="inline-flex items-center rounded-full border border-[#d8e3ee] bg-[#f6f9fc] px-2.5 py-1 text-xs font-semibold text-[#5f7790]">
                      D{depthById[selectedNode.nodeId] ?? 0}
                    </span>
                    {selectedInstance ? (
                      <span
                        className={cn(
                          "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold",
                          selectedInstance.presence === "MISSING"
                            ? "border-amber-200 bg-amber-50 text-amber-700"
                            : "border-emerald-200 bg-emerald-50 text-emerald-700",
                        )}
                      >
                        {selectedInstance.presence === "MISSING" ? "材料缺失" : "材料可达"}
                      </span>
                    ) : null}
                  </div>
                  <div>
                    <h3 className="text-xl font-semibold tracking-tight text-foreground">{selectedNode.displayTitle ?? selectedNode.title}</h3>
                    <p className="mt-2 text-sm text-[#647b93]">{selectedNode.metaText}</p>
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
                  <DetailMetric label="覆盖材料数" value={`${descendantMaterialCountById[selectedNode.nodeId] ?? 0}`} />
                  <DetailMetric
                    label={selectedNode.kind === "container" ? "直接子节点" : "材料状态"}
                    value={
                      selectedNode.kind === "container"
                        ? `${selectedChildren.length}`
                        : selectedInstance?.presence === "MISSING"
                          ? "缺失"
                          : "正常"
                    }
                  />
                  <DetailMetric label="路径深度" value={`D${depthById[selectedNode.nodeId] ?? 0}`} />
                  <DetailMetric
                    label="复述点数"
                    value={selectedRecallPointsQ.data ? `${selectedRecallPointsQ.data.length}` : selectedRecallPointsQ.isLoading ? "..." : "-"}
                  />
                </div>

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
                ) : null}

                {selectedChildren.length > 0 ? (
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-[#688099]">下级节点</div>
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
                  </div>
                ) : null}

                {instancesQ.error ? <ErrorNotice title="实例详情加载失败" message={formatApiError(instancesQ.error)} /> : null}
                {selectedRecallPointsQ.error ? <ErrorNotice title="复述点统计加载失败" message={formatApiError(selectedRecallPointsQ.error)} /> : null}

                <div className="pt-1">
                  <Button variant="outline" onClick={() => nav(`/p/${pid}/learning-object-nodes/${selectedNode.nodeId}`)}>
                    查看节点详情
                  </Button>
                </div>
              </div>
            ) : (
              <ContentEmptyState
                title="先选择一个对象节点"
                message="从左侧结构图里点击任意目录或材料节点，这里就会显示它的路径、状态和复述点摘要。"
              />
            )}
          </section>
        </aside>
      </div>
    </div>
  )
}

function OverviewMetric({ caption, label, value }: { caption: string; label: string; value: string }) {
  return (
    <div className="theme-status-surface px-4 py-3">
      <div className="text-xs font-semibold uppercase tracking-[0.18em] text-[#69819a]">{label}</div>
      <div className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{value}</div>
      <div className="mt-1 text-xs text-[#7a91a9]">{caption}</div>
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

function ObjectTypeBadge({ uiType }: { uiType?: ObjectTreeVisualType }) {
  const labelByType: Record<ObjectTreeVisualType, { className: string; label: string }> = {
    root: {
      label: "根目录",
      className: "border-[#b9cee3] bg-[#f3f8ff] text-[#2f547b]",
    },
    group: {
      label: "分组节点",
      className: "border-[#a8c0da] bg-[#eef5fd] text-[#31567d]",
    },
    material: {
      label: "材料节点",
      className: "border-[#d3dde8] bg-white text-[#5f7892]",
    },
  }

  const config = labelByType[uiType ?? "material"]
  return <span className={cn("inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold", config.className)}>{config.label}</span>
}

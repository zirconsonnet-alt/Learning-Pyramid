import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { ChevronRight } from "lucide-react"
import { Link } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { listLearningObjectNodes, type LearningObjectNode } from "@/ui/api/learningObjects"
import { Button } from "@/ui/components/ui/button"
import {
  isSyntheticFilesContainer,
  sortLearningObjectNodeIdsForDisplay,
} from "@/ui/learningObjectDisplayOrder"
import { scanProjectDirectoryMedia, useProjectDirectoryBinding } from "@/ui/localMedia/projectDirectory"
import { useImportLearningObjectsFromBrowser } from "@/ui/queries/workbench"
import { showErrorFeedback, showInfoFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { cn } from "@/ui/utils"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function splitLeafDisplayTitle(node: LearningObjectNode) {
  if (node.kind !== "leaf") {
    return { main: node.title, suffix: null as string | null }
  }

  const title = node.title.trim()
  const fallbackFileName = node.relativePath?.split("/").pop()?.trim() ?? ""
  const dotIndex = fallbackFileName.lastIndexOf(".")
  if (dotIndex <= 0 || dotIndex >= fallbackFileName.length - 1) {
    return { main: title || fallbackFileName || "未命名材料", suffix: null as string | null }
  }

  const suffix = fallbackFileName.slice(dotIndex)
  if (title && title.toLowerCase().endsWith(suffix.toLowerCase())) {
    const main = title.slice(0, title.length - suffix.length).trim()
    return { main: main || title, suffix }
  }

  return { main: title || fallbackFileName.slice(0, dotIndex), suffix }
}

function TreeNode({
  nodeId,
  depth,
  expanded,
  toggle,
  nodeById,
  selectedInstanceId,
  onSelectInstance,
}: {
  nodeId: string
  depth: number
  expanded: Set<string>
  toggle: (nodeId: string) => void
  nodeById: Record<string, LearningObjectNode>
  selectedInstanceId: string | null
  onSelectInstance: (instanceId: string) => void
}) {
  const data = nodeById[nodeId]
  if (!data) return null

  if (data.kind === "container") {
    if (isSyntheticFilesContainer(data)) {
      return (
        <>
          {data.children.map((childId) => (
            <TreeNode
              key={childId}
              nodeId={childId}
              depth={depth}
              expanded={expanded}
              toggle={toggle}
              nodeById={nodeById}
              selectedInstanceId={selectedInstanceId}
              onSelectInstance={onSelectInstance}
            />
          ))}
        </>
      )
    }

    const isOpen = expanded.has(nodeId)
    return (
      <div className="space-y-1">
        <button
          type="button"
          className={cn(
            "group flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-sm transition-colors",
            isOpen ? "bg-[#f7f9fc] text-[#20354b]" : "text-[#4a5d73] hover:bg-[#f7f9fc] hover:text-[#20354b]",
          )}
          style={{ paddingLeft: depth * 14 + 10 }}
          onClick={() => toggle(nodeId)}
          aria-expanded={isOpen}
        >
          <span
            className={cn(
              "flex h-4 w-4 shrink-0 items-center justify-center rounded-md text-[#9aa7b4] transition-colors",
              isOpen && "bg-white text-[#6b7d90]",
            )}
          >
            <ChevronRight className={cn("h-3.5 w-3.5 transition-transform", isOpen && "rotate-90")} />
          </span>
          <span className="truncate font-medium">{data.title}</span>
        </button>
        {isOpen ? (
          <div className="ml-3 space-y-1 border-l border-[#edf2f7] pl-3">
            {data.children.map((childId) => (
              <TreeNode
                key={childId}
                nodeId={childId}
                depth={depth + 1}
                expanded={expanded}
                toggle={toggle}
                nodeById={nodeById}
                selectedInstanceId={selectedInstanceId}
                onSelectInstance={onSelectInstance}
              />
            ))}
          </div>
        ) : null}
      </div>
    )
  }

  const isSelected = selectedInstanceId === data.instanceId
  const { main, suffix } = splitLeafDisplayTitle(data)

  return (
    <button
      type="button"
      className={cn(
        "group relative flex w-full items-center gap-3 overflow-hidden rounded-xl px-3 py-2.5 text-left transition-colors",
        isSelected ? "bg-[#eef5ff] text-[#153f74]" : "text-[#33475b] hover:bg-[#f6f8fb]",
      )}
      style={{ paddingLeft: depth * 14 + 10 }}
      onClick={() => onSelectInstance(data.instanceId)}
      aria-current={isSelected ? "true" : undefined}
    >
      <span className={cn("absolute inset-y-1.5 left-0 w-[3px] rounded-r-full", isSelected ? "bg-[#3b82f6]" : "bg-transparent")} />
      <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", isSelected ? "bg-[#60a5fa]" : "bg-[#c9d3de]")} />
      <span className="min-w-0 flex items-baseline gap-2">
        <span className={cn("truncate text-sm font-medium", isSelected ? "text-[#153f74]" : "text-[#2f4358]")}>{main}</span>
        {suffix ? (
          <span className={cn("shrink-0 text-[11px] font-medium tracking-[0.04em]", isSelected ? "text-[#7aa7e8]" : "text-[#9aa7b5]")}>
            {suffix}
          </span>
        ) : null}
      </span>
    </button>
  )
}

export function LearningObjectTree({
  projectId,
  selectedInstanceId,
  onSelectInstance,
}: {
  projectId: string
  selectedInstanceId: string | null
  onSelectInstance: (instanceId: string) => void
}) {
  const directoryBinding = useProjectDirectoryBinding(projectId)
  const importLearningObjectsM = useImportLearningObjectsFromBrowser(projectId)
  const q = useQuery({
    queryKey: ["learningObjectNodes", projectId],
    queryFn: () => listLearningObjectNodes(projectId),
    enabled: !!projectId,
  })

  const { nodeById, rootIds, containerIds } = useMemo(() => {
    const rawMap: Record<string, LearningObjectNode> = {}
    const roots: string[] = []
    const containers: string[] = []

    for (const node of q.data ?? []) {
      rawMap[node.nodeId] = node
      if (node.parentId === null) roots.push(node.nodeId)
      if (node.kind === "container") containers.push(node.nodeId)
    }

    const map: Record<string, LearningObjectNode> = {}
    for (const node of q.data ?? []) {
      map[node.nodeId] =
        node.kind === "container"
          ? {
              ...node,
              children: sortLearningObjectNodeIdsForDisplay(node.children, rawMap),
            }
          : node
    }

    return {
      nodeById: map,
      rootIds: sortLearningObjectNodeIdsForDisplay(roots, map),
      containerIds: sortLearningObjectNodeIdsForDisplay(containers, map),
    }
  }, [q.data])

  const [expanded, setExpanded] = useState<Set<string> | null>(null)
  const effectiveExpanded = expanded ?? new Set(containerIds)

  function toggle(nodeId: string) {
    setExpanded((prev) => {
      const next = new Set(prev ?? containerIds)
      if (next.has(nodeId)) next.delete(nodeId)
      else next.add(nodeId)
      return next
    })
  }

  async function onImportHere() {
    try {
      const scan = await scanProjectDirectoryMedia(projectId)
      const result = await importLearningObjectsM.mutateAsync(scan)
      if (result.unchanged) {
        showInfoFeedback("目录已是最新", "当前已授权目录里的媒体文件没有变化。")
        return
      }
      showSuccessFeedback(
        "内容目录已导入",
        `已导入 ${scan.relativeFilePaths.length} 个媒体文件，新增 ${result.created_instances_count} 个实例。`,
      )
    } catch (err) {
      showErrorFeedback("导入本地目录失败", formatApiError(err))
    }
  }

  if (q.isLoading) {
    return <LoadingNotice title="正在加载内容目录" message="正在读取这个项目的学习对象树和材料层级。" />
  }

  if (q.error) {
    return <ErrorNotice title="内容目录加载失败" message={formatApiError(q.error)} />
  }

  if (rootIds.length === 0) {
    const canImportHere = directoryBinding.permission === "granted" && !directoryBinding.loading
    return (
      <div className="space-y-3 rounded-[1rem] border border-dashed border-border/70 bg-white p-4">
        <div className="space-y-1">
          <p className="text-sm font-medium text-foreground">当前还没有学习对象</p>
          <p className="text-sm text-muted-foreground">
            {canImportHere
              ? "当前目录已经授权，可以直接在这里导入内容目录。"
              : "请先到项目设置里绑定本地目录并导入内容目录，完成后就能在这里看到视频和目录树。"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {canImportHere ? (
            <Button size="sm" className="rounded-full" onClick={() => void onImportHere()} disabled={importLearningObjectsM.isPending}>
              {importLearningObjectsM.isPending ? "导入中..." : "立即导入"}
            </Button>
          ) : null}
          <Button asChild size="sm" variant={canImportHere ? "outline" : "default"} className="rounded-full">
            <Link to={`/p/${projectId}/settings`}>{canImportHere ? "前往项目设置" : "前往项目设置"}</Link>
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-1.5">
      {rootIds.map((rootId) => (
        <TreeNode
          key={rootId}
          nodeId={rootId}
          depth={0}
          expanded={effectiveExpanded}
          toggle={toggle}
          nodeById={nodeById}
          selectedInstanceId={selectedInstanceId}
          onSelectInstance={onSelectInstance}
        />
      ))}
    </div>
  )
}

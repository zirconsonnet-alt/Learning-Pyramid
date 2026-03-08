import { useEffect, useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"

import { ApiError } from "@/ui/api/http"
import { listLearningObjectNodes, type LearningObjectNode } from "@/ui/api/learningObjects"
import { cn } from "@/ui/utils"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
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
    const firstChild = data.children[0] ? nodeById[data.children[0]] : undefined
    const isSyntheticFilesContainer = data.title === "Files" && (data.children.length === 0 || firstChild?.kind !== "container")
    if (isSyntheticFilesContainer) {
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
      <div>
        <div
          className="flex cursor-pointer items-center gap-2 rounded-xl px-3 py-2 text-sm text-[#486284] transition-colors hover:bg-accent/70 hover:text-foreground"
          style={{ paddingLeft: depth * 14 }}
          onClick={() => toggle(nodeId)}
          role="button"
          tabIndex={0}
        >
          <span className="w-4 text-center text-muted-foreground">{isOpen ? "▾" : "▸"}</span>
          <span className="truncate">{data.title}</span>
        </div>
        {isOpen ? (
          <div className="space-y-1">
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

  return (
    <div
      className={cn(
        "flex cursor-pointer items-center gap-2 rounded-xl px-3 py-2 text-sm transition-colors hover:bg-accent/70",
        selectedInstanceId === data.instanceId ? "bg-accent text-foreground shadow-[0_10px_24px_-18px_rgba(30,58,95,0.42)]" : "text-[#344968]",
      )}
      style={{ paddingLeft: depth * 14 }}
      onClick={() => onSelectInstance(data.instanceId)}
      role="button"
      tabIndex={0}
    >
      <span className="w-4 text-center text-muted-foreground">•</span>
      <span className="truncate">{data.title}</span>
    </div>
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
  const q = useQuery({
    queryKey: ["learningObjectNodes", projectId],
    queryFn: () => listLearningObjectNodes(projectId),
    enabled: !!projectId,
  })

  const { nodeById, rootIds, containerIds } = useMemo(() => {
    const map: Record<string, LearningObjectNode> = {}
    const roots: string[] = []
    const containers: string[] = []

    for (const node of q.data ?? []) {
      map[node.nodeId] = node
      if (node.parentId === null) roots.push(node.nodeId)
      if (node.kind === "container") containers.push(node.nodeId)
    }

    return { nodeById: map, rootIds: roots, containerIds: containers }
  }, [q.data])

  const [expanded, setExpanded] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (containerIds.length === 0) return
    setExpanded((prev) => (prev.size === 0 ? new Set(containerIds) : prev))
  }, [containerIds])

  function toggle(nodeId: string) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(nodeId)) next.delete(nodeId)
      else next.add(nodeId)
      return next
    })
  }

  if (q.isLoading) {
    return <p className="text-sm text-muted-foreground">加载学习对象树中...</p>
  }

  if (q.error) {
    return <p className="text-sm text-destructive">{formatApiError(q.error)}</p>
  }

  if (rootIds.length === 0) {
    return <p className="text-sm text-muted-foreground">当前扫描目录下暂无学习对象。</p>
  }

  return (
    <div className="space-y-1">
      {rootIds.map((rootId) => (
        <TreeNode
          key={rootId}
          nodeId={rootId}
          depth={0}
          expanded={expanded}
          toggle={toggle}
          nodeById={nodeById}
          selectedInstanceId={selectedInstanceId}
          onSelectInstance={onSelectInstance}
        />
      ))}
    </div>
  )
}

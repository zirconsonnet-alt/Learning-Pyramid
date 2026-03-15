import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { listLearningObjectNodes, type LearningObjectNode } from "@/ui/api/learningObjects"
import { Button } from "@/ui/components/ui/button"
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

  if (q.isLoading) {
    return <LoadingNotice title="正在加载内容目录" message="正在读取这个项目的学习对象树和材料层级。" />
  }

  if (q.error) {
    return <ErrorNotice title="内容目录加载失败" message={formatApiError(q.error)} />
  }

  if (rootIds.length === 0) {
    return (
      <div className="space-y-3 rounded-[1rem] border border-dashed border-border/70 bg-background/70 p-4">
        <div className="space-y-1">
          <p className="text-sm font-medium text-foreground">当前还没有学习对象</p>
          <p className="text-sm text-muted-foreground">
            请先到项目设置里绑定目录并执行同步，完成后就能在这里看到视频和目录树。
          </p>
        </div>
        <Button asChild size="sm" className="rounded-full">
          <Link to={`/p/${projectId}/settings`}>前往项目设置</Link>
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-1">
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

import { ContentEmptyState } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"

export type MindMapNode = {
  nodeId: string
  title: string
  kind: "leaf" | "container"
  children?: string[]
  learningTaskId?: string
  hidden?: boolean
}

function NodeView({
  nodeId,
  nodeById,
  onNodeClick,
}: {
  nodeId: string
  nodeById: Record<string, MindMapNode>
  onNodeClick: (n: MindMapNode) => void
}) {
  const n = nodeById[nodeId]
  if (!n) return null

  const children = n.kind === "container" ? (n.children ?? []) : []

  return (
    <div className="flex flex-col items-center">
      {n.hidden ? (
        <NodeButton node={n} onNodeClick={onNodeClick} className="pointer-events-none invisible" />
      ) : (
        <NodeButton node={n} onNodeClick={onNodeClick} />
      )}

      {children.length > 0 ? (
        <>
          {n.hidden ? <div className="h-4" /> : <div className="h-4 w-px bg-muted-foreground/30" />}
          <div className="flex items-start gap-6">
            {children.map((cid) => (
              <NodeView key={cid} nodeId={cid} nodeById={nodeById} onNodeClick={onNodeClick} />
            ))}
          </div>
        </>
      ) : null}
    </div>
  )
}

export function LayerBandTree({
  rootIds,
  nodeById,
  nodeLayerById,
  onNodeClick,
}: {
  rootIds: string[]
  nodeById: Record<string, MindMapNode>
  nodeLayerById: Record<string, number>
  onNodeClick: (n: MindMapNode) => void
}) {
  const layoutById: Record<string, { start: number; span: number }> = {}
  const visited = new Set<string>()
  let nextLeafColumn = 0

  function visit(nodeId: string): { start: number; span: number } {
    const cached = layoutById[nodeId]
    if (cached) return cached

    visited.add(nodeId)
    const node = nodeById[nodeId]
    if (!node) {
      const layout = { start: nextLeafColumn, span: 1 }
      nextLeafColumn += 1
      layoutById[nodeId] = layout
      return layout
    }

    const children = node.kind === "container" ? (node.children ?? []) : []
    if (children.length === 0) {
      const layout = { start: nextLeafColumn, span: 1 }
      nextLeafColumn += 1
      layoutById[nodeId] = layout
      return layout
    }

    let first = Number.POSITIVE_INFINITY
    let last = -1
    for (const childId of children) {
      const childLayout = visit(childId)
      first = Math.min(first, childLayout.start)
      last = Math.max(last, childLayout.start + childLayout.span - 1)
    }

    if (!Number.isFinite(first) || last < first) {
      first = nextLeafColumn
      last = nextLeafColumn
      nextLeafColumn += 1
    }

    const layout = { start: first, span: last - first + 1 }
    layoutById[nodeId] = layout
    return layout
  }

  for (const rootId of rootIds) visit(rootId)
  for (const nodeId of Object.keys(nodeById).sort()) {
    if (!visited.has(nodeId)) visit(nodeId)
  }

  const totalColumns = Math.max(nextLeafColumn, 1)
  const allNodeIds = Object.keys(layoutById)
  const maxLayerIndex = allNodeIds.reduce((max, nodeId) => Math.max(max, nodeLayerById[nodeId] ?? 0), 0)

  const rows = Array.from({ length: maxLayerIndex + 1 }, (_, offset) => maxLayerIndex - offset).map((layerIndex) => {
    const nodeIds = allNodeIds
      .filter((nodeId) => (nodeLayerById[nodeId] ?? 0) === layerIndex)
      .sort((a, b) => {
        const layoutA = layoutById[a]
        const layoutB = layoutById[b]
        if (layoutA.start !== layoutB.start) return layoutA.start - layoutB.start
        if (layoutA.span !== layoutB.span) return layoutA.span - layoutB.span
        return a.localeCompare(b)
      })
    return { layerIndex, nodeIds }
  })

  if (allNodeIds.length === 0) {
    return (
      <ContentEmptyState
        title="当前结构图还没有根节点"
        message="相关节点数据生成后，这里会自动展开对应的层级结构。"
      />
    )
  }

  return (
    <div className="min-w-max space-y-6">
      {rows.map((row) => (
        <div
          key={row.layerIndex}
          className="grid items-start gap-6"
          style={{ gridTemplateColumns: `48px repeat(${totalColumns}, minmax(96px, 1fr))` }}
        >
          <div className="pt-3 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            L{row.layerIndex}
          </div>
          {row.nodeIds.map((nodeId) => {
            const node = nodeById[nodeId]
            const layout = layoutById[nodeId]
            if (!node || !layout) return null

            return (
              <div key={nodeId} className="flex justify-center" style={{ gridColumn: `${layout.start + 2} / span ${layout.span}` }}>
                <div className="flex flex-col items-center">
                  <NodeButton node={node} onNodeClick={onNodeClick} />
                  {node.kind === "container" && (node.children?.length ?? 0) > 0 ? (
                    <div className="mt-2 h-5 w-px bg-muted-foreground/25" />
                  ) : null}
                </div>
              </div>
            )
          })}
        </div>
      ))}
    </div>
  )
}

function NodeButton({
  node,
  onNodeClick,
  className,
}: {
  node: MindMapNode
  onNodeClick: (n: MindMapNode) => void
  className?: string
}) {
  return (
    <Button
      variant="outline"
      className={["h-auto min-h-[4rem] max-w-[240px] whitespace-normal rounded-2xl px-4 py-3 text-left", className]
        .filter(Boolean)
        .join(" ")}
      onClick={() => onNodeClick(node)}
    >
      <div className="min-w-0">
        <div className="break-words font-medium">{node.title || " "}</div>
      </div>
    </Button>
  )
}

export function MindMapTree({
  rootIds,
  footerNodeIds = [],
  nodeById,
  onNodeClick,
}: {
  rootIds: string[]
  footerNodeIds?: string[]
  nodeById: Record<string, MindMapNode>
  onNodeClick: (n: MindMapNode) => void
}) {
  if (rootIds.length === 0 && footerNodeIds.length === 0) {
    return (
      <ContentEmptyState
        title="当前结构图还没有根节点"
        message="相关节点数据生成后，这里会自动展开对应的层级结构。"
      />
    )
  }

  return (
    <div className="min-w-max">
      <div className="flex items-start gap-10">
        {rootIds.map((rid) => (
          <NodeView key={rid} nodeId={rid} nodeById={nodeById} onNodeClick={onNodeClick} />
        ))}
      </div>
      {footerNodeIds.length > 0 ? (
        <div className="mt-10 flex items-start gap-6">
          {footerNodeIds.map((nodeId) => {
            const node = nodeById[nodeId]
            if (!node) return null
            return <NodeButton key={nodeId} node={node} onNodeClick={onNodeClick} />
          })}
        </div>
      ) : null}
    </div>
  )
}

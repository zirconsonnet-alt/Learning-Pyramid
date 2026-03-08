import { BookOpen, Layers3, ListTodo, type LucideIcon } from "lucide-react"
import { useMemo } from "react"

import { cn } from "@/ui/utils"
import type { MindMapNode } from "@/views/trees/components/MindMapTree"

type TaskTreeVisualType = "aggregation" | "chapter" | "task"

export type LearningTaskTreeNode = MindMapNode & {
  displayTitle?: string
  metaText?: string
  rawTitle?: string
  uiType?: TaskTreeVisualType
}

type LayoutNode = {
  centerX: number
  height: number
  layerIndex: number
  left: number
  nodeId: string
  top: number
  width: number
}

type TreeEdge = {
  childId: string
  parentId: string
}

const RAIL_WIDTH = 116
const CANVAS_PADDING_X = 28
const TOP_PADDING = 24
const BOTTOM_PADDING = 28
const COLUMN_WIDTH = 196
const ROW_HEIGHT = 172
const NODE_HEIGHT = 110

function getVisual(uiType?: TaskTreeVisualType): {
  cardClass: string
  iconClass: string
  Icon: LucideIcon
  label: string
  metaClass: string
  pillClass: string
  titleClass: string
  width: number
} {
  if (uiType === "aggregation") {
    return {
      width: 232,
      Icon: Layers3,
      label: "聚合",
      cardClass:
        "border-[#bdd1e5] bg-[linear-gradient(180deg,rgba(247,250,255,0.98),rgba(237,245,255,0.96))] shadow-[0_28px_56px_-38px_rgba(34,66,102,0.42)]",
      pillClass: "border-[#b4c9df] bg-white/88 text-[#36526f]",
      iconClass: "text-[#3d6186]",
      titleClass: "text-[#18324d]",
      metaClass: "text-[#607790]",
    }
  }

  if (uiType === "chapter") {
    return {
      width: 210,
      Icon: BookOpen,
      label: "章节",
      cardClass:
        "border-[#9fbad6] bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(244,249,255,0.9))] shadow-[0_24px_48px_-34px_rgba(44,79,118,0.34)]",
      pillClass: "border-[#adc4dc] bg-[#eef5fd] text-[#31567d]",
      iconClass: "text-[#3c648c]",
      titleClass: "text-[#19334e]",
      metaClass: "text-[#627a93]",
    }
  }

  return {
    width: 176,
    Icon: ListTodo,
    label: "任务",
    cardClass:
      "border-[#d3dde8] bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(251,253,255,0.96))] shadow-[0_20px_42px_-36px_rgba(15,23,42,0.34)]",
    pillClass: "border-[#d8e1ea] bg-white text-[#56718b]",
    iconClass: "text-[#607790]",
    titleClass: "text-[#1b3146]",
    metaClass: "text-[#6d849c]",
  }
}

function collectDescendantIds(nodeId: string, nodeById: Record<string, LearningTaskTreeNode>, target: Set<string>) {
  if (target.has(nodeId)) return
  target.add(nodeId)

  const node = nodeById[nodeId]
  if (!node || node.kind !== "container") return

  for (const childId of node.children ?? []) {
    collectDescendantIds(childId, nodeById, target)
  }
}

function getRowCaption(rowNodeIds: string[], nodeById: Record<string, LearningTaskTreeNode>) {
  const types = new Set(
    rowNodeIds
      .map((nodeId) => nodeById[nodeId]?.uiType)
      .filter((value): value is TaskTreeVisualType => value === "aggregation" || value === "chapter" || value === "task"),
  )

  if (types.size === 1) {
    const only = Array.from(types)[0]
    if (only === "task") return "任务层"
    if (only === "chapter") return "章节层"
    return "聚合层"
  }

  if (types.has("chapter") && types.has("aggregation")) return "章节 / 聚合"
  if (types.has("task") && types.has("chapter")) return "任务 / 章节"
  if (types.has("task") && types.has("aggregation")) return "任务 / 聚合"
  return "结构层"
}

function buildLayout(rootIds: string[], nodeById: Record<string, LearningTaskTreeNode>, nodeLayerById: Record<string, number>) {
  const parentById: Record<string, string | null> = {}
  const layoutById: Record<string, { span: number; start: number }> = {}
  const visited = new Set<string>()
  const edges: TreeEdge[] = []
  let nextLeafColumn = 0

  for (const node of Object.values(nodeById)) {
    if (node.kind !== "container") continue
    for (const childId of node.children ?? []) {
      parentById[childId] = node.nodeId
      edges.push({ parentId: node.nodeId, childId })
    }
  }

  function visit(nodeId: string): { span: number; start: number } {
    const cached = layoutById[nodeId]
    if (cached) return cached

    visited.add(nodeId)
    const node = nodeById[nodeId]
    if (!node) {
      const fallback = { start: nextLeafColumn, span: 1 }
      nextLeafColumn += 1
      layoutById[nodeId] = fallback
      return fallback
    }

    const children = node.kind === "container" ? (node.children ?? []) : []
    if (children.length === 0) {
      const leafLayout = { start: nextLeafColumn, span: 1 }
      nextLeafColumn += 1
      layoutById[nodeId] = leafLayout
      return leafLayout
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

    const nodeLayout = { start: first, span: last - first + 1 }
    layoutById[nodeId] = nodeLayout
    return nodeLayout
  }

  for (const rootId of rootIds) visit(rootId)
  for (const nodeId of Object.keys(nodeById).sort()) {
    if (!visited.has(nodeId)) visit(nodeId)
    if (!(nodeId in parentById)) parentById[nodeId] = null
  }

  const totalColumns = Math.max(nextLeafColumn, 1)
  const allNodeIds = Object.keys(layoutById)
  const maxLayerIndex = allNodeIds.reduce((max, nodeId) => Math.max(max, nodeLayerById[nodeId] ?? 0), 0)

  const rowNodeIds = Array.from({ length: maxLayerIndex + 1 }, (_, offset) => maxLayerIndex - offset).map((layerIndex) => {
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

  const rectById: Record<string, LayoutNode> = {}
  for (const row of rowNodeIds) {
    const rowIndex = maxLayerIndex - row.layerIndex
    const rowTop = TOP_PADDING + rowIndex * ROW_HEIGHT

    for (const nodeId of row.nodeIds) {
      const layout = layoutById[nodeId]
      const node = nodeById[nodeId]
      if (!layout || !node) continue

      const visual = getVisual(node.uiType)
      const centerX = RAIL_WIDTH + CANVAS_PADDING_X + layout.start * COLUMN_WIDTH + layout.span * COLUMN_WIDTH * 0.5

      rectById[nodeId] = {
        nodeId,
        layerIndex: row.layerIndex,
        width: visual.width,
        height: NODE_HEIGHT,
        centerX,
        left: centerX - visual.width / 2,
        top: rowTop + 34,
      }
    }
  }

  return {
    canvasHeight: TOP_PADDING + rowNodeIds.length * ROW_HEIGHT + BOTTOM_PADDING,
    canvasWidth: RAIL_WIDTH + CANVAS_PADDING_X * 2 + totalColumns * COLUMN_WIDTH,
    edges,
    maxLayerIndex,
    parentById,
    rectById,
    rows: rowNodeIds,
  }
}

export function LearningTaskTreeCanvas({
  focusNodeId,
  nodeById,
  nodeLayerById,
  onNodeHover,
  onNodeSelect,
  rootIds,
  selectedNodeId,
}: {
  focusNodeId?: string | null
  nodeById: Record<string, LearningTaskTreeNode>
  nodeLayerById: Record<string, number>
  onNodeHover?: (nodeId: string | null) => void
  onNodeSelect: (node: LearningTaskTreeNode) => void
  rootIds: string[]
  selectedNodeId?: string | null
}) {
  const { canvasHeight, canvasWidth, edges, parentById, rectById, rows } = useMemo(
    () => buildLayout(rootIds, nodeById, nodeLayerById),
    [nodeById, nodeLayerById, rootIds],
  )

  const activeNodeIds = useMemo(() => {
    if (!focusNodeId || !nodeById[focusNodeId]) return new Set<string>()

    const target = new Set<string>()
    let current: string | null | undefined = focusNodeId
    while (current) {
      target.add(current)
      current = parentById[current]
    }

    collectDescendantIds(focusNodeId, nodeById, target)
    return target
  }, [focusNodeId, nodeById, parentById])

  if (Object.keys(rectById).length === 0) {
    return <p className="text-sm text-muted-foreground">暂无根节点。</p>
  }

  return (
    <div className="min-w-max">
      <div className="relative" style={{ width: canvasWidth, height: canvasHeight }}>
        <div className="pointer-events-none absolute inset-0">
          {rows.map((row) => {
            const rowIndex = rows.findIndex((item) => item.layerIndex === row.layerIndex)
            const rowTop = TOP_PADDING + rowIndex * ROW_HEIGHT
            const caption = getRowCaption(row.nodeIds, nodeById)

            return (
              <div key={row.layerIndex} className="absolute inset-x-0" style={{ top: rowTop, height: ROW_HEIGHT - 14 }}>
                <div className="absolute inset-x-2 bottom-2 top-0 rounded-[30px] border border-white/65 bg-white/[0.34]" />
                <div className="absolute left-5 top-5 w-20">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#59718b]">L{row.layerIndex}</div>
                  <div className="mt-1 text-xs font-medium text-[#7a91a9]">{caption}</div>
                </div>
              </div>
            )
          })}
        </div>

        <svg className="pointer-events-none absolute inset-0" width={canvasWidth} height={canvasHeight} viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}>
          {edges.map((edge) => {
            const parentRect = rectById[edge.parentId]
            const childRect = rectById[edge.childId]
            if (!parentRect || !childRect) return null

            const isActive = !!focusNodeId && activeNodeIds.has(edge.parentId) && activeNodeIds.has(edge.childId)
            const startX = parentRect.centerX
            const startY = parentRect.top + parentRect.height
            const endX = childRect.centerX
            const endY = childRect.top
            const midY = startY + (endY - startY) / 2

            return (
              <path
                key={`${edge.parentId}-${edge.childId}`}
                d={`M ${startX} ${startY} V ${midY} H ${endX} V ${endY}`}
                fill="none"
                stroke={isActive ? "rgba(44, 83, 122, 0.92)" : "rgba(97, 122, 150, 0.58)"}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={isActive ? 2.8 : 1.7}
              />
            )
          })}
        </svg>

        {Object.values(rectById).map((rect) => {
          const node = nodeById[rect.nodeId]
          if (!node) return null

          const visual = getVisual(node.uiType)
          const isSelected = selectedNodeId === rect.nodeId
          const isActive = !!focusNodeId && activeNodeIds.has(rect.nodeId)
          const isMuted = !!focusNodeId && !isActive
          const displayTitle = node.displayTitle ?? node.title
          const metaText = node.metaText ?? (node.kind === "container" ? `${node.children?.length ?? 0} 个子节点` : "学习任务")
          const Icon = visual.Icon

          return (
            <button
              key={rect.nodeId}
              type="button"
              className={cn(
                "absolute flex flex-col rounded-[24px] border px-4 py-3 text-left transition duration-200",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#31567d]/30 focus-visible:ring-offset-2 focus-visible:ring-offset-transparent",
                visual.cardClass,
                isSelected && "border-[#31567d] shadow-[0_32px_64px_-36px_rgba(34,66,102,0.52)]",
                !isSelected && isActive && "border-[#86a6c6] shadow-[0_24px_54px_-36px_rgba(49,86,125,0.42)]",
                isMuted && "opacity-55 saturate-[0.82]",
              )}
              style={{ left: rect.left, top: rect.top, width: rect.width, height: rect.height }}
              onClick={() => onNodeSelect(node)}
              onFocus={() => onNodeHover?.(rect.nodeId)}
              onBlur={() => onNodeHover?.(null)}
              onMouseEnter={() => onNodeHover?.(rect.nodeId)}
              onMouseLeave={() => onNodeHover?.(null)}
            >
              <div className="flex items-center justify-between gap-2">
                <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold", visual.pillClass)}>
                  <Icon className={cn("size-3.5", visual.iconClass)} />
                  {visual.label}
                </span>
                <span className="inline-flex items-center rounded-full border border-white/80 bg-white/70 px-2.5 py-1 text-[11px] font-semibold text-[#5d7590]">
                  L{rect.layerIndex}
                </span>
              </div>

              <div className="mt-3 flex min-h-0 flex-1 flex-col justify-between">
                <div className={cn("text-[15px] font-semibold leading-snug tracking-tight", visual.titleClass)}>{displayTitle}</div>
                <div className={cn("mt-3 text-xs font-medium", visual.metaClass)}>{metaText}</div>
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}

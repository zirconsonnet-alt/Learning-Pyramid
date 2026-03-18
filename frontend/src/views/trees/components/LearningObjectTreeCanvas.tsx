import { File, FolderOpen, HardDrive, type LucideIcon } from "lucide-react"
import { useMemo } from "react"

import { ContentEmptyState } from "@/ui/components/contentEmptyState"
import { cn } from "@/ui/utils"

export type ObjectTreeVisualType = "root" | "group" | "material"

export type LearningObjectTreeCanvasNode = {
  nodeId: string
  title: string
  displayTitle?: string
  rawTitle?: string
  metaText?: string
  kind: "leaf" | "container"
  children?: string[]
  instanceId?: string
  uiType?: ObjectTreeVisualType
}

type LayoutNode = {
  centerX: number
  depth: number
  height: number
  left: number
  nodeId: string
  top: number
  width: number
}

type TreeEdge = {
  childId: string
  parentId: string
}

const RAIL_WIDTH = 110
const CANVAS_PADDING_X = 28
const TOP_PADDING = 24
const BOTTOM_PADDING = 28
const COLUMN_WIDTH = 196
const ROW_HEIGHT = 168
const NODE_HEIGHT = 108

function getVisual(uiType?: ObjectTreeVisualType): {
  cardClass: string
  iconClass: string
  Icon: LucideIcon
  label: string
  metaClass: string
  pillClass: string
  titleClass: string
  width: number
} {
  if (uiType === "root") {
    return {
      width: 230,
      Icon: HardDrive,
      label: "根目录",
      cardClass:
        "border-[#b5c9de] bg-[linear-gradient(180deg,rgba(245,250,255,0.99),rgba(236,244,255,0.96))] shadow-[0_28px_56px_-38px_rgba(34,66,102,0.42)]",
      pillClass: "border-[#b4c9df] bg-white/88 text-[#36526f]",
      iconClass: "text-[#3d6186]",
      titleClass: "text-[#18324d]",
      metaClass: "text-[#607790]",
    }
  }

  if (uiType === "group") {
    return {
      width: 206,
      Icon: FolderOpen,
      label: "分组",
      cardClass:
        "border-[#a5bfda] bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(244,249,255,0.92))] shadow-[0_24px_50px_-36px_rgba(44,79,118,0.34)]",
      pillClass: "border-[#adc4dc] bg-[#eef5fd] text-[#31567d]",
      iconClass: "text-[#3c648c]",
      titleClass: "text-[#19334e]",
      metaClass: "text-[#627a93]",
    }
  }

  return {
    width: 186,
    Icon: File,
    label: "材料",
    cardClass:
      "border-[#d3dde8] bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(251,253,255,0.96))] shadow-[0_20px_42px_-36px_rgba(15,23,42,0.34)]",
    pillClass: "border-[#d8e1ea] bg-white text-[#56718b]",
    iconClass: "text-[#607790]",
    titleClass: "text-[#1b3146]",
    metaClass: "text-[#6d849c]",
  }
}

function collectDescendantIds(nodeId: string, nodeById: Record<string, LearningObjectTreeCanvasNode>, target: Set<string>) {
  if (target.has(nodeId)) return
  target.add(nodeId)

  const node = nodeById[nodeId]
  if (!node || node.kind !== "container") return

  for (const childId of node.children ?? []) {
    collectDescendantIds(childId, nodeById, target)
  }
}

function getRowCaption(depth: number, rowNodeIds: string[], nodeById: Record<string, LearningObjectTreeCanvasNode>) {
  const types = new Set(
    rowNodeIds
      .map((nodeId) => nodeById[nodeId]?.uiType)
      .filter((value): value is ObjectTreeVisualType => value === "root" || value === "group" || value === "material"),
  )

  if (depth === 0) return "根层"
  if (types.size === 1 && types.has("material")) return "材料层"
  if (types.size === 1 && types.has("group")) return "目录层"
  return "目录 / 材料"
}

function buildLayout(
  rootIds: string[],
  nodeById: Record<string, LearningObjectTreeCanvasNode>,
  nodeDepthById: Record<string, number>,
) {
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
  const maxDepth = allNodeIds.reduce((max, nodeId) => Math.max(max, nodeDepthById[nodeId] ?? 0), 0)
  const rows = Array.from({ length: maxDepth + 1 }, (_, depth) => {
    const nodeIds = allNodeIds
      .filter((nodeId) => (nodeDepthById[nodeId] ?? 0) === depth)
      .sort((a, b) => {
        const layoutA = layoutById[a]
        const layoutB = layoutById[b]
        if (layoutA.start !== layoutB.start) return layoutA.start - layoutB.start
        if (layoutA.span !== layoutB.span) return layoutA.span - layoutB.span
        return a.localeCompare(b)
      })
    return { depth, nodeIds }
  })

  const rectById: Record<string, LayoutNode> = {}
  for (const row of rows) {
    const rowTop = TOP_PADDING + row.depth * ROW_HEIGHT

    for (const nodeId of row.nodeIds) {
      const layout = layoutById[nodeId]
      const node = nodeById[nodeId]
      if (!layout || !node) continue

      const visual = getVisual(node.uiType)
      const centerX = RAIL_WIDTH + CANVAS_PADDING_X + layout.start * COLUMN_WIDTH + layout.span * COLUMN_WIDTH * 0.5

      rectById[nodeId] = {
        nodeId,
        depth: row.depth,
        width: visual.width,
        height: NODE_HEIGHT,
        centerX,
        left: centerX - visual.width / 2,
        top: rowTop + 34,
      }
    }
  }

  return {
    canvasHeight: TOP_PADDING + rows.length * ROW_HEIGHT + BOTTOM_PADDING,
    canvasWidth: RAIL_WIDTH + CANVAS_PADDING_X * 2 + totalColumns * COLUMN_WIDTH,
    edges,
    parentById,
    rectById,
    rows,
  }
}

export function LearningObjectTreeCanvas({
  focusNodeId,
  nodeById,
  nodeDepthById,
  onNodeHover,
  onNodeSelect,
  rootIds,
  selectedNodeId,
}: {
  focusNodeId?: string | null
  nodeById: Record<string, LearningObjectTreeCanvasNode>
  nodeDepthById: Record<string, number>
  onNodeHover?: (nodeId: string | null) => void
  onNodeSelect: (node: LearningObjectTreeCanvasNode) => void
  rootIds: string[]
  selectedNodeId?: string | null
}) {
  const { canvasHeight, canvasWidth, edges, parentById, rectById, rows } = useMemo(
    () => buildLayout(rootIds, nodeById, nodeDepthById),
    [nodeById, nodeDepthById, rootIds],
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
    return (
      <ContentEmptyState
        icon={HardDrive}
        title="当前对象树还没有根节点"
        message="内容目录导入完成后，学习对象的根目录与分组结构会显示在这里。"
      />
    )
  }

  return (
    <div className="min-w-max">
      <div className="relative" style={{ width: canvasWidth, height: canvasHeight }}>
        <div className="pointer-events-none absolute inset-0">
          {rows.map((row) => {
            const rowTop = TOP_PADDING + row.depth * ROW_HEIGHT
            const caption = getRowCaption(row.depth, row.nodeIds, nodeById)

            return (
              <div key={row.depth} className="absolute inset-x-0" style={{ top: rowTop, height: ROW_HEIGHT - 14 }}>
                <div className="absolute inset-x-2 bottom-2 top-0 rounded-[30px] border border-white/65 bg-white/[0.34]" />
                <div className="absolute left-5 top-5 w-20">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#59718b]">D{row.depth}</div>
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
          const metaText = node.metaText ?? (node.kind === "container" ? `${node.children?.length ?? 0} 个子节点` : "学习材料")
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
                <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#89a1b7]">D{rect.depth}</span>
              </div>

              <div className={cn("mt-3 line-clamp-2 text-[1rem] font-semibold tracking-tight", visual.titleClass)}>{displayTitle}</div>
              <div className={cn("mt-2 line-clamp-2 text-xs leading-5", visual.metaClass)}>{metaText}</div>
            </button>
          )
        })}
      </div>
    </div>
  )
}

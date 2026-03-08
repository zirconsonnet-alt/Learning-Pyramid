const LEGACY_AGGREGATION_TITLE_PATTERN = /^(?:Auto)?RollUp@L(\d+)$/i
const DEFAULT_AGGREGATION_TITLE_PATTERNS = [
  LEGACY_AGGREGATION_TITLE_PATTERN,
  /^聚合节点$/,
  /^聚合节点@L\d+(?:-\d+)?$/,
]

export function isDefaultAggregationTitle(rawTitle: string | null | undefined) {
  const title = String(rawTitle ?? "").trim()
  return DEFAULT_AGGREGATION_TITLE_PATTERNS.some((pattern) => pattern.test(title))
}

export function formatLearningTaskNodeDisplayTitle(
  rawTitle: string | null | undefined,
  options?: { sourceLayerIndex?: number | null },
) {
  const title = String(rawTitle ?? "").trim()
  if (!title) return "未命名节点"

  const legacyMatch = title.match(LEGACY_AGGREGATION_TITLE_PATTERN)
  if (legacyMatch) return `聚合节点@L${legacyMatch[1]}`

  if (/^聚合节点@L\d+(?:-\d+)?$/.test(title)) return title
  if (title === "聚合节点" && options?.sourceLayerIndex !== null && options?.sourceLayerIndex !== undefined) {
    return `聚合节点@L${Math.max(0, options.sourceLayerIndex)}`
  }
  if (title === "聚合节点") return title

  return title.replace(/^(\d+(?:\.\d+)*)补充$/, "$1 补充")
}

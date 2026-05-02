function shortenOpaqueId(value: string | null | undefined, digits = 6) {
  const normalized = value?.trim()
  if (!normalized) return ""
  const lastSegment = normalized.includes("_") ? normalized.split("_").at(-1) ?? normalized : normalized
  const compact = lastSegment.replace(/[^a-zA-Z0-9]/g, "") || lastSegment
  return `#${compact.slice(-digits)}`
}

export function formatOpaqueReference(
  value: string | null | undefined,
  label: string,
  digits = 6,
  empty = `${label}未关联`,
) {
  const shortened = shortenOpaqueId(value, digits)
  return shortened ? `${label} ${shortened}` : empty
}

export function formatProjectReference(projectId: string | null | undefined, empty = "项目未关联") {
  return formatOpaqueReference(projectId, "项目", 6, empty)
}

export function formatRecallPointReference(recallPointId: string | null | undefined, empty = "复述点未关联") {
  return formatOpaqueReference(recallPointId, "复述点", 6, empty)
}

export function formatInstanceReference(
  instanceId: string | null | undefined,
  displayName?: string | null,
  empty = "内容实例待确认",
) {
  const normalizedTitle = displayName?.trim()
  if (normalizedTitle) return normalizedTitle
  return formatOpaqueReference(instanceId, "内容实例", 6, empty)
}

export function simplifyMaterialDisplayName(value: string | null | undefined, empty = "内容待确认") {
  const normalized = value?.trim()
  if (!normalized) return empty
  const leaf = normalized.split("/").at(-1)?.split("\\").at(-1)?.trim() ?? normalized
  const dotIndex = leaf.lastIndexOf(".")
  if (dotIndex <= 0 || dotIndex >= leaf.length - 1) return leaf || normalized
  const extension = leaf.slice(dotIndex + 1)
  if (!/^[a-z0-9]{1,8}$/i.test(extension)) return leaf
  return leaf.slice(0, dotIndex).trim() || leaf
}

export function formatMaterialReference(materialId: string | null | undefined, empty = "内容待确认") {
  return formatOpaqueReference(materialId, "内容", 6, empty)
}

export function formatObjectNodeReference(nodeId: string | null | undefined, empty = "对象节点未关联") {
  return formatOpaqueReference(nodeId, "对象节点", 6, empty)
}

export function formatParentNodeReference(nodeId: string | null | undefined, empty = "父节点未关联") {
  return formatOpaqueReference(nodeId, "父节点", 6, empty)
}

export function formatLearningTaskReference(taskId: string | null | undefined, empty = "学习任务未关联") {
  return formatOpaqueReference(taskId, "学习任务", 6, empty)
}

export function formatReviewTaskReference(taskId: string | null | undefined, empty = "复习任务未关联") {
  return formatOpaqueReference(taskId, "复习任务", 6, empty)
}

export function formatConvergenceReference(taskId: string | null | undefined, empty = "收敛步骤未关联") {
  return formatOpaqueReference(taskId, "收敛步骤", 6, empty)
}

export function formatReviewChainReference(chainId: string | null | undefined, empty = "复习链未关联") {
  return formatOpaqueReference(chainId, "复习链", 6, empty)
}

export function formatRangeReference(rangeId: string | null | undefined, empty = "结果范围未关联") {
  return formatOpaqueReference(rangeId, "结果范围", 6, empty)
}

export function formatArtifactReference(artifactId: string | null | undefined, empty = "转写片段未关联") {
  return formatOpaqueReference(artifactId, "转写片段", 6, empty)
}

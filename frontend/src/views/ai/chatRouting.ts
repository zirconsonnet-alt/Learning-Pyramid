import { buildScopedProjectPath } from "@/ui/projectPaths"

export type AiChatContextKind = "task" | "object" | "recall"

export function isAiChatContextKind(value: string | null | undefined): value is AiChatContextKind {
  return value === "task" || value === "object" || value === "recall"
}

export function describeAiChatContextKind(kind: AiChatContextKind) {
  if (kind === "task") return "学习任务节点"
  if (kind === "object") return "学习对象节点"
  return "复述点"
}

export function buildAiChatPath(
  subjectId: string,
  projectId: string,
  params: { kind: AiChatContextKind; nodeId: string; conversationId?: string | null },
) {
  const searchParams = new URLSearchParams()
  searchParams.set("kind", params.kind)
  searchParams.set("nodeId", params.nodeId)
  if (params.conversationId) searchParams.set("conversation", params.conversationId)
  return `${buildScopedProjectPath(subjectId, projectId, "/ai-chat")}?${searchParams.toString()}`
}

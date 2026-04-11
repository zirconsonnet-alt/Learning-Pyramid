import { z } from "zod"

import { apiRequest, type ApiRequestExecutionOptions } from "@/ui/api/http"
import { normalizeRichContent, RichContentSchema } from "@/ui/api/richContent"

export const ReviewTaskSchema = z.object({
  projectId: z.string(),
  reviewTaskId: z.string(),
  inputRangeId: z.string(),
  createdAt: z.string(),
  state: z.string(),
  executedAt: z.string().nullable(),
  resultRangeId: z.string().nullable(),
})
export type ReviewTask = z.infer<typeof ReviewTaskSchema>

export const ConvergenceSchema = z.object({
  projectId: z.string(),
  convergenceId: z.string(),
  seedRangeId: z.string(),
  ruleId: z.string(),
  reviewTaskIds: z.array(z.string()),
  state: z.string(),
  roundCount: z.number().int(),
})
export type Convergence = z.infer<typeof ConvergenceSchema>

export const ReviewChainItemSchema = z.object({
  kind: z.enum(["CONVERGENCE", "REVIEW_TASK"]),
  id: z.string(),
})

export const ReviewChainSchema = z.object({
  projectId: z.string(),
  reviewChainId: z.string(),
  headIndex: z.number().int(),
  state: z.string(),
  queue: z.array(ReviewChainItemSchema),
})
export type ReviewChain = z.infer<typeof ReviewChainSchema>

export const ReviewChainBindingSchema = z.object({
  projectId: z.string(),
  reviewChainId: z.string(),
  entryNodeId: z.string(),
  entryNodeTitle: z.string(),
  entryNodeKind: z.enum(["leaf", "container"]),
  learningTaskId: z.string().nullable(),
  learningTaskTitle: z.string().nullable(),
  childCount: z.number().int().nullable(),
  targetLayerIndex: z.number().int(),
})
export type ReviewChainBinding = z.infer<typeof ReviewChainBindingSchema>

export const RangeSnapshotSchema = z.object({
  projectId: z.string(),
  rangeId: z.string(),
  recallPointIds: z.array(z.string()),
})
export type RangeSnapshot = z.infer<typeof RangeSnapshotSchema>

export const RecallPointSchema = z.object({
  projectId: z.string(),
  recallPointId: z.string(),
  createdAt: z.string(),
  state: z.enum(["ACTIVE", "DELETED"]),
  deletedAt: z.string().nullable(),
  question: RichContentSchema,
  answer: RichContentSchema,
  anchor: z.object({ instanceId: z.string(), position: z.string() }).nullable(),
  references: z.array(z.string()).default([]),
  insights: z.array(RichContentSchema),
  sourceProjectId: z.string().nullable().optional(),
  sourceRecallPointId: z.string().nullable().optional(),
  sourceMaterialId: z.string().nullable().optional(),
  sourceMaterialTitle: z.string().nullable().optional(),
  sourceAnchorLabel: z.string().nullable().optional(),
  mistakeStatus: z.enum(["OPEN", "RESOLVING", "RESOLVED"]).nullable().optional(),
  mistakeNote: z.string().nullable().optional(),
})
export type RecallPoint = z.infer<typeof RecallPointSchema>

const CollectRecallPointToMistakeMaterialResultSchema = z.object({
  target_project_id: z.string(),
  target_material_id: z.string(),
  target_node_id: z.string(),
  target_recall_point_id: z.string(),
  created_inbox: z.boolean(),
})

export const ReviewRecommendationItemSchema = z.object({
  recallPoint: RecallPointSchema,
  reviewRecommendationIndex: z.number(),
  estimatedMemoryStrength: z.number(),
  weightedSuccessRatio: z.number(),
  lastReviewedAt: z.string().nullable(),
  lastReviewResult: z.enum(["CAN_RECALL", "CANNOT_RECALL"]).nullable(),
  reviewCount: z.number().int(),
})
export type ReviewRecommendationItem = z.infer<typeof ReviewRecommendationItemSchema>

export const ReviewRecommendationPageSchema = z.object({
  items: z.array(ReviewRecommendationItemSchema),
  totalCount: z.number().int(),
  offset: z.number().int(),
  limit: z.number().int(),
  nextOffset: z.number().int().nullable(),
})
export type ReviewRecommendationPage = z.infer<typeof ReviewRecommendationPageSchema>

export const RecallPointReviewProjectionSchema = z.object({
  recallPointId: z.string(),
  calculatedAt: z.string(),
  reviewRecommendationIndex: z.number(),
  estimatedMemoryStrength: z.number(),
  weightedSuccessRatio: z.number(),
  forgettingCurveDecayPerDay: z.number(),
  historyWindowSize: z.number().int(),
  lastReviewedAt: z.string().nullable(),
  lastReviewResult: z.enum(["CAN_RECALL", "CANNOT_RECALL"]).nullable(),
  reviewCount: z.number().int(),
  history: z.array(
    z.object({
      reviewTaskId: z.string(),
      occurredAt: z.string(),
      result: z.enum(["CAN_RECALL", "CANNOT_RECALL"]),
    }),
  ),
})
export type RecallPointReviewProjection = z.infer<typeof RecallPointReviewProjectionSchema>

export function getReviewTask(projectId: string, reviewTaskId: string) {
  return apiRequest({ path: `/projects/${projectId}/review-tasks/${reviewTaskId}`, responseSchema: ReviewTaskSchema })
}

export function getConvergence(projectId: string, convergenceId: string) {
  return apiRequest({ path: `/projects/${projectId}/convergences/${convergenceId}`, responseSchema: ConvergenceSchema })
}

export function getReviewChain(projectId: string, reviewChainId: string) {
  return apiRequest({ path: `/projects/${projectId}/review-chains/${reviewChainId}`, responseSchema: ReviewChainSchema })
}

export function getReviewChainBinding(projectId: string, reviewChainId: string) {
  return apiRequest({
    path: `/projects/${projectId}/review-chains/${reviewChainId}/binding`,
    responseSchema: ReviewChainBindingSchema,
  })
}

export function getRangeSnapshot(projectId: string, rangeId: string) {
  return apiRequest({ path: `/projects/${projectId}/ranges/${rangeId}`, responseSchema: RangeSnapshotSchema })
}

export function getRecallPoint(projectId: string, recallPointId: string) {
  return apiRequest({ path: `/projects/${projectId}/recall-points/${recallPointId}`, responseSchema: RecallPointSchema })
}

export function listRecallPoints(projectId: string) {
  return apiRequest({ path: `/projects/${projectId}/recall-points`, responseSchema: z.array(RecallPointSchema) })
}

export function searchRecallPoints(
  projectId: string,
  params?: {
    q?: string
    limit?: number
  },
  options?: ApiRequestExecutionOptions,
) {
  const search = new URLSearchParams()
  if (params?.q !== undefined && params.q.trim()) search.set("q", params.q.trim())
  if (params?.limit !== undefined) search.set("limit", String(params.limit))
  const query = search.toString()
  return apiRequest({
    path: `/projects/${projectId}/recall-points/search${query ? `?${query}` : ""}`,
    responseSchema: z.array(RecallPointSchema),
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export function getRecallPointReviewProjection(projectId: string, recallPointId: string) {
  return apiRequest({
    path: `/projects/${projectId}/recall-points/${recallPointId}/review-projection`,
    responseSchema: RecallPointReviewProjectionSchema,
  })
}

export function listReviewRecommendations(projectId: string, params?: { offset?: number; limit?: number }) {
  const search = new URLSearchParams()
  if (params?.offset !== undefined) search.set("offset", String(params.offset))
  if (params?.limit !== undefined) search.set("limit", String(params.limit))
  const query = search.toString()
  return apiRequest({
    path: `/projects/${projectId}/review-recommendations${query ? `?${query}` : ""}`,
    responseSchema: ReviewRecommendationPageSchema,
  })
}

export function editRecallPoint(
  projectId: string,
  recallPointId: string,
  params: {
    question: z.infer<typeof RichContentSchema>
    answer: z.infer<typeof RichContentSchema>
    anchor: { instanceId: string; position: string } | null
    mistakeStatus?: "OPEN" | "RESOLVING" | "RESOLVED" | null
    mistakeNote?: string | null
  },
) {
  return apiRequest({
    path: `/projects/${projectId}/recall-points/${recallPointId}`,
    method: "PUT",
    body: {
      question: RichContentSchema.parse(normalizeRichContent(params.question)),
      answer: RichContentSchema.parse(normalizeRichContent(params.answer)),
      anchor: params.anchor,
      mistakeStatus: params.mistakeStatus ?? undefined,
      mistakeNote: params.mistakeNote ?? undefined,
    },
    responseSchema: z.null(),
  })
}

export function collectRecallPointToMistakeMaterial(
  projectId: string,
  recallPointId: string,
  params: {
    targetMaterialId: string
    targetNodeId?: string | null
    mistakeNote?: string | null
  },
) {
  return apiRequest({
    path: `/projects/${projectId}/recall-points/${recallPointId}/collect-to-mistake-material`,
    method: "POST",
    body: {
      targetMaterialId: params.targetMaterialId,
      targetNodeId: params.targetNodeId ?? undefined,
      mistakeNote: params.mistakeNote ?? undefined,
    },
    responseSchema: CollectRecallPointToMistakeMaterialResultSchema,
  })
}

export function deleteRecallPoint(projectId: string, recallPointId: string) {
  return apiRequest({
    path: `/projects/${projectId}/recall-points/${recallPointId}`,
    method: "DELETE",
    responseSchema: z.null(),
  })
}

export function commitReviewTask(
  projectId: string,
  reviewTaskId: string,
  params: {
    canRecall: number[]
    appendedInsights?: { recallPointId: string; insight: z.infer<typeof RichContentSchema> }[]
  },
) {
  return apiRequest({
    path: `/projects/${projectId}/review-tasks/${reviewTaskId}/commit`,
    method: "POST",
    body: {
      canRecall: params.canRecall,
      appendedInsights: params.appendedInsights?.map((item) => ({
        recallPointId: item.recallPointId,
        insight: RichContentSchema.parse(normalizeRichContent(item.insight)),
      })),
    },
    responseSchema: z.null(),
  })
}

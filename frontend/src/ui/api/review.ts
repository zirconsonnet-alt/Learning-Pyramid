import { z } from "zod"

import { apiRequest, type ApiRequestExecutionOptions } from "@/ui/api/http"
import { projectApiPath, type ScopedProjectRef } from "@/ui/api/projectScope"
import { isVirtualStudyReviewProjectId } from "@/ui/guideWalkthrough/guideVirtualProjectIds"
import {
  getVirtualStudyReviewRecallPoint,
  searchVirtualStudyReviewRecallPoints,
} from "@/ui/guideWalkthrough/virtualStudyReviewProject"
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

export const ReviewItemBindingSchema = z.object({
  projectId: z.string(),
  kind: z.enum(["CONVERGENCE", "REVIEW_CHAIN"]),
  reviewChainId: z.string(),
  convergenceId: z.string().nullable(),
})
export type ReviewItemBinding = z.infer<typeof ReviewItemBindingSchema>

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
})
export type RecallPoint = z.infer<typeof RecallPointSchema>

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

export function getReviewTask(scope: ScopedProjectRef, reviewTaskId: string) {
  return apiRequest({ path: projectApiPath(scope, `/review-tasks/${reviewTaskId}`), responseSchema: ReviewTaskSchema })
}

export function getReviewTaskBinding(scope: ScopedProjectRef, reviewTaskId: string) {
  return apiRequest({
    path: projectApiPath(scope, `/review-tasks/${reviewTaskId}/binding`),
    responseSchema: ReviewItemBindingSchema,
  })
}

export function getConvergence(scope: ScopedProjectRef, convergenceId: string) {
  return apiRequest({ path: projectApiPath(scope, `/convergences/${convergenceId}`), responseSchema: ConvergenceSchema })
}

export function getConvergenceBinding(scope: ScopedProjectRef, convergenceId: string) {
  return apiRequest({
    path: projectApiPath(scope, `/convergences/${convergenceId}/binding`),
    responseSchema: ReviewItemBindingSchema,
  })
}

export function getReviewChain(scope: ScopedProjectRef, reviewChainId: string) {
  return apiRequest({ path: projectApiPath(scope, `/review-chains/${reviewChainId}`), responseSchema: ReviewChainSchema })
}

export function getReviewChainBinding(scope: ScopedProjectRef, reviewChainId: string) {
  return apiRequest({
    path: projectApiPath(scope, `/review-chains/${reviewChainId}/binding`),
    responseSchema: ReviewChainBindingSchema,
  })
}

export function getRangeSnapshot(scope: ScopedProjectRef, rangeId: string) {
  return apiRequest({ path: projectApiPath(scope, `/ranges/${rangeId}`), responseSchema: RangeSnapshotSchema })
}

export function getRecallPoint(scope: ScopedProjectRef, recallPointId: string) {
  if (isVirtualStudyReviewProjectId(scope.scopedProjectId)) {
    return Promise.resolve(getVirtualStudyReviewRecallPoint(recallPointId))
  }
  return apiRequest({ path: projectApiPath(scope, `/recall-points/${recallPointId}`), responseSchema: RecallPointSchema })
}

export function listRecallPoints(scope: ScopedProjectRef) {
  return apiRequest({ path: projectApiPath(scope, "/recall-points"), responseSchema: z.array(RecallPointSchema) })
}

export function searchRecallPoints(
  scope: ScopedProjectRef,
  params?: {
    q?: string
    limit?: number
  },
  options?: ApiRequestExecutionOptions,
) {
  if (isVirtualStudyReviewProjectId(scope.scopedProjectId)) {
    return Promise.resolve(searchVirtualStudyReviewRecallPoints(params?.q ?? "").slice(0, params?.limit ?? 500))
  }
  const search = new URLSearchParams()
  if (params?.q !== undefined && params.q.trim()) search.set("q", params.q.trim())
  if (params?.limit !== undefined) search.set("limit", String(params.limit))
  const query = search.toString()
  return apiRequest({
    path: projectApiPath(scope, `/recall-points/search${query ? `?${query}` : ""}`),
    responseSchema: z.array(RecallPointSchema),
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export function getRecallPointReviewProjection(scope: ScopedProjectRef, recallPointId: string) {
  return apiRequest({
    path: projectApiPath(scope, `/recall-points/${recallPointId}/review-projection`),
    responseSchema: RecallPointReviewProjectionSchema,
  })
}

export function listReviewRecommendations(scope: ScopedProjectRef, params?: { offset?: number; limit?: number }) {
  const search = new URLSearchParams()
  if (params?.offset !== undefined) search.set("offset", String(params.offset))
  if (params?.limit !== undefined) search.set("limit", String(params.limit))
  const query = search.toString()
  return apiRequest({
    path: projectApiPath(scope, `/review-recommendations${query ? `?${query}` : ""}`),
    responseSchema: ReviewRecommendationPageSchema,
  })
}

export async function listAllReviewRecommendations(scope: ScopedProjectRef, params?: { limit?: number }) {
  const limit = params?.limit ?? 500
  const items: ReviewRecommendationItem[] = []
  let offset = 0

  for (;;) {
    const page = await listReviewRecommendations(scope, { offset, limit })
    items.push(...page.items)
    if (page.nextOffset == null) {
      return { ...page, items, offset: 0, limit }
    }
    offset = page.nextOffset
  }
}

export function editRecallPoint(
  scope: ScopedProjectRef,
  recallPointId: string,
  params: {
    question: z.infer<typeof RichContentSchema>
    answer: z.infer<typeof RichContentSchema>
    anchor: { instanceId: string; position: string } | null
  },
) {
  return apiRequest({
    path: projectApiPath(scope, `/recall-points/${recallPointId}`),
    method: "PUT",
    body: {
      question: RichContentSchema.parse(normalizeRichContent(params.question)),
      answer: RichContentSchema.parse(normalizeRichContent(params.answer)),
      anchor: params.anchor,
    },
    responseSchema: z.null(),
  })
}

export function deleteRecallPoint(scope: ScopedProjectRef, recallPointId: string) {
  return apiRequest({
    path: projectApiPath(scope, `/recall-points/${recallPointId}`),
    method: "DELETE",
    responseSchema: z.null(),
  })
}

export function commitReviewTask(
  scope: ScopedProjectRef,
  reviewTaskId: string,
  params: {
    canRecall: number[]
    appendedInsights?: { recallPointId: string; insight: z.infer<typeof RichContentSchema> }[]
  },
) {
  return apiRequest({
    path: projectApiPath(scope, `/review-tasks/${reviewTaskId}/commit`),
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

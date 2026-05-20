import { z } from "zod"

import { RichContentSchema } from "./richContent"
import { projectApiPath, type ApiRequester, type ScopedProjectRef } from "./requester"

const AnchorSchema = z.object({
  instanceId: z.string(),
  position: z.string(),
})

export const QueueSchema = z.object({
  headId: z.string().nullable(),
  ids: z.array(z.string()),
})

export const ReviewTaskSchema = z.object({
  projectId: z.string(),
  reviewTaskId: z.string(),
  inputRangeId: z.string(),
  createdAt: z.string(),
  state: z.string(),
  executedAt: z.string().nullable(),
  resultRangeId: z.string().nullable(),
})

export const RangeSnapshotSchema = z.object({
  projectId: z.string(),
  rangeId: z.string(),
  recallPointIds: z.array(z.string()),
})

export const RecallPointSchema = z.object({
  projectId: z.string(),
  recallPointId: z.string(),
  createdAt: z.string(),
  state: z.enum(["ACTIVE", "DELETED"]),
  deletedAt: z.string().nullable(),
  question: RichContentSchema,
  answer: RichContentSchema,
  anchor: AnchorSchema.nullable(),
  references: z.array(z.string()).default([]),
  insights: z.array(z.unknown()),
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

export const ReviewRecommendationPageSchema = z.object({
  items: z.array(ReviewRecommendationItemSchema),
  totalCount: z.number().int(),
  offset: z.number().int(),
  limit: z.number().int(),
  nextOffset: z.number().int().nullable(),
})

export type RecallPoint = z.infer<typeof RecallPointSchema>
export type Queue = z.infer<typeof QueueSchema>
export type ReviewTask = z.infer<typeof ReviewTaskSchema>
export type RangeSnapshot = z.infer<typeof RangeSnapshotSchema>
export type ReviewRecommendationItem = z.infer<typeof ReviewRecommendationItemSchema>
export type ReviewRecommendationPage = z.infer<typeof ReviewRecommendationPageSchema>

export type ReviewRecommendationQuery = {
  offset?: number
  limit?: number
}

export type CommitReviewTaskInput = {
  canRecall: number[]
  appendedInsights?: Array<{
    recallPointId: string
    insight: z.infer<typeof RichContentSchema>
  }>
}

export type RecallPointSearchQuery = {
  q?: string
  limit?: number
}

function recallPointSearchPath(scope: ScopedProjectRef, query?: RecallPointSearchQuery) {
  const params = new URLSearchParams()
  if (query?.q !== undefined && query.q.trim()) params.set("q", query.q.trim())
  if (query?.limit !== undefined) params.set("limit", String(query.limit))
  const suffix = params.toString()
  return `${projectApiPath(scope, "/recall-points/search")}${suffix ? `?${suffix}` : ""}`
}

function reviewRecommendationsPath(scope: ScopedProjectRef, query?: ReviewRecommendationQuery) {
  const params = new URLSearchParams()
  if (query?.offset !== undefined) params.set("offset", String(query.offset))
  if (query?.limit !== undefined) params.set("limit", String(query.limit))
  const suffix = params.toString()
  return `${projectApiPath(scope, "/review-recommendations")}${suffix ? `?${suffix}` : ""}`
}

export function createReviewApi(requester: ApiRequester) {
  return {
    getQueue: (scope: ScopedProjectRef) =>
      requester.request({
        path: projectApiPath(scope, "/queue"),
        responseSchema: QueueSchema,
      }),
    getReviewTask: (scope: ScopedProjectRef, reviewTaskId: string) =>
      requester.request({
        path: projectApiPath(scope, `/review-tasks/${encodeURIComponent(reviewTaskId)}`),
        responseSchema: ReviewTaskSchema,
      }),
    getRangeSnapshot: (scope: ScopedProjectRef, rangeId: string) =>
      requester.request({
        path: projectApiPath(scope, `/ranges/${encodeURIComponent(rangeId)}`),
        responseSchema: RangeSnapshotSchema,
      }),
    listRecallPoints: (scope: ScopedProjectRef) =>
      requester.request({
        path: projectApiPath(scope, "/recall-points"),
        responseSchema: z.array(RecallPointSchema),
      }),
    searchRecallPoints: (scope: ScopedProjectRef, query?: RecallPointSearchQuery) =>
      requester.request({
        path: recallPointSearchPath(scope, query),
        responseSchema: z.array(RecallPointSchema),
      }),
    listRecommendations: (scope: ScopedProjectRef, query?: ReviewRecommendationQuery) =>
      requester.request({
        path: reviewRecommendationsPath(scope, query),
        responseSchema: ReviewRecommendationPageSchema,
      }),
    commitReviewTask: (scope: ScopedProjectRef, reviewTaskId: string, body: CommitReviewTaskInput) =>
      requester.request({
        path: projectApiPath(scope, `/review-tasks/${encodeURIComponent(reviewTaskId)}/commit`),
        method: "POST",
        body: {
          canRecall: body.canRecall,
          appendedInsights: body.appendedInsights?.map((item) => ({
            recallPointId: item.recallPointId,
            insight: RichContentSchema.parse(item.insight),
          })),
        },
        responseSchema: z.null(),
      }),
  }
}

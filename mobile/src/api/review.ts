import { z } from "zod"

import { projectApiPath, type ApiRequester, type ScopedProjectRef } from "./types"

const AnchorSchema = z.object({
  instanceId: z.string(),
  position: z.string(),
})

export const RecallPointSchema = z.object({
  projectId: z.string(),
  recallPointId: z.string(),
  createdAt: z.unknown(),
  state: z.string(),
  deletedAt: z.unknown().nullable().optional(),
  question: z.unknown(),
  answer: z.unknown(),
  anchor: AnchorSchema.nullable(),
  references: z.array(z.string()),
  insights: z.array(z.unknown()),
})

export const ReviewRecommendationItemSchema = z.object({
  recallPoint: RecallPointSchema,
  reviewRecommendationIndex: z.number(),
  estimatedMemoryStrength: z.number(),
  weightedSuccessRatio: z.number(),
  lastReviewedAt: z.unknown().nullable(),
  lastReviewResult: z.unknown().nullable(),
  reviewCount: z.number(),
})

export const ReviewRecommendationPageSchema = z.object({
  items: z.array(ReviewRecommendationItemSchema),
  totalCount: z.number(),
  offset: z.number(),
  limit: z.number(),
  nextOffset: z.number().nullable(),
})

export type RecallPoint = z.infer<typeof RecallPointSchema>
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
    insight: unknown
  }>
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
    listRecallPoints: (scope: ScopedProjectRef) =>
      requester.request({
        path: projectApiPath(scope, "/recall-points"),
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
        body,
        responseSchema: z.null(),
      }),
  }
}

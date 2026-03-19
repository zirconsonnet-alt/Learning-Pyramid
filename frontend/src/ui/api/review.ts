import { z } from "zod"

import { apiRequest } from "@/ui/api/http"
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
  question: RichContentSchema,
  answer: RichContentSchema,
  anchor: z.object({ instanceId: z.string(), position: z.string() }),
  insights: z.array(RichContentSchema),
})
export type RecallPoint = z.infer<typeof RecallPointSchema>

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

export function editRecallPoint(
  projectId: string,
  recallPointId: string,
  params: { question: z.infer<typeof RichContentSchema>; answer: z.infer<typeof RichContentSchema>; anchor: { instanceId: string; position: string } },
) {
  return apiRequest({
    path: `/projects/${projectId}/recall-points/${recallPointId}`,
    method: "PUT",
    body: {
      question: RichContentSchema.parse(normalizeRichContent(params.question)),
      answer: RichContentSchema.parse(normalizeRichContent(params.answer)),
      anchor: params.anchor,
    },
    responseSchema: z.null(),
  })
}

export function commitReviewTask(projectId: string, reviewTaskId: string, canRecall: number[]) {
  return apiRequest({
    path: `/projects/${projectId}/review-tasks/${reviewTaskId}/commit`,
    method: "POST",
    body: { canRecall },
    responseSchema: z.null(),
  })
}

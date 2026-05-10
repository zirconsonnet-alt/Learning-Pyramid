import { z } from "zod"

import { apiRequest } from "@/ui/api/http"
import { projectApiPath, type ProjectScope } from "@/ui/api/projectScope"
import { ProjectTypeSchema } from "@/ui/api/projects"

export const ReviewChainTemplateItemSchema = z.object({
  kind: z.enum(["CONVERGENCE", "REVIEW_TASK"]),
  count: z.number().int().optional(),
})
export type ReviewChainTemplateItem = z.infer<typeof ReviewChainTemplateItemSchema>

export const LayerConfigSchema = z.object({
  reviewChainTemplate: z.array(ReviewChainTemplateItemSchema),
  aggregationKNode: z.number().int(),
  aggregationKPoint: z.number().int(),
  thresholdRollUpEnabled: z.boolean().default(true),
})
export type LayerConfig = z.infer<typeof LayerConfigSchema>

export const RollUpStrategySchema = z.enum(["MANUAL", "THRESHOLD_AUTO", "LEARNING_OBJECT_ISOMORPHIC"])
export type RollUpStrategy = z.infer<typeof RollUpStrategySchema>

export const ProjectConfigSchema = z.object({
  projectId: z.string(),
  projectType: ProjectTypeSchema,
  rollUpStrategy: RollUpStrategySchema.default("THRESHOLD_AUTO"),
  updatedAt: z.string(),
  layerConfigs: z.record(z.string(), LayerConfigSchema),
  pushConfig: z
    .object({
      minRecallPointsToEnable: z.number().int(),
      maxHistoryLen: z.number().int(),
      recommendedBatchSize: z.number().int(),
      forgettingCurveDecayPerDay: z.number(),
    })
    .nullable()
    .optional(),
})
export type ProjectConfig = z.infer<typeof ProjectConfigSchema>

export function getProjectConfig(scope: ProjectScope) {
  return apiRequest({ path: projectApiPath(scope, "/project-config"), responseSchema: ProjectConfigSchema })
}

export function setReviewRecommendationConfig(
  scope: ProjectScope,
  params: {
    minRecallPointsToEnable?: number
    maxHistoryLen?: number
    recommendedBatchSize?: number
    forgettingCurveDecayPerDay?: number
  },
) {
  const body: Record<string, unknown> = {}
  if (params.minRecallPointsToEnable !== undefined) body.minRecallPointsToEnable = params.minRecallPointsToEnable
  if (params.maxHistoryLen !== undefined) body.maxHistoryLen = params.maxHistoryLen
  if (params.recommendedBatchSize !== undefined) body.recommendedBatchSize = params.recommendedBatchSize
  if (params.forgettingCurveDecayPerDay !== undefined) body.forgettingCurveDecayPerDay = params.forgettingCurveDecayPerDay
  return apiRequest({
    path: projectApiPath(scope, "/review-recommendation-config"),
    method: "POST",
    body,
    responseSchema: z.null(),
  })
}

export function setLayerConfig(
  scope: ProjectScope,
  layerIndex: number,
  p: { reviewChainTemplate?: ReviewChainTemplateItem[]; kNode?: number; kPoint?: number; thresholdRollUpEnabled?: boolean },
) {
  const body: Record<string, unknown> = {}
  if (p.reviewChainTemplate !== undefined) body.reviewChainTemplate = p.reviewChainTemplate
  if (p.kNode !== undefined) body.kNode = p.kNode
  if (p.kPoint !== undefined) body.kPoint = p.kPoint
  if (p.thresholdRollUpEnabled !== undefined) body.thresholdRollUpEnabled = p.thresholdRollUpEnabled
  return apiRequest({
    path: projectApiPath(scope, `/layers/${layerIndex}/config`),
    method: "POST",
    body,
    responseSchema: z.null(),
  })
}

export function setProjectRollUpStrategy(scope: ProjectScope, rollUpStrategy: RollUpStrategy) {
  return apiRequest({
    path: projectApiPath(scope, "/roll-up-strategy"),
    method: "POST",
    body: { rollUpStrategy },
    responseSchema: z.null(),
  })
}

import { z } from "zod"

import { apiRequest } from "@/ui/api/http"

export const LocalServiceConfigSchema = z.object({
  baseUrl: z.string(),
  apiKey: z.string().optional(),
  model: z.string().optional(),
})
export type LocalServiceConfig = z.infer<typeof LocalServiceConfigSchema>

export const ReviewChainTemplateItemSchema = z.object({
  kind: z.enum(["CONVERGENCE", "REVIEW_TASK"]),
  count: z.number().int().optional(),
})
export type ReviewChainTemplateItem = z.infer<typeof ReviewChainTemplateItemSchema>

export const LayerConfigSchema = z.object({
  reviewChainTemplate: z.array(ReviewChainTemplateItemSchema),
  aggregationKNode: z.number().int(),
  aggregationKPoint: z.number().int(),
})
export type LayerConfig = z.infer<typeof LayerConfigSchema>

export const ProjectConfigSchema = z.object({
  projectId: z.string(),
  updatedAt: z.string(),
  layerConfigs: z.record(z.string(), LayerConfigSchema),
  externalServices: z
    .object({
      asr: LocalServiceConfigSchema.nullable(),
      recommender: LocalServiceConfigSchema.nullable(),
    })
    .nullable()
    .optional(),
  pushConfig: z
    .object({
      minRecallPointsToEnable: z.number().int(),
      maxHistoryLen: z.number().int(),
    })
    .nullable()
    .optional(),
})
export type ProjectConfig = z.infer<typeof ProjectConfigSchema>

export function getProjectConfig(projectId: string) {
  return apiRequest({ path: `/projects/${projectId}/project-config`, responseSchema: ProjectConfigSchema })
}

export function setExternalServices(
  projectId: string,
  p: {
    asr: { baseUrl: string; apiKey?: string; model?: string } | null
  },
) {
  return apiRequest({
    path: `/projects/${projectId}/external-services`,
    method: "POST",
    body: {
      asr: p.asr,
    },
    responseSchema: z.null(),
  })
}

export function setLayerConfig(
  projectId: string,
  layerIndex: number,
  p: { reviewChainTemplate?: ReviewChainTemplateItem[]; kNode?: number; kPoint?: number },
) {
  const body: Record<string, unknown> = {}
  if (p.reviewChainTemplate !== undefined) body.reviewChainTemplate = p.reviewChainTemplate
  if (p.kNode !== undefined) body.kNode = p.kNode
  if (p.kPoint !== undefined) body.kPoint = p.kPoint
  return apiRequest({
    path: `/projects/${projectId}/layers/${layerIndex}/config`,
    method: "POST",
    body,
    responseSchema: z.null(),
  })
}

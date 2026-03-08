import { z } from "zod"

import { apiRequest } from "@/ui/api/http"

export const LayerSchema = z.object({
  projectId: z.string(),
  layerId: z.string(),
  layerIndex: z.number(),
  layerMode: z.string(),
  orchestratorManagedReviewChainIds: z.array(z.string()),
})
export type Layer = z.infer<typeof LayerSchema>

export const LayersSchema = z.array(LayerSchema)

export const AggQueueSchema = z.object({ currentNodeIds: z.array(z.string()) })

export const AggregationEventSchema = z.object({
  projectId: z.string(),
  eventId: z.string(),
  createdAt: z.string(),
  layerIndex: z.number(),
  parentNodeId: z.string(),
  childNodeIds: z.array(z.string()),
  reason: z.string(),
  title: z.string().nullable(),
})
export const AggregationEventsSchema = z.array(AggregationEventSchema)
export type AggregationEvent = z.infer<typeof AggregationEventSchema>

export const ManualRollUpResultSchema = z.object({ parentNodeId: z.string().nullable() })

export function listLayers(projectId: string) {
  return apiRequest({ path: `/projects/${projectId}/layers`, responseSchema: LayersSchema })
}

export function getAggregationQueue(projectId: string, layerIndex: number) {
  return apiRequest({ path: `/projects/${projectId}/aggregation-queue/${layerIndex}`, responseSchema: AggQueueSchema })
}

export function listAggregationEvents(projectId: string) {
  return apiRequest({ path: `/projects/${projectId}/aggregation-events`, responseSchema: AggregationEventsSchema })
}

export function manualRollUp(projectId: string, layerIndex: number, title?: string) {
  return apiRequest({
    path: `/projects/${projectId}/layers/${layerIndex}/roll-up`,
    method: "POST",
    body: title === undefined ? {} : { title },
    responseSchema: ManualRollUpResultSchema,
  })
}

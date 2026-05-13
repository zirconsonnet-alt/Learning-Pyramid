import { z } from "zod"

import { apiRequest, type ApiRequestExecutionOptions } from "@/ui/api/http"
import { projectApiPath, type ScopedProjectRef } from "@/ui/api/projectScope"
import { isVirtualStudyReviewProjectId } from "@/ui/guideWalkthrough/guideVirtualProjectIds"
import { getVirtualStudyReviewLayers } from "@/ui/guideWalkthrough/virtualStudyReviewProject"

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

export function listLayers(scope: ScopedProjectRef, options?: ApiRequestExecutionOptions) {
  if (isVirtualStudyReviewProjectId(scope.scopedProjectId)) {
    return Promise.resolve(getVirtualStudyReviewLayers())
  }
  return apiRequest({
    path: projectApiPath(scope, "/layers"),
    responseSchema: LayersSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export function getAggregationQueue(scope: ScopedProjectRef, layerIndex: number) {
  if (isVirtualStudyReviewProjectId(scope.scopedProjectId)) {
    return Promise.resolve({ currentNodeIds: [] })
  }
  return apiRequest({ path: projectApiPath(scope, `/aggregation-queue/${layerIndex}`), responseSchema: AggQueueSchema })
}

export function listAggregationEvents(scope: ScopedProjectRef) {
  if (isVirtualStudyReviewProjectId(scope.scopedProjectId)) {
    return Promise.resolve([])
  }
  return apiRequest({ path: projectApiPath(scope, "/aggregation-events"), responseSchema: AggregationEventsSchema })
}

export function manualRollUp(scope: ScopedProjectRef, layerIndex: number, title?: string) {
  if (isVirtualStudyReviewProjectId(scope.scopedProjectId)) {
    return Promise.resolve({ parentNodeId: null })
  }
  return apiRequest({
    path: projectApiPath(scope, `/layers/${layerIndex}/roll-up`),
    method: "POST",
    body: title === undefined ? {} : { title },
    responseSchema: ManualRollUpResultSchema,
  })
}

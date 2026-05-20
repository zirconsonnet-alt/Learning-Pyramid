import { z } from "zod"

import { projectApiPath, type ApiRequester, type ScopedProjectRef } from "./requester"

export const LayerSchema = z.object({
  projectId: z.string(),
  layerId: z.string(),
  layerIndex: z.number(),
  layerMode: z.string(),
  orchestratorManagedReviewChainIds: z.array(z.string()),
})

export const AggregationQueueSchema = z.object({
  currentNodeIds: z.array(z.string()),
})

export const ManualRollUpResultSchema = z.object({
  parentNodeId: z.string().nullable(),
})

export type Layer = z.infer<typeof LayerSchema>
export type AggregationQueue = z.infer<typeof AggregationQueueSchema>
export type ManualRollUpResult = z.infer<typeof ManualRollUpResultSchema>

export function createLayersApi(requester: ApiRequester) {
  return {
    listLayers: (scope: ScopedProjectRef) =>
      requester.request({
        path: projectApiPath(scope, "/layers"),
        responseSchema: z.array(LayerSchema),
      }),
    getAggregationQueue: (scope: ScopedProjectRef, layerIndex: number) =>
      requester.request({
        path: projectApiPath(scope, `/aggregation-queue/${layerIndex}`),
        responseSchema: AggregationQueueSchema,
      }),
    manualRollUp: (scope: ScopedProjectRef, layerIndex: number) =>
      requester.request({
        path: projectApiPath(scope, `/layers/${layerIndex}/roll-up`),
        method: "POST",
        body: {},
        responseSchema: ManualRollUpResultSchema,
      }),
  }
}

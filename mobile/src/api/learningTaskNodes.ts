import { z } from "zod"

import { RecallPointSchema } from "./review"
import { projectApiPath, type ApiRequester, type ScopedProjectRef } from "./requester"

export const LearningTaskLeafSchema = z.object({
  kind: z.literal("leaf"),
  projectId: z.string(),
  nodeId: z.string(),
  parentId: z.string().nullable(),
  boundLearningTaskId: z.string(),
  title: z.string(),
  targetLayerIndex: z.number().int().nullable().optional().default(null),
})

export const LearningTaskContainerSchema = z.object({
  kind: z.literal("container"),
  projectId: z.string(),
  nodeId: z.string(),
  parentId: z.string().nullable(),
  children: z.array(z.string()),
  title: z.string(),
  nodeOrigin: z.enum(["AGGREGATION"]).default("AGGREGATION"),
  targetLayerIndex: z.number().int().nullable().optional().default(null),
})

export const LearningTaskNodeSchema = z.discriminatedUnion("kind", [
  LearningTaskLeafSchema,
  LearningTaskContainerSchema,
])

export type LearningTaskNode = z.infer<typeof LearningTaskNodeSchema>

export function createLearningTaskNodesApi(requester: ApiRequester) {
  return {
    listNodes: (scope: ScopedProjectRef) =>
      requester.request({
        path: projectApiPath(scope, "/learning-task-nodes"),
        responseSchema: z.array(LearningTaskNodeSchema),
      }),
    listRecallPointsByNode: (scope: ScopedProjectRef, nodeId: string) =>
      requester.request({
        path: projectApiPath(scope, `/learning-task-nodes/${encodeURIComponent(nodeId)}/recall-points`),
        responseSchema: z.array(RecallPointSchema),
      }),
  }
}

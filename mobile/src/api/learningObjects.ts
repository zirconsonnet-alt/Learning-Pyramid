import { z } from "zod"

import { RecallPointSchema } from "./review"
import { projectApiPath, type ApiRequester, type ScopedProjectRef } from "./types"

const LearningObjectNodeBaseSchema = z.object({
  projectId: z.string(),
  nodeId: z.string(),
  relativePath: z.unknown().nullable().optional(),
  source: z.string().nullable().optional(),
  parentId: z.string().nullable(),
  title: z.string(),
})

export const LearningObjectLeafSchema = LearningObjectNodeBaseSchema.extend({
  kind: z.literal("leaf"),
  instanceId: z.string(),
})

export const LearningObjectContainerSchema = LearningObjectNodeBaseSchema.extend({
  kind: z.literal("container"),
  children: z.array(z.string()),
})

export const LearningObjectNodeSchema = z.discriminatedUnion("kind", [
  LearningObjectLeafSchema,
  LearningObjectContainerSchema,
])

export type LearningObjectNode = z.infer<typeof LearningObjectNodeSchema>

export function createLearningObjectsApi(requester: ApiRequester) {
  return {
    listNodes: (scope: ScopedProjectRef) =>
      requester.request({
        path: projectApiPath(scope, "/learning-object-nodes"),
        responseSchema: z.array(LearningObjectNodeSchema),
      }),
    getNode: (scope: ScopedProjectRef, nodeId: string) =>
      requester.request({
        path: projectApiPath(scope, `/learning-objects/${encodeURIComponent(nodeId)}`),
        responseSchema: LearningObjectNodeSchema,
      }),
    listRecallPointsByNode: (scope: ScopedProjectRef, nodeId: string) =>
      requester.request({
        path: projectApiPath(scope, `/learning-objects/${encodeURIComponent(nodeId)}/recall-points`),
        responseSchema: z.array(RecallPointSchema),
      }),
  }
}

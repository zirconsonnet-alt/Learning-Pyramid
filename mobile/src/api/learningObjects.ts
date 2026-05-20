import { z } from "zod"

import { RecallPointSchema } from "./review"
import { projectApiPath, type ApiRequester, type ScopedProjectRef } from "./requester"

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

export const BaiduNetdiskImportItemSchema = z.object({
  fileId: z.string(),
  path: z.string(),
  name: z.string().optional(),
  isDir: z.boolean().optional(),
  sizeBytes: z.number().int().nonnegative().optional(),
  mimeType: z.string().nullable().optional(),
  durationMs: z.number().int().nonnegative().nullable().optional(),
})

export type BaiduNetdiskImportItem = z.infer<typeof BaiduNetdiskImportItemSchema>

export const ImportLearningObjectsFromBaiduNetdiskResultSchema = z.object({
  unchanged: z.boolean(),
  created_instances_count: z.number().int(),
  reused_instances_count: z.number().int(),
  marked_missing_count: z.number().int(),
  deleted_instances_count: z.number().int().optional().default(0),
  created_learning_object_nodes_count: z.number().int(),
  replaced_learning_object_nodes_count: z.number().int(),
  imported_count: z.number().int(),
  warnings: z.array(z.unknown()),
})

export type ImportLearningObjectsFromBaiduNetdiskResult = z.infer<
  typeof ImportLearningObjectsFromBaiduNetdiskResultSchema
>

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
    importFromBaiduNetdisk: (
      scope: ScopedProjectRef,
      params: { accountId: string; items: Array<z.input<typeof BaiduNetdiskImportItemSchema>> },
    ) =>
      requester.request({
        path: projectApiPath(scope, "/import-learning-objects-from-baidu-netdisk"),
        method: "POST",
        body: {
          accountId: params.accountId,
          items: params.items.map((item) => BaiduNetdiskImportItemSchema.parse(item)),
        },
        responseSchema: ImportLearningObjectsFromBaiduNetdiskResultSchema,
      }),
  }
}

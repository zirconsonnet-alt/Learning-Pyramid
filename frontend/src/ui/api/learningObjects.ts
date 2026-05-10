import { z } from "zod"

import { AsrArtifactSchema } from "@/ui/api/asr"
import { apiRequest, type ApiRequestExecutionOptions } from "@/ui/api/http"
import { projectApiPath, type ProjectScope } from "@/ui/api/projectScope"
import { RecallPointSchema } from "@/ui/api/review"

export const LearningObjectLeafSchema = z.object({
  kind: z.literal("leaf"),
  projectId: z.string(),
  nodeId: z.string(),
  relativePath: z.string().optional(),
  source: z.string().nullable().optional(),
  parentId: z.string().nullable(),
  instanceId: z.string(),
  title: z.string(),
})

export const LearningObjectContainerSchema = z.object({
  kind: z.literal("container"),
  projectId: z.string(),
  nodeId: z.string(),
  relativePath: z.string().optional(),
  source: z.string().nullable().optional(),
  parentId: z.string().nullable(),
  children: z.array(z.string()),
  title: z.string(),
})

export const LearningObjectNodeSchema = z.discriminatedUnion("kind", [
  LearningObjectLeafSchema,
  LearningObjectContainerSchema,
])

export type LearningObjectNode = z.infer<typeof LearningObjectNodeSchema>

export const LearningObjectRootsSchema = z.object({ rootLearningObjectNodeIds: z.array(z.string()) })

const AddLearningObjectResultSchema = z.object({ nodeId: z.string() })
const InitializeBookLearningObjectsResultSchema = z.object({
  created_instances_count: z.number().int(),
  created_learning_object_nodes_count: z.number().int(),
  root_count: z.number().int(),
})
const ImportLearningObjectsFromBrowserResultSchema = z.object({
  unchanged: z.boolean(),
  created_instances_count: z.number().int(),
  marked_missing_count: z.number().int(),
  replaced_learning_object_nodes_count: z.number().int(),
  warnings: z.array(z.unknown()),
})
const BaiduNetdiskImportItemSchema = z.object({
  fileId: z.string(),
  path: z.string(),
  name: z.string().optional(),
  isDir: z.boolean().optional(),
  sizeBytes: z.number().int().nonnegative().optional(),
  mimeType: z.string().nullable().optional(),
  durationMs: z.number().int().nonnegative().nullable().optional(),
})
const ImportLearningObjectsFromBaiduNetdiskResultSchema = z.object({
  created_instances_count: z.number().int(),
  reused_instances_count: z.number().int(),
  created_learning_object_nodes_count: z.number().int(),
  imported_count: z.number().int(),
})

export function addLearningObjectLeaf(
  scope: ProjectScope,
  params: { parentId?: string | null; instanceId: string; title: string },
) {
  return apiRequest({
    path: projectApiPath(scope, "/learning-objects/leaf"),
    method: "POST",
    body: { parentId: params.parentId ?? null, instanceId: params.instanceId, title: params.title },
    responseSchema: AddLearningObjectResultSchema,
  })
}

export function addLearningObjectContainer(
  scope: ProjectScope,
  params: { parentId?: string | null; children: string[]; title: string },
) {
  return apiRequest({
    path: projectApiPath(scope, "/learning-objects/container"),
    method: "POST",
    body: { parentId: params.parentId ?? null, children: params.children, title: params.title },
    responseSchema: AddLearningObjectResultSchema,
  })
}

export function initializeBookLearningObjects(scope: ProjectScope, params: { items: { depth: number; title: string }[] }) {
  return apiRequest({
    path: projectApiPath(scope, "/initialize-book-learning-objects"),
    method: "POST",
    body: { items: params.items },
    responseSchema: InitializeBookLearningObjectsResultSchema,
  })
}

export function initializeBookLearningObjectsFromSubjectMaterial(scope: ProjectScope, params: { sourceMaterialId: string }) {
  return apiRequest({
    path: projectApiPath(scope, "/initialize-book-learning-objects-from-material"),
    method: "POST",
    body: { sourceMaterialId: params.sourceMaterialId },
    responseSchema: InitializeBookLearningObjectsResultSchema,
  })
}

export function getLearningObjectNode(scope: ProjectScope, nodeId: string) {
  return apiRequest({
    path: projectApiPath(scope, `/learning-objects/${nodeId}`),
    responseSchema: LearningObjectNodeSchema,
  })
}

export function listLearningObjectRoots(scope: ProjectScope) {
  return apiRequest({
    path: projectApiPath(scope, "/learning-object-roots"),
    responseSchema: LearningObjectRootsSchema,
  })
}

export function listLearningObjectNodes(scope: ProjectScope, options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: projectApiPath(scope, "/learning-object-nodes"),
    responseSchema: z.array(LearningObjectNodeSchema),
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export function importLearningObjectsFromBrowser(
  scope: ProjectScope,
  params: { rootTitle?: string; relativeFilePaths: string[] },
) {
  return apiRequest({
    path: projectApiPath(scope, "/import-learning-objects-from-browser"),
    method: "POST",
    body: {
      rootTitle: params.rootTitle,
      relativeFilePaths: params.relativeFilePaths,
    },
    responseSchema: ImportLearningObjectsFromBrowserResultSchema,
  })
}

export function importLearningObjectsFromBaiduNetdisk(
  scope: ProjectScope,
  params: {
    accountId: string
    items: Array<z.input<typeof BaiduNetdiskImportItemSchema>>
  },
) {
  return apiRequest({
    path: projectApiPath(scope, "/import-learning-objects-from-baidu-netdisk"),
    method: "POST",
    body: {
      accountId: params.accountId,
      items: params.items.map((item) => BaiduNetdiskImportItemSchema.parse(item)),
    },
    responseSchema: ImportLearningObjectsFromBaiduNetdiskResultSchema,
  })
}

export function listRecallPointsByLearningObjectNode(scope: ProjectScope, nodeId: string) {
  return apiRequest({
    path: projectApiPath(scope, `/learning-objects/${nodeId}/recall-points`),
    responseSchema: z.array(RecallPointSchema),
  })
}

export function exportRecallPointsByLearningObjectNode(scope: ProjectScope, nodeId: string) {
  return apiRequest({
    path: projectApiPath(scope, `/learning-objects/${nodeId}/exports/recall-points`),
    responseSchema: z.array(RecallPointSchema),
  })
}

export function exportAsrByLearningObjectNode(scope: ProjectScope, nodeId: string) {
  return apiRequest({
    path: projectApiPath(scope, `/learning-objects/${nodeId}/exports/asr`),
    responseSchema: z.array(AsrArtifactSchema),
  })
}

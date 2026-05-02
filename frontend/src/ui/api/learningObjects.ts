import { z } from "zod"

import { AsrArtifactSchema } from "@/ui/api/asr"
import { apiRequest, type ApiRequestExecutionOptions } from "@/ui/api/http"
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
  projectId: string,
  params: { parentId?: string | null; instanceId: string; title: string },
) {
  return apiRequest({
    path: `/projects/${projectId}/learning-objects/leaf`,
    method: "POST",
    body: { parentId: params.parentId ?? null, instanceId: params.instanceId, title: params.title },
    responseSchema: AddLearningObjectResultSchema,
  })
}

export function addLearningObjectContainer(
  projectId: string,
  params: { parentId?: string | null; children: string[]; title: string },
) {
  return apiRequest({
    path: `/projects/${projectId}/learning-objects/container`,
    method: "POST",
    body: { parentId: params.parentId ?? null, children: params.children, title: params.title },
    responseSchema: AddLearningObjectResultSchema,
  })
}

export function initializeBookLearningObjects(projectId: string, params: { items: { depth: number; title: string }[] }) {
  return apiRequest({
    path: `/projects/${projectId}/initialize-book-learning-objects`,
    method: "POST",
    body: { items: params.items },
    responseSchema: InitializeBookLearningObjectsResultSchema,
  })
}

export function initializeBookLearningObjectsFromSubjectMaterial(projectId: string, params: { sourceMaterialId: string }) {
  return apiRequest({
    path: `/projects/${projectId}/initialize-book-learning-objects-from-material`,
    method: "POST",
    body: { sourceMaterialId: params.sourceMaterialId },
    responseSchema: InitializeBookLearningObjectsResultSchema,
  })
}

export function getLearningObjectNode(projectId: string, nodeId: string) {
  return apiRequest({
    path: `/projects/${projectId}/learning-objects/${nodeId}`,
    responseSchema: LearningObjectNodeSchema,
  })
}

export function listLearningObjectRoots(projectId: string) {
  return apiRequest({
    path: `/projects/${projectId}/learning-object-roots`,
    responseSchema: LearningObjectRootsSchema,
  })
}

export function listLearningObjectNodes(projectId: string, options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: `/projects/${projectId}/learning-object-nodes`,
    responseSchema: z.array(LearningObjectNodeSchema),
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export function importLearningObjectsFromBrowser(
  projectId: string,
  params: { rootTitle?: string; relativeFilePaths: string[] },
) {
  return apiRequest({
    path: `/projects/${projectId}/import-learning-objects-from-browser`,
    method: "POST",
    body: {
      rootTitle: params.rootTitle,
      relativeFilePaths: params.relativeFilePaths,
    },
    responseSchema: ImportLearningObjectsFromBrowserResultSchema,
  })
}

export function importLearningObjectsFromBaiduNetdisk(
  projectId: string,
  params: {
    accountId: string
    items: Array<z.input<typeof BaiduNetdiskImportItemSchema>>
  },
) {
  return apiRequest({
    path: `/projects/${projectId}/import-learning-objects-from-baidu-netdisk`,
    method: "POST",
    body: {
      accountId: params.accountId,
      items: params.items,
    },
    responseSchema: ImportLearningObjectsFromBaiduNetdiskResultSchema,
  })
}

export function listRecallPointsByLearningObjectNode(projectId: string, nodeId: string) {
  return apiRequest({
    path: `/projects/${projectId}/learning-objects/${nodeId}/recall-points`,
    responseSchema: z.array(RecallPointSchema),
  })
}

export function exportRecallPointsByLearningObjectNode(projectId: string, nodeId: string) {
  return apiRequest({
    path: `/projects/${projectId}/learning-objects/${nodeId}/exports/recall-points`,
    responseSchema: z.array(RecallPointSchema),
  })
}

export function exportAsrByLearningObjectNode(projectId: string, nodeId: string) {
  return apiRequest({
    path: `/projects/${projectId}/learning-objects/${nodeId}/exports/asr`,
    responseSchema: z.array(AsrArtifactSchema),
  })
}

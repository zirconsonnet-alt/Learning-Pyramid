import { z } from "zod"

import { AsrArtifactSchema } from "@/ui/api/asr"
import { apiRequest } from "@/ui/api/http"
import { RecallPointSchema } from "@/ui/api/review"

export const LearningObjectLeafSchema = z.object({
  kind: z.literal("leaf"),
  projectId: z.string(),
  nodeId: z.string(),
  parentId: z.string().nullable(),
  instanceId: z.string(),
  title: z.string(),
})

export const LearningObjectContainerSchema = z.object({
  kind: z.literal("container"),
  projectId: z.string(),
  nodeId: z.string(),
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

export function listLearningObjectNodes(projectId: string) {
  return apiRequest({
    path: `/projects/${projectId}/learning-object-nodes`,
    responseSchema: z.array(LearningObjectNodeSchema),
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

import { z } from "zod"

import { AsrArtifactSchema } from "@/ui/api/asr"
import { apiRequest, type ApiRequestExecutionOptions } from "@/ui/api/http"
import { RecallPointSchema } from "@/ui/api/review"

export const LearningTaskLeafSchema = z.object({
  kind: z.literal("leaf"),
  projectId: z.string(),
  nodeId: z.string(),
  parentId: z.string().nullable(),
  boundLearningTaskId: z.string(),
  title: z.string(),
})

export const LearningTaskContainerSchema = z.object({
  kind: z.literal("container"),
  projectId: z.string(),
  nodeId: z.string(),
  parentId: z.string().nullable(),
  children: z.array(z.string()),
  title: z.string(),
  nodeOrigin: z.enum(["AGGREGATION", "OBJECT_MIRROR"]).default("AGGREGATION"),
  boundLearningObjectNodeId: z.string().nullable().optional().default(null),
  objectMirrorStatus: z.enum(["ACTIVE", "ORPHANED"]).nullable().optional().default(null),
})

export const LearningTaskNodeSchema = z.discriminatedUnion("kind", [
  LearningTaskLeafSchema,
  LearningTaskContainerSchema,
])
export type LearningTaskNode = z.infer<typeof LearningTaskNodeSchema>

export const LearningTaskNodeBindingSchema = z.object({
  projectId: z.string(),
  reviewChainId: z.string(),
  entryNodeId: z.string(),
  entryNodeTitle: z.string(),
  entryNodeKind: z.enum(["leaf", "container"]),
  learningTaskId: z.string().nullable(),
  learningTaskTitle: z.string().nullable(),
  childCount: z.number().int().nullable(),
  targetLayerIndex: z.number().int(),
})
export type LearningTaskNodeBinding = z.infer<typeof LearningTaskNodeBindingSchema>

export function getLearningTaskNode(projectId: string, nodeId: string) {
  return apiRequest({
    path: `/projects/${projectId}/learning-task-nodes/${nodeId}`,
    responseSchema: LearningTaskNodeSchema,
  })
}

export function listLearningTaskNodes(projectId: string, options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: `/projects/${projectId}/learning-task-nodes`,
    responseSchema: z.array(LearningTaskNodeSchema),
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export function getLearningTaskNodeBinding(projectId: string, nodeId: string) {
  return apiRequest({
    path: `/projects/${projectId}/learning-task-nodes/${nodeId}/binding`,
    responseSchema: LearningTaskNodeBindingSchema,
  })
}

export function editLearningTaskNode(projectId: string, nodeId: string, title: string) {
  return apiRequest({
    path: `/projects/${projectId}/learning-task-nodes/${nodeId}`,
    method: "PATCH",
    body: { title },
    responseSchema: z.null(),
  })
}

export function listRecallPointsByLearningTaskNode(projectId: string, nodeId: string) {
  return apiRequest({
    path: `/projects/${projectId}/learning-task-nodes/${nodeId}/recall-points`,
    responseSchema: z.array(RecallPointSchema),
  })
}

export function exportRecallPointsByLearningTaskNode(projectId: string, nodeId: string) {
  return apiRequest({
    path: `/projects/${projectId}/learning-task-nodes/${nodeId}/exports/recall-points`,
    responseSchema: z.array(RecallPointSchema),
  })
}

export function exportAsrByLearningTaskNode(projectId: string, nodeId: string) {
  return apiRequest({
    path: `/projects/${projectId}/learning-task-nodes/${nodeId}/exports/asr`,
    responseSchema: z.array(AsrArtifactSchema),
  })
}

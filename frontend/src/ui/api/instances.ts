import { z } from "zod"

import { apiRequest, type ApiRequestExecutionOptions } from "@/ui/api/http"

export const InstanceMediaSourceKindSchema = z.enum(["SERVER_FS", "BROWSER_LOCAL", "NATIVE_LOCAL", "MANUAL", "BAIDU_NETDISK"])
export type InstanceMediaSourceKind = z.infer<typeof InstanceMediaSourceKindSchema>

export const InstancePlaybackKindSchema = z.enum(["FILE", "HLS"])
export type InstancePlaybackKind = z.infer<typeof InstancePlaybackKindSchema>

export const InstanceSchema = z.object({
  instanceId: z.string(),
  materialId: z.string(),
  materialDisplayName: z.string(),
  presence: z.enum(["PRESENT", "MISSING"]).nullable().optional().default("PRESENT"),
  lastSeenAt: z.string().nullable().optional().default(null),
  mediaSourceKind: InstanceMediaSourceKindSchema.nullable().optional().default(null),
  playbackKind: InstancePlaybackKindSchema.nullable().optional().default(null),
  durationMs: z.number().int().nonnegative().nullable().optional().default(null),
})
export type Instance = z.infer<typeof InstanceSchema>

const InstanceListSchema = z.array(InstanceSchema)
const AddInstanceResultSchema = z.object({ instanceId: z.string() })
const MissingInstancesSchema = z.object({ instanceIds: z.array(z.string()) })
const RecallPointIdsByInstanceSchema = z.object({ recallPointIds: z.array(z.string()) })
const BulkRemapRecallPointsResultSchema = z.object({ movedCount: z.number().int() })

export function listInstances(projectId: string, options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: `/projects/${projectId}/instances`,
    responseSchema: InstanceListSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export function listMissingInstances(projectId: string, options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: `/projects/${projectId}/missing-instances`,
    responseSchema: MissingInstancesSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export function listRecallPointsByInstance(projectId: string, instanceId: string, options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: `/projects/${projectId}/instances/${instanceId}/recall-points`,
    responseSchema: RecallPointIdsByInstanceSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export function bulkRemapRecallPointsInstance(
  projectId: string,
  params: { fromInstanceId: string; toInstanceId: string; recallPointIds?: string[] },
) {
  return apiRequest({
    path: `/projects/${projectId}/instances/remap-recall-points`,
    method: "POST",
    body: {
      fromInstanceId: params.fromInstanceId,
      toInstanceId: params.toInstanceId,
      recallPointIds: params.recallPointIds,
    },
    responseSchema: BulkRemapRecallPointsResultSchema,
  })
}

export function addInstance(projectId: string, materialId: string) {
  return apiRequest({
    path: `/projects/${projectId}/instances`,
    method: "POST",
    body: { materialId },
    responseSchema: AddInstanceResultSchema,
  })
}

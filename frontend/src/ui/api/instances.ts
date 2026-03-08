import { z } from "zod"

import { apiRequest } from "@/ui/api/http"

export const InstanceSchema = z.object({
  instanceId: z.string(),
  materialId: z.string(),
  materialDisplayName: z.string(),
  presence: z.enum(["PRESENT", "MISSING"]).nullable().optional().default("PRESENT"),
  lastSeenAt: z.string().nullable().optional().default(null),
})
export type Instance = z.infer<typeof InstanceSchema>

const InstanceListSchema = z.array(InstanceSchema)
const AddInstanceResultSchema = z.object({ instanceId: z.string() })
const MissingInstancesSchema = z.object({ instanceIds: z.array(z.string()) })
const RecallPointIdsByInstanceSchema = z.object({ recallPointIds: z.array(z.string()) })
const BulkRemapRecallPointsResultSchema = z.object({ movedCount: z.number().int() })

export function listInstances(projectId: string) {
  return apiRequest({ path: `/projects/${projectId}/instances`, responseSchema: InstanceListSchema })
}

export function listMissingInstances(projectId: string) {
  return apiRequest({ path: `/projects/${projectId}/missing-instances`, responseSchema: MissingInstancesSchema })
}

export function listRecallPointsByInstance(projectId: string, instanceId: string) {
  return apiRequest({
    path: `/projects/${projectId}/instances/${instanceId}/recall-points`,
    responseSchema: RecallPointIdsByInstanceSchema,
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

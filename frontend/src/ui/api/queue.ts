import { z } from "zod"

import { apiRequest, type ApiRequestExecutionOptions } from "@/ui/api/http"

export const QueueSchema = z.object({
  headId: z.string().nullable(),
  ids: z.array(z.string()),
})
export type Queue = z.infer<typeof QueueSchema>

export function getQueue(projectId: string, options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: `/projects/${projectId}/queue`,
    responseSchema: QueueSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

import { z } from "zod"

import { apiRequest, type ApiRequestExecutionOptions } from "@/ui/api/http"
import { projectApiPath, type ProjectScope } from "@/ui/api/projectScope"

export const QueueSchema = z.object({
  headId: z.string().nullable(),
  ids: z.array(z.string()),
})
export type Queue = z.infer<typeof QueueSchema>

export function getQueue(scope: ProjectScope, options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: projectApiPath(scope, "/queue"),
    responseSchema: QueueSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

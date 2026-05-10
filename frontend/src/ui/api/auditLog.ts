import { z } from "zod"

import { apiRequest, type ApiRequestExecutionOptions } from "@/ui/api/http"
import { projectApiPath, type ProjectScope } from "@/ui/api/projectScope"

export const AuditLogEventSchema = z.object({
  projectId: z.string(),
  eventId: z.string(),
  occurredAt: z.string(),
  kind: z.string(),
  apiName: z.string(),
  result: z.string(),
  payload: z.string(),
})
export type AuditLogEvent = z.infer<typeof AuditLogEventSchema>

export function listAuditLogEvents(scope: ProjectScope, options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: projectApiPath(scope, "/audit-log-events"),
    responseSchema: z.array(AuditLogEventSchema),
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

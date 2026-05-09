import { z } from "zod"

import { apiRequest, type ApiRequestExecutionOptions } from "@/ui/api/http"

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

export function listAuditLogEvents(projectId: string, options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: `/projects/${projectId}/audit-log-events`,
    responseSchema: z.array(AuditLogEventSchema),
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export function listScopedAuditLogEvents(subjectId: string, projectId: string, options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: `/subjects/${subjectId}/projects/${projectId}/audit-log-events`,
    responseSchema: z.array(AuditLogEventSchema),
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

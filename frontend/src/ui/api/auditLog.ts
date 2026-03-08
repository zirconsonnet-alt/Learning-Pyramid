import { z } from "zod"

import { apiRequest } from "@/ui/api/http"

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

export function listAuditLogEvents(projectId: string) {
  return apiRequest({
    path: `/projects/${projectId}/audit-log-events`,
    responseSchema: z.array(AuditLogEventSchema),
  })
}


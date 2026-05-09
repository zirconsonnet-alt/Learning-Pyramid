import { useQuery } from "@tanstack/react-query"

import { listAuditLogEvents, listScopedAuditLogEvents } from "@/ui/api/auditLog"

const AUDIT_LOG_QUERY_TIMEOUT_MS = 90_000

export function useAuditLogEvents(projectId: string) {
  return useQuery({
    queryKey: ["auditLogEvents", projectId],
    queryFn: ({ signal }) => listAuditLogEvents(projectId, { signal, timeoutMs: AUDIT_LOG_QUERY_TIMEOUT_MS }),
    enabled: !!projectId,
    refetchInterval: 5000,
  })
}

export function useScopedAuditLogEvents(subjectId: string, projectId: string) {
  return useQuery({
    queryKey: ["auditLogEvents", subjectId, projectId],
    queryFn: ({ signal }) => listScopedAuditLogEvents(subjectId, projectId, { signal, timeoutMs: AUDIT_LOG_QUERY_TIMEOUT_MS }),
    enabled: !!subjectId && !!projectId,
    refetchInterval: 5000,
  })
}

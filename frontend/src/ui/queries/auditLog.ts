import { useQuery } from "@tanstack/react-query"

import { listAuditLogEvents } from "@/ui/api/auditLog"
import type { ScopedProjectRef } from "@/ui/api/projectScope"

const AUDIT_LOG_QUERY_TIMEOUT_MS = 90_000

export function useAuditLogEvents(scope: ScopedProjectRef | null) {
  return useQuery({
    queryKey: ["auditLogEvents", scope?.subjectId ?? "", scope?.scopedProjectId ?? ""],
    queryFn: ({ signal }) => listAuditLogEvents(scope as ScopedProjectRef, { signal, timeoutMs: AUDIT_LOG_QUERY_TIMEOUT_MS }),
    enabled: !!scope?.subjectId && !!scope.scopedProjectId,
    refetchInterval: 5000,
  })
}

export function useScopedAuditLogEvents(subjectId: string, projectId: string) {
  const scope = subjectId && projectId ? { subjectId, scopedProjectId: projectId } : null
  return useQuery({
    queryKey: ["auditLogEvents", subjectId, projectId],
    queryFn: ({ signal }) => listAuditLogEvents(scope as ScopedProjectRef, { signal, timeoutMs: AUDIT_LOG_QUERY_TIMEOUT_MS }),
    enabled: !!scope,
    refetchInterval: 5000,
  })
}

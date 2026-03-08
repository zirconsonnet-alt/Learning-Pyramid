import { useQuery } from "@tanstack/react-query"

import { listAuditLogEvents } from "@/ui/api/auditLog"

export function useAuditLogEvents(projectId: string) {
  return useQuery({
    queryKey: ["auditLogEvents", projectId],
    queryFn: () => listAuditLogEvents(projectId),
    enabled: !!projectId,
    refetchInterval: 5000,
  })
}


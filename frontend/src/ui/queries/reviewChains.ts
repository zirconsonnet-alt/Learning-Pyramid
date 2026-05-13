import { useQuery } from "@tanstack/react-query"

import type { ScopedProjectRef } from "@/ui/api/projectScope"
import { getConvergence, getReviewChain, getReviewChainBinding } from "@/ui/api/review"

export function useReviewChain(scope: ScopedProjectRef | null, reviewChainId: string) {
  const projectId = scope?.scopedProjectId ?? ""
  return useQuery({
    queryKey: ["reviewChain", scope?.subjectId ?? "", projectId, reviewChainId],
    queryFn: () => getReviewChain(scope as ScopedProjectRef, reviewChainId),
    enabled: !!scope?.subjectId && !!projectId && !!reviewChainId,
  })
}

export function useReviewChainBinding(scope: ScopedProjectRef | null, reviewChainId: string) {
  const projectId = scope?.scopedProjectId ?? ""
  return useQuery({
    queryKey: ["reviewChainBinding", scope?.subjectId ?? "", projectId, reviewChainId],
    queryFn: () => getReviewChainBinding(scope as ScopedProjectRef, reviewChainId),
    enabled: !!scope?.subjectId && !!projectId && !!reviewChainId,
  })
}

export function useConvergence(scope: ScopedProjectRef | null, convergenceId: string) {
  const projectId = scope?.scopedProjectId ?? ""
  return useQuery({
    queryKey: ["convergence", scope?.subjectId ?? "", projectId, convergenceId],
    queryFn: () => getConvergence(scope as ScopedProjectRef, convergenceId),
    enabled: !!scope?.subjectId && !!projectId && !!convergenceId,
  })
}

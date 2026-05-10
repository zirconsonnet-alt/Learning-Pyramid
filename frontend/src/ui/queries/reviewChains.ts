import { useQuery } from "@tanstack/react-query"

import type { ProjectScope } from "@/ui/api/projectScope"
import { getConvergence, getReviewChain, getReviewChainBinding } from "@/ui/api/review"

export function useReviewChain(scope: ProjectScope | null, reviewChainId: string) {
  const projectId = scope?.projectId ?? ""
  return useQuery({
    queryKey: ["reviewChain", scope?.subjectId ?? "", projectId, reviewChainId],
    queryFn: () => getReviewChain(scope as ProjectScope, reviewChainId),
    enabled: !!scope?.subjectId && !!projectId && !!reviewChainId,
  })
}

export function useReviewChainBinding(scope: ProjectScope | null, reviewChainId: string) {
  const projectId = scope?.projectId ?? ""
  return useQuery({
    queryKey: ["reviewChainBinding", scope?.subjectId ?? "", projectId, reviewChainId],
    queryFn: () => getReviewChainBinding(scope as ProjectScope, reviewChainId),
    enabled: !!scope?.subjectId && !!projectId && !!reviewChainId,
  })
}

export function useConvergence(scope: ProjectScope | null, convergenceId: string) {
  const projectId = scope?.projectId ?? ""
  return useQuery({
    queryKey: ["convergence", scope?.subjectId ?? "", projectId, convergenceId],
    queryFn: () => getConvergence(scope as ProjectScope, convergenceId),
    enabled: !!scope?.subjectId && !!projectId && !!convergenceId,
  })
}

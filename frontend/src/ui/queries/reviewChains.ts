import { useQuery } from "@tanstack/react-query"

import { getConvergence, getReviewChain, getReviewChainBinding } from "@/ui/api/review"

export function useReviewChain(projectId: string, reviewChainId: string) {
  return useQuery({
    queryKey: ["reviewChain", projectId, reviewChainId],
    queryFn: () => getReviewChain(projectId, reviewChainId),
    enabled: !!projectId && !!reviewChainId,
  })
}

export function useReviewChainBinding(projectId: string, reviewChainId: string) {
  return useQuery({
    queryKey: ["reviewChainBinding", projectId, reviewChainId],
    queryFn: () => getReviewChainBinding(projectId, reviewChainId),
    enabled: !!projectId && !!reviewChainId,
  })
}

export function useConvergence(projectId: string, convergenceId: string) {
  return useQuery({
    queryKey: ["convergence", projectId, convergenceId],
    queryFn: () => getConvergence(projectId, convergenceId),
    enabled: !!projectId && !!convergenceId,
  })
}

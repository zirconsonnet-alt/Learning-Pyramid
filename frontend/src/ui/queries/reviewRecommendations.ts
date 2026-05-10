import { useQuery } from "@tanstack/react-query"

import type { ProjectScope } from "@/ui/api/projectScope"
import { getRecallPointReviewProjection, listAllReviewRecommendations, listReviewRecommendations } from "@/ui/api/review"

export function useReviewRecommendations(scope: ProjectScope | null, params?: { offset?: number; limit?: number }) {
  const projectId = scope?.projectId ?? ""
  return useQuery({
    queryKey: ["reviewRecommendations", scope?.subjectId ?? "", projectId, params?.offset ?? 0, params?.limit ?? null],
    queryFn: () => listReviewRecommendations(scope as ProjectScope, params),
    enabled: !!scope?.subjectId && !!projectId,
  })
}

export function useAllReviewRecommendations(scope: ProjectScope | null) {
  const projectId = scope?.projectId ?? ""
  return useQuery({
    queryKey: ["allReviewRecommendations", scope?.subjectId ?? "", projectId],
    queryFn: () => listAllReviewRecommendations(scope as ProjectScope),
    enabled: !!scope?.subjectId && !!projectId,
  })
}

export function useRecallPointReviewProjection(scope: ProjectScope | null, recallPointId: string) {
  const projectId = scope?.projectId ?? ""
  return useQuery({
    queryKey: ["recallPointReviewProjection", scope?.subjectId ?? "", projectId, recallPointId],
    queryFn: () => getRecallPointReviewProjection(scope as ProjectScope, recallPointId),
    enabled: !!scope?.subjectId && !!projectId && !!recallPointId,
  })
}

import { useQuery } from "@tanstack/react-query"

import type { ScopedProjectRef } from "@/ui/api/projectScope"
import { getRecallPointReviewProjection, listAllReviewRecommendations, listReviewRecommendations } from "@/ui/api/review"

export function useReviewRecommendations(scope: ScopedProjectRef | null, params?: { offset?: number; limit?: number }) {
  const projectId = scope?.scopedProjectId ?? ""
  return useQuery({
    queryKey: ["reviewRecommendations", scope?.subjectId ?? "", projectId, params?.offset ?? 0, params?.limit ?? null],
    queryFn: () => listReviewRecommendations(scope as ScopedProjectRef, params),
    enabled: !!scope?.subjectId && !!projectId,
  })
}

export function useAllReviewRecommendations(scope: ScopedProjectRef | null) {
  const projectId = scope?.scopedProjectId ?? ""
  return useQuery({
    queryKey: ["allReviewRecommendations", scope?.subjectId ?? "", projectId],
    queryFn: () => listAllReviewRecommendations(scope as ScopedProjectRef),
    enabled: !!scope?.subjectId && !!projectId,
  })
}

export function useRecallPointReviewProjection(scope: ScopedProjectRef | null, recallPointId: string) {
  const projectId = scope?.scopedProjectId ?? ""
  return useQuery({
    queryKey: ["recallPointReviewProjection", scope?.subjectId ?? "", projectId, recallPointId],
    queryFn: () => getRecallPointReviewProjection(scope as ScopedProjectRef, recallPointId),
    enabled: !!scope?.subjectId && !!projectId && !!recallPointId,
  })
}

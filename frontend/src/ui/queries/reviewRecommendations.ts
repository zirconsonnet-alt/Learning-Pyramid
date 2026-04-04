import { useQuery } from "@tanstack/react-query"

import { getRecallPointReviewProjection, listReviewRecommendations } from "@/ui/api/review"

export function useReviewRecommendations(projectId: string, params?: { offset?: number; limit?: number }) {
  return useQuery({
    queryKey: ["reviewRecommendations", projectId, params?.offset ?? 0, params?.limit ?? null],
    queryFn: () => listReviewRecommendations(projectId, params),
    enabled: !!projectId,
  })
}

export function useRecallPointReviewProjection(projectId: string, recallPointId: string) {
  return useQuery({
    queryKey: ["recallPointReviewProjection", projectId, recallPointId],
    queryFn: () => getRecallPointReviewProjection(projectId, recallPointId),
    enabled: !!projectId && !!recallPointId,
  })
}

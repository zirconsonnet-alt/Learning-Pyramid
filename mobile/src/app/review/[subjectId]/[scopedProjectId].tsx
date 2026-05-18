import { useMemo } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useLocalSearchParams } from "expo-router"

import { useLearningPyramidApi } from "../../../api/ApiProvider"
import { toErrorMessage } from "../../../api/errorMessage"
import { firstRouteParam } from "../../../routing/params"
import { ReviewQueueScreen } from "../../../screens/ReviewQueueScreen"

export default function ReviewRoute() {
  const api = useLearningPyramidApi()
  const queryClient = useQueryClient()
  const params = useLocalSearchParams<{ subjectId: string; scopedProjectId: string }>()
  const subjectId = firstRouteParam(params.subjectId) ?? ""
  const scopedProjectId = firstRouteParam(params.scopedProjectId) ?? ""
  const scope = { subjectId, scopedProjectId }
  const hasScope = Boolean(subjectId && scopedProjectId)

  const queueQ = useQuery({
    queryKey: ["review-queue", subjectId, scopedProjectId],
    queryFn: () => api.review.getQueue(scope),
    enabled: hasScope,
  })
  const reviewTaskId = queueQ.data?.headId ?? null
  const taskQ = useQuery({
    queryKey: ["review-task", subjectId, scopedProjectId, reviewTaskId],
    queryFn: () => api.review.getReviewTask(scope, reviewTaskId ?? ""),
    enabled: hasScope && Boolean(reviewTaskId),
  })
  const rangeQ = useQuery({
    queryKey: ["review-range", subjectId, scopedProjectId, taskQ.data?.inputRangeId ?? ""],
    queryFn: () => api.review.getRangeSnapshot(scope, taskQ.data?.inputRangeId ?? ""),
    enabled: hasScope && Boolean(taskQ.data?.inputRangeId),
  })
  const recallPointsQ = useQuery({
    queryKey: ["review-recall-points", subjectId, scopedProjectId],
    queryFn: () => api.review.listRecallPoints(scope),
    enabled: hasScope && Boolean(rangeQ.data),
  })
  const commitReview = useMutation({
    mutationFn: (params: { reviewTaskId: string; canRecall: number[] }) =>
      api.review.commitReviewTask(scope, params.reviewTaskId, { canRecall: params.canRecall }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["review-queue", subjectId, scopedProjectId] }),
        queryClient.invalidateQueries({ queryKey: ["review-task", subjectId, scopedProjectId] }),
        queryClient.invalidateQueries({ queryKey: ["review-recall-points", subjectId, scopedProjectId] }),
      ])
    },
  })

  const recallPointIds = rangeQ.data?.recallPointIds ?? []
  const recallPoints = useMemo(() => {
    const byId = new Map((recallPointsQ.data ?? []).map((item) => [item.recallPointId, item]))
    return recallPointIds.map((id) => byId.get(id)).filter((item): item is NonNullable<typeof item> => Boolean(item))
  }, [recallPointIds, recallPointsQ.data])
  const missingRecallPoint = Boolean(rangeQ.data && recallPointsQ.data && recallPoints.length !== recallPointIds.length)
  const errorMessage =
    (queueQ.isError ? toErrorMessage(queueQ.error, "复习队列加载失败") : null) ??
    (taskQ.isError ? toErrorMessage(taskQ.error, "复习任务加载失败") : null) ??
    (rangeQ.isError ? toErrorMessage(rangeQ.error, "复习范围加载失败") : null) ??
    (recallPointsQ.isError ? toErrorMessage(recallPointsQ.error, "复述点加载失败") : null) ??
    (commitReview.isError ? toErrorMessage(commitReview.error, "复习提交失败") : null) ??
    (missingRecallPoint ? "复习内容加载不完整" : null)
  const loading =
    queueQ.isLoading ||
    (Boolean(reviewTaskId) && taskQ.isLoading) ||
    (Boolean(taskQ.data?.inputRangeId) && rangeQ.isLoading) ||
    (Boolean(rangeQ.data) && recallPointsQ.isLoading)

  return (
    <ReviewQueueScreen
      committing={commitReview.isPending}
      errorMessage={errorMessage}
      loading={loading}
      onCommit={(params) => commitReview.mutate(params)}
      recallPointIds={recallPointIds}
      recallPoints={recallPoints}
      reviewTaskId={reviewTaskId}
      submitted={commitReview.isSuccess}
    />
  )
}

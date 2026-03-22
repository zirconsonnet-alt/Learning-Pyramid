import { useQueries, useQuery } from "@tanstack/react-query"

import { getLearningTask } from "@/ui/api/learningTasks"
import { getConvergence, getRangeSnapshot, getRecallPoint, getReviewChain, getReviewTask, type Convergence, type ReviewChain } from "@/ui/api/review"

function collectReviewTaskIdsFromChain(chain: ReviewChain | undefined, convergences: readonly (Convergence | undefined)[]) {
  if (!chain) return [] as string[]

  const convergenceById = new Map<string, Convergence>()
  for (const convergence of convergences) {
    if (convergence) convergenceById.set(convergence.convergenceId, convergence)
  }

  const reviewTaskIds: string[] = []
  const seen = new Set<string>()

  for (const item of chain.queue) {
    const itemReviewTaskIds = item.kind === "REVIEW_TASK" ? [item.id] : (convergenceById.get(item.id)?.reviewTaskIds ?? [])
    for (const reviewTaskId of itemReviewTaskIds) {
      if (seen.has(reviewTaskId)) continue
      seen.add(reviewTaskId)
      reviewTaskIds.push(reviewTaskId)
    }
  }

  return reviewTaskIds
}

export function useLearningTaskReviewTasks(projectId: string, learningTaskId: string) {
  const taskQ = useQuery({
    queryKey: ["learningTask", projectId, learningTaskId],
    queryFn: () => getLearningTask(projectId, learningTaskId),
    enabled: !!projectId && !!learningTaskId,
  })

  const reviewChainId = taskQ.data?.reviewChainId ?? ""
  const chainQ = useQuery({
    queryKey: ["reviewChain", projectId, reviewChainId],
    queryFn: () => getReviewChain(projectId, reviewChainId),
    enabled: !!projectId && !!reviewChainId,
  })

  const convergenceIds = chainQ.data?.queue.filter((item) => item.kind === "CONVERGENCE").map((item) => item.id) ?? []
  const convergenceQs = useQueries({
    queries: convergenceIds.map((convergenceId) => ({
      queryKey: ["convergence", projectId, convergenceId],
      queryFn: () => getConvergence(projectId, convergenceId),
      enabled: !!projectId,
    })),
  })

  const reviewTaskIds = collectReviewTaskIdsFromChain(
    chainQ.data,
    convergenceQs.map((query) => query.data as Convergence | undefined),
  )

  const reviewTaskQs = useQueries({
    queries: reviewTaskIds.map((reviewTaskId) => ({
      queryKey: ["reviewTask", projectId, reviewTaskId],
      queryFn: () => getReviewTask(projectId, reviewTaskId),
      enabled: !!projectId,
    })),
  })

  return {
    taskQ,
    chainQ,
    convergenceQs,
    reviewTaskIds,
    reviewTaskQs,
  }
}

export function useReviewTaskDetails(projectId: string, reviewTaskId: string) {
  const reviewTaskQ = useQuery({
    queryKey: ["reviewTask", projectId, reviewTaskId],
    queryFn: () => getReviewTask(projectId, reviewTaskId),
    enabled: !!projectId && !!reviewTaskId,
  })

  const inputRangeId = reviewTaskQ.data?.inputRangeId ?? ""
  const inputRangeQ = useQuery({
    queryKey: ["range", projectId, inputRangeId],
    queryFn: () => getRangeSnapshot(projectId, inputRangeId),
    enabled: !!projectId && !!inputRangeId,
  })

  const resultRangeId = reviewTaskQ.data?.resultRangeId ?? ""
  const resultRangeQ = useQuery({
    queryKey: ["range", projectId, resultRangeId],
    queryFn: () => getRangeSnapshot(projectId, resultRangeId),
    enabled: !!projectId && !!resultRangeId,
  })

  const recallPointIds = inputRangeQ.data?.recallPointIds ?? []
  const recallPointQs = useQueries({
    queries: recallPointIds.map((recallPointId) => ({
      queryKey: ["recallPoint", projectId, recallPointId],
      queryFn: () => getRecallPoint(projectId, recallPointId),
      enabled: !!projectId,
    })),
  })

  return {
    reviewTaskQ,
    inputRangeQ,
    resultRangeQ,
    recallPointQs,
  }
}

import { useQueries, useQuery } from "@tanstack/react-query"

import { getLearningTask } from "@/ui/api/learningTasks"
import type { ScopedProjectRef } from "@/ui/api/projectScope"
import {
  getConvergence,
  getRangeSnapshot,
  getRecallPoint,
  getReviewChain,
  getReviewTask,
  getReviewTaskBinding,
  type Convergence,
  type ReviewChain,
} from "@/ui/api/review"

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

export function useLearningTaskReviewTasks(scope: ScopedProjectRef | null, learningTaskId: string) {
  const projectId = scope?.scopedProjectId ?? ""
  const taskQ = useQuery({
    queryKey: ["learningTask", scope?.subjectId ?? "", projectId, learningTaskId],
    queryFn: () => getLearningTask(scope as ScopedProjectRef, learningTaskId),
    enabled: !!scope?.subjectId && !!projectId && !!learningTaskId,
  })

  const reviewChainId = taskQ.data?.reviewChainId ?? ""
  const chainQ = useQuery({
    queryKey: ["reviewChain", scope?.subjectId ?? "", projectId, reviewChainId],
    queryFn: () => getReviewChain(scope as ScopedProjectRef, reviewChainId),
    enabled: !!scope?.subjectId && !!projectId && !!reviewChainId,
  })

  const convergenceIds = chainQ.data?.queue.filter((item) => item.kind === "CONVERGENCE").map((item) => item.id) ?? []
  const convergenceQs = useQueries({
    queries: convergenceIds.map((convergenceId) => ({
      queryKey: ["convergence", scope?.subjectId ?? "", projectId, convergenceId],
      queryFn: () => getConvergence(scope as ScopedProjectRef, convergenceId),
      enabled: !!scope?.subjectId && !!projectId,
    })),
  })

  const reviewTaskIds = collectReviewTaskIdsFromChain(
    chainQ.data,
    convergenceQs.map((query) => query.data as Convergence | undefined),
  )

  const reviewTaskQs = useQueries({
    queries: reviewTaskIds.map((reviewTaskId) => ({
      queryKey: ["reviewTask", scope?.subjectId ?? "", projectId, reviewTaskId],
      queryFn: () => getReviewTask(scope as ScopedProjectRef, reviewTaskId),
      enabled: !!scope?.subjectId && !!projectId,
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

export function useReviewTaskDetails(scope: ScopedProjectRef | null, reviewTaskId: string) {
  const projectId = scope?.scopedProjectId ?? ""
  const reviewTaskQ = useQuery({
    queryKey: ["reviewTask", scope?.subjectId ?? "", projectId, reviewTaskId],
    queryFn: () => getReviewTask(scope as ScopedProjectRef, reviewTaskId),
    enabled: !!scope?.subjectId && !!projectId && !!reviewTaskId,
  })

  const reviewTaskBindingQ = useQuery({
    queryKey: ["reviewTaskBinding", scope?.subjectId ?? "", projectId, reviewTaskId],
    queryFn: () => getReviewTaskBinding(scope as ScopedProjectRef, reviewTaskId),
    enabled: !!scope?.subjectId && !!projectId && !!reviewTaskId,
  })

  const inputRangeId = reviewTaskQ.data?.inputRangeId ?? ""
  const inputRangeQ = useQuery({
    queryKey: ["range", scope?.subjectId ?? "", projectId, inputRangeId],
    queryFn: () => getRangeSnapshot(scope as ScopedProjectRef, inputRangeId),
    enabled: !!scope?.subjectId && !!projectId && !!inputRangeId,
  })

  const resultRangeId = reviewTaskQ.data?.resultRangeId ?? ""
  const resultRangeQ = useQuery({
    queryKey: ["range", scope?.subjectId ?? "", projectId, resultRangeId],
    queryFn: () => getRangeSnapshot(scope as ScopedProjectRef, resultRangeId),
    enabled: !!scope?.subjectId && !!projectId && !!resultRangeId,
  })

  const recallPointIds = inputRangeQ.data?.recallPointIds ?? []
  const recallPointQs = useQueries({
    queries: recallPointIds.map((recallPointId) => ({
      queryKey: ["recallPoint", scope?.subjectId ?? "", projectId, recallPointId],
      queryFn: () => getRecallPoint(scope as ScopedProjectRef, recallPointId),
      enabled: !!scope?.subjectId && !!projectId,
    })),
  })

  return {
    reviewTaskQ,
    reviewTaskBindingQ,
    inputRangeQ,
    resultRangeQ,
    recallPointQs,
  }
}

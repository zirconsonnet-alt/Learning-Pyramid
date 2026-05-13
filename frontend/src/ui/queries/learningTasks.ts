import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { ApiError } from "@/ui/api/http"
import { editLearningTask, getLearningTask } from "@/ui/api/learningTasks"
import { editLearningTaskNode, getLearningTaskNode, getLearningTaskNodeBinding, listLearningTaskNodes } from "@/ui/api/learningTaskNodes"
import type { ScopedProjectRef } from "@/ui/api/projectScope"
import { isVirtualStudyReviewProjectId } from "@/ui/guideWalkthrough/guideVirtualProjectIds"
import { getVirtualStudyReviewLearningTaskNodes } from "@/ui/guideWalkthrough/virtualStudyReviewProject"

const LEARNING_TASK_QUERY_TIMEOUT_MS = 90_000

export function useLearningTask(scope: ScopedProjectRef | null, learningTaskId: string) {
  const projectId = scope?.scopedProjectId ?? ""
  return useQuery({
    queryKey: ["learningTask", scope?.subjectId ?? "", projectId, learningTaskId],
    queryFn: () => getLearningTask(scope as ScopedProjectRef, learningTaskId),
    enabled: !!scope?.subjectId && !!projectId && !!learningTaskId,
  })
}

export function useLearningTaskNode(scope: ScopedProjectRef | null, nodeId: string) {
  const projectId = scope?.scopedProjectId ?? ""
  return useQuery({
    queryKey: ["learningTaskNode", scope?.subjectId ?? "", projectId, nodeId],
    queryFn: () => getLearningTaskNode(scope as ScopedProjectRef, nodeId),
    enabled: !!scope?.subjectId && !!projectId && !!nodeId,
  })
}

export function useLearningTaskNodes(scope: ScopedProjectRef | null) {
  const projectId = scope?.scopedProjectId ?? ""
  return useQuery({
    queryKey: ["learningTaskNodes", scope?.subjectId ?? "", projectId],
    queryFn: ({ signal }) =>
      isVirtualStudyReviewProjectId(projectId)
        ? getVirtualStudyReviewLearningTaskNodes()
        : listLearningTaskNodes(scope as ScopedProjectRef, { signal, timeoutMs: LEARNING_TASK_QUERY_TIMEOUT_MS }),
    enabled: !!scope?.subjectId && !!projectId,
  })
}

export function useLearningTaskNodeBinding(scope: ScopedProjectRef | null, nodeId: string) {
  const projectId = scope?.scopedProjectId ?? ""
  return useQuery({
    queryKey: ["learningTaskNodeBinding", scope?.subjectId ?? "", projectId, nodeId],
    queryFn: async () => {
      try {
        return await getLearningTaskNodeBinding(scope as ScopedProjectRef, nodeId)
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null
        throw err
      }
    },
    enabled: !!scope?.subjectId && !!projectId && !!nodeId,
    retry: false,
  })
}

export function useEditLearningTask(scope: ScopedProjectRef | null, learningTaskId: string) {
  const projectId = scope?.scopedProjectId ?? ""
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (title: string) => editLearningTask(scope as ScopedProjectRef, learningTaskId, title),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["learningTask", projectId, learningTaskId] }),
        qc.invalidateQueries({ queryKey: ["learningTaskNodes", projectId] }),
        qc.invalidateQueries({ queryKey: ["learningTaskNode", projectId] }),
        qc.invalidateQueries({ queryKey: ["learningTaskNodeBinding", projectId] }),
        qc.invalidateQueries({ queryKey: ["reviewChainBinding", projectId] }),
      ])
    },
  })
}

export function useEditLearningTaskNode(scope: ScopedProjectRef | null, nodeId: string) {
  const projectId = scope?.scopedProjectId ?? ""
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (title: string) => editLearningTaskNode(scope as ScopedProjectRef, nodeId, title),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["learningTaskNodes", projectId] }),
        qc.invalidateQueries({ queryKey: ["learningTaskNode", projectId] }),
        qc.invalidateQueries({ queryKey: ["learningTaskNodeBinding", projectId] }),
        qc.invalidateQueries({ queryKey: ["reviewChainBinding", projectId] }),
      ])
    },
  })
}

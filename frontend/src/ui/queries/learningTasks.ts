import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { ApiError } from "@/ui/api/http"
import { editLearningTask, getLearningTask } from "@/ui/api/learningTasks"
import { editLearningTaskNode, getLearningTaskNode, getLearningTaskNodeBinding, listLearningTaskNodes } from "@/ui/api/learningTaskNodes"
import { isVirtualStudyReviewProjectId } from "@/ui/guideWalkthrough/guideVirtualProjectIds"
import { getVirtualStudyReviewLearningTaskNodes } from "@/ui/guideWalkthrough/virtualStudyReviewProject"

const LEARNING_TASK_QUERY_TIMEOUT_MS = 90_000

export function useLearningTask(projectId: string, learningTaskId: string) {
  return useQuery({
    queryKey: ["learningTask", projectId, learningTaskId],
    queryFn: () => getLearningTask(projectId, learningTaskId),
    enabled: !!projectId && !!learningTaskId,
  })
}

export function useLearningTaskNode(projectId: string, nodeId: string) {
  return useQuery({
    queryKey: ["learningTaskNode", projectId, nodeId],
    queryFn: () => getLearningTaskNode(projectId, nodeId),
    enabled: !!projectId && !!nodeId,
  })
}

export function useLearningTaskNodes(projectId: string) {
  return useQuery({
    queryKey: ["learningTaskNodes", projectId],
    queryFn: ({ signal }) =>
      isVirtualStudyReviewProjectId(projectId)
        ? getVirtualStudyReviewLearningTaskNodes()
        : listLearningTaskNodes(projectId, { signal, timeoutMs: LEARNING_TASK_QUERY_TIMEOUT_MS }),
    enabled: !!projectId,
  })
}

export function useLearningTaskNodeBinding(projectId: string, nodeId: string) {
  return useQuery({
    queryKey: ["learningTaskNodeBinding", projectId, nodeId],
    queryFn: async () => {
      try {
        return await getLearningTaskNodeBinding(projectId, nodeId)
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null
        throw err
      }
    },
    enabled: !!projectId && !!nodeId,
    retry: false,
  })
}

export function useEditLearningTask(projectId: string, learningTaskId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (title: string) => editLearningTask(projectId, learningTaskId, title),
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

export function useEditLearningTaskNode(projectId: string, nodeId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (title: string) => editLearningTaskNode(projectId, nodeId, title),
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

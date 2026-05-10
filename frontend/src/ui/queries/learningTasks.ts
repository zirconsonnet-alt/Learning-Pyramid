import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { ApiError } from "@/ui/api/http"
import { editLearningTask, getLearningTask } from "@/ui/api/learningTasks"
import { editLearningTaskNode, getLearningTaskNode, getLearningTaskNodeBinding, listLearningTaskNodes } from "@/ui/api/learningTaskNodes"
import type { ProjectScope } from "@/ui/api/projectScope"
import { isVirtualStudyReviewProjectId } from "@/ui/guideWalkthrough/guideVirtualProjectIds"
import { getVirtualStudyReviewLearningTaskNodes } from "@/ui/guideWalkthrough/virtualStudyReviewProject"

const LEARNING_TASK_QUERY_TIMEOUT_MS = 90_000

export function useLearningTask(scope: ProjectScope | null, learningTaskId: string) {
  const projectId = scope?.projectId ?? ""
  return useQuery({
    queryKey: ["learningTask", scope?.subjectId ?? "", projectId, learningTaskId],
    queryFn: () => getLearningTask(scope as ProjectScope, learningTaskId),
    enabled: !!scope?.subjectId && !!projectId && !!learningTaskId,
  })
}

export function useLearningTaskNode(scope: ProjectScope | null, nodeId: string) {
  const projectId = scope?.projectId ?? ""
  return useQuery({
    queryKey: ["learningTaskNode", scope?.subjectId ?? "", projectId, nodeId],
    queryFn: () => getLearningTaskNode(scope as ProjectScope, nodeId),
    enabled: !!scope?.subjectId && !!projectId && !!nodeId,
  })
}

export function useLearningTaskNodes(scope: ProjectScope | null) {
  const projectId = scope?.projectId ?? ""
  return useQuery({
    queryKey: ["learningTaskNodes", scope?.subjectId ?? "", projectId],
    queryFn: ({ signal }) =>
      isVirtualStudyReviewProjectId(projectId)
        ? getVirtualStudyReviewLearningTaskNodes()
        : listLearningTaskNodes(scope as ProjectScope, { signal, timeoutMs: LEARNING_TASK_QUERY_TIMEOUT_MS }),
    enabled: !!scope?.subjectId && !!projectId,
  })
}

export function useLearningTaskNodeBinding(scope: ProjectScope | null, nodeId: string) {
  const projectId = scope?.projectId ?? ""
  return useQuery({
    queryKey: ["learningTaskNodeBinding", scope?.subjectId ?? "", projectId, nodeId],
    queryFn: async () => {
      try {
        return await getLearningTaskNodeBinding(scope as ProjectScope, nodeId)
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null
        throw err
      }
    },
    enabled: !!scope?.subjectId && !!projectId && !!nodeId,
    retry: false,
  })
}

export function useEditLearningTask(scope: ProjectScope | null, learningTaskId: string) {
  const projectId = scope?.projectId ?? ""
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (title: string) => editLearningTask(scope as ProjectScope, learningTaskId, title),
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

export function useEditLearningTaskNode(scope: ProjectScope | null, nodeId: string) {
  const projectId = scope?.projectId ?? ""
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (title: string) => editLearningTaskNode(scope as ProjectScope, nodeId, title),
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

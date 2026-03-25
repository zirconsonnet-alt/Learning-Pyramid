import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query"

import { ApiError } from "@/ui/api/http"
import { getAggregationQueue, listAggregationEvents, listLayers, manualRollUp } from "@/ui/api/layers"
import { getLearningObjectNode, importLearningObjectsFromBrowser } from "@/ui/api/learningObjects"
import { addInstance, bulkRemapRecallPointsInstance, listInstances, listMissingInstances, listRecallPointsByInstance } from "@/ui/api/instances"
import { submitLearningTask } from "@/ui/api/learningTasks"
import { getProjectConfig, setLayerConfig } from "@/ui/api/projectConfig"
import type { ReviewChainTemplateItem } from "@/ui/api/projectConfig"
import { getProjectStorageConfig } from "@/ui/api/projectStorageConfig"
import { getQueue } from "@/ui/api/queue"
import { commitReviewTask, getRangeSnapshot, getRecallPoint, getReviewTask } from "@/ui/api/review"
import type { RichContent } from "@/ui/api/richContent"

export function useInstances(projectId: string) {
  return useQuery({ queryKey: ["instances", projectId], queryFn: () => listInstances(projectId), enabled: !!projectId })
}

export function useMissingInstances(projectId: string) {
  return useQuery({
    queryKey: ["missingInstances", projectId],
    queryFn: () => listMissingInstances(projectId),
    enabled: !!projectId,
  })
}

export function useRecallPointsByInstance(projectId: string, instanceId: string) {
  return useQuery({
    queryKey: ["recallPointsByInstance", projectId, instanceId],
    queryFn: () => listRecallPointsByInstance(projectId, instanceId),
    enabled: !!projectId && !!instanceId,
  })
}

export function useQueue(projectId: string) {
  return useQuery({
    queryKey: ["queue", projectId],
    queryFn: () => getQueue(projectId),
    enabled: !!projectId,
    refetchInterval: 1500,
  })
}

export function useAddInstance(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: { materialId: string }) => addInstance(projectId, p.materialId),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["instances", projectId] })
    },
  })
}

export function useBulkRemapRecallPointsInstance(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: { fromInstanceId: string; toInstanceId: string; recallPointIds?: string[] }) =>
      bulkRemapRecallPointsInstance(projectId, p),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["instances", projectId] }),
        qc.invalidateQueries({ queryKey: ["missingInstances", projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPointsByInstance", projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPoint", projectId] }),
      ])
    },
  })
}

export function useLearningObjectNode(projectId: string, nodeId: string) {
  return useQuery({
    queryKey: ["learningObjectNode", projectId, nodeId],
    queryFn: () => getLearningObjectNode(projectId, nodeId),
    enabled: !!projectId && !!nodeId,
  })
}

export function useLayers(projectId: string) {
  return useQuery({ queryKey: ["layers", projectId], queryFn: () => listLayers(projectId), enabled: !!projectId })
}

export function useProjectConfig(projectId: string) {
  return useQuery({
    queryKey: ["projectConfig", projectId],
    queryFn: () => getProjectConfig(projectId),
    enabled: !!projectId,
    refetchInterval: 5000,
  })
}

export function useProjectStorageConfig(projectId: string) {
  return useQuery({
    queryKey: ["projectStorageConfig", projectId],
    queryFn: async () => {
      try {
        return await getProjectStorageConfig(projectId)
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          return null
        }
        throw err
      }
    },
    enabled: !!projectId,
    refetchInterval: 5000,
    retry: false,
  })
}

export function useSetLayerConfig(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: { layerIndex: number; reviewChainTemplate?: ReviewChainTemplateItem[]; kNode?: number; kPoint?: number }) =>
      setLayerConfig(projectId, p.layerIndex, {
        reviewChainTemplate: p.reviewChainTemplate,
        kNode: p.kNode,
        kPoint: p.kPoint,
      }),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["projectConfig", projectId] }),
        qc.invalidateQueries({ queryKey: ["layers", projectId] }),
      ])
    },
  })
}

export function useAggregationEvents(projectId: string) {
  return useQuery({
    queryKey: ["aggregationEvents", projectId],
    queryFn: () => listAggregationEvents(projectId),
    enabled: !!projectId,
    refetchInterval: 3000,
  })
}

export function useAggregationQueue(projectId: string, layerIndex: number) {
  return useQuery({
    queryKey: ["aggQueue", projectId, layerIndex],
    queryFn: () => getAggregationQueue(projectId, layerIndex),
    enabled: !!projectId && Number.isFinite(layerIndex),
    refetchInterval: 3000,
  })
}

export function useSubmitLearningTask(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: {
      title: string
      items: { question: RichContent; answer: RichContent; anchor: { instanceId: string; position: string } }[]
    }) => submitLearningTask({ projectId, ...p }),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["queue", projectId] }),
        qc.invalidateQueries({ queryKey: ["layers", projectId] }),
        qc.invalidateQueries({ queryKey: ["aggQueue", projectId] }),
        qc.invalidateQueries({ queryKey: ["aggregationEvents", projectId] }),
        qc.invalidateQueries({ queryKey: ["learningTaskNodes", projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPointsByTaskNode", projectId] }),
      ])
    },
  })
}

export function useReviewBundle(projectId: string, headId: string) {
  const reviewTaskQ = useQuery({
    queryKey: ["reviewTask", projectId, headId],
    queryFn: () => getReviewTask(projectId, headId),
    enabled: !!projectId && !!headId,
  })

  const rangeQ = useQuery({
    queryKey: ["range", projectId, reviewTaskQ.data?.inputRangeId],
    queryFn: () => getRangeSnapshot(projectId, reviewTaskQ.data!.inputRangeId),
    enabled: !!projectId && !!reviewTaskQ.data?.inputRangeId,
  })

  const recallPointQs = useQueries({
    queries:
      rangeQ.data?.recallPointIds.map((rpId) => ({
        queryKey: ["recallPoint", projectId, rpId],
        queryFn: () => getRecallPoint(projectId, rpId),
        enabled: !!projectId && !!rpId,
      })) ?? [],
  })

  return { reviewTaskQ, rangeQ, recallPointQs }
}

export function useCommitReviewTask(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: {
      reviewTaskId: string
      canRecall: number[]
      appendedInsights?: { recallPointId: string; insight: RichContent }[]
    }) =>
      commitReviewTask(projectId, p.reviewTaskId, {
        canRecall: p.canRecall,
        appendedInsights: p.appendedInsights,
      }),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["queue", projectId] }),
        qc.invalidateQueries({ queryKey: ["layers", projectId] }),
        qc.invalidateQueries({ queryKey: ["aggQueue", projectId] }),
        qc.invalidateQueries({ queryKey: ["aggregationEvents", projectId] }),
        qc.invalidateQueries({ queryKey: ["reviewTask", projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPoint", projectId] }),
      ])
    },
  })
}

export function useManualRollUp(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: { layerIndex: number; title?: string }) => manualRollUp(projectId, p.layerIndex, p.title),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["layers", projectId] }),
        qc.invalidateQueries({ queryKey: ["aggQueue", projectId] }),
        qc.invalidateQueries({ queryKey: ["aggregationEvents", projectId] }),
      ])
    },
  })
}

export function useImportLearningObjectsFromBrowser(projectId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: { rootTitle?: string; relativeFilePaths: string[] }) => importLearningObjectsFromBrowser(projectId, p),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["instances", projectId] }),
        qc.invalidateQueries({ queryKey: ["missingInstances", projectId] }),
        qc.invalidateQueries({ queryKey: ["learningObjectNodes", projectId] }),
      ])
    },
  })
}

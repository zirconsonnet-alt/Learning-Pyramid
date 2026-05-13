import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query"

import { ApiError } from "@/ui/api/http"
import { getAggregationQueue, listAggregationEvents, listLayers, manualRollUp } from "@/ui/api/layers"
import {
  getLearningObjectNode,
  importLearningObjectsFromBaiduNetdisk,
  importLearningObjectsFromBrowser,
  initializeBookLearningObjects,
  initializeBookLearningObjectsFromSubjectMaterial,
} from "@/ui/api/learningObjects"
import { getInstancePlaybackDescriptor } from "@/ui/api/media"
import { addInstance, bulkRemapRecallPointsInstance, listInstances, listMissingInstances, listRecallPointsByInstance } from "@/ui/api/instances"
import { submitLearningTask } from "@/ui/api/learningTasks"
import { getProjectConfig, setLayerConfig, setProjectRollUpStrategy, setReviewRecommendationConfig } from "@/ui/api/projectConfig"
import type { ReviewChainTemplateItem, RollUpStrategy } from "@/ui/api/projectConfig"
import type { ScopedProjectRef } from "@/ui/api/projectScope"
import { getProjectStorageConfig } from "@/ui/api/projectStorageConfig"
import { getQueue } from "@/ui/api/queue"
import { commitReviewTask, getRangeSnapshot, getRecallPoint, getReviewTask } from "@/ui/api/review"
import type { RichContent } from "@/ui/api/richContent"
import { isVirtualStudyReviewProjectId } from "@/ui/guideWalkthrough/guideVirtualProjectIds"
import {
  commitVirtualStudyReviewTask,
  getVirtualStudyReviewInstances,
  getVirtualStudyReviewLayers,
  getVirtualStudyReviewPlaybackDescriptor,
  getVirtualStudyReviewProjectConfig,
  getVirtualStudyReviewQueue,
  getVirtualStudyReviewRangeSnapshot,
  getVirtualStudyReviewRecallPoint,
  getVirtualStudyReviewRecallPointIdsByInstance,
  getVirtualStudyReviewReviewTask,
  submitVirtualStudyReviewLearningTask,
} from "@/ui/guideWalkthrough/virtualStudyReviewProject"

const WORKBENCH_QUERY_TIMEOUT_MS = 90_000

function scopeProjectId(scope: ScopedProjectRef | null) {
  return scope?.scopedProjectId ?? ""
}

function scopeSubjectId(scope: ScopedProjectRef | null) {
  return scope?.subjectId ?? ""
}

function hasProjectScope(scope: ScopedProjectRef | null): scope is ScopedProjectRef {
  return Boolean(scope?.subjectId && scope.scopedProjectId)
}

export function useInstances(scope: ScopedProjectRef | null) {
  const projectId = scopeProjectId(scope)
  return useQuery({
    queryKey: ["instances", scopeSubjectId(scope), projectId],
    queryFn: ({ signal }) =>
      isVirtualStudyReviewProjectId(projectId)
        ? getVirtualStudyReviewInstances()
        : listInstances(scope as ScopedProjectRef, { signal, timeoutMs: WORKBENCH_QUERY_TIMEOUT_MS }),
    enabled: hasProjectScope(scope),
  })
}

export function useMissingInstances(scope: ScopedProjectRef | null) {
  const projectId = scopeProjectId(scope)
  return useQuery({
    queryKey: ["missingInstances", scopeSubjectId(scope), projectId],
    queryFn: () => (isVirtualStudyReviewProjectId(projectId) ? { instanceIds: [] } : listMissingInstances(scope as ScopedProjectRef)),
    enabled: hasProjectScope(scope),
  })
}

export function useRecallPointsByInstance(scope: ScopedProjectRef | null, instanceId: string) {
  const projectId = scopeProjectId(scope)
  return useQuery({
    queryKey: ["recallPointsByInstance", scopeSubjectId(scope), projectId, instanceId],
    queryFn: ({ signal }) =>
      isVirtualStudyReviewProjectId(projectId)
        ? getVirtualStudyReviewRecallPointIdsByInstance(instanceId)
        : listRecallPointsByInstance(scope as ScopedProjectRef, instanceId, { signal, timeoutMs: WORKBENCH_QUERY_TIMEOUT_MS }),
    enabled: hasProjectScope(scope) && !!instanceId,
  })
}

export function useInstancePlaybackDescriptor(scope: ScopedProjectRef | null, instanceId: string, enabled = true) {
  const projectId = scopeProjectId(scope)
  return useQuery({
    queryKey: ["instancePlaybackDescriptor", scopeSubjectId(scope), projectId, instanceId],
    queryFn: ({ signal }) =>
      isVirtualStudyReviewProjectId(projectId)
        ? getVirtualStudyReviewPlaybackDescriptor(instanceId)
        : getInstancePlaybackDescriptor(scope as ScopedProjectRef, instanceId, { signal, timeoutMs: WORKBENCH_QUERY_TIMEOUT_MS }),
    enabled: enabled && hasProjectScope(scope) && !!instanceId,
    staleTime: 15_000,
  })
}

export function useQueue(scope: ScopedProjectRef | null) {
  const projectId = scopeProjectId(scope)
  return useQuery({
    queryKey: ["queue", scopeSubjectId(scope), projectId],
    queryFn: ({ signal }) =>
      isVirtualStudyReviewProjectId(projectId)
        ? getVirtualStudyReviewQueue()
        : getQueue(scope as ScopedProjectRef, { signal, timeoutMs: WORKBENCH_QUERY_TIMEOUT_MS }),
    enabled: hasProjectScope(scope),
    refetchInterval: isVirtualStudyReviewProjectId(projectId) ? false : 5_000,
  })
}

export function useAddInstance(scope: ScopedProjectRef | null) {
  const projectId = scopeProjectId(scope)
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: { materialId: string }) => addInstance(scope as ScopedProjectRef, p.materialId),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["instances", scopeSubjectId(scope), projectId] })
    },
  })
}

export function useBulkRemapRecallPointsInstance(scope: ScopedProjectRef | null) {
  const projectId = scopeProjectId(scope)
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: { fromInstanceId: string; toInstanceId: string; recallPointIds?: string[] }) =>
      bulkRemapRecallPointsInstance(scope as ScopedProjectRef, p),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["instances", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["missingInstances", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPointsByInstance", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPoint", scopeSubjectId(scope), projectId] }),
      ])
    },
  })
}

export function useLearningObjectNode(scope: ScopedProjectRef | null, nodeId: string) {
  const projectId = scopeProjectId(scope)
  return useQuery({
    queryKey: ["learningObjectNode", scopeSubjectId(scope), projectId, nodeId],
    queryFn: () => getLearningObjectNode(scope as ScopedProjectRef, nodeId),
    enabled: hasProjectScope(scope) && !!nodeId,
  })
}

export function useLayers(scope: ScopedProjectRef | null) {
  const projectId = scopeProjectId(scope)
  return useQuery({
    queryKey: ["layers", scopeSubjectId(scope), projectId],
    queryFn: ({ signal }) =>
      isVirtualStudyReviewProjectId(projectId)
        ? getVirtualStudyReviewLayers()
        : listLayers(scope as ScopedProjectRef, { signal, timeoutMs: WORKBENCH_QUERY_TIMEOUT_MS }),
    enabled: hasProjectScope(scope),
  })
}

export function useProjectConfig(scope: ScopedProjectRef | null) {
  const projectId = scopeProjectId(scope)
  return useQuery({
    queryKey: ["projectConfig", scopeSubjectId(scope), projectId],
    queryFn: () => (isVirtualStudyReviewProjectId(projectId) ? getVirtualStudyReviewProjectConfig() : getProjectConfig(scope as ScopedProjectRef)),
    enabled: hasProjectScope(scope),
    refetchInterval: isVirtualStudyReviewProjectId(projectId) ? false : 5000,
  })
}

export function useProjectStorageConfig(scope: ScopedProjectRef | null) {
  const projectId = scopeProjectId(scope)
  return useQuery({
    queryKey: ["projectStorageConfig", scopeSubjectId(scope), projectId],
    queryFn: async () => {
      try {
        return await getProjectStorageConfig(scope as ScopedProjectRef)
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          return null
        }
        throw err
      }
    },
    enabled: hasProjectScope(scope),
    refetchInterval: 5000,
    retry: false,
  })
}

export function useSetLayerConfig(scope: ScopedProjectRef | null) {
  const projectId = scopeProjectId(scope)
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: {
      layerIndex: number
      reviewChainTemplate?: ReviewChainTemplateItem[]
      kNode?: number
      kPoint?: number
      thresholdRollUpEnabled?: boolean
    }) =>
      setLayerConfig(scope as ScopedProjectRef, p.layerIndex, {
        reviewChainTemplate: p.reviewChainTemplate,
        kNode: p.kNode,
        kPoint: p.kPoint,
        thresholdRollUpEnabled: p.thresholdRollUpEnabled,
      }),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["projectConfig", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["layers", scopeSubjectId(scope), projectId] }),
      ])
    },
  })
}

export function useSetProjectRollUpStrategy(scope: ScopedProjectRef | null) {
  const projectId = scopeProjectId(scope)
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (rollUpStrategy: RollUpStrategy) => setProjectRollUpStrategy(scope as ScopedProjectRef, rollUpStrategy),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["projectConfig", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["layers", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["learningTaskNodes", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["aggregationEvents", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["aggQueue", scopeSubjectId(scope), projectId] }),
      ])
    },
  })
}

export function useSetReviewRecommendationConfig(scope: ScopedProjectRef | null) {
  const projectId = scopeProjectId(scope)
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: {
      minRecallPointsToEnable?: number
      maxHistoryLen?: number
      recommendedBatchSize?: number
      forgettingCurveDecayPerDay?: number
    }) => setReviewRecommendationConfig(scope as ScopedProjectRef, params),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["projectConfig", scopeSubjectId(scope), projectId] })
    },
  })
}

export function useAggregationEvents(scope: ScopedProjectRef | null) {
  const projectId = scopeProjectId(scope)
  return useQuery({
    queryKey: ["aggregationEvents", scopeSubjectId(scope), projectId],
    queryFn: () => listAggregationEvents(scope as ScopedProjectRef),
    enabled: hasProjectScope(scope),
    refetchInterval: 3000,
  })
}

export function useAggregationQueue(scope: ScopedProjectRef | null, layerIndex: number) {
  const projectId = scopeProjectId(scope)
  return useQuery({
    queryKey: ["aggQueue", scopeSubjectId(scope), projectId, layerIndex],
    queryFn: () => getAggregationQueue(scope as ScopedProjectRef, layerIndex),
    enabled: hasProjectScope(scope) && Number.isFinite(layerIndex),
    refetchInterval: 3000,
  })
}

export function useSubmitLearningTask(scope: ScopedProjectRef | null) {
  const projectId = scopeProjectId(scope)
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: {
      title: string
      items: { question: RichContent; answer: RichContent; anchor: { instanceId: string; position: string } | null; references: string[] }[]
    }) =>
      isVirtualStudyReviewProjectId(projectId)
        ? Promise.resolve(submitVirtualStudyReviewLearningTask(p))
        : submitLearningTask({ scope: scope as ScopedProjectRef, ...p }),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["queue", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["layers", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["aggQueue", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["aggregationEvents", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["learningTaskNodes", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPoints", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPointSearch", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPointsByTaskNode", scopeSubjectId(scope), projectId] }),
      ])
    },
  })
}

export function useInitializeBookLearningObjects(scope: ScopedProjectRef | null) {
  const projectId = scopeProjectId(scope)
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: { items: { depth: number; title: string }[] }) => initializeBookLearningObjects(scope as ScopedProjectRef, params),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["instances", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["learningObjectNodes", scopeSubjectId(scope), projectId] }),
      ])
    },
  })
}

export function useInitializeBookLearningObjectsFromSubjectMaterial(scope: ScopedProjectRef | null) {
  const projectId = scopeProjectId(scope)
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: { sourceMaterialId: string }) => initializeBookLearningObjectsFromSubjectMaterial(scope as ScopedProjectRef, params),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["instances", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["learningObjectNodes", scopeSubjectId(scope), projectId] }),
      ])
    },
  })
}

export function useReviewBundle(scope: ScopedProjectRef | null, headId: string) {
  const projectId = scopeProjectId(scope)
  const reviewTaskQ = useQuery({
    queryKey: ["reviewTask", scopeSubjectId(scope), projectId, headId],
    queryFn: () => (isVirtualStudyReviewProjectId(projectId) ? getVirtualStudyReviewReviewTask(headId) : getReviewTask(scope as ScopedProjectRef, headId)),
    enabled: hasProjectScope(scope) && !!headId,
  })

  const rangeQ = useQuery({
    queryKey: ["range", scopeSubjectId(scope), projectId, reviewTaskQ.data?.inputRangeId],
    queryFn: () =>
      isVirtualStudyReviewProjectId(projectId)
        ? getVirtualStudyReviewRangeSnapshot(reviewTaskQ.data!.inputRangeId)
        : getRangeSnapshot(scope as ScopedProjectRef, reviewTaskQ.data!.inputRangeId),
    enabled: hasProjectScope(scope) && !!reviewTaskQ.data?.inputRangeId,
  })

  const recallPointQs = useQueries({
    queries:
      rangeQ.data?.recallPointIds.map((rpId) => ({
        queryKey: ["recallPoint", scopeSubjectId(scope), projectId, rpId],
        queryFn: () => (isVirtualStudyReviewProjectId(projectId) ? getVirtualStudyReviewRecallPoint(rpId) : getRecallPoint(scope as ScopedProjectRef, rpId)),
        enabled: hasProjectScope(scope) && !!rpId,
      })) ?? [],
  })

  return { reviewTaskQ, rangeQ, recallPointQs }
}

export function useCommitReviewTask(scope: ScopedProjectRef | null) {
  const projectId = scopeProjectId(scope)
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: {
      reviewTaskId: string
      canRecall: number[]
      appendedInsights?: { recallPointId: string; insight: RichContent }[]
    }) =>
      isVirtualStudyReviewProjectId(projectId)
        ? Promise.resolve(commitVirtualStudyReviewTask(p))
        : commitReviewTask(scope as ScopedProjectRef, p.reviewTaskId, {
            canRecall: p.canRecall,
            appendedInsights: p.appendedInsights,
          }),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["queue", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["layers", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["aggQueue", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["aggregationEvents", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["reviewTask", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPoint", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["reviewRecommendations", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPointReviewProjection", scopeSubjectId(scope), projectId] }),
      ])
    },
  })
}

export function useManualRollUp(scope: ScopedProjectRef | null) {
  const projectId = scopeProjectId(scope)
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: { layerIndex: number; title?: string }) => manualRollUp(scope as ScopedProjectRef, p.layerIndex, p.title),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["layers", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["aggQueue", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["aggregationEvents", scopeSubjectId(scope), projectId] }),
      ])
    },
  })
}

export function useImportLearningObjectsFromBrowser(scope: ScopedProjectRef | null) {
  const projectId = scopeProjectId(scope)
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: { rootTitle?: string; relativeFilePaths: string[] }) => importLearningObjectsFromBrowser(scope as ScopedProjectRef, p),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["instances", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["missingInstances", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["learningObjectNodes", scopeSubjectId(scope), projectId] }),
      ])
    },
  })
}

export function useImportLearningObjectsFromBaiduNetdisk(scope: ScopedProjectRef | null) {
  const projectId = scopeProjectId(scope)
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: {
      accountId: string
      items: Array<{
        fileId: string
        path: string
        name?: string
        isDir?: boolean
        sizeBytes?: number
        mimeType?: string | null
        durationMs?: number | null
      }>
    }) => importLearningObjectsFromBaiduNetdisk(scope as ScopedProjectRef, params),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["instances", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["missingInstances", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["learningObjectNodes", scopeSubjectId(scope), projectId] }),
        qc.invalidateQueries({ queryKey: ["instancePlaybackDescriptor", scopeSubjectId(scope), projectId] }),
      ])
    },
  })
}

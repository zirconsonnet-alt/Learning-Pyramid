import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query"
import * as DocumentPicker from "expo-document-picker"
import { router, useLocalSearchParams } from "expo-router"

import { useApiRuntime, useLearningPyramidApi } from "../../../api/ApiProvider"
import { toErrorMessage } from "../../../api/errorMessage"
import type { LearningObjectNode } from "../../../api/learningObjects"
import { projectTypeRequiresLearningObjectTree, type ProjectType } from "../../../api/projectConfig"
import type { AskProjectLlmInput } from "../../../api/system"
import { useAuth } from "../../../auth/AuthProvider"
import { ProjectShell } from "../../../navigation/ProjectShell"
import type { ProjectShellAction } from "../../../navigation/ProjectShell"
import { firstRouteParam } from "../../../routing/params"
import { MobileWorkbenchScreen, type ReviewCommitPayload } from "../../../screens/MobileWorkbenchScreen"
import { ProjectAiChatScreen } from "../../../screens/ProjectAiChatScreen"
import { ProjectReviewRecommendationsScreen } from "../../../screens/ProjectReviewRecommendationsScreen"
import { ProjectStructureScreen } from "../../../screens/ProjectStructureScreen"
import {
  buildSubmitLearningTaskItems,
  createRecallDraft,
  getIncompleteDraftReason,
  setDraftRichText,
  type MobileRecallDraft,
} from "../../../workbench/recallDrafts"

function createLocalId() {
  return globalThis.crypto.randomUUID()
}

function firstLeaf(nodes: LearningObjectNode[]) {
  return nodes.find((node) => node.kind === "leaf") ?? null
}

function taskScopeKey(instanceId: string | null) {
  return instanceId ?? "__loose_points__"
}

export default function ProjectRoute() {
  const api = useLearningPyramidApi()
  const auth = useAuth()
  const runtime = useApiRuntime()
  const queryClient = useQueryClient()
  const params = useLocalSearchParams<{ subjectId: string; scopedProjectId: string }>()
  const subjectId = firstRouteParam(params.subjectId) ?? ""
  const scopedProjectId = firstRouteParam(params.scopedProjectId) ?? ""
  const scope = useMemo(() => ({ subjectId, scopedProjectId }), [scopedProjectId, subjectId])
  const hasScope = Boolean(subjectId && scopedProjectId)
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null)
  const [currentMs, setCurrentMs] = useState(0)
  const [drafts, setDrafts] = useState<MobileRecallDraft[]>([])
  const [pageActions, setPageActions] = useState<ProjectShellAction[]>([])
  const [taskTitlesByScope, setTaskTitlesByScope] = useState<Record<string, string>>({})
  const [subtitlePickErrorMessage, setSubtitlePickErrorMessage] = useState<string | null>(null)
  const previousActiveInstanceIdRef = useRef<string | null>(null)
  const previousRecommendedTitleRef = useRef("")

  const projectConfigQ = useQuery({
    queryKey: ["project-config", subjectId, scopedProjectId],
    queryFn: () => api.projectConfig.getProjectConfig(scope),
    enabled: hasScope,
  })
  const projectType: ProjectType = projectConfigQ.data?.projectType ?? "COURSE"
  const requiresLearningObjectTree = projectTypeRequiresLearningObjectTree(projectType)
  const materialsQ = useQuery({
    queryKey: ["subject-materials", subjectId],
    queryFn: () => api.subjects.listMaterials(subjectId),
    enabled: Boolean(subjectId),
  })
  const subjectsQ = useQuery({
    queryKey: ["subjects"],
    queryFn: () => api.subjects.listSubjects(),
    enabled: Boolean(subjectId),
  })
  const currentSubject = (subjectsQ.data ?? []).find((subject) => subject.subjectId === subjectId) ?? null
  const currentMaterial = (materialsQ.data ?? []).find((material) => material.scopedProjectId === scopedProjectId) ?? null

  const nodesQ = useQuery({
    queryKey: ["learning-object-nodes", subjectId, scopedProjectId],
    queryFn: () => api.learningObjects.listNodes(scope),
    enabled: hasScope,
  })

  const nodes = nodesQ.data ?? []
  const activeNode = useMemo(() => {
    if (!requiresLearningObjectTree) return null
    if (activeNodeId) {
      const selected = nodes.find((node) => node.nodeId === activeNodeId)
      if (selected?.kind === "leaf") return selected
    }
    return firstLeaf(nodes)
  }, [activeNodeId, nodes, requiresLearningObjectTree])
  const activeInstanceId = activeNode?.kind === "leaf" ? activeNode.instanceId : null
  const activeTaskScopeKey = taskScopeKey(requiresLearningObjectTree ? activeInstanceId : null)
  const recommendedTaskTitle =
    projectType === "LOOSE_POINTS" ? "零散知识点" : activeNode?.kind === "leaf" ? activeNode.title : ""
  const taskTitle = taskTitlesByScope[activeTaskScopeKey] ?? recommendedTaskTitle

  useEffect(() => {
    if (!requiresLearningObjectTree) return
    if (activeNode?.kind !== "leaf") {
      if (activeNodeId !== null) setActiveNodeId(null)
      if (previousActiveInstanceIdRef.current !== null) {
        previousActiveInstanceIdRef.current = null
        setCurrentMs(0)
      }
      return
    }

    if (activeNodeId !== activeNode.nodeId) setActiveNodeId(activeNode.nodeId)
    if (
      previousActiveInstanceIdRef.current !== null &&
      previousActiveInstanceIdRef.current !== activeNode.instanceId
    ) {
      setCurrentMs(0)
    }
    previousActiveInstanceIdRef.current = activeNode.instanceId
  }, [activeNode, activeNodeId, requiresLearningObjectTree])

  useEffect(() => {
    const previousRecommendedTitle = previousRecommendedTitleRef.current
    if (!recommendedTaskTitle) return
    setTaskTitlesByScope((current) => {
      const currentTitle = current[activeTaskScopeKey]
      if (currentTitle && currentTitle !== previousRecommendedTitle) return current
      if (currentTitle === recommendedTaskTitle) return current
      return { ...current, [activeTaskScopeKey]: recommendedTaskTitle }
    })
    previousRecommendedTitleRef.current = recommendedTaskTitle
  }, [activeTaskScopeKey, recommendedTaskTitle])

  const queueQ = useQuery({
    queryKey: ["review-queue", subjectId, scopedProjectId],
    queryFn: () => api.review.getQueue(scope),
    enabled: hasScope,
  })
  const reviewTaskId = queueQ.data?.headId ?? null
  const reviewTaskQ = useQuery({
    queryKey: ["review-task", subjectId, scopedProjectId, reviewTaskId],
    queryFn: () => api.review.getReviewTask(scope, reviewTaskId ?? ""),
    enabled: hasScope && Boolean(reviewTaskId),
  })
  const reviewRangeQ = useQuery({
    queryKey: ["review-range", subjectId, scopedProjectId, reviewTaskQ.data?.inputRangeId ?? ""],
    queryFn: () => api.review.getRangeSnapshot(scope, reviewTaskQ.data?.inputRangeId ?? ""),
    enabled: hasScope && Boolean(reviewTaskQ.data?.inputRangeId),
  })
  const reviewRecallPointsQ = useQuery({
    queryKey: ["review-recall-points", subjectId, scopedProjectId],
    queryFn: () => api.review.listRecallPoints(scope),
    enabled: hasScope && Boolean(reviewRangeQ.data),
  })
  const reviewRecommendationsQ = useQuery({
    queryKey: ["review-recommendations", subjectId, scopedProjectId, 20],
    queryFn: () => api.review.listRecommendations(scope, { limit: 20 }),
    enabled: hasScope,
  })
  const referenceCandidatesQ = useQuery({
    queryKey: ["recall-point-reference-candidates", subjectId, scopedProjectId],
    queryFn: () => api.review.searchRecallPoints(scope, { limit: 12 }),
    enabled: hasScope,
  })
  const systemCapabilitiesQ = useQuery({
    queryKey: ["system-capabilities"],
    queryFn: () => api.system.getCapabilities(),
    enabled: hasScope,
  })
  const playbackQ = useQuery({
    queryKey: ["learning-object-playback", subjectId, scopedProjectId, activeInstanceId ?? ""],
    queryFn: () => api.media.getPlayback(scope, activeInstanceId ?? ""),
    enabled: hasScope && Boolean(activeInstanceId) && projectType === "COURSE",
  })
  const subtitleQ = useQuery({
    queryKey: ["instance-subtitle-file", subjectId, scopedProjectId, activeInstanceId ?? ""],
    queryFn: () => api.subtitles.getInstanceSubtitleFile(scope, activeInstanceId ?? ""),
    enabled: hasScope && Boolean(activeInstanceId) && projectType === "COURSE",
  })

  const learningTaskNodesQ = useQuery({
    queryKey: ["learning-task-nodes", subjectId, scopedProjectId],
    queryFn: () => api.learningTaskNodes.listNodes(scope),
    enabled: hasScope,
  })
  const layersQ = useQuery({
    queryKey: ["layers", subjectId, scopedProjectId],
    queryFn: () => api.layers.listLayers(scope),
    enabled: hasScope,
  })
  const layers = layersQ.data ?? []
  const aggregationQueueQs = useQueries({
    queries: layers.map((layer) => ({
      queryKey: ["aggregation-queue", subjectId, scopedProjectId, layer.layerIndex],
      queryFn: () => api.layers.getAggregationQueue(scope, layer.layerIndex),
      enabled: hasScope,
    })),
  })
  const aggregationQueuesByLayerIndex = useMemo(
    () =>
      Object.fromEntries(
        layers.map((layer, index) => [
          layer.layerIndex,
          aggregationQueueQs[index]?.data ?? { currentNodeIds: [] },
        ]),
      ),
    [aggregationQueueQs, layers],
  )
  const learningTaskNodesById = useMemo(
    () =>
      Object.fromEntries((learningTaskNodesQ.data ?? []).map((node) => [node.nodeId, node])),
    [learningTaskNodesQ.data],
  )
  const thresholdRollUpEnabledByLayerIndex = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(projectConfigQ.data?.layerConfigs ?? {}).map(([layerIndex, config]) => [
          Number(layerIndex),
          config.thresholdRollUpEnabled,
        ]),
      ),
    [projectConfigQ.data?.layerConfigs],
  )

  const reviewRecallPointIds = reviewRangeQ.data?.recallPointIds ?? []
  const reviewRecallPoints = useMemo(() => {
    const byId = new Map((reviewRecallPointsQ.data ?? []).map((item) => [item.recallPointId, item]))
    return reviewRecallPointIds.map((id) => byId.get(id)).filter((item): item is NonNullable<typeof item> => Boolean(item))
  }, [reviewRecallPointIds, reviewRecallPointsQ.data])
  const reviewMissingRecallPoint = Boolean(
    reviewRangeQ.data && reviewRecallPointsQ.data && reviewRecallPoints.length !== reviewRecallPointIds.length,
  )

  const activeDrafts = drafts.filter((draft) => draft.instanceId === (requiresLearningObjectTree ? activeInstanceId : null))
  const firstIncompleteDraftReason = activeDrafts
    .map((draft) => getIncompleteDraftReason(draft, projectType))
    .find((reason): reason is string => Boolean(reason))
  const reviewQueueBlocksSubmit = queueQ.isLoading || queueQ.isFetching || queueQ.isError || Boolean(reviewTaskId)

  const submitLearningTask = useMutation({
    mutationFn: (input: {
      nodeId: string | null
      title: string
      drafts: MobileRecallDraft[]
      submittedLocalIds: string[]
    }) =>
      api.learningTasks.submitLearningTask(scope, {
        title: input.title,
        items: buildSubmitLearningTaskItems(input.drafts, projectType),
      }),
    onSuccess: async (_result, variables) => {
      const submittedLocalIds = new Set(variables.submittedLocalIds)
      setDrafts((current) => current.filter((draft) => !submittedLocalIds.has(draft.localId)))
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["review-queue", subjectId, scopedProjectId] }),
        queryClient.invalidateQueries({ queryKey: ["review-recall-points", subjectId, scopedProjectId] }),
        queryClient.invalidateQueries({ queryKey: ["learning-task-nodes", subjectId, scopedProjectId] }),
        queryClient.invalidateQueries({ queryKey: ["layers", subjectId, scopedProjectId] }),
        variables.nodeId
          ? queryClient.invalidateQueries({
              queryKey: ["learning-object-recall-points", subjectId, scopedProjectId, variables.nodeId],
            })
          : Promise.resolve(),
      ])
    },
  })

  const commitReview = useMutation({
    mutationFn: (payload: ReviewCommitPayload) =>
      api.review.commitReviewTask(scope, payload.reviewTaskId, {
        canRecall: payload.canRecall,
        appendedInsights: payload.appendedInsights,
      }),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["review-queue", subjectId, scopedProjectId] }),
        queryClient.invalidateQueries({ queryKey: ["review-task", subjectId, scopedProjectId] }),
        queryClient.invalidateQueries({ queryKey: ["review-recall-points", subjectId, scopedProjectId] }),
        queryClient.invalidateQueries({ queryKey: ["learning-task-nodes", subjectId, scopedProjectId] }),
      ])
    },
  })

  const uploadSubtitle = useMutation({
    mutationFn: (input: { instanceId: string; fileName: string; content: string }) =>
      api.subtitles.uploadInstanceSubtitleFile(scope, input.instanceId, {
        fileName: input.fileName,
        content: input.content,
      }),
    onSuccess: async (_result, variables) => {
      await queryClient.invalidateQueries({
        queryKey: ["instance-subtitle-file", subjectId, scopedProjectId, variables.instanceId],
      })
    },
  })

  const rollUp = useMutation({
    mutationFn: (layerIndex: number) => api.layers.manualRollUp(scope, layerIndex),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["layers", subjectId, scopedProjectId] }),
        queryClient.invalidateQueries({ queryKey: ["learning-task-nodes", subjectId, scopedProjectId] }),
        queryClient.invalidateQueries({ queryKey: ["aggregation-queue", subjectId, scopedProjectId] }),
      ])
    },
  })

  const setLayerConfig = useMutation({
    mutationFn: (input: { layerIndex: number; enabled: boolean }) =>
      api.projectConfig.setLayerConfig(scope, input.layerIndex, { thresholdRollUpEnabled: input.enabled }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["project-config", subjectId, scopedProjectId] })
    },
  })
  const askProjectLlm = useMutation({
    mutationFn: (input: AskProjectLlmInput) => api.system.askProjectLlm(scope, input),
  })

  const loading = projectConfigQ.isLoading || nodesQ.isLoading
  const errorMessage =
    (projectConfigQ.isError ? toErrorMessage(projectConfigQ.error, "项目配置加载失败") : null) ??
    (nodesQ.isError ? toErrorMessage(nodesQ.error, "学习对象加载失败") : null) ??
    (queueQ.isError ? toErrorMessage(queueQ.error, "复习队列加载失败") : null) ??
    (submitLearningTask.isError ? toErrorMessage(submitLearningTask.error, "学习提交失败") : null)
  const reviewErrorMessage =
    (reviewTaskQ.isError ? toErrorMessage(reviewTaskQ.error, "复习任务加载失败") : null) ??
    (reviewRangeQ.isError ? toErrorMessage(reviewRangeQ.error, "复习范围加载失败") : null) ??
    (reviewRecallPointsQ.isError ? toErrorMessage(reviewRecallPointsQ.error, "复述点加载失败") : null) ??
    (commitReview.isError ? toErrorMessage(commitReview.error, "复习提交失败") : null) ??
    (reviewMissingRecallPoint ? "复习内容加载不完整" : null)
  const reviewLoading =
    Boolean(reviewTaskId) &&
    (reviewTaskQ.isLoading ||
      (Boolean(reviewTaskQ.data?.inputRangeId) && reviewRangeQ.isLoading) ||
      (Boolean(reviewRangeQ.data) && reviewRecallPointsQ.isLoading))
  const layersErrorMessage =
    (layersQ.isError ? toErrorMessage(layersQ.error, "层级任务加载失败") : null) ??
    (learningTaskNodesQ.isError ? toErrorMessage(learningTaskNodesQ.error, "学习任务加载失败") : null)
  const rollUpErrorMessage = rollUp.isError ? toErrorMessage(rollUp.error, "层推进失败") : null
  const subtitleErrorMessage =
    subtitlePickErrorMessage ??
    (subtitleQ.isError ? toErrorMessage(subtitleQ.error, "字幕加载失败") : null) ??
    (uploadSubtitle.isError ? toErrorMessage(uploadSubtitle.error, "字幕导入失败") : null)
  const reviewRecommendationsErrorMessage = reviewRecommendationsQ.isError
    ? toErrorMessage(reviewRecommendationsQ.error, "复习推荐加载失败")
    : null
  const systemCapabilitiesErrorMessage = systemCapabilitiesQ.isError
    ? toErrorMessage(systemCapabilitiesQ.error, "AI 能力状态加载失败")
    : null

  function addDraft() {
    if (requiresLearningObjectTree && !activeInstanceId) return
    const now = Date.now()
    setDrafts((current) => [
      ...current,
      createRecallDraft({
        projectType,
        instanceId: requiresLearningObjectTree ? activeInstanceId : null,
        currentMs,
        localId: createLocalId(),
        now,
      }),
    ])
  }

  function updateDraft(localId: string, updater: (draft: MobileRecallDraft) => MobileRecallDraft) {
    setDrafts((current) =>
      current.map((draft) =>
        draft.localId === localId
          ? {
              ...updater(draft),
              updatedAt: Date.now(),
            }
          : draft,
      ),
    )
  }

  function submitDrafts() {
    if (activeDrafts.length === 0) return
    if (firstIncompleteDraftReason) return
    if (reviewQueueBlocksSubmit || submitLearningTask.isPending) return
    const title = taskTitle.trim()
    if (!title) return
    submitLearningTask.mutate({
      nodeId: activeNode?.kind === "leaf" ? activeNode.nodeId : null,
      title,
      drafts: activeDrafts,
      submittedLocalIds: activeDrafts.map((draft) => draft.localId),
    })
  }

  async function pickAndUploadSubtitle() {
    if (!activeInstanceId || uploadSubtitle.isPending) return
    setSubtitlePickErrorMessage(null)
    try {
      const result = await DocumentPicker.getDocumentAsync({
        copyToCacheDirectory: true,
        multiple: false,
        type: "*/*",
      })
      if (result.canceled) return
      const asset = result.assets[0]
      if (!asset) return
      const response = await fetch(asset.uri)
      const content = await response.text()
      await uploadSubtitle.mutateAsync({
        instanceId: activeInstanceId,
        fileName: asset.name || "subtitle.srt",
        content,
      })
    } catch (error) {
      setSubtitlePickErrorMessage(toErrorMessage(error, "字幕文件读取失败"))
    }
  }

  const updatePageActions = useCallback((actions: ProjectShellAction[]) => {
    setPageActions(actions)
  }, [])

  return (
    <ProjectShell
      context={{
        projectTitle: currentMaterial?.title ?? scopedProjectId,
        scopedProjectId,
        subjectId,
        subjectTitle: currentSubject?.title ?? subjectId,
      }}
      openGlobalSettings={() => router.push("/settings/global")}
      pageActions={pageActions}
      renderAi={() => (
        <ProjectAiChatScreen
          activeLearningObjectNode={activeNode}
          capabilities={systemCapabilitiesQ.data ?? null}
          capabilitiesErrorMessage={systemCapabilitiesErrorMessage}
          capabilitiesLoading={systemCapabilitiesQ.isLoading}
          learningObjectNodes={nodes}
          learningTaskNodes={learningTaskNodesQ.data ?? []}
          onAsk={async (input) => {
            const result = await askProjectLlm.mutateAsync(input)
            return result.content
          }}
          openGlobalSettings={() => router.push("/settings/global")}
        />
      )}
      renderLearning={() => (
        <MobileWorkbenchScreen
          activeNode={activeNode}
          aggregationQueuesByLayerIndex={aggregationQueuesByLayerIndex}
          apiBaseUrl={runtime.apiBaseUrl}
          currentMs={currentMs}
          drafts={activeDrafts}
          errorMessage={errorMessage}
          layers={layers}
          layersErrorMessage={layersErrorMessage}
          layersLoading={layersQ.isLoading}
          learningTaskNodesById={learningTaskNodesById}
          learningTaskNodesLoading={learningTaskNodesQ.isLoading}
          loading={loading}
          nodes={nodes}
          onAddDraft={addDraft}
          onAddDraftReference={(localId, recallPointId) =>
            updateDraft(localId, (draft) => ({
              ...draft,
              references: draft.references.includes(recallPointId)
                ? draft.references
                : [...draft.references, recallPointId],
            }))
          }
          onCommitReview={(payload) => commitReview.mutate(payload)}
          onImportSubtitle={() => {
            void pickAndUploadSubtitle()
          }}
          onPageActionsChange={updatePageActions}
          onPlaybackTimeChange={setCurrentMs}
          onRemoveDraft={(localId) => setDrafts((current) => current.filter((draft) => draft.localId !== localId))}
          onRemoveDraftReference={(localId, recallPointId) =>
            updateDraft(localId, (draft) => ({
              ...draft,
              references: draft.references.filter((item) => item !== recallPointId),
            }))
          }
          onRollUp={(layerIndex) => rollUp.mutate(layerIndex)}
          onSelectNode={(node) => {
            if (node.kind !== "leaf") return
            setActiveNodeId(node.nodeId)
            setCurrentMs(0)
          }}
          onSubmitDrafts={submitDrafts}
          onTaskTitleChange={(title) =>
            setTaskTitlesByScope((current) => ({
              ...current,
              [activeTaskScopeKey]: title,
            }))
          }
          onToggleThresholdRollUp={(layerIndex, enabled) => setLayerConfig.mutate({ layerIndex, enabled })}
          onUpdateDraftPosition={(localId, position) => updateDraft(localId, (draft) => ({ ...draft, position }))}
          onUpdateDraftText={(localId, field, text) => updateDraft(localId, (draft) => setDraftRichText(draft, field, text))}
          playback={playbackQ.data ?? null}
          playbackErrorMessage={playbackQ.isError ? toErrorMessage(playbackQ.error, "媒体加载失败") : null}
          playbackLoading={playbackQ.isLoading}
          projectType={projectType}
          referenceCandidates={referenceCandidatesQ.data ?? []}
          reviewCommitting={commitReview.isPending}
          reviewErrorMessage={reviewErrorMessage}
          reviewLoading={reviewLoading}
          reviewRecallPointIds={reviewRecallPointIds}
          reviewRecallPoints={reviewRecallPoints}
          reviewTaskId={reviewTaskId}
          rollUpErrorMessage={rollUpErrorMessage}
          rollUpStrategy={projectConfigQ.data?.rollUpStrategy ?? "LEARNING_OBJECT_ISOMORPHIC"}
          rollingUp={rollUp.isPending}
          sessionCookie={runtime.getSessionCookie()}
          subtitleErrorMessage={subtitleErrorMessage}
          subtitleFile={subtitleQ.data ?? null}
          subtitleImporting={uploadSubtitle.isPending}
          subtitleLoading={subtitleQ.isLoading}
          submitting={submitLearningTask.isPending}
          taskTitle={taskTitle}
          thresholdRollUpEnabledByLayerIndex={thresholdRollUpEnabledByLayerIndex}
          thresholdRollUpUpdating={setLayerConfig.isPending}
        />
      )}
      renderReview={() => (
        <ProjectReviewRecommendationsScreen
          data={reviewRecommendationsQ.data ?? null}
          errorMessage={reviewRecommendationsErrorMessage}
          loading={reviewRecommendationsQ.isLoading}
        />
      )}
      renderStructure={() => (
        <ProjectStructureScreen
          learningObjectNodes={nodes}
          learningObjectNodesErrorMessage={nodesQ.isError ? toErrorMessage(nodesQ.error, "学习对象树加载失败") : null}
          learningObjectNodesLoading={nodesQ.isLoading}
          learningTaskNodes={learningTaskNodesQ.data ?? []}
          learningTaskNodesErrorMessage={
            learningTaskNodesQ.isError ? toErrorMessage(learningTaskNodesQ.error, "学习任务树加载失败") : null
          }
          learningTaskNodesLoading={learningTaskNodesQ.isLoading}
        />
      )}
      signOut={() => void auth.signOut()}
    />
  )
}

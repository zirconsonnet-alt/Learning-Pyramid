import { useEffect, useMemo, useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { router, useLocalSearchParams } from "expo-router"

import { useApiRuntime, useLearningPyramidApi } from "../../../api/ApiProvider"
import { toErrorMessage } from "../../../api/errorMessage"
import type { LearningObjectNode } from "../../../api/learningObjects"
import { firstRouteParam } from "../../../routing/params"
import { MobileWorkbenchScreen } from "../../../screens/MobileWorkbenchScreen"
import {
  buildSubmitLearningTaskItems,
  createRecallDraft,
  type MobileRecallDraft,
} from "../../../workbench/recallDrafts"

function createLocalId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}_${Math.random().toString(16).slice(2)}`
}

function firstLeaf(nodes: LearningObjectNode[]) {
  return nodes.find((node) => node.kind === "leaf") ?? null
}

export default function ProjectRoute() {
  const api = useLearningPyramidApi()
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
  const previousActiveInstanceIdRef = useRef<string | null>(null)

  const nodesQ = useQuery({
    queryKey: ["learning-object-nodes", subjectId, scopedProjectId],
    queryFn: () => api.learningObjects.listNodes(scope),
    enabled: hasScope,
  })

  const nodes = nodesQ.data ?? []
  const activeNode = useMemo(() => {
    if (activeNodeId) {
      const selected = nodes.find((node) => node.nodeId === activeNodeId)
      if (selected?.kind === "leaf") return selected
    }
    return firstLeaf(nodes)
  }, [activeNodeId, nodes])
  const activeInstanceId = activeNode?.kind === "leaf" ? activeNode.instanceId : ""

  useEffect(() => {
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
  }, [activeNode, activeNodeId])

  const queueQ = useQuery({
    queryKey: ["review-queue", subjectId, scopedProjectId],
    queryFn: () => api.review.getQueue(scope),
    enabled: hasScope,
  })

  const playbackQ = useQuery({
    queryKey: ["learning-object-playback", subjectId, scopedProjectId, activeInstanceId],
    queryFn: () => api.media.getPlayback(scope, activeInstanceId),
    enabled: hasScope && Boolean(activeInstanceId),
  })

  const recallPointsQ = useQuery({
    queryKey: ["learning-object-recall-points", subjectId, scopedProjectId, activeNode?.nodeId ?? ""],
    queryFn: () => api.learningObjects.listRecallPointsByNode(scope, activeNode?.nodeId ?? ""),
    enabled: hasScope && Boolean(activeNode?.nodeId),
  })

  const submitLearningTask = useMutation({
    mutationFn: (input: { nodeId: string; instanceId: string; title: string; drafts: MobileRecallDraft[] }) =>
      api.learningTasks.submitLearningTask(scope, {
        title: input.title,
        items: buildSubmitLearningTaskItems(input.drafts),
      }),
    onSuccess: async (_result, variables) => {
      setDrafts((current) => current.filter((draft) => draft.instanceId !== variables.instanceId))
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["review-queue", subjectId, scopedProjectId] }),
        queryClient.invalidateQueries({
          queryKey: ["learning-object-recall-points", subjectId, scopedProjectId, variables.nodeId],
        }),
        queryClient.invalidateQueries({ queryKey: ["review-recall-points", subjectId, scopedProjectId] }),
        queryClient.invalidateQueries({ queryKey: ["learning-object-nodes", subjectId, scopedProjectId] }),
      ])
    },
  })

  const activeDrafts = drafts.filter((draft) => draft.instanceId === activeInstanceId)
  const reviewQueueBlocksSubmit = queueQ.isLoading || queueQ.isFetching || queueQ.isError || Boolean(queueQ.data?.headId)
  const canSubmitDrafts =
    activeNode?.kind === "leaf" &&
    activeDrafts.length > 0 &&
    !reviewQueueBlocksSubmit &&
    !submitLearningTask.isPending
  const loading = nodesQ.isLoading
  const errorMessage =
    (nodesQ.isError ? toErrorMessage(nodesQ.error, "学习对象加载失败") : null) ??
    (queueQ.isError ? toErrorMessage(queueQ.error, "复习队列加载失败") : null) ??
    (submitLearningTask.isError ? toErrorMessage(submitLearningTask.error, "学习提交失败") : null)

  function addDraft() {
    if (!activeInstanceId) return
    const now = Date.now()
    setDrafts((current) => [
      ...current,
      createRecallDraft({
        instanceId: activeInstanceId,
        currentMs,
        localId: createLocalId(),
        now,
      }),
    ])
  }

  function updateDraft(localId: string, patch: Partial<Pick<MobileRecallDraft, "answerText" | "questionText">>) {
    setDrafts((current) =>
      current.map((draft) =>
        draft.localId === localId
          ? {
              ...draft,
              ...patch,
              updatedAt: Date.now(),
            }
          : draft,
      ),
    )
  }

  function removeDraft(localId: string) {
    setDrafts((current) => current.filter((draft) => draft.localId !== localId))
  }

  function submitDrafts() {
    if (!canSubmitDrafts) return
    submitLearningTask.mutate({
      nodeId: activeNode.nodeId,
      instanceId: activeNode.instanceId,
      title: activeNode.title,
      drafts: activeDrafts,
    })
  }

  return (
    <MobileWorkbenchScreen
      activeNode={activeNode}
      apiBaseUrl={runtime.apiBaseUrl}
      currentMs={currentMs}
      drafts={activeDrafts}
      errorMessage={errorMessage}
      loading={loading}
      nodes={nodes}
      onAddDraft={addDraft}
      onPlaybackTimeChange={setCurrentMs}
      onRemoveDraft={removeDraft}
      onSelectNode={(node) => {
        if (node.kind !== "leaf") return
        setActiveNodeId(node.nodeId)
        setCurrentMs(0)
      }}
      onSubmitDrafts={submitDrafts}
      onUpdateDraft={updateDraft}
      openReviewQueue={() =>
        router.push({
          pathname: "/review/[subjectId]/[scopedProjectId]",
          params: { subjectId, scopedProjectId },
        })
      }
      playback={playbackQ.data ?? null}
      playbackErrorMessage={playbackQ.isError ? toErrorMessage(playbackQ.error, "媒体加载失败") : null}
      playbackLoading={playbackQ.isLoading}
      recallPoints={recallPointsQ.data ?? []}
      recallPointsErrorMessage={recallPointsQ.isError ? toErrorMessage(recallPointsQ.error, "复述点加载失败") : null}
      recallPointsLoading={recallPointsQ.isLoading}
      reviewHeadId={queueQ.data?.headId ?? null}
      reviewQueueLoading={reviewQueueBlocksSubmit}
      sessionCookie={runtime.getSessionCookie()}
      submitting={submitLearningTask.isPending}
    />
  )
}

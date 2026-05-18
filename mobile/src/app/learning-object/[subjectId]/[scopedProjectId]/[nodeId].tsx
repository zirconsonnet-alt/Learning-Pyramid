import { useQuery } from "@tanstack/react-query"
import { useLocalSearchParams } from "expo-router"

import { useApiRuntime, useLearningPyramidApi } from "../../../../api/ApiProvider"
import { toErrorMessage } from "../../../../api/errorMessage"
import { firstRouteParam } from "../../../../routing/params"
import { LearningObjectScreen } from "../../../../screens/LearningObjectScreen"

export default function LearningObjectRoute() {
  const api = useLearningPyramidApi()
  const runtime = useApiRuntime()
  const params = useLocalSearchParams<{ subjectId: string; scopedProjectId: string; nodeId: string }>()
  const subjectId = firstRouteParam(params.subjectId) ?? ""
  const scopedProjectId = firstRouteParam(params.scopedProjectId) ?? ""
  const nodeId = firstRouteParam(params.nodeId) ?? ""
  const scope = { subjectId, scopedProjectId }
  const hasScope = Boolean(subjectId && scopedProjectId && nodeId)

  const nodeQ = useQuery({
    queryKey: ["learning-object-node", subjectId, scopedProjectId, nodeId],
    queryFn: () => api.learningObjects.getNode(scope, nodeId),
    enabled: hasScope,
  })
  const playbackQ = useQuery({
    queryKey: ["learning-object-playback", subjectId, scopedProjectId, nodeQ.data?.kind === "leaf" ? nodeQ.data.instanceId : ""],
    queryFn: () => api.media.getPlayback(scope, nodeQ.data?.kind === "leaf" ? nodeQ.data.instanceId : ""),
    enabled: hasScope && nodeQ.data?.kind === "leaf",
  })
  const recallPointsQ = useQuery({
    queryKey: ["learning-object-recall-points", subjectId, scopedProjectId, nodeId],
    queryFn: () => api.learningObjects.listRecallPointsByNode(scope, nodeId),
    enabled: hasScope,
  })

  return (
    <LearningObjectScreen
      apiBaseUrl={runtime.apiBaseUrl}
      node={nodeQ.data ?? null}
      nodeErrorMessage={nodeQ.isError ? toErrorMessage(nodeQ.error, "学习对象加载失败") : null}
      nodeLoading={nodeQ.isLoading}
      playback={playbackQ.data ?? null}
      playbackErrorMessage={playbackQ.isError ? toErrorMessage(playbackQ.error, "媒体加载失败") : null}
      playbackLoading={playbackQ.isLoading}
      recallPoints={recallPointsQ.data ?? []}
      recallPointsErrorMessage={recallPointsQ.isError ? toErrorMessage(recallPointsQ.error, "复述点加载失败") : null}
      recallPointsLoading={recallPointsQ.isLoading}
      sessionCookie={runtime.getSessionCookie()}
    />
  )
}

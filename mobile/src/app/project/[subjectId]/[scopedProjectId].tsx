import { useQuery } from "@tanstack/react-query"
import { router, useLocalSearchParams } from "expo-router"

import { useLearningPyramidApi } from "../../../api/ApiProvider"
import { toErrorMessage } from "../../../api/errorMessage"
import { firstRouteParam } from "../../../routing/params"
import { ProjectScreen } from "../../../screens/ProjectScreen"

export default function ProjectRoute() {
  const api = useLearningPyramidApi()
  const params = useLocalSearchParams<{ subjectId: string; scopedProjectId: string }>()
  const subjectId = firstRouteParam(params.subjectId) ?? ""
  const scopedProjectId = firstRouteParam(params.scopedProjectId) ?? ""
  const scope = { subjectId, scopedProjectId }
  const nodesQ = useQuery({
    queryKey: ["learning-object-nodes", subjectId, scopedProjectId],
    queryFn: () => api.learningObjects.listNodes(scope),
    enabled: Boolean(subjectId && scopedProjectId),
  })

  return (
    <ProjectScreen
      errorMessage={nodesQ.isError ? toErrorMessage(nodesQ.error, "学习对象加载失败") : null}
      loading={nodesQ.isLoading}
      nodes={nodesQ.data ?? []}
      openNode={(node) =>
        router.push({
          pathname: "/learning-object/[subjectId]/[scopedProjectId]/[nodeId]",
          params: { subjectId, scopedProjectId, nodeId: node.nodeId },
        })
      }
    />
  )
}

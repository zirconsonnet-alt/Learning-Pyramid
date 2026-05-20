import { useQuery } from "@tanstack/react-query"
import { router, useLocalSearchParams } from "expo-router"

import { useLearningPyramidApi } from "../../../api/ApiProvider"
import { firstRouteParam } from "../../../routing/params"
import { ProjectSettingsScreen } from "../../../screens/ProjectSettingsScreen"

export default function ProjectSettingsRoute() {
  const api = useLearningPyramidApi()
  const params = useLocalSearchParams<{ scopedProjectId: string; subjectId: string }>()
  const subjectId = firstRouteParam(params.subjectId) ?? ""
  const scopedProjectId = firstRouteParam(params.scopedProjectId) ?? ""
  const materialsQ = useQuery({
    queryKey: ["subject-materials", subjectId],
    queryFn: () => api.subjects.listMaterials(subjectId),
    enabled: Boolean(subjectId),
  })
  const material = (materialsQ.data ?? []).find((item) => item.scopedProjectId === scopedProjectId)

  return (
    <ProjectSettingsScreen
      openOfflinePackages={() => router.push(`../../offline-packages/${subjectId}/${scopedProjectId}`)}
      projectTitle={material?.title ?? null}
    />
  )
}

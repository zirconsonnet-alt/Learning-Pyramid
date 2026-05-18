import { useQuery } from "@tanstack/react-query"
import { router, useLocalSearchParams } from "expo-router"

import { useLearningPyramidApi } from "../../api/ApiProvider"
import { toErrorMessage } from "../../api/errorMessage"
import type { StudyMaterial } from "../../api/subjects"
import { firstRouteParam } from "../../routing/params"
import { SubjectMaterialsScreen } from "../../screens/SubjectMaterialsScreen"

export default function SubjectRoute() {
  const api = useLearningPyramidApi()
  const subjectId = firstRouteParam(useLocalSearchParams<{ subjectId: string }>().subjectId) ?? ""
  const materialsQ = useQuery({
    queryKey: ["subject-materials", subjectId],
    queryFn: () => api.subjects.listMaterials(subjectId),
    enabled: Boolean(subjectId),
  })

  function openMaterial(material: StudyMaterial) {
    if (!material.scopedProjectId) return
    router.push({
      pathname: "/project/[subjectId]/[scopedProjectId]",
      params: { subjectId, scopedProjectId: material.scopedProjectId },
    })
  }

  return (
    <SubjectMaterialsScreen
      errorMessage={materialsQ.isError ? toErrorMessage(materialsQ.error, "材料加载失败") : null}
      loading={materialsQ.isLoading}
      materials={materialsQ.data ?? []}
      openMaterial={openMaterial}
    />
  )
}

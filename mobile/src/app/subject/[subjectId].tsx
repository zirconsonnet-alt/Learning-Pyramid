import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { router, useLocalSearchParams } from "expo-router"

import { useLearningPyramidApi } from "../../api/ApiProvider"
import { toErrorMessage } from "../../api/errorMessage"
import type { StudyMaterial } from "../../api/subjects"
import { firstRouteParam } from "../../routing/params"
import { SubjectMaterialsScreen } from "../../screens/SubjectMaterialsScreen"

export default function SubjectRoute() {
  const api = useLearningPyramidApi()
  const queryClient = useQueryClient()
  const subjectId = firstRouteParam(useLocalSearchParams<{ subjectId: string }>().subjectId) ?? ""
  const materialsQ = useQuery({
    queryKey: ["subject-materials", subjectId],
    queryFn: () => api.subjects.listMaterials(subjectId),
    enabled: Boolean(subjectId),
  })
  const createMaterialM = useMutation({
    mutationFn: (input: Parameters<typeof api.subjects.createMaterial>[1]) =>
      api.subjects.createMaterial(subjectId, input),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["subject-materials", subjectId] })
      await queryClient.invalidateQueries({ queryKey: ["subjects"] })
    },
  })
  const deleteMaterialM = useMutation({
    mutationFn: (materialId: string) => api.subjects.deleteMaterial(subjectId, materialId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["subject-materials", subjectId] })
      await queryClient.invalidateQueries({ queryKey: ["subjects"] })
    },
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
      createMaterial={(input) => createMaterialM.mutate(input)}
      deleteMaterial={(materialId) => deleteMaterialM.mutate(materialId)}
      errorMessage={
        (materialsQ.isError ? toErrorMessage(materialsQ.error, "材料加载失败") : null) ??
        (createMaterialM.isError ? toErrorMessage(createMaterialM.error, "项目创建失败") : null) ??
        (deleteMaterialM.isError ? toErrorMessage(deleteMaterialM.error, "项目删除失败") : null)
      }
      loading={materialsQ.isLoading}
      materials={materialsQ.data ?? []}
      openMaterial={openMaterial}
      openMine={() => router.push("/mine")}
      openSubjectSettings={() => router.push({ pathname: "/subject/[subjectId]/settings", params: { subjectId } })}
    />
  )
}

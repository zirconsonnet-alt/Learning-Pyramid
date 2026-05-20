import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useLocalSearchParams } from "expo-router"

import { useLearningPyramidApi } from "../../../api/ApiProvider"
import { toErrorMessage } from "../../../api/errorMessage"
import { firstRouteParam } from "../../../routing/params"
import { SubjectSettingsScreen } from "../../../screens/SubjectSettingsScreen"

export default function SubjectSettingsRoute() {
  const api = useLearningPyramidApi()
  const queryClient = useQueryClient()
  const subjectId = firstRouteParam(useLocalSearchParams<{ subjectId: string }>().subjectId) ?? ""
  const subjectsQ = useQuery({
    queryKey: ["subjects"],
    queryFn: () => api.subjects.listSubjects(),
    enabled: Boolean(subjectId),
  })
  const saveTitleM = useMutation({
    mutationFn: (title: string) => api.subjects.editSubject(subjectId, { title }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["subjects"] })
    },
  })
  const subject = (subjectsQ.data ?? []).find((item) => item.subjectId === subjectId) ?? null
  const errorMessage =
    (subjectsQ.isError ? toErrorMessage(subjectsQ.error, "学科加载失败") : null) ??
    (saveTitleM.isError ? toErrorMessage(saveTitleM.error, "学科保存失败") : null)

  return (
    <SubjectSettingsScreen
      errorMessage={errorMessage}
      loading={subjectsQ.isLoading}
      saveTitle={(title) => saveTitleM.mutate(title)}
      subject={subject}
    />
  )
}

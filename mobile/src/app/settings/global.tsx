import { useMutation, useQueries, useQueryClient } from "@tanstack/react-query"

import { useLearningPyramidApi } from "../../api/ApiProvider"
import { toErrorMessage } from "../../api/errorMessage"
import { buildUpdateUserGlobalSettingsBody } from "../../api/profile"
import { GlobalSettingsScreen } from "../../screens/GlobalSettingsScreen"

export default function GlobalSettingsRoute() {
  const api = useLearningPyramidApi()
  const queryClient = useQueryClient()
  const [llmQ, asrQ, globalQ] = useQueries({
    queries: [
      {
        queryKey: ["my-llm-settings"],
        queryFn: () => api.profile.getMyLlmSettings(),
      },
      {
        queryKey: ["my-asr-settings"],
        queryFn: () => api.profile.getMyAsrSettings(),
      },
      {
        queryKey: ["my-global-settings"],
        queryFn: () => api.profile.getMyGlobalSettings(),
      },
    ],
  })

  const updateLlmM = useMutation({
    mutationFn: api.profile.updateMyLlmSettings,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["my-llm-settings"] })
    },
  })
  const updateAsrM = useMutation({
    mutationFn: api.profile.updateMyAsrSettings,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["my-asr-settings"] })
    },
  })
  const updateGlobalM = useMutation({
    mutationFn: (theme: string) => api.profile.updateMyGlobalSettings(buildUpdateUserGlobalSettingsBody(globalQ.data, theme)),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["my-global-settings"] })
    },
  })

  const errorMessage =
    (llmQ.isError ? toErrorMessage(llmQ.error, "大模型配置加载失败") : null) ??
    (asrQ.isError ? toErrorMessage(asrQ.error, "语音识别配置加载失败") : null) ??
    (globalQ.isError ? toErrorMessage(globalQ.error, "全局设置加载失败") : null) ??
    (updateLlmM.isError ? toErrorMessage(updateLlmM.error, "大模型配置保存失败") : null) ??
    (updateAsrM.isError ? toErrorMessage(updateAsrM.error, "语音识别配置保存失败") : null) ??
    (updateGlobalM.isError ? toErrorMessage(updateGlobalM.error, "主题保存失败") : null)

  return (
    <GlobalSettingsScreen
      asrSettings={asrQ.data ?? null}
      clearAsrApiKey={() => updateAsrM.mutate({ clearApiKey: true })}
      clearLlmApiKey={() => updateLlmM.mutate({ clearApiKey: true })}
      errorMessage={errorMessage}
      globalSettings={globalQ.data ?? null}
      llmSettings={llmQ.data ?? null}
      loading={llmQ.isLoading || asrQ.isLoading || globalQ.isLoading}
      saveAsrSettings={(input) => updateAsrM.mutate(input)}
      saveLlmSettings={(input) => updateLlmM.mutate(input)}
      saveTheme={(theme) => updateGlobalM.mutate(theme)}
    />
  )
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { getGlobalLlmSettings, getPublicDownloads, getSystemCapabilities, getSystemRuntime, updateGlobalLlmSettings } from "@/ui/api/system"

export function useSystemCapabilities() {
  return useQuery({
    queryKey: ["systemCapabilities"],
    queryFn: ({ signal }) => getSystemCapabilities({ signal }),
    staleTime: Infinity,
  })
}

export function usePublicDownloads() {
  return useQuery({
    queryKey: ["publicDownloads"],
    queryFn: ({ signal }) => getPublicDownloads({ signal }),
    staleTime: 60_000,
  })
}

export function useSystemRuntime(enabled = true) {
  return useQuery({
    queryKey: ["systemRuntime"],
    queryFn: ({ signal }) => getSystemRuntime({ signal }),
    enabled,
    staleTime: 2_000,
    refetchInterval: enabled ? 5_000 : false,
  })
}

export function useGlobalLlmSettings(enabled = true) {
  return useQuery({
    queryKey: ["globalLlmSettings"],
    queryFn: ({ signal }) => getGlobalLlmSettings({ signal }),
    enabled,
    staleTime: 2_000,
  })
}

export function useUpdateGlobalLlmSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: {
      baseUrl?: string
      modelName?: string
      apiKey?: string
      promptAssemblyMode?: "system" | "user_concat"
      clearApiKey?: boolean
    }) =>
      updateGlobalLlmSettings(params),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["globalLlmSettings"] }),
        qc.invalidateQueries({ queryKey: ["systemCapabilities"] }),
        qc.invalidateQueries({ queryKey: ["systemRuntime"] }),
      ])
    },
  })
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  changeMyPassword,
  findUserByUid,
  getMyAsrSettings,
  getMyLlmSettings,
  getMyProfile,
  updateMyAsrSettings,
  updateMyLlmSettings,
  updateMyProfile,
  uploadMyAvatar,
} from "@/ui/api/profile"

export function useMyProfile(enabled = true) {
  return useQuery({
    queryKey: ["profile", "me"],
    queryFn: getMyProfile,
    enabled,
    staleTime: 30_000,
  })
}

export function useUpdateMyProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: updateMyProfile,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["profile", "me"] })
      await qc.invalidateQueries({ queryKey: ["auth", "me"] })
    },
  })
}

export function useChangeMyPassword() {
  return useMutation({
    mutationFn: changeMyPassword,
  })
}

export function useUploadMyAvatar() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: uploadMyAvatar,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["profile", "me"] })
      await qc.invalidateQueries({ queryKey: ["auth", "me"] })
    },
  })
}

export function useMyLlmSettings(enabled = true) {
  return useQuery({
    queryKey: ["profile", "me", "llmSettings"],
    queryFn: getMyLlmSettings,
    enabled,
    staleTime: 30_000,
  })
}

export function useUpdateMyLlmSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: updateMyLlmSettings,
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["profile", "me", "llmSettings"] }),
        qc.invalidateQueries({ queryKey: ["systemCapabilities"] }),
        qc.invalidateQueries({ queryKey: ["systemRuntime"] }),
      ])
    },
  })
}

export function useMyAsrSettings(enabled = true) {
  return useQuery({
    queryKey: ["profile", "me", "asrSettings"],
    queryFn: getMyAsrSettings,
    enabled,
    staleTime: 30_000,
  })
}

export function useUpdateMyAsrSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: updateMyAsrSettings,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["profile", "me", "asrSettings"] })
    },
  })
}

export function useFindUserByUid() {
  return useMutation({
    mutationFn: (publicUid: string) => findUserByUid(publicUid),
  })
}

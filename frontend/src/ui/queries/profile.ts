import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { changeMyPassword, findUserByUid, getMyProfile, updateMyProfile, uploadMyAvatar } from "@/ui/api/profile"

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

export function useFindUserByUid() {
  return useMutation({
    mutationFn: (publicUid: string) => findUserByUid(publicUid),
  })
}

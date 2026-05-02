import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  confirmEmailVerification,
  confirmPasswordReset,
  getCurrentUser,
  login,
  logout,
  register,
  requestEmailVerification,
  requestPasswordReset,
} from "@/ui/api/auth"
import { clearPersistedClientState } from "@/ui/store/clientSession"

export function useCurrentUser(enabled = true) {
  return useQuery({
    queryKey: ["auth", "me"],
    queryFn: ({ signal }) => getCurrentUser({ signal }),
    enabled,
    staleTime: 30_000,
  })
}

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: { email: string; password: string }) => login(params),
    onSuccess: async () => {
      clearPersistedClientState()
      qc.clear()
      await qc.invalidateQueries({ queryKey: ["auth", "me"] })
      await qc.invalidateQueries({ queryKey: ["projects"] })
    },
  })
}

export function useRegister() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: { email: string; password: string; inviteCode?: string | null; humanCheckToken?: string | null }) => register(params),
    onSuccess: async () => {
      clearPersistedClientState()
      qc.clear()
      await qc.invalidateQueries({ queryKey: ["auth", "me"] })
      await qc.invalidateQueries({ queryKey: ["projects"] })
    },
  })
}

export function useRequestPasswordReset() {
  return useMutation({
    mutationFn: (params: { email: string }) => requestPasswordReset(params),
  })
}

export function useRequestEmailVerification() {
  return useMutation({
    mutationFn: (params: { email: string }) => requestEmailVerification(params),
  })
}

export function useConfirmEmailVerification() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: { token: string }) => confirmEmailVerification(params),
    onSuccess: async () => {
      clearPersistedClientState()
      qc.clear()
      await qc.invalidateQueries({ queryKey: ["auth", "me"] })
      await qc.invalidateQueries({ queryKey: ["projects"] })
    },
  })
}

export function useConfirmPasswordReset() {
  return useMutation({
    mutationFn: (params: { token: string; newPassword: string }) => confirmPasswordReset(params),
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: logout,
    onSuccess: async () => {
      clearPersistedClientState()
      qc.clear()
    },
  })
}

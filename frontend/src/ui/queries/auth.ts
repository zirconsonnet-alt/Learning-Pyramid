import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { getCurrentUser, login, logout, register } from "@/ui/api/auth"
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
    mutationFn: (params: { email: string; password: string }) => register(params),
    onSuccess: async () => {
      clearPersistedClientState()
      qc.clear()
      await qc.invalidateQueries({ queryKey: ["auth", "me"] })
      await qc.invalidateQueries({ queryKey: ["projects"] })
    },
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

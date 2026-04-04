import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  beginBaiduNetdiskConnect,
  disconnectBaiduNetdiskAccount,
  listBaiduNetdiskCloudAccounts,
} from "@/ui/api/cloudAccounts"

const CLOUD_ACCOUNT_QUERY_TIMEOUT_MS = 60_000

export function useBaiduNetdiskCloudAccounts(enabled = true) {
  return useQuery({
    queryKey: ["cloudAccounts", "baiduNetdisk"],
    queryFn: ({ signal }) => listBaiduNetdiskCloudAccounts({ signal, timeoutMs: CLOUD_ACCOUNT_QUERY_TIMEOUT_MS }),
    enabled,
    staleTime: 15_000,
  })
}

export function useBeginBaiduNetdiskConnect() {
  return useMutation({
    mutationFn: () => beginBaiduNetdiskConnect({ timeoutMs: CLOUD_ACCOUNT_QUERY_TIMEOUT_MS }),
  })
}

export function useDisconnectBaiduNetdiskAccount() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (accountId: string) => disconnectBaiduNetdiskAccount(accountId),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["cloudAccounts", "baiduNetdisk"] })
    },
  })
}

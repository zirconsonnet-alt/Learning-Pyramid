import { z } from "zod"

import { apiRequest, type ApiRequestExecutionOptions } from "@/ui/api/http"

export const CloudAccountSchema = z.object({
  accountId: z.string(),
  provider: z.string(),
  providerUserId: z.string(),
  displayName: z.string(),
  avatarUrl: z.string().nullable(),
  expiresAt: z.string().nullable(),
  scope: z.string(),
  meta: z.record(z.string(), z.unknown()),
  createdAt: z.string(),
  updatedAt: z.string(),
  disabledAt: z.string().nullable(),
})
export type CloudAccount = z.infer<typeof CloudAccountSchema>

export const BeginCloudAccountConnectSchema = z.object({
  provider: z.string(),
  authorizeUrl: z.string(),
  state: z.string(),
})
export type BeginCloudAccountConnect = z.infer<typeof BeginCloudAccountConnectSchema>

export function listBaiduNetdiskCloudAccounts(options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: "/profile/me/cloud-accounts/baidu-netdisk",
    responseSchema: z.array(CloudAccountSchema),
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export function beginBaiduNetdiskConnect(options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: "/profile/me/cloud-accounts/baidu-netdisk/connect",
    method: "POST",
    responseSchema: BeginCloudAccountConnectSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export function disconnectBaiduNetdiskAccount(accountId: string) {
  return apiRequest({
    path: `/profile/me/cloud-accounts/baidu-netdisk/${accountId}`,
    method: "DELETE",
    responseSchema: z.null(),
  })
}

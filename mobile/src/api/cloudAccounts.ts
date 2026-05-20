import { z } from "zod"

import type { ApiRequester } from "./requester"

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

export function createCloudAccountsApi(requester: ApiRequester) {
  return {
    listBaiduNetdiskAccounts: () =>
      requester.request({
        path: "/profile/me/cloud-accounts/baidu-netdisk",
        responseSchema: z.array(CloudAccountSchema),
      }),
  }
}

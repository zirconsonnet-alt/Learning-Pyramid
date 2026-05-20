import { z } from "zod"

import { projectApiPath, type ApiRequester, type ScopedProjectRef } from "./requester"

export const BaiduNetdiskFileItemSchema = z.object({
  fileId: z.string(),
  path: z.string(),
  name: z.string(),
  isDir: z.boolean(),
  sizeBytes: z.number().int().nonnegative().nullable(),
  mimeType: z.string().nullable(),
  durationMs: z.number().int().nonnegative().nullable(),
  category: z.number().int().nullable(),
})

export type BaiduNetdiskFileItem = z.infer<typeof BaiduNetdiskFileItemSchema>

export const BaiduNetdiskFileListSchema = z.object({
  accountId: z.string(),
  dirPath: z.string(),
  page: z.number().int(),
  limit: z.number().int(),
  hasMore: z.boolean(),
  items: z.array(BaiduNetdiskFileItemSchema),
})

export type BaiduNetdiskFileList = z.infer<typeof BaiduNetdiskFileListSchema>

export function createBaiduNetdiskApi(requester: ApiRequester) {
  return {
    listProjectFiles: (
      scope: ScopedProjectRef,
      params: { accountId: string; dirPath?: string; page?: number; limit?: number },
    ) => {
      const query = new URLSearchParams({
        accountId: params.accountId,
        dirPath: params.dirPath ?? "/",
        page: String(params.page ?? 1),
        limit: String(params.limit ?? 200),
      })
      return requester.request({
        path: projectApiPath(scope, `/baidu-netdisk/files?${query.toString()}`),
        responseSchema: BaiduNetdiskFileListSchema,
      })
    },
  }
}

import { z } from "zod"

import { apiRequest, type ApiRequestExecutionOptions } from "@/ui/api/http"
import { projectApiPath, type ProjectScope } from "@/ui/api/projectScope"

export const BaiduNetdiskFileItemSchema = z.object({
  fileId: z.string(),
  path: z.string(),
  name: z.string(),
  isDir: z.boolean(),
  sizeBytes: z.number().int().nonnegative().nullable(),
  mimeType: z.string().nullable(),
  durationMs: z.number().int().nonnegative().nullable(),
  category: z.string().nullable(),
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

export function listProjectBaiduNetdiskFiles(
  scope: ProjectScope,
  params: {
    accountId: string
    dirPath?: string
    page?: number
    limit?: number
  },
  options?: ApiRequestExecutionOptions,
) {
  const query = new URLSearchParams({
    accountId: params.accountId,
    dirPath: params.dirPath ?? "/",
    page: String(params.page ?? 1),
    limit: String(params.limit ?? 200),
  })
  return apiRequest({
    path: projectApiPath(scope, `/baidu-netdisk/files?${query.toString()}`),
    responseSchema: BaiduNetdiskFileListSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

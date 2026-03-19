import { z } from "zod"

import { apiRequest } from "@/ui/api/http"
import { getBaseUrl } from "@/ui/api/http"

export const UploadedMediaAssetSchema = z.object({
  assetId: z.string(),
  mimeType: z.string().nullable().optional(),
  url: z.string(),
})

export type UploadedMediaAsset = z.infer<typeof UploadedMediaAssetSchema>

export function uploadMediaAsset(projectId: string, file: File) {
  return apiRequest({
    path: `/projects/${projectId}/media-assets`,
    method: "POST",
    body: file,
    headers: {
      "Content-Type": file.type || "application/octet-stream",
      "X-Filename": encodeURIComponent(file.name),
    },
    responseSchema: UploadedMediaAssetSchema,
  })
}

export function mediaAssetUrl(projectId: string, assetId: string) {
  return `${getBaseUrl()}/projects/${projectId}/media-assets/${assetId}`
}

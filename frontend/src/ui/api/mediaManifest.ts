import { z } from "zod"

import { apiRequest } from "@/ui/api/http"

export const ClientMediaManifestEntrySchema = z.object({
  relativePath: z.string().min(1),
  displayName: z.string().optional().nullable(),
  mediaKind: z.enum(["video", "audio"]).optional().nullable(),
  sizeBytes: z.number().int().nonnegative().optional().nullable(),
  modifiedAt: z.string().optional().nullable(),
})
export type ClientMediaManifestEntryInput = z.infer<typeof ClientMediaManifestEntrySchema>

export const MediaManifestSyncReportSchema = z.object({
  unchanged: z.boolean(),
  created_instances_count: z.number().int(),
  marked_missing_count: z.number().int(),
  replaced_learning_object_nodes_count: z.number().int(),
  warnings: z.array(z.string()),
})
export type MediaManifestSyncReport = z.infer<typeof MediaManifestSyncReportSchema>

export function syncClientMediaManifest(
  projectId: string,
  payload: { rootTitle?: string; entries: ClientMediaManifestEntryInput[] },
) {
  return apiRequest({
    path: `/projects/${projectId}/media-manifest/sync`,
    method: "POST",
    body: payload,
    responseSchema: MediaManifestSyncReportSchema,
    timeoutMs: 90_000,
  })
}

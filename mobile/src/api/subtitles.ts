import { z } from "zod"

import { projectApiPath, type ApiRequester, type ScopedProjectRef } from "./requester"

export const SubtitleSegmentSchema = z.object({
  startMs: z.number().int(),
  endMs: z.number().int(),
  text: z.string(),
})

const FoundInstanceSubtitleFileSchema = z.object({
  found: z.literal(true),
  instanceId: z.string(),
  fileName: z.string(),
  format: z.enum(["srt", "vtt", "ass", "ssa"]),
  source: z.string().optional(),
  segments: z.array(SubtitleSegmentSchema),
})

const MissingInstanceSubtitleFileSchema = z.object({
  found: z.literal(false),
  instanceId: z.string(),
})

export const InstanceSubtitleFileSchema = z.discriminatedUnion("found", [
  FoundInstanceSubtitleFileSchema,
  MissingInstanceSubtitleFileSchema,
])

export type SubtitleSegment = z.infer<typeof SubtitleSegmentSchema>
export type InstanceSubtitleFile = z.infer<typeof InstanceSubtitleFileSchema>

export const DeleteInstanceSubtitleFileResultSchema = z.object({
  deleted: z.boolean(),
  instanceId: z.string(),
})

export type UploadInstanceSubtitleFileInput = {
  fileName: string
  content: string
}

export function createSubtitlesApi(requester: ApiRequester) {
  return {
    getInstanceSubtitleFile: (scope: ScopedProjectRef, instanceId: string) =>
      requester.request({
        path: projectApiPath(scope, `/instances/${encodeURIComponent(instanceId)}/subtitle-file`),
        responseSchema: InstanceSubtitleFileSchema,
      }),
    uploadInstanceSubtitleFile: (scope: ScopedProjectRef, instanceId: string, input: UploadInstanceSubtitleFileInput) =>
      requester.request({
        path: projectApiPath(scope, `/instances/${encodeURIComponent(instanceId)}/subtitle-file`),
        method: "POST",
        body: input,
        responseSchema: InstanceSubtitleFileSchema,
      }),
    deleteInstanceSubtitleFile: (scope: ScopedProjectRef, instanceId: string) =>
      requester.request({
        path: projectApiPath(scope, `/instances/${encodeURIComponent(instanceId)}/subtitle-file`),
        method: "DELETE",
        responseSchema: DeleteInstanceSubtitleFileResultSchema,
      }),
  }
}

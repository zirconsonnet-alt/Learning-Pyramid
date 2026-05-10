import { z } from "zod"

import { apiRequest, type ApiRequestExecutionOptions } from "@/ui/api/http"
import { projectApiPath, type ProjectScope } from "@/ui/api/projectScope"
import { isVirtualStudyReviewProjectId } from "@/ui/guideWalkthrough/guideVirtualProjectIds"

export const SubtitleSegmentSchema = z.object({
  startMs: z.number().int(),
  endMs: z.number().int(),
  text: z.string(),
})
export type SubtitleSegment = z.infer<typeof SubtitleSegmentSchema>

const FoundInstanceSubtitleFileSchema = z.object({
  found: z.literal(true),
  instanceId: z.string(),
  fileName: z.string(),
  format: z.enum(["srt", "vtt", "ass", "ssa"]),
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
export type InstanceSubtitleFile = z.infer<typeof InstanceSubtitleFileSchema>

export function getInstanceSubtitleFile(scope: ProjectScope, instanceId: string, options?: ApiRequestExecutionOptions) {
  if (isVirtualStudyReviewProjectId(scope.projectId)) {
    return Promise.resolve({
      found: false as const,
      instanceId,
    })
  }
  return apiRequest({
    path: projectApiPath(scope, `/instances/${instanceId}/subtitle-file`),
    responseSchema: InstanceSubtitleFileSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

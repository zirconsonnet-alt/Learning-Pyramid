import { z } from "zod"

import { apiRequest } from "@/ui/api/http"

export const AsrSegmentSchema = z.object({
  startMs: z.number().int(),
  endMs: z.number().int(),
  text: z.string(),
  confidence: z.number().nullable().optional(),
})

export const AsrArtifactSchema = z.object({
  projectId: z.string(),
  asrArtifactId: z.string(),
  createdAt: z.string(),
  provider: z.string(),
  producerRuntimeKind: z.enum(["MOBILE_WEB", "DESKTOP_WEB", "DESKTOP_NATIVE"]),
  recallPointId: z.string(),
  sourceInstanceId: z.string(),
  centerMs: z.number().int(),
  preMs: z.number().int(),
  postMs: z.number().int(),
  segments: z.array(AsrSegmentSchema),
})
export type AsrArtifact = z.infer<typeof AsrArtifactSchema>

const RequestAsrResponseSchema = z.object({ asrArtifactId: z.string() })

export function requestAsr(
  projectId: string,
  p: { recallPointId: string; centerMs: number; preMs: number; postMs: number; provider?: string },
) {
  return apiRequest({
    path: `/projects/${projectId}/asr`,
    method: "POST",
    body: p,
    responseSchema: RequestAsrResponseSchema,
    timeoutMs: 90_000,
  })
}

export function getAsrArtifact(projectId: string, asrArtifactId: string) {
  return apiRequest({
    path: `/projects/${projectId}/asr-artifacts/${asrArtifactId}`,
    responseSchema: AsrArtifactSchema,
  })
}

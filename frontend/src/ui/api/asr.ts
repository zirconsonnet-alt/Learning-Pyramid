import { z } from "zod"

import { apiRequest } from "@/ui/api/http"

export const AsrSegmentSchema = z.object({
  startMs: z.number().int(),
  endMs: z.number().int(),
  text: z.string(),
  confidence: z.number().nullable().optional(),
})
export type AsrSegment = z.infer<typeof AsrSegmentSchema>

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

export const AsrTranscriptResultSchema = z.object({
  projectId: z.string(),
  provider: z.string(),
  recallPointId: z.string(),
  sourceInstanceId: z.string(),
  centerMs: z.number().int(),
  preMs: z.number().int(),
  postMs: z.number().int(),
  segments: z.array(AsrSegmentSchema),
})
export type AsrTranscriptResult = z.infer<typeof AsrTranscriptResultSchema>

export const InstanceAsrTranscriptResultSchema = z.object({
  projectId: z.string(),
  provider: z.string(),
  sourceInstanceId: z.string(),
  startMs: z.number().int(),
  endMs: z.number().int(),
  segments: z.array(AsrSegmentSchema),
})
export type InstanceAsrTranscriptResult = z.infer<typeof InstanceAsrTranscriptResultSchema>

export function requestAsr(
  projectId: string,
  p: {
    recallPointId: string
    centerMs: number
    preMs: number
    postMs: number
    provider?: string
    serviceConfig?: {
      baseUrl: string
      modelName?: string
      apiKey?: string
    }
  },
) {
  return apiRequest({
    path: `/projects/${projectId}/asr`,
    method: "POST",
    body: p,
    responseSchema: AsrTranscriptResultSchema,
    timeoutMs: 90_000,
  })
}

export function requestAsrFromAudioClip(
  projectId: string,
  p: {
    recallPointId: string
    centerMs: number
    preMs: number
    postMs: number
    file: File
    provider?: string
    serviceConfig?: {
      baseUrl: string
      modelName?: string
      apiKey?: string
    }
  },
) {
  const body = new FormData()
  body.set("recallPointId", p.recallPointId)
  body.set("centerMs", String(Math.floor(p.centerMs)))
  body.set("preMs", String(Math.floor(p.preMs)))
  body.set("postMs", String(Math.floor(p.postMs)))
  body.set("provider", p.provider ?? "WHISPER")
  body.set("file", p.file, p.file.name || "clip.flac")
  if (p.serviceConfig?.baseUrl) body.set("serviceBaseUrl", p.serviceConfig.baseUrl)
  if (p.serviceConfig?.modelName) body.set("serviceModelName", p.serviceConfig.modelName)
  if (p.serviceConfig?.apiKey) body.set("serviceApiKey", p.serviceConfig.apiKey)
  return apiRequest({
    path: `/projects/${projectId}/asr/audio`,
    method: "POST",
    body,
    responseSchema: AsrTranscriptResultSchema,
    timeoutMs: 180_000,
  })
}

export function requestInstanceAsr(
  projectId: string,
  instanceId: string,
  p: {
    startMs: number
    endMs: number
    provider?: string
    serviceConfig?: {
      baseUrl: string
      modelName?: string
      apiKey?: string
    }
  },
) {
  return apiRequest({
    path: `/projects/${projectId}/instances/${instanceId}/asr`,
    method: "POST",
    body: p,
    responseSchema: InstanceAsrTranscriptResultSchema,
    timeoutMs: 180_000,
  })
}

export function requestInstanceAsrFromAudioClip(
  projectId: string,
  instanceId: string,
  p: {
    startMs: number
    endMs: number
    file: File
    provider?: string
    serviceConfig?: {
      baseUrl: string
      modelName?: string
      apiKey?: string
    }
  },
) {
  const body = new FormData()
  body.set("startMs", String(Math.floor(p.startMs)))
  body.set("endMs", String(Math.floor(p.endMs)))
  body.set("provider", p.provider ?? "WHISPER")
  body.set("file", p.file, p.file.name || "clip.flac")
  if (p.serviceConfig?.baseUrl) body.set("serviceBaseUrl", p.serviceConfig.baseUrl)
  if (p.serviceConfig?.modelName) body.set("serviceModelName", p.serviceConfig.modelName)
  if (p.serviceConfig?.apiKey) body.set("serviceApiKey", p.serviceConfig.apiKey)
  return apiRequest({
    path: `/projects/${projectId}/instances/${instanceId}/asr/audio`,
    method: "POST",
    body,
    responseSchema: InstanceAsrTranscriptResultSchema,
    timeoutMs: 180_000,
  })
}

export function getAsrArtifact(projectId: string, asrArtifactId: string) {
  return apiRequest({
    path: `/projects/${projectId}/asr-artifacts/${asrArtifactId}`,
    responseSchema: AsrArtifactSchema,
  })
}

import { z } from "zod"

import { apiRequest } from "@/ui/api/http"
import { projectApiPath, type ProjectScope } from "@/ui/api/projectScope"

const AUDIO_PAYLOAD_TOO_LARGE_MESSAGE =
  "上传的音频片段过大，服务器或网关拒绝了这次请求。请稍后重试；如果问题持续出现，需要调大站点上传限制。"

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
  scope: ProjectScope,
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
    path: projectApiPath(scope, "/asr"),
    method: "POST",
    body: p,
    responseSchema: AsrTranscriptResultSchema,
    timeoutMs: 90_000,
  })
}

export function requestAsrFromAudioClip(
  scope: ProjectScope,
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
    path: projectApiPath(scope, "/asr/audio"),
    method: "POST",
    body,
    responseSchema: AsrTranscriptResultSchema,
    timeoutMs: 180_000,
    payloadTooLargeMessage: AUDIO_PAYLOAD_TOO_LARGE_MESSAGE,
  })
}

export function requestInstanceAsr(
  scope: ProjectScope,
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
    path: projectApiPath(scope, `/instances/${instanceId}/asr`),
    method: "POST",
    body: p,
    responseSchema: InstanceAsrTranscriptResultSchema,
    timeoutMs: 180_000,
  })
}

export function requestInstanceAsrFromAudioClip(
  scope: ProjectScope,
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
    path: projectApiPath(scope, `/instances/${instanceId}/asr/audio`),
    method: "POST",
    body,
    responseSchema: InstanceAsrTranscriptResultSchema,
    timeoutMs: 180_000,
    payloadTooLargeMessage: AUDIO_PAYLOAD_TOO_LARGE_MESSAGE,
  })
}

export function getAsrArtifact(scope: ProjectScope, asrArtifactId: string) {
  return apiRequest({
    path: projectApiPath(scope, `/asr-artifacts/${asrArtifactId}`),
    responseSchema: AsrArtifactSchema,
  })
}

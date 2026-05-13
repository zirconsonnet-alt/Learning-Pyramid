import { z } from "zod"

import { apiRequest, getBaseUrl, type ApiRequestExecutionOptions } from "@/ui/api/http"
import { projectApiPath, type ScopedProjectRef } from "@/ui/api/projectScope"

export const PlaybackDescriptorSchema = z.object({
  instanceId: z.string(),
  sourceKind: z.enum(["SERVER_FS", "BROWSER_LOCAL", "NATIVE_LOCAL", "MANUAL", "BAIDU_NETDISK"]),
  playbackKind: z.enum(["FILE", "HLS"]),
  url: z.string(),
  mimeType: z.string(),
  durationMs: z.number().int().nonnegative().nullable(),
  supportsFrameGrab: z.boolean(),
  supportsServerAsr: z.boolean(),
})
export type PlaybackDescriptor = z.infer<typeof PlaybackDescriptorSchema>

export function getInstancePlaybackDescriptor(scope: ScopedProjectRef, instanceId: string, options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: projectApiPath(scope, `/media/instances/${instanceId}/playback`),
    responseSchema: PlaybackDescriptorSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export function resolvePlaybackDescriptorUrl(url: string) {
  const baseUrl = getBaseUrl()
  const absoluteBase = /^https?:\/\//i.test(baseUrl)
    ? `${baseUrl.replace(/\/$/, "")}/`
    : `${window.location.origin}${baseUrl.startsWith("/") ? baseUrl : `/${baseUrl}`}/`
  return new URL(url, absoluteBase).toString()
}

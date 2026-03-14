import { z } from "zod"

import { apiRequest, type ApiRequestExecutionOptions } from "@/ui/api/http"

export const PlaybackDescriptorSchema = z.object({
  mode: z.enum(["relay_progressive", "direct_file", "relay_hls"]),
  streamId: z.string().optional(),
  url: z.string().optional(),
  manifestUrl: z.string().optional(),
  contentType: z.string().optional(),
  supportsRange: z.boolean(),
  agentId: z.string().optional(),
  ready: z.boolean().optional(),
  reason: z.string().optional(),
  decisionReason: z.string().optional(),
  probe: z
    .object({
      container: z.string(),
      videoCodec: z.string().nullable().optional(),
      audioCodec: z.string().nullable().optional(),
      durationMs: z.number().int().nonnegative().nullable().optional(),
      bitrateBps: z.number().int().nonnegative().nullable().optional(),
      width: z.number().int().nonnegative().nullable().optional(),
      height: z.number().int().nonnegative().nullable().optional(),
      fps: z.number().nonnegative().nullable().optional(),
      audioChannels: z.number().int().nonnegative().nullable().optional(),
      audioSampleRate: z.number().int().nonnegative().nullable().optional(),
      videoStreamCount: z.number().int().nonnegative().nullable().optional(),
      audioStreamCount: z.number().int().nonnegative().nullable().optional(),
      subtitleStreamCount: z.number().int().nonnegative().nullable().optional(),
      sizeBytes: z.number().int().nonnegative().nullable().optional(),
      modifiedAt: z.string().nullable().optional(),
      updatedAt: z.string().optional(),
    })
    .optional(),
})
export type PlaybackDescriptor = z.infer<typeof PlaybackDescriptorSchema>

export function getPlaybackDescriptor(
  projectId: string,
  instanceId: string,
  options?: { preferHls?: boolean },
  requestOptions?: ApiRequestExecutionOptions,
) {
  const search = options?.preferHls ? "?preferHls=1" : ""
  return apiRequest({
    path: `/projects/${projectId}/media/instances/${instanceId}/playback${search}`,
    responseSchema: PlaybackDescriptorSchema,
    signal: requestOptions?.signal,
    timeoutMs: requestOptions?.timeoutMs,
  })
}

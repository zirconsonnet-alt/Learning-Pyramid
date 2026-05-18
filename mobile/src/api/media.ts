import { z } from "zod"

import { projectApiPath, type ApiRequester, type ScopedProjectRef } from "./types"

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

export function createMediaApi(requester: ApiRequester) {
  return {
    getPlayback: (scope: ScopedProjectRef, instanceId: string) =>
      requester.request({
        path: projectApiPath(scope, `/media/instances/${encodeURIComponent(instanceId)}/playback`),
        responseSchema: PlaybackDescriptorSchema,
      }),
  }
}

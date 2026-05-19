import { z } from "zod"

import { isDesktopRuntime } from "@/ui/runtime/appRuntime"

const DesktopBaiduHlsPlaybackSchema = z.object({
  url: z.string().url(),
  mimeType: z.literal("application/vnd.apple.mpegurl"),
})

export type DesktopBaiduHlsPlayback = z.infer<typeof DesktopBaiduHlsPlaybackSchema>

export async function createDesktopBaiduHlsUrl(params: { playlistText: string; upstreamUrl: string }): Promise<DesktopBaiduHlsPlayback | null> {
  if (!isDesktopRuntime()) return null
  const { invoke } = await import("@tauri-apps/api/core")
  return DesktopBaiduHlsPlaybackSchema.parse(
    await invoke("desktop_baidu_hls_url", {
      playlistText: params.playlistText,
      upstreamUrl: params.upstreamUrl,
    }),
  )
}

import { z } from "zod"

import { isDesktopRuntime } from "@/ui/runtime/appRuntime"

const NativeMediaPlaybackSchema = z.object({
  url: z.string().url(),
  mimeType: z.string().min(1),
})

export type NativeMediaPlayback = z.infer<typeof NativeMediaPlaybackSchema>

export async function createDesktopNativeMediaUrl(params: {
  projectRoot: string
  learningObjectRoot: string
  materialId: string
}): Promise<NativeMediaPlayback | null> {
  if (!isDesktopRuntime()) return null
  const { invoke } = await import("@tauri-apps/api/core")
  return NativeMediaPlaybackSchema.parse(
    await invoke("desktop_native_media_url", {
      projectRoot: params.projectRoot,
      learningObjectRoot: params.learningObjectRoot,
      materialId: params.materialId,
    }),
  )
}

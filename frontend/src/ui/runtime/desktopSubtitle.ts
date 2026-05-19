import { z } from "zod"

import { isDesktopRuntime } from "@/ui/runtime/appRuntime"

const NativeSubtitleFileSchema = z.discriminatedUnion("found", [
  z.object({
    found: z.literal(true),
    fileName: z.string().min(1),
    format: z.enum(["srt", "vtt", "ass", "ssa"]),
    text: z.string(),
  }),
  z.object({
    found: z.literal(false),
  }),
])

export type NativeSubtitleFile = z.infer<typeof NativeSubtitleFileSchema>

export async function readDesktopNativeSubtitleFile(params: {
  projectRoot: string
  learningObjectRoot: string
  materialId: string
}): Promise<NativeSubtitleFile | null> {
  if (!isDesktopRuntime()) return null
  const { invoke } = await import("@tauri-apps/api/core")
  return NativeSubtitleFileSchema.parse(
    await invoke("desktop_native_subtitle_file", {
      projectRoot: params.projectRoot,
      learningObjectRoot: params.learningObjectRoot,
      materialId: params.materialId,
    }),
  )
}

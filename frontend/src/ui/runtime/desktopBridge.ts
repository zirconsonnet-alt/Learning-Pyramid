import { z } from "zod"

import { isDesktopRuntime } from "@/ui/runtime/appRuntime"

const DesktopHealthSchema = z.object({
  ok: z.literal(true),
  runtime: z.literal("desktop"),
  platform: z.string().min(1),
  arch: z.string().min(1),
})

export type DesktopHealth = z.infer<typeof DesktopHealthSchema>

export async function checkDesktopHealth(): Promise<DesktopHealth | null> {
  if (!isDesktopRuntime()) return null
  const { invoke } = await import("@tauri-apps/api/core")
  return DesktopHealthSchema.parse(await invoke("desktop_health"))
}

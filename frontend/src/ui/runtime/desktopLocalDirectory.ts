import { z } from "zod"

import { isDesktopRuntime } from "@/ui/runtime/appRuntime"

const DesktopLocalDirectoryScanSchema = z.object({
  projectRoot: z.string().min(1),
  rootTitle: z.string().min(1),
  relativeFilePaths: z.array(z.string().min(1)),
})

export type DesktopLocalDirectoryScan = z.infer<typeof DesktopLocalDirectoryScanSchema>

export async function chooseDesktopLocalDirectory(): Promise<DesktopLocalDirectoryScan | null> {
  if (!isDesktopRuntime()) return null
  const { invoke } = await import("@tauri-apps/api/core")
  const result = await invoke("desktop_choose_local_directory")
  if (result === null) return null
  return DesktopLocalDirectoryScanSchema.parse(result)
}

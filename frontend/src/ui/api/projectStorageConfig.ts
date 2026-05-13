import { z } from "zod"

import { apiRequest } from "@/ui/api/http"
import { projectApiPath, type ScopedProjectRef } from "@/ui/api/projectScope"

export const ProjectStorageConfigSchema = z.object({
  projectId: z.string(),
  projectRoot: z.string(),
  learningObjectRoot: z.string(),
  fsSyncPolicy: z.enum(["DISABLED", "STARTUP_SYNC", "MANUAL_SYNC"]),
  updatedAt: z.string(),
})
export type ProjectStorageConfig = z.infer<typeof ProjectStorageConfigSchema>

export function getProjectStorageConfig(scope: ScopedProjectRef) {
  return apiRequest({
    path: projectApiPath(scope, "/project-storage-config"),
    responseSchema: ProjectStorageConfigSchema,
  })
}

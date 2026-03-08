import { z } from "zod"

import { apiRequest } from "@/ui/api/http"

export const ProjectStorageConfigSchema = z.object({
  projectId: z.string(),
  projectRoot: z.string(),
  learningObjectRoot: z.string(),
  fsSyncPolicy: z.enum(["DISABLED", "STARTUP_SYNC", "MANUAL_SYNC"]),
  updatedAt: z.string(),
})
export type ProjectStorageConfig = z.infer<typeof ProjectStorageConfigSchema>

export function getProjectStorageConfig(projectId: string) {
  return apiRequest({
    path: `/projects/${projectId}/project-storage-config`,
    responseSchema: ProjectStorageConfigSchema,
  })
}

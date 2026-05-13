import { z } from "zod"

import { apiRequest, type ApiRequestExecutionOptions } from "@/ui/api/http"
import { projectApiPath, type ScopedProjectRef } from "@/ui/api/projectScope"

export const ProjectSchema = z.object({
  subjectId: z.string().nullable().optional(),
  projectId: z.string(),
  title: z.string(),
  state: z.string(),
  createdAt: z.string(),
  deletedAt: z.string().nullable(),
})
export type Project = z.infer<typeof ProjectSchema>

export const MaterialSourceKindSchema = z.enum(["SERVER_FS", "BROWSER_LOCAL", "NATIVE_LOCAL", "MANUAL", "BAIDU_NETDISK"])
export type MaterialSourceKind = z.infer<typeof MaterialSourceKindSchema>
export const ProjectTypeSchema = z.enum(["COURSE", "BOOK", "LOOSE_POINTS"])
export type ProjectType = z.infer<typeof ProjectTypeSchema>
export const ProjectMaterialSourceBindingSchema = z.object({
  projectId: z.string(),
  sourceKind: MaterialSourceKindSchema,
  sourceRootLabel: z.string().nullable(),
  updatedAt: z.string(),
})
export type ProjectMaterialSourceBinding = z.infer<typeof ProjectMaterialSourceBindingSchema>

export function getProjectMaterialSourceBinding(scope: ScopedProjectRef, options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: projectApiPath(scope, "/material-source-binding"),
    responseSchema: ProjectMaterialSourceBindingSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

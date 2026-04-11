import { z } from "zod"

import { apiRequest, type ApiRequestExecutionOptions } from "@/ui/api/http"

export const ProjectSchema = z.object({
  projectId: z.string(),
  title: z.string(),
  state: z.string(),
  createdAt: z.string(),
  deletedAt: z.string().nullable(),
})
export type Project = z.infer<typeof ProjectSchema>

const ProjectListSchema = z.array(ProjectSchema)
const CreateProjectResultSchema = z.object({ projectId: z.string() })
export const MaterialSourceKindSchema = z.enum(["SERVER_FS", "BROWSER_LOCAL", "NATIVE_LOCAL", "MANUAL", "BAIDU_NETDISK"])
export type MaterialSourceKind = z.infer<typeof MaterialSourceKindSchema>
export const ProjectTypeSchema = z.enum(["COURSE", "BOOK", "MISTAKE_BOOK", "LOOSE_POINTS"])
export type ProjectType = z.infer<typeof ProjectTypeSchema>
export const ProjectMaterialSourceBindingSchema = z.object({
  projectId: z.string(),
  sourceKind: MaterialSourceKindSchema,
  sourceRootLabel: z.string().nullable(),
  updatedAt: z.string(),
})
export type ProjectMaterialSourceBinding = z.infer<typeof ProjectMaterialSourceBindingSchema>

export function listProjects() {
  return apiRequest({ path: "/projects", responseSchema: ProjectListSchema })
}

export function createProject(
  title: string,
  options?: {
    projectRoot?: string
    initialSourceKind?: MaterialSourceKind
    initialProjectType?: ProjectType
  },
) {
  return apiRequest({
    path: "/projects",
    method: "POST",
    body: {
      title,
      projectRoot: options?.projectRoot,
      initialSourceKind: options?.initialSourceKind,
      initialProjectType: options?.initialProjectType,
    },
    responseSchema: CreateProjectResultSchema,
  })
}

export function editProject(projectId: string, title: string) {
  return apiRequest({
    path: `/projects/${projectId}`,
    method: "PATCH",
    body: { title },
    responseSchema: z.null(),
  })
}

export function deleteProject(projectId: string) {
  return apiRequest({ path: `/projects/${projectId}`, method: "DELETE", responseSchema: z.null() })
}

export function getProjectMaterialSourceBinding(projectId: string, options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: `/projects/${projectId}/material-source-binding`,
    responseSchema: ProjectMaterialSourceBindingSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

import { z } from "zod"

import { apiRequest } from "@/ui/api/http"

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
export const MaterialSourceKindSchema = z.enum(["SERVER_FS", "BROWSER_LOCAL", "MANUAL"])
export type MaterialSourceKind = z.infer<typeof MaterialSourceKindSchema>

export function listProjects() {
  return apiRequest({ path: "/projects", responseSchema: ProjectListSchema })
}

export function createProject(
  title: string,
  options?: {
    projectRoot?: string
    initialSourceKind?: MaterialSourceKind
  },
) {
  return apiRequest({
    path: "/projects",
    method: "POST",
    body: {
      title,
      projectRoot: options?.projectRoot,
      initialSourceKind: options?.initialSourceKind,
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

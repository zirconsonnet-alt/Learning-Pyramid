import { z } from "zod"

import { apiRequest } from "@/ui/api/http"
import { DesktopAgentSchema } from "@/ui/api/desktopAgents"

export const ProjectMaterialSourceBindingSchema = z.object({
  projectId: z.string(),
  sourceKind: z.enum(["SERVER_FS", "DESKTOP_AGENT_MANIFEST"]),
  desktopAgentId: z.string().nullable(),
  sourceRootLabel: z.string().nullable(),
  updatedAt: z.string(),
})
export type ProjectMaterialSourceBinding = z.infer<typeof ProjectMaterialSourceBindingSchema>

const ProjectDesktopAgentStatusSchema = z.object({
  projectId: z.string(),
  binding: ProjectMaterialSourceBindingSchema,
  agent: DesktopAgentSchema.nullable(),
})
export type ProjectDesktopAgentStatus = z.infer<typeof ProjectDesktopAgentStatusSchema>

export function getProjectMaterialSourceBinding(projectId: string) {
  return apiRequest({
    path: `/projects/${projectId}/material-source-binding`,
    responseSchema: ProjectMaterialSourceBindingSchema,
  })
}

export function setProjectMaterialSourceBinding(
  projectId: string,
  payload: { sourceKind: "SERVER_FS" | "DESKTOP_AGENT_MANIFEST"; desktopAgentId?: string | null; sourceRootLabel?: string | null },
) {
  return apiRequest({
    path: `/projects/${projectId}/material-source-binding`,
    method: "POST",
    body: {
      sourceKind: payload.sourceKind,
      desktopAgentId: payload.desktopAgentId ?? null,
      sourceRootLabel: payload.sourceRootLabel ?? null,
    },
    responseSchema: z.null(),
  })
}

export function getProjectDesktopAgentStatus(projectId: string) {
  return apiRequest({
    path: `/projects/${projectId}/desktop-agents/status`,
    responseSchema: ProjectDesktopAgentStatusSchema,
  })
}

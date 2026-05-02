export function buildSubjectSettingsPath(subjectProjectId: string) {
  return subjectProjectId ? `/p/${subjectProjectId}/settings` : ""
}

export function buildProjectSettingsPath(projectId: string, options?: { subjectProjectId?: string }) {
  if (!projectId) return ""
  return options?.subjectProjectId && options.subjectProjectId === projectId ? `/p/${projectId}/project-settings` : `/p/${projectId}/settings`
}

export function buildProjectWorkbenchPath(projectId: string) {
  return projectId ? `/p/${projectId}/workbench` : ""
}

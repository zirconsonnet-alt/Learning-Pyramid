export function buildSubjectSettingsPath(subjectId: string) {
  return subjectId ? `/subjects/${subjectId}/settings` : ""
}

export function buildProjectSettingsPath(projectId: string) {
  if (!projectId) return ""
  return `/p/${projectId}/settings`
}

export function buildProjectWorkbenchPath(projectId: string) {
  return projectId ? `/p/${projectId}/workbench` : ""
}

export function buildSubjectSettingsPath(subjectId: string) {
  return subjectId ? `/subjects/${subjectId}/settings` : ""
}

export function buildScopedProjectPath(subjectId: string, projectId: string, suffix: string) {
  const normalizedSuffix = suffix.startsWith("/") ? suffix : `/${suffix}`
  return subjectId && projectId ? `/subjects/${encodeURIComponent(subjectId)}/projects/${encodeURIComponent(projectId)}${normalizedSuffix}` : ""
}

export function buildProjectSettingsPath(subjectId: string, projectId: string) {
  return buildScopedProjectPath(subjectId, projectId, "/settings")
}

export function buildProjectWorkbenchPath(subjectId: string, projectId: string) {
  return buildScopedProjectPath(subjectId, projectId, "/workbench")
}

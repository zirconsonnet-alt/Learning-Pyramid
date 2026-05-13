export function buildSubjectSettingsPath(subjectId: string) {
  return subjectId ? `/subjects/${subjectId}/settings` : ""
}

export function buildScopedProjectPath(subjectId: string, scopedProjectId: string, suffix: string) {
  const normalizedSuffix = suffix.startsWith("/") ? suffix : `/${suffix}`
  return subjectId && scopedProjectId ? `/subjects/${encodeURIComponent(subjectId)}/projects/${encodeURIComponent(scopedProjectId)}${normalizedSuffix}` : ""
}

export function buildProjectSettingsPath(subjectId: string, scopedProjectId: string) {
  return buildScopedProjectPath(subjectId, scopedProjectId, "/settings")
}

export function buildProjectWorkbenchPath(subjectId: string, scopedProjectId: string) {
  return buildScopedProjectPath(subjectId, scopedProjectId, "/workbench")
}

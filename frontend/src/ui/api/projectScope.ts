export type ProjectScope = {
  subjectId: string
  projectId: string
}

export function projectApiPath(scope: ProjectScope, suffix = "") {
  const normalizedSuffix = suffix ? (suffix.startsWith("/") ? suffix : `/${suffix}`) : ""
  return `/subjects/${encodeURIComponent(scope.subjectId)}/projects/${encodeURIComponent(scope.projectId)}${normalizedSuffix}`
}

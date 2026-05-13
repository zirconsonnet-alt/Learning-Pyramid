export type ScopedProjectRef = {
  subjectId: string
  scopedProjectId: string
}

export function projectApiPath(scope: ScopedProjectRef, suffix = "") {
  const normalizedSuffix = suffix ? (suffix.startsWith("/") ? suffix : `/${suffix}`) : ""
  return `/subjects/${encodeURIComponent(scope.subjectId)}/projects/${encodeURIComponent(scope.scopedProjectId)}${normalizedSuffix}`
}

import { useAppStore } from "@/ui/store/appStore"

export function buildSubjectSettingsPath(subjectId: string) {
  return subjectId ? `/subjects/${subjectId}/settings` : ""
}

export function buildScopedProjectPath(subjectId: string, projectId: string, suffix: string) {
  const normalizedSuffix = suffix.startsWith("/") ? suffix : `/${suffix}`
  return subjectId && projectId ? `/subjects/${encodeURIComponent(subjectId)}/projects/${encodeURIComponent(projectId)}${normalizedSuffix}` : ""
}

function currentSubjectIdForProject(projectId: string) {
  if (typeof window !== "undefined") {
    const match = window.location.pathname.match(/^\/subjects\/([^/]+)\/projects\/([^/]+)/)
    const subjectId = decodeURIComponent(match?.[1] ?? "")
    const currentProjectId = decodeURIComponent(match?.[2] ?? "")
    if (subjectId && currentProjectId === projectId) return subjectId
  }
  const projectRef = useAppStore.getState().selectedWorkbenchProjectRef
  return projectRef?.projectId === projectId ? projectRef.subjectId : ""
}

export function buildCurrentProjectPath(projectId: string, suffix: string) {
  return buildScopedProjectPath(currentSubjectIdForProject(projectId), projectId, suffix)
}

export function buildProjectSettingsPath(subjectId: string, projectId: string) {
  return buildScopedProjectPath(subjectId, projectId, "/settings")
}

export function buildProjectWorkbenchPath(subjectId: string, projectId: string) {
  return buildScopedProjectPath(subjectId, projectId, "/workbench")
}

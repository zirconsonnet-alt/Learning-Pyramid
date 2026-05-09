import type { ReactNode } from "react"
import { Navigate, useLocation, useParams } from "react-router-dom"

import { isVirtualStudyReviewProjectId } from "@/ui/guideWalkthrough/guideVirtualProjectIds"
import { useProjects } from "@/ui/queries/projects"
import { getPomodoroSnapshot, isQuickPomodoroSessionActive, pomodoroProjectRefKey, usePomodoroNow, usePomodoroStore } from "@/ui/store/pomodoroStore"
import { buildPomodoroPath } from "@/views/pomodoro/pomodoroRouting"

export function PomodoroWorkbenchGate(props: { children: ReactNode }) {
  const { children } = props
  const { subjectId, projectId } = useParams()
  const location = useLocation()
  const enabled = usePomodoroStore((state) => state.enabled)
  const weeklySchedule = usePomodoroStore((state) => state.weeklySchedule)
  const quickPomodoro = usePomodoroStore((state) => state.quickPomodoro)
  const activeQuickPomodoro = isQuickPomodoroSessionActive(quickPomodoro) ? quickPomodoro : null
  const pomodoroActive = enabled || Boolean(activeQuickPomodoro)
  const now = usePomodoroNow(pomodoroActive)
  const projectsQ = useProjects(true)

  if (!projectId) {
    return <>{children}</>
  }

  if (isVirtualStudyReviewProjectId(projectId)) {
    return <>{children}</>
  }

  if (!pomodoroActive) {
    return <>{children}</>
  }

  const snapshot = getPomodoroSnapshot({ enabled, weeklySchedule, quickPomodoro }, now)
  const pomodoroProjectCatalogReady = !projectsQ.isLoading
  const focusProjectRef = snapshot.currentProjectRef
  const accessibleProjectRefs = new Set(
    (projectsQ.data ?? [])
      .map((item) => (item.subjectId ? pomodoroProjectRefKey({ subjectId: item.subjectId, projectId: item.projectId }) : ""))
      .filter(Boolean),
  )
  const focusProjectKey = pomodoroProjectRefKey(focusProjectRef)
  const focusProjectId =
    pomodoroProjectCatalogReady &&
    focusProjectRef &&
    focusProjectKey &&
    accessibleProjectRefs.has(focusProjectKey)
      ? focusProjectRef.projectId
      : ""

  if (snapshot.canUseWorkbench && focusProjectRef && (subjectId !== focusProjectRef.subjectId || projectId !== focusProjectId)) {
    return (
      <Navigate
        to={`/subjects/${encodeURIComponent(focusProjectRef.subjectId)}/projects/${encodeURIComponent(focusProjectRef.projectId)}/workbench`}
        replace
        state={{
          from: `${location.pathname}${location.search}${location.hash}`,
          blockedProjectId: projectId,
          targetProjectId: focusProjectId,
        }}
      />
    )
  }

  if (!snapshot.shouldRestrictWorkbench) {
    return <>{children}</>
  }

  if (snapshot.canUseWorkbench) {
    return <>{children}</>
  }

  return (
    <Navigate
      to={buildPomodoroPath()}
      replace
      state={{
        from: `${location.pathname}${location.search}${location.hash}`,
        blockedProjectId: projectId,
        targetProjectId: focusProjectId || undefined,
      }}
    />
  )
}

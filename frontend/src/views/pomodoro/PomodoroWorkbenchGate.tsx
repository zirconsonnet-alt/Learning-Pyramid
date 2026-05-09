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
  const snapshot = getPomodoroSnapshot({ enabled, weeklySchedule, quickPomodoro }, now)

  if (!projectId) {
    return <>{children}</>
  }

  if (isVirtualStudyReviewProjectId(projectId)) {
    return <>{children}</>
  }

  if (!snapshot.enabled) {
    return <>{children}</>
  }

  const pomodoroProjectCatalogReady = !projectsQ.isLoading
  const focusProjectRef = snapshot.currentProjectRef
  const focusProjectKey = pomodoroProjectRefKey(focusProjectRef)
  const accessibleProjectRefs = new Set(
    (projectsQ.data ?? [])
      .map((item) => (item.subjectId ? pomodoroProjectRefKey({ subjectId: item.subjectId, projectId: item.projectId }) : ""))
      .filter(Boolean),
  )
  const canUseFocusedWorkbench = Boolean(
    snapshot.canUseWorkbench &&
    pomodoroProjectCatalogReady &&
    focusProjectRef &&
    focusProjectKey &&
    accessibleProjectRefs.has(focusProjectKey),
  )

  if (!pomodoroProjectCatalogReady) {
    return null
  }

  if (canUseFocusedWorkbench && focusProjectRef && (subjectId !== focusProjectRef.subjectId || projectId !== focusProjectRef.projectId)) {
    return (
      <Navigate
        to={`/subjects/${encodeURIComponent(focusProjectRef.subjectId)}/projects/${encodeURIComponent(focusProjectRef.projectId)}/workbench`}
        replace
        state={{
          from: `${location.pathname}${location.search}${location.hash}`,
          blockedProjectId: projectId,
          targetProjectId: focusProjectRef.projectId,
        }}
      />
    )
  }

  if (canUseFocusedWorkbench) {
    return <>{children}</>
  }

  return (
    <Navigate
      to={buildPomodoroPath()}
      replace
      state={{
        from: `${location.pathname}${location.search}${location.hash}`,
        blockedProjectId: projectId,
        targetProjectId: focusProjectRef?.projectId,
      }}
    />
  )
}

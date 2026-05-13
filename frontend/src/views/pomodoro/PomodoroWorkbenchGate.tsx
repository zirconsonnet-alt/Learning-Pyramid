import type { ReactNode } from "react"
import { Navigate, useLocation, useParams } from "react-router-dom"

import { isVirtualStudyReviewProjectId } from "@/ui/guideWalkthrough/guideVirtualProjectIds"
import { useSubjectProjectCatalog } from "@/ui/queries/subjects"
import { getPomodoroSnapshot, isQuickPomodoroSessionActive, pomodoroProjectRefKey, usePomodoroNow, usePomodoroStore } from "@/ui/store/pomodoroStore"
import { buildPomodoroPath } from "@/views/pomodoro/pomodoroRouting"

export function PomodoroWorkbenchGate(props: { children: ReactNode }) {
  const { children } = props
  const { subjectId, scopedProjectId: projectId } = useParams()
  const location = useLocation()
  const enabled = usePomodoroStore((state) => state.enabled)
  const weeklySchedule = usePomodoroStore((state) => state.weeklySchedule)
  const quickPomodoro = usePomodoroStore((state) => state.quickPomodoro)
  const activeQuickPomodoro = isQuickPomodoroSessionActive(quickPomodoro) ? quickPomodoro : null
  const pomodoroActive = enabled || Boolean(activeQuickPomodoro)
  const now = usePomodoroNow(pomodoroActive)
  const projectCatalog = useSubjectProjectCatalog(true)
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

  const pomodoroProjectCatalogReady = !projectCatalog.isLoading
  const focusProjectRef = snapshot.currentProjectRef
  const focusProjectKey = pomodoroProjectRefKey(focusProjectRef)
  const accessibleProjectRefs = new Set(
    projectCatalog.projects.map((item) => pomodoroProjectRefKey({ subjectId: item.subjectId, scopedProjectId: item.projectId })),
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

  if (canUseFocusedWorkbench && focusProjectRef && (subjectId !== focusProjectRef.subjectId || projectId !== focusProjectRef.scopedProjectId)) {
    return (
      <Navigate
        to={`/subjects/${encodeURIComponent(focusProjectRef.subjectId)}/projects/${encodeURIComponent(focusProjectRef.scopedProjectId)}/workbench`}
        replace
        state={{
          from: `${location.pathname}${location.search}${location.hash}`,
          blockedProjectId: projectId,
          targetProjectId: focusProjectRef.scopedProjectId,
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
        targetProjectId: focusProjectRef?.scopedProjectId,
      }}
    />
  )
}

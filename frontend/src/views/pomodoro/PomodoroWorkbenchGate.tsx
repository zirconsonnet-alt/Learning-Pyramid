import type { ReactNode } from "react"
import { Navigate, useLocation, useParams } from "react-router-dom"

import { useProjects } from "@/ui/queries/projects"
import { getPomodoroSnapshot, usePomodoroNow, usePomodoroStore } from "@/ui/store/pomodoroStore"
import { buildPomodoroPath } from "@/views/pomodoro/pomodoroRouting"

export function PomodoroWorkbenchGate(props: { children: ReactNode }) {
  const { children } = props
  const { projectId } = useParams()
  const location = useLocation()
  const enabled = usePomodoroStore((state) => state.enabled)
  const weeklySchedule = usePomodoroStore((state) => state.weeklySchedule)
  const now = usePomodoroNow(enabled)
  const projectsQ = useProjects(true)

  if (!projectId) {
    return <>{children}</>
  }

  if (!enabled) {
    return <>{children}</>
  }

  const snapshot = getPomodoroSnapshot({ enabled, weeklySchedule }, now)
  const accessibleProjectIds = new Set((projectsQ.data ?? []).map((item) => item.projectId))
  const focusProjectId =
    snapshot.currentProjectId && accessibleProjectIds.has(snapshot.currentProjectId)
      ? snapshot.currentProjectId
      : ""

  if (snapshot.canUseWorkbench && focusProjectId && projectId !== focusProjectId) {
    return (
      <Navigate
        to={`/p/${focusProjectId}/workbench`}
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

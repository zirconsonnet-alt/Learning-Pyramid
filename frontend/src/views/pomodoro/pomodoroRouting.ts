export function buildPomodoroPath() {
  return "/pomodoro"
}

export function buildPomodoroPlanPath(planId: string) {
  return `/pomodoro/plans/${encodeURIComponent(planId)}`
}

export function buildPomodoroSettingsPath() {
  return "/pomodoro/settings"
}

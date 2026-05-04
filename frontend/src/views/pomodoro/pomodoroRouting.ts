export function buildPomodoroPath() {
  return "/pomodoro"
}

export function buildPomodoroEditPath(options?: { addPlan?: boolean }) {
  if (options?.addPlan) return "/pomodoro/edit?addPlan=1"
  return "/pomodoro/edit"
}

export function buildPomodoroSettingsPath() {
  return "/pomodoro/settings"
}

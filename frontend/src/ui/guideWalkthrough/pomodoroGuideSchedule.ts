import {
  POMODORO_WEEKDAYS,
  clonePomodoroWeekSchedule,
  createPomodoroPlanSchedule,
  validatePomodoroWeekSchedule,
  type PomodoroWeekSchedule,
  type PomodoroWeekday,
} from "@/ui/store/pomodoroStore"

export const GUIDE_POMODORO_START_TIME = "09:00"
export const GUIDE_POMODORO_FOCUS_MINUTES = 25
export const GUIDE_POMODORO_BREAK_MINUTES = 5
export const GUIDE_POMODORO_COUNT = 1

const GUIDE_POMODORO_PLAN_ID = "guide-pomodoro-tomorrow-9"

export function getGuidePomodoroWeekday(now = Date.now()): PomodoroWeekday {
  const tomorrow = new Date(now)
  tomorrow.setDate(tomorrow.getDate() + 1)
  const jsDay = tomorrow.getDay()
  if (jsDay === 0) return "sun"
  return POMODORO_WEEKDAYS[jsDay - 1] ?? "mon"
}

export function hasGuidePomodoroScheduleConflict(weeklySchedule: PomodoroWeekSchedule, now = Date.now()) {
  const guideDay = getGuidePomodoroWeekday(now)
  const previousConflictCount = validatePomodoroWeekSchedule(weeklySchedule).length
  const candidateSchedule = clonePomodoroWeekSchedule(weeklySchedule)
  candidateSchedule[guideDay] = {
    plans: [
      ...candidateSchedule[guideDay].plans,
      createPomodoroPlanSchedule(
        {
          id: GUIDE_POMODORO_PLAN_ID,
          enabled: true,
          startTime: GUIDE_POMODORO_START_TIME,
          focusMinutes: GUIDE_POMODORO_FOCUS_MINUTES,
          breakMinutes: GUIDE_POMODORO_BREAK_MINUTES,
          pomodoroCount: GUIDE_POMODORO_COUNT,
          projectRefs: [],
          focusPrompts: [],
          breakPrompt: "",
        },
        { day: guideDay, index: candidateSchedule[guideDay].plans.length },
      ),
    ],
  }

  return validatePomodoroWeekSchedule(candidateSchedule).length > previousConflictCount
}

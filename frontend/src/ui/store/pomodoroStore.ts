import { useEffect, useState } from "react"
import { create } from "zustand"
import { persist } from "zustand/middleware"

export type PomodoroPhase = "focus" | "break"
export type PomodoroWeekday = "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun"

export type PomodoroSegment = {
  phase: PomodoroPhase
  pomodoroIndex: number
  durationMs: number
  startOffsetMs: number
  endOffsetMs: number
  projectId: string | null
  promptText: string
}

export type PomodoroDaySchedule = {
  enabled: boolean
  startTime: string
  focusMinutes: number
  breakMinutes: number
  pomodoroCount: number
  projectIds: Array<string | null>
  breakPrompt: string
  focusPrompts: string[]
}

export type PomodoroWeekSchedule = Record<PomodoroWeekday, PomodoroDaySchedule>

export type PomodoroSnapshot = {
  enabled: boolean
  hasEnabledSchedule: boolean
  status: "idle" | "running" | "completed"
  idleReason: "disabled" | "not_configured" | "waiting" | "day_off" | null
  phase: PomodoroPhase | null
  weekday: PomodoroWeekday
  todaySchedule: PomodoroDaySchedule
  totalPomodoros: number
  currentPomodoro: number
  completedPomodoros: number
  totalMs: number
  remainingMs: number
  segmentRemainingMs: number
  segmentIndex: number
  progressRatio: number
  segmentProgressRatio: number
  segment: PomodoroSegment | null
  startTime: string
  startAtMs: number | null
  endAtMs: number | null
  untilStartMs: number
  nextStartAtMs: number | null
  nextStartDay: PomodoroWeekday | null
  canUseWorkbench: boolean
  shouldRestrictWorkbench: boolean
  currentProjectId: string | null
}

export type PomodoroUpcomingSegmentPreview = {
  weekday: PomodoroWeekday
  phase: PomodoroPhase
  pomodoroIndex: number
  totalPomodoros: number
  startsInMs: number
  startAtMs: number
  projectId: string | null
  promptText: string
}

type PomodoroState = {
  enabled: boolean
  weeklySchedule: PomodoroWeekSchedule
  transitionSoundEnabled: boolean
  setEnabled: (enabled: boolean) => void
  setTransitionSoundEnabled: (enabled: boolean) => void
  setWeeklySchedule: (weeklySchedule: PomodoroWeekSchedule) => void
  setDaySchedule: (day: PomodoroWeekday, schedule: Partial<PomodoroDaySchedule>) => void
  setSettings: (settings: { enabled: boolean; weeklySchedule: PomodoroWeekSchedule; transitionSoundEnabled?: boolean }) => void
  reset: () => void
}

const DEFAULT_FOCUS_MINUTES = 25
const DEFAULT_BREAK_MINUTES = 5
const DEFAULT_POMODORO_COUNT = 4
const DEFAULT_POMODORO_START_TIME = "19:00"
const MAX_POMODORO_PROMPT_LENGTH = 200

export const POMODORO_WEEKDAYS: PomodoroWeekday[] = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

export const POMODORO_WEEKDAY_LABELS: Record<PomodoroWeekday, string> = {
  mon: "周一",
  tue: "周二",
  wed: "周三",
  thu: "周四",
  fri: "周五",
  sat: "周六",
  sun: "周日",
}

function clampInt(value: number, min: number, max: number) {
  if (!Number.isFinite(value)) return min
  return Math.min(max, Math.max(min, Math.round(value)))
}

function normalizeFocusMinutes(value: number) {
  return clampInt(value, 1, 180)
}

function normalizeBreakMinutes(value: number) {
  return clampInt(value, 1, 60)
}

function normalizePomodoroCount(value: number) {
  return clampInt(value, 1, 12)
}

function normalizePomodoroProjectId(value: unknown) {
  const text = typeof value === "string" ? value.trim() : ""
  return text || null
}

function normalizePomodoroPromptText(value: unknown) {
  const text = typeof value === "string" ? value.replace(/\s+/g, " ").trim() : ""
  return text.slice(0, MAX_POMODORO_PROMPT_LENGTH)
}

function normalizePomodoroProjectIds(value: unknown, pomodoroCount: number) {
  const normalizedCount = normalizePomodoroCount(pomodoroCount)
  const raw = Array.isArray(value) ? value : []
  const projectIds: Array<string | null> = []
  for (let index = 0; index < normalizedCount; index += 1) {
    projectIds.push(normalizePomodoroProjectId(raw[index]))
  }
  return projectIds
}

function normalizePomodoroFocusPrompts(value: unknown, pomodoroCount: number) {
  const normalizedCount = normalizePomodoroCount(pomodoroCount)
  const raw = Array.isArray(value) ? value : []
  const prompts: string[] = []
  for (let index = 0; index < normalizedCount; index += 1) {
    prompts.push(normalizePomodoroPromptText(raw[index]))
  }
  return prompts
}

export function normalizePomodoroStartTime(value: string | null | undefined) {
  const text = typeof value === "string" ? value.trim() : ""
  const match = /^(\d{1,2}):(\d{1,2})$/.exec(text)
  if (!match) return DEFAULT_POMODORO_START_TIME
  const hours = clampInt(Number.parseInt(match[1] ?? "", 10), 0, 23)
  const minutes = clampInt(Number.parseInt(match[2] ?? "", 10), 0, 59)
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`
}

export function createPomodoroDaySchedule(overrides?: Partial<PomodoroDaySchedule>): PomodoroDaySchedule {
  const pomodoroCount = normalizePomodoroCount(overrides?.pomodoroCount ?? DEFAULT_POMODORO_COUNT)
  return {
    enabled: Boolean(overrides?.enabled ?? false),
    startTime: normalizePomodoroStartTime(overrides?.startTime),
    focusMinutes: normalizeFocusMinutes(overrides?.focusMinutes ?? DEFAULT_FOCUS_MINUTES),
    breakMinutes: normalizeBreakMinutes(overrides?.breakMinutes ?? DEFAULT_BREAK_MINUTES),
    pomodoroCount,
    projectIds: normalizePomodoroProjectIds(overrides?.projectIds, pomodoroCount),
    breakPrompt: normalizePomodoroPromptText(overrides?.breakPrompt),
    focusPrompts: normalizePomodoroFocusPrompts(overrides?.focusPrompts, pomodoroCount),
  }
}

export function createPomodoroWeekSchedule(overrides?: Partial<Record<PomodoroWeekday, Partial<PomodoroDaySchedule>>>) {
  return POMODORO_WEEKDAYS.reduce((result, day) => {
    result[day] = createPomodoroDaySchedule(overrides?.[day])
    return result
  }, {} as PomodoroWeekSchedule)
}

export function clonePomodoroWeekSchedule(weeklySchedule: PomodoroWeekSchedule) {
  return POMODORO_WEEKDAYS.reduce((result, day) => {
    result[day] = createPomodoroDaySchedule(weeklySchedule[day])
    return result
  }, {} as PomodoroWeekSchedule)
}

export function normalizePomodoroWeekSchedule(
  input: unknown,
  legacyConfig?: {
    focusMinutes?: unknown
    breakMinutes?: unknown
    pomodoroCount?: unknown
  },
) {
  const raw = input && typeof input === "object" ? (input as Partial<Record<PomodoroWeekday, unknown>>) : {}
  const fallbackFocusMinutes =
    typeof legacyConfig?.focusMinutes === "number"
      ? normalizeFocusMinutes(legacyConfig.focusMinutes)
      : DEFAULT_FOCUS_MINUTES
  const fallbackBreakMinutes =
    typeof legacyConfig?.breakMinutes === "number"
      ? normalizeBreakMinutes(legacyConfig.breakMinutes)
      : DEFAULT_BREAK_MINUTES
  const fallbackPomodoroCount =
    typeof legacyConfig?.pomodoroCount === "number"
      ? normalizePomodoroCount(legacyConfig.pomodoroCount)
      : DEFAULT_POMODORO_COUNT

  return POMODORO_WEEKDAYS.reduce((result, day) => {
    const item = raw?.[day]
    const schedule = item && typeof item === "object" ? (item as Partial<PomodoroDaySchedule>) : {}
    result[day] = createPomodoroDaySchedule({
      enabled: schedule.enabled,
      startTime: schedule.startTime,
      focusMinutes:
        typeof schedule.focusMinutes === "number" ? schedule.focusMinutes : fallbackFocusMinutes,
      breakMinutes:
        typeof schedule.breakMinutes === "number" ? schedule.breakMinutes : fallbackBreakMinutes,
      pomodoroCount:
        typeof schedule.pomodoroCount === "number" ? schedule.pomodoroCount : fallbackPomodoroCount,
      projectIds: schedule.projectIds,
      breakPrompt: schedule.breakPrompt,
      focusPrompts: schedule.focusPrompts,
    })
    return result
  }, {} as PomodoroWeekSchedule)
}

export function hasEnabledPomodoroSchedule(weeklySchedule: PomodoroWeekSchedule) {
  return POMODORO_WEEKDAYS.some((day) => weeklySchedule[day].enabled)
}

function readStartMinutes(startTime: string) {
  const [hoursText, minutesText] = normalizePomodoroStartTime(startTime).split(":")
  const hours = Number.parseInt(hoursText ?? "0", 10)
  const minutes = Number.parseInt(minutesText ?? "0", 10)
  return hours * 60 + minutes
}

function getPomodoroWeekday(date: Date): PomodoroWeekday {
  const day = date.getDay()
  if (day === 0) return "sun"
  if (day === 1) return "mon"
  if (day === 2) return "tue"
  if (day === 3) return "wed"
  if (day === 4) return "thu"
  if (day === 5) return "fri"
  return "sat"
}

function getScheduledStartAtMs(date: Date, startTime: string) {
  const startMinutes = readStartMinutes(startTime)
  const hours = Math.floor(startMinutes / 60)
  const minutes = startMinutes % 60
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), hours, minutes, 0, 0).getTime()
}

function findNextPomodoroStart(now: number, weeklySchedule: PomodoroWeekSchedule) {
  if (!hasEnabledPomodoroSchedule(weeklySchedule)) {
    return {
      nextStartAtMs: null,
      nextStartDay: null,
    }
  }

  const baseDate = new Date(now)
  for (let offset = 0; offset < 14; offset += 1) {
    const candidateDate = new Date(baseDate.getFullYear(), baseDate.getMonth(), baseDate.getDate() + offset)
    const candidateDay = getPomodoroWeekday(candidateDate)
    const candidateSchedule = weeklySchedule[candidateDay]
    if (!candidateSchedule.enabled) continue
    const candidateStartAtMs = getScheduledStartAtMs(candidateDate, candidateSchedule.startTime)
    if (candidateStartAtMs > now) {
      return {
        nextStartAtMs: candidateStartAtMs,
        nextStartDay: candidateDay,
      }
    }
  }

  return {
    nextStartAtMs: null,
    nextStartDay: null,
  }
}

function createInitialState() {
  return {
    enabled: false,
    weeklySchedule: createPomodoroWeekSchedule(),
    transitionSoundEnabled: false,
  }
}

export function buildPomodoroSegments(
  focusMinutes: number,
  breakMinutes: number,
  pomodoroCount: number,
  projectIds?: Array<string | null>,
  focusPrompts?: string[],
  breakPrompt?: string,
): PomodoroSegment[] {
  const normalizedFocusMinutes = normalizeFocusMinutes(focusMinutes)
  const normalizedBreakMinutes = normalizeBreakMinutes(breakMinutes)
  const normalizedPomodoroCount = normalizePomodoroCount(pomodoroCount)
  const normalizedProjectIds = normalizePomodoroProjectIds(projectIds, normalizedPomodoroCount)
  const normalizedFocusPrompts = normalizePomodoroFocusPrompts(focusPrompts, normalizedPomodoroCount)
  const normalizedBreakPrompt = normalizePomodoroPromptText(breakPrompt)
  const focusDurationMs = normalizedFocusMinutes * 60_000
  const breakDurationMs = normalizedBreakMinutes * 60_000
  const segments: PomodoroSegment[] = []
  let offsetMs = 0

  for (let index = 0; index < normalizedPomodoroCount; index += 1) {
    segments.push({
      phase: "focus",
      pomodoroIndex: index + 1,
      durationMs: focusDurationMs,
      startOffsetMs: offsetMs,
      endOffsetMs: offsetMs + focusDurationMs,
      projectId: normalizedProjectIds[index] ?? null,
      promptText: normalizedFocusPrompts[index] ?? "",
    })
    offsetMs += focusDurationMs

    if (index < normalizedPomodoroCount - 1) {
      segments.push({
        phase: "break",
        pomodoroIndex: index + 1,
        durationMs: breakDurationMs,
        startOffsetMs: offsetMs,
        endOffsetMs: offsetMs + breakDurationMs,
        projectId: null,
        promptText: normalizedBreakPrompt,
      })
      offsetMs += breakDurationMs
    }
  }

  return segments
}

export function getPomodoroSnapshot(
  input: { enabled: boolean; weeklySchedule: PomodoroWeekSchedule },
  now = Date.now(),
): PomodoroSnapshot {
  const weeklySchedule = normalizePomodoroWeekSchedule(input.weeklySchedule)
  const enabled = Boolean(input.enabled)
  const hasEnabledSchedule = hasEnabledPomodoroSchedule(weeklySchedule)
  const date = new Date(now)
  const weekday = getPomodoroWeekday(date)
  const todaySchedule = weeklySchedule[weekday]
  const totalPomodoros = todaySchedule.pomodoroCount
  const todaySegments = buildPomodoroSegments(
    todaySchedule.focusMinutes,
    todaySchedule.breakMinutes,
    todaySchedule.pomodoroCount,
    todaySchedule.projectIds,
    todaySchedule.focusPrompts,
    todaySchedule.breakPrompt,
  )
  const totalMs = todaySegments.at(-1)?.endOffsetMs ?? 0
  const nextStart = findNextPomodoroStart(now, weeklySchedule)
  const startAtMs = todaySchedule.enabled ? getScheduledStartAtMs(date, todaySchedule.startTime) : null
  const endAtMs = startAtMs === null ? null : startAtMs + totalMs

  const createBaseSnapshot = (
    overrides: Partial<PomodoroSnapshot>,
  ): PomodoroSnapshot => ({
    enabled,
    hasEnabledSchedule,
    status: "idle",
    idleReason: null,
    phase: null,
    weekday,
    todaySchedule,
    totalPomodoros,
    currentPomodoro: 0,
    completedPomodoros: 0,
    totalMs,
    remainingMs: 0,
    segmentRemainingMs: 0,
    segmentIndex: -1,
    progressRatio: 0,
    segmentProgressRatio: 0,
    segment: null,
    startTime: todaySchedule.startTime,
    startAtMs,
    endAtMs,
    untilStartMs: 0,
    nextStartAtMs: nextStart.nextStartAtMs,
    nextStartDay: nextStart.nextStartDay,
    canUseWorkbench: false,
    shouldRestrictWorkbench: enabled && hasEnabledSchedule,
    currentProjectId: null,
    ...overrides,
  })

  if (!enabled) {
    return createBaseSnapshot({
      status: "idle",
      idleReason: "disabled",
      canUseWorkbench: true,
      shouldRestrictWorkbench: false,
    })
  }

  if (!hasEnabledSchedule) {
    return createBaseSnapshot({
      status: "idle",
      idleReason: "not_configured",
      canUseWorkbench: true,
      shouldRestrictWorkbench: false,
    })
  }

  if (!todaySchedule.enabled || startAtMs === null || endAtMs === null) {
    return createBaseSnapshot({
      status: "idle",
      idleReason: "day_off",
      totalMs: 0,
      startAtMs: null,
      endAtMs: null,
    })
  }

  if (now < startAtMs) {
    return createBaseSnapshot({
      status: "idle",
      idleReason: "waiting",
      untilStartMs: Math.max(0, startAtMs - now),
    })
  }

  if (now >= endAtMs) {
    return createBaseSnapshot({
      status: "completed",
      idleReason: null,
      currentPomodoro: totalPomodoros,
      completedPomodoros: totalPomodoros,
      remainingMs: 0,
      segmentRemainingMs: 0,
      segmentIndex: todaySegments.length - 1,
      progressRatio: 1,
      segmentProgressRatio: 1,
      segment: todaySegments.at(-1) ?? null,
    })
  }

  const elapsedMs = Math.max(0, now - startAtMs)
  const segmentIndex = todaySegments.findIndex((segment) => elapsedMs < segment.endOffsetMs)
  const segment = segmentIndex >= 0 ? todaySegments[segmentIndex] : null
  const segmentElapsedMs = segment ? Math.max(0, elapsedMs - segment.startOffsetMs) : 0
  const segmentRemainingMs = segment ? Math.max(0, segment.endOffsetMs - elapsedMs) : 0
  const completedPomodoros = todaySegments.filter(
    (item) => item.phase === "focus" && item.endOffsetMs <= elapsedMs,
  ).length
  const canUseWorkbench = segment?.phase === "focus"
  const currentProjectId = segment?.phase === "focus" ? segment.projectId ?? null : null

  return createBaseSnapshot({
    status: "running",
    idleReason: null,
    phase: segment?.phase ?? null,
    currentPomodoro: segment?.pomodoroIndex ?? 0,
    completedPomodoros,
    remainingMs: Math.max(0, totalMs - elapsedMs),
    segmentRemainingMs,
    segmentIndex,
    progressRatio: totalMs > 0 ? Math.min(1, elapsedMs / totalMs) : 0,
    segmentProgressRatio: segment && segment.durationMs > 0 ? Math.min(1, segmentElapsedMs / segment.durationMs) : 0,
    segment,
    canUseWorkbench,
    shouldRestrictWorkbench: !canUseWorkbench,
    currentProjectId,
  })
}

export function getPomodoroUpcomingSegmentPreview(
  input: { enabled: boolean; weeklySchedule: PomodoroWeekSchedule },
  now = Date.now(),
): PomodoroUpcomingSegmentPreview | null {
  const snapshot = getPomodoroSnapshot(input, now)
  if (!snapshot.enabled || !snapshot.hasEnabledSchedule) return null

  if (snapshot.status === "idle" && snapshot.idleReason === "waiting") {
    const projectId = snapshot.todaySchedule.projectIds[0] ?? null
    if (snapshot.startAtMs === null) return null
    return {
      weekday: snapshot.weekday,
      phase: "focus",
      pomodoroIndex: 1,
      totalPomodoros: snapshot.totalPomodoros,
      startsInMs: snapshot.untilStartMs,
      startAtMs: snapshot.startAtMs,
      projectId,
      promptText: snapshot.todaySchedule.focusPrompts[0] ?? "",
    }
  }

  if (snapshot.status === "running") {
    const segments = buildPomodoroSegments(
      snapshot.todaySchedule.focusMinutes,
      snapshot.todaySchedule.breakMinutes,
      snapshot.todaySchedule.pomodoroCount,
      snapshot.todaySchedule.projectIds,
      snapshot.todaySchedule.focusPrompts,
      snapshot.todaySchedule.breakPrompt,
    )
    const nextSegment = segments[snapshot.segmentIndex + 1]
    if (!nextSegment || snapshot.startAtMs === null) {
      return null
    }
    return {
      weekday: snapshot.weekday,
      phase: nextSegment.phase,
      pomodoroIndex: nextSegment.pomodoroIndex,
      totalPomodoros: snapshot.totalPomodoros,
      startsInMs: snapshot.segmentRemainingMs,
      startAtMs: snapshot.startAtMs + nextSegment.startOffsetMs,
      projectId: nextSegment.projectId ?? null,
      promptText: nextSegment.promptText,
    }
  }

  return null
}

export function describePomodoroPhase(
  phase: PomodoroPhase | null,
  status: PomodoroSnapshot["status"],
  idleReason: PomodoroSnapshot["idleReason"] = null,
  enabled = true,
  hasEnabledSchedule = true,
) {
  if (!enabled) return "已关闭"
  if (!hasEnabledSchedule || idleReason === "not_configured") return "待配置"
  if (status === "completed") return "今日已完成"
  if (phase === "focus") return "学习时间"
  if (phase === "break") return "间歇时间"
  if (idleReason === "day_off") return "今日未排程"
  return "等待开始"
}

export function formatPomodoroCountdown(ms: number) {
  const safeMs = Math.max(0, Math.floor(ms))
  const totalSeconds = Math.floor(safeMs / 1000)
  const seconds = totalSeconds % 60
  const totalMinutes = Math.floor(totalSeconds / 60)
  const minutes = totalMinutes % 60
  const hours = Math.floor(totalMinutes / 60)

  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`
  }
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`
}

export function formatPomodoroDuration(minutes: number) {
  const normalized = clampInt(minutes, 0, 999)
  if (normalized <= 0) return "0 分钟"
  if (normalized < 60) return `${normalized} 分钟`
  const hours = Math.floor(normalized / 60)
  const restMinutes = normalized % 60
  if (restMinutes === 0) return `${hours} 小时`
  return `${hours} 小时 ${restMinutes} 分钟`
}

export function usePomodoroNow(enabled = true) {
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    if (!enabled) {
      setNow(Date.now())
      return
    }
    setNow(Date.now())
    const timer = window.setInterval(() => {
      setNow(Date.now())
    }, 1000)
    return () => window.clearInterval(timer)
  }, [enabled])

  return now
}

const initialState = createInitialState()

export const usePomodoroStore = create<PomodoroState>()(
  persist(
    (set) => ({
      ...initialState,
      setEnabled: (enabled) =>
        set((state) => ({
          ...state,
          enabled,
        })),
      setTransitionSoundEnabled: (enabled) =>
        set((state) => ({
          ...state,
          transitionSoundEnabled: Boolean(enabled),
        })),
      setWeeklySchedule: (weeklySchedule) =>
        set((state) => ({
          ...state,
          weeklySchedule: normalizePomodoroWeekSchedule(weeklySchedule),
        })),
      setDaySchedule: (day, schedule) =>
        set((state) => ({
          ...state,
          weeklySchedule: {
            ...state.weeklySchedule,
            [day]: createPomodoroDaySchedule({
              ...state.weeklySchedule[day],
              ...schedule,
            }),
          },
        })),
      setSettings: (settings) =>
        set(() => ({
          enabled: Boolean(settings.enabled),
          weeklySchedule: normalizePomodoroWeekSchedule(settings.weeklySchedule),
          transitionSoundEnabled: Boolean(settings.transitionSoundEnabled),
        })),
      reset: () => set(createInitialState()),
    }),
    {
      name: "plm-pomodoro",
      version: 6,
      migrate: (persistedState: unknown, version) => {
        if (!persistedState || typeof persistedState !== "object") {
          return persistedState as PomodoroState
        }
        const raw = persistedState as {
          enabled?: unknown
          weeklySchedule?: unknown
          transitionSoundEnabled?: unknown
          focusMinutes?: unknown
          breakMinutes?: unknown
          pomodoroCount?: unknown
        }

        if (version >= 6) {
          return {
            enabled: typeof raw.enabled === "boolean" ? raw.enabled : false,
            weeklySchedule: normalizePomodoroWeekSchedule(raw.weeklySchedule),
            transitionSoundEnabled: typeof raw.transitionSoundEnabled === "boolean" ? raw.transitionSoundEnabled : false,
          } as PomodoroState
        }

        return {
          enabled: typeof raw.enabled === "boolean" ? raw.enabled : false,
          weeklySchedule: normalizePomodoroWeekSchedule(raw.weeklySchedule, {
            focusMinutes: raw.focusMinutes,
            breakMinutes: raw.breakMinutes,
            pomodoroCount: raw.pomodoroCount,
          }),
          transitionSoundEnabled: false,
        } as PomodoroState
      },
    },
  ),
)

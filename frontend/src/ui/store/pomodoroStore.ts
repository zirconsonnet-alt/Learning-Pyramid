import { useEffect, useState } from "react"
import { create } from "zustand"
import { persist } from "zustand/middleware"

export type PomodoroPhase = "focus" | "break"
export type PomodoroWeekday = "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun"

export type PomodoroSegment = {
  phase: PomodoroPhase
  planId: string
  planIndex: number
  pomodoroIndex: number
  durationMs: number
  startOffsetMs: number
  endOffsetMs: number
  projectRef: PomodoroProjectReference | null
  promptText: string
}

export type PomodoroProjectReference = {
  subjectId: string
  scopedProjectId: string
}

export type PomodoroPlanSchedule = {
  id: string
  enabled: boolean
  startTime: string
  focusMinutes: number
  breakMinutes: number
  pomodoroCount: number
  projectRefs: Array<PomodoroProjectReference | null>
  breakPrompt: string
  focusPrompts: string[]
}

export type PomodoroDaySchedule = {
  plans: PomodoroPlanSchedule[]
}

export type PomodoroWeekSchedule = Record<PomodoroWeekday, PomodoroDaySchedule>

export type QuickPomodoroSession = {
  id: string
  createdAtMs: number
  startAtMs: number
  endAtMs: number
  projectRef: PomodoroProjectReference | null
}

export type PomodoroDefaultPrompts = {
  focusPrompt: string
  breakPrompt: string
}

export type RandomMicroBreakSettings = {
  enabled: boolean
  minIntervalSeconds: number
  maxIntervalSeconds: number
  durationSeconds: number
}

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
  currentPlan: PomodoroPlanSchedule | null
  currentPlanIndex: number
  startTime: string
  startAtMs: number | null
  endAtMs: number | null
  untilStartMs: number
  nextStartAtMs: number | null
  nextStartDay: PomodoroWeekday | null
  canUseWorkbench: boolean
  shouldRestrictWorkbench: boolean
  currentProjectRef: PomodoroProjectReference | null
  currentScopedProjectId: string | null
}

export type PomodoroUpcomingSegmentPreview = {
  weekday: PomodoroWeekday
  phase: PomodoroPhase
  pomodoroIndex: number
  totalPomodoros: number
  startsInMs: number
  startAtMs: number
  projectRef: PomodoroProjectReference | null
  promptText: string
}

type PomodoroState = {
  enabled: boolean
  weeklySchedule: PomodoroWeekSchedule
  quickPomodoro: QuickPomodoroSession | null
  transitionSoundEnabled: boolean
  defaultFocusPrompt: string
  defaultBreakPrompt: string
  microBreaks: RandomMicroBreakSettings
  setEnabled: (enabled: boolean) => void
  setTransitionSoundEnabled: (enabled: boolean) => void
  setMicroBreakSettings: (settings: Partial<RandomMicroBreakSettings>) => void
  setWeeklySchedule: (weeklySchedule: PomodoroWeekSchedule) => void
  setDaySchedule: (day: PomodoroWeekday, schedule: Partial<PomodoroDaySchedule>) => void
  setSettings: (settings: {
    enabled: boolean
    weeklySchedule: PomodoroWeekSchedule
    transitionSoundEnabled?: boolean
    defaultFocusPrompt?: string
    defaultBreakPrompt?: string
    microBreaks?: Partial<RandomMicroBreakSettings>
  }) => void
  setDefaultPrompts: (prompts: Partial<PomodoroDefaultPrompts>) => void
  startQuickPomodoro: (projectRef?: PomodoroProjectReference | null) => QuickPomodoroSession
  clearQuickPomodoro: () => void
  reset: () => void
}

type PomodoroDayScheduleInput = Partial<PomodoroPlanSchedule> & {
  plans?: unknown[]
}

const DEFAULT_FOCUS_MINUTES = 25
const DEFAULT_BREAK_MINUTES = 5
const DEFAULT_POMODORO_COUNT = 4
const DEFAULT_POMODORO_START_TIME = "19:00"
const MAX_POMODORO_PROMPT_LENGTH = 200
export const QUICK_POMODORO_PREPARE_MS = 10_000
export const QUICK_POMODORO_FOCUS_MS = 25 * 60_000
const QUICK_POMODORO_PLAN_ID = "quick-pomodoro"

export const DEFAULT_RANDOM_MICRO_BREAK_SETTINGS: RandomMicroBreakSettings = {
  enabled: false,
  minIntervalSeconds: 180,
  maxIntervalSeconds: 300,
  durationSeconds: 10,
}

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

export function normalizeRandomMicroBreakSettings(value: unknown): RandomMicroBreakSettings {
  const raw = value && typeof value === "object" ? (value as Partial<RandomMicroBreakSettings>) : {}
  const minIntervalSeconds = clampInt(
    typeof raw.minIntervalSeconds === "number" ? raw.minIntervalSeconds : DEFAULT_RANDOM_MICRO_BREAK_SETTINGS.minIntervalSeconds,
    30,
    3600,
  )
  const maxIntervalSeconds = clampInt(
    typeof raw.maxIntervalSeconds === "number" ? raw.maxIntervalSeconds : DEFAULT_RANDOM_MICRO_BREAK_SETTINGS.maxIntervalSeconds,
    30,
    3600,
  )
  return {
    enabled: typeof raw.enabled === "boolean" ? raw.enabled : DEFAULT_RANDOM_MICRO_BREAK_SETTINGS.enabled,
    minIntervalSeconds,
    maxIntervalSeconds: Math.max(minIntervalSeconds, maxIntervalSeconds),
    durationSeconds: clampInt(
      typeof raw.durationSeconds === "number" ? raw.durationSeconds : DEFAULT_RANDOM_MICRO_BREAK_SETTINGS.durationSeconds,
      5,
      300,
    ),
  }
}

function normalizePomodoroPlanId(value: unknown, fallback: string) {
  const text = typeof value === "string" ? value.replace(/\s+/g, "-").trim() : ""
  return (text || fallback).slice(0, 80)
}

function normalizePomodoroProjectId(value: unknown) {
  const text = typeof value === "string" ? value.trim() : ""
  return text || null
}

function normalizePomodoroSubjectId(value: unknown) {
  const text = typeof value === "string" ? value.trim() : ""
  return text || null
}

export function pomodoroProjectRefKey(projectRef: PomodoroProjectReference | null | undefined) {
  return projectRef ? `${projectRef.subjectId}:${projectRef.scopedProjectId}` : ""
}

function normalizePomodoroProjectReference(value: unknown): PomodoroProjectReference | null {
  if (!value || typeof value !== "object") return null
  const raw = value as Partial<PomodoroProjectReference>
  const subjectId = normalizePomodoroSubjectId(raw.subjectId)
  const scopedProjectId = normalizePomodoroProjectId(raw.scopedProjectId)
  return subjectId && scopedProjectId ? { subjectId, scopedProjectId } : null
}

function createSessionId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

export function createQuickPomodoroSession(projectRef?: PomodoroProjectReference | null, now = Date.now()): QuickPomodoroSession {
  const startAtMs = now + QUICK_POMODORO_PREPARE_MS
  return {
    id: createSessionId(),
    createdAtMs: now,
    startAtMs,
    endAtMs: startAtMs + QUICK_POMODORO_FOCUS_MS,
    projectRef: normalizePomodoroProjectReference(projectRef),
  }
}

function normalizeQuickPomodoroSession(value: unknown): QuickPomodoroSession | null {
  if (!value || typeof value !== "object") return null
  const raw = value as Partial<QuickPomodoroSession>
  const createdAtMs = typeof raw.createdAtMs === "number" && Number.isFinite(raw.createdAtMs) ? raw.createdAtMs : Date.now()
  const startAtMs = typeof raw.startAtMs === "number" && Number.isFinite(raw.startAtMs) ? raw.startAtMs : createdAtMs + QUICK_POMODORO_PREPARE_MS
  const endAtMs = typeof raw.endAtMs === "number" && Number.isFinite(raw.endAtMs) ? raw.endAtMs : startAtMs + QUICK_POMODORO_FOCUS_MS
  if (endAtMs <= createdAtMs || startAtMs < createdAtMs) return null
  return {
    id: typeof raw.id === "string" && raw.id.trim() ? raw.id : createSessionId(),
    createdAtMs,
    startAtMs,
    endAtMs,
    projectRef: normalizePomodoroProjectReference(raw.projectRef),
  }
}

export function isQuickPomodoroSessionActive(quickPomodoro: QuickPomodoroSession | null | undefined, now = Date.now()) {
  return Boolean(quickPomodoro && now < quickPomodoro.endAtMs)
}

export function normalizePomodoroPromptText(value: unknown) {
  const text = typeof value === "string" ? value.replace(/\s+/g, " ").trim() : ""
  return text.slice(0, MAX_POMODORO_PROMPT_LENGTH)
}

function normalizePomodoroProjectRefs(value: unknown, pomodoroCount: number) {
  const normalizedCount = normalizePomodoroCount(pomodoroCount)
  const raw = Array.isArray(value) ? value : []
  const projectRefs: Array<PomodoroProjectReference | null> = []
  for (let index = 0; index < normalizedCount; index += 1) {
    projectRefs.push(normalizePomodoroProjectReference(raw[index]))
  }
  return projectRefs
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

export function createPomodoroPlanSchedule(
  overrides?: Partial<PomodoroPlanSchedule>,
  options?: { day?: PomodoroWeekday; index?: number },
): PomodoroPlanSchedule {
  const planIndex = options?.index ?? 0
  const fallbackId = `${options?.day ?? "plan"}-${planIndex + 1}`
  const pomodoroCount = normalizePomodoroCount(overrides?.pomodoroCount ?? DEFAULT_POMODORO_COUNT)
  return {
    id: normalizePomodoroPlanId(overrides?.id, fallbackId),
    enabled: Boolean(overrides?.enabled ?? false),
    startTime: normalizePomodoroStartTime(overrides?.startTime),
    focusMinutes: normalizeFocusMinutes(overrides?.focusMinutes ?? DEFAULT_FOCUS_MINUTES),
    breakMinutes: normalizeBreakMinutes(overrides?.breakMinutes ?? DEFAULT_BREAK_MINUTES),
    pomodoroCount,
    projectRefs: normalizePomodoroProjectRefs(overrides?.projectRefs, pomodoroCount),
    breakPrompt: normalizePomodoroPromptText(overrides?.breakPrompt),
    focusPrompts: normalizePomodoroFocusPrompts(overrides?.focusPrompts, pomodoroCount),
  }
}

export function buildQuickPomodoroPlan(quickPomodoro: QuickPomodoroSession): PomodoroPlanSchedule {
  return createPomodoroPlanSchedule(
    {
      id: QUICK_POMODORO_PLAN_ID,
      enabled: true,
      startTime: formatQuickPomodoroStartTime(quickPomodoro.startAtMs),
      focusMinutes: Math.floor(QUICK_POMODORO_FOCUS_MS / 60_000),
      breakMinutes: DEFAULT_BREAK_MINUTES,
      pomodoroCount: 1,
      projectRefs: [quickPomodoro.projectRef],
      focusPrompts: [""],
      breakPrompt: "",
    },
    { day: "mon", index: 0 },
  )
}

function formatQuickPomodoroStartTime(startAtMs: number) {
  const date = new Date(startAtMs)
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`
}

export function createPomodoroDaySchedule(
  overrides?: PomodoroDayScheduleInput,
  options?: { day?: PomodoroWeekday },
): PomodoroDaySchedule {
  const raw = overrides && typeof overrides === "object" ? (overrides as Record<string, unknown>) : {}
  const rawPlans = Array.isArray(raw.plans) ? raw.plans : raw.enabled ? [raw] : []
  const plans = rawPlans
    .map((item, index) =>
      createPomodoroPlanSchedule(
        item && typeof item === "object" ? (item as Partial<PomodoroPlanSchedule>) : {},
        { day: options?.day, index },
      ),
    )
    .sort((left, right) => readStartMinutes(left.startTime) - readStartMinutes(right.startTime) || left.id.localeCompare(right.id))
  return { plans }
}

export function createPomodoroWeekSchedule(overrides?: Partial<Record<PomodoroWeekday, PomodoroDayScheduleInput>>) {
  return POMODORO_WEEKDAYS.reduce((result, day) => {
    result[day] = createPomodoroDaySchedule(overrides?.[day], { day })
    return result
  }, {} as PomodoroWeekSchedule)
}

export function clonePomodoroWeekSchedule(weeklySchedule: PomodoroWeekSchedule) {
  return POMODORO_WEEKDAYS.reduce((result, day) => {
    result[day] = createPomodoroDaySchedule(weeklySchedule[day], { day })
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
    const schedule = item && typeof item === "object" ? (item as Record<string, unknown>) : {}
    const rawPlans = Array.isArray(schedule.plans) ? schedule.plans : schedule.enabled ? [schedule] : []
    result[day] = createPomodoroDaySchedule(
      {
        plans: rawPlans.map((rawPlan) => {
          const plan = rawPlan && typeof rawPlan === "object" ? (rawPlan as Partial<PomodoroPlanSchedule>) : {}
          return {
            ...plan,
            enabled: plan.enabled ?? (Array.isArray(schedule.plans) ? true : Boolean(schedule.enabled)),
            focusMinutes: typeof plan.focusMinutes === "number" ? plan.focusMinutes : fallbackFocusMinutes,
            breakMinutes: typeof plan.breakMinutes === "number" ? plan.breakMinutes : fallbackBreakMinutes,
            pomodoroCount: typeof plan.pomodoroCount === "number" ? plan.pomodoroCount : fallbackPomodoroCount,
          }
        }),
      },
      { day },
    )
    return result
  }, {} as PomodoroWeekSchedule)
}

export function hasEnabledPomodoroSchedule(weeklySchedule: PomodoroWeekSchedule) {
  return POMODORO_WEEKDAYS.some((day) => getActivePomodoroDayPlans(weeklySchedule[day]).length > 0)
}

export function getActivePomodoroDayPlans(daySchedule: PomodoroDaySchedule) {
  return [...(daySchedule?.plans ?? [])]
    .filter((plan) => plan.enabled)
    .sort((left, right) => readStartMinutes(left.startTime) - readStartMinutes(right.startTime) || left.id.localeCompare(right.id))
}

function readStartMinutes(startTime: string) {
  const [hoursText, minutesText] = normalizePomodoroStartTime(startTime).split(":")
  const hours = Number.parseInt(hoursText ?? "0", 10)
  const minutes = Number.parseInt(minutesText ?? "0", 10)
  return hours * 60 + minutes
}

function getPomodoroPlanDurationMs(plan: PomodoroPlanSchedule) {
  const focusDurationMs = normalizeFocusMinutes(plan.focusMinutes) * 60_000
  const breakDurationMs = normalizeBreakMinutes(plan.breakMinutes) * 60_000
  const pomodoroCount = normalizePomodoroCount(plan.pomodoroCount)
  return focusDurationMs * pomodoroCount + breakDurationMs * Math.max(0, pomodoroCount - 1)
}

export function validatePomodoroWeekSchedule(weeklySchedule: PomodoroWeekSchedule) {
  const normalized = normalizePomodoroWeekSchedule(weeklySchedule)
  const messages: string[] = []

  for (const day of POMODORO_WEEKDAYS) {
    const ranges = getActivePomodoroDayPlans(normalized[day]).map((plan) => {
      const startMinutes = readStartMinutes(plan.startTime)
      const endMinutes = startMinutes + getPomodoroPlanDurationMs(plan) / 60_000
      return { plan, startMinutes, endMinutes }
    })

    for (const range of ranges) {
      if (range.endMinutes > 24 * 60) {
        messages.push(`${POMODORO_WEEKDAY_LABELS[day]} ${range.plan.startTime} 的计划不能跨过当天 24:00`)
      }
    }

    const sortedRanges = ranges
      .filter((range) => range.endMinutes <= 24 * 60)
      .sort((left, right) => left.startMinutes - right.startMinutes || left.plan.id.localeCompare(right.plan.id))
    for (let index = 1; index < sortedRanges.length; index += 1) {
      const previous = sortedRanges[index - 1]
      const current = sortedRanges[index]
      if (previous && current && current.startMinutes < previous.endMinutes) {
        messages.push(
          `${POMODORO_WEEKDAY_LABELS[day]} 计划时间冲突：${previous.plan.startTime} 与 ${current.plan.startTime}`,
        )
      }
    }
  }

  return messages
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
    const candidatePlans = getActivePomodoroDayPlans(weeklySchedule[candidateDay])
    for (const candidatePlan of candidatePlans) {
      const candidateStartAtMs = getScheduledStartAtMs(candidateDate, candidatePlan.startTime)
      if (candidateStartAtMs > now) {
        return {
          nextStartAtMs: candidateStartAtMs,
          nextStartDay: candidateDay,
        }
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
    quickPomodoro: null,
    transitionSoundEnabled: false,
    defaultFocusPrompt: "",
    defaultBreakPrompt: "",
    microBreaks: normalizeRandomMicroBreakSettings(DEFAULT_RANDOM_MICRO_BREAK_SETTINGS),
  }
}

export function buildPomodoroSegments(
  focusMinutes: number,
  breakMinutes: number,
  pomodoroCount: number,
  projectRefs?: Array<PomodoroProjectReference | null>,
  focusPrompts?: string[],
  breakPrompt?: string,
  options?: { planId?: string; planIndex?: number },
): PomodoroSegment[] {
  const normalizedFocusMinutes = normalizeFocusMinutes(focusMinutes)
  const normalizedBreakMinutes = normalizeBreakMinutes(breakMinutes)
  const normalizedPomodoroCount = normalizePomodoroCount(pomodoroCount)
  const normalizedProjectRefs = normalizePomodoroProjectRefs(projectRefs, normalizedPomodoroCount)
  const normalizedFocusPrompts = normalizePomodoroFocusPrompts(focusPrompts, normalizedPomodoroCount)
  const normalizedBreakPrompt = normalizePomodoroPromptText(breakPrompt)
  const planId = normalizePomodoroPlanId(options?.planId, "plan-1")
  const planIndex = options?.planIndex ?? 0
  const focusDurationMs = normalizedFocusMinutes * 60_000
  const breakDurationMs = normalizedBreakMinutes * 60_000
  const segments: PomodoroSegment[] = []
  let offsetMs = 0

  for (let index = 0; index < normalizedPomodoroCount; index += 1) {
    segments.push({
      phase: "focus",
      planId,
      planIndex,
      pomodoroIndex: index + 1,
      durationMs: focusDurationMs,
      startOffsetMs: offsetMs,
      endOffsetMs: offsetMs + focusDurationMs,
      projectRef: normalizedProjectRefs[index] ?? null,
      promptText: normalizedFocusPrompts[index] ?? "",
    })
    offsetMs += focusDurationMs

    if (index < normalizedPomodoroCount - 1) {
      segments.push({
        phase: "break",
        planId,
        planIndex,
        pomodoroIndex: index + 1,
        durationMs: breakDurationMs,
        startOffsetMs: offsetMs,
        endOffsetMs: offsetMs + breakDurationMs,
        projectRef: null,
        promptText: normalizedBreakPrompt,
      })
      offsetMs += breakDurationMs
    }
  }

  return segments
}

export function getPomodoroSnapshot(
  input: { enabled: boolean; weeklySchedule: PomodoroWeekSchedule; quickPomodoro?: QuickPomodoroSession | null },
  now = Date.now(),
): PomodoroSnapshot {
  const weeklySchedule = normalizePomodoroWeekSchedule(input.weeklySchedule)
  const quickPomodoro = normalizeQuickPomodoroSession(input.quickPomodoro)
  const activeQuickPomodoro = quickPomodoro && now < quickPomodoro.endAtMs ? quickPomodoro : null
  const scheduledEnabled = Boolean(input.enabled)
  const enabled = scheduledEnabled || Boolean(activeQuickPomodoro)
  const hasScheduledEnabledSchedule = hasEnabledPomodoroSchedule(weeklySchedule)
  const hasEnabledSchedule = hasScheduledEnabledSchedule || Boolean(activeQuickPomodoro)
  const date = new Date(now)
  const weekday = getPomodoroWeekday(date)
  const todaySchedule = weeklySchedule[weekday]
  const todayPlans = getActivePomodoroDayPlans(todaySchedule)
  const todayPlanRanges = todayPlans.map((plan, planIndex) => {
    const segments = buildPomodoroSegments(
      plan.focusMinutes,
      plan.breakMinutes,
      plan.pomodoroCount,
      plan.projectRefs,
      plan.focusPrompts,
      plan.breakPrompt,
      { planId: plan.id, planIndex },
    )
    const startAtMs = getScheduledStartAtMs(date, plan.startTime)
    const totalMs = segments.at(-1)?.endOffsetMs ?? 0
    return {
      plan,
      planIndex,
      segments,
      totalMs,
      startAtMs,
      endAtMs: startAtMs + totalMs,
    }
  })
  const todayTimeline = todayPlanRanges.flatMap((range) =>
    range.segments.map((segment) => ({
      ...range,
      segment,
      segmentStartAtMs: range.startAtMs + segment.startOffsetMs,
      segmentEndAtMs: range.startAtMs + segment.endOffsetMs,
    })),
  )
  const firstTodayRange = todayPlanRanges[0] ?? null
  const lastTodayRange = todayPlanRanges.at(-1) ?? null
  const nextStart =
    activeQuickPomodoro && activeQuickPomodoro.startAtMs > now
      ? { nextStartAtMs: activeQuickPomodoro.startAtMs, nextStartDay: weekday }
      : findNextPomodoroStart(now, weeklySchedule)

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
    totalPomodoros: firstTodayRange?.plan.pomodoroCount ?? 0,
    currentPomodoro: 0,
    completedPomodoros: 0,
    totalMs: firstTodayRange?.totalMs ?? 0,
    remainingMs: 0,
    segmentRemainingMs: 0,
    segmentIndex: -1,
    progressRatio: 0,
    segmentProgressRatio: 0,
    segment: null,
    currentPlan: firstTodayRange?.plan ?? null,
    currentPlanIndex: firstTodayRange?.planIndex ?? -1,
    startTime: firstTodayRange?.plan.startTime ?? DEFAULT_POMODORO_START_TIME,
    startAtMs: firstTodayRange?.startAtMs ?? null,
    endAtMs: firstTodayRange?.endAtMs ?? null,
    untilStartMs: 0,
    nextStartAtMs: nextStart.nextStartAtMs,
    nextStartDay: nextStart.nextStartDay,
    canUseWorkbench: false,
    shouldRestrictWorkbench: enabled,
    currentProjectRef: null,
    currentScopedProjectId: null,
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

  if (activeQuickPomodoro) {
    const quickPlan = buildQuickPomodoroPlan(activeQuickPomodoro)
    const quickSegments = buildPomodoroSegments(
      quickPlan.focusMinutes,
      quickPlan.breakMinutes,
      quickPlan.pomodoroCount,
      quickPlan.projectRefs,
      quickPlan.focusPrompts,
      quickPlan.breakPrompt,
      { planId: quickPlan.id, planIndex: -1 },
    )
    const quickSegment = quickSegments[0] ?? null

    if (now < activeQuickPomodoro.startAtMs) {
      return createBaseSnapshot({
        status: "idle",
        idleReason: "waiting",
        totalPomodoros: 1,
        currentPomodoro: 0,
        completedPomodoros: 0,
        totalMs: QUICK_POMODORO_FOCUS_MS,
        currentPlan: quickPlan,
        currentPlanIndex: -1,
        startTime: quickPlan.startTime,
        startAtMs: activeQuickPomodoro.startAtMs,
        endAtMs: activeQuickPomodoro.endAtMs,
        untilStartMs: Math.max(0, activeQuickPomodoro.startAtMs - now),
        nextStartAtMs: activeQuickPomodoro.startAtMs,
        nextStartDay: weekday,
        shouldRestrictWorkbench: true,
      })
    }

    const elapsedMs = Math.max(0, now - activeQuickPomodoro.startAtMs)
    const remainingMs = Math.max(0, activeQuickPomodoro.endAtMs - now)
    const currentProjectRef = quickSegment?.projectRef ?? null
    const canUseWorkbench = Boolean(currentProjectRef)

    return createBaseSnapshot({
      status: "running",
      idleReason: null,
      phase: "focus",
      totalPomodoros: 1,
      currentPomodoro: 1,
      completedPomodoros: 0,
      totalMs: QUICK_POMODORO_FOCUS_MS,
      remainingMs,
      segmentRemainingMs: remainingMs,
      segmentIndex: 0,
      progressRatio: Math.min(1, elapsedMs / QUICK_POMODORO_FOCUS_MS),
      segmentProgressRatio: Math.min(1, elapsedMs / QUICK_POMODORO_FOCUS_MS),
      segment: quickSegment,
      currentPlan: quickPlan,
      currentPlanIndex: -1,
      startTime: quickPlan.startTime,
      startAtMs: activeQuickPomodoro.startAtMs,
      endAtMs: activeQuickPomodoro.endAtMs,
      canUseWorkbench,
      shouldRestrictWorkbench: !canUseWorkbench,
      currentProjectRef,
      currentScopedProjectId: currentProjectRef?.scopedProjectId ?? null,
    })
  }

  if (!hasEnabledSchedule) {
    return createBaseSnapshot({
      status: "idle",
      idleReason: "not_configured",
    })
  }

  if (todayPlanRanges.length === 0) {
    return createBaseSnapshot({
      status: "idle",
      idleReason: "day_off",
      totalMs: 0,
      startAtMs: null,
      endAtMs: null,
    })
  }

  const runningTimelineIndex = todayTimeline.findIndex(
    (item) => now >= item.segmentStartAtMs && now < item.segmentEndAtMs,
  )
  const runningItem = runningTimelineIndex >= 0 ? todayTimeline[runningTimelineIndex] : null
  const upcomingRange = todayPlanRanges.find((range) => range.startAtMs > now) ?? null

  if (!runningItem && upcomingRange) {
    return createBaseSnapshot({
      status: "idle",
      idleReason: "waiting",
      totalPomodoros: upcomingRange.plan.pomodoroCount,
      totalMs: upcomingRange.totalMs,
      currentPlan: upcomingRange.plan,
      currentPlanIndex: upcomingRange.planIndex,
      startTime: upcomingRange.plan.startTime,
      startAtMs: upcomingRange.startAtMs,
      endAtMs: upcomingRange.endAtMs,
      untilStartMs: Math.max(0, upcomingRange.startAtMs - now),
    })
  }

  if (!runningItem || (lastTodayRange && now >= lastTodayRange.endAtMs)) {
    const completedPomodoros = todayPlanRanges.reduce((sum, range) => sum + range.plan.pomodoroCount, 0)
    return createBaseSnapshot({
      status: "completed",
      idleReason: null,
      totalPomodoros: completedPomodoros,
      currentPomodoro: completedPomodoros,
      completedPomodoros,
      totalMs: todayPlanRanges.reduce((sum, range) => sum + range.totalMs, 0),
      remainingMs: 0,
      segmentRemainingMs: 0,
      segmentIndex: todayTimeline.length - 1,
      progressRatio: 1,
      segmentProgressRatio: 1,
      segment: todayTimeline.at(-1)?.segment ?? null,
      currentPlan: lastTodayRange?.plan ?? null,
      currentPlanIndex: lastTodayRange?.planIndex ?? -1,
      startTime: lastTodayRange?.plan.startTime ?? DEFAULT_POMODORO_START_TIME,
      startAtMs: lastTodayRange?.startAtMs ?? null,
      endAtMs: lastTodayRange?.endAtMs ?? null,
    })
  }

  const elapsedMs = Math.max(0, now - runningItem.startAtMs)
  const segment = runningItem.segment
  const segmentElapsedMs = segment ? Math.max(0, elapsedMs - segment.startOffsetMs) : 0
  const segmentRemainingMs = segment ? Math.max(0, segment.endOffsetMs - elapsedMs) : 0
  const completedPomodoros = runningItem.segments.filter(
    (item) => item.phase === "focus" && item.endOffsetMs <= elapsedMs,
  ).length
  const currentProjectRef = segment?.phase === "focus" ? segment.projectRef ?? null : null
  const canUseWorkbench = Boolean(currentProjectRef)

  return createBaseSnapshot({
    status: "running",
    idleReason: null,
    phase: segment?.phase ?? null,
    totalPomodoros: runningItem.plan.pomodoroCount,
    currentPomodoro: segment?.pomodoroIndex ?? 0,
    completedPomodoros,
    totalMs: runningItem.totalMs,
    remainingMs: Math.max(0, runningItem.totalMs - elapsedMs),
    segmentRemainingMs,
    segmentIndex: runningTimelineIndex,
    progressRatio: runningItem.totalMs > 0 ? Math.min(1, elapsedMs / runningItem.totalMs) : 0,
    segmentProgressRatio: segment && segment.durationMs > 0 ? Math.min(1, segmentElapsedMs / segment.durationMs) : 0,
    segment,
    currentPlan: runningItem.plan,
    currentPlanIndex: runningItem.planIndex,
    startTime: runningItem.plan.startTime,
    startAtMs: runningItem.startAtMs,
    endAtMs: runningItem.endAtMs,
    canUseWorkbench,
    shouldRestrictWorkbench: !canUseWorkbench,
    currentProjectRef,
    currentScopedProjectId: currentProjectRef?.scopedProjectId ?? null,
  })
}

export function getPomodoroUpcomingSegmentPreview(
  input: { enabled: boolean; weeklySchedule: PomodoroWeekSchedule; quickPomodoro?: QuickPomodoroSession | null },
  now = Date.now(),
): PomodoroUpcomingSegmentPreview | null {
  const snapshot = getPomodoroSnapshot(input, now)
  if (!snapshot.enabled || !snapshot.hasEnabledSchedule) return null

  if (snapshot.status === "idle" && snapshot.idleReason === "waiting") {
    const projectRef = snapshot.currentPlan?.projectRefs[0] ?? null
    if (snapshot.startAtMs === null) return null
    return {
      weekday: snapshot.weekday,
      phase: "focus",
      pomodoroIndex: 1,
      totalPomodoros: snapshot.totalPomodoros,
      startsInMs: snapshot.untilStartMs,
      startAtMs: snapshot.startAtMs,
      projectRef,
      promptText: snapshot.currentPlan?.focusPrompts[0] ?? "",
    }
  }

  if (snapshot.status === "running" && snapshot.currentPlan && snapshot.segment) {
    const segments = buildPomodoroSegments(
      snapshot.currentPlan.focusMinutes,
      snapshot.currentPlan.breakMinutes,
      snapshot.currentPlan.pomodoroCount,
      snapshot.currentPlan.projectRefs,
      snapshot.currentPlan.focusPrompts,
      snapshot.currentPlan.breakPrompt,
      { planId: snapshot.currentPlan.id, planIndex: snapshot.currentPlanIndex },
    )
    const currentSegmentIndex = segments.findIndex(
      (segment) =>
        segment.phase === snapshot.segment?.phase &&
        segment.pomodoroIndex === snapshot.segment?.pomodoroIndex &&
        segment.startOffsetMs === snapshot.segment?.startOffsetMs,
    )
    const nextSegment = currentSegmentIndex >= 0 ? segments[currentSegmentIndex + 1] : null
    if (snapshot.startAtMs === null) {
      return null
    }
    if (!nextSegment) {
      if (snapshot.currentPlan.id === QUICK_POMODORO_PLAN_ID) return null
      const finalBreakPreview =
        snapshot.segment.phase === "focus"
          ? {
              weekday: snapshot.weekday,
              phase: "break" as const,
              pomodoroIndex: snapshot.segment.pomodoroIndex,
              totalPomodoros: snapshot.totalPomodoros,
              startsInMs: snapshot.segmentRemainingMs,
              startAtMs: snapshot.startAtMs + snapshot.segment.endOffsetMs,
              projectRef: null,
              promptText: snapshot.currentPlan.breakPrompt,
            }
          : null
      return finalBreakPreview
    }
    return {
      weekday: snapshot.weekday,
      phase: nextSegment.phase,
      pomodoroIndex: nextSegment.pomodoroIndex,
      totalPomodoros: snapshot.totalPomodoros,
      startsInMs: snapshot.segmentRemainingMs,
      startAtMs: snapshot.startAtMs + nextSegment.startOffsetMs,
      projectRef: nextSegment.projectRef ?? null,
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
    const refreshNow = () => {
      setNow(Date.now())
    }
    const initialTimer = window.setTimeout(refreshNow, 0)
    if (!enabled) {
      return () => window.clearTimeout(initialTimer)
    }
    const timer = window.setInterval(() => {
      refreshNow()
    }, 1000)
    return () => {
      window.clearTimeout(initialTimer)
      window.clearInterval(timer)
    }
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
      setMicroBreakSettings: (settings) =>
        set((state) => ({
          ...state,
          microBreaks: normalizeRandomMicroBreakSettings({ ...state.microBreaks, ...settings }),
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
            [day]: createPomodoroDaySchedule(schedule, { day }),
          },
        })),
      setSettings: (settings) =>
        set((state) => ({
          enabled: Boolean(settings.enabled),
          weeklySchedule: normalizePomodoroWeekSchedule(settings.weeklySchedule),
          quickPomodoro: state.quickPomodoro,
          transitionSoundEnabled: Boolean(settings.transitionSoundEnabled),
          defaultFocusPrompt: normalizePomodoroPromptText(settings.defaultFocusPrompt ?? state.defaultFocusPrompt),
          defaultBreakPrompt: normalizePomodoroPromptText(settings.defaultBreakPrompt ?? state.defaultBreakPrompt),
          microBreaks: normalizeRandomMicroBreakSettings(settings.microBreaks ?? state.microBreaks),
        })),
      setDefaultPrompts: (prompts) =>
        set((state) => ({
          ...state,
          defaultFocusPrompt: normalizePomodoroPromptText(prompts.focusPrompt ?? state.defaultFocusPrompt),
          defaultBreakPrompt: normalizePomodoroPromptText(prompts.breakPrompt ?? state.defaultBreakPrompt),
        })),
      startQuickPomodoro: (projectRef) => {
        const quickPomodoro = createQuickPomodoroSession(projectRef)
        set((state) => ({
          ...state,
          quickPomodoro,
        }))
        return quickPomodoro
      },
      clearQuickPomodoro: () =>
        set((state) => ({
          ...state,
          quickPomodoro: null,
        })),
      reset: () => set(createInitialState()),
    }),
    {
      name: "plm-pomodoro",
      version: 10,
      migrate: (persistedState: unknown, version) => {
        if (!persistedState || typeof persistedState !== "object") {
          return persistedState as PomodoroState
        }
        const raw = persistedState as {
          enabled?: unknown
          weeklySchedule?: unknown
          quickPomodoro?: unknown
          transitionSoundEnabled?: unknown
          defaultFocusPrompt?: unknown
          defaultBreakPrompt?: unknown
          microBreaks?: unknown
          focusMinutes?: unknown
          breakMinutes?: unknown
          pomodoroCount?: unknown
        }

        if (version >= 7) {
          return {
            enabled: typeof raw.enabled === "boolean" ? raw.enabled : false,
            weeklySchedule: normalizePomodoroWeekSchedule(raw.weeklySchedule),
            quickPomodoro: normalizeQuickPomodoroSession(raw.quickPomodoro),
            transitionSoundEnabled: typeof raw.transitionSoundEnabled === "boolean" ? raw.transitionSoundEnabled : false,
            defaultFocusPrompt: normalizePomodoroPromptText(raw.defaultFocusPrompt),
            defaultBreakPrompt: normalizePomodoroPromptText(raw.defaultBreakPrompt),
            microBreaks: normalizeRandomMicroBreakSettings(raw.microBreaks),
          } as PomodoroState
        }

        return {
          enabled: typeof raw.enabled === "boolean" ? raw.enabled : false,
          weeklySchedule: normalizePomodoroWeekSchedule(raw.weeklySchedule, {
            focusMinutes: raw.focusMinutes,
            breakMinutes: raw.breakMinutes,
            pomodoroCount: raw.pomodoroCount,
          }),
          quickPomodoro: null,
          transitionSoundEnabled: false,
          defaultFocusPrompt: "",
          defaultBreakPrompt: "",
          microBreaks: normalizeRandomMicroBreakSettings(DEFAULT_RANDOM_MICRO_BREAK_SETTINGS),
        } as PomodoroState
      },
    },
  ),
)

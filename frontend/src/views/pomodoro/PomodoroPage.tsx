import { useEffect, useMemo, useState } from "react"
import { BellRing, CheckCircle2, Clock3, Coffee, Lock, PanelsTopLeft, RotateCcw, Save, TimerReset, Volume2 } from "lucide-react"
import { Link, useLocation } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import type { ReviewChainTemplateItem } from "@/ui/api/projectConfig"
import { playPomodoroTransitionSound, playPomodoroVoicePrompt, unlockPomodoroAudio } from "@/ui/pomodoroAudio"
import { ContentNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useCurrentUser } from "@/ui/queries/auth"
import { useProject, useProjects } from "@/ui/queries/projects"
import { useUpdateMyGlobalSettings } from "@/ui/queries/profile"
import { useSystemCapabilities } from "@/ui/queries/system"
import { usePageMeta } from "@/ui/seo/usePageMeta"
import { useAppStore } from "@/ui/store/appStore"
import { showErrorFeedback, showInfoFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { useGlobalConfigStore } from "@/ui/store/globalConfigStore"
import { usePomodoroDailyReportStore, type DailyReportDirection } from "@/ui/store/pomodoroDailyReportStore"
import { summarizeLearningPlanDaily } from "@/ui/learningPlans/learningPlanEvaluation"
import { selectActiveLearningPlans, useLearningPlanStore } from "@/ui/store/learningPlanStore"
import { loadDailyStudyPresenceTotalsByDate } from "@/ui/store/studyPresenceStore"
import {
  POMODORO_WEEKDAYS,
  POMODORO_WEEKDAY_LABELS,
  buildPomodoroSegments,
  describePomodoroPhase,
  formatPomodoroCountdown,
  formatPomodoroDuration,
  getPomodoroSnapshot,
  normalizePomodoroStartTime,
  normalizePomodoroWeekSchedule,
  type PomodoroDaySchedule,
  type PomodoroSegment,
  type PomodoroSnapshot,
  type PomodoroWeekSchedule,
  type PomodoroWeekday,
  usePomodoroNow,
  usePomodoroStore,
} from "@/ui/store/pomodoroStore"
import { getLocalDateKey, loadDailyStudyTotalsByDate, type DailyWorkbenchStats } from "@/ui/store/workbenchDailyStats"
import { useThemeStore } from "@/ui/store/themeStore"
import { cn } from "@/ui/utils"
import { buildPomodoroPath } from "@/views/pomodoro/pomodoroRouting"

type PomodoroDraftDay = {
  enabled: boolean
  startTime: string
  focusMinutes: string
  breakMinutes: string
  pomodoroCount: string
  projectIds: Array<string | null>
  breakPrompt: string
  focusPrompts: string[]
}

type PomodoroDraft = Record<PomodoroWeekday, PomodoroDraftDay>

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function parsePositiveInteger(value: string, fallback: number) {
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) ? parsed : fallback
}

function clampInteger(value: number, min: number, max: number) {
  if (!Number.isFinite(value)) return min
  return Math.min(max, Math.max(min, Math.round(value)))
}

function normalizeFocusInput(value: string, fallback: number) {
  return clampInteger(parsePositiveInteger(value, fallback), 1, 180)
}

function normalizeBreakInput(value: string, fallback: number) {
  return clampInteger(parsePositiveInteger(value, fallback), 1, 60)
}

function normalizeCountInput(value: string, fallback: number) {
  return clampInteger(parsePositiveInteger(value, fallback), 1, 12)
}

function normalizeDraftProjectIds(projectIds: Array<string | null> | undefined, pomodoroCount: number) {
  const normalizedCount = clampInteger(pomodoroCount, 1, 12)
  return Array.from({ length: normalizedCount }, (_, index) => {
    const value = projectIds?.[index]
    return typeof value === "string" && value.trim() ? value.trim() : null
  })
}

function normalizeDraftPromptText(value: string | null | undefined) {
  return String(value ?? "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 200)
}

function normalizeDraftFocusPrompts(focusPrompts: string[] | undefined, pomodoroCount: number) {
  const normalizedCount = clampInteger(pomodoroCount, 1, 12)
  return Array.from({ length: normalizedCount }, (_, index) => normalizeDraftPromptText(focusPrompts?.[index]))
}

function clonePomodoroDraftDay(day: PomodoroDraftDay): PomodoroDraftDay {
  return {
    ...day,
    projectIds: [...day.projectIds],
    focusPrompts: [...day.focusPrompts],
  }
}

function toPomodoroDraft(weeklySchedule: PomodoroWeekSchedule): PomodoroDraft {
  return POMODORO_WEEKDAYS.reduce((result, day) => {
    const schedule = weeklySchedule[day]
    result[day] = {
      enabled: schedule.enabled,
      startTime: schedule.startTime,
      focusMinutes: String(schedule.focusMinutes),
      breakMinutes: String(schedule.breakMinutes),
      pomodoroCount: String(schedule.pomodoroCount),
      projectIds: normalizeDraftProjectIds(schedule.projectIds, schedule.pomodoroCount),
      breakPrompt: normalizeDraftPromptText(schedule.breakPrompt),
      focusPrompts: normalizeDraftFocusPrompts(schedule.focusPrompts, schedule.pomodoroCount),
    }
    return result
  }, {} as PomodoroDraft)
}

function buildPomodoroScheduleFromDraft(draft: PomodoroDraft): PomodoroWeekSchedule {
  return normalizePomodoroWeekSchedule(
    POMODORO_WEEKDAYS.reduce((result, day) => {
      const item = draft[day]
      result[day] = {
        enabled: item.enabled,
        startTime: normalizePomodoroStartTime(item.startTime),
        focusMinutes: normalizeFocusInput(item.focusMinutes, 25),
        breakMinutes: normalizeBreakInput(item.breakMinutes, 5),
        pomodoroCount: normalizeCountInput(item.pomodoroCount, 4),
        projectIds: normalizeDraftProjectIds(
          item.projectIds,
          normalizeCountInput(item.pomodoroCount, 4),
        ),
        breakPrompt: normalizeDraftPromptText(item.breakPrompt),
        focusPrompts: normalizeDraftFocusPrompts(
          item.focusPrompts,
          normalizeCountInput(item.pomodoroCount, 4),
        ),
      }
      return result
    }, {} as Record<PomodoroWeekday, PomodoroDaySchedule>),
  )
}

function findFirstEnabledDay(weeklySchedule: PomodoroWeekSchedule) {
  return POMODORO_WEEKDAYS.find((day) => weeklySchedule[day].enabled) ?? "mon"
}

function timelineTone(status: "done" | "current" | "upcoming", phase: PomodoroSegment["phase"]) {
  if (status === "current") {
    return phase === "focus"
      ? "border-primary/20 bg-[hsl(var(--primary)/0.08)] text-foreground"
      : "border-amber-200 bg-amber-50 text-amber-950"
  }
  if (status === "done") {
    return "border-emerald-200 bg-emerald-50 text-emerald-950"
  }
  return "border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] text-[color:var(--theme-soft-text-strong)]"
}

function PhaseBadge(props: { snapshot: PomodoroSnapshot }) {
  const { snapshot } = props
  const label = describePomodoroPhase(
    snapshot.phase,
    snapshot.status,
    snapshot.idleReason,
    snapshot.enabled,
    snapshot.hasEnabledSchedule,
  )
  const className =
    snapshot.status === "completed"
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : snapshot.phase === "focus"
        ? "border-primary/15 bg-[hsl(var(--primary)/0.08)] text-primary"
        : snapshot.phase === "break"
          ? "border-amber-200 bg-amber-50 text-amber-800"
          : "border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] text-[color:var(--theme-subtle-text)]"
  return <span className={cn("inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium", className)}>{label}</span>
}

function MetricTile(props: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-[1.15rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] px-4 py-4">
      <div className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">{props.label}</div>
      <div className="mt-2 text-lg font-semibold tracking-[-0.02em] text-foreground">{props.value}</div>
      {props.hint ? <div className="mt-1 text-xs leading-5 text-muted-foreground">{props.hint}</div> : null}
    </div>
  )
}

function readLocationState(locationState: unknown) {
  if (!locationState || typeof locationState !== "object") {
    return {
      fromPath: "",
      blockedProjectId: "",
      targetProjectId: "",
    }
  }
  const input = locationState as { from?: unknown; blockedProjectId?: unknown; targetProjectId?: unknown }
  return {
    fromPath: typeof input.from === "string" ? input.from : "",
    blockedProjectId: typeof input.blockedProjectId === "string" ? input.blockedProjectId : "",
    targetProjectId: typeof input.targetProjectId === "string" ? input.targetProjectId : "",
  }
}

function formatDateTime(ms: number | null) {
  if (ms === null) return "未设置"
  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(ms)
}

function formatReportUpdatedAt(ms: number | null) {
  if (ms === null) return "尚未保存"
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(ms)
}

function describeProjectLabel(projectId: string | null, projectTitleMap: Map<string, string>) {
  if (!projectId) return "未指定项目"
  return projectTitleMap.get(projectId) || "已删除或无权限项目"
}

function sumFocusDurationMs(schedule: PomodoroDaySchedule) {
  return schedule.focusMinutes * schedule.pomodoroCount * 60_000
}

function buildDailyReportObjectiveSummary(stats: DailyWorkbenchStats, scheduledFocusMs: number) {
  if (stats.effectiveMs <= 0) {
    return scheduledFocusMs > 0 ? "今天的番茄组已完成；学习行为时长还在等待工作台同步。" : "今天还没有学习行为时长。"
  }
  const ratio = scheduledFocusMs > 0 ? stats.effectiveMs / scheduledFocusMs : 0
  if (ratio >= 0.9) return "客观投入接近或超过今日番茄计划。"
  if (ratio >= 0.5) return "客观投入已经过半，日报里可以记录一下中途卡点。"
  return "客观投入低于排程焦点时长，建议在主观复盘里写明原因。"
}

const DAILY_REPORT_DIRECTION_OPTIONS: Array<{ value: Exclude<DailyReportDirection, "">; label: string; hint: string }> = [
  { value: "progress", label: "进步了", hint: "今天更清楚、更稳定，或推进了关键材料。" },
  { value: "flat", label: "持平", hint: "节奏基本稳定，但还没有明显突破。" },
  { value: "regress", label: "退步了", hint: "效率、理解、执行或状态比预期更弱。" },
]

function describeCurrentState(snapshot: PomodoroSnapshot, projectTitleMap: Map<string, string>) {
  const currentProjectLabel = describeProjectLabel(snapshot.currentProjectId, projectTitleMap)
  if (!snapshot.enabled) {
    return "番茄钟当前关闭，所有项目工作台都可直接访问。"
  }
  if (!snapshot.hasEnabledSchedule) {
    return "番茄钟已开启，但还没有启用任何日期排程。先给至少一天设定开始时间，系统才会按时自动开始。"
  }
  if (snapshot.status === "running") {
    return snapshot.phase === "focus"
      ? snapshot.currentProjectId
        ? `当前是第 ${snapshot.currentPomodoro}/${snapshot.totalPomodoros} 个学习番茄，系统会把工作台收敛到“${currentProjectLabel}”。`
        : `当前是第 ${snapshot.currentPomodoro}/${snapshot.totalPomodoros} 个学习番茄，但这个番茄还没有绑定项目，所以暂时不会自动跳转。`
      : `当前处于第 ${snapshot.currentPomodoro}/${snapshot.totalPomodoros} 个番茄后的间歇时间，所有项目工作台都会暂时锁定。`
  }
  if (snapshot.status === "completed") {
    return `今天的番茄组已经跑完，下次会在 ${formatDateTime(snapshot.nextStartAtMs)} 自动开始。`
  }
  if (snapshot.idleReason === "waiting") {
    return `今天会在 ${snapshot.startTime} 自动开始。现在距离学习时段还有 ${formatPomodoroCountdown(snapshot.untilStartMs)}。`
  }
  if (snapshot.idleReason === "day_off") {
    return `今天没有安排番茄组，工作台会整天保持锁定。下次自动开始时间是 ${formatDateTime(snapshot.nextStartAtMs)}。`
  }
  return "番茄钟会按照你设定的每周排程自动开始。"
}

function resolvePreviewDay(snapshot: PomodoroSnapshot) {
  if (snapshot.todaySchedule.enabled) return snapshot.weekday
  if (snapshot.nextStartDay) return snapshot.nextStartDay
  return snapshot.weekday
}

export function PomodoroPage() {
  const location = useLocation()
  const selectedProjectId = useAppStore((state) => state.selectedProjectId)
  const { projectTitle: selectedProjectTitle } = useProject(selectedProjectId ?? "", { enabled: Boolean(selectedProjectId) })
  const projectsQ = useProjects(true)
  const selectedTheme = useThemeStore((state) => state.theme)
  const defaultProjectReviewTemplate = useGlobalConfigStore((state) => state.defaultProjectReviewTemplate)
  const enabled = usePomodoroStore((state) => state.enabled)
  const weeklySchedule = usePomodoroStore((state) => state.weeklySchedule)
  const transitionSoundEnabled = usePomodoroStore((state) => state.transitionSoundEnabled)
  const setEnabled = usePomodoroStore((state) => state.setEnabled)
  const setTransitionSoundEnabled = usePomodoroStore((state) => state.setTransitionSoundEnabled)
  const setSettings = usePomodoroStore((state) => state.setSettings)
  const reportsByDate = usePomodoroDailyReportStore((state) => state.reportsByDate)
  const getDailyReport = usePomodoroDailyReportStore((state) => state.getReport)
  const updateDailyReport = usePomodoroDailyReportStore((state) => state.updateReport)
  const plansById = useLearningPlanStore((state) => state.plansById)
  const progressSnapshotsByPlanId = useLearningPlanStore((state) => state.progressSnapshotsByPlanId)
  const now = usePomodoroNow(enabled)
  const { fromPath, blockedProjectId, targetProjectId } = useMemo(() => readLocationState(location.state), [location.state])
  const [pomodoroDraft, setPomodoroDraft] = useState<PomodoroDraft>(() => toPomodoroDraft(weeklySchedule))
  const [testingPromptKey, setTestingPromptKey] = useState("")
  const [statsRevision, setStatsRevision] = useState(0)
  const [previewDay, setPreviewDay] = useState<PomodoroWeekday>(() =>
    resolvePreviewDay(getPomodoroSnapshot({ enabled, weeklySchedule }, Date.now())),
  )

  usePageMeta({
    title: "番茄钟 | LearningPyramid",
    description: "独立的全局番茄钟功能页。这里负责每周自动排程、阶段切换铃声和工作台锁定策略。",
    path: buildPomodoroPath(),
  })

  const capabilitiesQ = useSystemCapabilities()
  const authEnabled = capabilitiesQ.data?.authEnabled ?? false
  const currentUserQ = useCurrentUser(authEnabled)
  const updateGlobalSettings = useUpdateMyGlobalSettings()
  const shouldSyncRemotely = authEnabled && Boolean(currentUserQ.data?.userId)
  const projectTitleMap = useMemo(
    () => new Map((projectsQ.data ?? []).map((project) => [project.projectId, project.title] as const)),
    [projectsQ.data],
  )
  const availableProjects = projectsQ.data ?? []
  const reportProjectIds = useMemo(
    () => Array.from(new Set(availableProjects.map((project) => project.projectId).filter(Boolean))),
    [availableProjects],
  )

  const snapshot = useMemo(() => getPomodoroSnapshot({ enabled, weeklySchedule }, now), [enabled, now, weeklySchedule])
  const todayDateKey = useMemo(() => getLocalDateKey(new Date(now)), [now])
  const dailyReport = useMemo(() => getDailyReport(todayDateKey), [getDailyReport, reportsByDate, todayDateKey])
  const todayStudyTotals = useMemo(() => {
    const totalsByDate = loadDailyStudyTotalsByDate(reportProjectIds)
    return totalsByDate[todayDateKey] ?? { effectiveMs: 0, watchMs: 0, composeMs: 0, reviewMs: 0, qaMs: 0 }
  }, [reportProjectIds, statsRevision, todayDateKey])
  const todayPresenceTotals = useMemo(() => {
    const totalsByDate = loadDailyStudyPresenceTotalsByDate(reportProjectIds)
    return totalsByDate[todayDateKey] ?? { presenceMs: 0 }
  }, [reportProjectIds, statsRevision, todayDateKey])
  const hasFocusProject = snapshot.currentProjectId ? projectTitleMap.has(snapshot.currentProjectId) : false
  const focusProjectTitle =
    snapshot.currentProjectId && hasFocusProject ? projectTitleMap.get(snapshot.currentProjectId) ?? "" : ""
  const rememberedWorkbenchPath = fromPath.startsWith("/p/") && fromPath.includes("/workbench") ? fromPath : ""
  const focusWorkbenchPath =
    snapshot.currentProjectId && hasFocusProject ? `/p/${snapshot.currentProjectId}/workbench` : ""
  const fallbackWorkbenchPath = selectedProjectId ? `/p/${selectedProjectId}/workbench` : ""
  const preferredWorkbenchPath = focusWorkbenchPath || rememberedWorkbenchPath || fallbackWorkbenchPath
  const preferredWorkbenchLabel = focusWorkbenchPath
    ? `进入${focusProjectTitle || "当前番茄项目"}工作台`
    : rememberedWorkbenchPath
      ? "回到刚才的工作台"
      : selectedProjectId
        ? `进入${selectedProjectTitle || "当前项目"}工作台`
        : "进入工作台"
  const todayReportUnlocked =
    snapshot.enabled &&
    snapshot.todaySchedule.enabled &&
    snapshot.status === "completed" &&
    snapshot.currentPomodoro >= snapshot.totalPomodoros
  const scheduledFocusMs = sumFocusDurationMs(snapshot.todaySchedule)
  const plannedGapMs = todayReportUnlocked ? Math.max(0, scheduledFocusMs - todayStudyTotals.effectiveMs) : 0
  const todayStudyPresenceMs = Math.max(todayPresenceTotals.presenceMs, todayStudyTotals.effectiveMs)
  const blankPresenceMs = Math.max(0, todayStudyPresenceMs - todayStudyTotals.effectiveMs)
  const dailyReportObjectiveSummary = buildDailyReportObjectiveSummary(todayStudyTotals, scheduledFocusMs)
  const dailyPlanSummaries = useMemo(() => {
    return reportProjectIds
      .flatMap((projectId) => {
        const projectTitle = projectTitleMap.get(projectId) ?? "当前学科"
        return selectActiveLearningPlans(plansById, projectId).slice(0, 2).map((plan) => ({
          planId: plan.planId,
          projectTitle,
          planTitle: plan.title,
          summary: summarizeLearningPlanDaily(plan, progressSnapshotsByPlanId[plan.planId], todayDateKey),
        }))
      })
      .slice(0, 4)
  }, [plansById, progressSnapshotsByPlanId, projectTitleMap, reportProjectIds, todayDateKey])

  useEffect(() => {
    setPomodoroDraft(toPomodoroDraft(weeklySchedule))
  }, [weeklySchedule])

  useEffect(() => {
    setStatsRevision((revision) => revision + 1)
    const timer = window.setInterval(() => {
      setStatsRevision((revision) => revision + 1)
    }, 15_000)
    return () => window.clearInterval(timer)
  }, [todayDateKey])

  const draftSchedule = useMemo(() => buildPomodoroScheduleFromDraft(pomodoroDraft), [pomodoroDraft])
  const enabledDayCount = useMemo(() => POMODORO_WEEKDAYS.filter((day) => draftSchedule[day].enabled).length, [draftSchedule])

  useEffect(() => {
    if (!draftSchedule[previewDay].enabled && enabledDayCount > 0) {
      setPreviewDay(findFirstEnabledDay(draftSchedule))
    }
  }, [draftSchedule, enabledDayCount, previewDay])

  const enabledUnassignedPomodoros = useMemo(
    () =>
      POMODORO_WEEKDAYS.reduce((count, day) => {
        const schedule = draftSchedule[day]
        if (!schedule.enabled) return count
        return count + schedule.projectIds.filter((projectId) => !projectId).length
      }, 0),
    [draftSchedule],
  )

  const previewSchedule = draftSchedule[previewDay]
  const previewSegments = useMemo(
    () =>
      previewSchedule.enabled
        ? buildPomodoroSegments(
            previewSchedule.focusMinutes,
            previewSchedule.breakMinutes,
            previewSchedule.pomodoroCount,
            previewSchedule.projectIds,
            previewSchedule.focusPrompts,
            previewSchedule.breakPrompt,
          )
        : [],
    [
      previewSchedule.breakPrompt,
      previewSchedule.breakMinutes,
      previewSchedule.enabled,
      previewSchedule.focusMinutes,
      previewSchedule.focusPrompts,
      previewSchedule.pomodoroCount,
      previewSchedule.projectIds,
    ],
  )
  const headlineCountdown =
    snapshot.status === "running"
      ? formatPomodoroCountdown(snapshot.segmentRemainingMs)
      : snapshot.idleReason === "waiting"
        ? formatPomodoroCountdown(snapshot.untilStartMs)
        : "00:00"

  async function persistPomodoroSettings(overrides?: {
    enabled?: boolean
    weeklySchedule?: PomodoroWeekSchedule
    transitionSoundEnabled?: boolean
  }) {
    const payload = {
      theme: selectedTheme,
      pomodoro: {
        enabled: overrides?.enabled ?? enabled,
        weeklySchedule: overrides?.weeklySchedule ?? weeklySchedule,
        transitionSoundEnabled: overrides?.transitionSoundEnabled ?? transitionSoundEnabled,
      },
      defaultProjectReviewTemplate: defaultProjectReviewTemplate as ReviewChainTemplateItem[],
    }
    if (shouldSyncRemotely) {
      await updateGlobalSettings.mutateAsync(payload)
    }
    return payload
  }

  async function savePomodoroConfig() {
    try {
      await persistPomodoroSettings({ weeklySchedule: draftSchedule })
      setSettings({ enabled, weeklySchedule: draftSchedule, transitionSoundEnabled })
      showSuccessFeedback(
        "番茄钟排程已保存",
        enabledDayCount > 0
          ? enabledUnassignedPomodoros > 0
            ? `当前启用了 ${enabledDayCount} 天自动开始排程，但还有 ${enabledUnassignedPomodoros} 个番茄未绑定项目。`
            : `当前一共启用了 ${enabledDayCount} 天自动开始排程。`
          : "排程已保存，但还没有启用任何日期。",
      )
    } catch (err) {
      showErrorFeedback("保存番茄钟排程失败", formatApiError(err))
    }
  }

  async function handleTogglePomodoro() {
    const nextEnabled = !enabled
    try {
      await persistPomodoroSettings({ enabled: nextEnabled, weeklySchedule: draftSchedule })
      setEnabled(nextEnabled)
      if (nextEnabled) {
        showInfoFeedback(
          "番茄钟已开启",
          enabledDayCount > 0
            ? "之后会按每周排程自动开始，学习时段只会放行当前番茄绑定的项目工作台。"
            : "番茄钟已开启，但你还没启用任何日期排程。",
        )
      } else {
        showInfoFeedback("番茄钟已关闭", "工作台已恢复正常访问，不再受自动排程限制。")
      }
    } catch (err) {
      showErrorFeedback(nextEnabled ? "开启番茄钟失败" : "关闭番茄钟失败", formatApiError(err))
    }
  }

  async function handleToggleTransitionSound() {
    const nextEnabled = !transitionSoundEnabled
    try {
      await persistPomodoroSettings({ transitionSoundEnabled: nextEnabled, weeklySchedule: draftSchedule })
      setTransitionSoundEnabled(nextEnabled)
      if (nextEnabled) {
        await unlockPomodoroAudio()
      }
      showInfoFeedback(
        nextEnabled ? "阶段切换铃声已开启" : "阶段切换铃声已关闭",
        nextEnabled
          ? "之后在学习时间与休息时间切换时，系统会尝试自动播放铃声。"
          : "之后即使阶段切换，系统也不会自动播放提示音。",
      )
    } catch (err) {
      showErrorFeedback(nextEnabled ? "开启阶段切换铃声失败" : "关闭阶段切换铃声失败", formatApiError(err))
    }
  }

  async function handleTestSound() {
    try {
      await unlockPomodoroAudio()
      const played = await playPomodoroTransitionSound(snapshot.phase === "break" ? "focus" : "break")
      if (!played) {
        showInfoFeedback("铃声暂时没响", "当前浏览器可能还没有放行音频。先和页面交互一下，再试一次。")
        return
      }
      showSuccessFeedback("测试铃声已播放", "如果你能听到提示音，之后学习/休息切换时也会自动尝试播放。")
    } catch (err) {
      showErrorFeedback("测试铃声失败", formatApiError(err))
    }
  }

  async function handleTestPrompt(promptText: string, promptKey: string) {
    const normalizedPrompt = normalizeDraftPromptText(promptText)
    if (!normalizedPrompt) {
      showInfoFeedback("先写一条提示词", "提示词留空时，系统不会播报语音。")
      return
    }
    try {
      setTestingPromptKey(promptKey)
      await unlockPomodoroAudio()
      const played = await playPomodoroVoicePrompt(normalizedPrompt)
      if (!played) {
        showInfoFeedback("语音暂时没播出来", "浏览器可能还没有放行媒体播放。先点一下页面，再试一次。")
        return
      }
      showSuccessFeedback("语音提示词已播放", "如果刚才能听到播报，之后在切换前 10 秒系统也会自动尝试播报。")
    } catch (err) {
      showErrorFeedback("生成提示词语音失败", formatApiError(err))
    } finally {
      setTestingPromptKey((current) => (current === promptKey ? "" : current))
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.55fr)_minmax(20rem,1fr)]">
        <Card className="theme-card-main overflow-hidden">
          <CardHeader className="theme-card-header">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-[1.1rem] border [border-color:var(--theme-icon-border)] [background:var(--theme-icon-bg)] [color:var(--theme-icon-text)]">
                <TimerReset className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <CardTitle>番茄钟</CardTitle>
                <CardDescription className="mt-1">这是独立功能页，不再挂在全局配置里。这里统一管理每周自动开始排程、阶段切换铃声，以及工作台放行策略。</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-5 pt-5">
            <div className="rounded-[1.5rem] border border-[color:var(--theme-soft-border)] bg-[radial-gradient(circle_at_top_left,hsl(var(--primary)/0.12),transparent_36%),var(--theme-card-main-bg)] p-5 sm:p-6">
              <div className="flex flex-wrap items-center gap-3">
                <PhaseBadge snapshot={snapshot} />
                <span className="inline-flex items-center rounded-full border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-3 py-1 text-xs font-medium text-muted-foreground">
                  {snapshot.status === "running" ? `剩余 ${headlineCountdown}` : snapshot.idleReason === "waiting" ? `距离开始 ${headlineCountdown}` : "按排程自动运行"}
                </span>
                <span className="inline-flex items-center rounded-full border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-3 py-1 text-xs font-medium text-muted-foreground">
                  {transitionSoundEnabled ? "切换铃声已开启" : "切换铃声已关闭"}
                </span>
              </div>
              <div className="mt-4 text-3xl font-semibold tracking-[-0.04em] text-foreground sm:text-4xl">{headlineCountdown}</div>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-muted-foreground">
                {describeCurrentState(snapshot, projectTitleMap)}
              </p>
              <div className="mt-5 flex flex-wrap gap-3">
                <Button variant={enabled ? "outline" : "default"} onClick={handleTogglePomodoro} disabled={updateGlobalSettings.isPending}>
                  <TimerReset className="h-4 w-4" />
                  {enabled ? "关闭番茄钟" : "开启番茄钟"}
                </Button>
                <Button variant="outline" onClick={handleToggleTransitionSound} disabled={updateGlobalSettings.isPending}>
                  <BellRing className="h-4 w-4" />
                  {transitionSoundEnabled ? "关闭阶段切换铃声" : "开启阶段切换铃声"}
                </Button>
                <Button variant="outline" onClick={handleTestSound}>
                  <Volume2 className="h-4 w-4" />
                  测试铃声
                </Button>
                {snapshot.canUseWorkbench && preferredWorkbenchPath ? (
                  <Button asChild>
                    <Link to={preferredWorkbenchPath}>
                      <PanelsTopLeft className="h-4 w-4" />
                      {preferredWorkbenchLabel}
                    </Link>
                  </Button>
                ) : null}
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-4">
              <MetricTile label="今天" value={POMODORO_WEEKDAY_LABELS[snapshot.weekday]} hint={snapshot.todaySchedule.enabled ? `${snapshot.startTime} 自动开始` : "今天未启用"} />
              <MetricTile label="启用中的日期" value={`${enabledDayCount} 天`} hint="只有启用的日期才会自动开始。" />
              <MetricTile label="下次自动开始" value={formatDateTime(snapshot.nextStartAtMs)} hint="按当前设备本地时间解释。" />
              <MetricTile
                label="工作台策略"
                value={enabled ? "按番茄项目放行" : "当前不限制"}
                hint={
                  enabled
                    ? "学习时段只放行当前番茄绑定的项目工作台；未开始、间歇和完成后都会统一锁定。"
                    : "关闭后所有项目工作台都可直接进入。"
                }
              />
            </div>

            {blockedProjectId ? (
              <ContentNotice
                title="刚刚有工作台被自动拦回"
                message={
                  targetProjectId
                    ? `这次拦截是因为当前番茄已经绑定到“${describeProjectLabel(targetProjectId, projectTitleMap)}”。你可以继续在这里调整排程，或者直接进入对应项目。`
                    : "这正是番茄钟当前在生效。你可以继续在这里等下一段学习时间开始，也可以修改今天的排程。"
                }
                icon={Lock}
                tone="info"
              />
            ) : null}
          </CardContent>
        </Card>

        <Card className="theme-card-main">
          <CardHeader className="theme-card-header">
            <CardTitle>铃声与说明</CardTitle>
            <CardDescription>番茄钟还是全局偏好的一部分，但交互上已经独立出来。这里的设置会跟随账号同步。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 pt-5">
            <div className="rounded-[1.2rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] p-4">
              <div className="text-sm font-medium text-foreground">阶段切换铃声</div>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">当学习时间切到休息时间，或休息时间切回学习时间时，系统会尝试自动播放提示铃声。默认关闭，避免突然打扰。</p>
            </div>
            <div className="rounded-[1.2rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] p-4">
              <div className="text-sm font-medium text-foreground">浏览器音频说明</div>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">浏览器通常要求用户先和页面交互一次，后续才能稳定自动播放声音。所以我加了“测试铃声”按钮，第一次打开时点一下就比较稳。</p>
            </div>
            <div className="rounded-[1.2rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] p-4">
              <div className="text-sm font-medium text-foreground">项目切换策略</div>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">排程仍然是全局的，但每个番茄现在都可以绑定一个项目。到学习时间时，系统会优先跳到对应项目；如果某个番茄还没绑定项目，就不会自动跳转。</p>
            </div>
          </CardContent>
        </Card>
      </section>

      <section>
        <Card className="theme-card-main overflow-hidden">
          <CardHeader className="theme-card-header">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <CardTitle>当日日报</CardTitle>
                <CardDescription className="mt-1">最后一个番茄结束后解锁。日报把客观学习时长和你的主观判断放在一起。</CardDescription>
              </div>
              <span
                className={cn(
                  "inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold",
                  todayReportUnlocked
                    ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                    : "border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] text-muted-foreground",
                )}
              >
                {todayReportUnlocked ? "今日已解锁" : "等待最后一个番茄"}
              </span>
            </div>
          </CardHeader>
          <CardContent className="space-y-5 pt-5">
            {!todayReportUnlocked ? (
              <ContentNotice
                title="日报还没解锁"
                message={
                  snapshot.todaySchedule.enabled && snapshot.endAtMs !== null
                    ? `今天的番茄组预计在 ${formatDateTime(snapshot.endAtMs)} 完成。最后一个番茄结束后，这里会开放今日客观指标和主观复盘。`
                    : "今天没有可完成的番茄组。先开启番茄钟，并为今天启用一组排程。"
                }
                icon={Lock}
                tone="info"
              />
            ) : (
              <>
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <MetricTile label="有效学习" value={formatPomodoroDuration(Math.round(todayStudyTotals.effectiveMs / 60_000))} hint={dailyReportObjectiveSummary} />
                  <MetricTile label="学习驻留" value={formatPomodoroDuration(Math.round(todayStudyPresenceMs / 60_000))} hint="今天在学习页、工作台和 AI 页里的活跃驻留。" />
                  <MetricTile label="疑似走神" value={formatPomodoroDuration(Math.round(blankPresenceMs / 60_000))} hint="学习驻留减去有效学习；可理解为暂停、卡住或离开节奏的时间。" />
                  <MetricTile label="计划内流失" value={formatPomodoroDuration(Math.round(plannedGapMs / 60_000))} hint="今日排程的学习番茄时长减去有效学习时长。" />
                </div>

                <div className="rounded-[1.2rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-3 text-sm leading-6 text-muted-foreground">
                  客观构成：材料接触 {formatPomodoroDuration(Math.round(todayStudyTotals.watchMs / 60_000))}，复述点构建{" "}
                  {formatPomodoroDuration(Math.round(todayStudyTotals.composeMs / 60_000))}，复习{" "}
                  {formatPomodoroDuration(Math.round(todayStudyTotals.reviewMs / 60_000))}，AI 问答{" "}
                  {formatPomodoroDuration(Math.round(todayStudyTotals.qaMs / 60_000))}。
                </div>

                {dailyPlanSummaries.length > 0 ? (
                  <div className="rounded-[1.2rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-4">
                    <div className="text-sm font-semibold text-foreground">计划偏差</div>
                    <div className="mt-3 space-y-3">
                      {dailyPlanSummaries.map((item) => (
                        <div key={item.planId} className="rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] px-4 py-3 text-sm">
                          <div className="font-semibold text-foreground">{item.projectTitle} · {item.planTitle}</div>
                          <div className="mt-1 text-xs leading-5 text-muted-foreground">{item.summary}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}

                <div className="grid gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
                  <div className="rounded-[1.2rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] p-4">
                    <div className="text-sm font-semibold text-foreground">主观判断</div>
                    <div className="mt-3 grid gap-3">
                      {DAILY_REPORT_DIRECTION_OPTIONS.map((option) => (
                        <button
                          key={option.value}
                          type="button"
                          className={cn(
                            "rounded-[1rem] border px-4 py-3 text-left transition-colors",
                            dailyReport.direction === option.value
                              ? "border-primary/30 bg-[hsl(var(--primary)/0.1)] text-foreground"
                              : "border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] text-[color:var(--theme-soft-text-strong)] hover:border-primary/20",
                          )}
                          onClick={() => updateDailyReport(todayDateKey, { direction: option.value })}
                        >
                          <div className="text-sm font-semibold">{option.label}</div>
                          <div className="mt-1 text-xs leading-5 text-muted-foreground">{option.hint}</div>
                        </button>
                      ))}
                    </div>

                    <div className="mt-5">
                      <div className="flex items-center justify-between gap-3">
                        <Label>专注自评</Label>
                        <span className="text-xs text-muted-foreground">{dailyReport.focusScore > 0 ? `${dailyReport.focusScore}/5` : "未选择"}</span>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        {[1, 2, 3, 4, 5].map((score) => (
                          <Button
                            key={score}
                            type="button"
                            variant={dailyReport.focusScore === score ? "default" : "outline"}
                            size="sm"
                            onClick={() => updateDailyReport(todayDateKey, { focusScore: score })}
                          >
                            {score}
                          </Button>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="rounded-[1.2rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="text-sm font-semibold text-foreground">文字复盘</div>
                      <div className="text-xs text-muted-foreground">自动保存：{formatReportUpdatedAt(dailyReport.updatedAt)}</div>
                    </div>
                    <div className="mt-4 space-y-4">
                      <div className="space-y-2">
                        <Label htmlFor="daily-report-summary">今天学得怎么样？</Label>
                        <textarea
                          id="daily-report-summary"
                          rows={5}
                          maxLength={800}
                          className="min-h-32 w-full resize-y rounded-xl border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-input-bg)] px-4 py-3 text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
                          placeholder="记录今天真正理解了什么、哪里卡住、为什么觉得进步或退步。"
                          value={dailyReport.summary}
                          onChange={(event) => updateDailyReport(todayDateKey, { summary: event.target.value })}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="daily-report-adjustment">明天怎么调整？</Label>
                        <textarea
                          id="daily-report-adjustment"
                          rows={3}
                          maxLength={500}
                          className="min-h-24 w-full resize-y rounded-xl border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-input-bg)] px-4 py-3 text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
                          placeholder="例如：先补完第 3 章的复述点；第一个番茄不打开聊天窗口。"
                          value={dailyReport.adjustment}
                          onChange={(event) => updateDailyReport(todayDateKey, { adjustment: event.target.value })}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,0.65fr)]">
        <Card className="theme-card-main overflow-hidden">
          <CardHeader className="theme-card-header">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl border [border-color:var(--theme-icon-border)] [background:var(--theme-icon-bg)] [color:var(--theme-icon-text)]">
                <Clock3 className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <CardTitle>每周排程</CardTitle>
                <CardDescription className="mt-1">像手机闹钟一样，为每天设定固定自动开始时间。工作日、周末都可以分别定制。</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-5 pt-5">
            <ContentNotice
              title="这是全局自动排程"
              message="开启后，只有当前番茄绑定的项目工作台会在学习时段放行；等待开始、间歇和完成后都会统一拦回番茄钟页。"
              icon={Clock3}
              tone="info"
            />

            {availableProjects.length === 0 && !projectsQ.isLoading ? (
              <ContentNotice
                title="还没有可绑定的项目"
                message="先去项目中心创建至少一个项目，下面的番茄项目下拉才会有可选项。"
                icon={PanelsTopLeft}
                tone="info"
              />
            ) : null}

            <div className="flex flex-wrap gap-3">
              <Button
                variant="outline"
                onClick={() =>
                  setPomodoroDraft((prev) => {
                    const next = { ...prev }
                    for (const day of ["mon", "tue", "wed", "thu", "fri"] as PomodoroWeekday[]) {
                      next[day] = { ...clonePomodoroDraftDay(next[day]), enabled: true }
                    }
                    return next
                  })
                }
              >
                工作日全部开启
              </Button>
              <Button
                variant="outline"
                onClick={() =>
                  setPomodoroDraft((prev) => {
                    const next = { ...prev }
                    for (const day of ["sat", "sun"] as PomodoroWeekday[]) {
                      next[day] = { ...clonePomodoroDraftDay(next[day]), enabled: false }
                    }
                    return next
                  })
                }
              >
                周末全部关闭
              </Button>
              <Button
                variant="outline"
                onClick={() =>
                  setPomodoroDraft((prev) => {
                    const next = { ...prev }
                    const monday = clonePomodoroDraftDay(next.mon)
                    for (const day of ["tue", "wed", "thu", "fri"] as PomodoroWeekday[]) {
                      next[day] = clonePomodoroDraftDay(monday)
                    }
                    return next
                  })
                }
              >
                用周一覆盖工作日
              </Button>
              <Button
                variant="outline"
                onClick={() =>
                  setPomodoroDraft((prev) => {
                    const next = { ...prev }
                    next.sun = clonePomodoroDraftDay(next.sat)
                    return next
                  })
                }
              >
                用周六覆盖周日
              </Button>
              <Button
                variant="ghost"
                onClick={() =>
                  setPomodoroDraft((prev) => {
                    const next = { ...prev }
                    for (const day of POMODORO_WEEKDAYS) {
                      next[day] = { ...clonePomodoroDraftDay(next[day]), enabled: false }
                    }
                    return next
                  })
                }
              >
                全部关闭
              </Button>
            </div>

            <div className="space-y-3">
              {POMODORO_WEEKDAYS.map((day) => {
                const item = pomodoroDraft[day]
                const normalizedPomodoroCount = normalizeCountInput(item.pomodoroCount, 4)
                const dayProjectIds = normalizeDraftProjectIds(item.projectIds, normalizedPomodoroCount)
                const dayFocusPrompts = normalizeDraftFocusPrompts(item.focusPrompts, normalizedPomodoroCount)
                return (
                  <div
                    key={day}
                    className="space-y-4 rounded-[1.15rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] p-4"
                  >
                    <div
                      className={cn(
                        "grid gap-3",
                        "xl:grid-cols-[88px_96px_minmax(0,0.95fr)_minmax(0,0.85fr)_minmax(0,0.85fr)_minmax(0,0.85fr)_76px]",
                      )}
                    >
                      <div className="flex items-center justify-between xl:justify-start">
                        <div>
                          <div className="text-sm font-semibold text-foreground">{POMODORO_WEEKDAY_LABELS[day]}</div>
                          <div className="mt-1 text-xs text-muted-foreground">{day === snapshot.weekday ? "今天" : "每周重复"}</div>
                        </div>
                        <Button type="button" variant="ghost" size="sm" className="xl:hidden" onClick={() => setPreviewDay(day)}>
                          预览
                        </Button>
                      </div>

                      <label className="flex items-center gap-2 rounded-xl border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-3 py-2 text-sm text-foreground">
                        <input
                          type="checkbox"
                          checked={item.enabled}
                          onChange={(event) =>
                            setPomodoroDraft((prev) => ({
                              ...prev,
                              [day]: { ...clonePomodoroDraftDay(prev[day]), enabled: event.target.checked },
                            }))
                          }
                        />
                        启用
                      </label>

                      <div className="space-y-2">
                        <Label htmlFor={`pomodoro-start-${day}`}>开始时间</Label>
                        <Input
                          id={`pomodoro-start-${day}`}
                          type="time"
                          value={item.startTime}
                          onChange={(event) =>
                            setPomodoroDraft((prev) => ({
                              ...prev,
                              [day]: { ...clonePomodoroDraftDay(prev[day]), startTime: event.target.value },
                            }))
                          }
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor={`pomodoro-focus-${day}`}>学习 M</Label>
                        <Input
                          id={`pomodoro-focus-${day}`}
                          type="number"
                          min={1}
                          max={180}
                          value={item.focusMinutes}
                          onChange={(event) =>
                            setPomodoroDraft((prev) => ({
                              ...prev,
                              [day]: { ...clonePomodoroDraftDay(prev[day]), focusMinutes: event.target.value },
                            }))
                          }
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor={`pomodoro-break-${day}`}>间歇 N</Label>
                        <Input
                          id={`pomodoro-break-${day}`}
                          type="number"
                          min={1}
                          max={60}
                          value={item.breakMinutes}
                          onChange={(event) =>
                            setPomodoroDraft((prev) => ({
                              ...prev,
                              [day]: { ...clonePomodoroDraftDay(prev[day]), breakMinutes: event.target.value },
                            }))
                          }
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor={`pomodoro-count-${day}`}>番茄数</Label>
                        <Input
                          id={`pomodoro-count-${day}`}
                          type="number"
                          min={1}
                          max={12}
                          value={item.pomodoroCount}
                          onChange={(event) =>
                            setPomodoroDraft((prev) => {
                              const current = prev[day]
                              const nextCount = normalizeCountInput(
                                event.target.value,
                                normalizeCountInput(current.pomodoroCount, 4),
                              )
                              return {
                                ...prev,
                                [day]: {
                                  ...clonePomodoroDraftDay(current),
                                  pomodoroCount: event.target.value,
                                  projectIds: normalizeDraftProjectIds(current.projectIds, nextCount),
                                  focusPrompts: normalizeDraftFocusPrompts(current.focusPrompts, nextCount),
                                },
                              }
                            })
                          }
                        />
                      </div>

                      <div className="hidden items-end xl:flex">
                        <Button type="button" variant="ghost" size="sm" onClick={() => setPreviewDay(day)}>
                          预览
                        </Button>
                      </div>
                    </div>

                    <div className="rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div>
                          <div className="text-sm font-medium text-foreground">番茄对应项目与学习前提示词</div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            第几个番茄开始，就自动跳到这里选中的项目工作台；提示词会在学习开始前 10 秒尝试语音播报。
                          </div>
                        </div>
                        <div className="text-xs text-muted-foreground">
                          已绑定 {dayProjectIds.filter(Boolean).length}/{normalizedPomodoroCount}
                        </div>
                      </div>

                      {availableProjects.length === 0 && !projectsQ.isLoading ? (
                        <div className="mt-3 rounded-xl border border-dashed border-[color:var(--theme-soft-border)] px-3 py-3 text-sm text-muted-foreground">
                          当前还没有项目可选。
                        </div>
                      ) : null}

                      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                        {dayProjectIds.map((projectId, index) => {
                          const promptKey = `${day}:focus:${index}`
                          return (
                            <div key={`${day}-project-${index}`} className="space-y-3 rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] p-3">
                              <div className="space-y-2">
                                <Label htmlFor={`pomodoro-project-${day}-${index}`}>番茄 {index + 1}</Label>
                                <select
                                  id={`pomodoro-project-${day}-${index}`}
                                  className="theme-select h-10 w-full rounded-xl px-3 text-sm"
                                  value={projectId ?? ""}
                                  onChange={(event) =>
                                    setPomodoroDraft((prev) => {
                                      const current = prev[day]
                                      const nextProjectIds = normalizeDraftProjectIds(
                                        current.projectIds,
                                        normalizeCountInput(current.pomodoroCount, 4),
                                      )
                                      nextProjectIds[index] = event.target.value.trim() || null
                                      return {
                                        ...prev,
                                        [day]: {
                                          ...clonePomodoroDraftDay(current),
                                          projectIds: nextProjectIds,
                                        },
                                      }
                                    })
                                  }
                                >
                                  <option value="">未指定项目</option>
                                  {availableProjects.map((project) => (
                                    <option key={project.projectId} value={project.projectId}>
                                      {project.title}
                                    </option>
                                  ))}
                                </select>
                              </div>

                              <div className="space-y-2">
                                <div className="flex items-center justify-between gap-2">
                                  <Label htmlFor={`pomodoro-focus-prompt-${day}-${index}`}>学习前提示词</Label>
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => void handleTestPrompt(dayFocusPrompts[index] ?? "", promptKey)}
                                    disabled={testingPromptKey === promptKey || !normalizeDraftPromptText(dayFocusPrompts[index]).trim()}
                                  >
                                    <Volume2 className="h-3.5 w-3.5" />
                                    试听
                                  </Button>
                                </div>
                                <textarea
                                  id={`pomodoro-focus-prompt-${day}-${index}`}
                                  maxLength={200}
                                  rows={3}
                                  className="min-h-20 w-full resize-y rounded-xl border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-input-bg)] px-3 py-2 text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
                                  placeholder="例如：十秒后进入学习时间，先把手机放远，打开当前项目。"
                                  value={dayFocusPrompts[index] ?? ""}
                                  onChange={(event) =>
                                    setPomodoroDraft((prev) => {
                                      const current = prev[day]
                                      const nextFocusPrompts = normalizeDraftFocusPrompts(
                                        current.focusPrompts,
                                        normalizeCountInput(current.pomodoroCount, 4),
                                      )
                                      nextFocusPrompts[index] = event.target.value
                                      return {
                                        ...prev,
                                        [day]: {
                                          ...clonePomodoroDraftDay(current),
                                          focusPrompts: nextFocusPrompts,
                                        },
                                      }
                                    })
                                  }
                                />
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </div>

                    <div className="rounded-[1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] p-3">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div>
                          <div className="text-sm font-medium text-foreground">休息前提示词</div>
                          <div className="mt-1 text-xs leading-5 text-muted-foreground">
                            每次间歇开始前 10 秒播报这一句；最后一个番茄没有间歇，因此不会播。
                          </div>
                        </div>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => void handleTestPrompt(item.breakPrompt, `${day}:break`)}
                          disabled={testingPromptKey === `${day}:break` || !normalizeDraftPromptText(item.breakPrompt).trim()}
                        >
                          <Volume2 className="h-4 w-4" />
                          试听休息提示
                        </Button>
                      </div>
                      <textarea
                        id={`pomodoro-break-prompt-${day}`}
                        maxLength={200}
                        rows={3}
                        className="mt-3 min-h-20 w-full resize-y rounded-xl border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-input-bg)] px-3 py-2 text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
                        placeholder="例如：十秒后进入休息。保存一下当前进度，站起来喝口水。"
                        value={item.breakPrompt}
                        onChange={(event) =>
                          setPomodoroDraft((prev) => ({
                            ...prev,
                            [day]: {
                              ...clonePomodoroDraftDay(prev[day]),
                              breakPrompt: event.target.value,
                            },
                          }))
                        }
                      />
                    </div>
                  </div>
                )
              })}
            </div>

            <div className="flex flex-wrap gap-3">
              <Button onClick={savePomodoroConfig} disabled={updateGlobalSettings.isPending}>
                <Save className="h-4 w-4" />
                保存排程
              </Button>
              <Button variant="outline" onClick={() => setPomodoroDraft(toPomodoroDraft(weeklySchedule))}>
                <RotateCcw className="h-4 w-4" />
                恢复已保存值
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card className="theme-card-main">
          <CardHeader className="theme-card-header">
            <CardTitle>排程预览</CardTitle>
            <CardDescription>这里预览你当前编辑中的某一天配置，还没保存前也会实时更新。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 pt-5">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
              <MetricTile label="预览日期" value={POMODORO_WEEKDAY_LABELS[previewDay]} hint={previewSchedule.enabled ? `${previewSchedule.startTime} 自动开始` : "当前未启用"} />
              <MetricTile label="单个学习番茄" value={formatPomodoroDuration(previewSchedule.focusMinutes)} />
              <MetricTile label="单次间歇" value={formatPomodoroDuration(previewSchedule.breakMinutes)} />
              <MetricTile label="番茄数量" value={`${previewSchedule.pomodoroCount} 个`} hint="最后一个番茄不会再进入间歇。" />
            </div>

            {previewSegments.length === 0 ? (
              <ContentNotice title="这一天当前未启用" message="如果这一天不启用，到了这一天时系统不会自动开始，工作台也会整天保持锁定。" icon={TimerReset} tone="info" />
            ) : (
              <div className="space-y-3">
                {previewSegments.map((segment, index) => {
                  const status: "done" | "current" | "upcoming" =
                    previewDay !== snapshot.weekday
                      ? "upcoming"
                      : snapshot.status === "completed"
                        ? "done"
                        : index < snapshot.segmentIndex
                          ? "done"
                          : index === snapshot.segmentIndex && snapshot.status === "running"
                            ? "current"
                            : "upcoming"
                  const Icon = status === "done" ? CheckCircle2 : segment.phase === "focus" ? Clock3 : Coffee
                  return (
                    <div key={`${previewDay}-${segment.phase}-${segment.pomodoroIndex}-${index}`} className={cn("rounded-[1.15rem] border px-4 py-4 transition-colors", timelineTone(status, segment.phase))}>
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-xs font-semibold uppercase tracking-[0.16em] opacity-70">{segment.phase === "focus" ? `番茄 ${segment.pomodoroIndex}` : `间歇 ${segment.pomodoroIndex}`}</div>
                          <div className="mt-2 text-base font-semibold">{segment.phase === "focus" ? "学习时间" : "间歇时间"}</div>
                          <div className="mt-1 text-sm opacity-80">
                            {segment.phase === "focus"
                              ? segment.projectId
                                ? `开始后会自动跳到“${describeProjectLabel(segment.projectId, projectTitleMap)}”。`
                                : "这个番茄还没有指定项目，因此不会自动跳转。"
                              : "所有项目工作台锁定，建议离开屏幕稍作休息。"}
                          </div>
                        </div>
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[1rem] border border-current/15 bg-white/40">
                          <Icon className="h-4.5 w-4.5" />
                        </div>
                      </div>
                      <div className="mt-4 flex items-center justify-between gap-3 text-sm font-medium">
                        <span>{segment.phase === "focus" ? "阶段时长" : "休息时长"}</span>
                        <span>{formatPomodoroDuration(Math.round(segment.durationMs / 60_000))}</span>
                      </div>
                      {segment.phase === "focus" ? (
                        <div className="mt-3 text-sm text-[color:var(--theme-soft-text-strong)]">
                          绑定项目：{describeProjectLabel(segment.projectId, projectTitleMap)}
                        </div>
                      ) : null}
                      {segment.promptText ? (
                        <div className="mt-3 rounded-[1rem] border border-current/10 bg-white/35 px-3 py-3 text-sm leading-6">
                          预告语音：{segment.promptText}
                        </div>
                      ) : null}
                    </div>
                  )
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  )
}

import { useCallback, useEffect, useMemo, useState } from "react"
import { useQueries } from "@tanstack/react-query"
import { BarChart3, CircleStop, FolderOpen, Music2, PanelsTopLeft, Pause, Play, Plus, RefreshCw, RotateCcw, Save, Settings2, SkipForward, TimerReset, Trash2, Volume2 } from "lucide-react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { listSubjectMaterials, type StudyMaterial, type Subject } from "@/ui/api/subjects"
import { playPomodoroVoicePrompt, unlockPomodoroAudio } from "@/ui/pomodoroAudio"
import {
  getPomodoroRestMusicPlayerSnapshot,
  pausePomodoroRestMusic,
  playPomodoroRestMusicTrack,
  subscribePomodoroRestMusicPlayer,
} from "@/ui/pomodoroRestMusicPlayer"
import { Button } from "@/ui/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/ui/components/ui/dialog"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import {
  resolvePomodoroRestMusicFile,
  scanPomodoroRestMusicDirectory,
  type PomodoroRestMusicTrack,
  usePomodoroRestMusicDirectoryBinding,
} from "@/ui/localMedia/projectDirectory"
import { useCurrentUser } from "@/ui/queries/auth"
import { useMembershipSummary } from "@/ui/queries/membership"
import { useUpdateMyGlobalSettings } from "@/ui/queries/profile"
import { useSubjects } from "@/ui/queries/subjects"
import { useSystemCapabilities } from "@/ui/queries/system"
import { usePageMeta } from "@/ui/seo/usePageMeta"
import { completeGuideWalkthroughStep } from "@/ui/guideWalkthrough/guideWalkthroughController"
import { showErrorFeedback, showInfoFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { listPomodoroActivityRecords, type PomodoroActivityRecord } from "@/ui/store/pomodoroActivityStore"
import {
  POMODORO_WEEKDAYS,
  POMODORO_WEEKDAY_LABELS,
  describePomodoroPhase,
  formatPomodoroCountdown,
  buildPomodoroSegments,
  getPomodoroSnapshot,
  isQuickPomodoroSessionActive,
  normalizePomodoroStartTime,
  normalizePomodoroPromptText,
  normalizePomodoroWeekSchedule,
  pomodoroProjectRefKey,
  validatePomodoroWeekSchedule,
  type PomodoroDefaultPrompts,
  type PomodoroPlanSchedule,
  type PomodoroProjectReference,
  type PomodoroSnapshot,
  type PomodoroWeekSchedule,
  type PomodoroWeekday,
  usePomodoroNow,
  usePomodoroStore,
} from "@/ui/store/pomodoroStore"
import { resolvePomodoroWallpaperScope } from "@/ui/pomodoroWallpaper"
import { loadPomodoroSegmentMetricSummary, type PomodoroSegmentMetricSummary } from "@/ui/store/workbenchDailyStats"
import { formatStudyMaterialTypeLabel } from "@/ui/subjects/studyMaterials"
import { useThemeStore } from "@/ui/store/themeStore"
import { cn } from "@/ui/utils"
import { MemberOnlyFeatureNotice } from "@/views/membership/membershipUi"
import { buildPomodoroPath, buildPomodoroPlanPath, buildPomodoroSettingsPath } from "@/views/pomodoro/pomodoroRouting"
import { PomodoroWallpaperBackdrop, usePomodoroWallpaper } from "@/views/pomodoro/PomodoroWallpaperBackdrop"

type PomodoroPlanDraft = {
  id: string
  activeDays: PomodoroWeekday[]
  startTime: string
  focusMinutes: string
  breakMinutes: string
  pomodoroCount: string
  subjectId: string
  projectRefs: Array<PomodoroProjectReference | null>
  breakPrompt: string
  focusPrompts: string[]
}

type PomodoroSubjectProjectOption = {
  subjectId: string
  subjectTitle: string
  projectId: string
  title: string
  materialType: StudyMaterial["materialType"]
}

type PomodoroPlanMetricSummary = {
  planId: string
  planIndex: number
  dateKey: string
  label: string
  segments: PomodoroSegmentMetricSummary[]
  scheduledFocusMs: number
  webPresenceMs: number
  videoMs: number
  recallEntryMs: number
  reviewMs: number
  aiQaMs: number
  distractionMs: number
  absenceMs: number
  activeLearningMs: number
  attendanceRate: number
  effectiveLearningRate: number
  status: "not-started" | "in-progress" | "completed"
}

const QUICK_POMODORO_PLAN_ID = "quick-pomodoro"

function createPomodoroDraftId() {
  return `plan-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

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

function normalizePomodoroProjectRef(value: unknown): PomodoroProjectReference | null {
  if (!value || typeof value !== "object") return null
  const input = value as Partial<PomodoroProjectReference>
  const subjectId = typeof input.subjectId === "string" ? input.subjectId.trim() : ""
  const scopedProjectId = typeof input.scopedProjectId === "string" ? input.scopedProjectId.trim() : ""
  return subjectId && scopedProjectId ? { subjectId, scopedProjectId } : null
}

function normalizeDraftProjectRefs(projectRefs: Array<PomodoroProjectReference | null> | undefined, pomodoroCount: number) {
  const normalizedCount = clampInteger(pomodoroCount, 1, 12)
  return Array.from({ length: normalizedCount }, (_, index) => {
    return normalizePomodoroProjectRef(projectRefs?.[index])
  })
}

function normalizeDraftPromptText(value: string | null | undefined) {
  return normalizePomodoroPromptText(value)
}

function normalizeDraftFocusPrompts(focusPrompts: string[] | undefined, pomodoroCount: number, defaultFocusPrompt = "") {
  const normalizedCount = clampInteger(pomodoroCount, 1, 12)
  const fallbackPrompt = normalizeDraftPromptText(defaultFocusPrompt)
  return Array.from({ length: normalizedCount }, (_, index) => normalizeDraftPromptText(focusPrompts?.[index] ?? fallbackPrompt))
}

function getPomodoroSubjectProjectOptionLabel(option: PomodoroSubjectProjectOption) {
  return `${option.title}（${formatStudyMaterialTypeLabel(option.materialType)}）`
}

function normalizeDraftSubjectId(
  subjectId: string | undefined,
  projectRefs: Array<PomodoroProjectReference | null> | undefined,
) {
  const normalizedSubjectId = typeof subjectId === "string" ? subjectId.trim() : ""
  if (normalizedSubjectId) return normalizedSubjectId
  const inferredSubjectIds = Array.from(new Set((projectRefs ?? []).map((projectRef) => projectRef?.subjectId ?? "").filter(Boolean)))
  return inferredSubjectIds.length === 1 ? inferredSubjectIds[0] : ""
}

function buildScopedWorkbenchPath(subjectId: string, projectId: string) {
  return subjectId && projectId ? `/subjects/${encodeURIComponent(subjectId)}/projects/${encodeURIComponent(projectId)}/workbench` : ""
}

function toPomodoroProjectReference(project: { subjectId: string; projectId: string }): PomodoroProjectReference {
  return { subjectId: project.subjectId, scopedProjectId: project.projectId }
}

function buildPomodoroSubjectProjectOptions(
  subjects: Subject[],
  materialResults: Array<StudyMaterial[] | undefined>,
  projectTitleByRef: Map<string, string>,
) {
  const subjectProjectOptions = new Map<string, PomodoroSubjectProjectOption[]>()
  const projectTitleByProjectRef = new Map<string, string>()

  subjects.forEach((subject, index) => {
    const options = (materialResults[index] ?? [])
      .filter((material) => material.scopedProjectId)
      .map((material) => {
        const projectId = material.scopedProjectId ?? ""
        return {
          subjectId: subject.subjectId,
          subjectTitle: subject.title,
          projectId,
          title: material.title || projectTitleByRef.get(pomodoroProjectRefKey({ subjectId: subject.subjectId, scopedProjectId: projectId })) || "未命名项目",
          materialType: material.materialType,
        }
      })

    for (const option of options) {
      projectTitleByProjectRef.set(pomodoroProjectRefKey(toPomodoroProjectReference(option)), option.title)
    }
    subjectProjectOptions.set(subject.subjectId, options)
  })

  return { subjectProjectOptions, projectTitleByProjectRef }
}

function clonePomodoroPlanDraft(draft: PomodoroPlanDraft): PomodoroPlanDraft {
  return {
    ...draft,
    activeDays: [...draft.activeDays],
    projectRefs: draft.projectRefs.map((projectRef) => (projectRef ? { ...projectRef } : null)),
    focusPrompts: [...draft.focusPrompts],
  }
}

function createDefaultPomodoroPlanDraft(overrides?: Partial<PomodoroPlanDraft>, defaultPrompts?: PomodoroDefaultPrompts): PomodoroPlanDraft {
  const pomodoroCount = normalizeCountInput(overrides?.pomodoroCount ?? "4", 4)
  const hasBreakPromptOverride = Boolean(overrides && Object.prototype.hasOwnProperty.call(overrides, "breakPrompt"))
  const focusPromptDefaults = overrides?.focusPrompts === undefined ? defaultPrompts?.focusPrompt : ""
  return {
    id: overrides?.id ?? createPomodoroDraftId(),
    activeDays: overrides?.activeDays ? [...overrides.activeDays] : [],
    startTime: normalizePomodoroStartTime(overrides?.startTime ?? "20:00"),
    focusMinutes: String(normalizeFocusInput(overrides?.focusMinutes ?? "25", 25)),
    breakMinutes: String(normalizeBreakInput(overrides?.breakMinutes ?? "5", 5)),
    pomodoroCount: String(pomodoroCount),
    subjectId: overrides?.subjectId?.trim() ?? "",
    projectRefs: normalizeDraftProjectRefs(overrides?.projectRefs, pomodoroCount),
    breakPrompt: normalizeDraftPromptText(hasBreakPromptOverride ? overrides?.breakPrompt : defaultPrompts?.breakPrompt),
    focusPrompts: normalizeDraftFocusPrompts(overrides?.focusPrompts, pomodoroCount, focusPromptDefaults),
  }
}

function appendDefaultPomodoroPlanDraft(prev: PomodoroPlanDraft[], defaultPrompts?: PomodoroDefaultPrompts) {
  const draftStartTimes = [...new Set(prev.map((draft) => normalizePomodoroStartTime(draft.startTime)))].sort()
  return [
    ...prev,
    createDefaultPomodoroPlanDraft({
      startTime: draftStartTimes.at(-1) ?? "20:00",
    }, defaultPrompts),
  ]
}

function getPomodoroPlanDraftKey(plan: PomodoroPlanSchedule) {
  return JSON.stringify({
    startTime: normalizePomodoroStartTime(plan.startTime),
    focusMinutes: normalizeFocusInput(String(plan.focusMinutes), 25),
    breakMinutes: normalizeBreakInput(String(plan.breakMinutes), 5),
    pomodoroCount: normalizeCountInput(String(plan.pomodoroCount), 4),
    projectRefs: normalizeDraftProjectRefs(plan.projectRefs, plan.pomodoroCount),
    subjectId: normalizeDraftSubjectId("", plan.projectRefs),
    breakPrompt: normalizeDraftPromptText(plan.breakPrompt),
    focusPrompts: normalizeDraftFocusPrompts(plan.focusPrompts, plan.pomodoroCount),
  })
}

function toPomodoroPlanDrafts(weeklySchedule: PomodoroWeekSchedule): PomodoroPlanDraft[] {
  const draftsByKey = new Map<string, PomodoroPlanDraft>()
  for (const day of POMODORO_WEEKDAYS) {
    for (const plan of weeklySchedule[day].plans) {
      if (!plan.enabled) continue
      const key = getPomodoroPlanDraftKey(plan)
      const existing = draftsByKey.get(key)
      if (existing) {
        if (!existing.activeDays.includes(day)) {
          existing.activeDays = POMODORO_WEEKDAYS.filter((item) => item === day || existing.activeDays.includes(item))
        }
        continue
      }
      draftsByKey.set(
        key,
        createDefaultPomodoroPlanDraft({
          id: plan.id || createPomodoroDraftId(),
          activeDays: [day],
          startTime: plan.startTime,
          focusMinutes: String(plan.focusMinutes),
          breakMinutes: String(plan.breakMinutes),
          pomodoroCount: String(plan.pomodoroCount),
          subjectId: normalizeDraftSubjectId("", plan.projectRefs),
          projectRefs: plan.projectRefs,
          breakPrompt: plan.breakPrompt,
          focusPrompts: plan.focusPrompts,
        }),
      )
    }
  }
  return [...draftsByKey.values()].sort(
    (left, right) => normalizePomodoroStartTime(left.startTime).localeCompare(normalizePomodoroStartTime(right.startTime)),
  )
}

function formatActiveDaySummary(activeDays: PomodoroWeekday[]) {
  if (activeDays.length === 0) return "未选择生效日"
  if (activeDays.length === POMODORO_WEEKDAYS.length) return "每天"
  return activeDays.map((day) => POMODORO_WEEKDAY_LABELS[day]).join("、")
}

function buildPomodoroScheduleFromPlanDrafts(drafts: PomodoroPlanDraft[]): PomodoroWeekSchedule {
  const nextSchedule = POMODORO_WEEKDAYS.reduce((result, day) => {
    result[day] = { plans: [] }
    return result
  }, {} as PomodoroWeekSchedule)

  drafts.forEach((draft) => {
    const activeDays = new Set(draft.activeDays)
    const normalizedPomodoroCount = normalizeCountInput(draft.pomodoroCount, 4)
    const sharedPlan = {
      id: draft.id,
      enabled: true,
      startTime: normalizePomodoroStartTime(draft.startTime),
      focusMinutes: normalizeFocusInput(draft.focusMinutes, 25),
      breakMinutes: normalizeBreakInput(draft.breakMinutes, 5),
      pomodoroCount: normalizedPomodoroCount,
      projectRefs: normalizeDraftProjectRefs(draft.projectRefs, normalizedPomodoroCount),
      breakPrompt: normalizeDraftPromptText(draft.breakPrompt),
      focusPrompts: normalizeDraftFocusPrompts(draft.focusPrompts, normalizedPomodoroCount),
    }
    POMODORO_WEEKDAYS.forEach((day) => {
      if (activeDays.has(day)) {
        nextSchedule[day].plans.push(sharedPlan)
      }
    })
  })

  return normalizePomodoroWeekSchedule(nextSchedule)
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
      ? "text-emerald-700"
      : snapshot.phase === "focus"
        ? "text-primary"
        : snapshot.phase === "break"
          ? "text-amber-700"
          : "text-[color:var(--theme-subtle-text)]"
  return <span className={cn("text-3xl font-semibold tracking-[-0.04em] sm:text-4xl", className)}>{label}</span>
}

function MetricTile(props: { label: string; value: string }) {
  return (
    <div className="border-t border-border/60 py-3">
      <div className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">{props.label}</div>
      <div className="mt-2 text-lg font-semibold tracking-[-0.02em] text-foreground">{props.value}</div>
    </div>
  )
}

function MetricDonut(props: { summary: Pick<PomodoroPlanMetricSummary, "scheduledFocusMs" | "videoMs" | "recallEntryMs" | "reviewMs" | "aiQaMs" | "distractionMs" | "absenceMs"> }) {
  const { summary } = props
  const slices = [
    { label: "视频观看", value: summary.videoMs, color: "#2563eb" },
    { label: "复述点录入", value: summary.recallEntryMs, color: "#16a34a" },
    { label: "复习用时", value: summary.reviewMs, color: "#d97706" },
    { label: "AI 问答", value: summary.aiQaMs, color: "#7c3aed" },
    { label: "走神时间", value: summary.distractionMs, color: "#64748b" },
    { label: "缺席时间", value: summary.absenceMs, color: "#dc2626" },
  ].filter((slice) => slice.value > 0)
  const total = Math.max(summary.scheduledFocusMs, slices.reduce((sum, slice) => sum + slice.value, 0))
  let cursor = 0
  const gradient =
    slices.length === 0 || total <= 0
      ? "conic-gradient(#e5e7eb 0deg 360deg)"
      : `conic-gradient(${slices
          .map((slice) => {
            const start = (cursor / total) * 360
            cursor += slice.value
            const end = (cursor / total) * 360
            return `${slice.color} ${start}deg ${end}deg`
          })
          .join(", ")})`

  return (
    <div className="grid gap-3 sm:grid-cols-[7.5rem_minmax(0,1fr)]">
      <div
        data-pomodoro-metric-donut
        className="relative aspect-square w-28 rounded-full"
        style={{ background: gradient }}
        aria-label="番茄学习时间分解"
      >
        <div className="absolute inset-5 rounded-full bg-[color:var(--theme-card-main-bg)]" />
      </div>
      <div className="grid content-center gap-2 text-xs text-muted-foreground">
        {slices.length === 0 ? (
          <div>暂无学习分解</div>
        ) : (
          slices.map((slice) => (
            <div key={slice.label} className="flex items-center justify-between gap-3">
              <span className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: slice.color }} />
                {slice.label}
              </span>
              <span>{formatDurationCompact(slice.value)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
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

function formatDateKey(ms = Date.now()) {
  const date = new Date(ms)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

function formatPomodoroActivityTime(ms: number) {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(ms)
}

function formatDurationCompact(ms: number) {
  if (!Number.isFinite(ms) || ms <= 0) return "0m"
  const totalMinutes = Math.floor(ms / 60_000)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours <= 0) return `${Math.max(1, minutes)}m`
  if (minutes === 0) return `${hours}h`
  return `${hours}h ${minutes}m`
}

function formatPercent(value: number) {
  if (!Number.isFinite(value)) return "0%"
  return `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`
}

function getScheduledStartAtMsForDate(date: Date, startTime: string) {
  const [hoursText = "0", minutesText = "0"] = normalizePomodoroStartTime(startTime).split(":")
  return new Date(date.getFullYear(), date.getMonth(), date.getDate(), Number(hoursText), Number(minutesText), 0, 0).getTime()
}

function buildPomodoroPlanMetricSummaries(schedule: PomodoroWeekSchedule, now: number): PomodoroPlanMetricSummary[] {
  const date = new Date(now)
  const weekday = POMODORO_WEEKDAYS[date.getDay() === 0 ? 6 : date.getDay() - 1]
  const dateKey = formatDateKey(now)
  const plans = (schedule[weekday]?.plans ?? []).filter((plan) => plan.enabled)

  return plans.map((plan, planIndex) => {
    const planStartAtMs = getScheduledStartAtMsForDate(date, plan.startTime)
    const focusSegments = buildPomodoroSegments(
      plan.focusMinutes,
      plan.breakMinutes,
      plan.pomodoroCount,
      plan.projectRefs,
      plan.focusPrompts,
      plan.breakPrompt,
      { planId: plan.id, planIndex },
    ).filter((segment) => segment.phase === "focus")
    const segments: PomodoroSegmentMetricSummary[] = focusSegments.map((segment) =>
      loadPomodoroSegmentMetricSummary({
        projectId: segment.projectRef?.scopedProjectId ?? null,
        projectRef: segment.projectRef ?? null,
        dateKey,
        planId: plan.id,
        planIndex,
        pomodoroIndex: segment.pomodoroIndex,
        scheduledStartAtMs: planStartAtMs + segment.startOffsetMs,
        scheduledEndAtMs: planStartAtMs + segment.endOffsetMs,
        now,
      }),
    )
    const scheduledFocusMs = segments.reduce((sum, segment) => sum + segment.scheduledFocusMs, 0)
    const webPresenceMs = segments.reduce((sum, segment) => sum + segment.webPresenceMs, 0)
    const videoMs = segments.reduce((sum, segment) => sum + segment.videoMs, 0)
    const recallEntryMs = segments.reduce((sum, segment) => sum + segment.recallEntryMs, 0)
    const reviewMs = segments.reduce((sum, segment) => sum + segment.reviewMs, 0)
    const aiQaMs = segments.reduce((sum, segment) => sum + segment.aiQaMs, 0)
    const distractionMs = segments.reduce((sum, segment) => sum + segment.distractionMs, 0)
    const absenceMs = Math.max(0, scheduledFocusMs - webPresenceMs)
    const activeLearningMs = videoMs + recallEntryMs + reviewMs + aiQaMs
    const attendanceRate = scheduledFocusMs > 0 ? webPresenceMs / scheduledFocusMs : 0
    const effectiveLearningRate = scheduledFocusMs > 0 ? activeLearningMs / scheduledFocusMs : 0
    const status = segments.some((segment) => segment.status === "in-progress")
      ? "in-progress"
      : segments.every((segment) => segment.status === "completed")
        ? "completed"
        : "not-started"

    return {
      planId: plan.id,
      planIndex,
      dateKey,
      label: `计划 ${planIndex + 1}`,
      segments,
      scheduledFocusMs,
      webPresenceMs,
      videoMs,
      recallEntryMs,
      reviewMs,
      aiQaMs,
      distractionMs,
      absenceMs,
      activeLearningMs,
      attendanceRate,
      effectiveLearningRate,
      status,
    }
  })
}

function buildPomodoroMetricSummary(input: {
  planId: string
  planIndex: number
  dateKey: string
  label: string
  segments: PomodoroSegmentMetricSummary[]
}): PomodoroPlanMetricSummary {
  const scheduledFocusMs = input.segments.reduce((sum, segment) => sum + segment.scheduledFocusMs, 0)
  const webPresenceMs = input.segments.reduce((sum, segment) => sum + segment.webPresenceMs, 0)
  const videoMs = input.segments.reduce((sum, segment) => sum + segment.videoMs, 0)
  const recallEntryMs = input.segments.reduce((sum, segment) => sum + segment.recallEntryMs, 0)
  const reviewMs = input.segments.reduce((sum, segment) => sum + segment.reviewMs, 0)
  const aiQaMs = input.segments.reduce((sum, segment) => sum + segment.aiQaMs, 0)
  const distractionMs = input.segments.reduce((sum, segment) => sum + segment.distractionMs, 0)
  const absenceMs = Math.max(0, scheduledFocusMs - webPresenceMs)
  const activeLearningMs = videoMs + recallEntryMs + reviewMs + aiQaMs
  const attendanceRate = scheduledFocusMs > 0 ? webPresenceMs / scheduledFocusMs : 0
  const effectiveLearningRate = scheduledFocusMs > 0 ? activeLearningMs / scheduledFocusMs : 0
  const status = input.segments.some((segment) => segment.status === "in-progress")
    ? "in-progress"
    : input.segments.every((segment) => segment.status === "completed")
      ? "completed"
      : "not-started"

  return {
    planId: input.planId,
    planIndex: input.planIndex,
    dateKey: input.dateKey,
    label: input.label,
    segments: input.segments,
    scheduledFocusMs,
    webPresenceMs,
    videoMs,
    recallEntryMs,
    reviewMs,
    aiQaMs,
    distractionMs,
    absenceMs,
    activeLearningMs,
    attendanceRate,
    effectiveLearningRate,
    status,
  }
}

function RestMusicPlayer(props: { isRestPhase: boolean }) {
  const { isRestPhase } = props
  const musicDirectory = usePomodoroRestMusicDirectoryBinding()
  const [tracks, setTracks] = useState<PomodoroRestMusicTrack[]>([])
  const [selectedTrackPath, setSelectedTrackPath] = useState("")
  const [tracksLoading, setTracksLoading] = useState(false)
  const [tracksError, setTracksError] = useState("")
  const [playerState, setPlayerState] = useState(getPomodoroRestMusicPlayerSnapshot)
  const selectedTrack = tracks.find((track) => track.relativePath === selectedTrackPath) ?? null
  const currentTrackPath = playerState.currentTrackPath
  const isPlaying = playerState.isPlaying

  const loadRestMusicTracks = useCallback(async (options?: { force?: boolean }) => {
    if (!options?.force && musicDirectory.permission !== "granted") {
      setTracks([])
      setSelectedTrackPath("")
      return
    }
    try {
      setTracksLoading(true)
      setTracksError("")
      const result = await scanPomodoroRestMusicDirectory()
      setTracks(result.tracks)
      setSelectedTrackPath((current) =>
        current && result.tracks.some((track) => track.relativePath === current)
          ? current
          : result.tracks[0]?.relativePath ?? "",
      )
    } catch (err) {
      setTracks([])
      setSelectedTrackPath("")
      setTracksError(formatApiError(err))
    } finally {
      setTracksLoading(false)
    }
  }, [musicDirectory.permission])

  async function playRestMusicTrack(relativePath = selectedTrackPath) {
    const normalizedPath = relativePath.trim()
    if (!normalizedPath) {
      showInfoFeedback("先选择一首音乐", "当前音乐目录里还没有选中的曲目。")
      return
    }
    try {
      const file = await resolvePomodoroRestMusicFile(normalizedPath)
      if (!file) {
        showErrorFeedback("播放休息音乐失败", "浏览器暂时无法读取这首音乐，请重新授权音乐目录。")
        return
      }
      await playPomodoroRestMusicTrack(normalizedPath, file)
      setSelectedTrackPath(normalizedPath)
    } catch (err) {
      pausePomodoroRestMusic()
      showErrorFeedback("播放休息音乐失败", formatApiError(err))
    }
  }

  async function playNextRestMusicTrack() {
    if (tracks.length === 0) return
    const currentIndex = Math.max(0, tracks.findIndex((track) => track.relativePath === (currentTrackPath || selectedTrackPath)))
    const nextTrack = tracks[(currentIndex + 1) % tracks.length]
    if (nextTrack) {
      await playRestMusicTrack(nextTrack.relativePath)
    }
  }

  async function requestRestMusicPermission() {
    try {
      const permission = await musicDirectory.requestPermission()
      if (permission === "granted") {
        showSuccessFeedback("休息音乐目录权限已恢复", "现在可以选择并播放目录里的音乐。")
        await loadRestMusicTracks({ force: true })
      } else {
        showInfoFeedback("休息音乐目录仍未授权", "浏览器没有放行读取权限，可以到番茄钟设置里更换目录。")
      }
    } catch (err) {
      showErrorFeedback("授权休息音乐目录失败", formatApiError(err))
    }
  }

  useEffect(() => {
    return subscribePomodoroRestMusicPlayer(() => {
      setPlayerState(getPomodoroRestMusicPlayerSnapshot())
    })
  }, [])

  useEffect(() => {
    if (!isRestPhase || musicDirectory.permission !== "granted") return
    void loadRestMusicTracks()
  }, [isRestPhase, loadRestMusicTracks, musicDirectory.handleName, musicDirectory.permission])

  if (!isRestPhase) return null

  return (
    <section className="space-y-4 border-t border-border/60 pt-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
            <Music2 className="h-4 w-4" />
            休息音乐
          </div>
          <div className="mt-1 text-xl font-semibold text-foreground">
            {musicDirectory.handleName || "未绑定音乐目录"}
          </div>
        </div>
        <Button asChild variant="outline">
          <Link to={buildPomodoroSettingsPath()}>
            <FolderOpen className="h-4 w-4" />
            番茄钟设置
          </Link>
        </Button>
      </div>

      {musicDirectory.permission === "granted" ? (
        <div className="space-y-3">
          {tracksError ? <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{tracksError}</div> : null}
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto]">
            <div className="space-y-2">
              <Label htmlFor="pomodoro-rest-music-track">选择音乐</Label>
              <select
                id="pomodoro-rest-music-track"
                className="theme-select h-11 w-full rounded-xl px-3 text-sm"
                value={selectedTrackPath}
                onChange={(event) => setSelectedTrackPath(event.target.value)}
                disabled={tracksLoading || tracks.length === 0}
              >
                {tracks.length === 0 ? <option value="">没有可播放的音乐文件</option> : null}
                {tracks.map((track) => (
                  <option key={track.relativePath} value={track.relativePath}>
                    {track.relativePath}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-wrap items-end gap-2">
              <Button
                type="button"
                onClick={() => (isPlaying ? pausePomodoroRestMusic() : void playRestMusicTrack())}
                disabled={tracksLoading || !selectedTrack}
              >
                {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                {isPlaying ? "暂停" : "播放"}
              </Button>
              <Button type="button" variant="outline" onClick={() => void playNextRestMusicTrack()} disabled={tracks.length < 2}>
                <SkipForward className="h-4 w-4" />
                下一首
              </Button>
              <Button type="button" variant="ghost" onClick={() => void loadRestMusicTracks()} disabled={tracksLoading}>
                <RefreshCw className={cn("h-4 w-4", tracksLoading ? "animate-spin" : "")} />
                刷新
              </Button>
            </div>
          </div>
          <div className="text-sm text-muted-foreground">
            {tracksLoading
              ? "正在读取音乐目录..."
              : tracks.length > 0
                ? `已找到 ${tracks.length} 首音乐。${currentTrackPath ? `正在使用：${currentTrackPath}` : ""}`
                : "这个目录里还没有可播放的音乐文件。"}
          </div>
        </div>
      ) : (
        <div className="rounded-lg border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-3 text-sm leading-6 text-muted-foreground">
          {musicDirectory.permission === "missing"
            ? "还没有在番茄钟设置里绑定休息音乐目录。"
            : musicDirectory.permission === "unsupported"
              ? "当前浏览器不支持本地音乐目录授权。"
              : "音乐目录需要重新授权后才能读取。"}
          {(musicDirectory.permission === "prompt" || musicDirectory.permission === "denied") ? (
            <div className="mt-3">
              <Button type="button" variant="outline" onClick={() => void requestRestMusicPermission()}>
                <FolderOpen className="h-4 w-4" />
                继续授权
              </Button>
            </div>
          ) : null}
        </div>
      )}
    </section>
  )
}

export function PomodoroPage() {
  const nav = useNavigate()
  const { planId: routePlanId } = useParams()
  const activePlanId = routePlanId ? decodeURIComponent(routePlanId) : null
  const subjectsQ = useSubjects(true)
  const selectedTheme = useThemeStore((state) => state.theme)
  const enabled = usePomodoroStore((state) => state.enabled)
  const weeklySchedule = usePomodoroStore((state) => state.weeklySchedule)
  const quickPomodoro = usePomodoroStore((state) => state.quickPomodoro)
  const transitionSoundEnabled = usePomodoroStore((state) => state.transitionSoundEnabled)
  const defaultFocusPrompt = usePomodoroStore((state) => state.defaultFocusPrompt)
  const defaultBreakPrompt = usePomodoroStore((state) => state.defaultBreakPrompt)
  const microBreaks = usePomodoroStore((state) => state.microBreaks)
  const setEnabled = usePomodoroStore((state) => state.setEnabled)
  const setSettings = usePomodoroStore((state) => state.setSettings)
  const startQuickPomodoro = usePomodoroStore((state) => state.startQuickPomodoro)
  const clearQuickPomodoro = usePomodoroStore((state) => state.clearQuickPomodoro)
  const quickPomodoroClockActive = isQuickPomodoroSessionActive(quickPomodoro)
  const now = usePomodoroNow(enabled || quickPomodoroClockActive)
  const [pomodoroDrafts, setPomodoroDrafts] = useState<PomodoroPlanDraft[]>(() => toPomodoroPlanDrafts(weeklySchedule))
  const [selectedSubjectIdByPlanId, setSelectedSubjectIdByPlanId] = useState<Record<string, string>>({})
  const [pomodoroOverviewMode, setPomodoroOverviewMode] = useState<"plans" | "stats">("plans")
  const [testingPromptKey, setTestingPromptKey] = useState("")
  const [deletingPomodoroDraftId, setDeletingPomodoroDraftId] = useState("")
  const [quickPomodoroDialogOpen, setQuickPomodoroDialogOpen] = useState(false)
  const [quickPomodoroSubjectId, setQuickPomodoroSubjectId] = useState("")
  const [quickPomodoroProjectId, setQuickPomodoroProjectId] = useState("")
  const [pomodoroActivityRecords, setPomodoroActivityRecords] = useState<PomodoroActivityRecord[]>(() => listPomodoroActivityRecords())
  usePageMeta({
    title: activePlanId ? "番茄计划详情 | LearningPyramid" : "番茄钟 | LearningPyramid",
    description: activePlanId ? "编辑单个番茄计划" : "番茄钟",
    path: activePlanId ? buildPomodoroPlanPath(activePlanId) : buildPomodoroPath(),
  })

  const capabilitiesQ = useSystemCapabilities()
  const authEnabled = capabilitiesQ.data?.authEnabled ?? false
  const currentUserQ = useCurrentUser(authEnabled)
  const wallpaperScope = useMemo(
    () => resolvePomodoroWallpaperScope(capabilitiesQ.data?.authEnabled, currentUserQ.data?.userId),
    [capabilitiesQ.data?.authEnabled, currentUserQ.data?.userId],
  )
  const { wallpaperUrl } = usePomodoroWallpaper(wallpaperScope)
  const updateGlobalSettings = useUpdateMyGlobalSettings()
  const shouldSyncRemotely = authEnabled && Boolean(currentUserQ.data?.userId)
  const membershipQ = useMembershipSummary(authEnabled)
  const pomodoroMemberBlocked = authEnabled && (membershipQ.isLoading || Boolean(membershipQ.error) || !membershipQ.data?.isActive)
  const projectTitleByRef = useMemo(() => new Map<string, string>(), [])
  const subjectMaterialQs = useQueries({
    queries: (subjectsQ.data ?? []).map((subject) => ({
      queryKey: ["subjectMaterials", subject.subjectId],
      queryFn: () => listSubjectMaterials(subject.subjectId),
      enabled: !subjectsQ.isLoading && !subjectsQ.error,
      staleTime: 60_000,
    })),
  })
  const materialResults = subjectMaterialQs.map((query) => query.data)
  const pomodoroSubjects = useMemo(
    () =>
      (subjectsQ.data ?? []).map((subject, index) => ({
        subject,
        materials: (materialResults[index] ?? []).filter((material) => material.scopedProjectId),
      })),
    [materialResults, subjectsQ.data],
  )
  const { subjectProjectOptions, projectTitleByProjectRef } = useMemo(
    () => buildPomodoroSubjectProjectOptions(
      pomodoroSubjects.map((item) => item.subject),
      pomodoroSubjects.map((item) => item.materials),
      projectTitleByRef,
    ),
    [pomodoroSubjects, projectTitleByRef],
  )
  const availablePomodoroProjects = useMemo(
    () => Array.from(subjectProjectOptions.values()).flat(),
    [subjectProjectOptions],
  )
  const validPomodoroProjectRefs = useMemo(
    () => new Set(availablePomodoroProjects.map((project) => pomodoroProjectRefKey(toPomodoroProjectReference(project)))),
    [availablePomodoroProjects],
  )
  const pomodoroProjectOptionsLoading =
    subjectsQ.isLoading ||
    subjectMaterialQs.some((query) => query.isLoading)
  const defaultPrompts = useMemo(
    () => ({ focusPrompt: defaultFocusPrompt, breakPrompt: defaultBreakPrompt }),
    [defaultBreakPrompt, defaultFocusPrompt],
  )

  const snapshot = useMemo(() => getPomodoroSnapshot({ enabled, weeklySchedule, quickPomodoro }, now), [enabled, now, quickPomodoro, weeklySchedule])
  const activeQuickPomodoro = isQuickPomodoroSessionActive(quickPomodoro, now) ? quickPomodoro : null
  const quickPomodoroButtonLabel =
    activeQuickPomodoro ? "结束小番茄" : "新建小番茄"
  const isFocusRunning = snapshot.status === "running" && snapshot.phase === "focus"
  const focusProjectRef = snapshot.currentProjectRef
  const focusProjectKey = pomodoroProjectRefKey(focusProjectRef)
  const hasFocusProject = Boolean(focusProjectKey && validPomodoroProjectRefs.has(focusProjectKey))
  const focusProjectTitle =
    focusProjectRef && hasFocusProject ? projectTitleByProjectRef.get(focusProjectKey) ?? projectTitleByRef.get(focusProjectKey) ?? "" : ""
  const quickPomodoroSelectableProjects = quickPomodoroSubjectId ? subjectProjectOptions.get(quickPomodoroSubjectId) ?? [] : []
  const quickPomodoroProjectRef =
    quickPomodoroSubjectId && quickPomodoroProjectId
      ? { subjectId: quickPomodoroSubjectId, scopedProjectId: quickPomodoroProjectId }
      : null
  const canCreateQuickPomodoro =
    Boolean(quickPomodoroProjectRef) &&
    validPomodoroProjectRefs.has(pomodoroProjectRefKey(quickPomodoroProjectRef))
  const focusWorkbenchPath =
    focusProjectRef && hasFocusProject
      ? buildScopedWorkbenchPath(focusProjectRef.subjectId, focusProjectRef.scopedProjectId)
      : ""
  const activeWorkbenchPath = snapshot.status === "running" && snapshot.phase === "focus" && snapshot.canUseWorkbench
    ? focusWorkbenchPath
    : ""
  const activeWorkbenchLabel = activeWorkbenchPath
    ? `进入${focusProjectTitle || "当前番茄项目"}工作台`
    : "进入工作台"

  useEffect(() => {
    setPomodoroDrafts(toPomodoroPlanDrafts(weeklySchedule))
    setSelectedSubjectIdByPlanId({})
  }, [weeklySchedule])

  useEffect(() => {
    if (pomodoroProjectOptionsLoading) return
    setPomodoroDrafts((prev) => {
      let changed = false
      const next = prev.map((draft) => {
        const subjectId = selectedSubjectIdByPlanId[draft.id] || normalizeDraftSubjectId(draft.subjectId, draft.projectRefs)
        if (subjectId === draft.subjectId) return draft
        changed = true
        return { ...draft, subjectId }
      })
      return changed ? next : prev
    })
  }, [pomodoroProjectOptionsLoading, selectedSubjectIdByPlanId])

  useEffect(() => {
    if (pomodoroOverviewMode !== "stats") return
    setPomodoroActivityRecords(listPomodoroActivityRecords())
  }, [pomodoroOverviewMode, now])

  useEffect(() => {
    if (!quickPomodoroSubjectId) {
      if (quickPomodoroProjectId) setQuickPomodoroProjectId("")
      return
    }
    if (!quickPomodoroProjectId) return
    const projects = subjectProjectOptions.get(quickPomodoroSubjectId) ?? []
    if (!projects.some((project) => project.projectId === quickPomodoroProjectId)) {
      setQuickPomodoroProjectId("")
    }
  }, [quickPomodoroProjectId, quickPomodoroSubjectId, subjectProjectOptions])

  const draftSchedule = useMemo(
    () => buildPomodoroScheduleFromPlanDrafts(pomodoroDrafts),
    [pomodoroDrafts],
  )
  const planConflictMessages = useMemo(() => validatePomodoroWeekSchedule(draftSchedule), [draftSchedule])
  const draftActiveDays = POMODORO_WEEKDAYS.filter((day) => draftSchedule[day].plans.some((plan) => plan.enabled))
  const enabledDayCount = draftActiveDays.length
  const activeDaySummary = formatActiveDaySummary(draftActiveDays)
  const projectBindingMessages = useMemo(
    () => {
      if (pomodoroProjectOptionsLoading) return []
      return pomodoroDrafts.flatMap((draft, draftIndex) => {
        const draftProjectRefs = normalizeDraftProjectRefs(draft.projectRefs, normalizeCountInput(draft.pomodoroCount, 4))
        const draftSubjectId = normalizeDraftSubjectId(draft.subjectId, draftProjectRefs)
        if (!draftSubjectId) return [`计划 ${draftIndex + 1} 需要先为这个计划选择学科`]
        return draftProjectRefs.flatMap((projectRef, pomodoroIndex) => {
          if (!projectRef) return [`计划 ${draftIndex + 1} 的番茄 ${pomodoroIndex + 1} 还没有选择项目`]
          if (!validPomodoroProjectRefs.has(pomodoroProjectRefKey(projectRef))) return [`计划 ${draftIndex + 1} 的番茄 ${pomodoroIndex + 1} 需要重新选择项目`]
          if (projectRef.subjectId !== draftSubjectId) return [`计划 ${draftIndex + 1} 的番茄 ${pomodoroIndex + 1} 需要重新选择这个学科下的项目`]
          return []
        })
      })
    },
    [pomodoroDrafts, pomodoroProjectOptionsLoading, validPomodoroProjectRefs],
  )
  const activePomodoroDraft = activePlanId ? pomodoroDrafts.find((draft) => draft.id === activePlanId) ?? null : null
  const activePomodoroDraftIndex = activePomodoroDraft ? pomodoroDrafts.findIndex((draft) => draft.id === activePomodoroDraft.id) : -1
  const todayDateKey = formatDateKey(now)
  const todayPomodoroRecords = useMemo(
    () => pomodoroActivityRecords.filter((record) => record.dateKey === todayDateKey),
    [pomodoroActivityRecords, todayDateKey],
  )
  const pomodoroPlanMetricSummaries = useMemo(
    () => buildPomodoroPlanMetricSummaries(draftSchedule, now),
    [draftSchedule, now],
  )
  const quickPomodoroMetricSummaries = useMemo(() => {
    const quickSegments: PomodoroSegmentMetricSummary[] = []
    const quickRecords = todayPomodoroRecords.filter((record) => record.planId === QUICK_POMODORO_PLAN_ID)

    quickRecords.forEach((record) => {
      quickSegments.push(
        loadPomodoroSegmentMetricSummary({
          projectId: record.projectId,
          projectRef: record.projectRef ?? null,
          dateKey: record.dateKey,
          planId: record.planId,
          planIndex: record.planIndex,
          pomodoroIndex: record.pomodoroIndex,
          scheduledStartAtMs: record.startAtMs,
          scheduledEndAtMs: record.endAtMs,
          now,
        }),
      )
    })

    if (quickPomodoro && formatDateKey(quickPomodoro.endAtMs) === todayDateKey) {
      const alreadyTracked = quickSegments.some(
        (segment) => segment.scheduledStartAtMs === quickPomodoro.startAtMs && segment.scheduledEndAtMs === quickPomodoro.endAtMs,
      )
      if (!alreadyTracked) {
        quickSegments.push(
          loadPomodoroSegmentMetricSummary({
            projectId: quickPomodoro.projectRef?.scopedProjectId ?? null,
            projectRef: quickPomodoro.projectRef ?? null,
            dateKey: formatDateKey(quickPomodoro.endAtMs),
            planId: QUICK_POMODORO_PLAN_ID,
            planIndex: -1,
            pomodoroIndex: 1,
            scheduledStartAtMs: quickPomodoro.startAtMs,
            scheduledEndAtMs: quickPomodoro.endAtMs,
            now,
          }),
        )
      }
    }

    if (quickSegments.length === 0) return []

    const sortedSegments = [...quickSegments].sort((left, right) => left.scheduledStartAtMs - right.scheduledStartAtMs)
    return [
      buildPomodoroMetricSummary({
        planId: QUICK_POMODORO_PLAN_ID,
        planIndex: -1,
        dateKey: todayDateKey,
        label: "小番茄",
        segments: sortedSegments,
      }),
    ]
  }, [now, quickPomodoro, todayDateKey, todayPomodoroRecords])
  const dailyMetricSummaries = [...pomodoroPlanMetricSummaries, ...quickPomodoroMetricSummaries]

  const headlineCountdown =
    snapshot.status === "running"
      ? formatPomodoroCountdown(snapshot.segmentRemainingMs)
      : snapshot.idleReason === "waiting"
        ? formatPomodoroCountdown(snapshot.untilStartMs)
        : "00:00"
  const isRestPhase = snapshot.status === "running" && snapshot.phase === "break"

  function updatePomodoroDraft(draftId: string, updater: (draft: PomodoroPlanDraft) => PomodoroPlanDraft) {
    setPomodoroDrafts((prev) => prev.map((draft) => (draft.id === draftId ? updater(clonePomodoroPlanDraft(draft)) : draft)))
  }

  function addPomodoroDraftPlan() {
    setPomodoroDrafts((prev) => {
      const nextDrafts = appendDefaultPomodoroPlanDraft(prev, defaultPrompts)
      const nextDraft = nextDrafts[nextDrafts.length - 1]
      if (nextDraft) {
        completeGuideWalkthroughStep("pomodoro-create-plan")
        window.setTimeout(() => nav(buildPomodoroPlanPath(nextDraft.id)), 0)
      }
      return nextDrafts
    })
  }

  async function removePomodoroDraftPlan(draftId: string) {
    const nextDrafts = pomodoroDrafts.filter((draft) => draft.id !== draftId)
    const nextSchedule = buildPomodoroScheduleFromPlanDrafts(nextDrafts)
    try {
      setDeletingPomodoroDraftId(draftId)
      await persistPomodoroSettings({ weeklySchedule: nextSchedule })
      setPomodoroDrafts(nextDrafts)
      setSettings({ enabled, weeklySchedule: nextSchedule, transitionSoundEnabled, microBreaks })
      showInfoFeedback("番茄计划已删除", nextDrafts.length > 0 ? "剩余计划已经保存。" : "当前没有番茄计划。")
      if (activePlanId === draftId) nav(buildPomodoroPath())
    } catch (err) {
      showErrorFeedback("删除番茄计划失败", formatApiError(err))
    } finally {
      setDeletingPomodoroDraftId((current) => (current === draftId ? "" : current))
    }
  }

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
        defaultFocusPrompt,
        defaultBreakPrompt,
        microBreaks,
      },
    }
    if (shouldSyncRemotely) {
      await updateGlobalSettings.mutateAsync(payload)
    }
    return payload
  }

  async function savePomodoroConfig() {
    if (planConflictMessages.length > 0) {
      showErrorFeedback("计划时间冲突", planConflictMessages.join("；"))
      return
    }
    try {
      await persistPomodoroSettings({ weeklySchedule: draftSchedule })
      setSettings({ enabled, weeklySchedule: draftSchedule, transitionSoundEnabled, microBreaks })
      showSuccessFeedback(
        "番茄钟排程已保存",
        enabledDayCount > 0 ? `当前在${activeDaySummary}生效。` : "排程已保存，但还没有启用任何日期。",
      )
      nav(buildPomodoroPath())
    } catch (err) {
      showErrorFeedback("保存番茄钟排程失败", formatApiError(err))
    }
  }

  async function handleTogglePomodoro() {
    const nextEnabled = !enabled
    if (!nextEnabled) {
      try {
        await persistPomodoroSettings({ enabled: false, weeklySchedule: draftSchedule })
        setEnabled(false)
        showInfoFeedback("番茄钟已关闭", "工作台已恢复正常访问，不再受自动排程限制。")
      } catch (err) {
        showErrorFeedback("关闭番茄钟失败", formatApiError(err))
      }
      return
    }
    if (planConflictMessages.length > 0) {
      showErrorFeedback("计划时间冲突", planConflictMessages.join("；"))
      return
    }
    if (projectBindingMessages.length > 0) {
      showInfoFeedback("先补全番茄项目", "开启番茄钟前，需要给学习时段选好项目。")
      return
    }
    try {
      await persistPomodoroSettings({ enabled: nextEnabled, weeklySchedule: draftSchedule })
      setEnabled(nextEnabled)
      if (nextEnabled) {
        completeGuideWalkthroughStep("pomodoro-enable-clock")
        showInfoFeedback(
          "番茄钟已开启",
          enabledDayCount > 0
            ? `之后会在${activeDaySummary}自动开始，学习时段只会放行当前番茄绑定的项目工作台。`
            : "番茄钟已开启，但你还没启用任何日期排程。",
        )
      }
    } catch (err) {
      showErrorFeedback(nextEnabled ? "开启番茄钟失败" : "关闭番茄钟失败", formatApiError(err))
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

  function openQuickPomodoroDialog() {
    if (isFocusRunning) {
      showInfoFeedback("番茄钟正在运行", "当前已经处于学习阶段，结束后再新建小番茄。")
      return
    }
    setQuickPomodoroDialogOpen(true)
  }

  function handleStartQuickPomodoro() {
    if (isFocusRunning) {
      showInfoFeedback("番茄钟正在运行", "当前已经处于学习阶段，结束后再新建小番茄。")
      return
    }
    if (!quickPomodoroProjectRef || !canCreateQuickPomodoro) {
      showInfoFeedback("先选择项目", "请选择学科和项目后再创建小番茄。")
      return
    }
    startQuickPomodoro(quickPomodoroProjectRef)
    setQuickPomodoroDialogOpen(false)
    setQuickPomodoroSubjectId("")
    setQuickPomodoroProjectId("")
    showSuccessFeedback(
      "小番茄已创建",
      "10 秒后开始 25 分钟学习，系统会进入所选项目工作台。",
    )
  }

  function handleQuickPomodoroButtonClick() {
    if (activeQuickPomodoro) {
      clearQuickPomodoro()
      showInfoFeedback("小番茄已结束", "工作台已恢复当前番茄之外的访问。")
      return
    }
    openQuickPomodoroDialog()
  }

  const wallpaperBackdrop = <PomodoroWallpaperBackdrop wallpaperUrl={wallpaperUrl} />

  if (pomodoroMemberBlocked) {
    return (
      <>
        {wallpaperBackdrop}
        <div data-pomodoro-wallpaper-scope="page" className="relative z-10 mx-auto flex w-full max-w-3xl flex-col gap-6">
          <MemberOnlyFeatureNotice
            title="番茄钟是会员专属功能"
            message="当前账号还没有有效会员。开通会员后，就可以继续使用排程、小番茄和相关设置。"
          />
        </div>
      </>
    )
  }

  if (activePlanId) {
    return (
      <>
        {wallpaperBackdrop}
        <div data-pomodoro-wallpaper-scope="page" className="relative z-10 mx-auto flex w-full max-w-5xl flex-col gap-8">
          <section data-pomodoro-plan-detail className="space-y-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="text-2xl font-semibold text-foreground">
                {activePomodoroDraft ? `计划 ${activePomodoroDraftIndex + 1}` : "计划不存在"}
              </div>
              <Button asChild variant="outline">
                <Link to={buildPomodoroPath()}>返回番茄计划</Link>
              </Button>
            </div>

            {planConflictMessages.length > 0 ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                计划时间冲突：{planConflictMessages.join("；")}
              </div>
            ) : null}
            {!activePomodoroDraft ? (
              <div className="rounded-lg border border-dashed border-[color:var(--theme-soft-border)] px-4 py-8 text-sm text-muted-foreground">
                这个番茄计划不存在，可能已经被删除。
              </div>
            ) : null}

            {(activePomodoroDraft ? [activePomodoroDraft] : []).map((pomodoroDraft) => {
              const draftPomodoroCount = normalizeCountInput(pomodoroDraft.pomodoroCount, 4)
              const draftProjectRefs = normalizeDraftProjectRefs(pomodoroDraft.projectRefs, draftPomodoroCount)
              const draftFocusPrompts = normalizeDraftFocusPrompts(pomodoroDraft.focusPrompts, draftPomodoroCount)
              const draftSubjectId = normalizeDraftSubjectId(pomodoroDraft.subjectId, draftProjectRefs)
              const selectableProjects = draftSubjectId ? subjectProjectOptions.get(draftSubjectId) ?? [] : []
              return (
                <div key={pomodoroDraft.id} className="space-y-5 border-t border-border/60 pt-5">
                  <div className="flex flex-wrap gap-3">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() =>
                        updatePomodoroDraft(pomodoroDraft.id, (draft) => ({
                          ...draft,
                          activeDays: ["mon", "tue", "wed", "thu", "fri"],
                        }))
                      }
                    >
                      工作日生效
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() =>
                        updatePomodoroDraft(pomodoroDraft.id, (draft) => ({
                          ...draft,
                          activeDays: ["sat", "sun"],
                        }))
                      }
                    >
                      周末生效
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() =>
                        updatePomodoroDraft(pomodoroDraft.id, (draft) => ({
                          ...draft,
                          activeDays: [...POMODORO_WEEKDAYS],
                        }))
                      }
                    >
                      每天生效
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      onClick={() =>
                        updatePomodoroDraft(pomodoroDraft.id, (draft) => ({
                          ...draft,
                          activeDays: [],
                        }))
                      }
                    >
                      全部关闭
                    </Button>
                  </div>

                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="text-sm font-medium text-foreground">生效星期</div>
                      <div className="text-xs text-muted-foreground">
                        {pomodoroDraft.activeDays.length}/{POMODORO_WEEKDAYS.length}
                      </div>
                    </div>
                    <div className="grid gap-2 sm:grid-cols-4 lg:grid-cols-7">
                      {POMODORO_WEEKDAYS.map((day) => {
                        const checked = pomodoroDraft.activeDays.includes(day)
                        return (
                          <label
                            key={day}
                            className={cn(
                              "flex min-h-12 cursor-pointer items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm transition-colors",
                              checked
                                ? "border-primary/40 bg-[hsl(var(--primary)/0.10)] text-primary"
                                : "border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] text-muted-foreground",
                            )}
                          >
                            <input
                              type="checkbox"
                              className="sr-only"
                              checked={checked}
                              onChange={(event) =>
                                updatePomodoroDraft(pomodoroDraft.id, (draft) => {
                                  const nextActiveDays = new Set(draft.activeDays)
                                  if (event.target.checked) {
                                    nextActiveDays.add(day)
                                  } else {
                                    nextActiveDays.delete(day)
                                  }
                                  return {
                                    ...draft,
                                    activeDays: POMODORO_WEEKDAYS.filter((item) => nextActiveDays.has(item)),
                                  }
                                })
                              }
                            />
                            <span>{POMODORO_WEEKDAY_LABELS[day]}</span>
                          </label>
                        )
                      })}
                    </div>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <div className="space-y-2">
                      <Label htmlFor={`pomodoro-start-${pomodoroDraft.id}`}>开始时间</Label>
                      <Input
                        id={`pomodoro-start-${pomodoroDraft.id}`}
                        type="time"
                        value={pomodoroDraft.startTime}
                        onChange={(event) =>
                          updatePomodoroDraft(pomodoroDraft.id, (draft) => ({
                            ...draft,
                            startTime: event.target.value,
                          }))
                        }
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor={`pomodoro-focus-${pomodoroDraft.id}`}>学习 M</Label>
                      <Input
                        id={`pomodoro-focus-${pomodoroDraft.id}`}
                        type="number"
                        min={1}
                        max={180}
                        value={pomodoroDraft.focusMinutes}
                        onChange={(event) =>
                          updatePomodoroDraft(pomodoroDraft.id, (draft) => ({
                            ...draft,
                            focusMinutes: event.target.value,
                          }))
                        }
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor={`pomodoro-break-${pomodoroDraft.id}`}>间歇 N</Label>
                      <Input
                        id={`pomodoro-break-${pomodoroDraft.id}`}
                        type="number"
                        min={1}
                        max={60}
                        value={pomodoroDraft.breakMinutes}
                        onChange={(event) =>
                          updatePomodoroDraft(pomodoroDraft.id, (draft) => ({
                            ...draft,
                            breakMinutes: event.target.value,
                          }))
                        }
                      />
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor={`pomodoro-count-${pomodoroDraft.id}`}>番茄数</Label>
                      <Input
                        id={`pomodoro-count-${pomodoroDraft.id}`}
                        type="number"
                        min={1}
                        max={12}
                        value={pomodoroDraft.pomodoroCount}
                        onChange={(event) =>
                          updatePomodoroDraft(pomodoroDraft.id, (draft) => {
                            const nextCount = normalizeCountInput(
                              event.target.value,
                              normalizeCountInput(draft.pomodoroCount, 4),
                            )
                            return {
                              ...draft,
                              pomodoroCount: event.target.value,
                              projectRefs: normalizeDraftProjectRefs(draft.projectRefs, nextCount),
                              focusPrompts: normalizeDraftFocusPrompts(draft.focusPrompts, nextCount),
                            }
                          })
                        }
                      />
                    </div>
                  </div>

                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="text-sm font-medium text-foreground">番茄项目 / 提示词</div>
                      <div className="text-xs text-muted-foreground">
                        {draftProjectRefs.filter(Boolean).length}/{draftPomodoroCount}
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor={`pomodoro-subject-${pomodoroDraft.id}`}>学科</Label>
                <select
                  id={`pomodoro-subject-${pomodoroDraft.id}`}
                  className="theme-select h-10 w-full rounded-xl px-3 text-sm"
                        value={draftSubjectId}
                        onChange={(event) => {
                          const nextSubjectId = event.target.value
                          setSelectedSubjectIdByPlanId((prev) => ({
                            ...prev,
                            [pomodoroDraft.id]: nextSubjectId,
                          }))
                          updatePomodoroDraft(pomodoroDraft.id, (draft) => ({
                            ...draft,
                            subjectId: nextSubjectId,
                            projectRefs: normalizeDraftProjectRefs(draft.projectRefs, normalizeCountInput(draft.pomodoroCount, 4)).map(() => null),
                          }))
                        }}
                      >
                        <option value="">请选择学科</option>
                        {(subjectsQ.data ?? []).map((subject) => (
                          <option key={subject.subjectId} value={subject.subjectId}>
                            {subject.title}
                          </option>
                        ))}
                      </select>
                    </div>

                    {availablePomodoroProjects.length === 0 && !pomodoroProjectOptionsLoading ? (
                      <div className="mt-3 text-sm text-muted-foreground">暂无可绑定项目。请先到学科中心，在学科下创建项目。</div>
                    ) : null}

                    <div className="pomodoro-project-prompt-scroll flex flex-nowrap gap-3 overflow-x-auto pb-2">
                      {draftProjectRefs.map((projectRef, index) => {
                        const promptKey = `${pomodoroDraft.id}:focus:${index}`
                        return (
                          <div
                            key={`${pomodoroDraft.id}-project-${index}`}
                            className="min-w-[20rem] flex-1 basis-[20rem] shrink-0 space-y-3 border-t border-border/60 pt-3 sm:min-w-[22rem] sm:basis-[22rem] lg:min-w-[24rem] lg:basis-[24rem]"
                          >
                            <div className="space-y-2">
                              <Label htmlFor={`pomodoro-project-${pomodoroDraft.id}-${index}`}>番茄 {index + 1}</Label>
                              <select
                                id={`pomodoro-project-${pomodoroDraft.id}-${index}`}
                                data-guide-tour={index === 0 ? "pomodoro-project-binding" : undefined}
                                className="theme-select h-10 w-full rounded-xl px-3 text-sm"
                                value={projectRef && validPomodoroProjectRefs.has(pomodoroProjectRefKey(projectRef)) ? projectRef.scopedProjectId : ""}
                                disabled={!draftSubjectId}
                                onChange={(event) => {
                                  const nextProjectId = event.target.value.trim() || null
                                  const nextProjectRef = nextProjectId ? { subjectId: draftSubjectId, scopedProjectId: nextProjectId } : null
                                  updatePomodoroDraft(pomodoroDraft.id, (draft) => {
                                    const nextProjectRefs = normalizeDraftProjectRefs(
                                      draft.projectRefs,
                                      normalizeCountInput(draft.pomodoroCount, 4),
                                    )
                                    nextProjectRefs[index] = nextProjectRef
                                    return {
                                      ...draft,
                                      subjectId: draftSubjectId,
                                      projectRefs: nextProjectRefs,
                                    }
                                  })
                                  if (nextProjectId) completeGuideWalkthroughStep("pomodoro-bind-project")
                                }}
                              >
                                <option value="">请选择项目</option>
                                {selectableProjects.map((project) => (
                                  <option key={project.projectId} value={project.projectId}>
                                    {getPomodoroSubjectProjectOptionLabel(project)}
                                  </option>
                                ))}
                              </select>
                            </div>

                            <div className="space-y-2">
                              <div className="flex items-center justify-between gap-2">
                                <Label htmlFor={`pomodoro-focus-prompt-${pomodoroDraft.id}-${index}`}>学习前提示词</Label>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => void handleTestPrompt(draftFocusPrompts[index] ?? "", promptKey)}
                                  disabled={
                                    testingPromptKey === promptKey ||
                                    !normalizeDraftPromptText(draftFocusPrompts[index]).trim()
                                  }
                                >
                                  <Volume2 className="h-3.5 w-3.5" />
                                  试听
                                </Button>
                              </div>
                              <textarea
                                id={`pomodoro-focus-prompt-${pomodoroDraft.id}-${index}`}
                                maxLength={200}
                                rows={3}
                                className="min-h-20 w-full resize-y rounded-xl border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-input-bg)] px-3 py-2 text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
                                placeholder="学习前提示"
                                value={draftFocusPrompts[index] ?? ""}
                                onChange={(event) =>
                                  updatePomodoroDraft(pomodoroDraft.id, (draft) => {
                                    const nextFocusPrompts = normalizeDraftFocusPrompts(
                                      draft.focusPrompts,
                                      normalizeCountInput(draft.pomodoroCount, 4),
                                    )
                                    nextFocusPrompts[index] = event.target.value
                                    return {
                                      ...draft,
                                      focusPrompts: nextFocusPrompts,
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

                  <div className="space-y-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="text-sm font-medium text-foreground">休息前提示词</div>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => void handleTestPrompt(pomodoroDraft.breakPrompt, `${pomodoroDraft.id}:break`)}
                        disabled={
                          testingPromptKey === `${pomodoroDraft.id}:break` ||
                          !normalizeDraftPromptText(pomodoroDraft.breakPrompt).trim()
                        }
                      >
                        <Volume2 className="h-4 w-4" />
                        试听休息提示
                      </Button>
                    </div>
                    <textarea
                      id={`pomodoro-break-prompt-${pomodoroDraft.id}`}
                      maxLength={200}
                      rows={3}
                      className="min-h-20 w-full resize-y rounded-xl border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-input-bg)] px-3 py-2 text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
                      placeholder="休息前提示"
                      value={pomodoroDraft.breakPrompt}
                      onChange={(event) =>
                        updatePomodoroDraft(pomodoroDraft.id, (draft) => ({
                          ...draft,
                          breakPrompt: event.target.value,
                        }))
                      }
                    />
                  </div>
                </div>
              )
            })}

            {activePomodoroDraft ? (
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/60 pt-5">
                <div className="flex flex-wrap gap-3">
                  <Button onClick={savePomodoroConfig} disabled={updateGlobalSettings.isPending || planConflictMessages.length > 0}>
                    <Save className="h-4 w-4" />
                    保存
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      const restoredDrafts = toPomodoroPlanDrafts(weeklySchedule)
                      setPomodoroDrafts(restoredDrafts)
                      if (activePlanId && !restoredDrafts.some((draft) => draft.id === activePlanId)) {
                        nav(buildPomodoroPath())
                      }
                    }}
                  >
                    <RotateCcw className="h-4 w-4" />
                    恢复
                  </Button>
                  <Button asChild variant="ghost">
                    <Link to={buildPomodoroPath()}>返回</Link>
                  </Button>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                  onClick={() => removePomodoroDraftPlan(activePomodoroDraft.id)}
                  disabled={deletingPomodoroDraftId === activePomodoroDraft.id}
                >
                  <Trash2 className="h-4 w-4" />
                  删除计划
                </Button>
              </div>
            ) : null}
          </section>
        </div>
      </>
    )
  }

  return (
    <>
      {wallpaperBackdrop}
      <div data-pomodoro-wallpaper-scope="page" className="relative z-10 mx-auto flex w-full max-w-5xl flex-col gap-8">
        <section data-pomodoro-session-controls className="space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1 space-y-5">
            <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
              <PhaseBadge snapshot={snapshot} />
              <div className="text-3xl font-semibold tracking-[-0.04em] text-foreground sm:text-4xl">{headlineCountdown}</div>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button data-guide-tour="pomodoro-session-status" variant={enabled ? "outline" : "default"} onClick={handleTogglePomodoro} disabled={updateGlobalSettings.isPending || planConflictMessages.length > 0}>
                <TimerReset className="h-4 w-4" />
                {enabled ? "关闭番茄钟" : "开启番茄钟"}
              </Button>
              <Button variant={activeQuickPomodoro ? "destructive" : "outline"} onClick={handleQuickPomodoroButtonClick}>
                {activeQuickPomodoro ? <CircleStop className="h-4 w-4" /> : <TimerReset className="h-4 w-4" />}
                {quickPomodoroButtonLabel}
              </Button>
              <Button variant="outline" asChild>
                <Link to={buildPomodoroSettingsPath()} aria-label="打开番茄钟设置" data-guide-tour="pomodoro-settings-entry">
                  <Settings2 className="h-4 w-4" />
                  番茄钟设置
                </Link>
              </Button>
              {activeWorkbenchPath ? (
                <Button asChild>
                  <Link
                    to={activeWorkbenchPath}
                    data-guide-tour="pomodoro-web-entry-reminder"
                    onClick={() => completeGuideWalkthroughStep("pomodoro-enter-web")}
                  >
                    <PanelsTopLeft className="h-4 w-4" />
                    {activeWorkbenchLabel}
                  </Link>
                </Button>
              ) : (
                <span className="sr-only" data-guide-tour="pomodoro-web-entry-reminder">
                  番茄开始后登录网页进入工作台
                </span>
              )}
            </div>
          </div>
          <Button
            type="button"
            variant="outline"
            onClick={() => setPomodoroOverviewMode((current) => (current === "stats" ? "plans" : "stats"))}
          >
            <BarChart3 className="h-4 w-4" />
            {pomodoroOverviewMode === "stats" ? "计划" : "统计"}
          </Button>
        </div>

        <div data-guide-tour="pomodoro-enable-toggle" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricTile label="今日开始" value={snapshot.startAtMs !== null ? snapshot.startTime : "未启用"} />
          <MetricTile label="启用日期" value={`${enabledDayCount} 天`} />
          <MetricTile label="下次开始" value={formatDateTime(snapshot.nextStartAtMs)} />
          <MetricTile label="工作台" value={enabled ? "按番茄放行" : "不限制"} />
        </div>
        </section>

      <RestMusicPlayer isRestPhase={isRestPhase} />

      <section className="space-y-4 border-t border-border/60 pt-6">
        {pomodoroOverviewMode === "stats" ? (
          <div data-pomodoro-statistics className="space-y-5">
            <div className="space-y-3">
              {dailyMetricSummaries.length === 0 ? (
                <div className="rounded-[1.1rem] border border-dashed border-[color:var(--theme-soft-border)] px-4 py-8 text-sm text-muted-foreground">
                  今天还没有可统计的番茄记录。
                </div>
              ) : (
                dailyMetricSummaries.map((planSummary) => (
                  <div
                    key={`${planSummary.dateKey}:${planSummary.planId}:${planSummary.planIndex}`}
                    className="space-y-4 rounded-[1.1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] px-4 py-4 shadow-[var(--theme-soft-shadow)]"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="text-sm font-medium text-muted-foreground">{planSummary.label}</div>
                        <div className="mt-1 text-xl font-semibold text-foreground">
                          网页驻留 {formatDurationCompact(planSummary.webPresenceMs)}
                        </div>
                      </div>
                      <div className="text-right text-sm text-muted-foreground">
                        <div>缺席时间 {formatDurationCompact(planSummary.absenceMs)}</div>
                        <div className="mt-1">
                          出勤率 {formatPercent(planSummary.attendanceRate)} · 有效学习率 {formatPercent(planSummary.effectiveLearningRate)}
                        </div>
                      </div>
                    </div>

                    <MetricDonut summary={planSummary} />

                    <div className="pomodoro-project-prompt-scroll flex flex-nowrap gap-3 overflow-x-auto pb-2">
                      {planSummary.segments.map((segment) => (
                        <div
                          key={`${segment.planId}:${segment.pomodoroIndex}:${segment.scheduledStartAtMs}`}
                          className="min-w-[20rem] flex-1 basis-[20rem] shrink-0 space-y-3 border-t border-border/60 pt-3 text-sm sm:min-w-[22rem] sm:basis-[22rem] lg:min-w-[24rem] lg:basis-[24rem]"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="font-medium text-foreground">
                              番茄 {segment.pomodoroIndex}
                              {segment.status === "in-progress" ? "（进行中）" : segment.status === "not-started" ? "（未开始）" : ""}
                            </div>
                            <div className="text-muted-foreground">
                              {formatPomodoroActivityTime(segment.scheduledStartAtMs)}-{formatPomodoroActivityTime(segment.scheduledEndAtMs)}
                            </div>
                          </div>
                          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-muted-foreground">
                            <span>网页驻留 {formatDurationCompact(segment.webPresenceMs)}</span>
                            <span>缺席时间 {formatDurationCompact(segment.absenceMs)}</span>
                            <span>视频观看 {formatDurationCompact(segment.videoMs)}</span>
                            <span>复述点录入 {formatDurationCompact(segment.recallEntryMs)}</span>
                            <span>复习用时 {formatDurationCompact(segment.reviewMs)}</span>
                            <span>AI 问答 {formatDurationCompact(segment.aiQaMs)}</span>
                            <span>走神时间 {formatDurationCompact(segment.distractionMs)}</span>
                            <span>有效学习率 {formatPercent(segment.effectiveLearningRate)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        ) : (
        <div data-pomodoro-plan-overview data-guide-tour="pomodoro-plan-editor" className="space-y-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="text-lg font-semibold text-foreground">
                番茄计划：{pomodoroDrafts.length}组
              </div>
            </div>
            <Button type="button" variant="outline" data-guide-tour="pomodoro-create-plan-button" onClick={addPomodoroDraftPlan}>
              <Plus className="h-4 w-4" />
              新增计划
            </Button>
          </div>

          {planConflictMessages.length > 0 ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              计划时间冲突：{planConflictMessages.join("；")}
            </div>
          ) : null}
          <div className="grid gap-3 md:grid-cols-2">
            {pomodoroDrafts.map((pomodoroDraft, draftIndex) => {
              const draftPomodoroCount = normalizeCountInput(pomodoroDraft.pomodoroCount, 4)
              const draftProjectRefs = normalizeDraftProjectRefs(pomodoroDraft.projectRefs, draftPomodoroCount)
              const assignedProjectCount = draftProjectRefs.filter(Boolean).length
              return (
                <Link
                  key={pomodoroDraft.id}
                  to={buildPomodoroPlanPath(pomodoroDraft.id)}
                  className="block space-y-3 rounded-[1.1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] px-4 py-4 text-foreground shadow-[var(--theme-soft-shadow)] transition hover:-translate-y-px hover:border-primary/25"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium text-muted-foreground">计划 {draftIndex + 1}</div>
                      <div className="mt-1 text-xl font-semibold">{normalizePomodoroStartTime(pomodoroDraft.startTime)}</div>
                    </div>
                    <span className="rounded-full border border-[color:var(--theme-soft-border)] px-2.5 py-1 text-xs text-muted-foreground">详情</span>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {formatActiveDaySummary(pomodoroDraft.activeDays)} · {draftPomodoroCount} 个番茄
                  </div>
                  <div className="text-sm text-[color:var(--theme-soft-text-strong)]">
                    项目 {assignedProjectCount}/{draftPomodoroCount} · 学习 {normalizeFocusInput(pomodoroDraft.focusMinutes, 25)} 分钟 · 间歇 {normalizeBreakInput(pomodoroDraft.breakMinutes, 5)} 分钟
                  </div>
                </Link>
              )
            })}
          </div>
        </div>
        )}
      </section>
      </div>
      <Dialog open={quickPomodoroDialogOpen} onOpenChange={setQuickPomodoroDialogOpen}>
        <DialogContent className="max-w-md rounded-[1.25rem] border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)]">
          <DialogHeader>
            <DialogTitle>新建小番茄</DialogTitle>
            <DialogDescription className="sr-only">选择学科和项目后创建小番茄。</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="quick-pomodoro-subject">学科</Label>
              <select
                id="quick-pomodoro-subject"
                className="theme-select h-10 w-full rounded-xl px-3 text-sm"
                value={quickPomodoroSubjectId}
                onChange={(event) => {
                  setQuickPomodoroSubjectId(event.target.value)
                  setQuickPomodoroProjectId("")
                }}
              >
                <option value="">请选择学科</option>
                {(subjectsQ.data ?? []).map((subject) => (
                  <option key={subject.subjectId} value={subject.subjectId}>
                    {subject.title}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="quick-pomodoro-project">项目</Label>
              <select
                id="quick-pomodoro-project"
                className="theme-select h-10 w-full rounded-xl px-3 text-sm"
                value={quickPomodoroProjectId}
                disabled={!quickPomodoroSubjectId || pomodoroProjectOptionsLoading}
                onChange={(event) => setQuickPomodoroProjectId(event.target.value)}
              >
                <option value="">请选择项目</option>
                {quickPomodoroSelectableProjects.map((project) => (
                  <option key={project.projectId} value={project.projectId}>
                    {getPomodoroSubjectProjectOptionLabel(project)}
                  </option>
                ))}
              </select>
            </div>
            {availablePomodoroProjects.length === 0 && !pomodoroProjectOptionsLoading ? (
              <div className="text-sm text-muted-foreground">暂无可用项目。</div>
            ) : null}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setQuickPomodoroDialogOpen(false)}>
              取消
            </Button>
            <Button type="button" onClick={handleStartQuickPomodoro} disabled={!canCreateQuickPomodoro}>
              <TimerReset className="h-4 w-4" />
              创建小番茄
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

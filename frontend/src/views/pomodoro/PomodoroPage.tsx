import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { FolderOpen, Music2, PanelsTopLeft, Pause, Play, Plus, RefreshCw, RotateCcw, Save, Settings2, SkipForward, TimerReset, Trash2, Volume2 } from "lucide-react"
import { Link, useLocation, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { playPomodoroVoicePrompt, unlockPomodoroAudio } from "@/ui/pomodoroAudio"
import {
  getPomodoroRestMusicPlayerSnapshot,
  pausePomodoroRestMusic,
  playPomodoroRestMusicTrack,
  subscribePomodoroRestMusicPlayer,
} from "@/ui/pomodoroRestMusicPlayer"
import { Button } from "@/ui/components/ui/button"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import {
  resolvePomodoroRestMusicFile,
  scanPomodoroRestMusicDirectory,
  type PomodoroRestMusicTrack,
  usePomodoroRestMusicDirectoryBinding,
} from "@/ui/localMedia/projectDirectory"
import { readPomodoroWallpaperBlob } from "@/ui/pomodoroWallpaper"
import { useCurrentUser } from "@/ui/queries/auth"
import { useMembershipSummary } from "@/ui/queries/membership"
import { useProject, useProjects } from "@/ui/queries/projects"
import { useUpdateMyGlobalSettings } from "@/ui/queries/profile"
import { useSystemCapabilities } from "@/ui/queries/system"
import { usePageMeta } from "@/ui/seo/usePageMeta"
import { useAppStore } from "@/ui/store/appStore"
import { showErrorFeedback, showInfoFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import {
  POMODORO_WEEKDAYS,
  POMODORO_WEEKDAY_LABELS,
  describePomodoroPhase,
  formatPomodoroCountdown,
  getPomodoroSnapshot,
  isQuickPomodoroSessionActive,
  normalizePomodoroStartTime,
  normalizePomodoroPromptText,
  normalizePomodoroWeekSchedule,
  validatePomodoroWeekSchedule,
  type PomodoroDefaultPrompts,
  type PomodoroPlanSchedule,
  type PomodoroSnapshot,
  type PomodoroWeekSchedule,
  type PomodoroWeekday,
  usePomodoroNow,
  usePomodoroStore,
} from "@/ui/store/pomodoroStore"
import { useThemeStore } from "@/ui/store/themeStore"
import { cn } from "@/ui/utils"
import { MemberOnlyFeatureNotice } from "@/views/membership/membershipUi"
import { buildPomodoroPath, buildPomodoroPlanPath, buildPomodoroSettingsPath } from "@/views/pomodoro/pomodoroRouting"

type PomodoroPlanDraft = {
  id: string
  activeDays: PomodoroWeekday[]
  startTime: string
  focusMinutes: string
  breakMinutes: string
  pomodoroCount: string
  projectIds: Array<string | null>
  breakPrompt: string
  focusPrompts: string[]
}

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

function normalizeDraftProjectIds(projectIds: Array<string | null> | undefined, pomodoroCount: number) {
  const normalizedCount = clampInteger(pomodoroCount, 1, 12)
  return Array.from({ length: normalizedCount }, (_, index) => {
    const value = projectIds?.[index]
    return typeof value === "string" && value.trim() ? value.trim() : null
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

function clonePomodoroPlanDraft(draft: PomodoroPlanDraft): PomodoroPlanDraft {
  return {
    ...draft,
    activeDays: [...draft.activeDays],
    projectIds: [...draft.projectIds],
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
    projectIds: normalizeDraftProjectIds(overrides?.projectIds, pomodoroCount),
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
    projectIds: normalizeDraftProjectIds(plan.projectIds, plan.pomodoroCount),
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
          projectIds: plan.projectIds,
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
      projectIds: normalizeDraftProjectIds(draft.projectIds, normalizedPomodoroCount),
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
  return <span className={cn("text-sm font-semibold", className)}>{label}</span>
}

function MetricTile(props: { label: string; value: string }) {
  return (
    <div className="border-t border-border/60 py-3">
      <div className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">{props.label}</div>
      <div className="mt-2 text-lg font-semibold tracking-[-0.02em] text-foreground">{props.value}</div>
    </div>
  )
}

function readLocationState(locationState: unknown) {
  if (!locationState || typeof locationState !== "object") {
    return {
      fromPath: "",
    }
  }
  const input = locationState as { from?: unknown }
  return {
    fromPath: typeof input.from === "string" ? input.from : "",
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
  const location = useLocation()
  const nav = useNavigate()
  const { planId: routePlanId } = useParams()
  const activePlanId = routePlanId ? decodeURIComponent(routePlanId) : null
  const selectedProjectId = useAppStore((state) => state.selectedProjectId)
  const { projectTitle: selectedProjectTitle } = useProject(selectedProjectId ?? "", { enabled: Boolean(selectedProjectId) })
  const projectsQ = useProjects(true)
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
  const quickPomodoroClockActive = isQuickPomodoroSessionActive(quickPomodoro)
  const now = usePomodoroNow(enabled || quickPomodoroClockActive)
  const { fromPath } = useMemo(() => readLocationState(location.state), [location.state])
  const [pomodoroDrafts, setPomodoroDrafts] = useState<PomodoroPlanDraft[]>(() => toPomodoroPlanDrafts(weeklySchedule))
  const [testingPromptKey, setTestingPromptKey] = useState("")
  const [wallpaperUrl, setWallpaperUrl] = useState("")
  const wallpaperObjectUrlRef = useRef("")

  usePageMeta({
    title: activePlanId ? "番茄计划详情 | LearningPyramid" : "番茄钟 | LearningPyramid",
    description: activePlanId ? "编辑单个番茄计划" : "番茄钟",
    path: activePlanId ? buildPomodoroPlanPath(activePlanId) : buildPomodoroPath(),
  })

  const capabilitiesQ = useSystemCapabilities()
  const authEnabled = capabilitiesQ.data?.authEnabled ?? false
  const currentUserQ = useCurrentUser(authEnabled)
  const updateGlobalSettings = useUpdateMyGlobalSettings()
  const shouldSyncRemotely = authEnabled && Boolean(currentUserQ.data?.userId)
  const membershipQ = useMembershipSummary(authEnabled)
  const pomodoroMemberBlocked = authEnabled && (membershipQ.isLoading || Boolean(membershipQ.error) || !membershipQ.data?.isActive)
  const projectTitleMap = useMemo(
    () => new Map((projectsQ.data ?? []).map((project) => [project.projectId, project.title] as const)),
    [projectsQ.data],
  )
  const availableProjects = projectsQ.data ?? []
  const defaultPrompts = useMemo(
    () => ({ focusPrompt: defaultFocusPrompt, breakPrompt: defaultBreakPrompt }),
    [defaultBreakPrompt, defaultFocusPrompt],
  )

  const replacePomodoroWallpaperPreview = useCallback((blob: Blob | null) => {
    if (wallpaperObjectUrlRef.current) {
      URL.revokeObjectURL(wallpaperObjectUrlRef.current)
      wallpaperObjectUrlRef.current = ""
    }
    if (!blob) {
      setWallpaperUrl("")
      return
    }
    const nextUrl = URL.createObjectURL(blob)
    wallpaperObjectUrlRef.current = nextUrl
    setWallpaperUrl(nextUrl)
  }, [])

  const snapshot = useMemo(() => getPomodoroSnapshot({ enabled, weeklySchedule, quickPomodoro }, now), [enabled, now, quickPomodoro, weeklySchedule])
  const activeQuickPomodoro = isQuickPomodoroSessionActive(quickPomodoro, now) ? quickPomodoro : null
  const quickPomodoroButtonLabel =
    activeQuickPomodoro && now < activeQuickPomodoro.startAtMs
      ? `小番茄 ${formatPomodoroCountdown(activeQuickPomodoro.startAtMs - now)}`
      : activeQuickPomodoro
        ? "小番茄进行中"
        : "新建小番茄"
  const isFocusRunning = snapshot.status === "running" && snapshot.phase === "focus"
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

  useEffect(() => {
    setPomodoroDrafts(toPomodoroPlanDrafts(weeklySchedule))
  }, [weeklySchedule])

  useEffect(() => {
    let cancelled = false
    void readPomodoroWallpaperBlob()
      .then((blob) => {
        if (cancelled || !blob) return
        replacePomodoroWallpaperPreview(blob)
      })
      .catch(() => {
        // Wallpaper is cosmetic, so a local storage read failure should not block the timer page.
      })
    return () => {
      cancelled = true
      if (wallpaperObjectUrlRef.current) {
        URL.revokeObjectURL(wallpaperObjectUrlRef.current)
        wallpaperObjectUrlRef.current = ""
      }
    }
  }, [replacePomodoroWallpaperPreview])

  const draftSchedule = useMemo(
    () => buildPomodoroScheduleFromPlanDrafts(pomodoroDrafts),
    [pomodoroDrafts],
  )
  const planConflictMessages = useMemo(() => validatePomodoroWeekSchedule(draftSchedule), [draftSchedule])
  const draftActiveDays = POMODORO_WEEKDAYS.filter((day) => draftSchedule[day].plans.some((plan) => plan.enabled))
  const enabledDayCount = draftActiveDays.length
  const activeDaySummary = formatActiveDaySummary(draftActiveDays)
  const enabledDraftCount = pomodoroDrafts.filter((draft) => draft.activeDays.length > 0).length
  const enabledUnassignedPomodoros = POMODORO_WEEKDAYS.reduce(
    (sum, day) =>
      sum +
      draftSchedule[day].plans.reduce(
        (planSum, plan) => planSum + (plan.enabled ? plan.projectIds.filter((projectId) => !projectId).length : 0),
        0,
      ),
    0,
  )
  const draftStartTimes = [...new Set(pomodoroDrafts.map((draft) => normalizePomodoroStartTime(draft.startTime)))].sort()
  const activePomodoroDraft = activePlanId ? pomodoroDrafts.find((draft) => draft.id === activePlanId) ?? null : null
  const activePomodoroDraftIndex = activePomodoroDraft ? pomodoroDrafts.findIndex((draft) => draft.id === activePomodoroDraft.id) : -1

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
        window.setTimeout(() => nav(buildPomodoroPlanPath(nextDraft.id)), 0)
      }
      return nextDrafts
    })
  }

  function removePomodoroDraftPlan(draftId: string) {
    setPomodoroDrafts((prev) => prev.filter((draft) => draft.id !== draftId))
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
        enabledDayCount > 0
          ? enabledUnassignedPomodoros > 0
            ? `当前在${activeDaySummary}生效，但还有 ${enabledUnassignedPomodoros} 个番茄未绑定项目。`
            : `当前在${activeDaySummary}生效。`
          : "排程已保存，但还没有启用任何日期。",
      )
    } catch (err) {
      showErrorFeedback("保存番茄钟排程失败", formatApiError(err))
    }
  }

  async function handleTogglePomodoro() {
    if (planConflictMessages.length > 0) {
      showErrorFeedback("计划时间冲突", planConflictMessages.join("；"))
      return
    }
    const nextEnabled = !enabled
    try {
      await persistPomodoroSettings({ enabled: nextEnabled, weeklySchedule: draftSchedule })
      setEnabled(nextEnabled)
      if (nextEnabled) {
        showInfoFeedback(
          "番茄钟已开启",
          enabledDayCount > 0
            ? `之后会在${activeDaySummary}自动开始，学习时段只会放行当前番茄绑定的项目工作台。`
            : "番茄钟已开启，但你还没启用任何日期排程。",
        )
      } else {
        showInfoFeedback("番茄钟已关闭", "工作台已恢复正常访问，不再受自动排程限制。")
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

  function handleStartQuickPomodoro() {
    if (isFocusRunning) {
      showInfoFeedback("番茄钟正在运行", "当前已经处于学习阶段，结束后再新建小番茄。")
      return
    }
    const quick = startQuickPomodoro(selectedProjectId)
    showSuccessFeedback(
      "小番茄已创建",
      quick.projectId
        ? "10 秒后开始 25 分钟学习，系统会进入当前选中项目的工作台。"
        : "10 秒后开始 25 分钟学习。",
    )
  }

  const wallpaperBackdrop = wallpaperUrl ? (
    <div
      data-pomodoro-wallpaper-backdrop
      className="pointer-events-none fixed inset-x-0 bottom-0 top-[4.5rem] z-0 bg-cover bg-center"
      style={{ backgroundImage: `url(${wallpaperUrl})` }}
    >
      <div
        className="absolute inset-0 backdrop-blur-[1px]"
        style={{
          background:
            "linear-gradient(180deg, hsl(var(--background) / 0.58) 0%, hsl(var(--background) / 0.72) 48%, hsl(var(--background) / 0.82) 100%)",
        }}
      />
    </div>
  ) : null

  if (pomodoroMemberBlocked) {
    return (
      <div data-pomodoro-wallpaper-scope="page" className="relative z-10 mx-auto flex w-full max-w-3xl flex-col gap-6">
        <MemberOnlyFeatureNotice
          title="番茄钟是会员专属功能"
          message="当前账号还没有有效会员，所以这里先不开放番茄钟。开通会员后，就可以继续使用排程、小番茄和相关设置。"
        />
      </div>
    )
  }

  if (activePlanId) {
    return (
      <>
        {wallpaperBackdrop}
        <div data-pomodoro-wallpaper-scope="page" className="relative z-10 mx-auto flex w-full max-w-5xl flex-col gap-8">
          <section data-pomodoro-plan-detail className="space-y-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-sm font-medium text-muted-foreground">番茄计划详情</div>
                <div className="mt-1 text-2xl font-semibold text-foreground">
                  {activePomodoroDraft ? `计划 ${activePomodoroDraftIndex + 1}` : "计划不存在"}
                </div>
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
              const draftProjectIds = normalizeDraftProjectIds(pomodoroDraft.projectIds, draftPomodoroCount)
              const draftFocusPrompts = normalizeDraftFocusPrompts(pomodoroDraft.focusPrompts, draftPomodoroCount)
              const draftActiveDaySummary = formatActiveDaySummary(pomodoroDraft.activeDays)
              const draftIndex = activePomodoroDraftIndex
              return (
                <div key={pomodoroDraft.id} className="space-y-5 border-t border-border/60 pt-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium text-foreground">计划 {draftIndex + 1}</div>
                      <div className="mt-1 text-sm text-muted-foreground">
                        {normalizePomodoroStartTime(pomodoroDraft.startTime)} · {draftActiveDaySummary}
                      </div>
                    </div>
                    <Button type="button" variant="ghost" size="sm" onClick={() => removePomodoroDraftPlan(pomodoroDraft.id)}>
                      <Trash2 className="h-4 w-4" />
                      删除计划
                    </Button>
                  </div>

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
                              projectIds: normalizeDraftProjectIds(draft.projectIds, nextCount),
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
                        {draftProjectIds.filter(Boolean).length}/{draftPomodoroCount}
                      </div>
                    </div>

                    {availableProjects.length === 0 && !projectsQ.isLoading ? (
                      <div className="mt-3 text-sm text-muted-foreground">暂无可绑定项目</div>
                    ) : null}

                    <div className="pomodoro-project-prompt-scroll flex flex-nowrap gap-3 overflow-x-auto pb-2">
                      {draftProjectIds.map((projectId, index) => {
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
                                className="theme-select h-10 w-full rounded-xl px-3 text-sm"
                                value={projectId ?? ""}
                                onChange={(event) =>
                                  updatePomodoroDraft(pomodoroDraft.id, (draft) => {
                                    const nextProjectIds = normalizeDraftProjectIds(
                                      draft.projectIds,
                                      normalizeCountInput(draft.pomodoroCount, 4),
                                    )
                                    nextProjectIds[index] = event.target.value.trim() || null
                                    return {
                                      ...draft,
                                      projectIds: nextProjectIds,
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
              <div className="flex flex-wrap gap-3">
                <Button onClick={savePomodoroConfig} disabled={updateGlobalSettings.isPending || planConflictMessages.length > 0}>
                  <Save className="h-4 w-4" />
                  保存
                </Button>
                <Button variant="outline" onClick={() => setPomodoroDrafts(toPomodoroPlanDrafts(weeklySchedule))}>
                  <RotateCcw className="h-4 w-4" />
                  恢复
                </Button>
                <Button asChild variant="ghost">
                  <Link to={buildPomodoroPath()}>返回</Link>
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
              <Button variant={enabled ? "outline" : "default"} onClick={handleTogglePomodoro} disabled={updateGlobalSettings.isPending}>
                <TimerReset className="h-4 w-4" />
                {enabled ? "关闭番茄钟" : "开启番茄钟"}
              </Button>
              <Button variant="outline" onClick={handleStartQuickPomodoro} disabled={Boolean(activeQuickPomodoro) || isFocusRunning}>
                <TimerReset className="h-4 w-4" />
                {quickPomodoroButtonLabel}
              </Button>
              <Button variant="outline" asChild>
                <Link to={buildPomodoroSettingsPath()} aria-label="打开番茄钟设置">
                  <Settings2 className="h-4 w-4" />
                  番茄钟设置
                </Link>
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
        </div>

        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <MetricTile label="今日开始" value={snapshot.startAtMs !== null ? snapshot.startTime : "未启用"} />
          <MetricTile label="启用日期" value={`${enabledDayCount} 天`} />
          <MetricTile label="下次开始" value={formatDateTime(snapshot.nextStartAtMs)} />
          <MetricTile label="工作台" value={enabled ? "按番茄放行" : "不限制"} />
        </div>
      </section>

      <RestMusicPlayer isRestPhase={isRestPhase} />

      <section className="space-y-4 border-t border-border/60 pt-6">
        <div data-pomodoro-plan-overview className="space-y-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="text-sm font-medium text-muted-foreground">番茄计划</div>
              <div className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-foreground">
                {enabledDraftCount > 0 ? `${enabledDraftCount} 组` : "未启用"}
              </div>
              <div className="mt-2 text-sm leading-6 text-[color:var(--theme-soft-text-strong)]">
                {draftStartTimes.length > 0 ? draftStartTimes.join("、") : "还没有开始时间"}
              </div>
              <div className="mt-1 text-sm text-muted-foreground">
                {enabledUnassignedPomodoros > 0 ? `${enabledUnassignedPomodoros} 个番茄未绑定项目` : "项目已配置"} · {activeDaySummary}
              </div>
            </div>
            <Button type="button" variant="outline" onClick={addPomodoroDraftPlan}>
              <Plus className="h-4 w-4" />
              新增计划
            </Button>
          </div>

          {planConflictMessages.length > 0 ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              计划时间冲突：{planConflictMessages.join("；")}
            </div>
          ) : null}

          {pomodoroDrafts.length === 0 ? (
            <div className="rounded-lg border border-dashed border-[color:var(--theme-soft-border)] px-4 py-8 text-sm text-muted-foreground">
              还没有计划，新增一组后再进入详情设置。
            </div>
          ) : null}

          <div className="grid gap-3 md:grid-cols-2">
            {pomodoroDrafts.map((pomodoroDraft, draftIndex) => {
              const draftPomodoroCount = normalizeCountInput(pomodoroDraft.pomodoroCount, 4)
              const draftProjectIds = normalizeDraftProjectIds(pomodoroDraft.projectIds, draftPomodoroCount)
              const assignedProjectCount = draftProjectIds.filter(Boolean).length
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
      </section>
      </div>
    </>
  )
}

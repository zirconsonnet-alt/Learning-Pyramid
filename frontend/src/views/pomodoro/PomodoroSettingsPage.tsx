import { useCallback, useEffect, useRef, useState, type ChangeEvent } from "react"
import { ArrowLeft, FolderOpen, ImageOff, ImagePlus, Music2, RotateCcw, Save, Trash2 } from "lucide-react"
import { Link } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { Button } from "@/ui/components/ui/button"
import { Label } from "@/ui/components/ui/label"
import { type DirectoryBindingPermission, usePomodoroRestMusicDirectoryBinding } from "@/ui/localMedia/projectDirectory"
import {
  POMODORO_WALLPAPER_MAX_BYTES,
  readPomodoroWallpaperBlob,
  removePomodoroWallpaperBlob,
  savePomodoroWallpaperBlob,
} from "@/ui/pomodoroWallpaper"
import { useCurrentUser } from "@/ui/queries/auth"
import { useMembershipSummary } from "@/ui/queries/membership"
import { useUpdateMyGlobalSettings } from "@/ui/queries/profile"
import { useSystemCapabilities } from "@/ui/queries/system"
import { usePageMeta } from "@/ui/seo/usePageMeta"
import { showErrorFeedback, showInfoFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import {
  DEFAULT_RANDOM_MICRO_BREAK_SETTINGS,
  normalizePomodoroPromptText,
  normalizeRandomMicroBreakSettings,
  type RandomMicroBreakSettings,
  usePomodoroStore,
} from "@/ui/store/pomodoroStore"
import { useThemeStore } from "@/ui/store/themeStore"
import { MemberOnlyFeatureNotice } from "@/views/membership/membershipUi"
import { buildPomodoroPath, buildPomodoroSettingsPath } from "@/views/pomodoro/pomodoroRouting"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function describeLocalDirectoryPermission(permission: DirectoryBindingPermission) {
  if (permission === "unsupported") return "当前浏览器不支持目录授权"
  if (permission === "missing") return "未绑定目录"
  if (permission === "prompt") return "待授权"
  if (permission === "denied") return "已拒绝"
  return "已授权"
}

function describeLocalDirectoryPermissionTone(permission: DirectoryBindingPermission) {
  if (permission === "granted") return "theme-pill-accent"
  if (permission === "prompt") return "theme-pill-warm"
  if (permission === "denied") return "theme-pill-danger"
  return "theme-pill-default"
}

type MicroBreakDraft = {
  enabled: boolean
  minIntervalSeconds: string
  maxIntervalSeconds: string
  durationSeconds: string
}

function toMicroBreakDraft(settings: RandomMicroBreakSettings): MicroBreakDraft {
  return {
    enabled: settings.enabled,
    minIntervalSeconds: String(settings.minIntervalSeconds),
    maxIntervalSeconds: String(settings.maxIntervalSeconds),
    durationSeconds: String(settings.durationSeconds),
  }
}

function parseMicroBreakSeconds(value: string) {
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) ? parsed : 0
}

function validateMicroBreakDraft(draft: MicroBreakDraft) {
  const minIntervalSeconds = parseMicroBreakSeconds(draft.minIntervalSeconds)
  const maxIntervalSeconds = parseMicroBreakSeconds(draft.maxIntervalSeconds)
  const durationSeconds = parseMicroBreakSeconds(draft.durationSeconds)
  if (minIntervalSeconds < 30 || minIntervalSeconds > 3600) {
    return { error: "最短间隔需要在 30 到 3600 秒之间。", settings: null }
  }
  if (maxIntervalSeconds < 30 || maxIntervalSeconds > 3600) {
    return { error: "最长间隔需要在 30 到 3600 秒之间。", settings: null }
  }
  if (maxIntervalSeconds < minIntervalSeconds) {
    return { error: "最长间隔不能小于最短间隔。", settings: null }
  }
  if (durationSeconds < 5 || durationSeconds > 300) {
    return { error: "闭眼休息时长需要在 5 到 300 秒之间。", settings: null }
  }
  return {
    error: "",
    settings: normalizeRandomMicroBreakSettings({
      enabled: draft.enabled,
      minIntervalSeconds,
      maxIntervalSeconds,
      durationSeconds,
    }),
  }
}

export function PomodoroSettingsPage() {
  const selectedTheme = useThemeStore((state) => state.theme)
  const enabled = usePomodoroStore((state) => state.enabled)
  const weeklySchedule = usePomodoroStore((state) => state.weeklySchedule)
  const transitionSoundEnabled = usePomodoroStore((state) => state.transitionSoundEnabled)
  const defaultFocusPrompt = usePomodoroStore((state) => state.defaultFocusPrompt)
  const defaultBreakPrompt = usePomodoroStore((state) => state.defaultBreakPrompt)
  const microBreaks = usePomodoroStore((state) => state.microBreaks)
  const setDefaultPrompts = usePomodoroStore((state) => state.setDefaultPrompts)
  const setMicroBreakSettings = usePomodoroStore((state) => state.setMicroBreakSettings)
  const [focusPromptDraft, setFocusPromptDraft] = useState(defaultFocusPrompt)
  const [breakPromptDraft, setBreakPromptDraft] = useState(defaultBreakPrompt)
  const [microBreakDraft, setMicroBreakDraft] = useState(() => toMicroBreakDraft(microBreaks))
  const [microBreakError, setMicroBreakError] = useState("")

  usePageMeta({
    title: "番茄钟设置 | LearningPyramid",
    description: "设置番茄钟默认学习提示词和默认休息提示词。",
    path: buildPomodoroSettingsPath(),
  })

  const capabilitiesQ = useSystemCapabilities()
  const authEnabled = capabilitiesQ.data?.authEnabled ?? false
  const currentUserQ = useCurrentUser(authEnabled)
  const updateGlobalSettings = useUpdateMyGlobalSettings()
  const shouldSyncRemotely = authEnabled && Boolean(currentUserQ.data?.userId)
  const membershipQ = useMembershipSummary(authEnabled)
  const pomodoroMemberBlocked = authEnabled && (membershipQ.isLoading || Boolean(membershipQ.error) || !membershipQ.data?.isActive)
  const restMusicDirectory = usePomodoroRestMusicDirectoryBinding()
  const [restMusicDirectoryAction, setRestMusicDirectoryAction] = useState<"authorize" | "request" | "clear" | null>(null)
  const [wallpaperUrl, setWallpaperUrl] = useState("")
  const wallpaperInputRef = useRef<HTMLInputElement | null>(null)
  const wallpaperObjectUrlRef = useRef("")
  const restMusicDirectoryBusy = restMusicDirectoryAction !== null
  const canChooseRestMusicDirectory =
    restMusicDirectory.supported && !restMusicDirectory.loading && !restMusicDirectoryBusy
  const canRequestRestMusicDirectoryPermission =
    restMusicDirectory.supported &&
    !restMusicDirectory.loading &&
    !restMusicDirectoryBusy &&
    (restMusicDirectory.permission === "prompt" || restMusicDirectory.permission === "denied")
  const canClearRestMusicDirectory =
    restMusicDirectory.supported &&
    !restMusicDirectory.loading &&
    !restMusicDirectoryBusy &&
    restMusicDirectory.permission !== "missing"

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

  useEffect(() => {
    setFocusPromptDraft(defaultFocusPrompt)
  }, [defaultFocusPrompt])

  useEffect(() => {
    setBreakPromptDraft(defaultBreakPrompt)
  }, [defaultBreakPrompt])

  useEffect(() => {
    setMicroBreakDraft(toMicroBreakDraft(microBreaks))
    setMicroBreakError("")
  }, [microBreaks])

  useEffect(() => {
    let cancelled = false
    void readPomodoroWallpaperBlob()
      .then((blob) => {
        if (cancelled) return
        replacePomodoroWallpaperPreview(blob)
      })
      .catch(() => {
        // Local wallpaper is cosmetic; settings remain usable if IndexedDB is unavailable.
      })
    return () => {
      cancelled = true
      if (wallpaperObjectUrlRef.current) {
        URL.revokeObjectURL(wallpaperObjectUrlRef.current)
        wallpaperObjectUrlRef.current = ""
      }
    }
  }, [replacePomodoroWallpaperPreview])

  async function persistPomodoroPromptSettings(
    nextFocusPrompt: string,
    nextBreakPrompt: string,
    nextMicroBreaks = microBreaks,
  ) {
    const payload = {
      theme: selectedTheme,
      pomodoro: {
        enabled,
        weeklySchedule,
        transitionSoundEnabled,
        defaultFocusPrompt: nextFocusPrompt,
        defaultBreakPrompt: nextBreakPrompt,
        microBreaks: nextMicroBreaks,
      },
    }
    if (shouldSyncRemotely) {
      await updateGlobalSettings.mutateAsync(payload)
    }
    return payload
  }

  async function savePomodoroPromptSettings() {
    const nextFocusPrompt = normalizePomodoroPromptText(focusPromptDraft)
    const nextBreakPrompt = normalizePomodoroPromptText(breakPromptDraft)
    const { error, settings: nextMicroBreaks } = validateMicroBreakDraft(microBreakDraft)
    if (!nextMicroBreaks) {
      setMicroBreakError(error)
      showErrorFeedback("保存番茄钟设置失败", error)
      return
    }
    try {
      await persistPomodoroPromptSettings(nextFocusPrompt, nextBreakPrompt, nextMicroBreaks)
      setDefaultPrompts({ focusPrompt: nextFocusPrompt, breakPrompt: nextBreakPrompt })
      setMicroBreakSettings(nextMicroBreaks)
      setMicroBreakError("")
      showSuccessFeedback("番茄钟设置已保存", "默认提示词和随机微休息偏好已经更新。")
    } catch (err) {
      showErrorFeedback("保存番茄钟设置失败", formatApiError(err))
    }
  }

  async function resetPomodoroPromptSettings() {
    try {
      await persistPomodoroPromptSettings("", "", microBreaks)
      setDefaultPrompts({ focusPrompt: "", breakPrompt: "" })
      showInfoFeedback("默认提示词已清空", "之后新建番茄计划时提示词会保持为空。")
    } catch (err) {
      showErrorFeedback("清空默认提示词失败", formatApiError(err))
    }
  }

  async function resetMicroBreakPreferences() {
    const nextMicroBreaks = normalizeRandomMicroBreakSettings(DEFAULT_RANDOM_MICRO_BREAK_SETTINGS)
    try {
      await persistPomodoroPromptSettings(
        normalizePomodoroPromptText(focusPromptDraft),
        normalizePomodoroPromptText(breakPromptDraft),
        nextMicroBreaks,
      )
      setMicroBreakSettings(nextMicroBreaks)
      setMicroBreakDraft(toMicroBreakDraft(nextMicroBreaks))
      setMicroBreakError("")
      showInfoFeedback("随机微休息已恢复默认", "默认关闭，间隔 180-300 秒，每次闭眼休息 10 秒。")
    } catch (err) {
      showErrorFeedback("恢复随机微休息默认值失败", formatApiError(err))
    }
  }

  async function onAuthorizeRestMusicDirectory() {
    if (!canChooseRestMusicDirectory) return
    try {
      setRestMusicDirectoryAction("authorize")
      const permission = await restMusicDirectory.authorizeDirectory()
      if (permission === "granted") {
        showSuccessFeedback("休息音乐目录已绑定", "休息时可以在番茄钟页面选择并播放这个目录里的音乐。")
      } else {
        showInfoFeedback("休息音乐目录已记录", "浏览器还没有授予读取权限，需要继续授权后才能播放。")
      }
    } catch (err) {
      showErrorFeedback("绑定休息音乐目录失败", formatApiError(err))
    } finally {
      setRestMusicDirectoryAction(null)
    }
  }

  async function onRequestRestMusicDirectoryPermission() {
    if (!canRequestRestMusicDirectoryPermission) return
    try {
      setRestMusicDirectoryAction("request")
      const permission = await restMusicDirectory.requestPermission()
      if (permission === "granted") {
        showSuccessFeedback("休息音乐目录权限已恢复", "现在可以在番茄钟休息界面播放本地音乐。")
      } else {
        showInfoFeedback("休息音乐目录仍未授权", "浏览器没有放行读取权限，可以更换目录后重试。")
      }
    } catch (err) {
      showErrorFeedback("授权休息音乐目录失败", formatApiError(err))
    } finally {
      setRestMusicDirectoryAction(null)
    }
  }

  async function onClearRestMusicDirectory() {
    if (!canClearRestMusicDirectory) return
    try {
      setRestMusicDirectoryAction("clear")
      await restMusicDirectory.clearDirectory()
      showSuccessFeedback("休息音乐目录已清除", "当前浏览器不再保留这个音乐目录授权记录。")
    } catch (err) {
      showErrorFeedback("清除休息音乐目录失败", formatApiError(err))
    } finally {
      setRestMusicDirectoryAction(null)
    }
  }

  async function handlePomodoroWallpaperChange(event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget
    const file = input.files?.[0] ?? null
    input.value = ""
    if (!file) return
    if (!file.type.startsWith("image/")) {
      showErrorFeedback("设置壁纸失败", "请选择图片文件。")
      return
    }
    if (file.size > POMODORO_WALLPAPER_MAX_BYTES) {
      showErrorFeedback("设置壁纸失败", "请选择 12 MB 以内的图片。")
      return
    }
    try {
      await savePomodoroWallpaperBlob(file)
      replacePomodoroWallpaperPreview(file)
      showSuccessFeedback("壁纸已更新", "只保存在当前浏览器，不会上传服务器，也不会影响其他页面。")
    } catch (err) {
      showErrorFeedback("设置壁纸失败", formatApiError(err))
    }
  }

  async function handleRemovePomodoroWallpaper() {
    try {
      await removePomodoroWallpaperBlob()
      replacePomodoroWallpaperPreview(null)
      showInfoFeedback("壁纸已移除", "番茄钟页已恢复默认背景。")
    } catch (err) {
      showErrorFeedback("移除壁纸失败", formatApiError(err))
    }
  }

  if (pomodoroMemberBlocked) {
    return (
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
        <Button variant="ghost" asChild className="self-start px-0">
          <Link to={buildPomodoroPath()}>
            <ArrowLeft className="h-4 w-4" />
            返回番茄钟
          </Link>
        </Button>
        <MemberOnlyFeatureNotice
          title="番茄钟设置是会员专属功能"
          message="当前账号还没有有效会员，所以默认提示词、随机微休息、休息音乐目录和壁纸设置先不开放。"
        />
      </div>
    )
  }

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <section className="space-y-4">
        <Button variant="ghost" asChild className="px-0">
          <Link to={buildPomodoroPath()}>
            <ArrowLeft className="h-4 w-4" />
            返回番茄钟
          </Link>
        </Button>
        <div>
          <div className="text-sm font-medium text-muted-foreground">番茄钟设置</div>
          <h1 className="mt-1 text-2xl font-semibold tracking-[-0.03em] text-foreground">默认提示词</h1>
        </div>
      </section>

      <section className="space-y-5 border-t border-border/60 pt-6">
        <div className="space-y-4 border-b border-border/60 pb-6">
          <div>
            <h2 className="text-lg font-semibold text-foreground">本地资源</h2>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">
              管理只保存在当前浏览器里的休息音乐目录和番茄钟页壁纸。
            </p>
          </div>

          <div className="rounded-xl border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] p-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Music2 className="h-4 w-4 text-[color:var(--theme-soft-text-strong)]" />
                  <span className="text-sm font-semibold text-foreground">休息音乐目录</span>
                  <span
                    className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${describeLocalDirectoryPermissionTone(restMusicDirectory.permission)}`}
                  >
                    {describeLocalDirectoryPermission(restMusicDirectory.permission)}
                  </span>
                </div>
                <div className="mt-2 break-all text-sm text-muted-foreground">
                  {restMusicDirectory.handleName || "还没有绑定本地音乐目录。"}
                </div>
                <div className="mt-1 text-xs leading-6 text-[color:var(--theme-subtle-text)]">
                  这个目录属于本地浏览器授权，音乐文件不会上传到服务端。
                </div>
                {restMusicDirectory.error ? (
                  <div className="mt-2 text-sm text-destructive">{restMusicDirectory.error}</div>
                ) : null}
              </div>
              <div className="flex flex-wrap gap-2">
                {restMusicDirectory.permission === "granted" ? (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => void onAuthorizeRestMusicDirectory()}
                    disabled={!canChooseRestMusicDirectory}
                  >
                    <FolderOpen className="h-4 w-4" />
                    更换音乐目录
                  </Button>
                ) : null}
                {(restMusicDirectory.permission === "missing" || restMusicDirectory.permission === "unsupported") ? (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => void onAuthorizeRestMusicDirectory()}
                    disabled={!canChooseRestMusicDirectory}
                  >
                    <FolderOpen className="h-4 w-4" />
                    {restMusicDirectoryAction === "authorize" ? "打开目录选择器..." : "选择音乐目录"}
                  </Button>
                ) : null}
                {(restMusicDirectory.permission === "prompt" || restMusicDirectory.permission === "denied") ? (
                  <>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => void onRequestRestMusicDirectoryPermission()}
                      disabled={!canRequestRestMusicDirectoryPermission}
                    >
                      <FolderOpen className="h-4 w-4" />
                      {restMusicDirectoryAction === "request" ? "请求中..." : "继续授权"}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => void onAuthorizeRestMusicDirectory()}
                      disabled={!canChooseRestMusicDirectory}
                    >
                      <FolderOpen className="h-4 w-4" />
                      {restMusicDirectoryAction === "authorize" ? "打开目录选择器..." : "更换音乐目录"}
                    </Button>
                  </>
                ) : null}
                {restMusicDirectory.permission !== "missing" && restMusicDirectory.permission !== "unsupported" ? (
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => void onClearRestMusicDirectory()}
                    disabled={!canClearRestMusicDirectory}
                  >
                    <Trash2 className="h-4 w-4" />
                    {restMusicDirectoryAction === "clear" ? "清除中..." : "清除音乐目录"}
                  </Button>
                ) : null}
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] p-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <ImagePlus className="h-4 w-4 text-[color:var(--theme-soft-text-strong)]" />
                  <span className="text-sm font-semibold text-foreground">番茄钟壁纸</span>
                  <span className="theme-pill-default inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold">
                    {wallpaperUrl ? "已设置" : "未设置"}
                  </span>
                </div>
                <div className="mt-2 text-sm leading-6 text-muted-foreground">
                  壁纸只保存在当前浏览器，不会上传服务器，也不会影响其他页面。
                </div>
                {wallpaperUrl ? (
                  <div
                    className="mt-3 h-24 w-full max-w-xs rounded-xl border border-[color:var(--theme-soft-border)] bg-cover bg-center"
                    style={{ backgroundImage: `url(${wallpaperUrl})` }}
                    aria-label="当前番茄钟壁纸预览"
                  />
                ) : null}
              </div>
              <div className="flex flex-wrap gap-2">
                <input
                  ref={wallpaperInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={(event) => void handlePomodoroWallpaperChange(event)}
                />
                <Button type="button" variant="outline" onClick={() => wallpaperInputRef.current?.click()}>
                  <ImagePlus className="h-4 w-4" />
                  {wallpaperUrl ? "更换壁纸" : "设置壁纸"}
                </Button>
                {wallpaperUrl ? (
                  <Button type="button" variant="ghost" onClick={() => void handleRemovePomodoroWallpaper()}>
                    <ImageOff className="h-4 w-4" />
                    移除壁纸
                  </Button>
                ) : null}
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-4 border-b border-border/60 pb-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-foreground">随机微休息</h2>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                只在番茄钟学习阶段的视频全屏中生效，默认关闭。
              </p>
            </div>
            <label className="inline-flex min-h-10 cursor-pointer items-center gap-2 rounded-lg border border-[color:var(--theme-soft-border)] px-3 py-2 text-sm font-medium">
              <input
                id="pomodoro-micro-break-enabled"
                type="checkbox"
                checked={microBreakDraft.enabled}
                onChange={(event) =>
                  setMicroBreakDraft((prev) => ({
                    ...prev,
                    enabled: event.target.checked,
                  }))
                }
              />
              启用
            </label>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="pomodoro-micro-break-min-interval">最短间隔（秒）</Label>
              <input
                id="pomodoro-micro-break-min-interval"
                type="number"
                min={30}
                max={3600}
                value={microBreakDraft.minIntervalSeconds}
                onChange={(event) =>
                  setMicroBreakDraft((prev) => ({
                    ...prev,
                    minIntervalSeconds: event.target.value,
                  }))
                }
                className="h-10 w-full rounded-lg border border-[color:var(--theme-soft-border)] bg-background px-3 text-sm text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/15"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pomodoro-micro-break-max-interval">最长间隔（秒）</Label>
              <input
                id="pomodoro-micro-break-max-interval"
                type="number"
                min={30}
                max={3600}
                value={microBreakDraft.maxIntervalSeconds}
                onChange={(event) =>
                  setMicroBreakDraft((prev) => ({
                    ...prev,
                    maxIntervalSeconds: event.target.value,
                  }))
                }
                className="h-10 w-full rounded-lg border border-[color:var(--theme-soft-border)] bg-background px-3 text-sm text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/15"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pomodoro-micro-break-duration">闭眼休息（秒）</Label>
              <input
                id="pomodoro-micro-break-duration"
                type="number"
                min={5}
                max={300}
                value={microBreakDraft.durationSeconds}
                onChange={(event) =>
                  setMicroBreakDraft((prev) => ({
                    ...prev,
                    durationSeconds: event.target.value,
                  }))
                }
                className="h-10 w-full rounded-lg border border-[color:var(--theme-soft-border)] bg-background px-3 text-sm text-foreground outline-none focus:border-primary focus:ring-2 focus:ring-primary/15"
              />
            </div>
          </div>

          {microBreakError ? <div className="text-sm text-destructive">{microBreakError}</div> : null}

          <Button
            type="button"
            variant="outline"
            onClick={() => void resetMicroBreakPreferences()}
            disabled={updateGlobalSettings.isPending}
          >
            <RotateCcw className="h-4 w-4" />
            恢复微休息默认值
          </Button>
        </div>

        <div className="space-y-2">
          <Label htmlFor="pomodoro-default-focus-prompt">默认学习提示词</Label>
          <textarea
            id="pomodoro-default-focus-prompt"
            value={focusPromptDraft}
            maxLength={200}
            onChange={(event) => setFocusPromptDraft(event.target.value)}
            className="min-h-[112px] w-full resize-y rounded-lg border border-[color:var(--theme-soft-border)] bg-background px-3 py-2 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/15"
            placeholder="例如：10 秒后开始学习，请准备进入专注。"
          />
          <div className="text-xs text-muted-foreground">{focusPromptDraft.length}/200</div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="pomodoro-default-break-prompt">默认休息提示词</Label>
          <textarea
            id="pomodoro-default-break-prompt"
            value={breakPromptDraft}
            maxLength={200}
            onChange={(event) => setBreakPromptDraft(event.target.value)}
            className="min-h-[112px] w-full resize-y rounded-lg border border-[color:var(--theme-soft-border)] bg-background px-3 py-2 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/15"
            placeholder="例如：10 秒后进入休息，离开屏幕放松一下。"
          />
          <div className="text-xs text-muted-foreground">{breakPromptDraft.length}/200</div>
        </div>

        <div className="flex flex-wrap gap-3">
          <Button type="button" onClick={() => void savePomodoroPromptSettings()} disabled={updateGlobalSettings.isPending}>
            <Save className="h-4 w-4" />
            保存设置
          </Button>
          <Button type="button" variant="outline" onClick={() => void resetPomodoroPromptSettings()} disabled={updateGlobalSettings.isPending}>
            <RotateCcw className="h-4 w-4" />
            清空默认值
          </Button>
        </div>
      </section>
    </div>
  )
}

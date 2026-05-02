import { useEffect, useMemo, useState, type CSSProperties } from "react"
import type { CloudAccount } from "@/ui/api/cloudAccounts"
import { Clock3, Cloud, FolderOpen, Link2Off, Music2, Palette, RefreshCw, RotateCcw, Save, Settings2, TimerReset, Trash2 } from "lucide-react"
import { Link } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import type { ReviewChainTemplateItem } from "@/ui/api/projectConfig"
import { ContentNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useCurrentUser } from "@/ui/queries/auth"
import { useBaiduNetdiskCloudAccounts, useBeginBaiduNetdiskConnect, useDisconnectBaiduNetdiskAccount } from "@/ui/queries/cloudAccounts"
import { useUpdateMyGlobalSettings } from "@/ui/queries/profile"
import { useSystemCapabilities } from "@/ui/queries/system"
import { usePageMeta } from "@/ui/seo/usePageMeta"
import { type DirectoryBindingPermission, usePomodoroRestMusicDirectoryBinding } from "@/ui/localMedia/projectDirectory"
import {
  DEFAULT_PROJECT_REVIEW_TEMPLATE,
  cloneReviewChainTemplate,
  useGlobalConfigStore,
} from "@/ui/store/globalConfigStore"
import { showErrorFeedback, showInfoFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import {
  describePomodoroPhase,
  formatPomodoroCountdown,
  getPomodoroSnapshot,
  usePomodoroNow,
  usePomodoroStore,
} from "@/ui/store/pomodoroStore"
import { useThemeStore } from "@/ui/store/themeStore"
import { THEME_PRESETS } from "@/ui/theme/themePresets"
import { buildPomodoroPath } from "@/views/pomodoro/pomodoroRouting"
import { buildGlobalSettingsPath } from "@/views/settings/globalSettingsRouting"

type TemplateEditorItem = {
  id: number
  kind: "CONVERGENCE" | "REVIEW_TASK"
  count: string
}

let nextTemplateItemId = 1

const THEME_PRESET_ACTIVE_BORDER = "#b7a4f6"
const THEME_PRESET_ACTIVE_RING = "0 0 0 1px rgba(183, 164, 246, 0.96)"
const THEME_PRESET_ACTIVE_GLOW = "0 22px 40px -28px rgba(111, 90, 204, 0.54)"
const THEME_PRESET_CURRENT_BADGE_BG = "linear-gradient(135deg, #4b68d8 0%, #2f50b9 100%)"
const THEME_PRESET_CURRENT_BADGE_SHADOW = "0 14px 28px -22px rgba(47, 80, 185, 0.7)"

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
  if (permission === "granted") return "border-emerald-200 bg-emerald-50 text-emerald-700"
  if (permission === "prompt") return "border-amber-200 bg-amber-50 text-amber-700"
  if (permission === "denied") return "border-rose-200 bg-rose-50 text-rose-700"
  return "border-slate-200 bg-slate-50 text-slate-600"
}

function createTemplateEditorItem(kind: "CONVERGENCE" | "REVIEW_TASK", count = 1): TemplateEditorItem {
  return { id: nextTemplateItemId++, kind, count: String(count) }
}

function toTemplateEditorItems(items: ReviewChainTemplateItem[]) {
  return items.map((item) => createTemplateEditorItem(item.kind, item.count ?? 1))
}

function formatAccountExpiresAt(value: string | null | undefined) {
  if (!value) return "未返回到期时间"
  const dt = new Date(value)
  return Number.isNaN(dt.getTime()) ? value : dt.toLocaleString()
}

function waitForBaiduNetdiskConnectPopup(popup: Window | null): Promise<CloudAccount> {
  if (!popup) {
    return Promise.reject(new Error("浏览器拦截了授权弹窗，请允许弹窗后重试"))
  }
  return new Promise((resolve, reject) => {
    let settled = false
    const timerId = window.setInterval(() => {
      if (!popup.closed) return
      if (settled) return
      settled = true
      window.clearInterval(timerId)
      window.removeEventListener("message", onMessage)
      reject(new Error("授权窗口已关闭，绑定没有完成"))
    }, 400)

    function cleanup() {
      window.clearInterval(timerId)
      window.removeEventListener("message", onMessage)
    }

    function onMessage(event: MessageEvent) {
      const data = event.data
      if (!data || typeof data !== "object") return
      const payload = data as { type?: unknown; ok?: unknown; message?: unknown; account?: unknown }
      if (payload.type !== "plm:baidu-netdisk-connect") return
      if (settled) return
      settled = true
      cleanup()
      if (payload.ok !== true) {
        reject(new Error(typeof payload.message === "string" && payload.message.trim() ? payload.message : "百度网盘授权失败"))
        return
      }
      resolve(payload.account as CloudAccount)
    }

    window.addEventListener("message", onMessage)
  })
}

function PhaseBadge(props: {
  enabled: boolean
  status: "idle" | "running" | "completed"
  phase: "focus" | "break" | null
  idleReason: "disabled" | "not_configured" | "waiting" | "day_off" | null
  hasEnabledSchedule: boolean
}) {
  const label = describePomodoroPhase(
    props.phase,
    props.status,
    props.idleReason,
    props.enabled,
    props.hasEnabledSchedule,
  )
  const className =
    props.status === "completed"
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : props.phase === "focus"
        ? "border-primary/15 bg-[hsl(var(--primary)/0.08)] text-primary"
        : props.phase === "break"
          ? "border-amber-200 bg-amber-50 text-amber-800"
          : "border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] text-[color:var(--theme-subtle-text)]"
  return <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium ${className}`}>{label}</span>
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

export function GlobalSettingsPage() {
  const selectedTheme = useThemeStore((state) => state.theme)
  const setTheme = useThemeStore((state) => state.setTheme)
  const enabled = usePomodoroStore((state) => state.enabled)
  const weeklySchedule = usePomodoroStore((state) => state.weeklySchedule)
  const transitionSoundEnabled = usePomodoroStore((state) => state.transitionSoundEnabled)
  const defaultProjectReviewTemplate = useGlobalConfigStore((state) => state.defaultProjectReviewTemplate)
  const setDefaultProjectReviewTemplate = useGlobalConfigStore((state) => state.setDefaultProjectReviewTemplate)
  const resetDefaultProjectReviewTemplate = useGlobalConfigStore((state) => state.resetDefaultProjectReviewTemplate)
  const now = usePomodoroNow(enabled)
  const snapshot = useMemo(() => getPomodoroSnapshot({ enabled, weeklySchedule }, now), [enabled, now, weeklySchedule])
  const [templateItems, setTemplateItems] = useState<TemplateEditorItem[]>(() => toTemplateEditorItems(defaultProjectReviewTemplate))
  const [templateError, setTemplateError] = useState<string | null>(null)
  const [pendingTemplateKind, setPendingTemplateKind] = useState<"" | "CONVERGENCE" | "REVIEW_TASK">("")

  usePageMeta({
    title: "全局配置 | LearningPyramid",
    description: "统一管理界面主题和新建项目默认复习模板。番茄钟已经独立成固定功能页。",
    path: buildGlobalSettingsPath(),
  })

  const capabilitiesQ = useSystemCapabilities()
  const authEnabled = capabilitiesQ.data?.authEnabled ?? false
  const baiduNetdiskEnabled = capabilitiesQ.data?.baiduNetdiskEnabled ?? false
  const currentUserQ = useCurrentUser(authEnabled)
  const updateGlobalSettings = useUpdateMyGlobalSettings()
  const beginBaiduNetdiskConnect = useBeginBaiduNetdiskConnect()
  const disconnectBaiduNetdiskAccount = useDisconnectBaiduNetdiskAccount()
  const baiduAccountsQ = useBaiduNetdiskCloudAccounts(Boolean(currentUserQ.data) && baiduNetdiskEnabled)
  const baiduAccounts = baiduAccountsQ.data ?? []
  const shouldSyncRemotely = authEnabled && Boolean(currentUserQ.data?.userId)
  const restMusicDirectory = usePomodoroRestMusicDirectoryBinding()
  const [restMusicDirectoryAction, setRestMusicDirectoryAction] = useState<"authorize" | "request" | "clear" | null>(null)
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

  useEffect(() => {
    setTemplateItems(toTemplateEditorItems(defaultProjectReviewTemplate))
    setTemplateError(null)
  }, [defaultProjectReviewTemplate])

  async function persistGlobalSettings(overrides?: {
    theme?: string
    defaultProjectReviewTemplate?: ReviewChainTemplateItem[]
  }) {
    const payload = {
      theme: overrides?.theme ?? selectedTheme,
      pomodoro: {
        enabled,
        weeklySchedule,
        transitionSoundEnabled,
      },
      defaultProjectReviewTemplate: overrides?.defaultProjectReviewTemplate ?? defaultProjectReviewTemplate,
    }
    if (shouldSyncRemotely) {
      await updateGlobalSettings.mutateAsync(payload)
    }
    return payload
  }

  function buildTemplateDraft() {
    const items: ReviewChainTemplateItem[] = []
    let hasConvergence = false
    for (const item of templateItems) {
      if (item.kind === "CONVERGENCE") {
        items.push({ kind: "CONVERGENCE" })
        hasConvergence = true
        continue
      }
      const count = Number(item.count)
      if (!Number.isInteger(count) || count < 1) {
        setTemplateError("复习任务次数必须是大于等于 1 的整数")
        return null
      }
      items.push(count === 1 ? { kind: "REVIEW_TASK" } : { kind: "REVIEW_TASK", count })
    }
    if (items.length === 0) {
      setTemplateError("默认模板不能为空")
      return null
    }
    if (!hasConvergence) {
      setTemplateError("模板里至少需要一个收敛步骤")
      return null
    }
    return items
  }

  async function handleResetTemplate() {
    const defaultTemplate = cloneReviewChainTemplate(DEFAULT_PROJECT_REVIEW_TEMPLATE)
    try {
      await persistGlobalSettings({ defaultProjectReviewTemplate: defaultTemplate })
      resetDefaultProjectReviewTemplate()
      showInfoFeedback("默认模板已恢复", "新建项目会重新使用系统默认的单步收敛模板。")
    } catch (err) {
      showErrorFeedback("恢复默认模板失败", formatApiError(err))
    }
  }

  function appendTemplateItem() {
    if (!pendingTemplateKind) return
    setTemplateItems((prev) => [...prev, createTemplateEditorItem(pendingTemplateKind)])
    setPendingTemplateKind("")
    if (templateError) setTemplateError(null)
  }

  async function saveDefaultReviewTemplate() {
    setTemplateError(null)
    const items = buildTemplateDraft()
    if (!items) return
    try {
      await persistGlobalSettings({ defaultProjectReviewTemplate: items })
      setDefaultProjectReviewTemplate(items)
      showSuccessFeedback("默认复习模板已保存", "之后新建的项目会自动套用这套模板，已有项目不会被强制改写。")
    } catch (err) {
      showErrorFeedback("保存默认复习模板失败", formatApiError(err))
    }
  }

  const templateSummary =
    templateItems.length === 0
      ? "还没有步骤"
      : templateItems
          .map((item) => (item.kind === "CONVERGENCE" ? "收敛" : `复习任务${Number(item.count || 1) > 1 ? `×${item.count}` : ""}`))
          .join(" -> ")

  const pomodoroSummary =
    snapshot.status === "running"
      ? snapshot.phase === "focus"
        ? "学习中"
        : "休息中"
      : snapshot.status === "completed"
        ? "今日已完成"
        : snapshot.idleReason === "waiting"
          ? "等待开始"
          : snapshot.idleReason === "day_off"
            ? "今日未排程"
            : enabled
              ? "待配置"
              : "已关闭"
  const enabledIntegrationCount = baiduNetdiskEnabled ? 1 : 0
  const baiduIntegrationStatusLabel = !baiduNetdiskEnabled ? "未启用" : baiduAccounts.length > 0 ? "已连接" : "待连接"
  const baiduIntegrationStatusClass = !baiduNetdiskEnabled
    ? "border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] text-[color:var(--theme-subtle-text)]"
    : baiduAccounts.length > 0
      ? "border-emerald-200 bg-emerald-50 text-emerald-800"
      : "border-primary/15 bg-[hsl(var(--primary)/0.08)] text-primary"

  async function onConnectBaiduNetdisk() {
    const popup = window.open("", "plm-baidu-netdisk-connect", "popup=yes,width=720,height=820")
    if (!popup) {
      showErrorFeedback("无法打开授权窗口", "浏览器拦截了弹窗，请允许当前站点打开弹窗后重试。")
      return
    }
    try {
      const result = await beginBaiduNetdiskConnect.mutateAsync()
      popup.location.href = result.authorizeUrl
      const account = await waitForBaiduNetdiskConnectPopup(popup)
      await baiduAccountsQ.refetch()
      showSuccessFeedback("百度网盘已连接", `账号“${account.displayName}”已经绑定完成，现在可以去项目设置里导入视频。`)
    } catch (err) {
      popup.close()
      showErrorFeedback("连接百度网盘失败", formatApiError(err))
    }
  }

  async function onDisconnectCloudAccount(account: CloudAccount) {
    try {
      await disconnectBaiduNetdiskAccount.mutateAsync(account.accountId)
      await baiduAccountsQ.refetch()
      showSuccessFeedback("百度网盘已断开", `账号“${account.displayName}”已经从当前用户解绑。`)
    } catch (err) {
      showErrorFeedback("断开百度网盘失败", formatApiError(err))
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

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
      <section className="grid gap-6 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
        <Card className="theme-card-main overflow-hidden">
          <CardHeader className="theme-card-header">
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-[1.1rem] border [border-color:var(--theme-icon-border)] [background:var(--theme-icon-bg)] [color:var(--theme-icon-text)]">
                <Settings2 className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <CardTitle>全局配置</CardTitle>
                <CardDescription className="mt-1">这里保留真正的全局偏好：界面主题和新建项目默认复习模板。番茄钟已经独立到固定功能页。</CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 pt-5">
            <ContentNotice
              title="这一层级和项目设置不同"
              message="全局配置影响整个工作空间或未来新建项目；项目设置只影响当前项目。两者不会互相覆盖。"
              icon={Settings2}
              tone="info"
            />
            <div className="grid gap-4 md:grid-cols-3">
              <MetricTile label="当前主题" value={THEME_PRESETS.find((theme) => theme.id === selectedTheme)?.label ?? "雾蓝"} hint="会立即影响整个界面。" />
              <MetricTile label="番茄钟" value={pomodoroSummary} hint="排程、铃声和状态查看都已迁到顶栏里的番茄钟页面。" />
              <MetricTile label="默认复习模板" value={`${templateItems.length} 个步骤`} hint="只影响之后新建的项目。" />
            </div>
          </CardContent>
        </Card>

        <Card className="theme-card-main">
          <CardHeader className="theme-card-header">
            <CardTitle>番茄钟入口</CardTitle>
            <CardDescription>番茄钟现在是固定功能页，不再在这里编辑排程和铃声。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 pt-5">
            <div className="rounded-[1.25rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] p-4">
              <div className="flex flex-wrap items-center gap-3">
                <PhaseBadge
                  enabled={snapshot.enabled}
                  status={snapshot.status}
                  phase={snapshot.phase}
                  idleReason={snapshot.idleReason}
                  hasEnabledSchedule={snapshot.hasEnabledSchedule}
                />
                <span className="text-sm text-muted-foreground">
                  {snapshot.status === "running"
                    ? formatPomodoroCountdown(snapshot.segmentRemainingMs)
                    : snapshot.idleReason === "waiting"
                      ? formatPomodoroCountdown(snapshot.untilStartMs)
                      : "按排程自动运行"}
                </span>
              </div>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                {!enabled
                  ? "番茄钟当前关闭，工作台不会被限制。"
                  : !snapshot.hasEnabledSchedule
                    ? "番茄钟已开启，但还没有启用任何日期排程。"
                    : snapshot.status === "running"
                      ? snapshot.phase === "focus"
                        ? "当前是学习时段，任意项目工作台都可以进入。"
                        : "当前是间歇时段，任意项目工作台都会被统一拦回番茄钟页。"
                      : snapshot.status === "completed"
                        ? `今天的番茄计划已经结束，下次会在 ${formatDateTime(snapshot.nextStartAtMs)} 自动开始。`
                        : snapshot.idleReason === "waiting"
                          ? `今天会在 ${snapshot.startTime} 自动开始。`
                          : "今天没有排程，工作台会整天保持锁定。"}
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <MetricTile label="阶段切换铃声" value={transitionSoundEnabled ? "已开启" : "已关闭"} hint="切换提示音的开关也已经迁到番茄钟页。" />
              <MetricTile label="下次自动开始" value={formatDateTime(snapshot.nextStartAtMs)} hint="按当前设备本地时间解释。" />
            </div>
            <div className="rounded-[1.25rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] p-4">
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
                    这个目录授权只保存在当前浏览器里，音乐文件不会上传到服务端。
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
            <Button asChild variant="outline">
              <Link to={buildPomodoroPath()}>
                <TimerReset className="h-4 w-4" />
                打开番茄钟页面
              </Link>
            </Button>
          </CardContent>
        </Card>
      </section>

      <Card className="theme-card-main overflow-hidden">
        <CardHeader className="theme-card-header">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl border [border-color:var(--theme-icon-border)] [background:var(--theme-icon-bg)] [color:var(--theme-icon-text)]">
              <Cloud className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <CardTitle>系统接入中心</CardTitle>
              <CardDescription className="mt-1">系统级第三方资源接入统一收口在这里。完成绑定后，就可以在项目设置里直接使用这些外部资源能力。</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 pt-5">
          <ContentNotice
            title="这类接入属于全局能力"
            message="云盘授权不属于个人资料展示，而是整个工作空间可复用的资源接入能力，所以统一收在全局设置里。"
            icon={Cloud}
            tone="info"
          />

          <div className="grid gap-3 md:grid-cols-3">
            <MetricTile label="已启用接入" value={`${enabledIntegrationCount}/1`} hint="当前系统只接入了百度网盘。" />
            <MetricTile label="已绑定账号" value={`${baiduAccounts.length}`} hint="这里只统计当前账号可直接使用的绑定结果。" />
            <MetricTile label="百度网盘状态" value={baiduIntegrationStatusLabel} hint="连接完成后，就能在项目设置里导入视频。" />
          </div>

          <div className="rounded-[1.25rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] p-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <div className="text-xs uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">接入模块</div>
                  <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium ${baiduIntegrationStatusClass}`}>
                    {baiduIntegrationStatusLabel}
                  </span>
                </div>
                <div className="mt-2 text-base font-semibold text-foreground">百度网盘</div>
                <div className="mt-1 text-sm leading-6 text-muted-foreground">
                  把自己的百度网盘绑定到当前账号后，就可以在项目设置里直接浏览目录并导入视频。
                </div>
                <div className="mt-2 text-xs leading-6 text-[color:var(--theme-subtle-text)]">
                  使用位置：项目设置里的“百度网盘视频”导入入口。
                </div>
              </div>
              {baiduNetdiskEnabled ? (
                <Button type="button" variant="outline" className="shrink-0" onClick={() => void onConnectBaiduNetdisk()} disabled={beginBaiduNetdiskConnect.isPending}>
                  {beginBaiduNetdiskConnect.isPending ? (
                    <>
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      连接中...
                    </>
                  ) : (
                    <>
                      <Cloud className="h-4 w-4" />
                      连接百度网盘
                    </>
                  )}
                </Button>
              ) : (
                <span className="theme-meta shrink-0">当前部署未启用</span>
              )}
            </div>
          </div>

          {!baiduNetdiskEnabled ? (
            <div className="rounded-[1.2rem] border border-dashed border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-4 text-sm text-[color:var(--theme-subtle-text)]">
              当前部署还没有开启百度网盘接入能力。
            </div>
          ) : baiduAccountsQ.isLoading ? (
            <div className="rounded-[1.2rem] border border-dashed border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-4 text-sm text-[color:var(--theme-subtle-text)]">
              正在加载已绑定的百度网盘账号。
            </div>
          ) : baiduAccountsQ.error ? (
            <div className="theme-warm-surface rounded-[1.2rem] px-4 py-4 text-sm leading-6">
              百度网盘账号加载失败：{formatApiError(baiduAccountsQ.error)}
            </div>
          ) : baiduAccounts.length <= 0 ? (
            <div className="rounded-[1.2rem] border border-dashed border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-4 text-sm text-[color:var(--theme-subtle-text)]">
              还没有绑定百度网盘账号。完成连接后，这里会显示账号信息和授权状态。
            </div>
          ) : (
            <div className="space-y-3">
              {baiduAccounts.map((account) => (
                <div key={account.accountId} className="rounded-[1.2rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] px-4 py-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-foreground">{account.displayName}</div>
                      <div className="mt-1 text-xs text-[color:var(--theme-subtle-text)]">百度用户 ID：{account.providerUserId}</div>
                      <div className="mt-1 text-xs text-[color:var(--theme-subtle-text)]">授权到期：{formatAccountExpiresAt(account.expiresAt)}</div>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      className="shrink-0 text-muted-foreground"
                      onClick={() => void onDisconnectCloudAccount(account)}
                      disabled={disconnectBaiduNetdiskAccount.isPending}
                    >
                      <Link2Off className="h-4 w-4" />
                      断开
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="theme-card-main overflow-hidden">
        <CardHeader className="theme-card-header">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl border [border-color:var(--theme-icon-border)] [background:var(--theme-icon-bg)] [color:var(--theme-icon-text)]">
              <Palette className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <CardTitle>界面主题</CardTitle>
              <CardDescription className="mt-1">原本右上角的主题选择已经迁到这里。番茄钟则已经独立成固定功能页。</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="grid gap-3 pt-5 md:grid-cols-3">
          {THEME_PRESETS.map((theme) => {
            const isActive = selectedTheme === theme.id
            const previewCardStyle: CSSProperties = {
              background: theme.surface.background,
              borderColor: isActive ? THEME_PRESET_ACTIVE_BORDER : theme.surface.border,
              boxShadow: isActive ? `${THEME_PRESET_ACTIVE_RING}, ${THEME_PRESET_ACTIVE_GLOW}, ${theme.surface.shadow}` : theme.surface.shadow,
            }
            return (
              <button
                key={theme.id}
                type="button"
                className="flex w-full items-center justify-between gap-3 rounded-[1.4rem] border px-4 py-4 text-left transition-all duration-200 hover:-translate-y-px focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#b7a4f6]/70 focus-visible:ring-offset-2 focus-visible:ring-offset-transparent"
                style={previewCardStyle}
                disabled={updateGlobalSettings.isPending}
                onClick={async () => {
                  try {
                    await persistGlobalSettings({ theme: theme.id })
                    setTheme(theme.id)
                    showSuccessFeedback("主题已切换", `界面当前已切换为“${theme.label}”。`)
                  } catch (err) {
                    showErrorFeedback("切换主题失败", formatApiError(err))
                  }
                }}
              >
                <div className="min-w-0">
                  <div className="text-sm font-medium" style={{ color: theme.surface.title }}>{theme.label}</div>
                  <div className="mt-0.5 text-xs" style={{ color: theme.surface.description }}>{theme.description}</div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <div className="flex items-center gap-1.5">
                    {theme.preview.map((color) => (
                      <span key={`${theme.id}-${color}`} className="h-4 w-4 rounded-full shadow-inner" style={{ backgroundColor: color, border: `1px solid ${theme.surface.swatchBorder}` }} />
                    ))}
                  </div>
                  {isActive ? (
                    <span
                      className="inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold text-white"
                      style={{ borderColor: "rgba(255, 255, 255, 0.22)", background: THEME_PRESET_CURRENT_BADGE_BG, boxShadow: THEME_PRESET_CURRENT_BADGE_SHADOW }}
                    >
                      当前
                    </span>
                  ) : null}
                </div>
              </button>
            )
          })}
        </CardContent>
      </Card>

      <Card className="theme-card-main overflow-hidden">
        <CardHeader className="theme-card-header">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl border [border-color:var(--theme-icon-border)] [background:var(--theme-icon-bg)] [color:var(--theme-icon-text)]">
              <Clock3 className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <CardTitle>新建项目默认复习模板</CardTitle>
              <CardDescription className="mt-1">这里定义之后新建项目的默认模板。已有项目还是在项目设置里单独维护自己的层配置。</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 pt-5">
          <ContentNotice
            title="只作用于未来新项目"
            message="保存后，只会影响接下来新建的项目；已经存在的项目不会被强行覆盖。要修改现有项目，请进入对应项目设置。"
            icon={Clock3}
            tone="info"
          />

          <div className="rounded-[1.2rem] border border-border/70 bg-muted/15 p-4">
            <div className="text-sm font-medium text-foreground">当前模板摘要</div>
            <div className="mt-2 text-sm leading-6 text-muted-foreground">{templateSummary}</div>
          </div>

          <div className="overflow-hidden rounded-[1.1rem] border border-border/70 bg-background/90">
            {templateItems.length === 0 ? <div className="px-4 py-6 text-sm text-muted-foreground">还没有模板步骤，请在下方选择步骤类型后点击加号。</div> : null}

            {templateItems.map((item, index) => (
              <div key={item.id} className="border-t border-border/70 p-4 first:border-t-0">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <div className="flex items-start gap-3">
                    <span className="inline-flex items-center rounded-full border border-[#d8e3ee] bg-[#f6f9fc] px-2.5 py-1 text-xs font-semibold text-[#5f7790]">第 {index + 1} 步</span>
                    <div className="space-y-1">
                      <div className="text-sm font-medium text-foreground">{item.kind === "CONVERGENCE" ? "收敛" : "复习任务"}</div>
                      <div className="text-xs text-muted-foreground">{item.kind === "CONVERGENCE" ? "完成一轮后决定是否继续生成复习任务。" : "在当前范围上直接生成待执行复习任务。"}</div>
                    </div>
                  </div>

                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
                    {item.kind === "REVIEW_TASK" ? (
                      <div className="w-full max-w-[220px] space-y-2">
                        <Label htmlFor={`global-template-count-${item.id}`}>次数</Label>
                        <Input
                          id={`global-template-count-${item.id}`}
                          inputMode="numeric"
                          value={item.count}
                          onChange={(event) =>
                            setTemplateItems((prev) =>
                              prev.map((current) => (current.id === item.id ? { ...current, count: event.target.value } : current)),
                            )
                          }
                        />
                      </div>
                    ) : (
                      <div className="rounded-full border border-border/60 bg-muted/20 px-3 py-1.5 text-xs text-muted-foreground">这个步骤没有额外参数</div>
                    )}

                    <Button type="button" variant="ghost" size="sm" onClick={() => setTemplateItems((prev) => prev.filter((current) => current.id !== item.id))}>
                      删除
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Button type="button" variant="outline" size="icon" className="shrink-0" onClick={appendTemplateItem} disabled={!pendingTemplateKind} aria-label="追加模板步骤">
              <span className="text-lg leading-none">+</span>
            </Button>
            <div className="w-full sm:max-w-[220px]">
              <Label htmlFor="pendingGlobalTemplateKind" className="sr-only">选择步骤类型</Label>
              <select
                id="pendingGlobalTemplateKind"
                aria-label="选择步骤类型"
                className="h-10 w-full rounded-xl border bg-background px-4 text-sm"
                value={pendingTemplateKind}
                onChange={(event) => setPendingTemplateKind(event.target.value as "" | "CONVERGENCE" | "REVIEW_TASK")}
              >
                <option value="">选择类型</option>
                <option value="CONVERGENCE">收敛</option>
                <option value="REVIEW_TASK">复习任务</option>
              </select>
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <Button onClick={saveDefaultReviewTemplate} disabled={updateGlobalSettings.isPending}>
              <Save className="h-4 w-4" />
              保存默认模板
            </Button>
            <Button variant="outline" onClick={handleResetTemplate} disabled={updateGlobalSettings.isPending}>
              <RotateCcw className="h-4 w-4" />
              恢复系统默认
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setTemplateItems(toTemplateEditorItems(cloneReviewChainTemplate(DEFAULT_PROJECT_REVIEW_TEMPLATE)))
                setTemplateError(null)
              }}
            >
              预览系统默认
            </Button>
          </div>

          {templateError ? <p className="text-sm text-destructive">{templateError}</p> : null}
        </CardContent>
      </Card>
    </div>
  )
}

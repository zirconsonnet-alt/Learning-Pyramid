import { useEffect, useMemo, useRef, useState } from "react"
import { House, Menu, Sparkles, TimerReset } from "lucide-react"
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate, useParams } from "react-router-dom"

import { MainNav, getGlobalNavItems, getProjectNavItems } from "@/shell/MainNav"
import { PomodoroPreTransitionNotice, PomodoroTransitionEffect } from "@/shell/PomodoroTransitionEffect"
import { ApiError } from "@/ui/api/http"
import { useBootstrapGlobalSettings } from "@/ui/globalSettingsSync"
import { useLearningPlanRemoteSync } from "@/ui/learningPlans/learningPlanRemoteSync"
import { useSubjectContext } from "@/ui/queries/subjects"
import { ErrorNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { projectTypeRequiresLearningObjectTree } from "@/ui/projectTypes"
import { useCurrentUser, useLogout } from "@/ui/queries/auth"
import { useProject, useProjects } from "@/ui/queries/projects"
import { useSystemCapabilities } from "@/ui/queries/system"
import { useProjectConfig } from "@/ui/queries/workbench"
import { usePomodoroPreTransitionSpeech, usePomodoroTransitionSound } from "@/ui/pomodoroAudio"
import { useAppStore } from "@/ui/store/appStore"
import {
  formatPomodoroCountdown,
  getPomodoroSnapshot,
  getPomodoroUpcomingSegmentPreview,
  usePomodoroNow,
  usePomodoroStore,
} from "@/ui/store/pomodoroStore"
import { cn } from "@/ui/utils"
import { buildPomodoroPath } from "@/views/pomodoro/pomodoroRouting"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function describeArea(
  pathname: string,
  params: {
    hasProject: boolean
    subjectTitle: string
    materialTitle: string
    isSubjectRoot: boolean
  },
) {
  const { hasProject, isSubjectRoot, materialTitle, subjectTitle } = params
  if (pathname.startsWith("/projects")) {
    return {
      title: "学科中心",
      context: "浏览与切换学科",
    }
  }

  if (pathname.startsWith("/subjects/")) {
    return {
      title: "学科总面板",
      context: "创建和切换学科材料",
    }
  }

  if (pathname.startsWith("/pomodoro")) {
    return {
      title: "番茄钟",
      context: "全局学习节奏控制",
    }
  }

  if (pathname.startsWith("/settings/global")) {
    return {
      title: "全局配置",
      context: "主题与默认模板",
    }
  }

  if (pathname.startsWith("/guide")) {
    return {
      title: "产品指南",
      context: "了解系统能力与使用方式",
    }
  }

  if (pathname.startsWith("/friends")) {
    return {
      title: "好友学习",
      context: "向好友发送申请、查看学习排行与资料",
    }
  }

  if (pathname.startsWith("/membership")) {
    return {
      title: "会员中心",
      context: "从个人中心进入，查看会员权益、价格和订单",
    }
  }

  if (pathname.startsWith("/profile")) {
    return {
      title: "个人中心",
      context: "管理账号信息、会员权益与安全设置",
    }
  }

  if (pathname.startsWith("/admin")) {
    return {
      title: "后台管理",
      context: "管理用户状态、会员运营与后台记录",
    }
  }

  if (hasProject) {
    if (pathname.includes("/workbench")) {
      return {
        title: "学科工作台",
        context: isSubjectRoot ? subjectTitle : `${subjectTitle} / ${materialTitle}`,
      }
    }

    if (pathname.includes("/ai-chat")) {
      return {
        title: "AI问答",
        context: isSubjectRoot ? subjectTitle : `${subjectTitle} / ${materialTitle}`,
      }
    }

    if (pathname.includes("/task-tree")) {
      return {
        title: "学习任务树",
        context: materialTitle,
      }
    }

    if (pathname.includes("/object-tree")) {
      return {
        title: "学习对象树",
        context: materialTitle,
      }
    }

    if (pathname.includes("/settings")) {
      return {
        title: isSubjectRoot ? "学科设置" : "材料设置",
        context: isSubjectRoot ? subjectTitle : `${subjectTitle} / ${materialTitle}`,
      }
    }
  }

  return {
    title: "工作空间",
    context: "系统总览",
  }
}

export function AppShell() {
  const nav = useNavigate()
  const location = useLocation()
  const { projectId } = useParams()
  const pid = projectId ?? ""
  const selectedProjectId = useAppStore((state) => state.selectedProjectId)
  const setSelectedProjectId = useAppStore((state) => state.setSelectedProjectId)
  const effectiveProjectId = pid || selectedProjectId || ""
  const [projectMenuOpen, setProjectMenuOpen] = useState(false)
  const [accountMenuOpen, setAccountMenuOpen] = useState(false)
  const capabilitiesQ = useSystemCapabilities()
  const authEnabled = capabilitiesQ.data?.authEnabled ?? false
  const currentUserQ = useCurrentUser(authEnabled)
  const canAccessApp = !authEnabled || Boolean(currentUserQ.data)
  useBootstrapGlobalSettings(authEnabled && Boolean(currentUserQ.data?.userId), currentUserQ.data?.userId)
  useLearningPlanRemoteSync(authEnabled && Boolean(currentUserQ.data?.userId), currentUserQ.data?.userId)
  const subjectContextQ = useSubjectContext(effectiveProjectId, canAccessApp && Boolean(effectiveProjectId))
  const { projectTitle } = useProject(effectiveProjectId, { enabled: canAccessApp && Boolean(effectiveProjectId) })
  const projectsQ = useProjects(canAccessApp)
  const projectConfigQ = useProjectConfig(canAccessApp && effectiveProjectId ? effectiveProjectId : "")
  const logout = useLogout()
  const pomodoroEnabled = usePomodoroStore((state) => state.enabled)
  const pomodoroWeeklySchedule = usePomodoroStore((state) => state.weeklySchedule)
  const pomodoroTransitionSoundEnabled = usePomodoroStore((state) => state.transitionSoundEnabled)
  const pomodoroNow = usePomodoroNow(pomodoroEnabled)
  const fallbackProjectTitle = projectTitle || pid || "当前学科"
  const subjectTitle = subjectContextQ.data?.subject.title ?? fallbackProjectTitle
  const fallbackMaterialTitle = projectTitle || pid || "当前材料"
  const currentMaterialTitle = subjectContextQ.data?.currentMaterial.title ?? fallbackMaterialTitle
  const isSubjectRoot = subjectContextQ.data?.isSubjectRoot ?? true
  const area = describeArea(location.pathname, {
    hasProject: Boolean(pid),
    subjectTitle,
    materialTitle: currentMaterialTitle,
    isSubjectRoot,
  })
  const capabilitiesUnavailableError = capabilitiesQ.error && !capabilitiesQ.data ? formatApiError(capabilitiesQ.error) : null
  const currentUserUnavailableError =
    authEnabled && currentUserQ.error && currentUserQ.data === undefined ? formatApiError(currentUserQ.error) : null
  const locationToken = `${location.pathname}${location.search}${location.hash}`
  const projectMenuRef = useRef<HTMLDivElement | null>(null)
  const projectMenuButtonRef = useRef<HTMLButtonElement | null>(null)
  const accountMenuRef = useRef<HTMLDivElement | null>(null)
  const accountMenuButtonRef = useRef<HTMLButtonElement | null>(null)
  const pomodoroAutoJumpKeyRef = useRef("")
  const previousLocationRef = useRef(locationToken)
  const includeObjectTree = projectTypeRequiresLearningObjectTree(projectConfigQ.data?.projectType ?? "COURSE")
  const projectNavItems = useMemo(
    () => getProjectNavItems(effectiveProjectId, { includeObjectTree, settingsLabel: isSubjectRoot ? "学科设置" : "材料设置" }),
    [effectiveProjectId, includeObjectTree, isSubjectRoot],
  )
  const hasProjectContext = Boolean(pid)
  const isAdmin = Boolean(currentUserQ.data?.roles.some((role) => role === "super_admin" || role === "admin"))
  const globalNavItems = useMemo(() => getGlobalNavItems({ includeAdmin: isAdmin, includeMembership: authEnabled }), [authEnabled, isAdmin])
  const inlineNavItems = globalNavItems
  const menuProjectNavItems = hasProjectContext ? projectNavItems : []
  const pomodoroSnapshot = useMemo(
    () => getPomodoroSnapshot({ enabled: pomodoroEnabled, weeklySchedule: pomodoroWeeklySchedule }, pomodoroNow),
    [pomodoroEnabled, pomodoroNow, pomodoroWeeklySchedule],
  )
  const pomodoroUpcomingSegment = useMemo(
    () =>
      getPomodoroUpcomingSegmentPreview(
        { enabled: pomodoroEnabled, weeklySchedule: pomodoroWeeklySchedule },
        pomodoroNow,
      ),
    [pomodoroEnabled, pomodoroNow, pomodoroWeeklySchedule],
  )
  const accessibleProjectIds = useMemo(
    () => new Set((projectsQ.data ?? []).map((project) => project.projectId)),
    [projectsQ.data],
  )
  const pomodoroFocusProjectId =
    pomodoroSnapshot.currentProjectId && accessibleProjectIds.has(pomodoroSnapshot.currentProjectId)
      ? pomodoroSnapshot.currentProjectId
      : ""
  const focusProjectTitle =
    pomodoroFocusProjectId && projectsQ.data
      ? projectsQ.data.find((project) => project.projectId === pomodoroFocusProjectId)?.title ?? ""
      : ""
  const upcomingJumpProjectId =
    pomodoroUpcomingSegment?.phase === "focus" &&
    pomodoroUpcomingSegment.projectId &&
    accessibleProjectIds.has(pomodoroUpcomingSegment.projectId)
      ? pomodoroUpcomingSegment.projectId
      : ""
  const upcomingJumpProjectTitle =
    upcomingJumpProjectId && projectsQ.data
      ? projectsQ.data.find((project) => project.projectId === upcomingJumpProjectId)?.title ?? ""
      : ""
  const upcomingJumpPath = upcomingJumpProjectId ? `/p/${upcomingJumpProjectId}/workbench` : ""
  const shouldShowPomodoroPreJumpNotice =
    pomodoroUpcomingSegment?.phase === "focus" &&
    Boolean(upcomingJumpPath) &&
    location.pathname !== upcomingJumpPath &&
    (pomodoroUpcomingSegment?.startsInMs ?? 0) > 0 &&
    (pomodoroUpcomingSegment?.startsInMs ?? 0) <= 10_000
  const shouldShowPomodoroPreBreakNotice =
    pomodoroUpcomingSegment?.phase === "break" &&
    (pomodoroUpcomingSegment?.startsInMs ?? 0) > 0 &&
    (pomodoroUpcomingSegment?.startsInMs ?? 0) <= 10_000
  const pomodoroAutoJumpKey =
    pomodoroSnapshot.status === "running" &&
    pomodoroSnapshot.phase === "focus" &&
    pomodoroFocusProjectId
      ? `${pomodoroSnapshot.weekday}:${pomodoroSnapshot.segmentIndex}:${pomodoroFocusProjectId}:${pomodoroSnapshot.startAtMs ?? 0}`
      : ""
  usePomodoroTransitionSound(pomodoroSnapshot, pomodoroTransitionSoundEnabled)
  usePomodoroPreTransitionSpeech(
    pomodoroUpcomingSegment &&
      pomodoroUpcomingSegment.startsInMs > 0 &&
      pomodoroUpcomingSegment.startsInMs <= 10_000 &&
      pomodoroUpcomingSegment.promptText.trim()
      ? {
          key: `${pomodoroUpcomingSegment.weekday}:${pomodoroUpcomingSegment.phase}:${pomodoroUpcomingSegment.pomodoroIndex}:${pomodoroUpcomingSegment.startAtMs}:${pomodoroUpcomingSegment.promptText}`,
          promptText: pomodoroUpcomingSegment.promptText,
          startsInMs: pomodoroUpcomingSegment.startsInMs,
        }
      : null,
  )
  const showPomodoroShortcut = pomodoroEnabled
  const pomodoroShortcutText =
    pomodoroSnapshot.status === "running"
      ? `${pomodoroSnapshot.phase === "focus" ? "学习" : "间歇"} ${formatPomodoroCountdown(pomodoroSnapshot.segmentRemainingMs)}`
      : pomodoroSnapshot.status === "completed"
        ? "今日已完成"
        : pomodoroSnapshot.idleReason === "not_configured"
          ? "待配置"
          : pomodoroSnapshot.idleReason === "day_off"
            ? "今日未排程"
            : pomodoroSnapshot.idleReason === "waiting"
              ? `距离开始 ${formatPomodoroCountdown(pomodoroSnapshot.untilStartMs)}`
              : "已关闭"

  useEffect(() => {
    if (!pid || selectedProjectId === pid) return
    setSelectedProjectId(pid)
  }, [pid, selectedProjectId, setSelectedProjectId])

  useEffect(() => {
    if (previousLocationRef.current === locationToken) return
    previousLocationRef.current = locationToken
    setProjectMenuOpen(false)
    setAccountMenuOpen(false)
  }, [locationToken])

  useEffect(() => {
    if (!pomodoroAutoJumpKey || !pomodoroFocusProjectId) return
    if (pomodoroAutoJumpKeyRef.current === pomodoroAutoJumpKey) return
    pomodoroAutoJumpKeyRef.current = pomodoroAutoJumpKey
    const targetPath = `/p/${pomodoroFocusProjectId}/workbench`
    if (location.pathname === targetPath) return
    let cancelled = false

    async function jumpToFocusWorkbench() {
      if (typeof document !== "undefined" && document.fullscreenElement) {
        try {
          await document.exitFullscreen()
        } catch {
          // Ignore exit failure and continue with navigation.
        }
      }
      if (cancelled) return
      nav(targetPath, {
        replace: true,
        state: {
          pomodoroAutoJump: true,
          targetProjectId: pomodoroFocusProjectId,
        },
      })
    }

    void jumpToFocusWorkbench()
    return () => {
      cancelled = true
    }
  }, [location.pathname, nav, pomodoroAutoJumpKey, pomodoroFocusProjectId])

  useEffect(() => {
    if (!projectMenuOpen && !accountMenuOpen) return

    function onPointerDown(event: MouseEvent | TouchEvent) {
      const target = event.target
      if (!(target instanceof Node)) return
      const withinProjectMenu = projectMenuRef.current?.contains(target) || projectMenuButtonRef.current?.contains(target)
      const withinAccountMenu = accountMenuRef.current?.contains(target) || accountMenuButtonRef.current?.contains(target)
      if (withinProjectMenu || withinAccountMenu) return
      setProjectMenuOpen(false)
      setAccountMenuOpen(false)
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setProjectMenuOpen(false)
        setAccountMenuOpen(false)
      }
    }

    document.addEventListener("mousedown", onPointerDown)
    document.addEventListener("touchstart", onPointerDown)
    document.addEventListener("keydown", onKeyDown)
    return () => {
      document.removeEventListener("mousedown", onPointerDown)
      document.removeEventListener("touchstart", onPointerDown)
      document.removeEventListener("keydown", onKeyDown)
    }
  }, [accountMenuOpen, projectMenuOpen])

  async function onLogout() {
    await logout.mutateAsync()
    nav("/login", { replace: true })
  }

  if (capabilitiesQ.isLoading || (authEnabled && currentUserQ.isLoading)) {
    return (
      <div className="min-h-dvh">
        <main className="container flex min-h-dvh items-center justify-center py-10">
          <div className="theme-status-surface flex w-full max-w-lg items-center gap-4 px-6 py-5">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-[0_18px_36px_-24px_rgba(30,58,95,0.72)]">
              <Sparkles className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-medium text-foreground">正在准备工作空间</p>
              <p className="text-sm text-muted-foreground">加载账号能力、项目上下文和系统导航。</p>
            </div>
          </div>
        </main>
      </div>
    )
  }

  if (capabilitiesUnavailableError) {
    return (
      <div className="min-h-dvh">
        <main className="container flex min-h-dvh items-center justify-center py-10">
          <div className="w-full max-w-lg">
            <ErrorNotice
              title="工作空间暂时不可用"
              message={`当前无法确认部署能力，系统不会把这次失败误判成 Local 模式或未开启登录。${capabilitiesUnavailableError}`}
              action={
                <div className="flex flex-wrap gap-2">
                  <Button onClick={() => void capabilitiesQ.refetch()}>重试</Button>
                  <Button asChild variant="outline">
                    <Link to="/login">前往登录页</Link>
                  </Button>
                </div>
              }
            />
          </div>
        </main>
      </div>
    )
  }

  if (currentUserUnavailableError) {
    return (
      <div className="min-h-dvh">
        <main className="container flex min-h-dvh items-center justify-center py-10">
          <div className="w-full max-w-lg">
            <ErrorNotice
              title="暂时无法确认账号会话"
              message={`账号状态检查没有完成，系统不会把这次失败直接当成“未登录”。${currentUserUnavailableError}`}
              action={
                <div className="flex flex-wrap gap-2">
                  <Button onClick={() => void currentUserQ.refetch()}>重新检查</Button>
                  <Button asChild variant="outline">
                    <Link to="/login">前往登录页</Link>
                  </Button>
                </div>
              }
            />
          </div>
        </main>
      </div>
    )
  }

  if (authEnabled && !currentUserQ.data) {
    const from = `${location.pathname}${location.search}${location.hash}`
    return <Navigate to="/login" replace state={{ from }} />
  }

  return (
    <div className="min-h-dvh">
      <div className="theme-shell-glow pointer-events-none fixed inset-x-0 top-0 z-0 h-72" />
      <PomodoroTransitionEffect
        snapshot={pomodoroSnapshot}
        enabled={pomodoroEnabled}
        currentProjectTitle={focusProjectTitle || null}
      />
      {shouldShowPomodoroPreJumpNotice && pomodoroUpcomingSegment ? (
        <PomodoroPreTransitionNotice
          phase="focus"
          countdownMs={pomodoroUpcomingSegment.startsInMs}
          currentPomodoro={pomodoroUpcomingSegment.pomodoroIndex}
          totalPomodoros={pomodoroUpcomingSegment.totalPomodoros}
          projectTitle={upcomingJumpProjectTitle || null}
        />
      ) : null}
      {shouldShowPomodoroPreBreakNotice && pomodoroUpcomingSegment ? (
        <PomodoroPreTransitionNotice
          phase="break"
          countdownMs={pomodoroUpcomingSegment.startsInMs}
          currentPomodoro={pomodoroUpcomingSegment.pomodoroIndex}
          totalPomodoros={pomodoroUpcomingSegment.totalPomodoros}
        />
      ) : null}
      <header className="theme-shell-header sticky top-0 z-20 backdrop-blur-2xl">
        <div className="container py-2.5">
          <div className="relative flex w-full items-center gap-3 sm:gap-4">
            <Link
              to="/"
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-[1.05rem] bg-[linear-gradient(160deg,hsl(var(--primary)),hsl(var(--primary)/0.72))] text-primary-foreground shadow-[0_16px_34px_-26px_hsl(var(--primary)/0.4)] transition-all hover:-translate-y-px hover:shadow-[0_20px_40px_-26px_hsl(var(--primary)/0.46)]"
              aria-label="查看公开首页"
              title="查看公开首页"
            >
              <House className="h-4.5 w-4.5" />
            </Link>

            <div className="min-w-0 flex-1">
              <div className="min-w-0">
                <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="text-[13px] font-semibold tracking-[0.04em] text-[color:var(--theme-soft-text-strong)]">LearningPyramid</span>
                  <span className="text-xs text-muted-foreground">/</span>
                  <div className="min-w-0 truncate text-sm font-medium tracking-tight text-foreground sm:text-[15px]">{area.title}</div>
                </div>
                <div className="mt-0.5 min-w-0 truncate text-xs text-muted-foreground">{area.context}</div>
              </div>
            </div>

            <div className="flex min-w-0 items-center gap-2">
              {showPomodoroShortcut ? (
                <Link
                  to={buildPomodoroPath()}
                  className={cn(
                    "hidden h-10 items-center gap-2 rounded-xl border px-3 text-[13px] [box-shadow:var(--theme-soft-shadow)] sm:inline-flex",
                    pomodoroSnapshot.phase === "break"
                      ? "border-amber-200 bg-amber-50 text-amber-900"
                      : "border-primary/15 bg-[hsl(var(--primary)/0.08)] text-foreground",
                  )}
                >
                  <TimerReset className={cn("h-4 w-4", pomodoroSnapshot.phase === "break" ? "text-amber-700" : "text-primary")} />
                  <span>{pomodoroShortcutText}</span>
                </Link>
              ) : null}

              <div className="hidden min-w-0 items-center gap-2 overflow-x-auto sm:flex">
                {inlineNavItems.map((item) => {
                  const Icon = item.icon
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      className={({ isActive }) =>
                        cn(
                          "inline-flex h-9 items-center gap-2 rounded-xl border [border-color:var(--theme-soft-border)] [background:var(--theme-soft-bg)] px-3 text-[13px] text-[color:var(--theme-subtle-text)] [box-shadow:var(--theme-soft-shadow)] transition-colors hover:border-primary/15 hover:text-foreground",
                          (isActive || (item.to === "/projects" && location.pathname.startsWith("/subjects/"))) &&
                            "border-primary/15 bg-[hsl(var(--primary)/0.08)] text-foreground",
                        )
                      }
                    >
                      <Icon className="h-3.5 w-3.5 shrink-0 text-primary" />
                      <span>{item.label}</span>
                    </NavLink>
                  )
                })}
              </div>

              {menuProjectNavItems.length > 0 ? (
                <div className="relative shrink-0">
                  <Button
                    ref={projectMenuButtonRef}
                    variant="outline"
                    size="icon"
                    className="h-10 w-10 rounded-xl [border-color:var(--theme-soft-border)] [background:var(--theme-soft-bg)]"
                    onClick={() => {
                      setAccountMenuOpen(false)
                      setProjectMenuOpen((current) => !current)
                    }}
                    aria-expanded={projectMenuOpen}
                    aria-haspopup="menu"
                  >
                    <Menu className="h-4.5 w-4.5" />
                    <span className="sr-only">打开项目菜单</span>
                  </Button>

                  {projectMenuOpen ? (
                    <div
                      ref={projectMenuRef}
                      className="absolute right-0 top-[calc(100%+0.65rem)] z-30 w-[min(22rem,calc(100vw-1rem))] overflow-hidden rounded-[1.6rem] border [border-color:var(--theme-soft-border)] [background:radial-gradient(circle_at_top_left,hsl(var(--primary)/0.08),transparent_34%),var(--theme-card-main-bg)] shadow-[0_24px_60px_-30px_rgba(15,23,42,0.24)] backdrop-blur-2xl"
                    >
                      <div className="max-h-[min(70vh,calc(100dvh-5.5rem))] overflow-y-auto overscroll-contain p-3 [-webkit-overflow-scrolling:touch]">
                        <div className="theme-soft-surface p-3">
                          <div className="flex min-w-0 items-center gap-2">
                            <div className="shrink-0 text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                              {isSubjectRoot ? "当前学科" : "当前材料"}
                            </div>
                            <div className="min-w-0 truncate text-sm font-medium text-foreground">
                              {isSubjectRoot ? subjectTitle : currentMaterialTitle}
                            </div>
                          </div>
                          {!isSubjectRoot ? <div className="mt-1 text-xs text-muted-foreground">{subjectTitle}</div> : null}
                          <div className="mt-3">
                            <MainNav items={menuProjectNavItems} onNavigate={() => setProjectMenuOpen(false)} />
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {authEnabled && currentUserQ.data ? (
                <div className="relative shrink-0">
                  <button
                    ref={accountMenuButtonRef}
                    type="button"
                    className="inline-flex h-10 w-10 items-center justify-center overflow-hidden rounded-full border [border-color:var(--theme-soft-border)] [background:var(--theme-soft-bg)] text-sm font-semibold text-[color:var(--theme-soft-text-strong)] [box-shadow:var(--theme-soft-shadow)] transition-colors hover:border-primary/15"
                    onClick={() => {
                      setProjectMenuOpen(false)
                      setAccountMenuOpen((current) => !current)
                    }}
                    aria-expanded={accountMenuOpen}
                    aria-haspopup="menu"
                    aria-label="打开账号菜单"
                    title={currentUserQ.data.nickname || currentUserQ.data.email}
                  >
                    {currentUserQ.data.avatarUrl ? (
                      <img src={currentUserQ.data.avatarUrl} alt={currentUserQ.data.nickname} className="h-full w-full object-cover" />
                    ) : (
                      (currentUserQ.data.nickname || currentUserQ.data.email).slice(0, 1).toUpperCase()
                    )}
                  </button>

                  {accountMenuOpen ? (
                    <div
                      ref={accountMenuRef}
                      className="absolute right-0 top-[calc(100%+0.65rem)] z-30 w-[min(18rem,calc(100vw-1rem))] overflow-hidden rounded-[1.6rem] border [border-color:var(--theme-soft-border)] [background:radial-gradient(circle_at_top_left,hsl(var(--primary)/0.08),transparent_34%),var(--theme-card-main-bg)] shadow-[0_24px_60px_-30px_rgba(15,23,42,0.24)] backdrop-blur-2xl"
                    >
                      <div className="p-3">
                        <div className="theme-soft-surface p-3">
                          <div className="flex items-center gap-3">
                            <div className="inline-flex h-12 w-12 items-center justify-center overflow-hidden rounded-2xl border [border-color:var(--theme-icon-border)] [background:var(--theme-icon-bg)] text-base font-semibold [color:var(--theme-icon-text)]">
                              {currentUserQ.data.avatarUrl ? (
                                <img src={currentUserQ.data.avatarUrl} alt={currentUserQ.data.nickname} className="h-full w-full object-cover" />
                              ) : (
                                (currentUserQ.data.nickname || currentUserQ.data.email).slice(0, 1).toUpperCase()
                              )}
                            </div>
                            <div className="min-w-0">
                              <div className="truncate text-sm font-medium text-foreground">{currentUserQ.data.nickname}</div>
                              <div className="mt-1 truncate text-xs text-muted-foreground">{currentUserQ.data.email}</div>
                            </div>
                          </div>
                          <div className="mt-3 grid gap-2">
                            <Button asChild variant="outline" className="w-full justify-start rounded-xl">
                              <Link
                                to="/profile"
                                onClick={() => setAccountMenuOpen(false)}
                              >
                                个人中心
                              </Link>
                            </Button>
                            <Button asChild variant="outline" className="w-full justify-start rounded-xl">
                              <Link
                                to="/membership"
                                onClick={() => setAccountMenuOpen(false)}
                              >
                                会员中心
                              </Link>
                            </Button>
                            <Button
                              variant="outline"
                              className="w-full justify-start rounded-xl"
                              onClick={() => {
                                setAccountMenuOpen(false)
                                void onLogout()
                              }}
                              disabled={logout.isPending}
                            >
                              {logout.isPending ? "退出中..." : "退出登录"}
                            </Button>
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </header>

      <main className="container relative z-10 py-5 lg:py-6">
        <Outlet />
      </main>
    </div>
  )
}

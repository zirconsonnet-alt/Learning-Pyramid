import { useEffect, useMemo, useRef, useState, type RefObject } from "react"
import { ChevronDown, CreditCard, LogOut, Sparkles, TimerReset, User, type LucideIcon } from "lucide-react"
import { Link, Navigate, NavLink, Outlet, useLocation, useNavigate, useParams } from "react-router-dom"
import "driver.js/dist/driver.css"

import { MainNav } from "@/shell/MainNav"
import { getGlobalNavItems, getProjectNavItems, getSubjectNavItems, type NavItem } from "@/shell/navItems"
import { PomodoroPreTransitionNotice, PomodoroTransitionEffect } from "@/shell/PomodoroTransitionEffect"
import { ApiError } from "@/ui/api/http"
import { useBootstrapGlobalSettings } from "@/ui/globalSettingsSync"
import { useLearningPlanRemoteSync } from "@/ui/learningPlans/learningPlanRemoteSync"
import { useSubjectContext, useSubjects } from "@/ui/queries/subjects"
import { ErrorNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { projectTypeRequiresLearningObjectTree } from "@/ui/projectTypes"
import { useCurrentUser, useLogout } from "@/ui/queries/auth"
import { useProject, useProjects } from "@/ui/queries/projects"
import { useSystemCapabilities } from "@/ui/queries/system"
import { useProjectConfig } from "@/ui/queries/workbench"
import { usePomodoroPreTransitionSpeech, usePomodoroTransitionSound } from "@/ui/pomodoroAudio"
import { setPomodoroRestMusicPhaseActive } from "@/ui/pomodoroRestMusicPlayer"
import { useGuideWalkthroughController } from "@/ui/guideWalkthrough/guideWalkthroughController"
import { buildProjectSettingsPath } from "@/ui/projectPaths"
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

const BRAND_LOGO_SRC = "/favicon-logo-white-v2-192.png"

function describeArea(
  pathname: string,
  params: {
    hasProject: boolean
    subjectTitle: string
    materialTitle: string
    isSubjectSettingsScope: boolean
  },
) {
  const { hasProject, isSubjectSettingsScope, materialTitle, subjectTitle } = params
  if (pathname.startsWith("/projects")) {
    return {
      title: "学科中心",
      context: "浏览与切换学科",
    }
  }

  if (pathname.startsWith("/subjects/")) {
    return {
      title: "项目中心",
      context: "创建和切换学科项目",
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
        context: isSubjectSettingsScope ? subjectTitle : `${subjectTitle} / ${materialTitle}`,
      }
    }

    if (pathname.includes("/ai-chat")) {
      return {
        title: "AI问答",
        context: isSubjectSettingsScope ? subjectTitle : `${subjectTitle} / ${materialTitle}`,
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

    if (pathname.includes("/project-settings")) {
      return {
        title: "项目设置",
        context: `${subjectTitle} / ${materialTitle}`,
      }
    }

    if (pathname.includes("/settings")) {
      return {
        title: isSubjectSettingsScope ? "学科设置" : "项目设置",
        context: isSubjectSettingsScope ? subjectTitle : `${subjectTitle} / ${materialTitle}`,
      }
    }
  }

  return {
    title: "工作空间",
    context: "系统总览",
  }
}

function matchesNavPath(pathname: string, to: string) {
  return pathname === to || pathname.startsWith(`${to}/`)
}

function isNavGroupActive(pathname: string, items: NavItem[]) {
  return items.some((item) => matchesNavPath(pathname, item.to))
}

function HeaderNavDropdown(props: {
  section: string
  title: string
  items: NavItem[]
  isOpen: boolean
  isActive: boolean
  buttonRef: RefObject<HTMLButtonElement>
  menuRef: RefObject<HTMLDivElement>
  onOpen: () => void
  onClose: () => void
}) {
  const { section, title, items, isOpen, isActive, buttonRef, menuRef, onOpen, onClose } = props

  return (
    <div
      className="relative min-w-0 shrink-0"
      onMouseEnter={onOpen}
      onMouseLeave={onClose}
      onFocusCapture={onOpen}
      onBlurCapture={(event) => {
        const currentTarget = event.currentTarget
        window.requestAnimationFrame(() => {
          if (!currentTarget.contains(document.activeElement)) onClose()
        })
      }}
    >
      <button
        ref={buttonRef}
        type="button"
        className={cn(
          "inline-flex h-10 min-w-0 max-w-[min(15rem,calc(100vw-7rem))] items-center gap-2 rounded-xl border px-3 text-left [box-shadow:var(--theme-soft-shadow)] transition-colors",
          isOpen || isActive
            ? "border-primary/15 bg-[hsl(var(--primary)/0.08)] text-foreground"
            : "[border-color:var(--theme-soft-border)] [background:var(--theme-soft-bg)] text-[color:var(--theme-subtle-text)] hover:border-primary/15 hover:text-foreground",
        )}
        onClick={onOpen}
        aria-expanded={isOpen}
        aria-haspopup="menu"
        title={`${section} · ${title}`}
      >
        <span className="flex min-w-0 items-center gap-2">
          <span className="shrink-0 text-[12px] font-medium text-muted-foreground">{section}</span>
          <span className="h-1 w-1 shrink-0 rounded-full bg-[color:var(--theme-soft-border)]" aria-hidden="true" />
          <span className="min-w-0 truncate text-[13px] font-medium text-current">{title}</span>
        </span>
        <ChevronDown className={cn("h-4 w-4 shrink-0 transition-transform duration-200", isOpen && "rotate-180")} />
      </button>

      {isOpen ? (
        <div
          ref={menuRef}
          className="absolute right-0 top-full z-30 w-[min(22rem,calc(100vw-1rem))] pt-2.5"
        >
          <div className="overflow-hidden rounded-[1.6rem] border [border-color:var(--theme-soft-border)] [background:radial-gradient(circle_at_top_left,hsl(var(--primary)/0.08),transparent_34%),var(--theme-card-main-bg)] shadow-[0_24px_60px_-30px_rgba(15,23,42,0.24)] backdrop-blur-2xl">
            <div className="max-h-[min(70vh,calc(100dvh-5.5rem))] overflow-y-auto overscroll-contain p-3 [-webkit-overflow-scrolling:touch]">
              <div className="theme-soft-surface p-3">
                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">{section}</div>
                <div className="mt-1 truncate text-sm font-medium text-foreground">{title}</div>
                <div className="mt-3">
                  <MainNav items={items} onNavigate={onClose} />
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

function AccountMenuLink(props: {
  to: string
  label: string
  icon: LucideIcon
  onNavigate: () => void
}) {
  const { to, label, icon: Icon, onNavigate } = props

  return (
    <NavLink to={to} onClick={onNavigate} className="block">
      {({ isActive }) => (
        <div
          className={cn(
            "group flex min-h-11 w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-sm transition-all duration-200",
            isActive
              ? "bg-primary text-primary-foreground shadow-[0_18px_36px_-28px_hsl(var(--primary)/0.42)]"
              : "text-[color:var(--theme-subtle-text)] hover:[background:var(--theme-soft-bg)] hover:text-foreground",
          )}
        >
          <span
            className={cn(
              "flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border transition-colors",
              isActive
                ? "border-white/15 bg-white/12 text-white"
                : "[border-color:var(--theme-icon-border)] [background:var(--theme-icon-bg)] [color:var(--theme-icon-text)] group-hover:bg-white",
            )}
          >
            <Icon className="h-4 w-4" />
          </span>
          <span className="min-w-0 truncate">{label}</span>
        </div>
      )}
    </NavLink>
  )
}

function AccountMenuActionButton(props: {
  label: string
  icon: LucideIcon
  onClick: () => void
  disabled?: boolean
}) {
  const { label, icon: Icon, onClick, disabled = false } = props

  return (
    <button
      type="button"
      className="group flex min-h-11 w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-left text-sm text-[color:var(--theme-subtle-text)] transition-all duration-200 hover:bg-destructive/8 hover:text-destructive disabled:pointer-events-none disabled:opacity-60"
      onClick={onClick}
      disabled={disabled}
    >
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border [border-color:var(--theme-icon-border)] [background:var(--theme-icon-bg)] [color:var(--theme-icon-text)] transition-colors group-hover:border-destructive/20 group-hover:bg-white group-hover:text-destructive">
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0 truncate">{label}</span>
    </button>
  )
}

export function AppShell() {
  const nav = useNavigate()
  const location = useLocation()
  useGuideWalkthroughController({ navigate: nav, pathname: location.pathname })
  const { projectId, subjectId: routeSubjectId } = useParams()
  const pid = projectId ?? ""
  const isProjectsScope = location.pathname === "/projects"
  const selectedProjectId = useAppStore((state) => state.selectedProjectId)
  const setSelectedProjectId = useAppStore((state) => state.setSelectedProjectId)
  const [globalMenuOpen, setGlobalMenuOpen] = useState(false)
  const [subjectMenuOpen, setSubjectMenuOpen] = useState(false)
  const [projectMenuOpen, setProjectMenuOpen] = useState(false)
  const [accountMenuOpen, setAccountMenuOpen] = useState(false)
  const capabilitiesQ = useSystemCapabilities()
  const authEnabled = capabilitiesQ.data?.authEnabled ?? false
  const currentUserQ = useCurrentUser(authEnabled)
  const canAccessApp = !authEnabled || Boolean(currentUserQ.data)
  useBootstrapGlobalSettings(authEnabled && Boolean(currentUserQ.data?.userId), currentUserQ.data?.userId)
  useLearningPlanRemoteSync(authEnabled && Boolean(currentUserQ.data?.userId), currentUserQ.data?.userId)
  const subjectsQ = useSubjects(canAccessApp && Boolean(routeSubjectId))
  const routeSubject = useMemo(
    () => (subjectsQ.data ?? []).find((subject) => subject.subjectId === routeSubjectId || subject.compatibilityProjectId === routeSubjectId) ?? null,
    [routeSubjectId, subjectsQ.data],
  )
  const routeScopedProjectId = routeSubjectId ? routeSubject?.compatibilityProjectId ?? "" : ""
  const effectiveProjectId = pid || (routeSubjectId ? routeScopedProjectId : isProjectsScope ? "" : selectedProjectId || "")
  const subjectContextQ = useSubjectContext(effectiveProjectId, canAccessApp && Boolean(effectiveProjectId))
  const { projectTitle } = useProject(effectiveProjectId, { enabled: canAccessApp && Boolean(effectiveProjectId) })
  const projectsQ = useProjects(canAccessApp)
  const projectConfigQ = useProjectConfig(canAccessApp && effectiveProjectId ? effectiveProjectId : "")
  const logout = useLogout()
  const pomodoroEnabled = usePomodoroStore((state) => state.enabled)
  const pomodoroWeeklySchedule = usePomodoroStore((state) => state.weeklySchedule)
  const pomodoroTransitionSoundEnabled = usePomodoroStore((state) => state.transitionSoundEnabled)
  const pomodoroNow = usePomodoroNow(pomodoroEnabled)
  const resolvedSubjectId = subjectContextQ.data?.subject.subjectId ?? routeSubject?.subjectId ?? ""
  const fallbackSubjectTitle = routeSubject?.title || projectTitle || pid || "当前学科"
  const subjectTitle = subjectContextQ.data?.subject.title ?? fallbackSubjectTitle
  const fallbackMaterialTitle = projectTitle || pid || "当前项目"
  const currentMaterialTitle = subjectContextQ.data?.currentMaterial.title ?? fallbackMaterialTitle
  const resolvedSubjectProjectId = subjectContextQ.data?.subjectProjectId ?? routeSubject?.compatibilityProjectId ?? ""
  const currentProjectContextId = subjectContextQ.data?.currentProjectId ?? pid
  const isSubjectRoot = subjectContextQ.data?.isSubjectRoot ?? (!pid && Boolean(routeSubjectId))
  const isSubjectSettingsScope = isSubjectRoot && !location.pathname.includes("/project-settings")
  const currentMaterialProjectId =
    subjectContextQ.data?.currentMaterial.compatibilityProjectId ?? (!isSubjectRoot ? currentProjectContextId : "")
  const isSubjectDashboardScope = Boolean(routeSubjectId) && !pid
  const hasSubjectContext = Boolean(resolvedSubjectId && resolvedSubjectProjectId)
  const hasProjectContext = Boolean(hasSubjectContext && currentMaterialProjectId && !isSubjectDashboardScope)
  const area = describeArea(location.pathname, {
    hasProject: Boolean(pid),
    subjectTitle,
    materialTitle: currentMaterialTitle,
    isSubjectSettingsScope,
  })
  const capabilitiesUnavailableError = capabilitiesQ.error && !capabilitiesQ.data ? formatApiError(capabilitiesQ.error) : null
  const currentUserUnavailableError =
    authEnabled && currentUserQ.error && currentUserQ.data === undefined ? formatApiError(currentUserQ.error) : null
  const locationToken = `${location.pathname}${location.search}${location.hash}`
  const globalMenuRef = useRef<HTMLDivElement | null>(null)
  const globalMenuButtonRef = useRef<HTMLButtonElement | null>(null)
  const subjectMenuRef = useRef<HTMLDivElement | null>(null)
  const subjectMenuButtonRef = useRef<HTMLButtonElement | null>(null)
  const projectMenuRef = useRef<HTMLDivElement | null>(null)
  const projectMenuButtonRef = useRef<HTMLButtonElement | null>(null)
  const accountMenuRef = useRef<HTMLDivElement | null>(null)
  const accountMenuButtonRef = useRef<HTMLButtonElement | null>(null)
  const pomodoroAutoJumpKeyRef = useRef("")
  const previousLocationRef = useRef(locationToken)
  const includeObjectTree = projectTypeRequiresLearningObjectTree(
    subjectContextQ.data?.currentMaterial.materialType ?? projectConfigQ.data?.projectType ?? "COURSE",
  )
  const subjectNavItems = useMemo(
    () => getSubjectNavItems(resolvedSubjectId, resolvedSubjectProjectId),
    [resolvedSubjectId, resolvedSubjectProjectId],
  )
  const currentProjectSettingsPath = useMemo(
    () => buildProjectSettingsPath(currentMaterialProjectId, { subjectProjectId: resolvedSubjectProjectId }),
    [currentMaterialProjectId, resolvedSubjectProjectId],
  )
  const projectNavItems = useMemo(
    () =>
      hasProjectContext
        ? getProjectNavItems(currentMaterialProjectId, {
            includeObjectTree,
            settingsLabel: "项目设置",
            settingsTo: currentProjectSettingsPath,
          })
        : [],
    [currentMaterialProjectId, currentProjectSettingsPath, hasProjectContext, includeObjectTree],
  )
  const isAdmin = Boolean(currentUserQ.data?.roles.some((role) => role === "super_admin" || role === "admin"))
  const globalNavItems = useMemo(() => getGlobalNavItems({ includeAdmin: isAdmin, includeMembership: authEnabled }), [authEnabled, isAdmin])
  const globalMenuActive = isNavGroupActive(location.pathname, globalNavItems)
  const subjectMenuActive = isNavGroupActive(location.pathname, subjectNavItems)
  const projectMenuActive = isNavGroupActive(location.pathname, projectNavItems)
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
  useEffect(() => {
    setPomodoroRestMusicPhaseActive(
      pomodoroSnapshot.status === "running" && pomodoroSnapshot.phase === "break",
    )
  }, [pomodoroSnapshot.phase, pomodoroSnapshot.status])
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
    const nextSelectedProjectId = pid || routeScopedProjectId
    if (!nextSelectedProjectId || selectedProjectId === nextSelectedProjectId) return
    setSelectedProjectId(nextSelectedProjectId)
  }, [pid, routeScopedProjectId, selectedProjectId, setSelectedProjectId])

  useEffect(() => {
    if (previousLocationRef.current === locationToken) return
    previousLocationRef.current = locationToken
    const frame = window.requestAnimationFrame(() => {
      setGlobalMenuOpen(false)
      setSubjectMenuOpen(false)
      setProjectMenuOpen(false)
      setAccountMenuOpen(false)
    })
    return () => window.cancelAnimationFrame(frame)
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
    if (!globalMenuOpen && !subjectMenuOpen && !projectMenuOpen && !accountMenuOpen) return

    function onPointerDown(event: MouseEvent | TouchEvent) {
      const target = event.target
      if (!(target instanceof Node)) return
      const withinGlobalMenu = globalMenuRef.current?.contains(target) || globalMenuButtonRef.current?.contains(target)
      const withinSubjectMenu = subjectMenuRef.current?.contains(target) || subjectMenuButtonRef.current?.contains(target)
      const withinProjectMenu = projectMenuRef.current?.contains(target) || projectMenuButtonRef.current?.contains(target)
      const withinAccountMenu = accountMenuRef.current?.contains(target) || accountMenuButtonRef.current?.contains(target)
      if (withinGlobalMenu || withinSubjectMenu || withinProjectMenu || withinAccountMenu) return
      setGlobalMenuOpen(false)
      setSubjectMenuOpen(false)
      setProjectMenuOpen(false)
      setAccountMenuOpen(false)
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setGlobalMenuOpen(false)
        setSubjectMenuOpen(false)
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
  }, [accountMenuOpen, globalMenuOpen, projectMenuOpen, subjectMenuOpen])

  async function onLogout() {
    await logout.mutateAsync()
    nav("/login", { replace: true })
  }

  function openAccountMenu() {
    setGlobalMenuOpen(false)
    setSubjectMenuOpen(false)
    setProjectMenuOpen(false)
    setAccountMenuOpen(true)
  }

  function toggleAccountMenu() {
    setGlobalMenuOpen(false)
    setSubjectMenuOpen(false)
    setProjectMenuOpen(false)
    if (typeof window !== "undefined" && window.matchMedia("(hover: hover)").matches) {
      setAccountMenuOpen(true)
      return
    }
    setAccountMenuOpen((current) => !current)
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
              className="inline-flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-[1.05rem] border border-white/75 bg-white p-1 shadow-[0_16px_34px_-26px_hsl(var(--primary)/0.4)] transition-all hover:-translate-y-px hover:shadow-[0_20px_40px_-26px_hsl(var(--primary)/0.46)]"
              aria-label="查看公开首页"
              title="查看公开首页"
            >
              <img className="h-full w-full object-contain" src={BRAND_LOGO_SRC} alt="" />
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

              <div className="flex min-w-0 items-center gap-2">
                <HeaderNavDropdown
                  section="全局"
                  title="系统"
                  items={globalNavItems}
                  isOpen={globalMenuOpen}
                  isActive={globalMenuActive}
                  buttonRef={globalMenuButtonRef}
                  menuRef={globalMenuRef}
                  onOpen={() => {
                    setSubjectMenuOpen(false)
                    setProjectMenuOpen(false)
                    setAccountMenuOpen(false)
                    setGlobalMenuOpen(true)
                  }}
                  onClose={() => setGlobalMenuOpen(false)}
                />

                {subjectNavItems.length > 0 ? (
                  <HeaderNavDropdown
                    section="学科"
                    title={subjectTitle}
                    items={subjectNavItems}
                    isOpen={subjectMenuOpen}
                    isActive={subjectMenuActive}
                    buttonRef={subjectMenuButtonRef}
                    menuRef={subjectMenuRef}
                    onOpen={() => {
                      setGlobalMenuOpen(false)
                      setProjectMenuOpen(false)
                      setAccountMenuOpen(false)
                      setSubjectMenuOpen(true)
                    }}
                    onClose={() => setSubjectMenuOpen(false)}
                  />
                ) : null}

                {projectNavItems.length > 0 ? (
                  <HeaderNavDropdown
                    section="项目"
                    title={currentMaterialTitle}
                    items={projectNavItems}
                    isOpen={projectMenuOpen}
                    isActive={projectMenuActive}
                    buttonRef={projectMenuButtonRef}
                    menuRef={projectMenuRef}
                    onOpen={() => {
                      setGlobalMenuOpen(false)
                      setSubjectMenuOpen(false)
                      setAccountMenuOpen(false)
                      setProjectMenuOpen(true)
                    }}
                    onClose={() => setProjectMenuOpen(false)}
                  />
                ) : null}
              </div>

              {authEnabled && currentUserQ.data ? (
                <div
                  className="relative shrink-0"
                  onMouseEnter={openAccountMenu}
                  onMouseLeave={() => setAccountMenuOpen(false)}
                  onFocusCapture={openAccountMenu}
                  onBlurCapture={(event) => {
                    const currentTarget = event.currentTarget
                    window.requestAnimationFrame(() => {
                      if (!currentTarget.contains(document.activeElement)) setAccountMenuOpen(false)
                    })
                  }}
                >
                  <button
                    ref={accountMenuButtonRef}
                    type="button"
                    className="inline-flex h-10 w-10 items-center justify-center overflow-hidden rounded-full border [border-color:var(--theme-soft-border)] [background:var(--theme-soft-bg)] text-sm font-semibold text-[color:var(--theme-soft-text-strong)] [box-shadow:var(--theme-soft-shadow)] transition-colors hover:border-primary/15"
                    onClick={toggleAccountMenu}
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
                      className="absolute right-0 top-full z-30 w-[min(18rem,calc(100vw-1rem))] pt-2.5"
                    >
                      <div className="overflow-hidden rounded-[1.6rem] border [border-color:var(--theme-soft-border)] [background:radial-gradient(circle_at_top_left,hsl(var(--primary)/0.08),transparent_34%),var(--theme-card-main-bg)] shadow-[0_24px_60px_-30px_rgba(15,23,42,0.24)] backdrop-blur-2xl">
                        <div className="p-3">
                          <div className="theme-soft-surface p-3">
                            <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">账号</div>
                            <div className="mt-3 flex items-center gap-3">
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
                              <AccountMenuLink to="/profile" label="个人中心" icon={User} onNavigate={() => setAccountMenuOpen(false)} />
                              <AccountMenuLink to="/membership" label="会员中心" icon={CreditCard} onNavigate={() => setAccountMenuOpen(false)} />
                              <AccountMenuActionButton
                                label={logout.isPending ? "退出中..." : "退出登录"}
                                icon={LogOut}
                                onClick={() => {
                                  setAccountMenuOpen(false)
                                  void onLogout()
                                }}
                                disabled={logout.isPending}
                              />
                            </div>
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

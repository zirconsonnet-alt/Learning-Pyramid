import { useEffect, useMemo, useRef, useState, type RefObject } from "react"
import { ChevronDown, CreditCard, LogOut, Sparkles, TimerReset, User, UsersRound, type LucideIcon } from "lucide-react"
import { Link, Navigate, NavLink, Outlet, useLocation, useNavigate, useParams } from "react-router-dom"
import "driver.js/dist/driver.css"

import { MainNav } from "@/shell/MainNav"
import { getGlobalNavItems, getProjectNavItems, getSubjectNavItems, type NavItem } from "@/shell/navItems"
import { PomodoroPreTransitionNotice, PomodoroTransitionEffect } from "@/shell/PomodoroTransitionEffect"
import { ApiError } from "@/ui/api/http"
import { useBootstrapGlobalSettings } from "@/ui/globalSettingsSync"
import { useLearningPlanRemoteSync } from "@/ui/learningPlans/learningPlanRemoteSync"
import { useScopedSubjectContext, useSubjectContext, useSubjectProjectCatalog, useSubjects } from "@/ui/queries/subjects"
import { ErrorNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { useCurrentUser, useLogout } from "@/ui/queries/auth"
import { useProject } from "@/ui/queries/projects"
import { isVirtualStudyReviewProjectId } from "@/ui/guideWalkthrough/guideVirtualProjectIds"
import { useSystemCapabilities } from "@/ui/queries/system"
import { usePomodoroPreTransitionSpeech, usePomodoroTransitionSound } from "@/ui/pomodoroAudio"
import { setPomodoroRestMusicPhaseActive } from "@/ui/pomodoroRestMusicPlayer"
import { useGuideWalkthroughController } from "@/ui/guideWalkthrough/guideWalkthroughController"
import { buildProjectSettingsPath } from "@/ui/projectPaths"
import { checkFrontendFreshness } from "@/ui/runtime/frontendFreshness"
import { useAppStore } from "@/ui/store/appStore"
import { recordPomodoroActivity } from "@/ui/store/pomodoroActivityStore"
import {
  formatPomodoroCountdown,
  getPomodoroSnapshot,
  getPomodoroUpcomingSegmentPreview,
  isQuickPomodoroSessionActive,
  pomodoroProjectRefKey,
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

const BRAND_LOGO_SRC = "/product-logo-192.png"

function describeArea(
  pathname: string,
  params: {
    hasProject: boolean
    subjectTitle: string
    materialTitle: string
  },
) {
  const { hasProject, materialTitle, subjectTitle } = params
  if (pathname.match(/^\/subjects\/[^/]+\/settings/)) {
    return {
      title: "学科设置",
      context: subjectTitle,
    }
  }

  if (pathname.startsWith("/subjects") && !pathname.match(/^\/subjects\/[^/]+/)) {
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
        context: `${subjectTitle} / ${materialTitle}`,
      }
    }

    if (pathname.includes("/ai-chat")) {
      return {
        title: "AI问答",
        context: `${subjectTitle} / ${materialTitle}`,
      }
    }

    if (pathname.includes("/structure-view")) {
      return {
        title: "结构视图",
        context: materialTitle,
      }
    }

    if (pathname.includes("/settings")) {
      return {
        title: "项目设置",
        context: `${subjectTitle} / ${materialTitle}`,
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
            <div className="max-h-[min(70vh,calc(100dvh-5.5rem))] overflow-y-auto overscroll-contain px-4 py-4 [-webkit-overflow-scrolling:touch]">
              <div className="px-1">
                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">{section}</div>
                <div className="mt-1 truncate text-sm font-medium text-foreground">{title}</div>
                <div className="mt-3 border-t border-border/60 pt-2">
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
            "group flex min-h-12 w-full items-center gap-3 rounded-xl px-2 py-2 text-sm transition-all duration-200",
            isActive
              ? "bg-[hsl(var(--primary)/0.08)] text-foreground"
              : "text-[color:var(--theme-subtle-text)] hover:bg-[color:var(--theme-soft-bg)] hover:text-foreground",
          )}
        >
          <span
            className={cn(
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-colors",
              isActive
                ? "bg-white text-primary shadow-[0_10px_22px_-18px_hsl(var(--primary)/0.4)]"
                : "text-[color:var(--theme-icon-text)] group-hover:bg-white group-hover:text-foreground",
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
      className="group flex min-h-12 w-full items-center gap-3 rounded-xl px-2 py-2 text-left text-sm text-[color:var(--theme-subtle-text)] transition-all duration-200 hover:bg-destructive/8 hover:text-destructive disabled:pointer-events-none disabled:opacity-60"
      onClick={onClick}
      disabled={disabled}
    >
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg [color:var(--theme-icon-text)] transition-colors group-hover:bg-white group-hover:text-destructive">
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
  const selectedWorkbenchProjectId = useAppStore((state) => state.selectedWorkbenchProjectId)
  const setSelectedWorkbenchProjectId = useAppStore((state) => state.setSelectedWorkbenchProjectId)
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
  const subjectsQ = useSubjects(canAccessApp)
  const routeSubject = useMemo(
    () => (subjectsQ.data ?? []).find((subject) => subject.subjectId === routeSubjectId) ?? null,
    [routeSubjectId, subjectsQ.data],
  )
  const effectiveProjectId = pid
  const routeProjectScope = routeSubjectId && pid ? { subjectId: routeSubjectId, projectId: pid } : null
  const isVirtualStudyReviewProject = isVirtualStudyReviewProjectId(effectiveProjectId)
  const isSubjectDashboardScope = Boolean(routeSubjectId) && !pid
  const subjectContextQ = useSubjectContext(routeProjectScope, canAccessApp && Boolean(effectiveProjectId) && !isSubjectDashboardScope)
  const scopedSubjectContextQ = useScopedSubjectContext(routeSubjectId ?? "", pid, canAccessApp && Boolean(routeSubjectId) && Boolean(pid) && !isSubjectDashboardScope)
  const subjectContext = scopedSubjectContextQ.data ?? subjectContextQ.data
  const { projectTitle } = useProject(routeProjectScope, { enabled: canAccessApp && Boolean(effectiveProjectId) && !isVirtualStudyReviewProject })
  const subjectProjectCatalog = useSubjectProjectCatalog(canAccessApp && !isVirtualStudyReviewProject)
  const logout = useLogout()
  const pomodoroEnabled = usePomodoroStore((state) => state.enabled)
  const pomodoroWeeklySchedule = usePomodoroStore((state) => state.weeklySchedule)
  const pomodoroQuickPomodoro = usePomodoroStore((state) => state.quickPomodoro)
  const pomodoroTransitionSoundEnabled = usePomodoroStore((state) => state.transitionSoundEnabled)
  const activePomodoroQuickSession = isQuickPomodoroSessionActive(pomodoroQuickPomodoro) ? pomodoroQuickPomodoro : null
  const pomodoroNow = usePomodoroNow(pomodoroEnabled || Boolean(activePomodoroQuickSession))
  const resolvedSubjectId = subjectContext?.subject.subjectId ?? routeSubject?.subjectId ?? ""
  const fallbackSubjectTitle = routeSubject?.title || projectTitle || pid || "当前学科"
  const subjectTitle = subjectContext?.subject.title ?? fallbackSubjectTitle
  const fallbackMaterialTitle = projectTitle || pid || "当前项目"
  const currentMaterialTitle = subjectContext?.currentMaterial.title ?? fallbackMaterialTitle
  const currentProjectContextId = subjectContext?.currentProjectId ?? pid
  const currentMaterialProjectId = subjectContext?.currentMaterial.projectId ?? currentProjectContextId
  const hasSubjectContext = Boolean(resolvedSubjectId)
  const hasProjectContext = Boolean(hasSubjectContext && currentMaterialProjectId && !isSubjectDashboardScope)
  const area = describeArea(location.pathname, {
    hasProject: Boolean(pid),
    subjectTitle,
    materialTitle: currentMaterialTitle,
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
  const completedPomodoroSegmentKeyRef = useRef("")
  const previousPomodoroSnapshotRef = useRef<typeof pomodoroSnapshot | null>(null)
  const lastPomodoroAutoNavigationKeyRef = useRef("")
  const previousLocationRef = useRef(locationToken)
  const subjectNavItems = useMemo(
    () => getSubjectNavItems(resolvedSubjectId),
    [resolvedSubjectId],
  )
  const currentProjectSettingsPath = useMemo(
    () => buildProjectSettingsPath(resolvedSubjectId, currentMaterialProjectId),
    [currentMaterialProjectId, resolvedSubjectId],
  )
  const projectNavItems = useMemo(
    () =>
      hasProjectContext
        ? getProjectNavItems(resolvedSubjectId, currentMaterialProjectId, {
            settingsLabel: "项目设置",
            settingsTo: currentProjectSettingsPath,
          })
        : [],
    [currentMaterialProjectId, currentProjectSettingsPath, hasProjectContext],
  )
  const isAdmin = Boolean(currentUserQ.data?.roles.some((role) => role === "super_admin" || role === "admin"))
  const globalNavItems = useMemo(() => getGlobalNavItems({ includeAdmin: isAdmin, includeMembership: authEnabled }), [authEnabled, isAdmin])
  const globalMenuActive = isNavGroupActive(location.pathname, globalNavItems)
  const subjectMenuActive = isNavGroupActive(location.pathname, subjectNavItems)
  const projectMenuActive = isNavGroupActive(location.pathname, projectNavItems)
  const pomodoroSnapshot = useMemo(
    () => getPomodoroSnapshot({ enabled: pomodoroEnabled, weeklySchedule: pomodoroWeeklySchedule, quickPomodoro: pomodoroQuickPomodoro }, pomodoroNow),
    [pomodoroEnabled, pomodoroNow, pomodoroQuickPomodoro, pomodoroWeeklySchedule],
  )
  const pomodoroUpcomingSegment = useMemo(
    () =>
      getPomodoroUpcomingSegmentPreview({ enabled: pomodoroEnabled, weeklySchedule: pomodoroWeeklySchedule, quickPomodoro: pomodoroQuickPomodoro }, pomodoroNow),
    [pomodoroEnabled, pomodoroNow, pomodoroQuickPomodoro, pomodoroWeeklySchedule],
  )
  const pomodoroAccessibleProjects = useMemo(
    () =>
      isVirtualStudyReviewProject
        ? [
            {
              subjectId: effectiveProjectId,
              projectId: effectiveProjectId,
              title: "学习复习引导示范项目",
            },
          ]
        : subjectProjectCatalog.projects,
    [effectiveProjectId, isVirtualStudyReviewProject, subjectProjectCatalog.projects],
  )
  const pomodoroProjectCatalogReady = !subjectProjectCatalog.isLoading
  const accessibleProjectRefs = useMemo(
    () =>
      new Set(
        pomodoroAccessibleProjects
          .map((project) =>
            project.subjectId ? pomodoroProjectRefKey({ subjectId: project.subjectId, projectId: project.projectId }) : "",
          )
          .filter(Boolean),
      ),
    [pomodoroAccessibleProjects],
  )
  const hasAccessiblePomodoroProjectRef = (projectRef: typeof pomodoroSnapshot.currentProjectRef) =>
    Boolean(projectRef && accessibleProjectRefs.has(pomodoroProjectRefKey(projectRef)))
  const findPomodoroProject = (projectRef: typeof pomodoroSnapshot.currentProjectRef) =>
    projectRef
      ? pomodoroAccessibleProjects.find(
          (project) => project.subjectId === projectRef.subjectId && project.projectId === projectRef.projectId,
        ) ?? null
      : null
  const pomodoroFocusProjectRef = pomodoroSnapshot.currentProjectRef
  const pomodoroFocusProjectId =
    pomodoroProjectCatalogReady && pomodoroFocusProjectRef && hasAccessiblePomodoroProjectRef(pomodoroFocusProjectRef)
      ? pomodoroFocusProjectRef.projectId
      : ""
  const focusProjectTitle =
    pomodoroFocusProjectId ? findPomodoroProject(pomodoroFocusProjectRef)?.title ?? "" : ""
  const pomodoroFocusWorkbenchPath =
    pomodoroFocusProjectRef && pomodoroFocusProjectId
      ? `/subjects/${encodeURIComponent(pomodoroFocusProjectRef.subjectId)}/projects/${encodeURIComponent(pomodoroFocusProjectRef.projectId)}/workbench`
      : "/subjects"
  const upcomingJumpProjectId =
    pomodoroUpcomingSegment?.phase === "focus" &&
    pomodoroUpcomingSegment.projectRef &&
    pomodoroProjectCatalogReady &&
    hasAccessiblePomodoroProjectRef(pomodoroUpcomingSegment.projectRef)
      ? pomodoroUpcomingSegment.projectRef.projectId
      : ""
  const upcomingJumpProjectTitle =
    upcomingJumpProjectId ? findPomodoroProject(pomodoroUpcomingSegment?.projectRef ?? null)?.title ?? "" : ""
  const upcomingJumpSubjectId = pomodoroUpcomingSegment?.phase === "focus" ? pomodoroUpcomingSegment.projectRef?.subjectId ?? "" : ""
  const upcomingJumpPath = upcomingJumpProjectId && upcomingJumpSubjectId ? `/subjects/${upcomingJumpSubjectId}/projects/${upcomingJumpProjectId}/workbench` : ""
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
  const isPomodoroBlockingOtherProjectWorkbench =
    pomodoroSnapshot.status === "running" &&
    pomodoroSnapshot.phase === "focus" &&
    Boolean(pomodoroFocusProjectId) &&
    Boolean(pid) &&
    Boolean(routeSubjectId) &&
    location.pathname.includes("/workbench") &&
    (routeSubjectId !== pomodoroFocusProjectRef?.subjectId || pid !== pomodoroFocusProjectId)
  usePomodoroTransitionSound(pomodoroSnapshot, pomodoroTransitionSoundEnabled)
  useEffect(() => {
    setPomodoroRestMusicPhaseActive(
      pomodoroSnapshot.status === "running" && pomodoroSnapshot.phase === "break",
    )
  }, [pomodoroSnapshot.phase, pomodoroSnapshot.status])
  useEffect(() => {
    if (
      pomodoroSnapshot.status !== "running" ||
      pomodoroSnapshot.phase !== "focus" ||
      !pomodoroSnapshot.currentProjectRef ||
      !pomodoroSnapshot.currentPlan ||
      !pomodoroSnapshot.segment ||
      !pomodoroFocusProjectId ||
      !pomodoroFocusWorkbenchPath ||
      location.pathname === pomodoroFocusWorkbenchPath
    ) {
      return
    }
    const autoNavigationKey = [
      pomodoroSnapshot.currentPlan.id,
      pomodoroSnapshot.currentPlanIndex,
      pomodoroSnapshot.segment.pomodoroIndex,
      pomodoroSnapshot.startAtMs ?? "",
      pomodoroSnapshot.currentProjectRef.subjectId,
      pomodoroSnapshot.currentProjectRef.projectId,
    ].join(":")
    if (lastPomodoroAutoNavigationKeyRef.current === autoNavigationKey) return
    lastPomodoroAutoNavigationKeyRef.current = autoNavigationKey
    nav(pomodoroFocusWorkbenchPath, { replace: location.pathname.startsWith("/pomodoro") })
  }, [
    location.pathname,
    nav,
    pomodoroFocusProjectId,
    pomodoroFocusWorkbenchPath,
    pomodoroSnapshot.currentPlan,
    pomodoroSnapshot.currentPlanIndex,
    pomodoroSnapshot.currentProjectRef,
    pomodoroSnapshot.phase,
    pomodoroSnapshot.segment,
    pomodoroSnapshot.startAtMs,
    pomodoroSnapshot.status,
  ])
  useEffect(() => {
    const previousSnapshot = previousPomodoroSnapshotRef.current
    previousPomodoroSnapshotRef.current = pomodoroSnapshot
    if (!previousSnapshot?.currentPlan || previousSnapshot.startAtMs === null || !previousSnapshot.segment) return
    if (previousSnapshot.status !== "running" || previousSnapshot.phase !== "focus") return

    const focusEndAtMs = previousSnapshot.startAtMs + previousSnapshot.segment.endOffsetMs
    if (pomodoroNow < focusEndAtMs) return

    const pomodoroIndex = previousSnapshot.segment.pomodoroIndex
    const startAtMs = previousSnapshot.startAtMs + previousSnapshot.segment.startOffsetMs
    const endAtMs = focusEndAtMs
    const completedSegmentKey = `${previousSnapshot.currentPlan.id}:${previousSnapshot.currentPlanIndex}:${pomodoroIndex}:${startAtMs}:${endAtMs}`
    if (completedPomodoroSegmentKeyRef.current === completedSegmentKey) return
    completedPomodoroSegmentKeyRef.current = completedSegmentKey
    const fallbackProjectRef = previousSnapshot.currentPlan.projectRefs[pomodoroIndex - 1] ?? null
    const completedProjectRef =
      previousSnapshot.segment.projectRef && hasAccessiblePomodoroProjectRef(previousSnapshot.segment.projectRef)
        ? previousSnapshot.segment.projectRef
        : pomodoroProjectRefKey(previousSnapshot.currentPlan.projectRefs[pomodoroIndex - 1]) &&
            hasAccessiblePomodoroProjectRef(fallbackProjectRef)
          ? fallbackProjectRef
          : null
    recordPomodoroActivity({
      planId: previousSnapshot.currentPlan.id,
      planIndex: previousSnapshot.currentPlanIndex,
      pomodoroIndex,
      projectRef: completedProjectRef,
      startAtMs,
      endAtMs,
    })
  }, [accessibleProjectRefs, pomodoroAccessibleProjects, pomodoroNow, pomodoroSnapshot])
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
    if (!pid || selectedWorkbenchProjectId === pid) return
    setSelectedWorkbenchProjectId(pid)
  }, [pid, selectedWorkbenchProjectId, setSelectedWorkbenchProjectId])

  useEffect(() => {
    void checkFrontendFreshness()
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

  const outletContent = isPomodoroBlockingOtherProjectWorkbench ? (
    <div className="mx-auto max-w-2xl">
      <ErrorNotice
        title="番茄钟正在学习另一个项目"
        message={`当前番茄钟已锁定“${focusProjectTitle || "当前番茄项目"}”，不能进入这个项目工作台。请先完成或停止当前番茄，再切换到其他项目。`}
        action={
          <Button asChild>
            <Link to={pomodoroFocusWorkbenchPath}>进入当前番茄工作台</Link>
          </Button>
        }
      />
    </div>
  ) : (
    <Outlet />
  )

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
                        <div className="p-4">
                          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">账号</div>
                          <div className="mt-3 flex items-center gap-3 px-1">
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
                          <div className="mt-4 border-t border-border/60 pt-3">
                            <div className="grid gap-1">
                              <AccountMenuLink to="/profile" label="个人中心" icon={User} onNavigate={() => setAccountMenuOpen(false)} />
                              <AccountMenuLink to="/friends" label="好友中心" icon={UsersRound} onNavigate={() => setAccountMenuOpen(false)} />
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
        {outletContent}
      </main>
    </div>
  )
}

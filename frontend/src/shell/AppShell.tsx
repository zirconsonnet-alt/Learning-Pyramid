import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react"
import { House, Menu, Sparkles } from "lucide-react"
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate, useParams } from "react-router-dom"

import { MainNav, getGlobalNavItems, getProjectNavItems } from "@/shell/MainNav"
import { ApiError } from "@/ui/api/http"
import { ErrorNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { projectTypeRequiresLearningObjectTree } from "@/ui/projectTypes"
import { useCurrentUser, useLogout } from "@/ui/queries/auth"
import { useProject } from "@/ui/queries/projects"
import { useSystemCapabilities } from "@/ui/queries/system"
import { useProjectConfig } from "@/ui/queries/workbench"
import { useAppStore } from "@/ui/store/appStore"
import { useThemeStore } from "@/ui/store/themeStore"
import { THEME_PRESETS } from "@/ui/theme/themePresets"
import { cn } from "@/ui/utils"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function describeArea(pathname: string, projectTitle: string, hasProject: boolean) {
  if (pathname.startsWith("/projects")) {
    return {
      title: "项目中心",
      context: "浏览与切换项目",
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
        title: "项目工作台",
        context: projectTitle,
      }
    }

    if (pathname.includes("/ai-chat")) {
      return {
        title: "AI问答",
        context: projectTitle,
      }
    }

    if (pathname.includes("/task-tree")) {
      return {
        title: "学习任务树",
        context: projectTitle,
      }
    }

    if (pathname.includes("/object-tree")) {
      return {
        title: "学习对象树",
        context: projectTitle,
      }
    }

    if (pathname.includes("/settings")) {
      return {
        title: "项目设置",
        context: projectTitle,
      }
    }
  }

  return {
    title: "工作空间",
    context: "系统总览",
  }
}

const THEME_PRESET_ACTIVE_BORDER = "#b7a4f6"
const THEME_PRESET_ACTIVE_RING = "0 0 0 1px rgba(183, 164, 246, 0.96)"
const THEME_PRESET_ACTIVE_GLOW = "0 22px 40px -28px rgba(111, 90, 204, 0.54)"
const THEME_PRESET_CURRENT_BADGE_BG = "linear-gradient(135deg, #4b68d8 0%, #2f50b9 100%)"
const THEME_PRESET_CURRENT_BADGE_SHADOW = "0 14px 28px -22px rgba(47, 80, 185, 0.7)"

export function AppShell() {
  const nav = useNavigate()
  const location = useLocation()
  const { projectId } = useParams()
  const pid = projectId ?? ""
  const selectedProjectId = useAppStore((state) => state.selectedProjectId)
  const setSelectedProjectId = useAppStore((state) => state.setSelectedProjectId)
  const effectiveProjectId = pid || selectedProjectId || ""
  const [navMenuOpen, setNavMenuOpen] = useState(false)
  const capabilitiesQ = useSystemCapabilities()
  const authEnabled = capabilitiesQ.data?.authEnabled ?? false
  const currentUserQ = useCurrentUser(authEnabled)
  const canAccessApp = !authEnabled || Boolean(currentUserQ.data)
  const { projectTitle } = useProject(effectiveProjectId, { enabled: canAccessApp && Boolean(effectiveProjectId) })
  const projectConfigQ = useProjectConfig(canAccessApp && effectiveProjectId ? effectiveProjectId : "")
  const logout = useLogout()
  const selectedTheme = useThemeStore((state) => state.theme)
  const setTheme = useThemeStore((state) => state.setTheme)
  const area = describeArea(location.pathname, projectTitle || pid || "当前项目", Boolean(pid))
  const capabilitiesUnavailableError = capabilitiesQ.error && !capabilitiesQ.data ? formatApiError(capabilitiesQ.error) : null
  const currentUserUnavailableError =
    authEnabled && currentUserQ.error && currentUserQ.data === undefined ? formatApiError(currentUserQ.error) : null
  const locationToken = `${location.pathname}${location.search}${location.hash}`
  const menuRef = useRef<HTMLDivElement | null>(null)
  const menuButtonRef = useRef<HTMLButtonElement | null>(null)
  const previousLocationRef = useRef(locationToken)
  const includeObjectTree = projectTypeRequiresLearningObjectTree(projectConfigQ.data?.projectType ?? "COURSE")
  const projectNavItems = useMemo(
    () => getProjectNavItems(effectiveProjectId, { includeObjectTree }),
    [effectiveProjectId, includeObjectTree],
  )
  const hasProjectContext = Boolean(pid)
  const hasRememberedProjectContext = Boolean(effectiveProjectId)
  const isAdmin = Boolean(currentUserQ.data?.roles.some((role) => role === "super_admin" || role === "admin"))
  const globalNavItems = useMemo(() => getGlobalNavItems({ includeAdmin: isAdmin, includeMembership: authEnabled }), [authEnabled, isAdmin])
  const inlineNavItems = globalNavItems
  const menuProjectNavItems = hasRememberedProjectContext ? projectNavItems : []
  const menuGlobalNavItems = hasProjectContext ? [] : globalNavItems

  useEffect(() => {
    if (!pid || selectedProjectId === pid) return
    setSelectedProjectId(pid)
  }, [pid, selectedProjectId, setSelectedProjectId])

  useEffect(() => {
    if (previousLocationRef.current === locationToken) return
    previousLocationRef.current = locationToken
    setNavMenuOpen(false)
  }, [locationToken])

  useEffect(() => {
    if (!navMenuOpen) return

    function onPointerDown(event: MouseEvent | TouchEvent) {
      const target = event.target
      if (!(target instanceof Node)) return
      if (menuRef.current?.contains(target) || menuButtonRef.current?.contains(target)) return
      setNavMenuOpen(false)
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setNavMenuOpen(false)
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
  }, [navMenuOpen])

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
              <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
                <span className="text-[13px] font-semibold tracking-[0.04em] text-[color:var(--theme-soft-text-strong)]">LearningPyramid</span>
                <span className="text-xs text-muted-foreground">/</span>
                <div className="min-w-0 truncate text-sm font-medium tracking-tight text-foreground sm:text-[15px]">{area.title}</div>
              </div>
            </div>

            <div className="flex shrink-0 items-center gap-2">
              <div className="hidden items-center gap-2 sm:flex">
                {inlineNavItems.map((item) => {
                  const Icon = item.icon
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      className={({ isActive }) =>
                        cn(
                          "inline-flex h-9 items-center gap-2 rounded-xl border [border-color:var(--theme-soft-border)] [background:var(--theme-soft-bg)] px-3 text-[13px] text-[color:var(--theme-subtle-text)] [box-shadow:var(--theme-soft-shadow)] transition-colors hover:border-primary/15 hover:text-foreground",
                          isActive && "border-primary/15 bg-[hsl(var(--primary)/0.08)] text-foreground",
                        )
                      }
                    >
                      <Icon className="h-3.5 w-3.5 shrink-0 text-primary" />
                      <span>{item.label}</span>
                    </NavLink>
                  )
                })}
              </div>

              <Button
                ref={menuButtonRef}
                variant="outline"
                size="icon"
                className="h-10 w-10 shrink-0 rounded-xl [border-color:var(--theme-soft-border)] [background:var(--theme-soft-bg)]"
                onClick={() => setNavMenuOpen((current) => !current)}
                aria-expanded={navMenuOpen}
                aria-haspopup="menu"
              >
                <Menu className="h-4.5 w-4.5" />
                <span className="sr-only">打开导航菜单</span>
              </Button>
            </div>

            {navMenuOpen ? (
              <div
                ref={menuRef}
                className="absolute right-0 top-[calc(100%+0.65rem)] z-30 w-[min(22rem,calc(100vw-1rem))] overflow-hidden rounded-[1.6rem] border [border-color:var(--theme-soft-border)] [background:radial-gradient(circle_at_top_left,hsl(var(--primary)/0.08),transparent_34%),var(--theme-card-main-bg)] shadow-[0_24px_60px_-30px_rgba(15,23,42,0.24)] backdrop-blur-2xl"
              >
                <div className="max-h-[min(70vh,calc(100dvh-5.5rem))] overflow-y-auto overscroll-contain p-3 [-webkit-overflow-scrolling:touch]">
                  {authEnabled && currentUserQ.data ? (
                    <div className="theme-soft-surface p-3">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">当前账号</div>
                      <div className="mt-3 flex flex-col items-center text-center">
                        <Link
                          to="/profile"
                          className="group relative inline-flex h-16 w-16 items-center justify-center overflow-hidden rounded-[1.4rem] border [border-color:var(--theme-icon-border)] [background:var(--theme-icon-bg)] text-lg font-semibold [color:var(--theme-icon-text)] transition hover:border-primary/15 hover:shadow-[0_16px_30px_-24px_hsl(var(--primary)/0.28)]"
                          onClick={() => setNavMenuOpen(false)}
                          aria-label="进入个人中心"
                          title="进入个人中心"
                        >
                          {currentUserQ.data.avatarUrl ? (
                            <img src={currentUserQ.data.avatarUrl} alt={currentUserQ.data.nickname} className="h-full w-full object-cover" />
                          ) : (
                            (currentUserQ.data.nickname || currentUserQ.data.email).slice(0, 1).toUpperCase()
                          )}
                        </Link>
                        <Link
                          to="/profile"
                          className="mt-3 block w-full rounded-xl px-2 py-1.5 transition hover:[background:var(--theme-subtle-bg)]"
                          onClick={() => setNavMenuOpen(false)}
                        >
                          <div className="truncate text-sm font-medium text-foreground">{currentUserQ.data.nickname}</div>
                          <div className="mt-1 truncate text-xs text-muted-foreground">{currentUserQ.data.email}</div>
                        </Link>
                      </div>
                      <Button
                        variant="outline"
                        size="sm"
                        className="mt-3 w-full rounded-xl"
                        onClick={() => {
                          setNavMenuOpen(false)
                          void onLogout()
                        }}
                        disabled={logout.isPending}
                      >
                        {logout.isPending ? "退出中..." : "退出登录"}
                      </Button>
                    </div>
                  ) : null}

                  {menuProjectNavItems.length > 0 ? (
                    <div className="theme-soft-surface mt-3 p-3">
                      <div className="flex min-w-0 items-center gap-2">
                        <div className="shrink-0 text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">当前项目</div>
                        <div className="min-w-0 truncate text-sm font-medium text-foreground">{projectTitle || "当前项目"}</div>
                      </div>
                      <div className="mt-3">
                        <MainNav items={menuProjectNavItems} onNavigate={() => setNavMenuOpen(false)} />
                      </div>
                    </div>
                  ) : null}

                  {menuGlobalNavItems.length > 0 ? (
                    <div className="theme-soft-surface mt-3 p-3">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">全局导航</div>
                      <div className="mt-3">
                        <MainNav items={menuGlobalNavItems} onNavigate={() => setNavMenuOpen(false)} />
                      </div>
                    </div>
                  ) : null}

                  <div className="theme-status-surface mt-3 p-3">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">界面主题</div>
                    <div className="mt-3 space-y-2">
                      {THEME_PRESETS.map((theme) => {
                        const isActive = selectedTheme === theme.id
                        const previewCardStyle: CSSProperties = {
                          background: theme.surface.background,
                          borderColor: isActive ? THEME_PRESET_ACTIVE_BORDER : theme.surface.border,
                          boxShadow: isActive
                            ? `${THEME_PRESET_ACTIVE_RING}, ${THEME_PRESET_ACTIVE_GLOW}, ${theme.surface.shadow}`
                            : theme.surface.shadow,
                        }
                        return (
                          <button
                            key={theme.id}
                            type="button"
                            className={cn(
                              "flex w-full items-center justify-between gap-3 rounded-2xl border px-3 py-2.5 text-left transition-all duration-200 hover:-translate-y-px focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#b7a4f6]/70 focus-visible:ring-offset-2 focus-visible:ring-offset-transparent",
                            )}
                            style={previewCardStyle}
                            onClick={() => {
                              setTheme(theme.id)
                              setNavMenuOpen(false)
                            }}
                          >
                            <div className="min-w-0">
                              <div className="text-sm font-medium" style={{ color: theme.surface.title }}>
                                {theme.label}
                              </div>
                              <div className="mt-0.5 text-xs" style={{ color: theme.surface.description }}>
                                {theme.description}
                              </div>
                            </div>
                            <div className="flex shrink-0 items-center gap-2">
                              <div className="flex items-center gap-1.5">
                                {theme.preview.map((color) => (
                                  <span
                                    key={`${theme.id}-${color}`}
                                    className="h-4 w-4 rounded-full shadow-inner"
                                    style={{ backgroundColor: color, border: `1px solid ${theme.surface.swatchBorder}` }}
                                  />
                                ))}
                              </div>
                              {isActive ? (
                                <span
                                  className="inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold text-white"
                                  style={{
                                    borderColor: "rgba(255, 255, 255, 0.22)",
                                    background: THEME_PRESET_CURRENT_BADGE_BG,
                                    boxShadow: THEME_PRESET_CURRENT_BADGE_SHADOW,
                                  }}
                                >
                                  当前
                                </span>
                              ) : null}
                            </div>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </header>

      <main className="container relative z-10 py-5 lg:py-6">
        <Outlet />
      </main>
    </div>
  )
}

import { useEffect, useMemo, useRef, useState } from "react"
import { Menu, Sparkles, Workflow } from "lucide-react"
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate, useParams } from "react-router-dom"

import { GLOBAL_NAV_ITEMS, MainNav, getProjectNavItems } from "@/shell/MainNav"
import { ApiError } from "@/ui/api/http"
import { ErrorNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { useCurrentUser, useLogout } from "@/ui/queries/auth"
import { useProject } from "@/ui/queries/projects"
import { useSystemCapabilities } from "@/ui/queries/system"
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

  if (hasProject) {
    if (pathname.includes("/workbench")) {
      return {
        title: "项目工作台",
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

export function AppShell() {
  const nav = useNavigate()
  const location = useLocation()
  const { projectId } = useParams()
  const pid = projectId ?? ""
  const [navMenuOpen, setNavMenuOpen] = useState(false)
  const capabilitiesQ = useSystemCapabilities()
  const authEnabled = capabilitiesQ.data?.authEnabled ?? false
  const currentUserQ = useCurrentUser(authEnabled)
  const canAccessApp = !authEnabled || Boolean(currentUserQ.data)
  const { projectTitle } = useProject(pid, { enabled: canAccessApp })
  const logout = useLogout()
  const area = describeArea(location.pathname, projectTitle || pid || "当前项目", Boolean(pid))
  const deploymentLabel = capabilitiesQ.data?.appMode === "hosted" ? "托管模式" : "本地模式"
  const areaContext = area.context && area.context !== area.title ? area.context : null
  const capabilitiesUnavailableError = capabilitiesQ.error && !capabilitiesQ.data ? formatApiError(capabilitiesQ.error) : null
  const currentUserUnavailableError =
    authEnabled && currentUserQ.error && currentUserQ.data === undefined ? formatApiError(currentUserQ.error) : null
  const menuRef = useRef<HTMLDivElement | null>(null)
  const menuButtonRef = useRef<HTMLButtonElement | null>(null)
  const projectNavItems = useMemo(() => getProjectNavItems(pid), [pid])

  useEffect(() => {
    setNavMenuOpen(false)
  }, [location.hash, location.pathname, location.search])

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
      <div className="pointer-events-none fixed inset-x-0 top-0 z-0 h-72 bg-[radial-gradient(circle_at_top,_rgba(216,226,238,0.18),_transparent_54%)]" />
      <header className="sticky top-0 z-20 border-b border-[#e4e9ef] bg-white/92 shadow-[0_16px_40px_-34px_rgba(15,23,42,0.22)] backdrop-blur-2xl supports-[backdrop-filter]:bg-white/86">
        <div className="container py-3 sm:py-4">
          <div className="relative flex w-full items-center gap-3 sm:gap-4">
            <Link
              to="/projects"
              className="inline-flex h-12 w-12 shrink-0 items-center justify-center rounded-[1.35rem] bg-[linear-gradient(160deg,#294f79,#1b3556)] text-primary-foreground shadow-[0_18px_38px_-28px_rgba(15,23,42,0.46)] transition-all hover:-translate-y-px hover:shadow-[0_22px_44px_-28px_rgba(15,23,42,0.52)]"
              aria-label="返回项目中心"
            >
              <Workflow className="h-5 w-5" />
            </Link>

            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2 text-xs text-[#6a7e98]">
                <span className="font-semibold tracking-[0.03em] text-[#465a74]">LearningPyramid</span>
                <span className="inline-flex items-center rounded-full border border-[#e0e6ed] bg-[#f7f9fb] px-2 py-0.5 text-[11px] font-medium text-[#66798e]">
                  {deploymentLabel}
                </span>
              </div>
              <div className="mt-1.5 min-w-0">
                <div className="truncate text-base font-semibold tracking-tight text-foreground sm:text-lg">{area.title}</div>
                {areaContext ? <div className="mt-0.5 truncate text-sm text-[#6a7e98]">{areaContext}</div> : null}
              </div>
            </div>

            <div className="flex shrink-0 items-center gap-2">
              {GLOBAL_NAV_ITEMS.map((item) => {
                const Icon = item.icon
                return (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    className={({ isActive }) =>
                      cn(
                        "inline-flex h-10 items-center gap-2 rounded-2xl border border-[#e3e8ef] bg-white px-2.5 text-sm text-[#5b6b82] shadow-[0_14px_28px_-24px_rgba(15,23,42,0.16)] transition-colors hover:border-primary/15 hover:text-foreground min-[420px]:px-3.5",
                        isActive && "border-primary/15 bg-[#eef5ff] text-foreground",
                      )
                    }
                  >
                    <Icon className="h-4 w-4 shrink-0 text-primary" />
                    <span className="hidden min-[420px]:inline">{item.label}</span>
                    <span className="sr-only min-[420px]:hidden">{item.label}</span>
                  </NavLink>
                )
              })}

              <Button
                ref={menuButtonRef}
                variant="outline"
                size="icon"
                className="h-11 w-11 shrink-0 rounded-2xl border-[#e3e8ef] bg-white"
                onClick={() => setNavMenuOpen((current) => !current)}
                aria-expanded={navMenuOpen}
                aria-haspopup="menu"
              >
                <Menu className="h-5 w-5" />
                <span className="sr-only">打开项目菜单</span>
              </Button>
            </div>

            {navMenuOpen ? (
              <div
                ref={menuRef}
                className="absolute right-0 top-[calc(100%+0.65rem)] z-30 w-[min(22rem,calc(100vw-1rem))] overflow-hidden rounded-[1.6rem] border border-[#e3e8ef] bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(246,248,251,0.96))] shadow-[0_24px_60px_-30px_rgba(15,23,42,0.24)] backdrop-blur-2xl"
              >
                <div className="max-h-[min(70vh,calc(100dvh-5.5rem))] overflow-y-auto overscroll-contain p-3 [-webkit-overflow-scrolling:touch]">
                  {pid ? (
                    <>
                      <div className="px-2 pb-2 pt-1">
                        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#73839a]">当前项目</div>
                        <div className="mt-1 truncate text-sm font-semibold text-foreground">{projectTitle || pid}</div>
                      </div>
                      <MainNav items={projectNavItems} onNavigate={() => setNavMenuOpen(false)} />
                    </>
                  ) : (
                    <div className="rounded-2xl border border-dashed border-border/70 bg-[#f8fafc] px-4 py-3 text-sm text-muted-foreground">
                      当前没有项目上下文。
                    </div>
                  )}

                  {authEnabled && currentUserQ.data ? (
                    <div className="mt-3 rounded-[1.25rem] border border-[#e3e8ef] bg-white p-3">
                      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#6a7e98]">当前账号</div>
                      <div className="mt-1 truncate text-sm font-medium text-foreground">{currentUserQ.data.email}</div>
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
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </header>

      <main className="container relative z-10 py-6 lg:py-8">
        <Outlet />
      </main>
    </div>
  )
}

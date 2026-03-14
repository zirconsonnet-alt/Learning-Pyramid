import { useState } from "react"
import { FolderKanban, Menu, RadioTower, Sparkles, Workflow, X } from "lucide-react"
import { Link, Navigate, Outlet, useLocation, useNavigate, useParams } from "react-router-dom"

import { MainNav } from "@/shell/MainNav"
import { ApiError } from "@/ui/api/http"
import { ErrorNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/ui/components/ui/dialog"
import { useCurrentUser, useLogout } from "@/ui/queries/auth"
import { useProject } from "@/ui/queries/projects"
import { useSystemCapabilities } from "@/ui/queries/system"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function describeArea(pathname: string, projectTitle: string, hasProject: boolean) {
  if (pathname.startsWith("/projects")) {
    return {
      eyebrow: "Project Hub",
      title: "项目中心",
      description: "从一个统一入口管理项目、切换工作区，并进入当前协作流程。",
      icon: FolderKanban,
    }
  }

  if (pathname.startsWith("/guide")) {
    return {
      eyebrow: "Guide",
      title: "产品指南",
      description: "查看系统能力、操作约定和桌面连接器接入说明。",
      icon: Sparkles,
    }
  }

  if (pathname.startsWith("/system/desktop-agent")) {
    return {
      eyebrow: "Desktop Agent",
      title: "桌面连接器",
      description: "管理本地素材接入、桌面安装包和配对会话。",
      icon: Workflow,
    }
  }

  if (pathname.startsWith("/system/relay-monitor")) {
    return {
      eyebrow: "Relay Monitor",
      title: "中继运营台",
      description: "巡检 HLS、桌面连接器和中继链路的运行健康度。",
      icon: RadioTower,
    }
  }

  if (hasProject) {
    if (pathname.includes("/workbench")) {
      return {
        eyebrow: "Workbench",
        title: projectTitle,
        description: "围绕当前项目完成播放、抽取、复习和生成等核心工作流。",
        icon: Workflow,
      }
    }

    if (pathname.includes("/task-tree")) {
      return {
        eyebrow: "Task Tree",
        title: `${projectTitle} · 学习任务树`,
        description: "维护任务结构、层级关系和执行路径。",
        icon: Workflow,
      }
    }

    if (pathname.includes("/object-tree")) {
      return {
        eyebrow: "Object Tree",
        title: `${projectTitle} · 学习对象树`,
        description: "审视内容结构、绑定节点和知识对象脉络。",
        icon: Workflow,
      }
    }

    if (pathname.includes("/timeline")) {
      return {
        eyebrow: "Timeline",
        title: `${projectTitle} · 时间线`,
        description: "从时间维度查看处理进度、聚合事件和回放节点。",
        icon: Workflow,
      }
    }

    if (pathname.includes("/settings")) {
      return {
        eyebrow: "Settings",
        title: `${projectTitle} · 项目设置`,
        description: "集中管理项目配置、素材源和系统集成参数。",
        icon: Workflow,
      }
    }
  }

  return {
    eyebrow: "LearningPyramid",
    title: "工作空间",
    description: "统一进入项目、工作台和系统能力页面。",
    icon: Sparkles,
  }
}

export function AppShell() {
  const nav = useNavigate()
  const location = useLocation()
  const { projectId } = useParams()
  const pid = projectId ?? ""
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const capabilitiesQ = useSystemCapabilities()
  const authEnabled = capabilitiesQ.data?.authEnabled ?? false
  const currentUserQ = useCurrentUser(authEnabled)
  const canAccessApp = !authEnabled || Boolean(currentUserQ.data)
  const { projectTitle } = useProject(pid, { enabled: canAccessApp })
  const logout = useLogout()
  const area = describeArea(location.pathname, projectTitle || pid || "当前项目", Boolean(pid))
  const AreaIcon = area.icon
  const modeLabel = capabilitiesQ.data?.appMode === "hosted" ? "Hosted" : "Local"
  const capabilitiesUnavailableError = capabilitiesQ.error && !capabilitiesQ.data ? formatApiError(capabilitiesQ.error) : null
  const currentUserUnavailableError =
    authEnabled && currentUserQ.error && currentUserQ.data === undefined ? formatApiError(currentUserQ.error) : null

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
      <div className="pointer-events-none fixed inset-x-0 top-0 z-0 h-72 bg-[radial-gradient(circle_at_top_left,_rgba(193,214,242,0.62),_transparent_42%),radial-gradient(circle_at_top_right,_rgba(224,233,247,0.54),_transparent_34%)]" />
      <header className="sticky top-0 z-20 border-b border-white/70 bg-white/82 shadow-[0_16px_40px_-34px_rgba(15,23,42,0.46)] backdrop-blur-2xl supports-[backdrop-filter]:bg-white/72">
        <div className="container py-3 sm:py-4">
          <div className="flex items-center gap-3 sm:hidden">
            <Link
              to="/projects"
              className="inline-flex shrink-0 items-center justify-center rounded-2xl border border-white/80 bg-white/88 p-2 shadow-[0_18px_34px_-28px_rgba(15,23,42,0.3)] transition-colors hover:border-primary/15 hover:text-primary"
            >
              <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-[0_18px_36px_-24px_rgba(30,58,95,0.72)]">
                <Workflow className="h-5 w-5" />
              </span>
            </Link>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#6a7e98]">
                <span className="truncate">{area.eyebrow}</span>
                <span className="h-1 w-1 rounded-full bg-[#9aa9bd]" />
                <span>{modeLabel}</span>
              </div>
              <div className="mt-1 flex min-w-0 items-center gap-2">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-2xl bg-[#edf4ff] text-primary">
                  <AreaIcon className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <div className="truncate text-base font-semibold tracking-tight text-foreground">{area.title}</div>
                  {pid ? <div className="truncate text-xs text-[#6a7e98]">{projectTitle || pid}</div> : null}
                </div>
              </div>
            </div>
            <Button
              variant="outline"
              size="icon"
              className="h-11 w-11 shrink-0 rounded-2xl border-white/80 bg-white/88"
              onClick={() => setMobileMenuOpen(true)}
            >
              <Menu className="h-5 w-5" />
              <span className="sr-only">打开导航菜单</span>
            </Button>
          </div>

          <div className="hidden flex-col gap-3 sm:flex sm:gap-4">
            <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
              <div className="flex min-w-0 items-start gap-3">
                <Link
                  to="/projects"
                  className="inline-flex shrink-0 items-center gap-3 rounded-2xl border border-white/80 bg-white/82 px-2.5 py-2 shadow-[0_18px_34px_-28px_rgba(15,23,42,0.3)] transition-colors hover:border-primary/15 hover:text-primary sm:px-3.5"
                >
                  <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-[0_18px_36px_-24px_rgba(30,58,95,0.72)]">
                    <Workflow className="h-5 w-5" />
                  </span>
                  <span className="hidden min-w-0 sm:block">
                    <span className="block text-sm font-semibold tracking-tight">LearningPyramid</span>
                    <span className="block text-xs text-muted-foreground">内容工作流与学习对象操作台</span>
                  </span>
                </Link>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="theme-meta-strong">{area.eyebrow}</div>
                    {pid ? <div className="theme-meta min-w-0 max-w-[12rem] truncate sm:max-w-[20rem]">{projectTitle || pid}</div> : null}
                    <div className="theme-meta hidden sm:inline-flex">{modeLabel}</div>
                  </div>
                  <div className="mt-2 flex items-start gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-[#edf4ff] text-primary shadow-[0_14px_30px_-24px_rgba(30,58,95,0.45)]">
                      <AreaIcon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <h1 className="truncate text-base font-semibold tracking-tight text-foreground sm:text-lg">{area.title}</h1>
                      <p className="mt-1 hidden max-w-3xl text-sm leading-6 text-[#5f7188] lg:block">{area.description}</p>
                    </div>
                  </div>
                </div>
              </div>
              {authEnabled && currentUserQ.data ? (
                <div className="theme-status-surface flex items-center justify-between gap-3 px-3 py-2.5 sm:px-4">
                  <div className="min-w-0">
                    <div className="hidden text-[11px] font-semibold uppercase tracking-[0.16em] text-[#6a7e98] sm:block">当前账号</div>
                    <div className="max-w-[14rem] truncate text-sm font-medium text-foreground sm:max-w-[18rem]">{currentUserQ.data.email}</div>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => void onLogout()} disabled={logout.isPending}>
                    {logout.isPending ? "退出中..." : "退出登录"}
                  </Button>
                </div>
              ) : null}
            </div>
            <MainNav />
          </div>
        </div>
      </header>

      <Dialog open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
        <DialogContent
          hideClose
          className="left-0 top-0 z-50 h-[100dvh] w-full max-w-none translate-x-0 translate-y-0 rounded-none border-0 bg-[linear-gradient(180deg,rgba(246,249,255,0.98),rgba(241,245,251,0.96))] p-0 shadow-none sm:hidden"
        >
          <div className="flex h-full flex-col overflow-hidden">
            <div className="border-b border-white/80 bg-white/86 px-5 pb-5 pt-[max(1rem,env(safe-area-inset-top))] shadow-[0_16px_40px_-34px_rgba(15,23,42,0.32)] backdrop-blur-2xl">
              <div className="flex items-start justify-between gap-3">
                <DialogHeader className="min-w-0 flex-1 text-left">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#6a7e98]">Global Navigation</div>
                  <DialogTitle className="mt-3 flex items-center gap-3 text-left text-lg">
                    <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-[0_18px_36px_-24px_rgba(30,58,95,0.72)]">
                      <AreaIcon className="h-4 w-4" />
                    </span>
                    <span className="min-w-0">
                      <span className="block truncate">{area.title}</span>
                      <span className="block text-xs font-medium tracking-normal text-[#6a7e98]">{area.eyebrow}</span>
                    </span>
                  </DialogTitle>
                  <DialogDescription className="mt-3 text-left leading-6 text-[#5f7188]">{area.description}</DialogDescription>
                </DialogHeader>
                <Button variant="outline" size="icon" className="mt-0.5 h-11 w-11 shrink-0 rounded-2xl bg-white/92" onClick={() => setMobileMenuOpen(false)}>
                  <X className="h-5 w-5" />
                  <span className="sr-only">关闭导航菜单</span>
                </Button>
              </div>

              <div className="mt-5 flex flex-wrap items-center gap-2">
                <div className="theme-meta">{modeLabel}</div>
                {pid ? <div className="theme-meta max-w-full truncate">{projectTitle || pid}</div> : null}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto px-5 pb-[max(1.5rem,env(safe-area-inset-bottom))] pt-5">
              {authEnabled && currentUserQ.data ? (
                <div className="theme-status-surface flex items-center justify-between gap-3 px-4 py-3">
                  <div className="min-w-0">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#6a7e98]">当前账号</div>
                    <div className="truncate text-sm font-medium text-foreground">{currentUserQ.data.email}</div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setMobileMenuOpen(false)
                      void onLogout()
                    }}
                    disabled={logout.isPending}
                  >
                    {logout.isPending ? "退出中..." : "退出登录"}
                  </Button>
                </div>
              ) : null}

              <div className="mt-5">
                <MainNav variant="drawer" onNavigate={() => setMobileMenuOpen(false)} />
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <main className="container relative z-10 py-6 lg:py-8">
        <Outlet />
      </main>
    </div>
  )
}

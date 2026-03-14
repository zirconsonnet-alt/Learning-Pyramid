import { useMemo, useState } from "react"
import { ArrowRight, FolderKanban, RadioTower, ShieldCheck, Workflow } from "lucide-react"
import { Navigate, useLocation, useNavigate } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useCurrentUser, useLogin, useRegister } from "@/ui/queries/auth"
import { useSystemCapabilities } from "@/ui/queries/system"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"

type AuthMode = "login" | "register"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "Unknown error"
}

function resolveReturnTo(state: unknown): string {
  if (!state || typeof state !== "object") return "/projects"
  const value = (state as Record<string, unknown>).from
  return typeof value === "string" && value.trim() ? value : "/projects"
}

export function AuthPage() {
  const nav = useNavigate()
  const location = useLocation()
  const capabilitiesQ = useSystemCapabilities()
  const authEnabled = capabilitiesQ.data?.authEnabled ?? false
  const allowSignup = capabilitiesQ.data?.allowSignup ?? false
  const currentUserQ = useCurrentUser(authEnabled)
  const login = useLogin()
  const register = useRegister()
  const [mode, setMode] = useState<AuthMode>("login")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const returnTo = useMemo(() => resolveReturnTo(location.state), [location.state])
  const effectiveMode: AuthMode = allowSignup ? mode : "login"
  const passwordValid = effectiveMode === "register" ? password.length >= 8 : password.length > 0
  const deploymentMode = capabilitiesQ.data?.appMode === "hosted" ? "Hosted Workspace" : "Local Workspace"
  const authNarrative =
    capabilitiesQ.data?.appMode === "hosted"
      ? "通过受保护的入口进入项目、桌面连接器和 Relay Monitor，管理远程素材与回放链路。"
      : "登录后进入本地工作空间，浏览器直接读取素材并管理学习对象、任务和回放。"
  const featureCards =
    capabilitiesQ.data?.appMode === "hosted"
      ? [
          { title: "受保护协作", description: "统一登录后再进入项目、设置和工作台。", icon: ShieldCheck },
          { title: "桌面素材接入", description: "用 Desktop Agent 把本地媒体目录映射到当前项目。", icon: Workflow },
          { title: "中继巡检", description: "用 Relay Monitor 持续观察 HLS、探测和桌面链路健康。", icon: RadioTower },
        ]
      : [
          { title: "项目工作流", description: "从一个入口进入任务、对象树、时间线和工作台。", icon: FolderKanban },
          { title: "浏览器本地媒体", description: "直接读取本机素材并进入播放、复习与生成链路。", icon: Workflow },
          { title: "账号保护", description: "登录态统一管理项目访问与后续操作权限。", icon: ShieldCheck },
        ]
  const capabilitiesUnavailableError = capabilitiesQ.error && !capabilitiesQ.data ? formatApiError(capabilitiesQ.error) : null
  const currentUserUnavailableError =
    authEnabled && currentUserQ.error && currentUserQ.data === undefined ? formatApiError(currentUserQ.error) : null

  if (capabilitiesQ.isLoading || (authEnabled && currentUserQ.isLoading)) {
    return (
      <div className="flex min-h-dvh items-center justify-center px-6">
        <div className="w-full max-w-md">
          <LoadingNotice title="正在检查登录状态" message="正在确认当前部署能力和账号会话，请稍候。" />
        </div>
      </div>
    )
  }

  if (capabilitiesUnavailableError) {
    return (
      <div className="flex min-h-dvh items-center justify-center px-6">
        <div className="w-full max-w-md">
          <ErrorNotice
            title="暂时无法确认部署能力"
            message={`当前无法确认这套部署是否启用了登录与 hosted 能力。${capabilitiesUnavailableError}`}
            action={
              <Button onClick={() => void capabilitiesQ.refetch()}>
                重试
              </Button>
            }
          />
        </div>
      </div>
    )
  }

  if (currentUserUnavailableError) {
    return (
      <div className="flex min-h-dvh items-center justify-center px-6">
        <div className="w-full max-w-md">
          <ErrorNotice
            title="暂时无法确认登录状态"
            message={`身份会话检查没有完成，系统不会把这次失败误判成“未登录”。${currentUserUnavailableError}`}
            action={
              <Button onClick={() => void currentUserQ.refetch()}>
                重新检查
              </Button>
            }
          />
        </div>
      </div>
    )
  }

  if (!authEnabled) {
    return <Navigate to="/projects" replace />
  }

  if (currentUserQ.data) {
    return <Navigate to={returnTo} replace />
  }

  async function onSubmit() {
    const payload = { email: email.trim(), password }
    if (!payload.email || !payload.password) return
    try {
      if (effectiveMode === "register") {
        await register.mutateAsync(payload)
        showSuccessFeedback("账号已创建", "注册成功，正在进入你的项目工作区。")
      } else {
        await login.mutateAsync(payload)
        showSuccessFeedback("登录成功", "身份验证已完成，正在恢复你的工作区。")
      }
      nav(returnTo, { replace: true })
    } catch (err) {
      showErrorFeedback(effectiveMode === "register" ? "注册失败" : "登录失败", formatApiError(err))
    }
  }

  const submitError = effectiveMode === "register" ? register.error : login.error
  const pending = effectiveMode === "register" ? register.isPending : login.isPending

  return (
    <div className="relative min-h-dvh overflow-hidden bg-[radial-gradient(circle_at_top_left,_rgba(190,212,243,0.56),_transparent_38%),radial-gradient(circle_at_80%_20%,_rgba(228,236,248,0.5),_transparent_32%),linear-gradient(180deg,_#f7fafe_0%,_#eef3f8_100%)]">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-72 bg-[linear-gradient(180deg,_rgba(255,255,255,0.6),_rgba(255,255,255,0))]" />
      <div className="relative mx-auto grid min-h-dvh w-full max-w-7xl gap-12 px-6 py-10 lg:grid-cols-[minmax(0,1.15fr)_minmax(360px,460px)] lg:items-center lg:px-10">
        <section className="flex flex-col justify-center space-y-8">
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className="theme-meta-strong">{deploymentMode}</span>
              {returnTo !== "/projects" ? <span className="theme-meta">登录后将返回上次页面</span> : null}
            </div>
            <div className="space-y-4">
              <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[#6d7e95]">LearningPyramid</p>
              <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-foreground lg:text-[3.4rem] lg:leading-[1.05]">
                把项目、素材接入、学习对象和回放链路放进同一个工作空间。
              </h1>
              <p className="max-w-2xl text-base leading-7 text-[#5f7188]">{authNarrative}</p>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            {featureCards.map((item) => {
              const Icon = item.icon
              return (
                <div key={item.title} className="theme-card-main flex h-full flex-col gap-4 p-5">
                  <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#edf4ff] text-primary shadow-[0_18px_34px_-26px_rgba(30,58,95,0.4)]">
                    <Icon className="h-5 w-5" />
                  </div>
                  <div className="space-y-2">
                    <h2 className="text-base font-semibold text-foreground">{item.title}</h2>
                    <p className="text-sm leading-6 text-[#60728a]">{item.description}</p>
                  </div>
                </div>
              )
            })}
          </div>

          <div className="theme-status-surface max-w-2xl px-5 py-4">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-[0_18px_34px_-24px_rgba(30,58,95,0.5)]">
                <ArrowRight className="h-4 w-4" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">登录后直接进入项目工作区</p>
                <p className="text-sm text-muted-foreground">
                  账号只负责保护访问权限；具体的媒体接入和项目配置会在进入系统后继续完成。
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="flex items-center justify-center lg:justify-end">
          <Card className="w-full max-w-md border-white/85 bg-white/92 shadow-[0_30px_90px_-42px_rgba(15,23,42,0.4)]">
            <CardHeader className="space-y-4">
              <div className="space-y-2">
                <CardTitle className="text-[1.45rem]">进入工作空间</CardTitle>
                <CardDescription>
                  {effectiveMode === "register" ? "创建账号后立刻进入项目空间。" : "使用账号进入项目、工作台与系统能力页。"}
                </CardDescription>
              </div>
              <div className="rounded-2xl border border-border/70 bg-[#f4f7fb] p-1">
                <div className="grid grid-cols-2 gap-1">
                  <Button variant={effectiveMode === "login" ? "default" : "ghost"} onClick={() => setMode("login")} className="w-full">
                    登录
                  </Button>
                  {allowSignup ? (
                    <Button variant={effectiveMode === "register" ? "default" : "ghost"} onClick={() => setMode("register")} className="w-full">
                      注册
                    </Button>
                  ) : (
                    <div className="flex items-center justify-center rounded-xl px-4 text-sm text-muted-foreground">未开放注册</div>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <form
                className="space-y-4"
                onSubmit={(event) => {
                  event.preventDefault()
                  void onSubmit()
                }}
              >
                <div className="grid gap-2">
                  <Label htmlFor="email">邮箱</Label>
                  <Input
                    id="email"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                  />
                </div>
                <div className="grid gap-2">
                  <div className="flex items-center justify-between gap-3">
                    <Label htmlFor="password">密码</Label>
                    {effectiveMode === "register" ? <span className="text-xs text-muted-foreground">至少 8 位</span> : null}
                  </div>
                  <Input
                    id="password"
                    type="password"
                    autoComplete={effectiveMode === "register" ? "new-password" : "current-password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={effectiveMode === "register" ? "至少 8 位" : "输入当前密码"}
                  />
                </div>
                <Button type="submit" disabled={pending || !email.trim() || !passwordValid} className="w-full">
                  {pending ? (effectiveMode === "register" ? "注册中..." : "登录中...") : effectiveMode === "register" ? "注册并进入" : "登录"}
                </Button>
                {submitError ? <p className="text-sm text-destructive">{formatApiError(submitError)}</p> : null}
                {!allowSignup ? <p className="text-sm text-muted-foreground">当前部署未开放公开注册。</p> : null}
              </form>
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  )
}

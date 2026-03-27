import { useEffect, useMemo, useState } from "react"
import { ArrowRight, CheckCircle2, CreditCard, FolderKanban, Gift, ShieldCheck, Sparkles, Workflow } from "lucide-react"
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useCurrentUser, useLogin, useRegister } from "@/ui/queries/auth"
import { useSystemCapabilities } from "@/ui/queries/system"
import { usePageMeta } from "@/ui/seo/usePageMeta"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"

type AuthMode = "login" | "register"

const systemPanels = [
  {
    route: "/projects",
    title: "项目工作区",
    description: "继续项目、对象树和任务推进，不再重新找入口。",
  },
  {
    route: "/membership",
    title: "会员中心",
    description: "首单价格、优惠券、邀请码和订单状态在同一页里完成。",
  },
  {
    route: "/admin/membership",
    title: "会员后台",
    description: "如果你具备管理员权限，可以继续看单、同步支付和退款回滚。",
  },
] as const

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function resolveReturnTo(state: unknown): string {
  if (!state || typeof state !== "object") return "/projects"
  const value = (state as Record<string, unknown>).from
  return typeof value === "string" && value.trim() ? value : "/projects"
}

function describeReturnTo(path: string): string {
  if (path === "/projects") return "项目工作区"
  if (path === "/membership") return "会员中心"
  if (path.startsWith("/admin/membership")) return "后台会员工作台"
  if (path.startsWith("/admin")) return "管理后台"
  if (path.startsWith("/p/")) return "上次项目页面"
  return path
}

export function AuthPage() {
  const nav = useNavigate()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const capabilitiesQ = useSystemCapabilities()
  const authEnabled = capabilitiesQ.data?.authEnabled ?? false
  const allowSignup = capabilitiesQ.data?.allowSignup ?? false
  const currentUserQ = useCurrentUser(authEnabled)
  const login = useLogin()
  const register = useRegister()
  const requestedMode = searchParams.get("mode") === "register" ? "register" : "login"
  const [mode, setMode] = useState<AuthMode>(requestedMode)
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [inviteCode, setInviteCode] = useState("")
  const returnTo = useMemo(() => resolveReturnTo(location.state), [location.state])
  const returnToLabel = useMemo(() => describeReturnTo(returnTo), [returnTo])
  const effectiveMode: AuthMode = allowSignup ? mode : "login"
  const passwordValid = effectiveMode === "register" ? password.length >= 8 : password.length > 0
  const deploymentMode = capabilitiesQ.data?.appMode === "hosted" ? "云端工作区" : "本地工作区"
  const authNarrative =
    capabilitiesQ.data?.appMode === "hosted"
      ? "通过受保护的入口进入项目、设置和工作台，集中管理云端学习流程。"
      : "登录后进入本地工作空间，浏览器直接读取素材并管理学习对象、任务和回放。"
  useEffect(() => {
    setMode(allowSignup ? requestedMode : "login")
  }, [allowSignup, requestedMode])

  const heroTitle =
    effectiveMode === "register" ? "先创建账号，再把项目、会员和邀请奖励一次接好。" : "回到你的项目、会员和运营节奏里。"
  const heroDescription =
    effectiveMode === "register"
      ? `${authNarrative} 创建完成后你就能进入项目空间，也能马上接住首单会员和邀请奖励链路。`
      : `${authNarrative} 这次登录不是只过一道门，而是把上一次的项目、会员和运营上下文接回来。`
  const featureCards =
    effectiveMode === "register"
      ? [
          { title: "创建后立刻进项目区", description: "账号建立完成后直接进入项目工作空间，不会停在空白页。", icon: FolderKanban },
          { title: "首单会员 14.9 元", description: "首单价格和会员权益已经接进产品里，不是额外的收银页。", icon: CreditCard },
          { title: "邀请成功返 5 元券", description: "邀请码、优惠券和后续复购链路已经打通，注册时就能接住。", icon: Gift },
        ]
      : [
          { title: "受保护入口", description: "登录态统一管理项目访问与后续操作权限，避免入口散掉。", icon: ShieldCheck },
          { title: "继续项目工作流", description: "项目、对象树、任务和工作台在同一个账号下恢复。", icon: Workflow },
          { title: "会员与订单不断层", description: "订单、支付同步、退款回滚和后台运营都在同一套系统里。", icon: Sparkles },
        ]
  const journeyCards =
    effectiveMode === "register"
      ? [
          { title: "创建账号", description: "邮箱、密码和邀请码一次填完，账号创建后立即进入工作空间。" },
          { title: "进入项目区", description: "从 `/projects` 开始创建项目、推进对象树和任务链路。" },
          { title: "启动会员转化", description: "首单 14.9 元，邀请成功返 5 元券，注册后就能继续购买动作。" },
        ]
      : [
          { title: "验证身份", description: "恢复受保护入口，而不是把你留在一个单独的登录页。" },
          { title: "回到上次页面", description: `当前登录完成后会优先返回${returnToLabel}，减少重找路径。` },
          { title: "继续运营动作", description: "项目、会员、订单与后台处理动作会在同一条链路里继续。" },
        ]
  const spotlightTitle = effectiveMode === "register" ? "这一轮注册同时把第一次转化也接住" : "这次登录会把哪些工作面板接回来"
  const spotlightRows =
    effectiveMode === "register"
      ? [
          { label: "标准月会员", value: "19.9 元" },
          { label: "新用户首单", value: "14.9 元" },
          { label: "邀请成功奖励", value: "5 元券" },
        ]
      : [
          { label: "默认返回", value: returnToLabel },
          { label: "系统能力", value: "项目 + 会员 + 订单" },
          { label: "后台处置", value: "同步支付 / 关单 / 退款" },
        ]
  const formSummaryTitle =
    effectiveMode === "register" ? "创建后立即进入项目空间，也能继续会员首单链路。" : `验证完成后会优先返回${returnToLabel}。`
  const formSummaryBody =
    effectiveMode === "register"
      ? "邀请码可选填；首单会员 14.9 元，邀请成功后返 5 元券，首单和续费都能用。"
      : "登录不是终点，而是把项目、会员和后台运营重新接回你上次停下来的地方。"
  const formTags =
    effectiveMode === "register"
      ? ["首单 14.9 元", "邀请码可选填", "奖励 5 元券"]
      : [returnToLabel, "受保护入口", "恢复工作区"]
  usePageMeta({
    title: effectiveMode === "register" ? "注册 | LearningPyramid" : "登录 | LearningPyramid",
    description:
      effectiveMode === "register"
        ? "创建账号后进入 LearningPyramid 工作空间，继续使用项目、会员与后台运营能力。"
        : "登录 LearningPyramid，进入项目、工作台、会员与后台运营工作空间。",
    path: "/login",
  })
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

  function switchMode(nextMode: AuthMode) {
    if (nextMode === "register" && !allowSignup) return
    setMode(nextMode)
    const nextParams = new URLSearchParams(searchParams)
    if (nextMode === "register") nextParams.set("mode", "register")
    else nextParams.delete("mode")
    setSearchParams(nextParams, { replace: true })
  }

  async function onSubmit() {
    const payload = { email: email.trim(), password, inviteCode: inviteCode.trim() || undefined }
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
              <span className="theme-meta">{effectiveMode === "register" ? "公开注册转化入口" : "受保护登录入口"}</span>
              <span className="theme-meta">{returnTo !== "/projects" ? `登录后返回${returnToLabel}` : "默认进入项目工作区"}</span>
            </div>
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <p className="text-sm font-semibold uppercase tracking-[0.22em] text-[#6d7e95]">LearningPyramid</p>
                <Link
                  to="/"
                  className="inline-flex items-center rounded-full border border-[#d5e1ee] bg-white/70 px-3 py-1 text-xs font-medium text-[#58708a] transition hover:border-[#c0d4e8] hover:text-[#16395f]"
                >
                  返回首页
                </Link>
              </div>
              <h1 className="max-w-3xl text-4xl font-semibold tracking-tight text-foreground lg:text-[3.4rem] lg:leading-[1.05]">
                {heroTitle}
              </h1>
              <p className="max-w-2xl text-base leading-7 text-[#5f7188]">{heroDescription}</p>
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

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.12fr)_minmax(280px,0.88fr)]">
            <div className="theme-card-main p-6">
              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#7a8da6]">
                  {effectiveMode === "register" ? "Onboarding flow" : "Return path"}
                </p>
                <h2 className="text-2xl font-semibold tracking-tight text-foreground">
                  {effectiveMode === "register" ? "第一次进来，不应该只看到一张表单。" : "这次登录之后，系统会立刻把你接回工作流。"}
                </h2>
                <p className="max-w-2xl text-sm leading-7 text-[#60728a]">
                  {effectiveMode === "register"
                    ? "从创建账号开始，就把项目入口、会员首单和邀请奖励讲清楚，用户不需要先登录再慢慢理解产品。"
                    : "账号只是恢复访问边界的一步。真正重要的是，项目、会员、订单和后台处置动作会继续保持在同一条链路里。"}
                </p>
              </div>

              <div className="mt-5 grid gap-3 md:grid-cols-3">
                {journeyCards.map((item, index) => (
                  <div key={item.title} className="auth-stage-card p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[#879bb4]">0{index + 1}</p>
                    <p className="mt-2 text-sm font-semibold text-[#193550]">{item.title}</p>
                    <p className="mt-2 text-sm leading-6 text-[#63778f]">{item.description}</p>
                  </div>
                ))}
              </div>

              <div className="mt-5 rounded-[1.4rem] border border-[#dbe6f1] bg-[#f7fbff] p-4">
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-[#eaf3ff] text-[#245994]">
                    <CheckCircle2 className="h-4 w-4" />
                  </div>
                  <div className="space-y-1">
                    <p className="text-sm font-medium text-foreground">系统里已经接好的真实面板</p>
                    <p className="text-sm leading-6 text-[#63768d]">
                      这不是抽象宣传语，下面三块对应的是你现在这套系统里已经存在的真实模块。
                    </p>
                  </div>
                </div>

                <div className="mt-4 grid gap-3 md:grid-cols-3">
                  {systemPanels.map((item) => (
                    <div key={item.route} className="auth-stage-card bg-white/92 p-4">
                      <span className="auth-route-pill">{item.route}</span>
                      <p className="mt-3 text-sm font-semibold text-[#17324e]">{item.title}</p>
                      <p className="mt-2 text-sm leading-6 text-[#63778f]">{item.description}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div className="auth-spotlight-card p-5 text-white">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-white/72">
                  {effectiveMode === "register" ? "Conversion story" : "Workspace resume"}
                </p>
                <h3 className="mt-2 text-xl font-semibold">{spotlightTitle}</h3>
                <div className="mt-5 space-y-3">
                  {spotlightRows.map((item) => (
                    <div key={item.label} className="flex items-center justify-between rounded-2xl bg-white/10 px-4 py-3">
                      <span className="text-sm text-white/74">{item.label}</span>
                      <strong className="text-sm font-semibold text-white">{item.value}</strong>
                    </div>
                  ))}
                </div>
              </div>

              <div className="theme-status-surface px-5 py-4">
                <div className="flex items-start gap-3">
                  <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-primary text-primary-foreground shadow-[0_18px_34px_-24px_rgba(30,58,95,0.5)]">
                    <ArrowRight className="h-4 w-4" />
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-foreground">
                      {effectiveMode === "register" ? "注册完成后直接进入项目工作区" : `登录完成后优先返回${returnToLabel}`}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {effectiveMode === "register"
                        ? "账号创建之后，不会把你停在中间页；具体项目配置、会员动作和后续购买都能在系统内继续完成。"
                        : "这次验证通过后，系统会继续恢复你的项目、会员和后台链路，而不是只结束在一个登录成功提示上。"}
                    </p>
                    <div className="flex flex-wrap gap-2 pt-1">
                      {formTags.map((item) => (
                        <span key={item} className="auth-route-pill">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
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
                  {effectiveMode === "register"
                    ? "创建账号后立刻进入项目空间，也能继续首单会员与邀请奖励链路。"
                    : "使用账号恢复项目、会员与后台运营工作区。"}
                </CardDescription>
              </div>
              <div className="rounded-2xl border border-border/70 bg-[#f4f7fb] p-1">
                <div className="grid grid-cols-2 gap-1">
                  <Button variant={effectiveMode === "login" ? "default" : "ghost"} onClick={() => switchMode("login")} className="w-full">
                    登录
                  </Button>
                  {allowSignup ? (
                    <Button variant={effectiveMode === "register" ? "default" : "ghost"} onClick={() => switchMode("register")} className="w-full">
                      注册
                    </Button>
                  ) : (
                    <div className="flex items-center justify-center rounded-xl px-4 text-sm text-muted-foreground">未开放注册</div>
                  )}
                </div>
              </div>
              <div className="rounded-[1.25rem] border border-[#dce7f2] bg-[#f7fbff] px-4 py-3">
                <p className="text-sm font-semibold text-foreground">{formSummaryTitle}</p>
                <p className="mt-1 text-sm leading-6 text-[#60728a]">{formSummaryBody}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {formTags.map((item) => (
                    <span key={item} className="auth-route-pill">
                      {item}
                    </span>
                  ))}
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
                {effectiveMode === "register" ? (
                  <div className="grid gap-2">
                    <div className="flex items-center justify-between gap-3">
                      <Label htmlFor="inviteCode">邀请码</Label>
                      <span className="text-xs text-muted-foreground">选填</span>
                    </div>
                    <Input
                      id="inviteCode"
                      autoComplete="off"
                      value={inviteCode}
                      onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
                      placeholder="输入好友的邀请码"
                    />
                  </div>
                ) : null}
                <Button type="submit" disabled={pending || !email.trim() || !passwordValid} className="w-full">
                  {pending
                    ? effectiveMode === "register"
                      ? "注册中..."
                      : "登录中..."
                    : effectiveMode === "register"
                      ? "注册并进入"
                      : "登录并进入"}
                </Button>
                {submitError ? <p className="text-sm text-destructive">{formatApiError(submitError)}</p> : null}
                {!allowSignup ? <p className="text-sm text-muted-foreground">当前部署未开放公开注册。</p> : null}
                {allowSignup ? (
                  <div className="flex items-center justify-between gap-3 border-t border-[#e2e8f0] pt-4">
                    <div className="text-sm text-muted-foreground">
                      {effectiveMode === "register" ? "已经有账号了？" : "第一次来，还没有账号？"}
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => switchMode(effectiveMode === "register" ? "login" : "register")}
                    >
                      {effectiveMode === "register" ? "去登录" : "去注册"}
                    </Button>
                  </div>
                ) : null}
              </form>
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  )
}

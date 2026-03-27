import { useMemo, useState } from "react"
import { Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useCurrentUser, useLogin, useRegister } from "@/ui/queries/auth"
import { useSystemCapabilities } from "@/ui/queries/system"
import { usePageMeta } from "@/ui/seo/usePageMeta"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { cn } from "@/ui/utils"

type AuthMode = "login" | "register"

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
  const effectiveMode: AuthMode = allowSignup ? requestedMode : "login"
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [inviteCode, setInviteCode] = useState("")
  const returnTo = useMemo(() => resolveReturnTo(location.state), [location.state])
  const passwordValid = effectiveMode === "register" ? password.length >= 8 : password.length > 0

  usePageMeta({
    title: effectiveMode === "register" ? "注册 | LearningPyramid" : "登录 | LearningPyramid",
    description: effectiveMode === "register" ? "创建 LearningPyramid 账号。" : "登录 LearningPyramid。",
    path: "/login",
  })

  const capabilitiesUnavailableError = capabilitiesQ.error && !capabilitiesQ.data ? formatApiError(capabilitiesQ.error) : null
  const currentUserUnavailableError =
    authEnabled && currentUserQ.error && currentUserQ.data === undefined ? formatApiError(currentUserQ.error) : null

  if (capabilitiesQ.isLoading || (authEnabled && currentUserQ.isLoading)) {
    return (
      <div className="flex min-h-dvh items-center justify-center px-6">
        <div className="w-full max-w-sm">
          <LoadingNotice title="正在检查登录状态" message="请稍候。" />
        </div>
      </div>
    )
  }

  if (capabilitiesUnavailableError) {
    return (
      <div className="flex min-h-dvh items-center justify-center px-6">
        <div className="w-full max-w-sm">
          <ErrorNotice
            title="暂时无法确认部署能力"
            message={capabilitiesUnavailableError}
            action={<Button onClick={() => void capabilitiesQ.refetch()}>重试</Button>}
          />
        </div>
      </div>
    )
  }

  if (currentUserUnavailableError) {
    return (
      <div className="flex min-h-dvh items-center justify-center px-6">
        <div className="w-full max-w-sm">
          <ErrorNotice
            title="暂时无法确认登录状态"
            message={currentUserUnavailableError}
            action={<Button onClick={() => void currentUserQ.refetch()}>重新检查</Button>}
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
        showSuccessFeedback("账号已创建", "正在进入工作区。")
      } else {
        await login.mutateAsync(payload)
        showSuccessFeedback("登录成功", "正在进入工作区。")
      }
      nav(returnTo, { replace: true })
    } catch (err) {
      showErrorFeedback(effectiveMode === "register" ? "注册失败" : "登录失败", formatApiError(err))
    }
  }

  const submitError = effectiveMode === "register" ? register.error : login.error
  const pending = effectiveMode === "register" ? register.isPending : login.isPending

  return (
    <div className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-[radial-gradient(circle_at_top,_rgba(197,214,239,0.58),_transparent_42%),linear-gradient(180deg,_#f7f5f1_0%,_#eef2f8_100%)] px-6 py-10">
      <Card className="w-full max-w-md border-white/85 bg-white/92 shadow-[0_30px_90px_-42px_rgba(15,23,42,0.28)]">
        <CardContent className="p-6 sm:p-8">
          {allowSignup ? (
            <div className="mb-6 grid grid-cols-2 gap-2 rounded-2xl border border-border/70 bg-[#f4f7fb] p-1">
              <Button variant={effectiveMode === "login" ? "default" : "ghost"} onClick={() => switchMode("login")} className="w-full">
                登录
              </Button>
              <Button variant={effectiveMode === "register" ? "default" : "ghost"} onClick={() => switchMode("register")} className="w-full">
                注册
              </Button>
            </div>
          ) : null}

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
                onChange={(event) => setEmail(event.target.value)}
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
                onChange={(event) => setPassword(event.target.value)}
                placeholder={effectiveMode === "register" ? "至少 8 位" : "输入密码"}
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
                  onChange={(event) => setInviteCode(event.target.value.toUpperCase())}
                  placeholder="输入邀请码"
                />
              </div>
            ) : null}

            <Button type="submit" disabled={pending || !email.trim() || !passwordValid} className="mt-2 h-12 w-full text-base">
              {pending ? (effectiveMode === "register" ? "注册中..." : "登录中...") : effectiveMode === "register" ? "注册并进入" : "登录并进入"}
            </Button>

            {submitError ? <p className="text-sm text-destructive">{formatApiError(submitError)}</p> : null}

            {allowSignup ? (
              <div className="flex items-center justify-center pt-2 text-sm text-muted-foreground">
                <button
                  type="button"
                  onClick={() => switchMode(effectiveMode === "register" ? "login" : "register")}
                  className={cn("transition hover:text-foreground", pending && "pointer-events-none opacity-60")}
                >
                  {effectiveMode === "register" ? "已有账号，去登录" : "没有账号，去注册"}
                </button>
              </div>
            ) : null}
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

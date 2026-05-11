import { useEffect, useMemo, useState } from "react"
import { Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import {
  useConfirmEmailVerification,
  useConfirmPasswordReset,
  useCurrentUser,
  useEmailVerificationStatus,
  useLogin,
  useRegister,
  useRequestEmailVerification,
  useRequestPasswordReset,
} from "@/ui/queries/auth"
import { useSystemCapabilities } from "@/ui/queries/system"
import { usePageMeta } from "@/ui/seo/usePageMeta"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { cn } from "@/ui/utils"
import { AltchaWidget } from "@/views/auth/AltchaWidget"

type AuthMode = "login" | "register" | "reset" | "verify"
type VerifyEmailNotice = "sent" | "resent" | null

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function resolveReturnTo(state: unknown): string {
  if (!state || typeof state !== "object") return "/subjects"
  const value = (state as Record<string, unknown>).from
  return typeof value === "string" && value.trim() ? value : "/subjects"
}

export function AuthPage() {
  const nav = useNavigate()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const capabilitiesQ = useSystemCapabilities()
  const authEnabled = capabilitiesQ.data?.authEnabled ?? false
  const allowSignup = capabilitiesQ.data?.allowSignup ?? false
  const signupInviteRequired = capabilitiesQ.data?.signupInviteRequired ?? true
  const passwordResetEnabled = capabilitiesQ.data?.passwordResetEnabled ?? false
  const emailVerificationEnabled = capabilitiesQ.data?.emailVerificationEnabled ?? false
  const signupHumanCheckEnabled = capabilitiesQ.data?.signupHumanCheckEnabled ?? false
  const signupHumanCheckProvider = capabilitiesQ.data?.signupHumanCheckProvider ?? null
  const signupHumanCheckChallengeUrl = capabilitiesQ.data?.signupHumanCheckChallengeUrl ?? null
  const currentUserQ = useCurrentUser(authEnabled)
  const login = useLogin()
  const register = useRegister()
  const requestEmailVerification = useRequestEmailVerification()
  const confirmEmailVerification = useConfirmEmailVerification()
  const requestPasswordReset = useRequestPasswordReset()
  const confirmPasswordReset = useConfirmPasswordReset()
  const requestedModeParam = searchParams.get("mode")
  const requestedMode: AuthMode =
    requestedModeParam === "register"
      ? "register"
      : requestedModeParam === "reset"
        ? "reset"
        : requestedModeParam === "verify"
          ? "verify"
          : "login"
  const effectiveMode: AuthMode =
    requestedMode === "register"
      ? allowSignup
        ? "register"
        : "login"
      : requestedMode === "reset"
        ? passwordResetEnabled
          ? "reset"
          : "login"
        : requestedMode === "verify"
          ? "verify"
          : "login"
  const actionToken = searchParams.get("token")?.trim() || ""
  const verificationWaitToken = searchParams.get("waitToken")?.trim() || ""
  const emailParam = searchParams.get("email")?.trim() || ""
  const resetToken = effectiveMode === "reset" ? actionToken : ""
  const verifyToken = effectiveMode === "verify" ? actionToken : ""
  const resetTokenPresent = effectiveMode === "reset" && Boolean(resetToken)
  const verifyTokenPresent = effectiveMode === "verify" && Boolean(verifyToken)
  const [emailDraft, setEmailDraft] = useState(emailParam)
  const [password, setPassword] = useState("")
  const [inviteCode, setInviteCode] = useState("")
  const [humanCheckToken, setHumanCheckToken] = useState<string | null>(null)
  const [humanCheckResetSignal, setHumanCheckResetSignal] = useState(0)
  const [verifyEmailNotice, setVerifyEmailNotice] = useState<VerifyEmailNotice>(
    effectiveMode === "verify" && !verifyTokenPresent && Boolean(verificationWaitToken) ? "sent" : null,
  )
  const returnTo = useMemo(() => resolveReturnTo(location.state), [location.state])
  const passwordValid =
    effectiveMode === "register" || resetTokenPresent ? password.length >= 8 : effectiveMode === "login" ? password.length > 0 : true
  const registerRequiresHumanCheck =
    effectiveMode === "register" && signupHumanCheckEnabled && signupHumanCheckProvider === "altcha" && Boolean(signupHumanCheckChallengeUrl)
  const email = effectiveMode === "verify" && emailParam ? emailParam : emailDraft
  const effectiveVerifyEmailNotice =
    effectiveMode === "verify" && !verifyTokenPresent && verificationWaitToken ? (verifyEmailNotice ?? "sent") : verifyEmailNotice
  const verifyStatusQ = useEmailVerificationStatus(
    effectiveVerifyEmailNotice === "sent" && verificationWaitToken ? verificationWaitToken : null,
    effectiveMode === "verify" && !verifyTokenPresent,
    effectiveVerifyEmailNotice === "sent" && verificationWaitToken ? 2000 : false,
  )

  useEffect(() => {
    if (verifyStatusQ.data?.status !== "verified") return
    void currentUserQ.refetch()
    showSuccessFeedback("邮箱已验证，正在进入工作区。", "当前页面已同步验证结果。")
    nav(returnTo, { replace: true, state: { verifiedUserId: verifyStatusQ.data.user.userId } })
  }, [currentUserQ, nav, returnTo, verifyStatusQ.data])

  usePageMeta({
    title:
      effectiveMode === "register"
        ? "注册 | LearningPyramid"
        : effectiveMode === "reset"
          ? resetTokenPresent
            ? "重置密码 | LearningPyramid"
            : "找回密码 | LearningPyramid"
        : effectiveMode === "verify"
          ? verifyTokenPresent
            ? "验证邮箱 | LearningPyramid"
            : effectiveVerifyEmailNotice === "sent"
              ? "等待邮箱验证 | LearningPyramid"
              : "重新发送验证邮件 | LearningPyramid"
          : "登录 | LearningPyramid",
    description:
      effectiveMode === "register"
        ? "创建 LearningPyramid 账号。"
        : effectiveMode === "reset"
          ? "找回或重置 LearningPyramid 密码。"
          : effectiveMode === "verify"
            ? "验证 LearningPyramid 注册邮箱。"
          : "登录 LearningPyramid。",
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
    return <Navigate to="/subjects" replace />
  }

  if (currentUserQ.data && effectiveMode !== "reset" && (effectiveMode !== "verify" || !verifyTokenPresent)) {
    return <Navigate to={returnTo} replace />
  }

  function switchMode(nextMode: AuthMode) {
    setVerifyEmailNotice(null)
    if (nextMode === "register" && !allowSignup) return
    if (nextMode === "reset" && !passwordResetEnabled) return
    const nextParams = new URLSearchParams(searchParams)
    if (nextMode === "register") {
      nextParams.set("mode", "register")
      nextParams.delete("token")
      nextParams.delete("waitToken")
      nextParams.delete("email")
    } else if (nextMode === "reset") {
      nextParams.set("mode", "reset")
      if (!resetTokenPresent) nextParams.delete("token")
      nextParams.delete("waitToken")
      nextParams.delete("email")
    } else if (nextMode === "verify") {
      nextParams.set("mode", "verify")
      nextParams.delete("token")
      nextParams.delete("waitToken")
      if (email.trim()) nextParams.set("email", email.trim())
      else nextParams.delete("email")
    } else {
      nextParams.delete("mode")
      nextParams.delete("token")
      nextParams.delete("waitToken")
      nextParams.delete("email")
    }
    setSearchParams(nextParams, { replace: true })
  }

  async function onSubmit() {
    const payload = {
      email: email.trim(),
      password,
      inviteCode: inviteCode.trim() || undefined,
      humanCheckToken: humanCheckToken?.trim() || undefined,
    }
    try {
      if (effectiveMode === "reset") {
        if (resetTokenPresent) {
          if (!passwordValid) return
          await confirmPasswordReset.mutateAsync({ token: resetToken, newPassword: password })
          await currentUserQ.refetch()
          showSuccessFeedback("密码已重置", "请使用新密码登录。")
          setPassword("")
          switchMode("login")
        } else {
          if (!payload.email) return
          await requestPasswordReset.mutateAsync({ email: payload.email })
          showSuccessFeedback("重置邮件已发送", "如果账号存在，我们已经发送密码重置链接。")
          switchMode("login")
        }
      } else if (effectiveMode === "verify") {
        if (verifyTokenPresent) {
          const verified = await confirmEmailVerification.mutateAsync({ token: verifyToken })
          showSuccessFeedback("邮箱验证成功", "正在进入工作区。")
          nav(returnTo, { replace: true, state: { verifiedUserId: verified.userId } })
        } else {
          if (!payload.email) return
          await requestEmailVerification.mutateAsync({ email: payload.email })
          if (verificationWaitToken) {
            setVerifyEmailNotice("sent")
            showSuccessFeedback("验证邮件请求已处理", "如果账号尚未验证，我们会发送激活链接；当前页面会继续等待验证结果。")
          } else {
            showSuccessFeedback("验证邮件请求已处理", "如果账号尚未验证，我们会发送激活链接；如果已经完成验证，请直接登录。")
            switchMode("login")
          }
        }
      } else if (effectiveMode === "register") {
        if (!payload.email || !payload.password) return
        const created = await register.mutateAsync(payload)
        if (created.emailVerificationRequired) {
          showSuccessFeedback(
            created.verificationEmailSent ? "账号已创建，请验证邮箱" : "账号已创建",
            created.verificationEmailSent ? "我们已经向你的邮箱发送了激活链接。" : "请稍后在验证页重新发送激活链接。",
          )
          setPassword("")
          setHumanCheckToken(null)
          setHumanCheckResetSignal((value) => value + 1)
          const nextParams = new URLSearchParams(searchParams)
          nextParams.set("mode", "verify")
          nextParams.set("email", payload.email)
          nextParams.delete("token")
          if (created.verificationWaitToken?.trim()) nextParams.set("waitToken", created.verificationWaitToken.trim())
          else nextParams.delete("waitToken")
          setVerifyEmailNotice("sent")
          setSearchParams(nextParams, { replace: true })
        } else {
          showSuccessFeedback("账号已创建", "正在进入工作区。")
          nav(returnTo, { replace: true })
        }
      } else {
        if (!payload.email || !payload.password) return
        await login.mutateAsync(payload)
        showSuccessFeedback("登录成功", "正在进入工作区。")
        nav(returnTo, { replace: true })
      }
    } catch (err) {
      if (effectiveMode === "register" && registerRequiresHumanCheck) {
        setHumanCheckToken(null)
        setHumanCheckResetSignal((value) => value + 1)
      }
      showErrorFeedback(
        effectiveMode === "register"
          ? "注册失败"
          : effectiveMode === "reset"
            ? "密码重置失败"
            : effectiveMode === "verify"
              ? verifyTokenPresent
                ? "邮箱验证失败"
                : verifyStatusQ.data?.status === "expired"
                  ? "邮箱验证等待已过期"
                : "验证邮件发送失败"
              : "登录失败",
        formatApiError(err),
      )
    }
  }

  const submitError =
    effectiveMode === "register"
      ? register.error
      : effectiveMode === "reset"
        ? resetTokenPresent
          ? confirmPasswordReset.error
          : requestPasswordReset.error
            : effectiveMode === "verify"
              ? verifyTokenPresent
                ? confirmEmailVerification.error
                : verifyStatusQ.data?.status === "expired"
                  ? new ApiError("等待验证已过期，请重新发送验证邮件。", { code: "VERIFICATION_WAIT_EXPIRED", status: 400 })
                : requestEmailVerification.error
            : login.error
  const pending =
    effectiveMode === "register"
      ? register.isPending
      : effectiveMode === "reset"
        ? resetTokenPresent
          ? confirmPasswordReset.isPending
          : requestPasswordReset.isPending
        : effectiveMode === "verify"
          ? verifyTokenPresent
            ? confirmEmailVerification.isPending
            : requestEmailVerification.isPending
          : login.isPending
  const title =
    effectiveMode === "register"
      ? "创建账号"
      : effectiveMode === "reset"
        ? resetTokenPresent
          ? "重置密码"
          : "找回密码"
        : effectiveMode === "verify"
          ? verifyTokenPresent
            ? "验证邮箱"
            : effectiveVerifyEmailNotice === "sent"
              ? "等待邮箱验证"
              : "重新发送验证邮件"
          : "欢迎回来"
  const description =
    effectiveMode === "register"
      ? ""
      : effectiveMode === "reset"
        ? resetTokenPresent
          ? "设置一个新的登录密码。"
          : "输入注册邮箱，我们会发送一次性重置链接。"
        : effectiveMode === "verify"
          ? verifyTokenPresent
            ? "点击下方按钮完成邮箱验证并自动登录。"
            : effectiveVerifyEmailNotice === "sent"
              ? ""
              : "输入注册邮箱，我们会重新发送一封验证邮件。"
        : ""
  return (
    <div className="relative flex min-h-dvh items-center justify-center overflow-hidden bg-[radial-gradient(circle_at_top,_rgba(197,214,239,0.58),_transparent_42%),linear-gradient(180deg,_#f7f5f1_0%,_#eef2f8_100%)] px-6 py-10">
      <Card className="w-full max-w-md border-white/85 bg-white/92 shadow-[0_30px_90px_-42px_rgba(15,23,42,0.28)]">
        <CardContent className="p-6 sm:p-8">
          <div className="mb-6">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
            {description ? <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p> : null}
          </div>

          {allowSignup && effectiveMode !== "reset" && effectiveMode !== "verify" ? (
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
            {(effectiveMode !== "reset" || !resetTokenPresent) && (effectiveMode !== "verify" || !verifyTokenPresent) ? (
              <div className="grid gap-2">
                <Label htmlFor="email">邮箱</Label>
                <Input
                  id="email"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(event) => {
                    setEmailDraft(event.target.value)
                    if (verifyEmailNotice) setVerifyEmailNotice(null)
                  }}
                  placeholder="you@example.com"
                />
              </div>
            ) : null}

            {effectiveMode === "verify" && !verifyTokenPresent && effectiveVerifyEmailNotice ? (
              <ContentNotice
                title={effectiveVerifyEmailNotice === "resent" ? "激活链接已重新发送" : "验证邮件已发送"}
                message={
                  effectiveVerifyEmailNotice === "resent"
                    ? "如果这个邮箱已经注册且尚未验证，我们会重新发送激活链接；如果你刚清理过账号，请直接重新注册。"
                    : "请到邮箱点击激活链接；你可以在手机或电脑上完成验证，当前页面会自动继续。"
                }
                tone="info"
              />
            ) : null}

            {effectiveMode === "register" || effectiveMode === "login" || resetTokenPresent ? (
              <div className="grid gap-2">
                <div className="flex items-center justify-between gap-3">
                  <Label htmlFor="password">{resetTokenPresent ? "新密码" : "密码"}</Label>
                  {effectiveMode === "register" || resetTokenPresent ? <span className="text-xs text-muted-foreground">至少 8 位</span> : null}
                </div>
                <Input
                  id="password"
                  type="password"
                  autoComplete={effectiveMode === "login" ? "current-password" : "new-password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder={effectiveMode === "login" ? "输入密码" : "至少 8 位"}
                />
              </div>
            ) : null}

            {effectiveMode === "register" ? (
              <div className="grid gap-2">
                <div className="flex items-center justify-between gap-3">
                  <Label htmlFor="inviteCode">邀请码</Label>
                </div>
                <Input
                  id="inviteCode"
                  autoComplete="off"
                  value={inviteCode}
                  onChange={(event) => setInviteCode(event.target.value.toUpperCase())}
                  placeholder={signupInviteRequired ? "输入邀请码；仅引导管理员邮箱可留空" : "可选填写邀请码"}
                />
                <p className="text-xs leading-5 text-muted-foreground">
                  {signupInviteRequired
                    ? "当前部署仍要求邀请码注册；只有部署时配置的引导管理员邮箱可以留空完成初始化。"
                    : "绑定邀请码可获7.5折券"}
                </p>
              </div>
            ) : null}

            {registerRequiresHumanCheck && signupHumanCheckChallengeUrl ? (
              <AltchaWidget
                challengeUrl={signupHumanCheckChallengeUrl}
                resetSignal={humanCheckResetSignal}
                onTokenChange={setHumanCheckToken}
              />
            ) : null}

            <Button
              type="submit"
              disabled={
                pending ||
                (((effectiveMode !== "reset" || !resetTokenPresent) && (effectiveMode !== "verify" || !verifyTokenPresent)) && !email.trim()) ||
                !passwordValid ||
                (registerRequiresHumanCheck && !humanCheckToken)
              }
              className="mt-2 h-12 w-full text-base"
            >
              {pending
                ? effectiveMode === "register"
                  ? "注册中..."
                  : effectiveMode === "reset"
                    ? resetTokenPresent
                      ? "重置中..."
                      : "发送中..."
                    : effectiveMode === "verify"
                      ? verifyTokenPresent
                        ? "验证中..."
                        : "发送中..."
                      : "登录中..."
                : effectiveMode === "register"
                  ? emailVerificationEnabled
                    ? "注册并发送验证邮件"
                    : "注册并进入"
                  : effectiveMode === "reset"
                    ? resetTokenPresent
                      ? "重置密码"
                      : "发送重置邮件"
                    : effectiveMode === "verify"
                      ? verifyTokenPresent
                        ? "验证邮箱并进入"
                        : "重新发送验证邮件"
                      : "登录并进入"}
            </Button>

            {submitError ? <p className="text-sm text-destructive">{formatApiError(submitError)}</p> : null}

            {effectiveMode === "login" &&
            submitError instanceof ApiError &&
            submitError.message.toLowerCase().includes("email verification") &&
            email.trim() ? (
              <div className="flex items-center justify-center pt-1 text-sm text-muted-foreground">
                <button
                  type="button"
                  onClick={() => {
                    const nextParams = new URLSearchParams(searchParams)
                    nextParams.set("mode", "verify")
                    nextParams.set("email", email.trim())
                    nextParams.delete("token")
                    setSearchParams(nextParams, { replace: true })
                  }}
                  className={cn("transition hover:text-foreground", pending && "pointer-events-none opacity-60")}
                >
                  去验证邮箱
                </button>
              </div>
            ) : null}

            {effectiveMode === "reset" ? (
              <div className="flex flex-wrap items-center justify-center gap-x-6 gap-y-3 pt-2 text-sm text-muted-foreground">
                <button
                  type="button"
                  onClick={() => switchMode("login")}
                  className={cn("transition hover:text-foreground", pending && "pointer-events-none opacity-60")}
                >
                  返回登录
                </button>
              </div>
            ) : (
              <>
                {passwordResetEnabled && effectiveMode === "login" ? (
                  <div className="flex items-center justify-center pt-1 text-sm text-muted-foreground">
                    <button
                      type="button"
                      onClick={() => switchMode("reset")}
                      className={cn("transition hover:text-foreground", pending && "pointer-events-none opacity-60")}
                    >
                      忘记密码
                    </button>
                  </div>
                ) : null}

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
              </>
            )}
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

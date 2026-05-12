import { useEffect, useMemo, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"

import { Button } from "@/ui/components/ui/button"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useCompletePayoutBinding, useOpenMobilePayoutBinding } from "@/ui/queries/membership"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { formatMembershipApiError, formatMembershipPrice } from "@/views/membership/membershipUi"

type WeixinBridge = {
  invoke: (name: string, params: Record<string, string>, callback: () => void) => void
}

function getWeixinBridge() {
  return typeof window !== "undefined"
    ? (window as unknown as { WeixinJSBridge?: WeixinBridge }).WeixinJSBridge
    : undefined
}

async function waitForWeixinBridge(timeoutMs = 1500) {
  const existing = getWeixinBridge()
  if (existing?.invoke || typeof window === "undefined" || typeof document === "undefined") {
    return existing
  }
  return await new Promise<WeixinBridge | undefined>((resolve) => {
    const onReady = () => {
      cleanup()
      resolve(getWeixinBridge())
    }
    const cleanup = () => {
      window.clearTimeout(timer)
      document.removeEventListener("WeixinJSBridgeReady", onReady)
    }
    const timer = window.setTimeout(() => {
      cleanup()
      resolve(getWeixinBridge())
    }, timeoutMs)
    document.addEventListener("WeixinJSBridgeReady", onReady, false)
  })
}

export function WechatPayoutBindingPage() {
  const [searchParams] = useSearchParams()
  const bindingAttemptId = searchParams.get("attempt") ?? ""
  const state = searchParams.get("state") ?? ""
  const codeFromWechat = searchParams.get("code") ?? searchParams.get("authorizationCode") ?? ""
  const [authorizationCode, setAuthorizationCode] = useState(codeFromWechat)
  const [wechatConfirmationStarted, setWechatConfirmationStarted] = useState(false)

  const openBinding = useOpenMobilePayoutBinding()
  const completeBinding = useCompletePayoutBinding()

  useEffect(() => {
    if (!bindingAttemptId || !state || openBinding.data || openBinding.isPending) return
    void openBinding.mutateAsync({ bindingAttemptId, state }).catch((err) => {
      showErrorFeedback("打开绑定失败", formatMembershipApiError(err))
    })
  }, [bindingAttemptId, state, openBinding])

  const payload = openBinding.data
  const accountLabel = useMemo(() => payload?.learningPyramidAccountLabel?.trim() || "当前 LearningPyramid 账号", [payload])
  const withdrawalAmountCent = payload?.amountCent ?? 0
  const isWithdrawalFlow = withdrawalAmountCent > 0

  async function requestMerchantTransfer(confirmation: { mchId: string; appId: string; packageInfo: string }) {
    const bridge = await waitForWeixinBridge()
    if (!bridge?.invoke) {
      showErrorFeedback("需要在微信内确认", "请使用手机微信打开这个页面，再继续确认收款。")
      return false
    }
    await new Promise<void>((resolve) => {
      bridge.invoke(
        "requestMerchantTransfer",
        {
          mchId: confirmation.mchId,
          appId: confirmation.appId,
          package: confirmation.packageInfo,
        },
        () => resolve(),
      )
    })
    setWechatConfirmationStarted(true)
    showSuccessFeedback("已发起微信确认", "请在当前微信会话里完成收款确认，到账状态会自动刷新。")
    return true
  }

  async function confirmBinding() {
    if (!bindingAttemptId || !state || !authorizationCode.trim()) {
      showErrorFeedback("确认绑定失败", "缺少微信授权结果，请重新扫码。")
      return
    }
    try {
      const result = await completeBinding.mutateAsync({
        bindingAttemptId,
        authorizationCode,
        state,
        confirmedLearningPyramidUserId: payload?.confirmedLearningPyramidUserId,
      })
      if ("withdrawal" in result) {
        showSuccessFeedback("提现已创建", "正在拉起微信收款确认。")
        if (result.withdrawal.confirmation) {
          await requestMerchantTransfer(result.withdrawal.confirmation)
        }
        return
      }
      showSuccessFeedback("微信收款账号已绑定", "可以回到电脑页面继续提现。")
    } catch (err) {
      showErrorFeedback("确认绑定失败", formatMembershipApiError(err))
    }
  }

  return (
    <main className="min-h-screen bg-background px-5 py-10 text-foreground">
      <section className="mx-auto grid max-w-md gap-6">
        <div>
          <div className="text-sm text-muted-foreground">LearningPyramid</div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">
            {wechatConfirmationStarted ? "已提交微信确认" : isWithdrawalFlow ? "确认微信提现" : "绑定微信收款账号"}
          </h1>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            {wechatConfirmationStarted
              ? "请回到电脑端查看到账状态。"
              : isWithdrawalFlow
                ? "确认后会直接发起这笔佣金提现，并在当前微信里继续确认收款。"
                : "确认后，电脑端账号的邀请佣金会提现到当前微信。"}
          </p>
        </div>

        <div className="rounded-lg border bg-card p-5 shadow-sm">
          <div className="text-sm text-muted-foreground">将绑定到账号</div>
          <div className="mt-2 break-all text-base font-semibold">{accountLabel || "正在读取绑定信息..."}</div>
          {isWithdrawalFlow ? (
            <>
              <div className="mt-4 text-sm text-muted-foreground">提现金额</div>
              <div className="mt-1 text-xl font-semibold">{formatMembershipPrice(withdrawalAmountCent)}</div>
            </>
          ) : null}
        </div>

        {!codeFromWechat && payload?.authorizationUrl && /^https?:\/\//i.test(payload.authorizationUrl) ? (
          <Button type="button" onClick={() => window.location.assign(payload.authorizationUrl ?? "")}>
            前往微信授权
          </Button>
        ) : null}

        {!codeFromWechat ? (
          <div className="grid gap-2">
            <Label htmlFor="wechat-binding-code">本地验收授权码</Label>
            <Input id="wechat-binding-code" value={authorizationCode} onChange={(event) => setAuthorizationCode(event.target.value)} />
          </div>
        ) : null}

        {wechatConfirmationStarted ? null : (
          <Button type="button" onClick={() => void confirmBinding()} disabled={completeBinding.isPending || !payload}>
            {completeBinding.isPending ? "处理中..." : isWithdrawalFlow ? "确认并提现" : "确认绑定"}
          </Button>
        )}

        <Link className="text-center text-sm text-muted-foreground hover:text-foreground" to="/membership">
          返回会员页面
        </Link>
      </section>
    </main>
  )
}

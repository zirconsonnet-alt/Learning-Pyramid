import { useEffect } from "react"
import { Link, useSearchParams } from "react-router-dom"

import { Button } from "@/ui/components/ui/button"
import { useCommissionWithdrawalWechatConfirmation } from "@/ui/queries/membership"
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

export function WechatWithdrawalConfirmationPage() {
  const [searchParams] = useSearchParams()
  const withdrawalId = searchParams.get("withdrawal") ?? ""
  const token = searchParams.get("token") ?? ""
  const confirmationQ = useCommissionWithdrawalWechatConfirmation()

  useEffect(() => {
    if (!withdrawalId || !token || confirmationQ.data || confirmationQ.isPending) return
    void confirmationQ.mutateAsync({ withdrawalId, token }).catch((err) => {
      showErrorFeedback("读取提现确认失败", formatMembershipApiError(err))
    })
  }, [withdrawalId, token, confirmationQ])

  async function requestMerchantTransfer() {
    const confirmation = confirmationQ.data?.confirmation
    if (!confirmation) {
      showErrorFeedback("继续确认失败", "当前提现单没有可用的微信确认参数，请回到电脑端重新申请提现。")
      return
    }
    const bridge = await waitForWeixinBridge()
    if (!bridge?.invoke) {
      showErrorFeedback("需要在微信内确认", "请使用手机微信打开这个页面，再继续确认收款。")
      return
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
    showSuccessFeedback("已发起微信确认", "请在当前微信会话里完成收款确认，到账状态会自动刷新。")
  }

  const payload = confirmationQ.data

  return (
    <main className="min-h-screen bg-background px-5 py-10 text-foreground">
      <section className="mx-auto grid max-w-md gap-6">
        <div>
          <div className="text-sm text-muted-foreground">LearningPyramid</div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">确认微信提现</h1>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">请在手机微信内继续确认收款，确认后到账状态会自动同步。</p>
        </div>

        <div className="rounded-lg border bg-card p-5 shadow-sm">
          <div className="text-sm text-muted-foreground">收款身份</div>
          <div className="mt-2 break-all text-base font-semibold">{payload?.identityMaskedLabel ?? "正在读取提现确认信息..."}</div>
          <div className="mt-4 text-sm text-muted-foreground">提现金额</div>
          <div className="mt-1 text-xl font-semibold">{payload ? formatMembershipPrice(payload.amountCent) : "--"}</div>
        </div>

        <Button type="button" onClick={() => void requestMerchantTransfer()} disabled={confirmationQ.isPending || !payload?.confirmation}>
          {confirmationQ.isPending ? "读取中..." : "继续微信确认"}
        </Button>

        <Link className="text-center text-sm text-muted-foreground hover:text-foreground" to="/membership">
          返回会员页面
        </Link>
      </section>
    </main>
  )
}

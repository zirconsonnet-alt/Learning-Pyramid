import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"

import { Button } from "@/ui/components/ui/button"
import { useCommissionWithdrawalWechatConfirmation, useMarkCommissionWithdrawalWechatConfirmationStarted } from "@/ui/queries/membership"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { formatMembershipApiError, formatMembershipPrice } from "@/views/membership/membershipUi"
import { requestWechatMerchantTransfer } from "@/views/membership/wechatTransfer"

export function WechatWithdrawalConfirmationPage() {
  const [searchParams] = useSearchParams()
  const withdrawalId = searchParams.get("withdrawal") ?? ""
  const token = searchParams.get("token") ?? ""
  const confirmationQ = useCommissionWithdrawalWechatConfirmation()
  const markConfirmationStarted = useMarkCommissionWithdrawalWechatConfirmationStarted()
  const [wechatConfirmationStarted, setWechatConfirmationStarted] = useState(false)

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
    const invokeResult = await requestWechatMerchantTransfer(confirmation)
    if (!invokeResult.ok) {
      showErrorFeedback("需要在微信内确认", invokeResult.message)
      return
    }
    try {
      await markConfirmationStarted.mutateAsync({ withdrawalId, token })
    } catch (err) {
      showErrorFeedback("同步确认状态失败", formatMembershipApiError(err))
      return
    }
    setWechatConfirmationStarted(true)
    showSuccessFeedback("已发起微信确认", "请在当前微信会话里完成收款确认，到账状态会自动刷新。")
  }

  const payload = confirmationQ.data

  return (
    <main className="min-h-screen bg-background px-5 py-10 text-foreground">
      <section className="mx-auto grid max-w-md gap-6">
        <div>
          <div className="text-sm text-muted-foreground">LearningPyramid</div>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">{wechatConfirmationStarted ? "已提交微信确认" : "确认微信提现"}</h1>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            {wechatConfirmationStarted ? "请回到电脑端查看到账状态。" : "请在手机微信内继续确认收款，确认后到账状态会自动同步。"}
          </p>
        </div>

        <div className="rounded-lg border bg-card p-5 shadow-sm">
          <div className="text-sm text-muted-foreground">收款身份</div>
          <div className="mt-2 break-all text-base font-semibold">{payload?.identityMaskedLabel ?? "正在读取提现确认信息..."}</div>
          <div className="mt-4 text-sm text-muted-foreground">提现金额</div>
          <div className="mt-1 text-xl font-semibold">{payload ? formatMembershipPrice(payload.amountCent) : "--"}</div>
        </div>

        {wechatConfirmationStarted ? null : (
          <Button type="button" onClick={() => void requestMerchantTransfer()} disabled={confirmationQ.isPending || markConfirmationStarted.isPending || !payload?.confirmation}>
            {confirmationQ.isPending ? "读取中..." : markConfirmationStarted.isPending ? "同步中..." : "继续微信确认"}
          </Button>
        )}

        <Link className="text-center text-sm text-muted-foreground hover:text-foreground" to="/membership">
          返回会员页面
        </Link>
      </section>
    </main>
  )
}

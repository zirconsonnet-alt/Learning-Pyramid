import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"

import { Button } from "@/ui/components/ui/button"
import {
  useCommissionWithdrawalWechatConfirmation,
  useCompleteWithdrawalConfirmationAttempt,
  useMarkCommissionWithdrawalWechatConfirmationStarted,
  useOpenMobileWithdrawalConfirmation,
} from "@/ui/queries/membership"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { formatMembershipApiError, formatMembershipPrice } from "@/views/membership/membershipUi"
import { readWithdrawalConfirmationToken, requestWechatMerchantTransfer, type WechatMerchantTransferConfirmation } from "@/views/membership/wechatTransfer"

export function WechatWithdrawalConfirmationPage() {
  const [searchParams] = useSearchParams()
  const withdrawalId = searchParams.get("withdrawal") ?? ""
  const token = searchParams.get("token") ?? ""
  const withdrawalConfirmationAttemptId = searchParams.get("attempt") ?? ""
  const state = searchParams.get("state") ?? ""
  const codeFromWechat = searchParams.get("code") ?? searchParams.get("authorizationCode") ?? ""
  const confirmationQ = useCommissionWithdrawalWechatConfirmation()
  const openMobileConfirmation = useOpenMobileWithdrawalConfirmation()
  const completeConfirmationAttempt = useCompleteWithdrawalConfirmationAttempt()
  const markConfirmationStarted = useMarkCommissionWithdrawalWechatConfirmationStarted()
  const [wechatConfirmationStarted, setWechatConfirmationStarted] = useState(false)
  const isAttemptFlow = Boolean(withdrawalConfirmationAttemptId && state)

  useEffect(() => {
    if (isAttemptFlow || !withdrawalId || !token || confirmationQ.data || confirmationQ.isPending) return
    void confirmationQ.mutateAsync({ withdrawalId, token }).catch((err) => {
      showErrorFeedback("读取提现确认失败", formatMembershipApiError(err))
    })
  }, [isAttemptFlow, withdrawalId, token, confirmationQ])

  useEffect(() => {
    if (!isAttemptFlow || !withdrawalConfirmationAttemptId || !state || openMobileConfirmation.data || openMobileConfirmation.isPending) return
    void openMobileConfirmation.mutateAsync({ withdrawalConfirmationAttemptId, state }).catch((err) => {
      showErrorFeedback("读取扫码提现失败", formatMembershipApiError(err))
    })
  }, [isAttemptFlow, withdrawalConfirmationAttemptId, state, openMobileConfirmation])

  async function requestExistingMerchantTransfer() {
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

  async function requestNewMerchantTransfer(confirmation: WechatMerchantTransferConfirmation, createdWithdrawalId: string, confirmationUrl: string | null | undefined) {
    const invokeResult = await requestWechatMerchantTransfer(confirmation)
    if (!invokeResult.ok) {
      showErrorFeedback("需要在微信内确认", invokeResult.message)
      return false
    }
    const confirmationToken = readWithdrawalConfirmationToken(confirmationUrl)
    if (!confirmationToken) {
      showErrorFeedback("同步确认状态失败", "缺少提现确认令牌，请回到电脑端重新扫码。")
      return false
    }
    try {
      await markConfirmationStarted.mutateAsync({ withdrawalId: createdWithdrawalId, token: confirmationToken })
    } catch (err) {
      showErrorFeedback("同步确认状态失败", formatMembershipApiError(err))
      return false
    }
    setWechatConfirmationStarted(true)
    showSuccessFeedback("已发起微信确认", "请在当前微信会话里完成收款确认，到账状态会自动刷新。")
    return true
  }

  async function confirmScannedWithdrawal() {
    if (!withdrawalConfirmationAttemptId || !state || !codeFromWechat) {
      showErrorFeedback("确认提现失败", "缺少微信授权结果，请重新扫码。")
      return
    }
    try {
      const result = await completeConfirmationAttempt.mutateAsync({
        withdrawalConfirmationAttemptId,
        authorizationCode: codeFromWechat,
        state,
        confirmedLearningPyramidUserId: openMobileConfirmation.data?.confirmedLearningPyramidUserId,
      })
      if (!("withdrawal" in result) || !result.withdrawal) {
        showErrorFeedback("确认提现失败", "当前扫码结果没有生成提现单，请回到电脑端重新申请提现。")
        return
      }
      if (result.withdrawal.confirmation) {
        await requestNewMerchantTransfer(result.withdrawal.confirmation, result.withdrawal.withdrawalId, result.withdrawal.confirmationUrl)
        return
      }
      showSuccessFeedback("提现请求已提交", "后续到账状态会由微信通知或后台对账更新。")
    } catch (err) {
      showErrorFeedback("确认提现失败", formatMembershipApiError(err))
    }
  }

  const payload = confirmationQ.data
  const attemptPayload = openMobileConfirmation.data
  const displayAmountCent = isAttemptFlow ? attemptPayload?.amountCent : payload?.amountCent
  const displayIdentity = isAttemptFlow ? attemptPayload?.learningPyramidAccountLabel : payload?.identityMaskedLabel
  const isLoading = isAttemptFlow ? openMobileConfirmation.isPending : confirmationQ.isPending
  const canConfirmScannedWithdrawal = Boolean(attemptPayload && codeFromWechat)

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
          <div className="text-sm text-muted-foreground">{isAttemptFlow ? "LearningPyramid 账号" : "收款身份"}</div>
          <div className="mt-2 break-all text-base font-semibold">{displayIdentity ?? "正在读取提现确认信息..."}</div>
          <div className="mt-4 text-sm text-muted-foreground">提现金额</div>
          <div className="mt-1 text-xl font-semibold">{displayAmountCent ? formatMembershipPrice(displayAmountCent) : "--"}</div>
        </div>

        {!codeFromWechat && attemptPayload?.authorizationUrl && /^https?:\/\//i.test(attemptPayload.authorizationUrl) ? (
          <Button type="button" onClick={() => window.location.assign(attemptPayload.authorizationUrl ?? "")}>
            前往微信授权
          </Button>
        ) : null}

        {wechatConfirmationStarted ? null : isAttemptFlow ? (
          <Button type="button" onClick={() => void confirmScannedWithdrawal()} disabled={openMobileConfirmation.isPending || completeConfirmationAttempt.isPending || markConfirmationStarted.isPending || !canConfirmScannedWithdrawal}>
            {isLoading ? "读取中..." : completeConfirmationAttempt.isPending ? "处理中..." : markConfirmationStarted.isPending ? "同步中..." : "确认并提现"}
          </Button>
        ) : (
          <Button type="button" onClick={() => void requestExistingMerchantTransfer()} disabled={confirmationQ.isPending || markConfirmationStarted.isPending || !payload?.confirmation}>
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

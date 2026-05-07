import { ChevronLeft, Copy, History, Ticket, Users } from "lucide-react"
import { type FormEvent, useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { QRCodeSVG } from "qrcode.react"

import type { CommissionWithdrawal, CouponRecord, InviteReferral, MembershipCreateOrderResult, MembershipOrder } from "@/ui/api/membership"
import { ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/ui/components/ui/dialog"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import {
  useCloseMembershipOrder,
  useCommissionSummary,
  useCommissionWithdrawals,
  useConfirmMembershipPayment,
  useCreateMembershipOrder,
  useMembershipCoupons,
  useMembershipOrderPreview,
  useMembershipOrders,
  useMembershipSummary,
  usePayoutBindingAttempt,
  useRequestCommissionWithdrawal,
  useStartPayoutBindingAttempt,
  useSyncMembershipPayment,
  useInviteSummary,
} from "@/ui/queries/membership"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { cn } from "@/ui/utils"
import { MembershipPurchaseDialog } from "@/views/membership/components/MembershipPurchaseDialog"
import {
  copyTextToClipboard,
  describeInviteRecordStatus,
  describeMembershipCouponSource,
  describeMembershipCouponStatus,
  describeWithdrawalStatus,
  formatMembershipApiError,
  formatMembershipCouponValue,
  formatMembershipDateTime,
  formatMembershipPrice,
  StatusPill,
} from "@/views/membership/membershipUi"

const DEFAULT_MEMBERSHIP_PLAN_ID = "monthly"

function getMembershipState(summary: ReturnType<typeof useMembershipSummary>["data"]) {
  if (summary?.isActive) return "会员有效"
  if (summary?.currentStatus === "expired") return "会员已过期"
  return "尚未开通"
}

function getInviteDisplayName(invite: InviteReferral) {
  return invite.inviteeNickname?.trim() || invite.inviteePublicUid?.trim() || "未命名用户"
}

type WechatMerchantTransferConfirmation = {
  mchId: string
  appId: string
  packageInfo: string
}

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

function CouponBagDialog(props: {
  open: boolean
  onOpenChange: (open: boolean) => void
  coupons: CouponRecord[]
  inviteLabelsByUserId: Map<string, string>
}) {
  const { open, onOpenChange, coupons, inviteLabelsByUserId } = props

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl rounded-[2rem] border-[color:var(--theme-soft-border)] [background:radial-gradient(circle_at_top_left,hsl(var(--primary)/0.1),transparent_36%),var(--theme-card-main-bg)] p-0">
        <div className="border-b border-[color:var(--theme-soft-border)] px-6 py-6 sm:px-8">
          <DialogHeader className="space-y-3 text-left">
            <div className="flex items-center gap-2">
              <StatusPill tone="warm">券包</StatusPill>
              <StatusPill tone="accent">{coupons.filter((coupon) => coupon.status === "available").length} 张可用</StatusPill>
            </div>
            <DialogTitle className="text-2xl tracking-tight text-foreground">我的优惠券</DialogTitle>
            <DialogDescription className="max-w-xl leading-7 text-muted-foreground">
              这里会按时间列出你当前拥有的优惠券，向下滑动可以继续查看更多记录。
            </DialogDescription>
          </DialogHeader>
        </div>

        <div className="max-h-[68vh] space-y-3 overflow-y-auto px-6 py-6 sm:px-8">
          {coupons.length === 0 ? (
            <div className="theme-subtle-surface rounded-[1.4rem] border-dashed px-5 py-10 text-center text-sm leading-7 text-[color:var(--theme-subtle-text)]">
              暂时还没有优惠券。绑定邀请码后会获得 7.5 折会员券。
            </div>
          ) : (
            coupons.map((coupon) => {
              const sourceInviteLabel = coupon.sourceInviteeUserId ? inviteLabelsByUserId.get(coupon.sourceInviteeUserId) : null
              return (
                <div key={coupon.couponId} className="theme-soft-surface rounded-[1.35rem] p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="text-sm font-semibold text-foreground">{coupon.title || describeMembershipCouponSource(coupon.source)}</div>
                        <StatusPill tone={coupon.status === "available" ? "accent" : "default"}>
                          {describeMembershipCouponStatus(coupon.status)}
                        </StatusPill>
                      </div>
                      <div className="mt-2 text-sm leading-6 text-muted-foreground">
                        满 {formatMembershipPrice(coupon.minSpendCent)} 可用，创建于 {formatMembershipDateTime(coupon.createdAt)}。
                      </div>
                      <div className="mt-1 text-xs leading-6 text-[color:var(--theme-subtle-text)]">
                        来源：{describeMembershipCouponSource(coupon.source)}
                        {sourceInviteLabel ? ` · 邀请用户 ${sourceInviteLabel}` : ""}
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      <div className="text-2xl font-semibold tracking-tight text-foreground">{formatMembershipCouponValue(coupon)}</div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {coupon.status === "used" && coupon.usedAt
                          ? `已于 ${formatMembershipDateTime(coupon.usedAt)} 使用`
                          : coupon.expiresAt
                            ? `${formatMembershipDateTime(coupon.expiresAt)} 到期`
                            : "长期有效"}
                      </div>
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

function InviteRecordsDialog(props: {
  open: boolean
  onOpenChange: (open: boolean) => void
  invites: InviteReferral[]
  totalInvitedUsers: number
}) {
  const { open, onOpenChange, invites, totalInvitedUsers } = props

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl rounded-[2rem] border-[color:var(--theme-soft-border)] [background:var(--theme-card-main-bg)] p-0">
        <div className="border-b border-[color:var(--theme-soft-border)] px-6 py-6 sm:px-8">
          <DialogHeader className="space-y-3 text-left">
            <div className="flex items-center gap-2">
              <StatusPill tone="accent">{totalInvitedUsers} 人</StatusPill>
            </div>
            <DialogTitle className="text-2xl tracking-tight text-foreground">我邀请的人</DialogTitle>
            <DialogDescription className="max-w-xl leading-7 text-muted-foreground">查看已绑定邀请码的用户和首单转化状态。</DialogDescription>
          </DialogHeader>
        </div>

        <div className="max-h-[68vh] space-y-3 overflow-y-auto px-6 py-6 sm:px-8">
          {invites.length === 0 ? (
            <div className="theme-subtle-surface rounded-[1.4rem] border-dashed px-5 py-10 text-center text-sm leading-7 text-[color:var(--theme-subtle-text)]">
              还没有邀请记录。把邀请码发给朋友后，这里会列出已绑定和已转化的用户。
            </div>
          ) : (
            invites.map((invite) => (
              <div key={`${invite.inviteeUserId}-${invite.boundAt}`} className="theme-soft-surface rounded-[1.3rem] p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="text-sm font-semibold text-foreground">{getInviteDisplayName(invite)}</div>
                      <StatusPill tone={invite.status === "rewarded" ? "accent" : "default"}>{describeInviteRecordStatus(invite.status)}</StatusPill>
                    </div>
                    {invite.inviteePublicUid ? <div className="mt-1 font-mono text-xs text-[color:var(--theme-subtle-text)]">UID {invite.inviteePublicUid}</div> : null}
                    <div className="mt-2 text-sm leading-6 text-muted-foreground">绑定时间：{formatMembershipDateTime(invite.boundAt)}</div>
                  </div>
                  <div className="shrink-0 text-right text-xs leading-6 text-muted-foreground">
                    {invite.rewardedAt ? (
                      <>
                        <div>奖励触发</div>
                        <div>{formatMembershipDateTime(invite.rewardedAt)}</div>
                      </>
                    ) : (
                      <>
                        <div>当前状态</div>
                        <div>等待首单转化</div>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
          {totalInvitedUsers > invites.length ? (
            <div className="text-xs leading-6 text-[color:var(--theme-subtle-text)]">当前展示最近 {invites.length} 条邀请记录，共 {totalInvitedUsers} 人。</div>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  )
}

function WithdrawalRecordsDialog(props: {
  open: boolean
  onOpenChange: (open: boolean) => void
  withdrawals: CommissionWithdrawal[]
  onResumeWithdrawalConfirmation: (withdrawal: CommissionWithdrawal) => void
}) {
  const { open, onOpenChange, withdrawals, onResumeWithdrawalConfirmation } = props

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl rounded-[2rem] border-[color:var(--theme-soft-border)] [background:var(--theme-card-main-bg)] p-0">
        <div className="border-b border-[color:var(--theme-soft-border)] px-6 py-6 sm:px-8">
          <DialogHeader className="space-y-3 text-left">
            <div className="flex items-center gap-2">
              <StatusPill tone="warm">{withdrawals.length} 条</StatusPill>
            </div>
            <DialogTitle className="text-2xl tracking-tight text-foreground">提现记录</DialogTitle>
            <DialogDescription className="max-w-xl leading-7 text-muted-foreground">查看提现申请状态，需要微信确认的记录也可以在这里继续处理。</DialogDescription>
          </DialogHeader>
        </div>

        <div className="max-h-[68vh] space-y-3 overflow-y-auto px-6 py-6 sm:px-8">
          {withdrawals.length === 0 ? (
            <div className="theme-subtle-surface rounded-[1.4rem] border-dashed px-5 py-10 text-center text-sm leading-7 text-[color:var(--theme-subtle-text)]">
              暂时还没有提现记录。
            </div>
          ) : (
            withdrawals.map((withdrawal) => (
              <div key={withdrawal.withdrawalId} className="theme-soft-surface rounded-[1.3rem] p-4 text-sm leading-6">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-base font-semibold text-foreground">{formatMembershipPrice(withdrawal.amountCent)}</span>
                  <StatusPill tone={withdrawal.status === "succeeded" ? "accent" : withdrawal.status === "failed" ? "default" : "warm"}>
                    {describeWithdrawalStatus(withdrawal.status)}
                  </StatusPill>
                </div>
                <div className="mt-2 text-xs text-muted-foreground">
                  {withdrawal.identityMaskedLabel || "微信收款身份"} · {formatMembershipDateTime(withdrawal.createdAt)}
                </div>
                {withdrawal.status === "awaiting_confirmation" && withdrawal.confirmation?.mode === "wechat_jsapi_requestMerchantTransfer" ? (
                  <div className="mt-3 flex flex-wrap items-center gap-3">
                    <Button type="button" variant="outline" size="sm" onClick={() => onResumeWithdrawalConfirmation(withdrawal)}>
                      继续微信确认
                    </Button>
                    <div className="text-xs text-muted-foreground">请在微信客户端内继续确认收款。</div>
                  </div>
                ) : null}
              </div>
            ))
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

export function MembershipPage() {
  const [selectedPlanId, setSelectedPlanId] = useState(DEFAULT_MEMBERSHIP_PLAN_ID)
  const [selectedCouponId, setSelectedCouponId] = useState("")
  const [selectedProvider, setSelectedProvider] = useState("")
  const [purchaseOpen, setPurchaseOpen] = useState(false)
  const [couponBagOpen, setCouponBagOpen] = useState(false)
  const [inviteRecordsOpen, setInviteRecordsOpen] = useState(false)
  const [withdrawalRecordsOpen, setWithdrawalRecordsOpen] = useState(false)
  const [latestCheckout, setLatestCheckout] = useState<MembershipCreateOrderResult | null>(null)
  const [withdrawAmountYuan, setWithdrawAmountYuan] = useState("5")
  const [activeBindingAttemptId, setActiveBindingAttemptId] = useState("")
  const [activeBindingQrPayload, setActiveBindingQrPayload] = useState("")
  const [bindingDialogOpen, setBindingDialogOpen] = useState(false)
  const [withdrawalConfirmationUrl, setWithdrawalConfirmationUrl] = useState("")
  const [withdrawalConfirmationDialogOpen, setWithdrawalConfirmationDialogOpen] = useState(false)

  const shouldAutoRefresh = latestCheckout?.order.provider === "wechat_native" && latestCheckout.order.status === "pending"
  const summaryQ = useMembershipSummary(true, shouldAutoRefresh ? 5_000 : false)
  const couponsQ = useMembershipCoupons(20)
  const inviteSummaryQ = useInviteSummary()
  const commissionQ = useCommissionSummary()
  const bindingAttemptQ = usePayoutBindingAttempt(activeBindingAttemptId, Boolean(activeBindingAttemptId), activeBindingAttemptId ? 2_000 : false)
  const withdrawalsQ = useCommissionWithdrawals()
  const ordersQ = useMembershipOrders(20, true, shouldAutoRefresh ? 5_000 : false)
  const pendingOrder = (ordersQ.data ?? []).find((item) => item.status === "pending")
  const effectiveSelectedPlanId = pendingOrder?.planId || selectedPlanId
  const previewQ = useMembershipOrderPreview(selectedCouponId || undefined, effectiveSelectedPlanId)
  const createOrder = useCreateMembershipOrder()
  const confirmPayment = useConfirmMembershipPayment()
  const syncPayment = useSyncMembershipPayment()
  const closeOrder = useCloseMembershipOrder()
  const requestWithdrawal = useRequestCommissionWithdrawal()
  const startPayoutBinding = useStartPayoutBindingAttempt()

  const coupons = couponsQ.data ?? []
  const availableCoupons = coupons.filter((item) => item.status === "available")
  const supportedProviders = summaryQ.data?.supportedPaymentProviders ?? []
  const effectiveSelectedProvider = supportedProviders.includes(selectedProvider)
    ? selectedProvider
    : supportedProviders.includes("wechat_native")
      ? "wechat_native"
      : supportedProviders[0] ?? ""
  const activeCheckout = latestCheckout?.order.orderId === pendingOrder?.orderId ? latestCheckout : null
  const selectedCoupon = useMemo(
    () => availableCoupons.find((item) => item.couponId === selectedCouponId) ?? null,
    [availableCoupons, selectedCouponId],
  )
  const recentInvites = inviteSummaryQ.data?.recentInvites ?? []
  const availableCouponCount = availableCoupons.length
  const usedCouponCount = coupons.filter((coupon) => coupon.status === "used").length
  const expiredCouponCount = coupons.filter((coupon) => coupon.status === "expired").length
  const inviteLabelsByUserId = useMemo(
    () =>
      new Map(
        recentInvites.map((invite) => [invite.inviteeUserId, getInviteDisplayName(invite)]),
      ),
    [recentInvites],
  )
  const autoSyncIntervalMs = Math.max(3, activeCheckout?.paymentPayload.pollIntervalSeconds ?? 5) * 1_000

  useEffect(() => {
    if (!latestCheckout) return
    const refreshedOrder = ordersQ.data?.find((item) => item.orderId === latestCheckout.order.orderId)
    if (refreshedOrder && refreshedOrder.status !== "pending") {
      setLatestCheckout(null)
    }
  }, [latestCheckout, ordersQ.data])

  useEffect(() => {
    const attempt = bindingAttemptQ.data
    if (!attempt) return
    if (attempt.qrCodePayload && attempt.qrCodePayload !== activeBindingQrPayload) {
      setActiveBindingQrPayload(attempt.qrCodePayload)
    }
    if (attempt.status === "bound" || attempt.nextAction === "withdraw" || attempt.nextAction === "confirm_withdrawal") {
      setBindingDialogOpen(false)
      setActiveBindingAttemptId("")
      setActiveBindingQrPayload("")
      if (attempt.withdrawal?.confirmationUrl) {
        setWithdrawalConfirmationUrl(attempt.withdrawal.confirmationUrl)
        setWithdrawalConfirmationDialogOpen(true)
      }
      showSuccessFeedback(
        attempt.withdrawal ? "提现等待微信确认" : "微信收款身份已绑定",
        attempt.withdrawal ? "请用手机微信扫描弹窗二维码确认收款。" : "提现会使用已验证的微信收款身份，页面只显示脱敏标识。",
      )
    }
  }, [activeBindingQrPayload, bindingAttemptQ.data])

  async function syncPaymentStatus(order: MembershipOrder, options?: { manual?: boolean }) {
    const manual = options?.manual ?? true
    try {
      const result = await syncPayment.mutateAsync({ orderId: order.orderId })
      if (result.confirmed) {
        showSuccessFeedback(
          result.idempotent ? "支付状态已同步" : "会员已开通",
          result.membership.currentEndsAt ? `会员有效期已更新到 ${formatMembershipDateTime(result.membership.currentEndsAt)}。` : "会员权益已经发放。",
        )
        setLatestCheckout(null)
        setPurchaseOpen(false)
        return
      }
      if (result.order.status === "closed") {
        setLatestCheckout(null)
        setPurchaseOpen(false)
        showSuccessFeedback(
          "订单已关闭",
          result.remote.remoteStatus === "closed"
            ? "这笔订单已关闭。"
            : result.remote.remoteStatus === "failed"
              ? "支付未完成，这笔订单已结束。"
              : result.remote.remoteStatus === "refunded"
                ? "这笔订单已退款，不会继续等待支付。"
                : "这笔订单已经结束。",
        )
        return
      }
      if (manual) {
        showSuccessFeedback("支付状态已刷新", "这笔订单暂未支付成功，请稍后再试。")
      }
    } catch (err) {
      if (manual) {
        showErrorFeedback("同步支付状态失败", formatMembershipApiError(err))
      }
    }
  }

  useEffect(() => {
    if (!purchaseOpen || !pendingOrder || pendingOrder.provider !== "wechat_native" || syncPayment.isPending) {
      return
    }
    if (activeCheckout?.paymentPayload.provider === "wechat_native" && !activeCheckout.paymentPayload.statusCheckSupported) {
      return
    }
    const timer = window.setInterval(() => {
      void syncPaymentStatus(pendingOrder, { manual: false })
    }, autoSyncIntervalMs)
    return () => window.clearInterval(timer)
  }, [
    purchaseOpen,
    pendingOrder,
    activeCheckout?.paymentPayload.provider,
    activeCheckout?.paymentPayload.statusCheckSupported,
    autoSyncIntervalMs,
    syncPayment.isPending,
  ])

  async function onCreateOrder() {
    if (!effectiveSelectedProvider) {
      showErrorFeedback("创建会员订单失败", "暂未开放支付方式，请稍后再试。")
      return
    }
    try {
      const result = await createOrder.mutateAsync({
        provider: effectiveSelectedProvider,
        planId: effectiveSelectedPlanId,
        couponId: selectedCouponId || undefined,
      })
      setLatestCheckout(result)
      showSuccessFeedback(
        result.reusedExistingOrder ? "待支付订单已更新" : "订单已创建",
        result.paymentPayload.provider === "wechat_native"
          ? `微信支付二维码已经生成，实付 ${formatMembershipPrice(result.order.payableAmountCent)}。`
          : result.order.couponDiscountCent > 0
            ? `本单已使用优惠券，实付 ${formatMembershipPrice(result.order.payableAmountCent)}。`
            : "订单已创建，请继续完成支付。",
      )
    } catch (err) {
      showErrorFeedback("创建会员订单失败", formatMembershipApiError(err))
    }
  }

  async function onConfirmPayment(order: MembershipOrder) {
    try {
      const result = await confirmPayment.mutateAsync({
        provider: order.provider,
        orderId: order.orderId,
        providerTradeNo: `manual_${order.orderId}`,
      })
      showSuccessFeedback(
        result.idempotent ? "支付状态已同步" : "会员已开通",
        result.membership.currentEndsAt ? `会员有效期已更新到 ${formatMembershipDateTime(result.membership.currentEndsAt)}。` : "会员权益已经发放。",
      )
      setLatestCheckout(null)
      setPurchaseOpen(false)
      if (selectedCouponId && order.couponId === selectedCouponId) {
        setSelectedCouponId("")
      }
    } catch (err) {
      showErrorFeedback("确认支付失败", formatMembershipApiError(err))
    }
  }

  async function onSyncPayment(order: MembershipOrder) {
    await syncPaymentStatus(order, { manual: true })
  }

  async function onCloseOrder(order: MembershipOrder) {
    if (typeof window !== "undefined" && !window.confirm("确认关闭这笔待支付订单吗？关闭后不会影响已生效会员权益。")) {
      return
    }
    try {
      const result = await closeOrder.mutateAsync({ orderId: order.orderId })
      setLatestCheckout((current) => (current?.order.orderId === order.orderId ? null : current))
      setPurchaseOpen(false)
      showSuccessFeedback(
        result.idempotent ? "订单已关闭" : "待支付订单已关闭",
        result.order.provider === "wechat_native" ? "这笔订单已停止等待支付。" : "这笔订单已关闭，不会再继续等待支付。",
      )
    } catch (err) {
      showErrorFeedback("关闭订单失败", formatMembershipApiError(err))
    }
  }

  async function onCopyPaymentLink() {
    const codeUrl = activeCheckout?.paymentPayload.codeUrl?.trim()
    if (!codeUrl) return
    try {
      await copyTextToClipboard(codeUrl)
      showSuccessFeedback("支付链接已复制", "支付链接已经复制，可在其他设备上继续支付。")
    } catch (err) {
      showErrorFeedback("复制支付链接失败", formatMembershipApiError(err))
    }
  }

  async function onCopyInviteCode() {
    const inviteCode = inviteSummaryQ.data?.inviteCode?.trim()
    if (!inviteCode) return
    try {
      await copyTextToClipboard(inviteCode)
      showSuccessFeedback("邀请码已复制", `邀请码 ${inviteCode} 已经复制到剪贴板。`)
    } catch (err) {
      showErrorFeedback("复制邀请码失败", formatMembershipApiError(err))
    }
  }

  async function onRequestWithdrawal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const amountCent = Math.round(Number(withdrawAmountYuan) * 100)
    if (!Number.isFinite(amountCent) || amountCent <= 0) {
      showErrorFeedback("提交提现失败", "请输入有效的提现金额。")
      return
    }
    if (payoutReadiness?.status !== "ready") {
      await onStartPayoutBinding(amountCent)
      return
    }
    try {
      const result = await requestWithdrawal.mutateAsync({
        amountCent,
      })
      let confirmationInvoked = false
      if (result.confirmation?.mode === "wechat_jsapi_requestMerchantTransfer") {
        confirmationInvoked = await requestMerchantTransfer(result.confirmation)
      }
      if (!confirmationInvoked && result.status === "awaiting_confirmation" && result.confirmationUrl) {
        setWithdrawalConfirmationUrl(result.confirmationUrl)
        setWithdrawalConfirmationDialogOpen(true)
      }
      showSuccessFeedback(
        result.status === "failed" ? "提现请求已退回" : result.status === "awaiting_confirmation" ? "提现等待微信确认" : "提现请求已提交",
        result.status === "failed"
          ? result.failureReason || "提现失败，金额已退回可提现余额。"
          : result.status === "awaiting_confirmation"
            ? confirmationInvoked
              ? "请在微信内完成收款确认，最终到账状态会由微信通知或后台对账更新。"
              : result.confirmationUrl
                ? "请用手机微信扫描弹窗二维码确认收款。"
                : "提现申请已创建。请在微信客户端里打开会员页，并在提现记录中点击“继续微信确认”。"
            : `已提交 ${formatMembershipPrice(result.amountCent)} 到微信收款账户。`,
      )
      setWithdrawAmountYuan("5")
    } catch (err) {
      showErrorFeedback("提交提现失败", formatMembershipApiError(err))
    }
  }

  async function requestMerchantTransfer(confirmation: WechatMerchantTransferConfirmation) {
    const bridge = await waitForWeixinBridge()
    if (!bridge?.invoke) {
      showErrorFeedback("需要在微信内确认", "当前浏览器不支持微信收款确认，请在微信客户端中打开后继续。")
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
    return true
  }

  async function onResumeWithdrawalConfirmation(withdrawal: CommissionWithdrawal) {
    if (withdrawal.confirmation?.mode !== "wechat_jsapi_requestMerchantTransfer") {
      showErrorFeedback("继续确认失败", "这条提现记录暂时没有可用的微信确认参数，请刷新页面后再试。")
      return
    }
    const invoked = await requestMerchantTransfer(withdrawal.confirmation)
    if (!invoked && withdrawal.confirmationUrl) {
      setWithdrawalConfirmationUrl(withdrawal.confirmationUrl)
      setWithdrawalConfirmationDialogOpen(true)
      showSuccessFeedback("请用微信扫码确认", "用手机微信扫描弹窗二维码后继续确认收款。")
      return
    }
    if (invoked) {
      showSuccessFeedback("已重新发起微信确认", "请在当前微信会话里完成收款确认，到账状态会自动刷新。")
    }
  }

  async function onStartPayoutBinding(amountCent = 0) {
    try {
      const result = await startPayoutBinding.mutateAsync({
        channel: "desktop_qr_official_account_h5",
        returnUrl: typeof window !== "undefined" ? `${window.location.origin}/membership` : "/membership",
        amountCent,
      })
      setActiveBindingAttemptId(result.bindingAttemptId)
      setActiveBindingQrPayload(result.qrCodePayload ?? result.mobileBindingUrl ?? "")
      setBindingDialogOpen(true)
      showSuccessFeedback(
        amountCent > 0 ? "提现扫码已开始" : "微信收款身份绑定已开始",
        amountCent > 0 ? "请用本人微信扫描二维码，手机端会继续完成这笔提现。" : "请用本人微信扫描二维码完成收款账号绑定。",
      )
    } catch (err) {
      showErrorFeedback(amountCent > 0 ? "启动提现扫码失败" : "开始绑定失败", formatMembershipApiError(err))
    }
  }

  if (summaryQ.isLoading && !summaryQ.data) {
    return <LoadingNotice title="正在加载会员中心" message="稍等一下，我们正在整理你的会员状态和权益信息。" />
  }

  if (summaryQ.error && !summaryQ.data) {
    return <ErrorNotice title="会员中心加载失败" message={formatMembershipApiError(summaryQ.error)} />
  }

  const summary = summaryQ.data
  const preview = previewQ.data
  const commissionAccount = commissionQ.data?.account
  const payoutReadiness = commissionQ.data?.payoutReadiness
  const recentWithdrawals = withdrawalsQ.data ?? []
  const membershipState = getMembershipState(summary)
  const purchaseDisabled =
    createOrder.isPending || confirmPayment.isPending || syncPayment.isPending || closeOrder.isPending || (supportedProviders.length === 0 && !pendingOrder)
  const purchaseButtonLabel = pendingOrder ? "继续支付" : summary?.isActive ? "立即续费" : "立即开通"

  return (
    <>
      <CouponBagDialog open={couponBagOpen} onOpenChange={setCouponBagOpen} coupons={coupons} inviteLabelsByUserId={inviteLabelsByUserId} />
      <InviteRecordsDialog
        open={inviteRecordsOpen}
        onOpenChange={setInviteRecordsOpen}
        invites={recentInvites}
        totalInvitedUsers={inviteSummaryQ.data?.totalInvitedUsers ?? 0}
      />
      <WithdrawalRecordsDialog
        open={withdrawalRecordsOpen}
        onOpenChange={setWithdrawalRecordsOpen}
        withdrawals={recentWithdrawals}
        onResumeWithdrawalConfirmation={(withdrawal) => void onResumeWithdrawalConfirmation(withdrawal)}
      />

      <Dialog open={withdrawalConfirmationDialogOpen} onOpenChange={setWithdrawalConfirmationDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>微信扫码确认收款</DialogTitle>
            <DialogDescription>请用收款微信扫描二维码，在手机微信里完成确认。确认后到账状态会自动同步。</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <div className="mx-auto rounded-lg border bg-white p-4">
              {withdrawalConfirmationUrl ? <QRCodeSVG value={withdrawalConfirmationUrl} size={192} level="M" includeMargin /> : null}
            </div>
            <div className="break-all text-center text-xs leading-5 text-muted-foreground">{withdrawalConfirmationUrl}</div>
            <div className="flex justify-end">
              <Button type="button" variant="outline" onClick={() => setWithdrawalConfirmationDialogOpen(false)}>
                稍后确认
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <MembershipPurchaseDialog
        open={purchaseOpen}
        onOpenChange={setPurchaseOpen}
        summary={summary}
        preview={preview}
        previewError={previewQ.error}
        previewLoading={previewQ.isLoading}
        selectedCouponId={selectedCouponId}
        selectedPlanId={effectiveSelectedPlanId}
        selectedProvider={effectiveSelectedProvider}
        supportedProviders={supportedProviders}
        availableCoupons={availableCoupons}
        pendingOrder={pendingOrder}
        activeCheckout={activeCheckout}
        createPending={createOrder.isPending}
        confirmPending={confirmPayment.isPending}
        syncPending={syncPayment.isPending}
        closePending={closeOrder.isPending}
        onSelectCoupon={setSelectedCouponId}
        onSelectPlan={setSelectedPlanId}
        onSelectProvider={setSelectedProvider}
        onConfirmPayment={(order) => void onConfirmPayment(order)}
        onSyncPayment={(order) => void onSyncPayment(order)}
        onCloseOrder={(order) => void onCloseOrder(order)}
        onCopyPaymentLink={() => void onCopyPaymentLink()}
        onConfirm={() => void onCreateOrder()}
      />

      <section className="mx-auto max-w-4xl">
        <div className="theme-card-main overflow-hidden">
          <div className="px-6 py-6 sm:px-8 [background:radial-gradient(circle_at_top_left,hsl(var(--primary)/0.11),transparent_36%),radial-gradient(circle_at_85%_18%,var(--theme-warm-bg),transparent_28%),var(--theme-card-main-bg)]">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-2xl space-y-5">
                <div className="space-y-2">
                  <h1 className="text-3xl font-semibold tracking-tight text-foreground">会员中心</h1>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button asChild variant="ghost">
                    <Link to="/profile">
                      <ChevronLeft className="h-4 w-4" />
                      返回个人中心
                    </Link>
                  </Button>
                  <Button onClick={() => setPurchaseOpen(true)} disabled={purchaseDisabled}>
                    {purchaseButtonLabel}
                  </Button>
                  <Button type="button" variant="outline" onClick={() => void onCopyInviteCode()} disabled={!inviteSummaryQ.data?.inviteCode}>
                    <Copy className="h-4 w-4" />
                    复制邀请码
                  </Button>
                </div>
              </div>

              <div className="grid w-full gap-3 sm:grid-cols-2 lg:w-[34rem]">
                <button
                  type="button"
                  onClick={() => setSelectedPlanId("monthly")}
                  aria-pressed={effectiveSelectedPlanId === "monthly"}
                  className={cn(
                    "rounded-[1.35rem] border px-5 py-4 text-left shadow-[var(--theme-soft-shadow)] backdrop-blur transition",
                    effectiveSelectedPlanId === "monthly"
                      ? "border-primary/30 bg-[hsl(var(--primary)/0.1)]"
                      : "border-[color:var(--theme-soft-border)] bg-[hsl(var(--background)/0.75)] hover:border-primary/20",
                  )}
                >
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">月会员</div>
                  <div className="mt-2 text-2xl font-semibold tracking-tight text-foreground">¥20 / 30 天</div>
                  <div className="mt-2 text-sm leading-6 text-muted-foreground">
                    首单 {formatMembershipPrice(summary?.firstOrderPriceCent ?? 0)} · 续费 {formatMembershipPrice(summary?.renewalPriceCent ?? 0)}
                  </div>
                  {effectiveSelectedPlanId === "monthly" && selectedCoupon ? (
                    <div className="mt-1 text-xs text-[color:var(--theme-warm-text)]">已选 {formatMembershipCouponValue(selectedCoupon)}</div>
                  ) : null}
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedPlanId("graduate_exam")}
                  aria-pressed={effectiveSelectedPlanId === "graduate_exam"}
                  className={cn(
                    "rounded-[1.35rem] border px-5 py-4 text-left shadow-[var(--theme-soft-shadow)] backdrop-blur transition",
                    effectiveSelectedPlanId === "graduate_exam"
                      ? "border-primary/30 bg-[hsl(var(--primary)/0.1)]"
                      : "border-[color:var(--theme-soft-border)] bg-[hsl(var(--background)/0.75)] hover:border-primary/20",
                  )}
                >
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">考研套餐</div>
                  <div className="mt-2 text-2xl font-semibold tracking-tight text-foreground">每日 ¥0.5</div>
                  <div className="mt-2 text-sm leading-6 text-muted-foreground">购买当天到 12 月 21 日自动按天数结算</div>
                  {effectiveSelectedPlanId === "graduate_exam" ? (
                    <div className="mt-1 text-xs text-[color:var(--theme-warm-text)]">
                      {preview?.planId === "graduate_exam"
                        ? `当前预估 ${formatMembershipPrice(preview.payableAmountCent)}`
                        : previewQ.isLoading
                          ? "正在计算当前价格"
                          : "支付前自动计算实际价格"}
                    </div>
                  ) : null}
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1.05fr)_minmax(18rem,0.95fr)]">
          <div className="theme-card-main overflow-hidden">
            <div className="border-b border-[color:var(--theme-soft-border)] px-6 py-5 sm:px-8">
              <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
                <div className="space-y-2">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">当前状态</div>
                  <div className="text-2xl font-semibold tracking-tight text-foreground">{membershipState}</div>
                  {summary?.currentEndsAt ? <div className="text-sm leading-6 text-muted-foreground">有效期至 {formatMembershipDateTime(summary.currentEndsAt)}</div> : null}
                </div>
                <div className="flex w-full max-w-[22rem] flex-col gap-3 md:w-auto">
                  <div className="rounded-[1.25rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-5 py-4">
                    <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">邀请码</div>
                    {inviteSummaryQ.error ? <div className="mt-3 text-sm text-destructive">{formatMembershipApiError(inviteSummaryQ.error)}</div> : null}
                    {!inviteSummaryQ.error ? (
                      <div className="mt-3 space-y-3">
                        <div className="min-w-0">
                          <div className="truncate text-2xl font-semibold tracking-tight text-foreground">{inviteSummaryQ.data?.inviteCode ?? "加载中..."}</div>
                          {inviteSummaryQ.data?.boundInviteCode ? (
                            <div className="mt-1 text-sm text-muted-foreground">已绑定上级邀请码：{inviteSummaryQ.data.boundInviteCode}</div>
                          ) : null}
                        </div>
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-5 px-6 py-6 sm:px-8">
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="theme-soft-surface rounded-[1.2rem] px-4 py-4">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">已邀请</div>
                  <div className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{inviteSummaryQ.data?.totalInvitedUsers ?? 0}</div>
                </div>
                <div className="theme-soft-surface rounded-[1.2rem] px-4 py-4">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">待结算佣金</div>
                  <div className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
                    {formatMembershipPrice(commissionAccount?.pendingCent ?? 0)}
                  </div>
                </div>
                <div className="theme-soft-surface rounded-[1.2rem] px-4 py-4">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">可提现佣金</div>
                  <div className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
                    {formatMembershipPrice(commissionAccount?.withdrawableCent ?? 0)}
                  </div>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <button
                  type="button"
                  className="theme-soft-surface flex items-center justify-between rounded-[1.2rem] px-4 py-4 text-left transition hover:-translate-y-px"
                  onClick={() => setInviteRecordsOpen(true)}
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <Users className="h-4 w-4 text-primary" />
                      <div className="text-sm font-semibold text-foreground">邀请的人</div>
                    </div>
                    <div className="mt-2 text-sm leading-6 text-muted-foreground">
                      {inviteSummaryQ.error
                        ? formatMembershipApiError(inviteSummaryQ.error)
                        : recentInvites.length > 0
                          ? `最近展示 ${recentInvites.length} 条记录`
                          : "暂无邀请记录"}
                    </div>
                  </div>
                  <StatusPill tone="accent">{inviteSummaryQ.data?.totalInvitedUsers ?? 0} 人</StatusPill>
                </button>

                <button
                  type="button"
                  className="theme-soft-surface flex items-center justify-between rounded-[1.2rem] px-4 py-4 text-left transition hover:-translate-y-px"
                  onClick={() => setWithdrawalRecordsOpen(true)}
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <History className="h-4 w-4 text-primary" />
                      <div className="text-sm font-semibold text-foreground">提现记录</div>
                    </div>
                    <div className="mt-2 text-sm leading-6 text-muted-foreground">
                      {recentWithdrawals.length > 0 ? `${recentWithdrawals.length} 条提现申请` : "暂无提现记录"}
                    </div>
                  </div>
                  <StatusPill tone="warm">{recentWithdrawals.length} 条</StatusPill>
                </button>
              </div>

              <div className="space-y-4">
                {commissionQ.error ? <div className="text-sm text-destructive">{formatMembershipApiError(commissionQ.error)}</div> : null}

                {!commissionQ.error ? (
                  <>
                    <div className="grid gap-3 sm:grid-cols-4">
                      <div className="theme-subtle-surface px-3 py-3">
                        <div className="text-xs text-muted-foreground">待结算</div>
                        <div className="mt-1 text-sm font-semibold text-foreground">{formatMembershipPrice(commissionAccount?.pendingCent ?? 0)}</div>
                      </div>
                      <div className="theme-subtle-surface px-3 py-3">
                        <div className="text-xs text-muted-foreground">可提现</div>
                        <div className="mt-1 text-sm font-semibold text-foreground">{formatMembershipPrice(commissionAccount?.withdrawableCent ?? 0)}</div>
                      </div>
                      <div className="theme-subtle-surface px-3 py-3">
                        <div className="text-xs text-muted-foreground">提现中</div>
                        <div className="mt-1 text-sm font-semibold text-foreground">{formatMembershipPrice(commissionAccount?.reservedCent ?? 0)}</div>
                      </div>
                      <div className="theme-subtle-surface px-3 py-3">
                        <div className="text-xs text-muted-foreground">已到账</div>
                        <div className="mt-1 text-sm font-semibold text-foreground">{formatMembershipPrice(commissionAccount?.paidOutCent ?? 0)}</div>
                      </div>
                    </div>

                    <form className="grid gap-3 md:grid-cols-[120px_auto]" onSubmit={(event) => void onRequestWithdrawal(event)}>
                      <div className="space-y-2">
                        <Label htmlFor="commission-withdraw-amount">提现金额</Label>
                        <Input
                          id="commission-withdraw-amount"
                          type="number"
                          min="0.01"
                          step="0.01"
                          value={withdrawAmountYuan}
                          onChange={(event) => setWithdrawAmountYuan(event.target.value)}
                        />
                      </div>
                      <div className="flex items-end">
                        <Button
                          type="submit"
                          disabled={requestWithdrawal.isPending || startPayoutBinding.isPending || (commissionAccount?.withdrawableCent ?? 0) <= 0}
                        >
                          {requestWithdrawal.isPending ? "提交中..." : startPayoutBinding.isPending ? "启动中..." : "申请提现"}
                        </Button>
                      </div>
                    </form>
                  </>
                ) : null}
              </div>
            </div>
          </div>

          <div className="theme-card-main overflow-hidden">
            <div className="border-b border-[color:var(--theme-soft-border)] px-6 py-5 sm:px-8">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <Ticket className="h-4 w-4 text-primary" />
                  <div className="text-sm font-semibold text-foreground">我的优惠券</div>
                </div>
                <Button type="button" variant="outline" onClick={() => setCouponBagOpen(true)} disabled={couponsQ.isLoading}>
                  <Ticket className="h-4 w-4" />
                  券包
                </Button>
              </div>
            </div>

            <div className="space-y-5 px-6 py-6 sm:px-8">
              <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
                <div className="theme-soft-surface rounded-[1.2rem] px-4 py-4">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">可用</div>
                  <div className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{availableCouponCount}</div>
                </div>
                <div className="theme-soft-surface rounded-[1.2rem] px-4 py-4">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">已使用</div>
                  <div className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{usedCouponCount}</div>
                </div>
                <div className="theme-soft-surface rounded-[1.2rem] px-4 py-4">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">已过期</div>
                  <div className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{expiredCouponCount}</div>
                </div>
              </div>

              {couponsQ.error ? <div className="text-sm text-destructive">{formatMembershipApiError(couponsQ.error)}</div> : null}

              {!couponsQ.error && coupons.length === 0 ? (
                <div className="theme-subtle-surface rounded-[1.4rem] border-dashed px-5 py-10 text-center text-sm leading-7 text-[color:var(--theme-subtle-text)]">
                  暂时还没有优惠券。绑定好友邀请码后会收到 7.5 折会员券。
                </div>
              ) : null}

              {coupons.length > 0 ? (
                <div className="space-y-3">
                  {coupons.map((coupon) => {
                    const sourceInviteLabel = coupon.sourceInviteeUserId ? inviteLabelsByUserId.get(coupon.sourceInviteeUserId) : null
                    return (
                      <div key={coupon.couponId} className="theme-soft-surface rounded-[1.3rem] p-4">
                        <div className="flex items-start justify-between gap-4">
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <div className="text-sm font-semibold text-foreground">{coupon.title || describeMembershipCouponSource(coupon.source)}</div>
                              <StatusPill tone={coupon.status === "available" ? "accent" : "default"}>
                                {describeMembershipCouponStatus(coupon.status)}
                              </StatusPill>
                            </div>
                            <div className="mt-2 text-sm leading-6 text-muted-foreground">
                              满 {formatMembershipPrice(coupon.minSpendCent)} 可用，创建于 {formatMembershipDateTime(coupon.createdAt)}。
                            </div>
                            <div className="mt-1 text-xs leading-6 text-[color:var(--theme-subtle-text)]">
                              来源：{describeMembershipCouponSource(coupon.source)}
                              {sourceInviteLabel ? ` · 邀请用户 ${sourceInviteLabel}` : ""}
                            </div>
                          </div>
                          <div className="shrink-0 text-right text-xs leading-6 text-muted-foreground">
                            <div className="text-2xl font-semibold tracking-tight text-foreground">{formatMembershipCouponValue(coupon)}</div>
                            <div className="mt-1">
                              {coupon.status === "used" && coupon.usedAt
                                ? `已于 ${formatMembershipDateTime(coupon.usedAt)} 使用`
                                : coupon.expiresAt
                                  ? `${formatMembershipDateTime(coupon.expiresAt)} 到期`
                                  : "长期有效"}
                            </div>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </section>
      <Dialog open={bindingDialogOpen} onOpenChange={setBindingDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>微信扫码确认提现</DialogTitle>
            <DialogDescription>请使用本人微信扫码，手机端会确认收款账号并继续完成这笔提现。</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <div className="mx-auto rounded-lg border bg-white p-4">
              {activeBindingQrPayload ? <QRCodeSVG value={activeBindingQrPayload} size={192} level="M" includeMargin /> : null}
            </div>
            <div className="text-center text-sm leading-6 text-muted-foreground">
              {bindingAttemptQ.data?.status === "scanned"
                ? "已扫码，请在手机微信中继续确认提现。"
                : bindingAttemptQ.data?.status === "expired"
                  ? "二维码已过期，请重新发起绑定。"
                  : "二维码短时间内有效，请勿让他人扫码。"}
            </div>
            {bindingAttemptQ.error ? <div className="text-sm text-destructive">{formatMembershipApiError(bindingAttemptQ.error)}</div> : null}
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setBindingDialogOpen(false)}>
                稍后再说
              </Button>
              <Button type="button" onClick={() => void onStartPayoutBinding()} disabled={startPayoutBinding.isPending}>
                重新生成
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}

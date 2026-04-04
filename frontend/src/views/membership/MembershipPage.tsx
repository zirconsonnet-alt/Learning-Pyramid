import { ChevronLeft, Copy, Ticket, Users } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"

import type { CouponRecord, InviteReferral, MembershipCreateOrderResult, MembershipOrder } from "@/ui/api/membership"
import { ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/ui/components/ui/dialog"
import {
  useCloseMembershipOrder,
  useConfirmMembershipPayment,
  useCreateMembershipOrder,
  useMembershipCoupons,
  useMembershipOrderPreview,
  useMembershipOrders,
  useMembershipSummary,
  useSyncMembershipPayment,
  useInviteSummary,
} from "@/ui/queries/membership"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { MembershipPurchaseDialog } from "@/views/membership/components/MembershipPurchaseDialog"
import {
  copyTextToClipboard,
  describeInviteRecordStatus,
  describeMembershipCouponSource,
  describeMembershipCouponStatus,
  formatMembershipApiError,
  formatMembershipDateTime,
  formatMembershipPrice,
  StatusPill,
} from "@/views/membership/membershipUi"

function getMembershipState(summary: ReturnType<typeof useMembershipSummary>["data"]) {
  if (summary?.isActive) return "会员有效"
  if (summary?.currentStatus === "expired") return "会员已过期"
  return "尚未开通"
}

function getInviteDisplayName(invite: InviteReferral) {
  return invite.inviteeNickname?.trim() || invite.inviteePublicUid?.trim() || "未命名用户"
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
              暂时还没有优惠券。好友完成首单后，你会收到邀请奖励券。
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
                      <div className="text-2xl font-semibold tracking-tight text-foreground">-{formatMembershipPrice(coupon.amountCent)}</div>
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

export function MembershipPage() {
  const [selectedCouponId, setSelectedCouponId] = useState("")
  const [selectedProvider, setSelectedProvider] = useState("")
  const [purchaseOpen, setPurchaseOpen] = useState(false)
  const [couponBagOpen, setCouponBagOpen] = useState(false)
  const [latestCheckout, setLatestCheckout] = useState<MembershipCreateOrderResult | null>(null)

  const shouldAutoRefresh = latestCheckout?.order.provider === "wechat_native" && latestCheckout.order.status === "pending"
  const summaryQ = useMembershipSummary(true, shouldAutoRefresh ? 5_000 : false)
  const couponsQ = useMembershipCoupons(20)
  const inviteSummaryQ = useInviteSummary()
  const previewQ = useMembershipOrderPreview(selectedCouponId || undefined)
  const ordersQ = useMembershipOrders(20, true, shouldAutoRefresh ? 5_000 : false)
  const createOrder = useCreateMembershipOrder()
  const confirmPayment = useConfirmMembershipPayment()
  const syncPayment = useSyncMembershipPayment()
  const closeOrder = useCloseMembershipOrder()

  const coupons = couponsQ.data ?? []
  const availableCoupons = coupons.filter((item) => item.status === "available")
  const pendingOrder = (ordersQ.data ?? []).find((item) => item.status === "pending")
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

  useEffect(() => {
    if (!latestCheckout) return
    const refreshedOrder = ordersQ.data?.find((item) => item.orderId === latestCheckout.order.orderId)
    if (refreshedOrder && refreshedOrder.status !== "pending") {
      setLatestCheckout(null)
    }
  }, [latestCheckout, ordersQ.data])

  async function onCreateOrder() {
    if (!effectiveSelectedProvider) {
      showErrorFeedback("创建会员订单失败", "暂未开放支付方式，请稍后再试。")
      return
    }
    try {
      const result = await createOrder.mutateAsync({
        provider: effectiveSelectedProvider,
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
      showSuccessFeedback("支付状态已刷新", "这笔订单暂未支付成功，请稍后再试。")
    } catch (err) {
      showErrorFeedback("同步支付状态失败", formatMembershipApiError(err))
    }
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

  if (summaryQ.isLoading && !summaryQ.data) {
    return <LoadingNotice title="正在加载会员中心" message="稍等一下，我们正在整理你的会员状态和权益信息。" />
  }

  if (summaryQ.error && !summaryQ.data) {
    return <ErrorNotice title="会员中心加载失败" message={formatMembershipApiError(summaryQ.error)} />
  }

  const summary = summaryQ.data
  const preview = previewQ.data
  const membershipState = getMembershipState(summary)
  const purchaseDisabled =
    createOrder.isPending || confirmPayment.isPending || syncPayment.isPending || closeOrder.isPending || (supportedProviders.length === 0 && !pendingOrder)
  const purchaseButtonLabel = pendingOrder ? "继续支付" : summary?.isActive ? "立即续费" : "立即开通"
  const currentPriceCent = preview?.payableAmountCent ?? summary?.currentPriceCent ?? 0

  return (
    <>
      <CouponBagDialog open={couponBagOpen} onOpenChange={setCouponBagOpen} coupons={coupons} inviteLabelsByUserId={inviteLabelsByUserId} />

      <MembershipPurchaseDialog
        open={purchaseOpen}
        onOpenChange={setPurchaseOpen}
        summary={summary}
        preview={preview}
        previewError={previewQ.error}
        previewLoading={previewQ.isLoading}
        selectedCouponId={selectedCouponId}
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

              <div className="rounded-[1.35rem] border border-[color:var(--theme-soft-border)] bg-[hsl(var(--background)/0.75)] px-5 py-4 text-right shadow-[var(--theme-soft-shadow)] backdrop-blur">
                <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">当前价格</div>
                <div className="mt-2 text-4xl font-semibold tracking-tight text-foreground">{formatMembershipPrice(currentPriceCent)}</div>
                <div className="mt-2 text-sm text-muted-foreground">
                  首单 {formatMembershipPrice(summary?.firstOrderPriceCent ?? 0)} · 续费 {formatMembershipPrice(summary?.renewalPriceCent ?? 0)}
                </div>
                {selectedCoupon ? <div className="mt-1 text-xs text-[color:var(--theme-warm-text)]">已选券抵扣 -{formatMembershipPrice(selectedCoupon.amountCent)}</div> : null}
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
                <div className="min-w-[18rem] max-w-xl rounded-[1.25rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] px-4 py-4">
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

            <div className="space-y-5 px-6 py-6 sm:px-8">
              <div className="flex items-center gap-2">
                <Users className="h-4 w-4 text-primary" />
                <div className="text-sm font-semibold text-foreground">我邀请的人</div>
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                <div className="theme-soft-surface rounded-[1.2rem] px-4 py-4">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">已邀请</div>
                  <div className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{inviteSummaryQ.data?.totalInvitedUsers ?? 0}</div>
                </div>
                <div className="theme-soft-surface rounded-[1.2rem] px-4 py-4">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">已转化</div>
                  <div className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{inviteSummaryQ.data?.rewardedInviteCount ?? 0}</div>
                </div>
                <div className="theme-soft-surface rounded-[1.2rem] px-4 py-4">
                  <div className="text-[11px] uppercase tracking-[0.14em] text-[color:var(--theme-subtle-text)]">可用券</div>
                  <div className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{availableCouponCount}</div>
                </div>
              </div>

              {inviteSummaryQ.error ? <div className="text-sm text-destructive">{formatMembershipApiError(inviteSummaryQ.error)}</div> : null}

              {!inviteSummaryQ.error && recentInvites.length === 0 ? (
                <div className="theme-subtle-surface rounded-[1.4rem] border-dashed px-5 py-10 text-center text-sm leading-7 text-[color:var(--theme-subtle-text)]">
                  还没有邀请记录。把邀请码发给朋友后，这里会列出已绑定和已转化的用户。
                </div>
              ) : null}

              {recentInvites.length > 0 ? (
                <div className="space-y-3">
                  {recentInvites.map((invite) => (
                    <div key={`${invite.inviteeUserId}-${invite.boundAt}`} className="theme-soft-surface rounded-[1.3rem] p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <div className="text-sm font-semibold text-foreground">{getInviteDisplayName(invite)}</div>
                            <StatusPill tone={invite.status === "rewarded" ? "accent" : "default"}>{describeInviteRecordStatus(invite.status)}</StatusPill>
                          </div>
                          {invite.inviteePublicUid ? (
                            <div className="mt-1 font-mono text-xs text-[color:var(--theme-subtle-text)]">UID {invite.inviteePublicUid}</div>
                          ) : null}
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
                  ))}
                  {inviteSummaryQ.data && inviteSummaryQ.data.totalInvitedUsers > recentInvites.length ? (
                    <div className="text-xs leading-6 text-[color:var(--theme-subtle-text)]">
                      当前展示最近 {recentInvites.length} 条邀请记录，共 {inviteSummaryQ.data.totalInvitedUsers} 人。
                    </div>
                  ) : null}
                </div>
              ) : null}
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
                  暂时还没有优惠券。好友完成首单后，你会收到邀请奖励券。
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
                            <div className="text-2xl font-semibold tracking-tight text-foreground">-{formatMembershipPrice(coupon.amountCent)}</div>
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
    </>
  )
}

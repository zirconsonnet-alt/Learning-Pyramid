import { useEffect, useState } from "react"
import { Copy, Gift, ReceiptText, ShieldCheck, Sparkles, Ticket, UsersRound } from "lucide-react"

import type { CouponRecord, MembershipCreateOrderResult, MembershipOrder } from "@/ui/api/membership"
import { ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import {
  useBindInviteCode,
  useCloseMembershipOrder,
  useConfirmMembershipPayment,
  useCreateMembershipOrder,
  useInviteSummary,
  useMembershipCoupons,
  useMembershipOrderPreview,
  useMembershipOrders,
  useMembershipSummary,
  useSyncMembershipPayment,
} from "@/ui/queries/membership"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { MembershipPurchaseDialog } from "@/views/membership/components/MembershipPurchaseDialog"
import {
  copyTextToClipboard,
  describeInviteRecordStatus,
  describeMembershipCouponSource,
  describeMembershipCouponStatus,
  describeMembershipOrderStatus,
  describeMembershipOrderType,
  describeMembershipPaymentProvider,
  formatMembershipApiError,
  formatMembershipDateTime,
  formatMembershipPrice,
  StatusPill,
} from "@/views/membership/membershipUi"

function CouponSummaryCard(props: { coupon: CouponRecord }) {
  const { coupon } = props
  return (
    <div className="rounded-[1.25rem] border border-[#dfe7ef] bg-white/90 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-foreground">{coupon.title || describeMembershipCouponSource(coupon.source)}</div>
          <div className="mt-1 text-xs leading-5 text-muted-foreground">满 {formatMembershipPrice(coupon.minSpendCent)} 可用</div>
        </div>
        <StatusPill tone={coupon.status === "available" ? "accent" : "default"}>{describeMembershipCouponStatus(coupon.status)}</StatusPill>
      </div>
      <div className="mt-3 flex items-end justify-between gap-4">
        <div className="text-2xl font-semibold tracking-tight text-[#17324d]">-{formatMembershipPrice(coupon.amountCent)}</div>
        <div className="text-right text-xs text-muted-foreground">
          <div>{coupon.status === "used" ? "使用时间" : "到期时间"}</div>
          <div>{formatMembershipDateTime(coupon.usedAt ?? coupon.expiresAt)}</div>
        </div>
      </div>
    </div>
  )
}

export function MembershipPage() {
  const [selectedCouponId, setSelectedCouponId] = useState("")
  const [selectedProvider, setSelectedProvider] = useState("")
  const [inviteCodeInput, setInviteCodeInput] = useState("")
  const [purchaseOpen, setPurchaseOpen] = useState(false)
  const [latestCheckout, setLatestCheckout] = useState<MembershipCreateOrderResult | null>(null)
  const shouldAutoRefresh = latestCheckout?.order.provider === "wechat_native" && latestCheckout.order.status === "pending"
  const summaryQ = useMembershipSummary(true, shouldAutoRefresh ? 5_000 : false)
  const inviteSummaryQ = useInviteSummary()
  const couponsQ = useMembershipCoupons(20)
  const previewQ = useMembershipOrderPreview(selectedCouponId || undefined)
  const ordersQ = useMembershipOrders(20, true, shouldAutoRefresh ? 5_000 : false)
  const createOrder = useCreateMembershipOrder()
  const confirmPayment = useConfirmMembershipPayment()
  const syncPayment = useSyncMembershipPayment()
  const closeOrder = useCloseMembershipOrder()
  const bindInvite = useBindInviteCode()

  const availableCoupons = (couponsQ.data ?? []).filter((item) => item.status === "available")
  const couponHistory = (couponsQ.data ?? []).slice(0, 6)
  const pendingOrder = (ordersQ.data ?? []).find((item) => item.status === "pending")
  const supportedProviders = summaryQ.data?.supportedPaymentProviders ?? []
  const effectiveSelectedProvider = supportedProviders.includes(selectedProvider)
    ? selectedProvider
    : supportedProviders.includes("wechat_native")
      ? "wechat_native"
      : supportedProviders[0] ?? ""
  const activeCheckout = latestCheckout?.order.orderId === pendingOrder?.orderId ? latestCheckout : null

  useEffect(() => {
    if (!latestCheckout) return
    const refreshedOrder = ordersQ.data?.find((item) => item.orderId === latestCheckout.order.orderId)
    if (refreshedOrder && refreshedOrder.status !== "pending") {
      setLatestCheckout(null)
    }
  }, [latestCheckout, ordersQ.data])

  async function onCreateOrder() {
    if (!effectiveSelectedProvider) {
      showErrorFeedback("创建会员订单失败", "当前部署还没有开启可用支付方式。请先完成微信支付配置。")
      return
    }
    try {
      const result = await createOrder.mutateAsync({
        provider: effectiveSelectedProvider,
        couponId: selectedCouponId || undefined,
      })
      setLatestCheckout(result)
      showSuccessFeedback(
        result.reusedExistingOrder ? "已更新待支付订单" : "会员订单已创建",
        result.paymentPayload.provider === "wechat_native"
          ? `微信支付二维码已经生成，实付 ${formatMembershipPrice(result.order.payableAmountCent)}。`
          : result.order.couponDiscountCent > 0
            ? `本单已使用优惠券，实付 ${formatMembershipPrice(result.order.payableAmountCent)}。`
            : "这笔订单已经生成，现在可以继续完成测试支付链路。",
      )
      setPurchaseOpen(false)
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
      if (selectedCouponId && order.couponId === selectedCouponId) {
        setSelectedCouponId("")
      }
    } catch (err) {
      showErrorFeedback("模拟支付失败", formatMembershipApiError(err))
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
        return
      }
      if (result.order.status === "closed") {
        setLatestCheckout(null)
        showSuccessFeedback(
          "订单已关闭",
          result.remote.remoteStatus === "closed"
            ? "微信侧这笔订单已经关闭，本地待支付单也已一并关闭。"
            : result.remote.remoteStatus === "failed"
              ? "微信侧返回支付失败，本地待支付单已经结束。"
              : result.remote.remoteStatus === "refunded"
                ? "渠道显示这笔订单已退款，本地不会再继续等待支付。"
                : `渠道当前返回 ${result.remote.remoteStatus}，这笔订单已经结束。`,
        )
        return
      }
      showSuccessFeedback("支付状态已刷新", `渠道当前返回 ${result.remote.remoteStatus}，这笔订单还没有进入已支付状态。`)
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
      showSuccessFeedback(
        result.idempotent ? "订单已关闭" : "待支付订单已关闭",
        result.order.provider === "wechat_native" ? "这笔微信待支付订单已停止等待支付。" : "这笔测试订单已经关闭，不会再继续等待支付。",
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
      showSuccessFeedback("支付链接已复制", "微信 Native 支付链接已经复制，可以用于排查或转给其他二维码工具。")
    } catch (err) {
      showErrorFeedback("复制支付链接失败", formatMembershipApiError(err))
    }
  }

  async function onBindInviteCode() {
    const inviteCode = inviteCodeInput.trim()
    if (!inviteCode) return
    try {
      const result = await bindInvite.mutateAsync({ inviteCode })
      showSuccessFeedback("邀请码已绑定", `当前账号已绑定邀请码 ${result.inviteCode}。`)
      setInviteCodeInput("")
    } catch (err) {
      showErrorFeedback("绑定邀请码失败", formatMembershipApiError(err))
    }
  }

  async function onCopyInviteCode() {
    const inviteCode = inviteSummaryQ.data?.inviteCode?.trim()
    if (!inviteCode) return
    try {
      await copyTextToClipboard(inviteCode)
      showSuccessFeedback("邀请码已复制", `邀请码 ${inviteCode} 已经复制到剪贴板。`)
    } catch (err) {
      showErrorFeedback("复制失败", formatMembershipApiError(err))
    }
  }

  if (summaryQ.isLoading && !summaryQ.data) {
    return <LoadingNotice title="正在加载会员中心" message="稍等一下，我们正在整理你的会员状态、邀请记录和优惠券信息。" />
  }

  if (summaryQ.error && !summaryQ.data) {
    return <ErrorNotice title="会员中心加载失败" message={formatMembershipApiError(summaryQ.error)} />
  }

  const summary = summaryQ.data
  const inviteSummary = inviteSummaryQ.data
  const preview = previewQ.data
  const recentInvites = inviteSummary?.recentInvites ?? []
  const purchaseEntryDescription =
    supportedProviders.length === 0
      ? "当前部署还没有开启可用支付方式。完成微信支付配置后，这里会开放创建订单。"
      : supportedProviders.includes("manual_test") && !supportedProviders.includes("wechat_native")
        ? "当前部署保留测试支付链路，适合本地或验收环境继续验证会员流程。"
        : "先通过弹窗确认价格和支付方式，再创建待支付订单。当前部署会直接生成微信扫码支付二维码。"
  const ordersDescription = supportedProviders.includes("manual_test")
    ? "待支付订单会根据渠道展示不同操作。微信扫码支付会显示二维码和状态同步入口；测试环境会额外显示模拟成功按钮。"
    : "待支付订单会根据渠道展示不同操作。微信扫码支付会显示二维码和状态同步入口。"

  return (
    <>
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
        createPending={createOrder.isPending}
        confirmPending={confirmPayment.isPending}
        onSelectCoupon={setSelectedCouponId}
        onSelectProvider={setSelectedProvider}
        onConfirm={() => void onCreateOrder()}
      />

      <div className="space-y-6">
        <section className="rounded-[2rem] border border-[#d6e2ee] bg-[radial-gradient(circle_at_top_left,_rgba(226,239,255,0.9),_rgba(255,255,255,0.98)_46%),radial-gradient(circle_at_80%_20%,_rgba(255,226,176,0.28),_transparent_28%),linear-gradient(135deg,_#f7fbff_0%,_#edf5ff_100%)] p-6 shadow-[0_24px_50px_-38px_rgba(15,23,42,0.38)]">
          <div className="flex flex-col gap-6 xl:flex-row xl:items-start xl:justify-between">
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <StatusPill tone="accent">{summary?.isActive ? "会员有效" : "月会员"}</StatusPill>
                <StatusPill>{summary?.isFirstOrderEligible ? "首单 14.9" : "续费 19.9"}</StatusPill>
                {availableCoupons.length > 0 ? <StatusPill tone="warm">可用券 {availableCoupons.length} 张</StatusPill> : null}
              </div>
              <div className="space-y-2">
                <h1 className="text-3xl font-semibold tracking-tight text-[#17324d]">会员中心</h1>
                <p className="max-w-3xl text-sm leading-7 text-[#60728a]">
                  会员状态、邀请码、优惠券和最近邀请记录都集中在这里。可用支付方式会跟随当前部署配置自动显示，不需要再手动区分环境。
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  onClick={() => setPurchaseOpen(true)}
                  disabled={createOrder.isPending || confirmPayment.isPending || syncPayment.isPending || closeOrder.isPending || (supportedProviders.length === 0 && !pendingOrder)}
                >
                  {pendingOrder ? "继续待支付订单" : summary?.isActive ? "立即续费" : "立即开通"}
                </Button>
                <Button variant="outline" onClick={() => void onCopyInviteCode()} disabled={!inviteSummary?.inviteCode}>
                  <Copy className="h-4 w-4" />
                  复制邀请码
                </Button>
              </div>
            </div>

            <div className="grid gap-3 sm:min-w-[20rem]">
              <Card className="border-white/80 bg-white/84 shadow-[0_18px_36px_-30px_rgba(15,23,42,0.22)]">
                <CardHeader className="pb-3">
                  <CardDescription>当前可开通价格</CardDescription>
                  <CardTitle className="text-3xl">{formatMembershipPrice(preview?.payableAmountCent ?? summary?.currentPriceCent ?? 0)}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 text-sm text-[#5f7188]">
                  <div>首单优惠价：{formatMembershipPrice(summary?.firstOrderPriceCent ?? 0)}</div>
                  <div>标准续费价：{formatMembershipPrice(summary?.renewalPriceCent ?? 0)}</div>
                  <div>邀请码：{inviteSummary?.inviteCode ?? "加载中..."}</div>
                  {preview?.couponDiscountCent ? <div>已选券抵扣：-{formatMembershipPrice(preview.couponDiscountCent)}</div> : null}
                </CardContent>
              </Card>
            </div>
          </div>
        </section>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(20rem,0.9fr)]">
          <Card className="border-[#d9e3ee] bg-white/86">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-xl">
                <ShieldCheck className="h-5 w-5 text-primary" />
                当前会员状态
              </CardTitle>
              <CardDescription>这里会把当前会员、下次结算和最近购买预览放在一起看。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-3">
              <div className="rounded-[1.4rem] border border-[#d9e6f2] bg-[#f8fbff] p-4">
                <div className="text-[11px] uppercase tracking-[0.14em] text-[#7a8ca3]">状态</div>
                <div className="mt-2 text-2xl font-semibold tracking-tight text-[#17324d]">
                  {summary?.isActive ? "会员有效" : summary?.currentStatus === "expired" ? "会员已过期" : "尚未开通"}
                </div>
                <div className="mt-2 text-sm leading-6 text-[#62758d]">
                  {summary?.currentEndsAt ? `有效期至 ${formatMembershipDateTime(summary.currentEndsAt)}` : "当前还没有生效中的会员权益。"}
                </div>
              </div>
              <div className="rounded-[1.4rem] border border-[#d9e6f2] bg-[#f8fbff] p-4">
                <div className="text-[11px] uppercase tracking-[0.14em] text-[#7a8ca3]">本单预览</div>
                {previewQ.error ? <div className="mt-2 text-sm text-destructive">{formatMembershipApiError(previewQ.error)}</div> : null}
                {!previewQ.error && preview ? (
                  <div className="mt-2 space-y-2 text-sm leading-6 text-[#62758d]">
                    <div>订单类型：{describeMembershipOrderType(preview.orderType)}</div>
                    <div>原价：{formatMembershipPrice(preview.listAmountCent)}</div>
                    <div>首单优惠：-{formatMembershipPrice(preview.firstOrderDiscountCent)}</div>
                    <div>优惠券抵扣：-{formatMembershipPrice(preview.couponDiscountCent)}</div>
                    <div className="font-medium text-[#17324d]">实付：{formatMembershipPrice(preview.payableAmountCent)}</div>
                  </div>
                ) : null}
              </div>
              <div className="rounded-[1.4rem] border border-[#d9e6f2] bg-[#f8fbff] p-4">
                <div className="text-[11px] uppercase tracking-[0.14em] text-[#7a8ca3]">购买入口</div>
                <div className="mt-2 text-sm leading-6 text-[#62758d]">{purchaseEntryDescription}</div>
                <Button
                  onClick={() => setPurchaseOpen(true)}
                  className="mt-4 w-full"
                  disabled={createOrder.isPending || confirmPayment.isPending || syncPayment.isPending || closeOrder.isPending || (supportedProviders.length === 0 && !pendingOrder)}
                >
                  {pendingOrder ? "更新待支付订单" : "打开购买弹窗"}
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card className="border-[#d9e3ee] bg-white/86">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-xl">
                <Gift className="h-5 w-5 text-primary" />
                邀请关系
              </CardTitle>
              <CardDescription>支持注册时填邀请码，也支持在首单支付前补绑一次。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm leading-6 text-[#62758d]">
              {inviteSummaryQ.error ? <div className="text-sm text-destructive">{formatMembershipApiError(inviteSummaryQ.error)}</div> : null}
              <div className="rounded-[1.2rem] border border-[#dbe6f1] bg-[#f8fbff] p-4">
                <div className="font-medium text-[#17324d]">我的邀请码</div>
                <div className="mt-2 text-2xl font-semibold tracking-tight text-[#17324d]">{inviteSummary?.inviteCode ?? "加载中..."}</div>
                <div className="mt-2 text-sm text-[#62758d]">
                  已邀请 {inviteSummary?.totalInvitedUsers ?? 0} 人，已触发奖励 {inviteSummary?.rewardedInviteCount ?? 0} 次
                </div>
              </div>
              <div className="rounded-[1.2rem] border border-[#dbe6f1] bg-[#f8fbff] p-4">
                <div className="font-medium text-[#17324d]">我绑定的邀请码</div>
                {inviteSummary?.boundInviteCode ? (
                  <div className="mt-2 space-y-1">
                    <div className="text-lg font-semibold text-[#17324d]">{inviteSummary.boundInviteCode}</div>
                    <div className="text-sm text-[#62758d]">绑定于 {formatMembershipDateTime(inviteSummary.boundAt)}</div>
                  </div>
                ) : (
                  <div className="mt-3 space-y-3">
                    <div className="grid gap-2">
                      <Label htmlFor="membershipInviteCode">输入邀请码</Label>
                      <Input
                        id="membershipInviteCode"
                        value={inviteCodeInput}
                        onChange={(event) => setInviteCodeInput(event.target.value.toUpperCase())}
                        placeholder="首单支付前可绑定一次"
                      />
                    </div>
                    <Button onClick={() => void onBindInviteCode()} disabled={bindInvite.isPending || !inviteCodeInput.trim()} className="w-full">
                      {bindInvite.isPending ? "绑定中..." : "绑定邀请码"}
                    </Button>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <Card className="border-[#d9e3ee] bg-white/86">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-xl">
                <UsersRound className="h-5 w-5 text-primary" />
                最近邀请记录
              </CardTitle>
              <CardDescription>这里会显示最近绑定的邀请码用户，以及是否已经触发奖励。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {recentInvites.length === 0 ? (
                <div className="rounded-[1.4rem] border border-dashed border-[#d7e0ea] bg-[#fbfdff] px-5 py-10 text-center text-sm text-[#697b92]">
                  还没有邀请记录。分享邀请码给好友后，这里会开始出现转化轨迹。
                </div>
              ) : null}
              {recentInvites.map((item) => (
                <div key={item.inviteeUserId} className="rounded-[1.25rem] border border-[#dfe7ef] bg-white/90 p-4">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="text-sm font-semibold text-foreground">{item.inviteeNickname || item.inviteePublicUid || item.inviteeUserId}</div>
                        <StatusPill tone={item.status === "rewarded" ? "accent" : "default"}>{describeInviteRecordStatus(item.status)}</StatusPill>
                      </div>
                      <div className="mt-2 text-sm leading-6 text-muted-foreground">
                        绑定于 {formatMembershipDateTime(item.boundAt)}
                        {item.rewardedAt ? `，奖励发放于 ${formatMembershipDateTime(item.rewardedAt)}` : "，暂未触发奖励"}
                      </div>
                    </div>
                    <div className="shrink-0 text-right text-xs text-muted-foreground">
                      <div>{item.inviteePublicUid ?? "未记录 UID"}</div>
                    </div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="border-[#d9e3ee] bg-white/86">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-xl">
                <Ticket className="h-5 w-5 text-primary" />
                优惠券
              </CardTitle>
              <CardDescription>上半部分看当前可用券，下半部分看最近的券历史。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {couponsQ.error ? <ErrorNotice title="优惠券加载失败" message={formatMembershipApiError(couponsQ.error)} /> : null}
              {!couponsQ.error ? (
                <>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-semibold text-foreground">当前可用</div>
                      <StatusPill tone={availableCoupons.length > 0 ? "accent" : "default"}>{availableCoupons.length} 张</StatusPill>
                    </div>
                    {availableCoupons.length === 0 ? (
                      <div className="rounded-[1.25rem] border border-dashed border-[#d7e0ea] bg-[#fbfdff] px-4 py-8 text-center text-sm text-[#697b92]">
                        还没有可用优惠券。邀请好友首单成功后，这里会自动出现 5 元券。
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {availableCoupons.slice(0, 3).map((coupon) => (
                          <CouponSummaryCard key={coupon.couponId} coupon={coupon} />
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="space-y-3 border-t border-[#dbe6f1] pt-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-semibold text-foreground">最近历史</div>
                      <StatusPill>{couponHistory.length} 条</StatusPill>
                    </div>
                    {couponHistory.length === 0 ? (
                      <div className="rounded-[1.25rem] border border-dashed border-[#d7e0ea] bg-[#fbfdff] px-4 py-8 text-center text-sm text-[#697b92]">
                        还没有任何优惠券记录。
                      </div>
                    ) : (
                      <div className="space-y-3">
                        {couponHistory.map((coupon) => (
                          <CouponSummaryCard key={coupon.couponId} coupon={coupon} />
                        ))}
                      </div>
                    )}
                  </div>
                </>
              ) : null}
            </CardContent>
          </Card>
        </div>

        <Card className="border-[#d9e3ee] bg-white/86">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-xl">
              <Sparkles className="h-5 w-5 text-primary" />
              当前轮次说明
            </CardTitle>
            <CardDescription>这一轮把待支付异常也接住了，用户可以主动关单，远端关闭或失败时本地也会同步结束，不再一直挂着。</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-3 text-sm leading-6 text-[#62758d]">
            <div className="rounded-[1.2rem] border border-[#dbe6f1] bg-[#f8fbff] p-4">
              <div className="font-medium text-[#17324d]">待支付订单可主动关闭</div>
              <div className="mt-2">如果用户临时不付了，可以直接在会员中心关闭待支付订单，避免历史里一直挂着一个 pending。</div>
            </div>
            <div className="rounded-[1.2rem] border border-[#dbe6f1] bg-[#f8fbff] p-4">
              <div className="font-medium text-[#17324d]">远端异常状态会落回本地</div>
              <div className="mt-2">微信那边如果已经关单、支付失败或出现终态，本地同步后也会把订单结束掉，不会继续假装在等待支付。</div>
            </div>
            <div className="rounded-[1.2rem] border border-[#dbe6f1] bg-[#f8fbff] p-4">
              <div className="font-medium text-[#17324d]">用户和后台处置一致</div>
              <div className="mt-2">用户侧能关单，后台也能看到同样的关闭结果和异常原因，排障时不会出现两边状态对不上的情况。</div>
            </div>
          </CardContent>
        </Card>

        <Card className="border-[#d9e3ee] bg-white/86">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-xl">
                <ReceiptText className="h-5 w-5 text-primary" />
                最近订单
              </CardTitle>
              <CardDescription>{ordersDescription}</CardDescription>
            </CardHeader>
          <CardContent className="space-y-4">
            {ordersQ.error ? <ErrorNotice title="订单列表加载失败" message={formatMembershipApiError(ordersQ.error)} /> : null}
            {!ordersQ.error && ordersQ.isLoading ? <LoadingNotice title="正在加载订单列表" message="我们正在同步最近的会员订单状态。" /> : null}
            {!ordersQ.error && !ordersQ.isLoading && (ordersQ.data?.length ?? 0) === 0 ? (
              <div className="rounded-[1.4rem] border border-dashed border-[#d7e0ea] bg-[#fbfdff] px-5 py-10 text-center text-sm text-[#697b92]">
                你还没有会员订单。可以先打开购买弹窗创建第一笔订单。
              </div>
            ) : null}
            {ordersQ.data?.map((order) => (
              <div key={order.orderId} className="rounded-[1.4rem] border border-[#dfe7ef] bg-white/90 p-4">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="text-sm font-semibold text-foreground">{describeMembershipOrderType(order.orderType)}</div>
                      <StatusPill
                        tone={
                          order.status === "paid"
                            ? "accent"
                            : order.status === "pending"
                              ? "warm"
                              : order.status === "closed" || order.status === "refunded"
                                ? "default"
                                : "default"
                        }
                      >
                        {describeMembershipOrderStatus(order.status)}
                      </StatusPill>
                      <StatusPill>{describeMembershipPaymentProvider(order.provider)}</StatusPill>
                      {order.couponDiscountCent > 0 ? <StatusPill tone="warm">已用券</StatusPill> : null}
                    </div>
                    <div className="text-sm text-muted-foreground">订单号：{order.orderId}</div>
                    <div className="text-sm text-muted-foreground">
                      创建于 {formatMembershipDateTime(order.createdAt)}
                      {order.paidAt ? `，支付于 ${formatMembershipDateTime(order.paidAt)}` : ""}
                      {order.closedAt ? `，关闭于 ${formatMembershipDateTime(order.closedAt)}` : ""}
                    </div>
                    <div className="space-y-1 text-sm text-muted-foreground">
                      <div>原价：{formatMembershipPrice(order.listAmountCent)} / {order.periodDays} 天</div>
                      <div>首单优惠：-{formatMembershipPrice(order.firstOrderDiscountCent)}</div>
                      <div>优惠券抵扣：-{formatMembershipPrice(order.couponDiscountCent)}</div>
                    </div>
                    {order.remark ? <div className="text-xs text-[#74859b]">状态说明：{order.remark}</div> : null}
                    {order.status === "pending" && order.provider === "wechat_native" ? (
                      <div className="rounded-[1.2rem] border border-[#dbe6f1] bg-[#f7fbff] p-4 text-sm leading-6 text-[#5f7188]">
                        <div className="font-medium text-[#17324d]">微信支付</div>
                        {activeCheckout?.order.orderId === order.orderId && activeCheckout.paymentPayload.qrImageDataUrl ? (
                          <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-start">
                            <img
                              src={activeCheckout.paymentPayload.qrImageDataUrl}
                              alt="微信支付二维码"
                              className="h-40 w-40 rounded-2xl border border-[#d7e3ef] bg-white p-2"
                            />
                            <div className="min-w-0 space-y-2">
                              <div>{activeCheckout.paymentPayload.instruction}</div>
                              <div>失效时间：{formatMembershipDateTime(activeCheckout.paymentPayload.expiresAt)}</div>
                              <div className="break-all text-xs text-[#6b7c92]">{activeCheckout.paymentPayload.codeUrl}</div>
                              <div className="flex flex-wrap gap-2">
                                <Button variant="outline" onClick={() => void onCopyPaymentLink()}>
                                  <Copy className="h-4 w-4" />
                                  复制支付链接
                                </Button>
                                <Button
                                  variant="outline"
                                  onClick={() => void onSyncPayment(order)}
                                  disabled={syncPayment.isPending || closeOrder.isPending}
                                >
                                  {syncPayment.isPending ? "同步中..." : "同步支付状态"}
                                </Button>
                                <Button variant="outline" onClick={() => void onCloseOrder(order)} disabled={closeOrder.isPending || syncPayment.isPending}>
                                  {closeOrder.isPending ? "关闭中..." : "关闭待支付订单"}
                                </Button>
                              </div>
                            </div>
                          </div>
                        ) : (
                          <div className="mt-2 space-y-2">
                            <div>这个待支付订单还没有在当前页面保留二维码。重新打开购买弹窗并确认一次，就能刷新这笔订单的微信二维码。</div>
                            <div className="flex flex-wrap gap-2">
                              <Button variant="outline" onClick={() => setPurchaseOpen(true)} disabled={createOrder.isPending}>
                                重新获取二维码
                              </Button>
                              <Button variant="outline" onClick={() => void onSyncPayment(order)} disabled={syncPayment.isPending || closeOrder.isPending}>
                                {syncPayment.isPending ? "同步中..." : "同步支付状态"}
                              </Button>
                              <Button variant="outline" onClick={() => void onCloseOrder(order)} disabled={closeOrder.isPending || syncPayment.isPending}>
                                {closeOrder.isPending ? "关闭中..." : "关闭待支付订单"}
                              </Button>
                            </div>
                          </div>
                        )}
                      </div>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 flex-col gap-2 lg:min-w-[12rem]">
                    <div className="rounded-2xl border border-[#dbe6f1] bg-[#f7fbff] px-4 py-3 text-right">
                      <div className="text-[11px] uppercase tracking-[0.14em] text-[#7a8ca3]">实付金额</div>
                      <div className="mt-1 text-2xl font-semibold tracking-tight text-[#17324d]">{formatMembershipPrice(order.payableAmountCent)}</div>
                    </div>
                    {order.status === "pending" && order.provider === "manual_test" ? (
                      <div className="grid gap-2">
                        <Button onClick={() => void onConfirmPayment(order)} disabled={confirmPayment.isPending || closeOrder.isPending} className="w-full">
                          {confirmPayment.isPending ? "处理中..." : "模拟支付成功"}
                        </Button>
                        <Button variant="outline" onClick={() => void onCloseOrder(order)} disabled={closeOrder.isPending || confirmPayment.isPending}>
                          {closeOrder.isPending ? "关闭中..." : "关闭待支付订单"}
                        </Button>
                      </div>
                    ) : null}
                    {order.status === "pending" && order.provider === "wechat_native" ? (
                      <div className="rounded-2xl border border-[#dbe6f1] bg-[#f7fbff] px-4 py-3 text-sm leading-6 text-[#5f7188]">
                        <div>渠道：{describeMembershipPaymentProvider(order.provider)}</div>
                        <div>状态：等待扫码支付</div>
                        <div className="mt-2">成功支付后这里会自动更新；如果微信侧已经关闭或失败，手动同步后本地也会结束这笔单。</div>
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </>
  )
}

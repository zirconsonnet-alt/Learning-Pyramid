import { ArrowRight, Copy, Gift, Ticket } from "lucide-react"
import { Link } from "react-router-dom"

import { Button } from "@/ui/components/ui/button"
import { useCommissionSummary, useInviteSummary, useMembershipCoupons, useMembershipSummary, usePayoutIdentity } from "@/ui/queries/membership"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import {
  copyTextToClipboard,
  describeMembershipCouponSource,
  formatMembershipApiError,
  formatMembershipCouponValue,
  formatMembershipDateTime,
  formatMembershipPrice,
  StatusPill,
} from "@/views/membership/membershipUi"

export function MembershipProfilePanel() {
  const summaryQ = useMembershipSummary()
  const inviteSummaryQ = useInviteSummary()
  const couponsQ = useMembershipCoupons(6)
  const commissionQ = useCommissionSummary(3)
  const payoutIdentityQ = usePayoutIdentity()

  const summary = summaryQ.data
  const inviteSummary = inviteSummaryQ.data
  const commissionAccount = commissionQ.data?.account
  const payoutIdentity = payoutIdentityQ.data
  const availableCoupons = (couponsQ.data ?? []).filter((item) => item.status === "available").slice(0, 3)

  async function onCopyInviteCode() {
    const inviteCode = inviteSummary?.inviteCode?.trim()
    if (!inviteCode) return
    try {
      await copyTextToClipboard(inviteCode)
      showSuccessFeedback("邀请码已复制", `邀请码 ${inviteCode} 已经复制到剪贴板。`)
    } catch (err) {
      showErrorFeedback("复制失败", formatMembershipApiError(err))
    }
  }

  return (
    <section className="theme-card-main p-5 [background:radial-gradient(circle_at_top_left,hsl(var(--primary)/0.1),transparent_36%),var(--theme-card-main-bg)]">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <StatusPill tone="warm">会员与邀请</StatusPill>
            {summary?.isActive ? <StatusPill tone="accent">会员有效</StatusPill> : <StatusPill>未开通</StatusPill>}
          </div>
          <div className="text-2xl font-semibold tracking-tight text-foreground">会员状态、邀请码和优惠券都在这里</div>
          <div className="max-w-2xl text-sm leading-7 text-muted-foreground">
            先看看当前状态，需要时再去会员中心开通、续费或查看订单。
          </div>
        </div>
        <Button asChild className="shrink-0">
          <Link to="/membership">
            进入会员中心
            <ArrowRight className="h-4 w-4" />
          </Link>
        </Button>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.05fr)_minmax(18rem,0.95fr)]">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="theme-soft-surface p-4">
            <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">会员状态</div>
            {summaryQ.error ? <div className="mt-3 text-sm text-destructive">{formatMembershipApiError(summaryQ.error)}</div> : null}
            {!summaryQ.error ? (
              <div className="mt-3 space-y-2">
                <div className="text-2xl font-semibold tracking-tight text-foreground">
                  {summary?.isActive ? "会员有效" : summary?.currentStatus === "expired" ? "会员已过期" : "尚未开通"}
                </div>
                {summary?.currentEndsAt ? <div className="text-sm leading-6 text-muted-foreground">{formatMembershipDateTime(summary.currentEndsAt)}</div> : null}
                <div className="theme-subtle-surface px-3 py-3 text-sm">
                  <div>首单价：{formatMembershipPrice(summary?.firstOrderPriceCent ?? 0)}</div>
                  <div className="mt-1">续费价：{formatMembershipPrice(summary?.renewalPriceCent ?? 0)}</div>
                  <div className="mt-1">
                    微信收款：{payoutIdentity?.status === "ready" ? payoutIdentity.maskedLabel : "未绑定"}
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          <div className="theme-soft-surface p-4">
            <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">邀请码</div>
            {inviteSummaryQ.error ? <div className="mt-3 text-sm text-destructive">{formatMembershipApiError(inviteSummaryQ.error)}</div> : null}
            {!inviteSummaryQ.error ? (
              <div className="mt-3 space-y-3">
                <div>
                  <div className="text-2xl font-semibold tracking-tight text-foreground">{inviteSummary?.inviteCode ?? "加载中..."}</div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    已邀请 {inviteSummary?.totalInvitedUsers ?? 0} 人，待结算 {formatMembershipPrice(commissionAccount?.pendingCent ?? 0)}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" onClick={() => void onCopyInviteCode()}>
                    <Copy className="h-4 w-4" />
                    复制邀请码
                  </Button>
                  <Button asChild variant="ghost">
                    <Link to="/membership">查看邀请记录</Link>
                  </Button>
                </div>
                {inviteSummary?.boundInviteCode ? <div className="theme-subtle-surface px-3 py-3 text-sm">{inviteSummary.boundInviteCode}</div> : null}
              </div>
            ) : null}
          </div>
        </div>

        <div className="theme-soft-surface p-4">
          <div className="flex items-center gap-2">
            <Ticket className="h-4 w-4 text-primary" />
            <div className="text-sm font-semibold text-foreground">可用优惠券</div>
          </div>
          <div className="mt-1 text-sm leading-6 text-muted-foreground">这里先展示最多 3 张可用券，更多记录可在会员中心查看。</div>

          {couponsQ.error ? <div className="mt-4 text-sm text-destructive">{formatMembershipApiError(couponsQ.error)}</div> : null}

          {!couponsQ.error && availableCoupons.length === 0 ? (
            <div className="theme-subtle-surface mt-4 border-dashed px-4 py-8 text-center text-sm">
              暂时还没有可用优惠券。绑定好友邀请码后，你会收到 7.5 折会员券。
            </div>
          ) : null}

          {availableCoupons.length > 0 ? (
            <div className="mt-4 space-y-3">
              {availableCoupons.map((coupon) => (
                <div key={coupon.couponId} className="theme-subtle-surface p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <Gift className="h-4 w-4 text-primary" />
                        <div className="text-sm font-semibold text-foreground">{coupon.title || describeMembershipCouponSource(coupon.source)}</div>
                      </div>
                      <div className="mt-2 text-sm leading-6 text-muted-foreground">
                        满 {formatMembershipPrice(coupon.minSpendCent)} 可用，到账后可用于首单或续费。
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      <div className="text-xl font-semibold tracking-tight text-foreground">{formatMembershipCouponValue(coupon)}</div>
                      <div className="mt-1 text-xs text-muted-foreground">{formatMembershipDateTime(coupon.expiresAt)} 到期</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  )
}

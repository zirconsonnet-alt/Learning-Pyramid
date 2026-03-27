import { ArrowRight, Copy, Gift, Ticket } from "lucide-react"
import { Link } from "react-router-dom"

import { Button } from "@/ui/components/ui/button"
import { useInviteSummary, useMembershipCoupons, useMembershipSummary } from "@/ui/queries/membership"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import {
  copyTextToClipboard,
  describeMembershipCouponSource,
  formatMembershipApiError,
  formatMembershipDateTime,
  formatMembershipPrice,
  StatusPill,
} from "@/views/membership/membershipUi"

export function MembershipProfilePanel() {
  const summaryQ = useMembershipSummary()
  const inviteSummaryQ = useInviteSummary()
  const couponsQ = useMembershipCoupons(6)

  const summary = summaryQ.data
  const inviteSummary = inviteSummaryQ.data
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
    <section className="rounded-[1.8rem] border border-[#d4e0ec] bg-[radial-gradient(circle_at_top_left,rgba(255,220,168,0.18),transparent_36%),linear-gradient(135deg,rgba(255,255,255,0.96),rgba(248,251,255,0.92))] p-5 shadow-[0_22px_44px_-34px_rgba(20,58,101,0.28)]">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <StatusPill tone="warm">会员与邀请</StatusPill>
            {summary?.isActive ? <StatusPill tone="accent">会员有效</StatusPill> : <StatusPill>未开通</StatusPill>}
          </div>
          <div className="text-2xl font-semibold tracking-tight text-[#17324d]">把会员状态、邀请码和可用券集中看完</div>
          <div className="max-w-2xl text-sm leading-7 text-[#60728a]">
            第三轮开始把会员体验收进个人中心。你可以先看状态，再去会员中心完成下单、选券和订单跟踪。
          </div>
        </div>
        <Button asChild className="shrink-0">
          <Link to="/membership">
            去会员中心
            <ArrowRight className="h-4 w-4" />
          </Link>
        </Button>
      </div>

      <div className="mt-5 grid gap-4 xl:grid-cols-[minmax(0,1.05fr)_minmax(18rem,0.95fr)]">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-[1.4rem] border border-[#d9e6f2] bg-white/88 p-4">
            <div className="text-[11px] uppercase tracking-[0.14em] text-[#7a8ca3]">会员状态</div>
            {summaryQ.error ? <div className="mt-3 text-sm text-destructive">{formatMembershipApiError(summaryQ.error)}</div> : null}
            {!summaryQ.error ? (
              <div className="mt-3 space-y-2">
                <div className="text-2xl font-semibold tracking-tight text-[#17324d]">
                  {summary?.isActive ? "会员有效" : summary?.currentStatus === "expired" ? "会员已过期" : "尚未开通"}
                </div>
                <div className="text-sm leading-6 text-[#62758d]">
                  {summary?.currentEndsAt ? `有效期至 ${formatMembershipDateTime(summary.currentEndsAt)}` : "当前还没有生效中的会员权益。"}
                </div>
                <div className="rounded-[1rem] border border-[#dbe6f1] bg-[#f8fbff] px-3 py-3 text-sm text-[#5f7188]">
                  <div>首单价：{formatMembershipPrice(summary?.firstOrderPriceCent ?? 0)}</div>
                  <div className="mt-1">续费价：{formatMembershipPrice(summary?.renewalPriceCent ?? 0)}</div>
                </div>
              </div>
            ) : null}
          </div>

          <div className="rounded-[1.4rem] border border-[#d9e6f2] bg-white/88 p-4">
            <div className="text-[11px] uppercase tracking-[0.14em] text-[#7a8ca3]">邀请码</div>
            {inviteSummaryQ.error ? <div className="mt-3 text-sm text-destructive">{formatMembershipApiError(inviteSummaryQ.error)}</div> : null}
            {!inviteSummaryQ.error ? (
              <div className="mt-3 space-y-3">
                <div>
                  <div className="text-2xl font-semibold tracking-tight text-[#17324d]">{inviteSummary?.inviteCode ?? "加载中..."}</div>
                  <div className="mt-1 text-sm text-[#62758d]">
                    已邀请 {inviteSummary?.totalInvitedUsers ?? 0} 人，已触发奖励 {inviteSummary?.rewardedInviteCount ?? 0} 次
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
                {inviteSummary?.boundInviteCode ? (
                  <div className="rounded-[1rem] border border-[#dbe6f1] bg-[#f8fbff] px-3 py-3 text-sm text-[#5f7188]">
                    已绑定上级邀请码：{inviteSummary.boundInviteCode}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>

        <div className="rounded-[1.4rem] border border-[#d9e6f2] bg-white/88 p-4">
          <div className="flex items-center gap-2">
            <Ticket className="h-4 w-4 text-primary" />
            <div className="text-sm font-semibold text-foreground">可用优惠券</div>
          </div>
          <div className="mt-1 text-sm leading-6 text-muted-foreground">这里先展示最多 3 张可用券，详细历史和下单选券都在会员中心里查看。</div>

          {couponsQ.error ? <div className="mt-4 text-sm text-destructive">{formatMembershipApiError(couponsQ.error)}</div> : null}

          {!couponsQ.error && availableCoupons.length === 0 ? (
            <div className="mt-4 rounded-[1.2rem] border border-dashed border-[#d7e0ea] bg-[#fbfdff] px-4 py-8 text-center text-sm text-[#697b92]">
              暂时还没有可用优惠券。邀请好友首单成功后，这里会自动出现 5 元券。
            </div>
          ) : null}

          {availableCoupons.length > 0 ? (
            <div className="mt-4 space-y-3">
              {availableCoupons.map((coupon) => (
                <div key={coupon.couponId} className="rounded-[1.2rem] border border-[#dfe7ef] bg-[#fbfdff] p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <Gift className="h-4 w-4 text-primary" />
                        <div className="text-sm font-semibold text-foreground">{coupon.title || describeMembershipCouponSource(coupon.source)}</div>
                      </div>
                      <div className="mt-2 text-sm leading-6 text-[#60728a]">
                        满 {formatMembershipPrice(coupon.minSpendCent)} 可用，到账后可用于首单或续费。
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      <div className="text-xl font-semibold tracking-tight text-[#17324d]">-{formatMembershipPrice(coupon.amountCent)}</div>
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

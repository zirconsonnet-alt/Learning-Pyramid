import { CreditCard, Ticket } from "lucide-react"

import type { CouponRecord, MembershipOrder, MembershipOrderPreview, MembershipSummary } from "@/ui/api/membership"
import { Button } from "@/ui/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/ui/components/ui/dialog"
import {
  describeMembershipPaymentProvider,
  describeMembershipCouponSource,
  describeMembershipCouponStatus,
  formatMembershipApiError,
  formatMembershipDateTime,
  formatMembershipPrice,
  StatusPill,
} from "@/views/membership/membershipUi"
import { cn } from "@/ui/utils"

function CouponOptionCard(props: {
  coupon: CouponRecord
  selected: boolean
  onSelect: () => void
}) {
  const { coupon, onSelect, selected } = props
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full rounded-[1.25rem] border p-4 text-left transition",
        selected
          ? "border-primary bg-[#edf4ff] shadow-[0_18px_36px_-30px_rgba(28,63,108,0.45)]"
          : "border-[#dfe7ef] bg-white hover:border-[#bfd4eb]",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-foreground">{coupon.title || describeMembershipCouponSource(coupon.source)}</div>
          <div className="mt-1 text-xs text-muted-foreground">满 {formatMembershipPrice(coupon.minSpendCent)} 可用</div>
        </div>
        <StatusPill tone={coupon.status === "available" ? "accent" : "default"}>{describeMembershipCouponStatus(coupon.status)}</StatusPill>
      </div>
      <div className="mt-3 flex items-end justify-between gap-4">
        <div className="text-2xl font-semibold tracking-tight text-[#17324d]">-{formatMembershipPrice(coupon.amountCent)}</div>
        <div className="text-right text-xs text-muted-foreground">
          <div>到期时间</div>
          <div>{formatMembershipDateTime(coupon.expiresAt)}</div>
        </div>
      </div>
    </button>
  )
}

export function MembershipPurchaseDialog(props: {
  open: boolean
  onOpenChange: (open: boolean) => void
  summary: MembershipSummary | undefined
  preview: MembershipOrderPreview | undefined
  previewError: unknown
  previewLoading: boolean
  selectedCouponId: string
  selectedProvider: string
  supportedProviders: string[]
  availableCoupons: CouponRecord[]
  pendingOrder?: MembershipOrder
  createPending: boolean
  confirmPending: boolean
  onSelectCoupon: (couponId: string) => void
  onSelectProvider: (provider: string) => void
  onConfirm: () => void
}) {
  const {
    open,
    onOpenChange,
    summary,
    preview,
    previewError,
    previewLoading,
    selectedCouponId,
    selectedProvider,
    supportedProviders,
    availableCoupons,
    pendingOrder,
    createPending,
    confirmPending,
    onSelectCoupon,
    onSelectProvider,
    onConfirm,
  } = props

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl rounded-[2rem] border-[#d6e2ee] bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(244,249,255,0.96))] p-0">
        <div className="grid gap-0 lg:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
          <div className="border-b border-[#dbe6f1] p-6 lg:border-b-0 lg:border-r">
            <DialogHeader className="space-y-3 text-left">
              <div className="flex items-center gap-2">
                <StatusPill tone="accent">{summary?.isActive ? "立即续费" : "立即开通"}</StatusPill>
                <StatusPill tone="warm">确认购买</StatusPill>
              </div>
              <DialogTitle className="text-2xl tracking-tight text-[#17324d]">开通月会员</DialogTitle>
              <DialogDescription className="max-w-xl leading-7 text-[#60728a]">
                这一轮开始把真实支付能力接到会员系统里。你可以先选支付方式，再确认生成待支付订单和对应的支付载荷。
              </DialogDescription>
            </DialogHeader>

            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <div className="rounded-[1.45rem] border border-[#d9e6f2] bg-white/86 p-4">
                <div className="text-[11px] uppercase tracking-[0.14em] text-[#7a8ca3]">价格拆分</div>
                {previewLoading && !preview ? <div className="mt-3 text-sm text-[#62758d]">正在计算当前价格…</div> : null}
                {previewError ? <div className="mt-3 text-sm text-destructive">{formatMembershipApiError(previewError)}</div> : null}
                {preview ? (
                  <div className="mt-3 space-y-2 text-sm leading-6 text-[#62758d]">
                    <div className="flex items-center justify-between gap-4">
                      <span>月会员原价</span>
                      <span>{formatMembershipPrice(preview.listAmountCent)}</span>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <span>{preview.orderType === "first_purchase" ? "首单优惠" : "续费价格"}</span>
                      <span>-{formatMembershipPrice(preview.firstOrderDiscountCent)}</span>
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <span>优惠券抵扣</span>
                      <span>-{formatMembershipPrice(preview.couponDiscountCent)}</span>
                    </div>
                    <div className="mt-3 flex items-center justify-between gap-4 border-t border-[#dbe6f1] pt-3 text-base font-semibold text-[#17324d]">
                      <span>本次实付</span>
                      <span>{formatMembershipPrice(preview.payableAmountCent)}</span>
                    </div>
                  </div>
                ) : null}
              </div>

              <div className="rounded-[1.45rem] border border-[#d9e6f2] bg-[#f8fbff] p-4">
                <div className="text-[11px] uppercase tracking-[0.14em] text-[#7a8ca3]">订单说明</div>
                <div className="mt-3 space-y-2 text-sm leading-6 text-[#62758d]">
                  <div>会员时长：30 天</div>
                  <div>支付方式：{describeMembershipPaymentProvider(selectedProvider)}</div>
                  <div>当前价格：{formatMembershipPrice(summary?.currentPriceCent ?? 0)}</div>
                  {pendingOrder ? <div>当前已有一笔待支付订单，将按新的选券配置更新。</div> : <div>确认后会创建一笔新的待支付订单。</div>}
                </div>
                {pendingOrder ? (
                  <div className="mt-4 rounded-[1.2rem] border border-[#d8e4f0] bg-white/88 p-3 text-sm text-[#5f7188]">
                    <div className="font-medium text-[#17324d]">当前待支付订单</div>
                    <div className="mt-1">订单号：{pendingOrder.orderId}</div>
                    <div className="mt-1">失效时间：{formatMembershipDateTime(pendingOrder.expiredAt)}</div>
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          <div className="p-6">
            <div className="flex items-center gap-2">
              <Ticket className="h-4 w-4 text-primary" />
              <div className="text-sm font-semibold text-foreground">选择支付方式与优惠券</div>
            </div>
            <div className="mt-1 text-sm leading-6 text-muted-foreground">切换支付方式或优惠券后会继续使用同一套价格预览。每笔订单最多使用一张券。</div>

            <div className="mt-5 space-y-3">
              {supportedProviders.map((provider) => (
                <button
                  key={provider}
                  type="button"
                  onClick={() => onSelectProvider(provider)}
                  className={cn(
                    "w-full rounded-[1.25rem] border p-4 text-left transition",
                    selectedProvider === provider
                      ? "border-primary bg-[#edf4ff] shadow-[0_18px_36px_-30px_rgba(28,63,108,0.45)]"
                      : "border-[#dfe7ef] bg-white hover:border-[#bfd4eb]",
                  )}
                >
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <div className="text-sm font-semibold text-foreground">{describeMembershipPaymentProvider(provider)}</div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {provider === "wechat_native" ? "生成微信二维码并支持同步支付状态。" : "保留测试支付入口，方便继续验证会员全链路。"}
                      </div>
                    </div>
                    {selectedProvider === provider ? <StatusPill tone="accent">当前方案</StatusPill> : null}
                  </div>
                </button>
              ))}
            </div>

            <div className="mt-5 space-y-3 border-t border-[#dbe6f1] pt-5">
              <button
                type="button"
                onClick={() => onSelectCoupon("")}
                className={cn(
                  "w-full rounded-[1.25rem] border p-4 text-left transition",
                  selectedCouponId
                    ? "border-[#dfe7ef] bg-white hover:border-[#bfd4eb]"
                    : "border-primary bg-[#edf4ff] shadow-[0_18px_36px_-30px_rgba(28,63,108,0.45)]",
                )}
              >
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="text-sm font-semibold text-foreground">不使用优惠券</div>
                    <div className="mt-1 text-xs text-muted-foreground">按当前会员价格直接结算。</div>
                  </div>
                  {!selectedCouponId ? <StatusPill tone="accent">当前方案</StatusPill> : null}
                </div>
              </button>

              {availableCoupons.map((coupon) => (
                <CouponOptionCard
                  key={coupon.couponId}
                  coupon={coupon}
                  selected={selectedCouponId === coupon.couponId}
                  onSelect={() => onSelectCoupon(coupon.couponId)}
                />
              ))}

              {availableCoupons.length === 0 ? (
                <div className="rounded-[1.3rem] border border-dashed border-[#d7e0ea] bg-[#fbfdff] px-4 py-8 text-center text-sm leading-6 text-[#697b92]">
                  当前没有可用优惠券。邀请好友首单成功后，这里会自动出现 5 元券。
                </div>
              ) : null}
            </div>

            <DialogFooter className="mt-6">
              <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={createPending || confirmPending}>
                取消
              </Button>
              <Button onClick={onConfirm} disabled={createPending || confirmPending || previewLoading || Boolean(previewError)} className="min-w-[10rem]">
                <CreditCard className="h-4 w-4" />
                {createPending ? "创建中..." : pendingOrder ? "更新待支付订单" : "确认创建订单"}
              </Button>
            </DialogFooter>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

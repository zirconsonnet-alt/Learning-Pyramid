import { CreditCard, Ticket } from "lucide-react"

import type { CouponRecord, MembershipCreateOrderResult, MembershipOrder, MembershipOrderPreview, MembershipSummary } from "@/ui/api/membership"
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
  formatMembershipCouponValue,
  formatMembershipDateTime,
  formatMembershipPrice,
  StatusPill,
} from "@/views/membership/membershipUi"
import { cn } from "@/ui/utils"
import { MembershipPlanPriceBlock } from "@/views/membership/components/MembershipPlanPriceBlock"

const MEMBERSHIP_PLAN_OPTIONS = [
  {
    planId: "monthly",
    title: "月会员",
    price: "¥20",
    unit: "/ 月",
    note: "按 20 元月会员结算",
    accent: false,
  },
  {
    planId: "graduate_exam",
    title: "考研套餐",
    price: "¥15",
    unit: "/ 月",
    note: "单最低15元 有效期至12月21日",
    accent: true,
  },
] as const

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
          ? "border-primary/20 bg-[hsl(var(--primary)/0.08)] shadow-[0_18px_36px_-30px_hsl(var(--primary)/0.35)]"
          : "theme-soft-surface hover:border-primary/20",
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
        <div className="text-2xl font-semibold tracking-tight text-foreground">{formatMembershipCouponValue(coupon)}</div>
        <div className="text-right text-xs text-muted-foreground">
          <div>到期时间</div>
          <div>{formatMembershipDateTime(coupon.expiresAt)}</div>
        </div>
      </div>
    </button>
  )
}

export function MembershipPaymentDialog(props: {
  open: boolean
  onOpenChange: (open: boolean) => void
  order?: MembershipOrder
  activeCheckout?: MembershipCreateOrderResult | null
  createPending: boolean
  confirmPending: boolean
  syncPending: boolean
  closePending: boolean
  onResumePayment: () => void
  onConfirmPayment: (order: MembershipOrder) => void
  onSyncPayment: (order: MembershipOrder) => void
  onCloseOrder: (order: MembershipOrder) => void
  onCopyPaymentLink: () => void
}) {
  const {
    open,
    onOpenChange,
    order,
    activeCheckout,
    createPending,
    confirmPending,
    syncPending,
    closePending,
    onResumePayment,
    onConfirmPayment,
    onSyncPayment,
    onCloseOrder,
    onCopyPaymentLink,
  } = props

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl rounded-[2rem] border-[color:var(--theme-soft-border)] [background:var(--theme-card-main-bg)] p-0">
        <div className="px-6 py-6 sm:px-8">
          <DialogHeader className="space-y-3 text-left">
            <div className="flex flex-wrap items-center gap-2">
              <StatusPill tone="warm">待支付订单</StatusPill>
              {order ? <StatusPill>{order.planName}</StatusPill> : null}
              {order ? <StatusPill>{describeMembershipPaymentProvider(order.provider)}</StatusPill> : null}
            </div>
            <DialogTitle className="text-2xl tracking-tight text-foreground">继续支付</DialogTitle>
            <DialogDescription className="sr-only">查看待支付订单并继续完成支付。</DialogDescription>
          </DialogHeader>

          {!order ? (
            <div className="theme-subtle-surface mt-6 px-4 py-8 text-center text-sm text-muted-foreground">正在读取待支付订单…</div>
          ) : (
            <div className="mt-6 space-y-4">
              <div className="theme-soft-surface p-4 text-sm leading-6 text-muted-foreground">
                <div className="flex items-center justify-between gap-4">
                  <span>实付金额</span>
                  <span className="text-base font-semibold text-foreground">{formatMembershipPrice(order.payableAmountCent)}</span>
                </div>
                <div className="mt-2 flex items-center justify-between gap-4">
                  <span>订单号</span>
                  <span className="break-all text-right">{order.orderId}</span>
                </div>
                <div className="mt-2 flex items-center justify-between gap-4">
                  <span>失效时间</span>
                  <span>{formatMembershipDateTime(order.expiredAt)}</span>
                </div>
              </div>

              {order.provider === "manual_test" ? (
                <div className="grid gap-2 sm:grid-cols-2">
                  <Button onClick={() => onConfirmPayment(order)} disabled={confirmPending || closePending}>
                    {confirmPending ? "处理中..." : "确认开通"}
                  </Button>
                  <Button variant="outline" onClick={() => onCloseOrder(order)} disabled={closePending || confirmPending}>
                    {closePending ? "关闭中..." : "关闭订单"}
                  </Button>
                </div>
              ) : null}

              {order.provider === "wechat_native" ? (
                <div className="theme-subtle-surface px-4 py-4 text-sm leading-6">
                  {activeCheckout?.paymentPayload.qrImageDataUrl ? (
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
                      <img
                        src={activeCheckout.paymentPayload.qrImageDataUrl}
                        alt="微信支付二维码"
                        className="h-36 w-36 rounded-2xl border border-[color:var(--theme-soft-border)] bg-white p-2"
                      />
                      <div className="min-w-0 flex-1 space-y-2">
                        <div className="font-medium text-foreground">{activeCheckout.paymentPayload.instruction}</div>
                        <div className="flex flex-wrap gap-2 pt-1">
                          <Button variant="outline" onClick={onCopyPaymentLink}>
                            <CreditCard className="h-4 w-4" />
                            复制链接
                          </Button>
                          <Button variant="outline" onClick={() => onSyncPayment(order)} disabled={syncPending || closePending}>
                            {syncPending ? "同步中..." : "同步状态"}
                          </Button>
                          <Button variant="outline" onClick={() => onCloseOrder(order)} disabled={closePending || syncPending}>
                            {closePending ? "关闭中..." : "关闭订单"}
                          </Button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <div>当前还没有支付二维码。点击继续支付生成最新支付信息。</div>
                      <div className="flex flex-wrap gap-2">
                        <Button onClick={onResumePayment} disabled={createPending || syncPending || closePending}>
                          {createPending ? "生成中..." : "继续支付"}
                        </Button>
                        <Button variant="outline" onClick={() => onSyncPayment(order)} disabled={syncPending || closePending || createPending}>
                          {syncPending ? "同步中..." : "同步状态"}
                        </Button>
                        <Button variant="outline" onClick={() => onCloseOrder(order)} disabled={closePending || syncPending || createPending}>
                          {closePending ? "关闭中..." : "关闭订单"}
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              ) : null}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
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
  selectedPlanId: string
  selectedProvider: string
  supportedProviders: string[]
  availableCoupons: CouponRecord[]
  createPending: boolean
  onSelectCoupon: (couponId: string) => void
  onSelectPlan: (planId: string) => void
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
    selectedPlanId,
    selectedProvider,
    supportedProviders,
    availableCoupons,
    createPending,
    onSelectCoupon,
    onSelectPlan,
    onSelectProvider,
    onConfirm,
  } = props

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl rounded-[2rem] border-[color:var(--theme-soft-border)] [background:radial-gradient(circle_at_top_left,hsl(var(--primary)/0.1),transparent_36%),var(--theme-card-main-bg)] p-0">
        <div className="grid gap-0 lg:grid-cols-[minmax(0,1.1fr)_minmax(320px,0.9fr)]">
          <div className="border-b border-[color:var(--theme-soft-border)] p-6 lg:border-b-0 lg:border-r">
            <DialogHeader className="space-y-3 text-left">
              <div className="flex items-center gap-2">
                <StatusPill tone="accent">{summary?.isActive ? "立即续费" : "立即开通"}</StatusPill>
                <StatusPill tone="warm">确认购买</StatusPill>
              </div>
              <DialogTitle className="text-2xl tracking-tight text-foreground">开通会员套餐</DialogTitle>
              <DialogDescription className="sr-only">选择会员套餐、支付方式和优惠券。</DialogDescription>
            </DialogHeader>

            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              {MEMBERSHIP_PLAN_OPTIONS.map((plan) => (
                <button
                  key={plan.planId}
                  type="button"
                  onClick={() => onSelectPlan(plan.planId)}
                  className={cn(
                    "group w-full min-w-0 text-left transition",
                    selectedPlanId === plan.planId
                      ? "opacity-100"
                      : "opacity-90 hover:opacity-100",
                  )}
                >
                  <MembershipPlanPriceBlock
                    title={plan.title}
                    price={plan.price}
                    unit={plan.unit}
                    note={plan.note}
                    accent={plan.accent}
                    className="relative"
                  >
                    {selectedPlanId === plan.planId ? (
                      <div className="absolute right-4 top-4">
                        <StatusPill tone="accent">当前套餐</StatusPill>
                      </div>
                    ) : null}
                  </MembershipPlanPriceBlock>
                </button>
              ))}
            </div>

            <div className="mt-6 grid gap-4 sm:grid-cols-2">
              <div className="theme-soft-surface p-4">
                <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">价格拆分</div>
                {previewLoading && !preview ? <div className="mt-3 text-sm text-muted-foreground">正在计算当前价格…</div> : null}
                {previewError ? <div className="mt-3 text-sm text-destructive">{formatMembershipApiError(previewError)}</div> : null}
                {preview ? (
                  <div className="mt-3 space-y-2 text-sm leading-6 text-muted-foreground">
                    <div className="flex items-center justify-between gap-4">
                      <span>{preview.planName}原价</span>
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
                    <div className="mt-3 flex items-center justify-between gap-4 border-t border-[color:var(--theme-soft-border)] pt-3 text-base font-semibold text-foreground">
                      <span>本次实付</span>
                      <span>{formatMembershipPrice(preview.payableAmountCent)}</span>
                    </div>
                  </div>
                ) : null}
              </div>

              <div className="theme-subtle-surface p-4">
                <div className="text-[11px] uppercase tracking-[0.14em] text-muted-foreground">订单说明</div>
                <div className="mt-3 space-y-2 text-sm leading-6">
                  <div>会员时长：{preview?.periodDays ?? 30} 天</div>
                  <div>套餐类型：{preview?.planName ?? "月会员"}</div>
                  <div>支付方式：{selectedProvider ? describeMembershipPaymentProvider(selectedProvider) : "暂未开放"}</div>
                  <div>确认后会创建一笔新的待支付订单。</div>
                </div>
              </div>
            </div>
          </div>

          <div className="p-6">
            <div className="flex items-center gap-2">
              <Ticket className="h-4 w-4 text-primary" />
              <div className="text-sm font-semibold text-foreground">选择支付方式与优惠券</div>
            </div>

            <div className="mt-5 space-y-3">
              {supportedProviders.length === 0 ? (
                <div className="theme-subtle-surface border-dashed px-4 py-8 text-center text-sm leading-6">
                  当前没有可用支付方式，请稍后再试。
                </div>
              ) : null}
              {supportedProviders.map((provider) => (
                <button
                  key={provider}
                  type="button"
                  onClick={() => onSelectProvider(provider)}
                  className={cn(
                    "w-full rounded-[1.25rem] border p-4 text-left transition",
                    selectedProvider === provider
                      ? "border-primary/20 bg-[hsl(var(--primary)/0.08)] shadow-[0_18px_36px_-30px_hsl(var(--primary)/0.35)]"
                      : "theme-soft-surface hover:border-primary/20",
                  )}
                >
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <div className="text-sm font-semibold text-foreground">{describeMembershipPaymentProvider(provider)}</div>
                      <div className="mt-1 text-xs text-muted-foreground">
                        {provider === "wechat_native" ? "扫码后即可继续支付。" : "确认后可直接完成开通。"}
                      </div>
                    </div>
                    {selectedProvider === provider ? <StatusPill tone="accent">当前方案</StatusPill> : null}
                  </div>
                </button>
              ))}
            </div>

            <div className="mt-5 space-y-3 border-t border-[color:var(--theme-soft-border)] pt-5">
              <button
                type="button"
                onClick={() => onSelectCoupon("")}
                className={cn(
                  "w-full rounded-[1.25rem] border p-4 text-left transition",
                  selectedCouponId
                    ? "theme-soft-surface hover:border-primary/20"
                    : "border-primary/20 bg-[hsl(var(--primary)/0.08)] shadow-[0_18px_36px_-30px_hsl(var(--primary)/0.35)]",
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
                <div className="theme-subtle-surface border-dashed px-4 py-8 text-center text-sm leading-6">
                  当前没有可用优惠券。绑定好友邀请码后，你会收到 7.5 折会员券。
                </div>
              ) : null}
            </div>

            <DialogFooter className="mt-6">
              <Button variant="ghost" onClick={() => onOpenChange(false)} disabled={createPending}>
                取消
              </Button>
              <Button
                onClick={onConfirm}
                disabled={
                  createPending ||
                  previewLoading ||
                  Boolean(previewError) ||
                  supportedProviders.length === 0 ||
                  !selectedProvider
                }
                className="min-w-[10rem]"
              >
                <CreditCard className="h-4 w-4" />
                {createPending ? "创建中..." : "确认并继续"}
              </Button>
            </DialogFooter>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

import { type ReactNode } from "react"
import { Crown } from "lucide-react"
import { Link } from "react-router-dom"

import { ApiError, MEMBERSHIP_CENTER_PATH } from "@/ui/api/http"
import { Button } from "@/ui/components/ui/button"
import { cn } from "@/ui/utils"

export function formatMembershipApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

export function formatMembershipPrice(amountCent: number) {
  return `¥${(amountCent / 100).toFixed(1)}`
}

export function formatMembershipCouponValue(coupon: { couponType?: string; discountRate?: number | null; amountCent: number }) {
  if (coupon.couponType === "percent" && coupon.discountRate) {
    return `${(coupon.discountRate / 10).toFixed(1).replace(/\.0$/, "")} 折`
  }
  return `-${formatMembershipPrice(coupon.amountCent)}`
}

export function formatMembershipDateTime(value: string | null | undefined) {
  if (!value) return "未开始"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  })
}

export function describeMembershipOrderType(value: string) {
  return value === "first_purchase" ? "首单" : "续费"
}

export function describeMembershipOrderStatus(value: string) {
  if (value === "pending") return "待支付"
  if (value === "paid") return "已支付"
  if (value === "expired") return "已过期"
  if (value === "closed") return "已关闭"
  if (value === "refunded") return "已退款"
  if (value === "refund_pending") return "退款中"
  return value
}

export function describeMembershipCouponStatus(value: string) {
  if (value === "available") return "可用"
  if (value === "used") return "已使用"
  if (value === "expired") return "已过期"
  if (value === "revoked") return "已撤销"
  return value
}

export function describeMembershipCouponSource(value: string) {
  if (value === "invite_discount") return "邀请码折扣"
  if (value === "invite_reward") return "邀请奖励"
  if (value === "admin_grant") return "后台发放"
  return value
}

export function describeMembershipPaymentProvider(value: string) {
  if (value === "manual_test") return "快捷确认"
  if (value === "wechat_native") return "微信扫码支付"
  return value
}

export function describeInviteRecordStatus(value: string) {
  if (value === "rewarded") return "首单已转化"
  if (value === "bound") return "已绑定待转化"
  if (value === "discount_issued") return "折扣券已发放"
  if (value === "commission_pending") return "佣金待结算"
  if (value === "commission_settled") return "佣金已结算"
  return value
}

export function describeCommissionStatus(value: string) {
  if (value === "pending") return "待结算"
  if (value === "settled") return "可提现"
  if (value === "canceled") return "已取消"
  if (value === "reversed") return "已冲正"
  return value
}

export function describeWithdrawalStatus(value: string) {
  if (value === "pending") return "待提交"
  if (value === "processing") return "处理中"
  if (value === "succeeded") return "已到账"
  if (value === "failed") return "失败退回"
  if (value === "canceled") return "已取消"
  return value
}

export async function copyTextToClipboard(value: string) {
  const text = value.trim()
  if (!text) return
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  if (typeof document === "undefined") {
    throw new Error("当前环境不支持复制")
  }
  const textarea = document.createElement("textarea")
  textarea.value = text
  textarea.setAttribute("readonly", "true")
  textarea.style.position = "absolute"
  textarea.style.left = "-9999px"
  document.body.appendChild(textarea)
  textarea.select()
  const copied = document.execCommand("copy")
  document.body.removeChild(textarea)
  if (!copied) {
    throw new Error("复制失败，请手动复制")
  }
}

export function StatusPill(props: { children: ReactNode; tone?: "default" | "accent" | "warm" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-xs",
        props.tone === "accent"
          ? "theme-pill-accent"
          : props.tone === "warm"
            ? "theme-pill-warm"
            : "theme-pill-default",
      )}
    >
      {props.children}
    </span>
  )
}

export function MemberOnlyFeatureNotice({
  title = "会员专属功能",
  message = "开通会员后即可使用 AI 能力和番茄钟；当前账号还没有有效会员，所以这里先为你锁定。",
  className,
  compact = false,
}: {
  title?: string
  message?: string
  className?: string
  compact?: boolean
}) {
  return (
    <section
      className={cn(
        "theme-card-main flex items-start gap-3 rounded-[1rem] border border-[color:var(--theme-soft-border)] px-4 py-4 shadow-[var(--theme-soft-shadow)]",
        compact ? "py-3" : "sm:px-5 sm:py-5",
        className,
      )}
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-amber-200/70 bg-amber-50 text-amber-700">
        <Crown className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1 space-y-2">
        <div>
          <h2 className="text-sm font-semibold text-foreground">{title}</h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">{message}</p>
        </div>
        <Button asChild size={compact ? "sm" : "default"}>
          <Link to={MEMBERSHIP_CENTER_PATH}>前往会员中心</Link>
        </Button>
      </div>
    </section>
  )
}

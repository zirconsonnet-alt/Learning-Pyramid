import { type ReactNode } from "react"

import { ApiError } from "@/ui/api/http"
import { cn } from "@/ui/utils"

export function formatMembershipApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

export function formatMembershipPrice(amountCent: number) {
  return `¥${(amountCent / 100).toFixed(1)}`
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
  if (value === "invite_reward") return "邀请奖励"
  if (value === "admin_grant") return "后台发放"
  return value
}

export function describeMembershipPaymentProvider(value: string) {
  if (value === "manual_test") return "测试支付"
  if (value === "wechat_native") return "微信扫码支付"
  return value
}

export function describeInviteRecordStatus(value: string) {
  if (value === "rewarded") return "首单已转化"
  if (value === "bound") return "已绑定待转化"
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
          ? "border-primary/20 bg-[#eef5ff] text-[#1d4f8f]"
          : props.tone === "warm"
            ? "border-[#f2d4a7] bg-[#fff4df] text-[#8b5a15]"
            : "border-[#dde5ee] bg-[#f8fafc] text-[#5b6b82]",
      )}
    >
      {props.children}
    </span>
  )
}

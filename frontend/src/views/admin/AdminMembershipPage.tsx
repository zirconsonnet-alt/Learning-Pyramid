import { type ReactNode, useEffect, useState } from "react"
import { Link } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { ContentEmptyState, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import {
  useCloseAdminMembershipOrder,
  useAdminMembershipCoupons,
  useAdminMembershipInvites,
  useAdminMembershipOrderDetail,
  useAdminMembershipOrders,
  useAdminMembershipOverview,
  useGrantAdminMembershipCoupon,
  useRefundAdminMembershipOrder,
  useSyncAdminMembershipOrderPayment,
  useVoidAdminMembershipCoupon,
} from "@/ui/queries/admin"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { cn } from "@/ui/utils"
import { AdminNav } from "@/views/admin/AdminNav"
import {
  copyTextToClipboard,
  describeInviteRecordStatus,
  describeMembershipCouponSource,
  describeMembershipCouponStatus,
  describeMembershipOrderStatus,
  describeMembershipOrderType,
  describeMembershipPaymentProvider,
  formatMembershipDateTime,
  formatMembershipPrice,
} from "@/views/membership/membershipUi"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function StatusPill(props: { children: ReactNode; tone?: "default" | "accent" | "warm" | "danger" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-xs",
        props.tone === "accent"
          ? "theme-pill-accent"
          : props.tone === "warm"
            ? "theme-pill-warm"
            : props.tone === "danger"
              ? "theme-pill-danger"
              : "theme-pill-default",
      )}
    >
      {props.children}
    </span>
  )
}

function userLabel(user: {
  userId: string
  publicUid: string | null
  nickname: string | null
  email: string | null
  status: string
}) {
  return {
    title: user.nickname?.trim() || user.publicUid?.trim() || user.userId,
    subtitle: user.publicUid?.trim() || user.email?.trim() || user.userId,
  }
}

function orderStatusTone(status: string): "default" | "accent" | "warm" | "danger" {
  if (status === "paid") return "accent"
  if (status === "pending") return "warm"
  if (status === "refunded" || status === "closed") return "danger"
  return "default"
}

function couponStatusTone(status: string): "default" | "accent" | "warm" | "danger" {
  if (status === "available") return "accent"
  if (status === "used") return "warm"
  if (status === "revoked") return "danger"
  return "default"
}

function inviteStatusTone(status: string): "default" | "accent" | "warm" | "danger" {
  return status === "rewarded" ? "accent" : "warm"
}

function paymentStatusTone(status: string): "default" | "accent" | "warm" | "danger" {
  if (status === "succeeded") return "accent"
  if (status === "refund_pending") return "warm"
  if (status === "refunded" || status === "failed") return "danger"
  return "default"
}

function describePaymentRecordStatus(status: string) {
  if (status === "succeeded") return "支付已确认"
  if (status === "refund_pending") return "退款处理中"
  if (status === "refunded") return "退款已完成"
  if (status === "failed") return "支付失败"
  return status
}

function describeRemotePaymentStatus(status: string) {
  if (status === "paid") return "远端显示已支付"
  if (status === "pending") return "远端仍待支付"
  if (status === "closed") return "远端订单已关闭"
  if (status === "failed") return "远端支付失败"
  if (status === "refunded") return "远端订单已退款"
  if (status === "unknown") return "远端状态未知"
  return status
}

function describeMembershipAccountStatus(status: string) {
  if (status === "active") return "会员有效"
  if (status === "expired") return "会员已过期"
  if (status === "never_purchased") return "未开通过会员"
  return status
}

function prettyJson(value: string | null | undefined) {
  const text = String(value || "").trim()
  if (!text) return ""
  try {
    return JSON.stringify(JSON.parse(text), null, 2)
  } catch {
    return text
  }
}

function DetailMetric(props: { label: string; value: string; tone?: "default" | "accent" | "warm" | "danger" }) {
  return (
    <div
      className={cn(
        "rounded-2xl border px-4 py-3",
        props.tone === "accent"
          ? "theme-accent-surface"
          : props.tone === "warm"
            ? "theme-warm-surface"
            : props.tone === "danger"
              ? "theme-danger-surface"
              : "theme-subtle-surface",
      )}
    >
      <div className="text-xs text-muted-foreground">{props.label}</div>
      <div className="mt-1 break-all text-sm font-medium text-foreground">{props.value}</div>
    </div>
  )
}

function TimelineRow(props: {
  title: string
  time: string | null | undefined
  description: string
  tone?: "default" | "accent" | "warm" | "danger"
}) {
  return (
    <div className="flex gap-3">
      <div className="flex flex-col items-center">
        <span
          className={cn(
            "mt-1 h-2.5 w-2.5 rounded-full",
            props.tone === "accent"
              ? "bg-primary"
              : props.tone === "warm"
                ? "bg-[color:var(--theme-warm-text)]"
                : props.tone === "danger"
                  ? "bg-destructive"
                  : "bg-[color:var(--theme-subtle-text)]",
          )}
        />
        <span className="mt-1 h-full w-px bg-[color:var(--theme-soft-border)]" />
      </div>
      <div className="min-w-0 flex-1 pb-4">
        <div className="text-sm font-medium text-foreground">{props.title}</div>
        <div className="text-xs text-muted-foreground">{formatMembershipDateTime(props.time)}</div>
        <div className="mt-1 text-sm text-muted-foreground">{props.description}</div>
      </div>
    </div>
  )
}

export function AdminMembershipPage() {
  const [orderUserSearch, setOrderUserSearch] = useState("")
  const [orderStatus, setOrderStatus] = useState("all")
  const [orderType, setOrderType] = useState("all")
  const [orderProvider, setOrderProvider] = useState("all")
  const [selectedOrderId, setSelectedOrderId] = useState("")
  const [inviteSearch, setInviteSearch] = useState("")
  const [inviteStatus, setInviteStatus] = useState("all")
  const [couponSearch, setCouponSearch] = useState("")
  const [couponStatus, setCouponStatus] = useState("all")
  const [grantUserId, setGrantUserId] = useState("")
  const [grantAmountCent, setGrantAmountCent] = useState("500")
  const [grantTitle, setGrantTitle] = useState("后台补偿 5 元券")
  const [grantExpiresInDays, setGrantExpiresInDays] = useState("30")
  const [grantMinSpendCent, setGrantMinSpendCent] = useState("0")

  const overviewQ = useAdminMembershipOverview()
  const ordersQ = useAdminMembershipOrders(
    {
      userSearch: orderUserSearch.trim() || undefined,
      status: orderStatus === "all" ? undefined : orderStatus,
      orderType: orderType === "all" ? undefined : orderType,
      provider: orderProvider === "all" ? undefined : orderProvider,
      limit: 50,
    },
    true,
  )
  const invitesQ = useAdminMembershipInvites(
    {
      search: inviteSearch.trim() || undefined,
      status: inviteStatus === "all" ? undefined : inviteStatus,
      limit: 50,
    },
    true,
  )
  const couponsQ = useAdminMembershipCoupons(
    {
      search: couponSearch.trim() || undefined,
      status: couponStatus === "all" ? undefined : couponStatus,
      limit: 50,
    },
    true,
  )
  const orderDetailQ = useAdminMembershipOrderDetail(selectedOrderId, Boolean(selectedOrderId))
  const grantCoupon = useGrantAdminMembershipCoupon()
  const refundOrder = useRefundAdminMembershipOrder()
  const syncPayment = useSyncAdminMembershipOrderPayment()
  const closeOrder = useCloseAdminMembershipOrder()
  const voidCoupon = useVoidAdminMembershipCoupon()

  useEffect(() => {
    const orders = ordersQ.data ?? []
    if (orders.length === 0) {
      if (selectedOrderId) setSelectedOrderId("")
      return
    }
    if (!selectedOrderId || !orders.some((item) => item.orderId === selectedOrderId)) {
      setSelectedOrderId(orders[0].orderId)
    }
  }, [ordersQ.data, selectedOrderId])

  async function onCopyValue(label: string, value: string | null | undefined) {
    const text = String(value || "").trim()
    if (!text) {
      showErrorFeedback("复制失败", `${label} 还没有可复制的值。`)
      return
    }
    try {
      await copyTextToClipboard(text)
      showSuccessFeedback("已复制", `${label} 已复制到剪贴板。`)
    } catch (err) {
      showErrorFeedback("复制失败", formatApiError(err))
    }
  }

  async function onSyncPayment(orderId: string) {
    setSelectedOrderId(orderId)
    try {
      const result = await syncPayment.mutateAsync({ orderId })
      if (result.confirmed) {
        showSuccessFeedback(
          result.idempotent ? "支付状态已同步" : "订单已确认支付",
          result.remote.providerTradeNo
            ? `支付流水号 ${result.remote.providerTradeNo}，当前订单已进入 ${describeMembershipOrderStatus(result.order.status)}。`
            : "本地订单和会员状态已经更新。",
        )
        return
      }
      if (result.order.status === "closed") {
        showSuccessFeedback(
          "订单已结束",
          result.remote.remoteStatus === "closed"
            ? "微信侧订单已经关闭，本地待支付记录也已同步关闭。"
            : result.remote.remoteStatus === "failed"
              ? "微信侧返回支付失败，本地待支付记录已经结束。"
              : `远端当前是 ${describeRemotePaymentStatus(result.remote.remoteStatus)}，本地不会再继续等待支付。`,
        )
        return
      }
      showSuccessFeedback("支付状态已刷新", describeRemotePaymentStatus(result.remote.remoteStatus))
    } catch (err) {
      showErrorFeedback("同步支付状态失败", formatApiError(err))
    }
  }

  async function onCloseOrder(orderId: string, orderType: string, provider: string) {
    setSelectedOrderId(orderId)
    if (
      typeof window !== "undefined" &&
      !window.confirm(
        `确认关闭这笔${orderType === "first_purchase" ? "首单" : "续费"}待支付订单吗？${
          provider === "wechat_native" ? "如果微信侧已经终态，这会把本地工作台一并收口。" : "这笔测试订单会立即结束等待支付。"
        }`,
      )
    ) {
      return
    }
    try {
      const result = await closeOrder.mutateAsync({ orderId })
      showSuccessFeedback(
        result.idempotent ? "订单已关闭" : "待支付订单已关闭",
        result.payment?.providerTradeNo ? `关联支付流水 ${result.payment.providerTradeNo} 已保留用于排障。` : "本地订单已结束等待支付。",
      )
    } catch (err) {
      showErrorFeedback("关闭订单失败", formatApiError(err))
    }
  }

  async function onGrantCoupon(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const amountCent = Number(grantAmountCent)
    const expiresInDays = Number(grantExpiresInDays)
    const minSpendCent = Number(grantMinSpendCent)
    if (!grantUserId.trim()) {
      showErrorFeedback("发券失败", "请先填写目标用户 ID 或 UID。")
      return
    }
    if (!Number.isFinite(amountCent) || amountCent <= 0) {
      showErrorFeedback("发券失败", "券面额必须是大于 0 的数字。")
      return
    }
    if (!grantTitle.trim()) {
      showErrorFeedback("发券失败", "请填写优惠券标题。")
      return
    }
    if (!Number.isFinite(expiresInDays) || expiresInDays <= 0) {
      showErrorFeedback("发券失败", "有效期天数必须是大于 0 的数字。")
      return
    }
    if (!Number.isFinite(minSpendCent) || minSpendCent < 0) {
      showErrorFeedback("发券失败", "最低消费金额不能小于 0。")
      return
    }
    try {
      const coupon = await grantCoupon.mutateAsync({
        userId: grantUserId.trim(),
        amountCent: Math.round(amountCent),
        title: grantTitle.trim(),
        expiresInDays: Math.round(expiresInDays),
        minSpendCent: Math.round(minSpendCent),
      })
      const owner = userLabel(coupon.user)
      showSuccessFeedback("会员券已发放", `已向 ${owner.title} 发放 ${coupon.title}。`)
      setGrantUserId("")
    } catch (err) {
      showErrorFeedback("发券失败", formatApiError(err))
    }
  }

  async function onVoidCoupon(couponId: string, title: string) {
    if (typeof window !== "undefined" && !window.confirm(`确认作废「${title}」吗？`)) {
      return
    }
    try {
      await voidCoupon.mutateAsync({
        couponId,
        reason: "后台会员中心手动作废",
      })
      showSuccessFeedback("优惠券已作废", `${title} 已从可用状态移除。`)
    } catch (err) {
      showErrorFeedback("作废优惠券失败", formatApiError(err))
    }
  }

  async function onRefundOrder(orderId: string, orderType: string, provider: string, status: string) {
    setSelectedOrderId(orderId)
    const actionLabel =
      provider === "wechat_native" && status === "paid"
        ? "发起微信退款"
        : provider === "wechat_native" && status === "refund_pending"
          ? "同步微信退款结果"
          : "执行退款回滚"
    if (
      typeof window !== "undefined" &&
      !window.confirm(
        `${actionLabel}这笔${orderType === "first_purchase" ? "首单" : "续费"}吗？${
          provider === "wechat_native" && status === "paid"
            ? "提交后订单会先进入退款中，待微信回调或同步成功后才会真正回滚会员权益。"
            : "这会同步重算会员权益。"
        }`,
      )
    ) {
      return
    }
    try {
      const result = await refundOrder.mutateAsync({
        orderId,
        reason: "后台会员中心执行退款回滚",
      })
      const notes = []
      if (result.restoredCouponId) notes.push(`已恢复优惠券 ${result.restoredCouponId}`)
      if (result.revokedRewardCouponId) notes.push(`已回收奖励券 ${result.revokedRewardCouponId}`)
      if (result.completed) {
        showSuccessFeedback(
          result.idempotent ? "退款状态已同步" : "会员订单已退款",
          notes.length > 0 ? notes.join("，") : "会员权益和相关营销状态已经重算。",
        )
        return
      }
      if (result.refundRequestSubmitted) {
        showSuccessFeedback(
          "退款申请已提交",
          result.providerRefundNo ? `微信退款单号 ${result.providerRefundNo}，当前状态 ${result.remoteStatus ?? "refund_pending"}。` : "订单已进入退款中。",
        )
        return
      }
      showSuccessFeedback(
        "退款状态已同步",
        result.remoteStatus === "failed" ? "微信侧退款未成功，订单已恢复为已支付状态。" : `当前远端状态：${result.remoteStatus ?? "unknown"}`,
      )
    } catch (err) {
      showErrorFeedback("执行退款回滚失败", formatApiError(err))
    }
  }

  if (overviewQ.isLoading && !overviewQ.data) {
    return <LoadingNotice title="正在加载会员后台" message="稍等一下，我们正在汇总订单、邀请和优惠券数据。" />
  }

  if (overviewQ.error && !overviewQ.data) {
    return <ErrorNotice title="会员后台加载失败" message={formatApiError(overviewQ.error)} />
  }

  const overview = overviewQ.data
  const stats = overview
    ? [
        { label: "已支付订单", value: overview.paidOrders, help: "完成支付的会员订单总数" },
        { label: "活跃会员", value: overview.activeMemberships, help: "当前仍在有效期内的会员" },
        { label: "会员收入", value: formatMembershipPrice(overview.totalPaidAmountCent), help: "已支付订单累计实收" },
        { label: "邀请绑定", value: overview.inviteBindings, help: "已录入的邀请码绑定关系" },
        { label: "已转化邀请", value: overview.rewardedInvites, help: "首单支付成功并发券的邀请" },
        { label: "可用优惠券", value: overview.availableCoupons, help: "当前仍可在会员下单时使用" },
      ]
    : []

  const riskSignals: Array<{ title: string; message: string; tone: "default" | "warm" | "danger" }> = []
  if (overview && overview.pendingOrders > 0) {
    riskSignals.push({
      title: "待支付订单仍在堆积",
      message: `当前还有 ${overview.pendingOrders} 笔待支付订单，适合定期巡检是否存在反复下单未支付的异常行为。`,
      tone: "warm",
    })
  }
  const pendingInviteCount = invitesQ.data?.filter((item) => item.status === "bound").length ?? 0
  if (pendingInviteCount > 0) {
    riskSignals.push({
      title: "存在待转化邀请",
      message: `当前筛选结果里有 ${pendingInviteCount} 条邀请码绑定还没转化首单，可以重点关注是否存在批量注册未支付。`,
      tone: "default",
    })
  }
  const revokedCouponCount = couponsQ.data?.filter((item) => item.status === "revoked").length ?? 0
  if (revokedCouponCount > 0) {
    riskSignals.push({
      title: "最近有手动作废的券",
      message: `当前券列表里有 ${revokedCouponCount} 张已撤销优惠券，建议结合操作日志回看原因。`,
      tone: "danger",
    })
  }
  const adminGrantedAvailableCount =
    couponsQ.data?.filter((item) => item.status === "available" && item.source === "admin_grant").length ?? 0
  if (adminGrantedAvailableCount > 0) {
    riskSignals.push({
      title: "后台补偿券仍在流通",
      message: `当前列表里还有 ${adminGrantedAvailableCount} 张后台发放的可用券，适合按活动或补偿批次定期复盘。`,
      tone: "default",
    })
  }
  const refundedOrderCount = ordersQ.data?.filter((item) => item.status === "refunded").length ?? 0
  if (refundedOrderCount > 0) {
    riskSignals.push({
      title: "近期已有退款回滚",
      message: `当前订单结果里有 ${refundedOrderCount} 笔已退款订单，建议结合邀请奖励和用券恢复情况一起复核。`,
      tone: "warm",
    })
  }

  const selectedOrderSummary = ordersQ.data?.find((item) => item.orderId === selectedOrderId) ?? null
  const selectedOrderDetail = orderDetailQ.data
  const detailOwner = selectedOrderDetail ? userLabel(selectedOrderDetail.order.user) : null
  const detailNotes: Array<{ title: string; message: string; tone: "default" | "accent" | "warm" | "danger" }> = []
  if (selectedOrderDetail) {
    if (selectedOrderDetail.operations.canSyncPayment && !selectedOrderDetail.payment) {
      detailNotes.push({
        title: "还没有本地支付流水",
        message: "这笔微信订单仍处于待支付，本地还没写入支付确认记录。可以直接在这里点击同步支付状态。",
        tone: "warm",
      })
    }
    if (selectedOrderDetail.operations.canSyncRefund && selectedOrderDetail.payment?.refundOutRefundNo) {
      detailNotes.push({
        title: "退款申请已提交微信",
        message: `退款单号 ${selectedOrderDetail.payment.refundOutRefundNo} 正在等待微信回调或后台主动同步。`,
        tone: "accent",
      })
    }
    if (
      selectedOrderDetail.order.status === "closed" &&
      selectedOrderDetail.payment?.status === "failed" &&
      selectedOrderDetail.order.provider === "wechat_native"
    ) {
      detailNotes.push({
        title: "待支付订单已按远端终态收口",
        message: selectedOrderDetail.order.remark
          ? `本地备注：${selectedOrderDetail.order.remark}。这类订单通常不需要再人工继续同步。`
          : "微信侧已经返回终态，本地已停止继续等待支付。",
        tone: "default",
      })
    }
    if (selectedOrderDetail.invite?.rewardTriggeredByThisOrder) {
      detailNotes.push({
        title: "这笔订单触发了邀请奖励",
        message: selectedOrderDetail.invite.rewardCoupon
          ? `奖励券 ${selectedOrderDetail.invite.rewardCoupon.couponId} 已发给邀请人。`
          : "邀请奖励已关联到这笔订单，可以继续检查奖励券状态。",
        tone: "accent",
      })
    }
    if (selectedOrderDetail.coupon && selectedOrderDetail.coupon.status !== "used" && selectedOrderDetail.order.status === "paid") {
      detailNotes.push({
        title: "订单和用券状态不一致",
        message: `订单显示已支付，但关联优惠券 ${selectedOrderDetail.coupon.couponId} 当前状态是 ${describeMembershipCouponStatus(
          selectedOrderDetail.coupon.status,
        )}，建议优先复核。`,
        tone: "danger",
      })
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-3">
        <div className="space-y-1">
          <div className="text-sm text-muted-foreground">后台管理 / 会员运营</div>
          <div className="text-2xl font-semibold text-foreground">会员运营与风控</div>
        </div>
        <AdminNav />
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
        {stats.map((item) => (
          <Card key={item.label}>
            <CardHeader className="pb-3">
              <CardDescription>{item.label}</CardDescription>
              <CardTitle className="text-2xl">{item.value}</CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">{item.help}</CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
        <Card>
          <CardHeader>
            <CardTitle>人工发券</CardTitle>
            <CardDescription>用于补偿、活动补发或人工干预。目标用户支持填写内部 userId，也支持直接填公开 UID。</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="grid gap-4 md:grid-cols-2" onSubmit={(event) => void onGrantCoupon(event)}>
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="admin-membership-grant-user">目标用户</Label>
                <Input
                  id="admin-membership-grant-user"
                  value={grantUserId}
                  onChange={(event) => setGrantUserId(event.target.value)}
                  placeholder="userId 或公开 UID"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="admin-membership-grant-title">券标题</Label>
                <Input
                  id="admin-membership-grant-title"
                  value={grantTitle}
                  onChange={(event) => setGrantTitle(event.target.value)}
                  placeholder="后台补偿 5 元券"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="admin-membership-grant-amount">券面额（分）</Label>
                <Input
                  id="admin-membership-grant-amount"
                  type="number"
                  min="1"
                  step="1"
                  value={grantAmountCent}
                  onChange={(event) => setGrantAmountCent(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="admin-membership-grant-expire">有效期（天）</Label>
                <Input
                  id="admin-membership-grant-expire"
                  type="number"
                  min="1"
                  step="1"
                  value={grantExpiresInDays}
                  onChange={(event) => setGrantExpiresInDays(event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="admin-membership-grant-min-spend">最低消费（分）</Label>
                <Input
                  id="admin-membership-grant-min-spend"
                  type="number"
                  min="0"
                  step="1"
                  value={grantMinSpendCent}
                  onChange={(event) => setGrantMinSpendCent(event.target.value)}
                />
              </div>
              <div className="theme-subtle-surface md:col-span-2 flex flex-wrap items-center justify-between gap-3 rounded-[1rem] border-dashed px-4 py-3">
                <div className="text-sm text-muted-foreground">
                  当前表单会发放一张面额 {formatMembershipPrice(Number(grantAmountCent) || 0)}、最低消费{" "}
                  {formatMembershipPrice(Number(grantMinSpendCent) || 0)} 的会员券。
                </div>
                <Button type="submit" disabled={grantCoupon.isPending}>
                  {grantCoupon.isPending ? "正在发券..." : "确认发券"}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>风控提醒</CardTitle>
            <CardDescription>这里先做一版轻量巡检，提醒后台优先处理的会员风险点。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {riskSignals.length === 0 ? (
              <ContentEmptyState title="当前没有明显异常" message="订单、邀请和优惠券看起来都比较平稳，继续按日常节奏巡检就可以。" />
            ) : null}
            {riskSignals.map((item) => (
              <div
                key={item.title}
                className={cn(
                  "rounded-[1rem] border px-4 py-4",
                  item.tone === "danger"
                    ? "theme-danger-surface"
                    : item.tone === "warm"
                      ? "theme-warm-surface"
                      : "theme-soft-surface",
                )}
              >
                <div className="text-sm font-semibold text-foreground">{item.title}</div>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.message}</p>
              </div>
            ))}
            <div className="theme-subtle-surface rounded-[1rem] border-dashed px-4 py-4 text-sm leading-6 text-muted-foreground">
              建议运营侧重点关注三类动作：待支付订单的重复创建、邀请码绑定后长期不转化、以及后台补偿券是否被及时消费或回收。
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>会员订单</CardTitle>
          <CardDescription>这一轮把订单区升级成后台工作台，除了筛选列表，还能直接查看支付流水、退款链路和营销关联。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_180px_180px_180px]">
            <div className="space-y-2">
              <Label htmlFor="admin-membership-order-search">搜索用户</Label>
              <Input
                id="admin-membership-order-search"
                value={orderUserSearch}
                onChange={(event) => setOrderUserSearch(event.target.value)}
                placeholder="邮箱 / 昵称 / UID / userId"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="admin-membership-order-status">订单状态</Label>
              <select
                id="admin-membership-order-status"
                className="theme-select h-10 w-full px-3"
                value={orderStatus}
                onChange={(event) => setOrderStatus(event.target.value)}
              >
                <option value="all">全部状态</option>
                <option value="pending">pending</option>
                <option value="paid">paid</option>
                <option value="expired">expired</option>
                <option value="closed">closed</option>
                <option value="refund_pending">refund_pending</option>
                <option value="refunded">refunded</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="admin-membership-order-type">订单类型</Label>
              <select
                id="admin-membership-order-type"
                className="theme-select h-10 w-full px-3"
                value={orderType}
                onChange={(event) => setOrderType(event.target.value)}
              >
                <option value="all">全部类型</option>
                <option value="first_purchase">first_purchase</option>
                <option value="renewal">renewal</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="admin-membership-order-provider">支付方式</Label>
              <select
                id="admin-membership-order-provider"
                className="theme-select h-10 w-full px-3"
                value={orderProvider}
                onChange={(event) => setOrderProvider(event.target.value)}
              >
                <option value="all">全部方式</option>
                <option value="manual_test">manual_test</option>
                <option value="wechat_native">wechat_native</option>
              </select>
            </div>
          </div>

          {ordersQ.error ? <ErrorNotice title="会员订单加载失败" message={formatApiError(ordersQ.error)} /> : null}
          {!ordersQ.error && ordersQ.isLoading ? <LoadingNotice title="正在加载会员订单" message="后台正在刷新会员支付记录。" /> : null}
          {!ordersQ.error && !ordersQ.isLoading && (ordersQ.data?.length ?? 0) === 0 ? (
            <ContentEmptyState title="没有匹配的订单" message="可以换一个搜索词，或者放宽订单状态和类型筛选。" />
          ) : null}

          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(320px,0.85fr)]">
            <div className="space-y-3">
              {ordersQ.data?.map((order) => {
                const owner = userLabel(order.user)
                const isSelected = order.orderId === selectedOrderId
                return (
                  <div
                    key={order.orderId}
                    className={cn(
                      "w-full rounded-[1rem] border p-4 text-left transition hover:border-primary/30 hover:bg-accent/40",
                      isSelected
                        ? "border-primary/40 bg-primary/10 shadow-sm"
                        : "border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)]",
                    )}
                    onClick={() => setSelectedOrderId(order.orderId)}
                  >
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                      <div className="min-w-0 flex-1 space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <div className="text-sm font-semibold text-foreground">{owner.title}</div>
                          <StatusPill tone={orderStatusTone(order.status)}>{describeMembershipOrderStatus(order.status)}</StatusPill>
                          <StatusPill>{describeMembershipOrderType(order.orderType)}</StatusPill>
                          <StatusPill>{describeMembershipPaymentProvider(order.provider)}</StatusPill>
                          {isSelected ? <StatusPill tone="accent">当前查看中</StatusPill> : null}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {owner.subtitle} · 订单号 {order.orderId}
                        </div>
                        <div className="text-sm text-muted-foreground">
                          实付 {formatMembershipPrice(order.payableAmountCent)} · 原价 {formatMembershipPrice(order.listAmountCent)} · 首单减{" "}
                          {formatMembershipPrice(order.firstOrderDiscountCent)} · 用券减 {formatMembershipPrice(order.couponDiscountCent)}
                        </div>
                        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                          <span>创建时间：{formatMembershipDateTime(order.createdAt)}</span>
                          <span>支付时间：{formatMembershipDateTime(order.paidAt)}</span>
                          <span>到期关闭：{formatMembershipDateTime(order.expiredAt)}</span>
                          <span>客户端：{order.clientVersion || "未上报"} / {order.clientIp || "未上报"}</span>
                        </div>
                          {order.couponId ? <div className="text-xs text-muted-foreground">使用优惠券：{order.couponId}</div> : null}
                          {order.remark ? <div className="text-xs text-muted-foreground">备注：{order.remark}</div> : null}
                       </div>
                       <div className="flex shrink-0 flex-wrap gap-2" onClick={(event) => event.stopPropagation()}>
                          {order.provider === "wechat_native" && order.status === "pending" ? (
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => void onSyncPayment(order.orderId)}
                            disabled={syncPayment.isPending}
                          >
                              同步支付
                            </Button>
                          ) : null}
                          {order.status === "pending" ? (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => void onCloseOrder(order.orderId, order.orderType, order.provider)}
                              disabled={closeOrder.isPending || syncPayment.isPending}
                            >
                              关闭订单
                            </Button>
                          ) : null}
                          {order.status === "paid" || (order.provider === "wechat_native" && order.status === "refund_pending") ? (
                            <Button
                              variant="secondary"
                            size="sm"
                            onClick={() => void onRefundOrder(order.orderId, order.orderType, order.provider, order.status)}
                            disabled={refundOrder.isPending}
                          >
                            {order.provider === "wechat_native" && order.status === "paid"
                              ? "申请微信退款"
                              : order.provider === "wechat_native" && order.status === "refund_pending"
                                ? "同步退款结果"
                                : "执行退款回滚"}
                          </Button>
                        ) : null}
                        {order.user.status !== "missing" ? (
                          <Button asChild variant="outline" size="sm">
                            <Link to={`/admin/users/${order.user.userId}`}>查看用户</Link>
                          </Button>
                        ) : null}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            <Card className="xl:sticky xl:top-24">
              <CardHeader>
                <CardTitle>订单详情面板</CardTitle>
                <CardDescription>
                  {selectedOrderSummary
                    ? `正在查看 ${selectedOrderSummary.orderId}，这里会集中展示支付、退款、会员状态和营销链路。`
                    : "选中一笔订单后，可以在这里查看支付时间线、原始回调和运营诊断。"}
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {!selectedOrderId ? (
                  <ContentEmptyState title="还没有选中订单" message="左侧选中一笔会员订单后，这里会显示完整排障信息。" />
                ) : null}
                {selectedOrderId && orderDetailQ.isLoading && !selectedOrderDetail ? (
                  <LoadingNotice title="正在加载订单详情" message="正在拉取支付流水、会员状态和营销链路。" />
                ) : null}
                {selectedOrderId && orderDetailQ.error && !selectedOrderDetail ? (
                  <ErrorNotice title="订单详情加载失败" message={formatApiError(orderDetailQ.error)} />
                ) : null}

                {selectedOrderDetail && detailOwner ? (
                  <>
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="text-lg font-semibold text-foreground">{detailOwner.title}</div>
                        <StatusPill tone={orderStatusTone(selectedOrderDetail.order.status)}>
                          {describeMembershipOrderStatus(selectedOrderDetail.order.status)}
                        </StatusPill>
                        <StatusPill>{describeMembershipOrderType(selectedOrderDetail.order.orderType)}</StatusPill>
                        <StatusPill>{describeMembershipPaymentProvider(selectedOrderDetail.order.provider)}</StatusPill>
                      </div>
                      <div className="text-sm text-muted-foreground">{detailOwner.subtitle}</div>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <Button variant="outline" size="sm" onClick={() => void onCopyValue("订单号", selectedOrderDetail.order.orderId)}>
                        复制订单号
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => void onCopyValue("支付流水号", selectedOrderDetail.payment?.providerTradeNo)}
                      >
                        复制支付流水
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => void onCopyValue("退款单号", selectedOrderDetail.payment?.refundOutRefundNo)}
                      >
                        复制退款单号
                      </Button>
                      {selectedOrderDetail.operations.canSyncPayment ? (
                        <Button size="sm" onClick={() => void onSyncPayment(selectedOrderDetail.order.orderId)} disabled={syncPayment.isPending}>
                          同步支付状态
                        </Button>
                      ) : null}
                      {selectedOrderDetail.operations.canCloseOrder ? (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() =>
                            void onCloseOrder(
                              selectedOrderDetail.order.orderId,
                              selectedOrderDetail.order.orderType,
                              selectedOrderDetail.order.provider,
                            )
                          }
                          disabled={closeOrder.isPending || syncPayment.isPending}
                        >
                          关闭待支付订单
                        </Button>
                      ) : null}
                      {selectedOrderDetail.operations.canRequestRefund || selectedOrderDetail.operations.canSyncRefund ? (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() =>
                            void onRefundOrder(
                              selectedOrderDetail.order.orderId,
                              selectedOrderDetail.order.orderType,
                              selectedOrderDetail.order.provider,
                              selectedOrderDetail.order.status,
                            )
                          }
                          disabled={refundOrder.isPending}
                        >
                          {selectedOrderDetail.operations.canSyncRefund ? "同步退款结果" : "申请退款 / 回滚"}
                        </Button>
                      ) : null}
                    </div>

                    <div className="grid gap-3 md:grid-cols-2">
                      <DetailMetric label="订单号" value={selectedOrderDetail.order.orderId} />
                      <DetailMetric label="当前会员状态" value={describeMembershipAccountStatus(selectedOrderDetail.membership.currentStatus)} />
                      <DetailMetric label="订单实付" value={formatMembershipPrice(selectedOrderDetail.order.payableAmountCent)} tone="accent" />
                      <DetailMetric label="会员当前价" value={formatMembershipPrice(selectedOrderDetail.membership.currentPriceCent)} />
                      <DetailMetric label="创建时间" value={formatMembershipDateTime(selectedOrderDetail.order.createdAt)} />
                      <DetailMetric label="支付时间" value={formatMembershipDateTime(selectedOrderDetail.order.paidAt)} />
                      <DetailMetric label="关闭时间" value={formatMembershipDateTime(selectedOrderDetail.order.closedAt)} />
                      <DetailMetric label="会员到期" value={formatMembershipDateTime(selectedOrderDetail.membership.currentEndsAt)} />
                      <DetailMetric label="客户端" value={`${selectedOrderDetail.order.clientVersion || "未上报"} / ${selectedOrderDetail.order.clientIp || "未上报"}`} />
                    </div>

                    <div className="theme-soft-surface rounded-[1rem] p-4">
                      <div className="text-sm font-semibold text-foreground">支付与退款时间线</div>
                      <div className="mt-4">
                        <TimelineRow
                          title="订单创建"
                          time={selectedOrderDetail.order.createdAt}
                          description={`以 ${describeMembershipPaymentProvider(selectedOrderDetail.order.provider)} 创建订单，等待支付。`}
                        />
                        <TimelineRow
                          title="支付确认"
                          time={selectedOrderDetail.payment?.confirmedAt ?? selectedOrderDetail.order.paidAt}
                          tone={selectedOrderDetail.order.status === "paid" || selectedOrderDetail.payment?.status === "succeeded" ? "accent" : "default"}
                          description={
                            selectedOrderDetail.payment
                              ? `${describePaymentRecordStatus(selectedOrderDetail.payment.status)}${selectedOrderDetail.payment.providerTradeNo ? `，支付流水 ${selectedOrderDetail.payment.providerTradeNo}` : ""}`
                              : "本地还没有支付流水记录。"
                          }
                        />
                        <TimelineRow
                          title="订单关闭"
                          time={selectedOrderDetail.order.closedAt}
                          tone={selectedOrderDetail.order.status === "closed" ? "danger" : "default"}
                          description={
                            selectedOrderDetail.order.status === "closed"
                              ? selectedOrderDetail.order.remark || "待支付订单已结束，不再继续等待支付。"
                              : "当前没有订单关闭记录。"
                          }
                        />
                        <TimelineRow
                          title="退款申请"
                          time={selectedOrderDetail.payment?.refundRequestedAt}
                          tone={selectedOrderDetail.order.status === "refund_pending" ? "warm" : "default"}
                          description={
                            selectedOrderDetail.payment?.refundOutRefundNo
                              ? `已生成退款单号 ${selectedOrderDetail.payment.refundOutRefundNo}`
                              : "当前没有退款申请记录。"
                          }
                        />
                        <TimelineRow
                          title="退款完成"
                          time={selectedOrderDetail.payment?.refundedAt}
                          tone={selectedOrderDetail.order.status === "refunded" ? "danger" : "default"}
                          description={
                            selectedOrderDetail.order.status === "refunded"
                              ? "本地账务已经完成退款回滚，会员权益与营销状态已重算。"
                              : "还没有完成退款。"
                          }
                        />
                      </div>
                      <div className="grid gap-3 md:grid-cols-2">
                        <DetailMetric
                          label="支付记录状态"
                          value={
                            selectedOrderDetail.payment
                              ? describePaymentRecordStatus(selectedOrderDetail.payment.status)
                              : "还没有支付记录"
                          }
                          tone={selectedOrderDetail.payment ? paymentStatusTone(selectedOrderDetail.payment.status) : "default"}
                        />
                        <DetailMetric
                          label="付款方标识"
                          value={selectedOrderDetail.payment?.providerBuyerId || "微信尚未返回 / 不适用"}
                        />
                      </div>
                    </div>

                    <div className="theme-soft-surface rounded-[1rem] p-4">
                      <div className="text-sm font-semibold text-foreground">营销关联</div>
                      <div className="mt-4 space-y-3 text-sm text-muted-foreground">
                        <div>
                          使用优惠券：
                          {selectedOrderDetail.coupon
                            ? `${selectedOrderDetail.coupon.title}（${selectedOrderDetail.coupon.couponId}，${describeMembershipCouponStatus(selectedOrderDetail.coupon.status)}）`
                            : "本单未使用优惠券"}
                        </div>
                        <div>
                          邀请绑定：
                          {selectedOrderDetail.invite
                            ? `${selectedOrderDetail.invite.binding.inviter.publicUid || selectedOrderDetail.invite.binding.inviter.userId} -> ${
                                selectedOrderDetail.invite.binding.invitee.publicUid || selectedOrderDetail.invite.binding.invitee.userId
                              }，状态 ${describeInviteRecordStatus(selectedOrderDetail.invite.binding.status)}`
                            : "当前用户没有邀请码绑定"}
                        </div>
                        <div>
                          奖励触发：
                          {selectedOrderDetail.invite?.rewardTriggeredByThisOrder
                            ? selectedOrderDetail.invite.rewardCoupon
                              ? `本单已触发奖励券 ${selectedOrderDetail.invite.rewardCoupon.couponId}`
                              : "本单已触发邀请奖励"
                            : "这笔订单没有触发新的邀请奖励"}
                        </div>
                      </div>
                    </div>

                    <div className="space-y-3">
                      {detailNotes.length === 0 ? (
                        <div className="theme-subtle-surface rounded-[1rem] border-dashed px-4 py-4 text-sm leading-6 text-muted-foreground">
                          当前这笔订单没有明显异常信号，支付、退款和营销关联看起来是自洽的。
                        </div>
                      ) : null}
                      {detailNotes.map((item) => (
                        <div
                          key={item.title}
                          className={cn(
                            "rounded-[1rem] border px-4 py-4",
                            item.tone === "danger"
                              ? "theme-danger-surface"
                              : item.tone === "warm"
                                ? "theme-warm-surface"
                                : item.tone === "accent"
                                  ? "theme-accent-surface"
                                  : "theme-soft-surface",
                          )}
                        >
                          <div className="text-sm font-semibold text-foreground">{item.title}</div>
                          <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.message}</p>
                        </div>
                      ))}
                    </div>

                    {(selectedOrderDetail.payment?.hasPaymentCallbackPayload || selectedOrderDetail.payment?.hasRefundCallbackPayload) && (
                      <div className="space-y-3">
                        <div className="text-sm font-semibold text-foreground">原始回调与同步报文</div>
                        {selectedOrderDetail.payment?.hasPaymentCallbackPayload ? (
                          <div className="rounded-[1rem] border border-[#e3e8ef] bg-[#0f172a] p-4">
                            <div className="mb-2 text-xs font-medium uppercase tracking-[0.2em] text-slate-300">Payment Payload</div>
                            <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-all text-xs leading-6 text-slate-100">
                              {prettyJson(selectedOrderDetail.payment.paymentCallbackPayloadJson)}
                            </pre>
                          </div>
                        ) : null}
                        {selectedOrderDetail.payment?.hasRefundCallbackPayload ? (
                          <div className="rounded-[1rem] border border-[#e3e8ef] bg-[#111827] p-4">
                            <div className="mb-2 text-xs font-medium uppercase tracking-[0.2em] text-slate-300">Refund Payload</div>
                            <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-all text-xs leading-6 text-slate-100">
                              {prettyJson(selectedOrderDetail.payment.refundCallbackPayloadJson)}
                            </pre>
                          </div>
                        ) : null}
                      </div>
                    )}
                  </>
                ) : null}
              </CardContent>
            </Card>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>邀请转化</CardTitle>
          <CardDescription>用来追踪邀请码绑定是否成功、谁已转化首单，以及奖励券是否正确发放。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px]">
            <div className="space-y-2">
              <Label htmlFor="admin-membership-invite-search">搜索用户</Label>
              <Input
                id="admin-membership-invite-search"
                value={inviteSearch}
                onChange={(event) => setInviteSearch(event.target.value)}
                placeholder="邀请人 / 被邀请人 邮箱、昵称、UID"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="admin-membership-invite-status">绑定状态</Label>
              <select
                id="admin-membership-invite-status"
                className="theme-select h-10 w-full px-3"
                value={inviteStatus}
                onChange={(event) => setInviteStatus(event.target.value)}
              >
                <option value="all">全部状态</option>
                <option value="bound">bound</option>
                <option value="rewarded">rewarded</option>
              </select>
            </div>
          </div>

          {invitesQ.error ? <ErrorNotice title="邀请记录加载失败" message={formatApiError(invitesQ.error)} /> : null}
          {!invitesQ.error && invitesQ.isLoading ? <LoadingNotice title="正在加载邀请记录" message="后台正在汇总邀请码绑定与奖励发放数据。" /> : null}
          {!invitesQ.error && !invitesQ.isLoading && (invitesQ.data?.length ?? 0) === 0 ? (
            <ContentEmptyState title="没有匹配的邀请记录" message="可以换个用户关键词，或者放宽绑定状态筛选。" />
          ) : null}

          {invitesQ.data?.map((item) => {
            const inviter = userLabel(item.inviter)
            const invitee = userLabel(item.invitee)
            return (
              <div key={`${item.invitee.userId}:${item.boundAt}`} className="theme-soft-surface rounded-[1rem] p-4">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="text-sm font-semibold text-foreground">{inviter.title}</div>
                      <span className="text-xs text-muted-foreground">邀请了</span>
                      <div className="text-sm font-semibold text-foreground">{invitee.title}</div>
                      <StatusPill tone={inviteStatusTone(item.status)}>{describeInviteRecordStatus(item.status)}</StatusPill>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      邀请码：{item.inviteCode} · 绑定时间：{formatMembershipDateTime(item.boundAt)}
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      <span>邀请人：{inviter.subtitle}</span>
                      <span>被邀请人：{invitee.subtitle}</span>
                      <span>奖励时间：{formatMembershipDateTime(item.rewardedAt)}</span>
                    </div>
                    {item.rewardCouponId || item.rewardTriggerOrderId ? (
                      <div className="text-xs text-muted-foreground">
                        触发订单：{item.rewardTriggerOrderId || "未触发"} · 奖励券：{item.rewardCouponId || "未发放"}
                      </div>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-2">
                    {item.inviter.status !== "missing" ? (
                      <Button asChild variant="outline" size="sm">
                        <Link to={`/admin/users/${item.inviter.userId}`}>查看邀请人</Link>
                      </Button>
                    ) : null}
                    {item.invitee.status !== "missing" ? (
                      <Button asChild variant="outline" size="sm">
                        <Link to={`/admin/users/${item.invitee.userId}`}>查看被邀请人</Link>
                      </Button>
                    ) : null}
                  </div>
                </div>
              </div>
            )
          })}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>优惠券运营</CardTitle>
          <CardDescription>查看邀请奖励券和后台补偿券的状态，必要时可以手动作废还未使用的券。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px]">
            <div className="space-y-2">
              <Label htmlFor="admin-membership-coupon-search">搜索用户</Label>
              <Input
                id="admin-membership-coupon-search"
                value={couponSearch}
                onChange={(event) => setCouponSearch(event.target.value)}
                placeholder="持券人 / 来源用户 邮箱、昵称、UID"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="admin-membership-coupon-status">优惠券状态</Label>
              <select
                id="admin-membership-coupon-status"
                className="theme-select h-10 w-full px-3"
                value={couponStatus}
                onChange={(event) => setCouponStatus(event.target.value)}
              >
                <option value="all">全部状态</option>
                <option value="available">available</option>
                <option value="used">used</option>
                <option value="revoked">revoked</option>
                <option value="expired">expired</option>
              </select>
            </div>
          </div>

          {couponsQ.error ? <ErrorNotice title="优惠券列表加载失败" message={formatApiError(couponsQ.error)} /> : null}
          {!couponsQ.error && couponsQ.isLoading ? <LoadingNotice title="正在加载优惠券" message="后台正在汇总会员券状态。" /> : null}
          {!couponsQ.error && !couponsQ.isLoading && (couponsQ.data?.length ?? 0) === 0 ? (
            <ContentEmptyState title="没有匹配的优惠券" message="可以调整用户关键词，或者换一个状态筛选。" />
          ) : null}

          {couponsQ.data?.map((coupon) => {
            const owner = userLabel(coupon.user)
            const sourceInvitee = coupon.sourceInvitee ? userLabel(coupon.sourceInvitee) : null
            return (
              <div key={coupon.couponId} className="theme-soft-surface rounded-[1rem] p-4">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="text-sm font-semibold text-foreground">{coupon.title}</div>
                      <StatusPill tone={couponStatusTone(coupon.status)}>{describeMembershipCouponStatus(coupon.status)}</StatusPill>
                      <StatusPill>{describeMembershipCouponSource(coupon.source)}</StatusPill>
                    </div>
                    <div className="text-sm text-muted-foreground">
                      持券人：{owner.title} · {owner.subtitle}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      面额 {formatMembershipPrice(coupon.amountCent)} · 满 {formatMembershipPrice(coupon.minSpendCent)} 可用
                    </div>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      <span>创建时间：{formatMembershipDateTime(coupon.createdAt)}</span>
                      <span>过期时间：{formatMembershipDateTime(coupon.expiresAt)}</span>
                      <span>使用时间：{formatMembershipDateTime(coupon.usedAt)}</span>
                    </div>
                    {coupon.usedOrderId ? (
                      <div className="text-xs text-muted-foreground">使用订单：{coupon.usedOrderId}</div>
                    ) : null}
                    {sourceInvitee ? (
                      <div className="text-xs text-muted-foreground">来源被邀请人：{sourceInvitee.title} · {sourceInvitee.subtitle}</div>
                    ) : null}
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-2">
                    {coupon.user.status !== "missing" ? (
                      <Button asChild variant="outline" size="sm">
                        <Link to={`/admin/users/${coupon.user.userId}`}>查看持券人</Link>
                      </Button>
                    ) : null}
                    {coupon.status === "available" ? (
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => void onVoidCoupon(coupon.couponId, coupon.title)}
                        disabled={voidCoupon.isPending}
                      >
                        作废优惠券
                      </Button>
                    ) : null}
                  </div>
                </div>
              </div>
            )
          })}
        </CardContent>
      </Card>
    </div>
  )
}

import { z } from "zod"

import { apiRequest } from "@/ui/api/http"

export const MembershipSummarySchema = z.object({
  userId: z.string(),
  currentStatus: z.enum(["never_purchased", "active", "expired"]),
  currentStartsAt: z.string().nullable(),
  currentEndsAt: z.string().nullable(),
  isActive: z.boolean(),
  isFirstOrderEligible: z.boolean(),
  baseMonthlyPriceCent: z.number(),
  firstOrderPriceCent: z.number(),
  renewalPriceCent: z.number(),
  currentPriceCent: z.number(),
  supportedPaymentProviders: z.array(z.string()),
})

export type MembershipSummary = z.infer<typeof MembershipSummarySchema>

export const MembershipOrderPreviewSchema = z.object({
  userId: z.string(),
  orderType: z.enum(["first_purchase", "renewal"]),
  periodDays: z.number(),
  listAmountCent: z.number(),
  firstOrderDiscountCent: z.number(),
  couponDiscountCent: z.number(),
  payableAmountCent: z.number(),
  couponId: z.string().nullable(),
})

export type MembershipOrderPreview = z.infer<typeof MembershipOrderPreviewSchema>

export const MembershipOrderSchema = z.object({
  orderId: z.string(),
  userId: z.string(),
  orderType: z.enum(["first_purchase", "renewal"]),
  pricingVersion: z.string(),
  periodDays: z.number(),
  listAmountCent: z.number(),
  firstOrderDiscountCent: z.number(),
  couponDiscountCent: z.number(),
  payableAmountCent: z.number(),
  couponId: z.string().nullable(),
  provider: z.string(),
  providerTradeNo: z.string().nullable(),
  status: z.enum(["pending", "paid", "closed", "expired", "refund_pending", "refunded"]),
  clientIp: z.string(),
  clientVersion: z.string(),
  createdAt: z.string(),
  paidAt: z.string().nullable(),
  closedAt: z.string().nullable(),
  refundedAt: z.string().nullable(),
  expiredAt: z.string().nullable(),
  entitlementId: z.string().nullable(),
  remark: z.string(),
})

export type MembershipOrder = z.infer<typeof MembershipOrderSchema>

const MembershipCreateOrderResultSchema = z.object({
  order: MembershipOrderSchema,
  paymentPayload: z.object({
    mode: z.string(),
    provider: z.string(),
    providerLabel: z.string(),
    instruction: z.string(),
    providerTradeNoHint: z.string(),
    expiresAt: z.string().nullable(),
    codeUrl: z.string().nullable(),
    qrImageDataUrl: z.string().nullable(),
    openUrl: z.string().nullable(),
    pollIntervalSeconds: z.number().nullable(),
    statusCheckSupported: z.boolean(),
  }),
  reusedExistingOrder: z.boolean(),
})

export type MembershipCreateOrderResult = z.infer<typeof MembershipCreateOrderResultSchema>

const MembershipPaymentConfirmationSchema = z.object({
  order: MembershipOrderSchema,
  membership: MembershipSummarySchema,
  paymentId: z.string(),
  idempotent: z.boolean(),
})

export type MembershipPaymentConfirmation = z.infer<typeof MembershipPaymentConfirmationSchema>

const MembershipOrderCloseResultSchema = z.object({
  order: MembershipOrderSchema,
  membership: MembershipSummarySchema,
  idempotent: z.boolean(),
})

export type MembershipOrderCloseResult = z.infer<typeof MembershipOrderCloseResultSchema>

const MembershipRemotePaymentStatusSchema = z.object({
  provider: z.string(),
  orderId: z.string(),
  providerTradeNo: z.string(),
  remoteStatus: z.string(),
  paidAt: z.string().nullable(),
  amountCent: z.number().nullable(),
  payerId: z.string().nullable(),
})

const MembershipPaymentSyncResultSchema = z.object({
  confirmed: z.boolean(),
  idempotent: z.boolean(),
  order: MembershipOrderSchema,
  membership: MembershipSummarySchema,
  paymentId: z.string().optional(),
  remote: MembershipRemotePaymentStatusSchema,
})

export type MembershipPaymentSyncResult = z.infer<typeof MembershipPaymentSyncResultSchema>

export const InviteReferralSchema = z.object({
  inviteeUserId: z.string(),
  inviteePublicUid: z.string().nullable(),
  inviteeNickname: z.string().nullable(),
  status: z.string(),
  boundAt: z.string(),
  rewardedAt: z.string().nullable(),
  rewardTriggerOrderId: z.string().nullable(),
  rewardCouponId: z.string().nullable(),
})

export type InviteReferral = z.infer<typeof InviteReferralSchema>

export const InviteSummarySchema = z.object({
  userId: z.string(),
  inviteCode: z.string(),
  boundInviterUserId: z.string().nullable(),
  boundInviteCode: z.string().nullable(),
  bindingStatus: z.string().nullable(),
  boundAt: z.string().nullable(),
  totalInvitedUsers: z.number(),
  rewardedInviteCount: z.number(),
  availableCouponCount: z.number(),
  recentInvites: z.array(InviteReferralSchema),
})

export type InviteSummary = z.infer<typeof InviteSummarySchema>

export const InviteBindingSchema = z.object({
  inviteeUserId: z.string(),
  inviterUserId: z.string(),
  inviteCode: z.string(),
  status: z.string(),
  boundAt: z.string(),
  rewardedAt: z.string().nullable(),
  rewardTriggerOrderId: z.string().nullable(),
  rewardCouponId: z.string().nullable(),
})

export type InviteBinding = z.infer<typeof InviteBindingSchema>

export const CouponRecordSchema = z.object({
  couponId: z.string(),
  userId: z.string(),
  title: z.string(),
  amountCent: z.number(),
  minSpendCent: z.number(),
  source: z.string(),
  status: z.string(),
  sourceInviteeUserId: z.string().nullable(),
  createdAt: z.string(),
  expiresAt: z.string().nullable(),
  usedAt: z.string().nullable(),
  usedOrderId: z.string().nullable(),
})

export type CouponRecord = z.infer<typeof CouponRecordSchema>

export function getMembershipSummary() {
  return apiRequest({
    path: "/membership/me",
    responseSchema: MembershipSummarySchema,
  })
}

export function listMembershipOrders(limit = 20) {
  return apiRequest({
    path: `/membership/orders?limit=${encodeURIComponent(String(limit))}`,
    responseSchema: z.array(MembershipOrderSchema),
  })
}

export function previewMembershipOrder(params?: { couponId?: string | null }) {
  return apiRequest({
    path: "/membership/orders/preview",
    method: "POST",
    body: params?.couponId ? { couponId: params.couponId } : {},
    responseSchema: MembershipOrderPreviewSchema,
  })
}

export function createMembershipOrder(params: { provider: string; couponId?: string | null }) {
  return apiRequest({
    path: "/membership/orders",
    method: "POST",
    body: {
      provider: params.provider,
      couponId: params.couponId?.trim() ? params.couponId.trim() : undefined,
    },
    responseSchema: MembershipCreateOrderResultSchema,
  })
}

export function confirmMembershipPayment(params: { provider: string; orderId: string; providerTradeNo?: string }) {
  return apiRequest({
    path: `/payments/membership/callback/${encodeURIComponent(params.provider)}`,
    method: "POST",
    body: {
      orderId: params.orderId,
      providerTradeNo: params.providerTradeNo,
    },
    responseSchema: MembershipPaymentConfirmationSchema,
  })
}

export function syncMembershipPayment(params: { orderId: string }) {
  return apiRequest({
    path: `/membership/orders/${encodeURIComponent(params.orderId)}/sync-payment`,
    method: "POST",
    responseSchema: MembershipPaymentSyncResultSchema,
  })
}

export function closeMembershipOrder(params: { orderId: string }) {
  return apiRequest({
    path: `/membership/orders/${encodeURIComponent(params.orderId)}/close`,
    method: "POST",
    responseSchema: MembershipOrderCloseResultSchema,
  })
}

export function getInviteSummary() {
  return apiRequest({
    path: "/invites/me",
    responseSchema: InviteSummarySchema,
  })
}

export function bindInviteCode(params: { inviteCode: string }) {
  return apiRequest({
    path: "/invites/bind",
    method: "POST",
    body: { inviteCode: params.inviteCode.trim() },
    responseSchema: InviteBindingSchema,
  })
}

export function listCoupons(limit = 20) {
  return apiRequest({
    path: `/coupons/me?limit=${encodeURIComponent(String(limit))}`,
    responseSchema: z.array(CouponRecordSchema),
  })
}

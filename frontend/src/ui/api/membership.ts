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
  discountCouponId: z.string().nullable(),
  commissionAmountCent: z.number().nullable(),
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
  pendingCommissionCent: z.number().default(0),
  withdrawableCommissionCent: z.number().default(0),
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
  discountCouponId: z.string().nullable(),
})

export type InviteBinding = z.infer<typeof InviteBindingSchema>

export const CouponRecordSchema = z.object({
  couponId: z.string(),
  userId: z.string(),
  title: z.string(),
  couponType: z.string().default("cash"),
  discountRate: z.number().nullable().default(null),
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

export const CommissionAccountSchema = z.object({
  userId: z.string(),
  pendingCent: z.number(),
  withdrawableCent: z.number(),
  reservedCent: z.number(),
  paidOutCent: z.number(),
  canceledCent: z.number(),
  updatedAt: z.string().nullable(),
})

export type CommissionAccount = z.infer<typeof CommissionAccountSchema>

export const PayoutBindingAttemptSchema = z.object({
  bindingAttemptId: z.string(),
  provider: z.string(),
  channel: z.string(),
  status: z.string(),
  state: z.string().optional(),
  authorizationUrl: z.string().optional(),
  desktopReturnUrl: z.string().optional(),
  mobileBindingUrl: z.string().optional(),
  qrCodePayload: z.string().optional(),
  pollAfterMs: z.number().optional(),
  qrExpiresAt: z.string().nullable().optional(),
  scannedAt: z.string().nullable().optional(),
  confirmedAt: z.string().nullable().optional(),
  nextAction: z.string().optional(),
  learningPyramidUserId: z.string().optional(),
  confirmedLearningPyramidUserId: z.string().optional(),
  createdAt: z.string(),
  completedAt: z.string().nullable(),
  expiresAt: z.string(),
  failureReason: z.string(),
})

export type PayoutBindingAttempt = z.infer<typeof PayoutBindingAttemptSchema>

export const PayoutIdentitySchema = z.object({
  provider: z.string(),
  status: z.enum(["unbound", "binding", "ready", "invalid", "provider_unavailable"]).or(z.string()),
  identityId: z.string().nullable(),
  maskedLabel: z.string().nullable(),
  verifiedAt: z.string().nullable(),
  nextAction: z.string().optional(),
  latestBindingAttempt: PayoutBindingAttemptSchema.nullable().optional(),
})

export type PayoutIdentity = z.infer<typeof PayoutIdentitySchema>

export const CommissionRecordSchema = z.object({
  commissionId: z.string(),
  inviteeUserId: z.string(),
  sourceOrderId: z.string(),
  sourcePaymentAmountCent: z.number(),
  thresholdAmountCent: z.number(),
  commissionAmountCent: z.number(),
  refundWindowEndsAt: z.string(),
  status: z.enum(["pending", "settled", "canceled", "reversed"]),
  createdAt: z.string(),
  settledAt: z.string().nullable(),
  canceledAt: z.string().nullable(),
  cancelReason: z.string(),
})

export type CommissionRecord = z.infer<typeof CommissionRecordSchema>

export const CommissionSummarySchema = z.object({
  account: CommissionAccountSchema,
  payoutReadiness: PayoutIdentitySchema,
  recentCommissions: z.array(CommissionRecordSchema),
})

export type CommissionSummary = z.infer<typeof CommissionSummarySchema>

export const CommissionWithdrawalSchema = z.object({
  withdrawalId: z.string(),
  userId: z.string(),
  amountCent: z.number(),
  targetType: z.literal("wechat_pay"),
  identityId: z.string().nullable(),
  identityMaskedLabel: z.string(),
  status: z.enum(["created", "awaiting_confirmation", "processing", "succeeded", "failed", "canceled", "needs_attention"]),
  providerTransferNo: z.string().nullable(),
  outBillNo: z.string(),
  transferBillNo: z.string().nullable(),
  providerState: z.string(),
  confirmation: z
    .object({
      mode: z.literal("wechat_jsapi_requestMerchantTransfer"),
      mchId: z.string(),
      appId: z.string(),
      packageInfo: z.string(),
    })
    .nullable(),
  confirmationUrl: z.string().nullable().optional(),
  failureReason: z.string(),
  createdAt: z.string(),
  reservedAt: z.string().nullable(),
  submittedAt: z.string().nullable(),
  confirmationRequestedAt: z.string().nullable(),
  completedAt: z.string().nullable(),
})

export type CommissionWithdrawal = z.infer<typeof CommissionWithdrawalSchema>

export const CommissionWithdrawalConfirmationSchema = z.object({
  withdrawalId: z.string(),
  amountCent: z.number(),
  identityMaskedLabel: z.string(),
  status: z.enum(["created", "awaiting_confirmation", "processing", "succeeded", "failed", "canceled", "needs_attention"]),
  providerState: z.string(),
  confirmation: z.object({
    mode: z.literal("wechat_jsapi_requestMerchantTransfer"),
    mchId: z.string(),
    appId: z.string(),
    packageInfo: z.string(),
  }),
})

export type CommissionWithdrawalConfirmation = z.infer<typeof CommissionWithdrawalConfirmationSchema>

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

export function getCommissionSummary(limit = 20) {
  return apiRequest({
    path: `/commissions/me?limit=${encodeURIComponent(String(limit))}`,
    responseSchema: CommissionSummarySchema,
  })
}

export function getPayoutIdentity() {
  return apiRequest({
    path: "/commissions/payout-identity",
    responseSchema: PayoutIdentitySchema,
  })
}

export function startPayoutBindingAttempt(params: { channel?: string; returnUrl: string }) {
  return apiRequest({
    path: "/commissions/payout-identity/wechat/binding-attempts",
    method: "POST",
    body: {
      channel: params.channel ?? "desktop_qr_official_account_h5",
      returnUrl: params.returnUrl,
    },
    responseSchema: PayoutBindingAttemptSchema,
  })
}

export function pollPayoutBindingAttempt(params: { bindingAttemptId: string }) {
  return apiRequest({
    path: `/commissions/payout-identity/wechat/binding-attempts/${encodeURIComponent(params.bindingAttemptId)}`,
    responseSchema: PayoutBindingAttemptSchema.extend({
      identityId: z.string().optional(),
      maskedLabel: z.string().optional(),
      verifiedAt: z.string().optional(),
    }),
  })
}

export function openMobilePayoutBinding(params: { bindingAttemptId: string; state: string }) {
  return apiRequest({
    path: `/commissions/payout-identity/wechat/mobile-bind?attempt=${encodeURIComponent(params.bindingAttemptId)}&state=${encodeURIComponent(params.state)}&response=json`,
    responseSchema: PayoutBindingAttemptSchema,
  })
}

export function completePayoutBinding(params: {
  bindingAttemptId: string
  authorizationCode: string
  state: string
  confirmedLearningPyramidUserId?: string
}) {
  return apiRequest({
    path: "/commissions/payout-identity/wechat/bind",
    method: "POST",
    body: {
      bindingAttemptId: params.bindingAttemptId,
      authorizationCode: params.authorizationCode.trim(),
      state: params.state,
      confirmedLearningPyramidUserId: params.confirmedLearningPyramidUserId,
    },
    responseSchema: z.object({
      identityId: z.string(),
      provider: z.string(),
      status: z.string(),
      maskedLabel: z.string(),
      verifiedAt: z.string(),
      failureReason: z.string(),
    }),
  })
}

export function listCommissionWithdrawals(limit = 20) {
  return apiRequest({
    path: `/commissions/withdrawals?limit=${encodeURIComponent(String(limit))}`,
    responseSchema: z.array(CommissionWithdrawalSchema),
  })
}

export function requestCommissionWithdrawal(params: { amountCent: number }) {
  return apiRequest({
    path: "/commissions/withdrawals",
    method: "POST",
    body: {
      amountCent: params.amountCent,
    },
    responseSchema: CommissionWithdrawalSchema,
  })
}

export function getCommissionWithdrawalWechatConfirmation(params: { withdrawalId: string; token: string }) {
  return apiRequest({
    path: `/commissions/withdrawals/${encodeURIComponent(params.withdrawalId)}/wechat-confirmation?token=${encodeURIComponent(params.token)}`,
    responseSchema: CommissionWithdrawalConfirmationSchema,
  })
}

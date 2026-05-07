import { z } from "zod"

import { apiRequest } from "@/ui/api/http"

export const AdminOverviewSchema = z.object({
  users: z.number(),
  activeUsers: z.number(),
  studyUsers: z.number(),
  studyUsers7d: z.number(),
  effectiveStudyMs: z.number(),
  watchMs: z.number(),
  composeMs: z.number(),
  reviewMs: z.number(),
  qaMs: z.number(),
})

export type AdminOverview = z.infer<typeof AdminOverviewSchema>

export const AdminUserSchema = z.object({
  userId: z.string(),
  email: z.string(),
  createdAt: z.string(),
  publicUid: z.string(),
  nickname: z.string(),
  bio: z.string(),
  avatarUrl: z.string().nullable(),
  status: z.string(),
  updatedAt: z.string(),
  roles: z.array(z.string()),
})

export type AdminUser = z.infer<typeof AdminUserSchema>

export const AdminUserDetailSchema = AdminUserSchema

export type AdminUserDetail = z.infer<typeof AdminUserDetailSchema>

export const AdminActionLogSchema = z.object({
  logId: z.string(),
  actorUserId: z.string(),
  actorPublicUid: z.string(),
  actorNickname: z.string(),
  actorAvatarUrl: z.string().nullable(),
  actionType: z.string(),
  targetKind: z.string(),
  targetId: z.string(),
  summary: z.string(),
  createdAt: z.string(),
})

export type AdminActionLog = z.infer<typeof AdminActionLogSchema>

export const AdminMembershipOverviewSchema = z.object({
  paidOrders: z.number(),
  activeMemberships: z.number(),
  totalPaidAmountCent: z.number(),
  firstPurchasePaidOrders: z.number(),
  renewalPaidOrders: z.number(),
  pendingOrders: z.number(),
  inviteBindings: z.number(),
  rewardedInvites: z.number(),
  coupons: z.number(),
  availableCoupons: z.number(),
  usedCoupons: z.number(),
  pendingCommissionCent: z.number().default(0),
  withdrawableCommissionCent: z.number().default(0),
  reservedWithdrawalCent: z.number().default(0),
  paidOutCent: z.number().default(0),
  commissionRecords: z.number().default(0),
  withdrawals: z.number().default(0),
})

export type AdminMembershipOverview = z.infer<typeof AdminMembershipOverviewSchema>

export const AdminMembershipUserRefSchema = z.object({
  userId: z.string(),
  email: z.string().nullable(),
  publicUid: z.string().nullable(),
  nickname: z.string().nullable(),
  status: z.string(),
})

export type AdminMembershipUserRef = z.infer<typeof AdminMembershipUserRefSchema>

export const AdminMembershipOrderSchema = z.object({
  orderId: z.string(),
  user: AdminMembershipUserRefSchema,
  planId: z.string(),
  planName: z.string(),
  orderType: z.string(),
  pricingVersion: z.string(),
  periodDays: z.number(),
  listAmountCent: z.number(),
  firstOrderDiscountCent: z.number(),
  couponDiscountCent: z.number(),
  payableAmountCent: z.number(),
  couponId: z.string().nullable(),
  provider: z.string(),
  providerTradeNo: z.string().nullable(),
  status: z.string(),
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

export type AdminMembershipOrder = z.infer<typeof AdminMembershipOrderSchema>

export const AdminMembershipPaymentSchema = z.object({
  paymentId: z.string(),
  orderId: z.string(),
  provider: z.string(),
  providerTradeNo: z.string().nullable(),
  providerBuyerId: z.string().nullable(),
  amountCent: z.number(),
  status: z.string(),
  createdAt: z.string(),
  confirmedAt: z.string().nullable(),
  refundOutRefundNo: z.string().nullable(),
  refundRequestedAt: z.string().nullable(),
  refundedAt: z.string().nullable(),
  hasPaymentCallbackPayload: z.boolean(),
  paymentCallbackPayloadJson: z.string().nullable(),
  hasRefundCallbackPayload: z.boolean(),
  refundCallbackPayloadJson: z.string().nullable(),
})

export type AdminMembershipPayment = z.infer<typeof AdminMembershipPaymentSchema>

export const AdminMembershipSummarySchema = z.object({
  user: AdminMembershipUserRefSchema,
  userId: z.string(),
  currentStatus: z.string(),
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

export type AdminMembershipSummary = z.infer<typeof AdminMembershipSummarySchema>

export const AdminMembershipGrantSchema = z.object({
  user: AdminMembershipUserRefSchema,
  userId: z.string(),
  entitlementId: z.string(),
  sourceRefId: z.string(),
  months: z.number(),
  grantedDays: z.number(),
  startAt: z.string(),
  endAt: z.string(),
  membership: AdminMembershipSummarySchema,
})

export type AdminMembershipGrant = z.infer<typeof AdminMembershipGrantSchema>

export const AdminMembershipInviteSchema = z.object({
  invitee: AdminMembershipUserRefSchema,
  inviter: AdminMembershipUserRefSchema,
  inviteCode: z.string(),
  status: z.string(),
  boundAt: z.string(),
  rewardedAt: z.string().nullable(),
  rewardTriggerOrderId: z.string().nullable(),
  rewardCouponId: z.string().nullable(),
  discountCouponId: z.string().nullable(),
  commissionId: z.string().optional(),
  commissionAmountCent: z.number().optional(),
  commissionStatus: z.string().optional(),
  refundWindowEndsAt: z.string().optional(),
})

export type AdminMembershipInvite = z.infer<typeof AdminMembershipInviteSchema>

export const AdminMembershipCouponSchema = z.object({
  couponId: z.string(),
  user: AdminMembershipUserRefSchema,
  title: z.string(),
  couponType: z.string().default("cash"),
  discountRate: z.number().nullable().default(null),
  amountCent: z.number(),
  minSpendCent: z.number(),
  source: z.string(),
  status: z.string(),
  sourceInvitee: AdminMembershipUserRefSchema.nullable(),
  createdAt: z.string(),
  expiresAt: z.string().nullable(),
  usedAt: z.string().nullable(),
  usedOrderId: z.string().nullable(),
})

export type AdminMembershipCoupon = z.infer<typeof AdminMembershipCouponSchema>

export const AdminMembershipCommissionSchema = z.object({
  commissionId: z.string(),
  inviter: AdminMembershipUserRefSchema,
  invitee: AdminMembershipUserRefSchema,
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

export type AdminMembershipCommission = z.infer<typeof AdminMembershipCommissionSchema>

export const AdminCommissionSettlementSchema = z.object({
  runId: z.string().default(""),
  scannedCount: z.number().default(0),
  settledCount: z.number(),
  canceledCount: z.number(),
  skippedCount: z.number(),
  errorCount: z.number().default(0),
})

export type AdminCommissionSettlement = z.infer<typeof AdminCommissionSettlementSchema>

export const AdminMembershipWithdrawalSchema = z.object({
  withdrawalId: z.string(),
  user: AdminMembershipUserRefSchema,
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
  failureReason: z.string(),
  createdAt: z.string(),
  reservedAt: z.string().nullable(),
  submittedAt: z.string().nullable(),
  confirmationRequestedAt: z.string().nullable(),
  completedAt: z.string().nullable(),
})

export type AdminMembershipWithdrawal = z.infer<typeof AdminMembershipWithdrawalSchema>

export const AdminPayoutIdentitySchema = z.object({
  identityId: z.string(),
  user: AdminMembershipUserRefSchema,
  userId: z.string(),
  provider: z.string(),
  appid: z.string(),
  maskedLabel: z.string(),
  status: z.string(),
  verifiedAt: z.string(),
  revokedAt: z.string().nullable(),
  latestBindingAttemptId: z.string().nullable(),
  failureReason: z.string(),
  createdAt: z.string(),
  updatedAt: z.string(),
})

export type AdminPayoutIdentity = z.infer<typeof AdminPayoutIdentitySchema>

export const AdminPayoutProviderEventSchema = z.object({
  eventId: z.string(),
  withdrawalId: z.string(),
  eventType: z.string(),
  provider: z.string(),
  providerEventId: z.string(),
  outBillNo: z.string(),
  transferBillNo: z.string().nullable(),
  providerState: z.string(),
  mappedStatus: z.string(),
  rawPayloadJson: z.string(),
  signatureVerified: z.boolean(),
  createdAt: z.string(),
})

export type AdminPayoutProviderEvent = z.infer<typeof AdminPayoutProviderEventSchema>

export const AdminReconciliationWarningSchema = z.object({
  warningId: z.string(),
  withdrawalId: z.string(),
  severity: z.string(),
  reasonCode: z.string(),
  message: z.string(),
  status: z.string(),
  createdAt: z.string(),
  resolvedAt: z.string().nullable(),
})

export type AdminReconciliationWarning = z.infer<typeof AdminReconciliationWarningSchema>

export const AdminWithdrawalSyncSchema = z.object({
  withdrawalId: z.string(),
  previousStatus: z.string(),
  currentStatus: z.string(),
  providerState: z.string(),
  action: z.string(),
  withdrawal: AdminMembershipWithdrawalSchema,
})

export type AdminWithdrawalSync = z.infer<typeof AdminWithdrawalSyncSchema>

export const AdminMembershipOrderOperationsSchema = z.object({
  hasPaymentRecord: z.boolean(),
  canSyncPayment: z.boolean(),
  canCloseOrder: z.boolean(),
  canRequestRefund: z.boolean(),
  canSyncRefund: z.boolean(),
})

export type AdminMembershipOrderOperations = z.infer<typeof AdminMembershipOrderOperationsSchema>

export const AdminMembershipOrderInviteSchema = z.object({
  binding: AdminMembershipInviteSchema,
  rewardTriggeredByThisOrder: z.boolean(),
  rewardCoupon: AdminMembershipCouponSchema.nullable(),
  discountCoupon: AdminMembershipCouponSchema.nullable(),
  commission: z
    .object({
      commissionId: z.string(),
      commissionAmountCent: z.number(),
      status: z.string(),
      refundWindowEndsAt: z.string(),
    })
    .nullable(),
})

export type AdminMembershipOrderInvite = z.infer<typeof AdminMembershipOrderInviteSchema>

export const AdminMembershipOrderDetailSchema = z.object({
  order: AdminMembershipOrderSchema,
  membership: AdminMembershipSummarySchema,
  payment: AdminMembershipPaymentSchema.nullable(),
  coupon: AdminMembershipCouponSchema.nullable(),
  invite: AdminMembershipOrderInviteSchema.nullable(),
  operations: AdminMembershipOrderOperationsSchema,
})

export type AdminMembershipOrderDetail = z.infer<typeof AdminMembershipOrderDetailSchema>

export const AdminMembershipRemotePaymentSchema = z.object({
  provider: z.string(),
  orderId: z.string(),
  providerTradeNo: z.string(),
  remoteStatus: z.string(),
  paidAt: z.string().nullable(),
  amountCent: z.number().nullable(),
  payerId: z.string().nullable(),
})

export type AdminMembershipRemotePayment = z.infer<typeof AdminMembershipRemotePaymentSchema>

export const AdminMembershipRefundSchema = z.object({
  order: AdminMembershipOrderSchema,
  membership: AdminMembershipSummarySchema,
  idempotent: z.boolean(),
  restoredCouponId: z.string().nullable(),
  restoredCouponStatus: z.string().nullable(),
  revokedRewardCouponId: z.string().nullable(),
  completed: z.boolean(),
  refundRequestSubmitted: z.boolean(),
  remoteStatus: z.string().nullable(),
  providerRefundNo: z.string().nullable(),
})

export type AdminMembershipRefund = z.infer<typeof AdminMembershipRefundSchema>

export const AdminMembershipSyncPaymentSchema = z.object({
  confirmed: z.boolean(),
  idempotent: z.boolean(),
  order: AdminMembershipOrderSchema,
  membership: AdminMembershipSummarySchema,
  payment: AdminMembershipPaymentSchema.nullable(),
  remote: AdminMembershipRemotePaymentSchema,
  operations: AdminMembershipOrderOperationsSchema,
})

export type AdminMembershipSyncPayment = z.infer<typeof AdminMembershipSyncPaymentSchema>

export const AdminMembershipCloseOrderSchema = z.object({
  order: AdminMembershipOrderSchema,
  membership: AdminMembershipSummarySchema,
  payment: AdminMembershipPaymentSchema.nullable(),
  operations: AdminMembershipOrderOperationsSchema,
  idempotent: z.boolean(),
})

export type AdminMembershipCloseOrder = z.infer<typeof AdminMembershipCloseOrderSchema>

const AdminUserListSchema = z.array(AdminUserSchema)
const AdminActionLogListSchema = z.array(AdminActionLogSchema)
const AdminMembershipOrderListSchema = z.array(AdminMembershipOrderSchema)
const AdminMembershipInviteListSchema = z.array(AdminMembershipInviteSchema)
const AdminMembershipCouponListSchema = z.array(AdminMembershipCouponSchema)
const AdminMembershipCommissionListSchema = z.array(AdminMembershipCommissionSchema)
const AdminMembershipWithdrawalListSchema = z.array(AdminMembershipWithdrawalSchema)
const AdminPayoutIdentityListSchema = z.array(AdminPayoutIdentitySchema)
const AdminPayoutProviderEventListSchema = z.array(AdminPayoutProviderEventSchema)
const AdminReconciliationWarningListSchema = z.array(AdminReconciliationWarningSchema)

function buildAdminListPath(path: string, params?: { search?: string; status?: string; role?: string; limit?: number }) {
  const query = new URLSearchParams()
  if (params?.search) query.set("search", params.search)
  if (params?.status) query.set("status", params.status)
  if (params?.role) query.set("role", params.role)
  if (typeof params?.limit === "number") query.set("limit", String(params.limit))
  const text = query.toString()
  return text ? `${path}?${text}` : path
}

export function getAdminOverview() {
  return apiRequest({
    path: "/admin/overview",
    responseSchema: AdminOverviewSchema,
  })
}

export function listAdminActionLogs(params?: { limit?: number }) {
  return apiRequest({
    path: buildAdminListPath("/admin/audit-logs", params),
    responseSchema: AdminActionLogListSchema,
  })
}

export function listAdminUsers(params?: { search?: string; status?: string; role?: string; limit?: number }) {
  return apiRequest({
    path: buildAdminListPath("/admin/users", params),
    responseSchema: AdminUserListSchema,
  })
}

export function getAdminUserDetail(userId: string) {
  return apiRequest({
    path: `/admin/users/${encodeURIComponent(userId)}`,
    responseSchema: AdminUserDetailSchema,
  })
}

export function updateAdminUserStatus(params: { userId: string; status: string }) {
  return apiRequest({
    path: `/admin/users/${encodeURIComponent(params.userId)}/status`,
    method: "PATCH",
    body: { status: params.status },
    responseSchema: AdminUserSchema,
  })
}

export function updateAdminUserRole(params: { userId: string; role: string; enabled: boolean }) {
  return apiRequest({
    path: `/admin/users/${encodeURIComponent(params.userId)}/roles`,
    method: "PATCH",
    body: {
      role: params.role,
      enabled: params.enabled,
    },
    responseSchema: AdminUserSchema,
  })
}

export function getAdminMembershipOverview() {
  return apiRequest({
    path: "/admin/membership/overview",
    responseSchema: AdminMembershipOverviewSchema,
  })
}

export function listAdminMembershipOrders(params?: { userSearch?: string; status?: string; orderType?: string; provider?: string; limit?: number }) {
  const query = new URLSearchParams()
  if (params?.userSearch) query.set("userSearch", params.userSearch)
  if (params?.status) query.set("status", params.status)
  if (params?.orderType) query.set("orderType", params.orderType)
  if (params?.provider) query.set("provider", params.provider)
  if (typeof params?.limit === "number") query.set("limit", String(params.limit))
  const suffix = query.toString()
  return apiRequest({
    path: suffix ? `/admin/membership/orders?${suffix}` : "/admin/membership/orders",
    responseSchema: AdminMembershipOrderListSchema,
  })
}

export function getAdminMembershipOrderDetail(orderId: string) {
  return apiRequest({
    path: `/admin/membership/orders/${encodeURIComponent(orderId)}`,
    responseSchema: AdminMembershipOrderDetailSchema,
  })
}

export function listAdminMembershipInvites(params?: { search?: string; status?: string; limit?: number }) {
  return apiRequest({
    path: buildAdminListPath("/admin/membership/invites", params),
    responseSchema: AdminMembershipInviteListSchema,
  })
}

export function listAdminMembershipCoupons(params?: { search?: string; status?: string; limit?: number }) {
  return apiRequest({
    path: buildAdminListPath("/admin/membership/coupons", params),
    responseSchema: AdminMembershipCouponListSchema,
  })
}

export function listAdminMembershipCommissions(params?: { search?: string; status?: string; limit?: number }) {
  return apiRequest({
    path: buildAdminListPath("/admin/membership/commissions", params),
    responseSchema: AdminMembershipCommissionListSchema,
  })
}

export function settleAdminMembershipCommissions() {
  return apiRequest({
    path: "/admin/membership/commissions/settle",
    method: "POST",
    responseSchema: AdminCommissionSettlementSchema,
  })
}

export function listAdminMembershipWithdrawals(params?: { search?: string; status?: string; limit?: number }) {
  return apiRequest({
    path: buildAdminListPath("/admin/membership/withdrawals", params),
    responseSchema: AdminMembershipWithdrawalListSchema,
  })
}

export function listAdminPayoutIdentities(params?: { search?: string; status?: string; limit?: number }) {
  return apiRequest({
    path: buildAdminListPath("/admin/membership/payout-identities", params),
    responseSchema: AdminPayoutIdentityListSchema,
  })
}

export function listAdminWithdrawalEvents(params?: { withdrawalId?: string; limit?: number }) {
  const query = new URLSearchParams()
  if (params?.withdrawalId) query.set("withdrawalId", params.withdrawalId)
  if (typeof params?.limit === "number") query.set("limit", String(params.limit))
  const suffix = query.toString()
  return apiRequest({
    path: suffix ? `/admin/membership/withdrawals/events?${suffix}` : "/admin/membership/withdrawals/events",
    responseSchema: AdminPayoutProviderEventListSchema,
  })
}

export function listAdminWithdrawalWarnings(params?: { status?: string; limit?: number }) {
  return apiRequest({
    path: buildAdminListPath("/admin/membership/withdrawals/warnings", params),
    responseSchema: AdminReconciliationWarningListSchema,
  })
}

export function acknowledgeAdminWithdrawalWarning(params: { warningId: string }) {
  return apiRequest({
    path: `/admin/membership/withdrawals/warnings/${encodeURIComponent(params.warningId)}/ack`,
    method: "POST",
    body: {},
    responseSchema: AdminReconciliationWarningSchema,
  })
}

export function syncAdminMembershipWithdrawal(params: { withdrawalId: string }) {
  return apiRequest({
    path: `/admin/membership/withdrawals/${encodeURIComponent(params.withdrawalId)}/sync`,
    method: "POST",
    body: {},
    responseSchema: AdminWithdrawalSyncSchema,
  })
}

export function resolveAdminMembershipWithdrawal(params: {
  withdrawalId: string
  status: "succeeded" | "failed"
  providerTransferNo?: string
  failureReason?: string
}) {
  return apiRequest({
    path: `/admin/membership/withdrawals/${encodeURIComponent(params.withdrawalId)}/resolve`,
    method: "POST",
    body: {
      status: params.status,
      providerTransferNo: params.providerTransferNo,
      failureReason: params.failureReason ?? "",
    },
    responseSchema: AdminMembershipWithdrawalSchema,
  })
}

export function grantAdminMembershipCoupon(params: {
  userId: string
  amountCent: number
  title: string
  expiresInDays: number
  minSpendCent?: number
}) {
  return apiRequest({
    path: "/admin/membership/coupons/grant",
    method: "POST",
    body: {
      userId: params.userId,
      amountCent: params.amountCent,
      title: params.title,
      expiresInDays: params.expiresInDays,
      minSpendCent: params.minSpendCent ?? 0,
    },
    responseSchema: AdminMembershipCouponSchema,
  })
}

export function grantAdminMembershipMonths(params: { userId: string; months: number }) {
  return apiRequest({
    path: "/admin/membership/grants",
    method: "POST",
    body: {
      userId: params.userId,
      months: params.months,
    },
    responseSchema: AdminMembershipGrantSchema,
  })
}

export function voidAdminMembershipCoupon(params: { couponId: string; reason?: string }) {
  return apiRequest({
    path: `/admin/membership/coupons/${encodeURIComponent(params.couponId)}/void`,
    method: "POST",
    body: { reason: params.reason ?? "" },
    responseSchema: AdminMembershipCouponSchema,
  })
}

export function refundAdminMembershipOrder(params: { orderId: string; reason?: string }) {
  return apiRequest({
    path: `/admin/membership/orders/${encodeURIComponent(params.orderId)}/refund`,
    method: "POST",
    body: { reason: params.reason ?? "" },
    responseSchema: AdminMembershipRefundSchema,
  })
}

export function syncAdminMembershipOrderPayment(params: { orderId: string }) {
  return apiRequest({
    path: `/admin/membership/orders/${encodeURIComponent(params.orderId)}/sync-payment`,
    method: "POST",
    responseSchema: AdminMembershipSyncPaymentSchema,
  })
}

export function closeAdminMembershipOrder(params: { orderId: string }) {
  return apiRequest({
    path: `/admin/membership/orders/${encodeURIComponent(params.orderId)}/close`,
    method: "POST",
    responseSchema: AdminMembershipCloseOrderSchema,
  })
}

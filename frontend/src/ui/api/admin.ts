import { z } from "zod"

import { apiRequest } from "@/ui/api/http"
import {
  StudyGroupJoinRequestSchema,
  StudyGroupMemberSchema,
  StudyGroupPostCommentSchema,
  StudyGroupPostSchema,
  StudyGroupSchema,
} from "@/ui/api/studyGroups"

export const AdminOverviewSchema = z.object({
  users: z.number(),
  activeUsers: z.number(),
  groups: z.number(),
  activeGroups: z.number(),
  posts: z.number(),
  comments: z.number(),
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

export const AdminUserStudyGroupSchema = z.object({
  groupId: z.string(),
  name: z.string(),
  description: z.string(),
  visibility: z.string(),
  joinPolicy: z.string(),
  status: z.string(),
  ownerUserId: z.string(),
  ownerPublicUid: z.string(),
  ownerNickname: z.string(),
  avatarUrl: z.string().nullable(),
  createdAt: z.string(),
  updatedAt: z.string(),
  memberCount: z.number(),
  memberRole: z.string(),
  joinedAt: z.string(),
})

export type AdminUserStudyGroup = z.infer<typeof AdminUserStudyGroupSchema>

export const AdminUserDetailSchema = AdminUserSchema.extend({
  groups: z.array(AdminUserStudyGroupSchema),
})

export type AdminUserDetail = z.infer<typeof AdminUserDetailSchema>

export const AdminGroupDetailSchema = StudyGroupSchema.extend({
  members: z.array(StudyGroupMemberSchema),
  joinRequests: z.array(StudyGroupJoinRequestSchema),
  posts: z.array(StudyGroupPostSchema),
  comments: z.array(StudyGroupPostCommentSchema),
})

export type AdminGroupDetail = z.infer<typeof AdminGroupDetailSchema>

export const AdminGroupPostSchema = z.object({
  postId: z.string(),
  groupId: z.string(),
  groupName: z.string(),
  authorUserId: z.string(),
  authorPublicUid: z.string(),
  authorNickname: z.string(),
  authorAvatarUrl: z.string().nullable(),
  kind: z.string(),
  content: z.string(),
  createdAt: z.string(),
  updatedAt: z.string(),
  commentCount: z.number(),
})

export type AdminGroupPost = z.infer<typeof AdminGroupPostSchema>

export const AdminGroupCommentSchema = z.object({
  commentId: z.string(),
  groupId: z.string(),
  groupName: z.string(),
  postId: z.string(),
  postKind: z.string(),
  postExcerpt: z.string(),
  authorUserId: z.string(),
  authorPublicUid: z.string(),
  authorNickname: z.string(),
  authorAvatarUrl: z.string().nullable(),
  content: z.string(),
  createdAt: z.string(),
  updatedAt: z.string(),
})

export type AdminGroupComment = z.infer<typeof AdminGroupCommentSchema>

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

export const AdminMembershipInviteSchema = z.object({
  invitee: AdminMembershipUserRefSchema,
  inviter: AdminMembershipUserRefSchema,
  inviteCode: z.string(),
  status: z.string(),
  boundAt: z.string(),
  rewardedAt: z.string().nullable(),
  rewardTriggerOrderId: z.string().nullable(),
  rewardCouponId: z.string().nullable(),
})

export type AdminMembershipInvite = z.infer<typeof AdminMembershipInviteSchema>

export const AdminMembershipCouponSchema = z.object({
  couponId: z.string(),
  user: AdminMembershipUserRefSchema,
  title: z.string(),
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
const AdminGroupListSchema = z.array(StudyGroupSchema)
const AdminGroupPostListSchema = z.array(AdminGroupPostSchema)
const AdminGroupCommentListSchema = z.array(AdminGroupCommentSchema)
const AdminActionLogListSchema = z.array(AdminActionLogSchema)
const AdminMembershipOrderListSchema = z.array(AdminMembershipOrderSchema)
const AdminMembershipInviteListSchema = z.array(AdminMembershipInviteSchema)
const AdminMembershipCouponListSchema = z.array(AdminMembershipCouponSchema)

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

export function listAdminGroups(params?: { search?: string; status?: string; limit?: number }) {
  return apiRequest({
    path: buildAdminListPath("/admin/groups", params),
    responseSchema: AdminGroupListSchema,
  })
}

export function getAdminGroupDetail(groupId: string) {
  return apiRequest({
    path: `/admin/groups/${encodeURIComponent(groupId)}`,
    responseSchema: AdminGroupDetailSchema,
  })
}

export function updateAdminGroupStatus(params: { groupId: string; status: string }) {
  return apiRequest({
    path: `/admin/groups/${encodeURIComponent(params.groupId)}/status`,
    method: "PATCH",
    body: { status: params.status },
    responseSchema: StudyGroupSchema,
  })
}

export function listAdminGroupPosts(params?: { search?: string; limit?: number }) {
  return apiRequest({
    path: buildAdminListPath("/admin/content/posts", params),
    responseSchema: AdminGroupPostListSchema,
  })
}

export function listAdminGroupComments(params?: { search?: string; limit?: number }) {
  return apiRequest({
    path: buildAdminListPath("/admin/content/comments", params),
    responseSchema: AdminGroupCommentListSchema,
  })
}

export function deleteAdminGroupPost(postId: string) {
  return apiRequest({
    path: `/admin/content/posts/${encodeURIComponent(postId)}`,
    method: "DELETE",
    responseSchema: AdminGroupPostSchema,
  })
}

export function deleteAdminGroupComment(commentId: string) {
  return apiRequest({
    path: `/admin/content/comments/${encodeURIComponent(commentId)}`,
    method: "DELETE",
    responseSchema: AdminGroupCommentSchema,
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

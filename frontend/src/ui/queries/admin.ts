import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  closeAdminMembershipOrder,
  getAdminMembershipOrderDetail,
  getAdminMembershipOverview,
  getAdminUserDetail,
  getAdminOverview,
  grantAdminMembershipCoupon,
  refundAdminMembershipOrder,
  listAdminActionLogs,
  listAdminMembershipCoupons,
  listAdminMembershipInvites,
  listAdminMembershipOrders,
  listAdminUsers,
  syncAdminMembershipOrderPayment,
  updateAdminUserRole,
  updateAdminUserStatus,
  voidAdminMembershipCoupon,
} from "@/ui/api/admin"

export function useAdminOverview(enabled = true) {
  return useQuery({
    queryKey: ["admin", "overview"],
    queryFn: getAdminOverview,
    enabled,
    staleTime: 15_000,
  })
}

export function useAdminActionLogs(params?: { limit?: number }, enabled = true) {
  return useQuery({
    queryKey: ["admin", "activity", params?.limit ?? 50],
    queryFn: () => listAdminActionLogs(params),
    enabled,
  })
}

export function useAdminMembershipOverview(enabled = true) {
  return useQuery({
    queryKey: ["admin", "membership", "overview"],
    queryFn: getAdminMembershipOverview,
    enabled,
    staleTime: 15_000,
  })
}

export function useAdminMembershipOrders(
  params?: { userSearch?: string; status?: string; orderType?: string; provider?: string; limit?: number },
  enabled = true,
) {
  return useQuery({
    queryKey: [
      "admin",
      "membership",
      "orders",
      params?.userSearch ?? "",
      params?.status ?? "",
      params?.orderType ?? "",
      params?.provider ?? "",
      params?.limit ?? 100,
    ],
    queryFn: () => listAdminMembershipOrders(params),
    enabled,
  })
}

export function useAdminMembershipOrderDetail(orderId: string, enabled = true) {
  return useQuery({
    queryKey: ["admin", "membership", "order-detail", orderId],
    queryFn: () => getAdminMembershipOrderDetail(orderId),
    enabled: enabled && Boolean(orderId),
  })
}

export function useAdminMembershipInvites(params?: { search?: string; status?: string; limit?: number }, enabled = true) {
  return useQuery({
    queryKey: ["admin", "membership", "invites", params?.search ?? "", params?.status ?? "", params?.limit ?? 100],
    queryFn: () => listAdminMembershipInvites(params),
    enabled,
  })
}

export function useAdminMembershipCoupons(params?: { search?: string; status?: string; limit?: number }, enabled = true) {
  return useQuery({
    queryKey: ["admin", "membership", "coupons", params?.search ?? "", params?.status ?? "", params?.limit ?? 100],
    queryFn: () => listAdminMembershipCoupons(params),
    enabled,
  })
}

export function useAdminUsers(params?: { search?: string; status?: string; role?: string; limit?: number }, enabled = true) {
  return useQuery({
    queryKey: ["admin", "users", params?.search ?? "", params?.status ?? "", params?.role ?? "", params?.limit ?? 100],
    queryFn: () => listAdminUsers(params),
    enabled,
  })
}

export function useAdminUserDetail(userId: string, enabled = true) {
  return useQuery({
    queryKey: ["admin", "user-detail", userId],
    queryFn: () => getAdminUserDetail(userId),
    enabled: enabled && Boolean(userId),
  })
}

export function useUpdateAdminUserStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: updateAdminUserStatus,
    onSuccess: async (_data, variables) => {
      await qc.invalidateQueries({ queryKey: ["admin", "overview"] })
      await qc.invalidateQueries({ queryKey: ["admin", "users"] })
      await qc.invalidateQueries({ queryKey: ["admin", "user-detail", variables.userId] })
      await qc.invalidateQueries({ queryKey: ["admin", "activity"] })
      await qc.invalidateQueries({ queryKey: ["auth", "me"] })
    },
  })
}

export function useUpdateAdminUserRole() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: updateAdminUserRole,
    onSuccess: async (_data, variables) => {
      await qc.invalidateQueries({ queryKey: ["admin", "users"] })
      await qc.invalidateQueries({ queryKey: ["admin", "user-detail", variables.userId] })
      await qc.invalidateQueries({ queryKey: ["admin", "activity"] })
      await qc.invalidateQueries({ queryKey: ["auth", "me"] })
    },
  })
}

export function useGrantAdminMembershipCoupon() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: grantAdminMembershipCoupon,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["admin", "membership", "overview"] })
      await qc.invalidateQueries({ queryKey: ["admin", "membership", "coupons"] })
      await qc.invalidateQueries({ queryKey: ["admin", "activity"] })
    },
  })
}

export function useVoidAdminMembershipCoupon() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: voidAdminMembershipCoupon,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["admin", "membership", "overview"] })
      await qc.invalidateQueries({ queryKey: ["admin", "membership", "coupons"] })
      await qc.invalidateQueries({ queryKey: ["admin", "activity"] })
    },
  })
}

export function useSyncAdminMembershipOrderPayment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: syncAdminMembershipOrderPayment,
    onSuccess: async (_data, variables) => {
      await qc.invalidateQueries({ queryKey: ["admin", "membership", "overview"] })
      await qc.invalidateQueries({ queryKey: ["admin", "membership", "orders"] })
      await qc.invalidateQueries({ queryKey: ["admin", "membership", "order-detail", variables.orderId] })
      await qc.invalidateQueries({ queryKey: ["admin", "activity"] })
      await qc.invalidateQueries({ queryKey: ["membership"] })
    },
  })
}

export function useCloseAdminMembershipOrder() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: closeAdminMembershipOrder,
    onSuccess: async (_data, variables) => {
      await qc.invalidateQueries({ queryKey: ["admin", "membership", "overview"] })
      await qc.invalidateQueries({ queryKey: ["admin", "membership", "orders"] })
      await qc.invalidateQueries({ queryKey: ["admin", "membership", "order-detail", variables.orderId] })
      await qc.invalidateQueries({ queryKey: ["admin", "activity"] })
      await qc.invalidateQueries({ queryKey: ["membership"] })
    },
  })
}

export function useRefundAdminMembershipOrder() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: refundAdminMembershipOrder,
    onSuccess: async (_data, variables) => {
      await qc.invalidateQueries({ queryKey: ["admin", "membership", "overview"] })
      await qc.invalidateQueries({ queryKey: ["admin", "membership", "orders"] })
      await qc.invalidateQueries({ queryKey: ["admin", "membership", "order-detail", variables.orderId] })
      await qc.invalidateQueries({ queryKey: ["admin", "membership", "invites"] })
      await qc.invalidateQueries({ queryKey: ["admin", "membership", "coupons"] })
      await qc.invalidateQueries({ queryKey: ["admin", "activity"] })
      await qc.invalidateQueries({ queryKey: ["membership"] })
    },
  })
}

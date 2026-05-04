import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  bindInviteCode,
  closeMembershipOrder,
  confirmMembershipPayment,
  createMembershipOrder,
  getCommissionSummary,
  getInviteSummary,
  getMembershipSummary,
  listCommissionWithdrawals,
  listCoupons,
  listMembershipOrders,
  previewMembershipOrder,
  requestCommissionWithdrawal,
  syncMembershipPayment,
} from "@/ui/api/membership"

export function useMembershipSummary(enabled = true, refetchInterval: number | false = false) {
  return useQuery({
    queryKey: ["membership", "summary"],
    queryFn: getMembershipSummary,
    enabled,
    staleTime: 15_000,
    refetchInterval,
  })
}

export function useMembershipOrders(limit = 20, enabled = true, refetchInterval: number | false = false) {
  return useQuery({
    queryKey: ["membership", "orders", limit],
    queryFn: () => listMembershipOrders(limit),
    enabled,
    staleTime: 10_000,
    refetchInterval,
  })
}

export function useMembershipOrderPreview(couponId?: string | null, enabled = true) {
  return useQuery({
    queryKey: ["membership", "preview", couponId ?? null],
    queryFn: () => previewMembershipOrder({ couponId }),
    enabled,
    staleTime: 10_000,
  })
}

export function useCreateMembershipOrder() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createMembershipOrder,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["membership", "summary"] })
      await qc.invalidateQueries({ queryKey: ["membership", "orders"] })
      await qc.invalidateQueries({ queryKey: ["membership", "preview"] })
      await qc.invalidateQueries({ queryKey: ["membership", "coupons"] })
    },
  })
}

export function useConfirmMembershipPayment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: confirmMembershipPayment,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["membership", "summary"] })
      await qc.invalidateQueries({ queryKey: ["membership", "orders"] })
      await qc.invalidateQueries({ queryKey: ["membership", "preview"] })
      await qc.invalidateQueries({ queryKey: ["membership", "invites"] })
      await qc.invalidateQueries({ queryKey: ["membership", "coupons"] })
      await qc.invalidateQueries({ queryKey: ["membership", "commissions"] })
    },
  })
}

export function useSyncMembershipPayment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: syncMembershipPayment,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["membership", "summary"] })
      await qc.invalidateQueries({ queryKey: ["membership", "orders"] })
      await qc.invalidateQueries({ queryKey: ["membership", "preview"] })
      await qc.invalidateQueries({ queryKey: ["membership", "invites"] })
      await qc.invalidateQueries({ queryKey: ["membership", "coupons"] })
      await qc.invalidateQueries({ queryKey: ["membership", "commissions"] })
    },
  })
}

export function useCloseMembershipOrder() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: closeMembershipOrder,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["membership", "summary"] })
      await qc.invalidateQueries({ queryKey: ["membership", "orders"] })
      await qc.invalidateQueries({ queryKey: ["membership", "preview"] })
      await qc.invalidateQueries({ queryKey: ["membership", "invites"] })
      await qc.invalidateQueries({ queryKey: ["membership", "coupons"] })
    },
  })
}

export function useInviteSummary(enabled = true) {
  return useQuery({
    queryKey: ["membership", "invites"],
    queryFn: getInviteSummary,
    enabled,
    staleTime: 15_000,
  })
}

export function useCommissionSummary(limit = 20, enabled = true) {
  return useQuery({
    queryKey: ["membership", "commissions", limit],
    queryFn: () => getCommissionSummary(limit),
    enabled,
    staleTime: 10_000,
  })
}

export function useCommissionWithdrawals(limit = 20, enabled = true) {
  return useQuery({
    queryKey: ["membership", "withdrawals", limit],
    queryFn: () => listCommissionWithdrawals(limit),
    enabled,
    staleTime: 10_000,
  })
}

export function useMembershipCoupons(limit = 20, enabled = true) {
  return useQuery({
    queryKey: ["membership", "coupons", limit],
    queryFn: () => listCoupons(limit),
    enabled,
    staleTime: 10_000,
  })
}

export function useBindInviteCode() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: bindInviteCode,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["membership", "invites"] })
      await qc.invalidateQueries({ queryKey: ["membership", "coupons"] })
    },
  })
}

export function useRequestCommissionWithdrawal() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: requestCommissionWithdrawal,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["membership", "commissions"] })
      await qc.invalidateQueries({ queryKey: ["membership", "withdrawals"] })
      await qc.invalidateQueries({ queryKey: ["membership", "invites"] })
    },
  })
}

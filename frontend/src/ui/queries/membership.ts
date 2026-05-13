import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  bindInviteCode,
  closeMembershipOrder,
  completeWithdrawalConfirmationAttempt,
  confirmMembershipPayment,
  createMembershipOrder,
  getCommissionSummary,
  getCommissionWithdrawalWechatConfirmation,
  getInviteSummary,
  getMembershipSummary,
  getPayoutIdentity,
  listCommissionWithdrawals,
  listCoupons,
  listMembershipOrders,
  markCommissionWithdrawalWechatConfirmationStarted,
  openMobileWithdrawalConfirmation,
  pollWithdrawalConfirmationAttempt,
  previewMembershipOrder,
  requestCommissionWithdrawal,
  startWithdrawalConfirmationAttempt,
  syncMembershipPayment,
  type CommissionWithdrawal,
  type WithdrawalConfirmationAttempt,
} from "@/ui/api/membership"

type QueryRefetchInterval<T> =
  | number
  | false
  | ((query: { state: { data?: T } }) => number | false | undefined)

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

export function useMembershipOrderPreview(couponId?: string | null, planId?: string | null, enabled = true) {
  return useQuery({
    queryKey: ["membership", "preview", couponId ?? null, planId ?? null],
    queryFn: () => previewMembershipOrder({ couponId, planId }),
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

export function usePayoutIdentity(enabled = true) {
  return useQuery({
    queryKey: ["membership", "payout-identity"],
    queryFn: getPayoutIdentity,
    enabled,
    staleTime: 10_000,
  })
}

export function useCommissionWithdrawals(limit = 20, enabled = true, refetchInterval: QueryRefetchInterval<CommissionWithdrawal[]> = false) {
  return useQuery({
    queryKey: ["membership", "withdrawals", limit],
    queryFn: () => listCommissionWithdrawals(limit),
    enabled,
    staleTime: 10_000,
    refetchInterval,
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

export function useCommissionWithdrawalWechatConfirmation() {
  return useMutation({
    mutationFn: getCommissionWithdrawalWechatConfirmation,
  })
}

export function useMarkCommissionWithdrawalWechatConfirmationStarted() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: markCommissionWithdrawalWechatConfirmationStarted,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["membership", "withdrawals"] })
      await qc.invalidateQueries({ queryKey: ["membership", "commissions"] })
    },
  })
}

export function useWithdrawalConfirmationAttempt(withdrawalConfirmationAttemptId: string, enabled = true, refetchInterval: QueryRefetchInterval<WithdrawalConfirmationAttempt> = false) {
  return useQuery({
    queryKey: ["membership", "withdrawal-confirmation-attempt", withdrawalConfirmationAttemptId],
    queryFn: () => pollWithdrawalConfirmationAttempt({ withdrawalConfirmationAttemptId }),
    enabled: enabled && Boolean(withdrawalConfirmationAttemptId),
    staleTime: 0,
    refetchInterval,
  })
}

export function useOpenMobileWithdrawalConfirmation() {
  return useMutation({
    mutationFn: openMobileWithdrawalConfirmation,
  })
}

export function useStartWithdrawalConfirmationAttempt() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: startWithdrawalConfirmationAttempt,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["membership", "payout-identity"] })
      await qc.invalidateQueries({ queryKey: ["membership", "commissions"] })
    },
  })
}

export function useCompleteWithdrawalConfirmationAttempt() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: completeWithdrawalConfirmationAttempt,
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["membership", "payout-identity"] })
      await qc.invalidateQueries({ queryKey: ["membership", "withdrawal-confirmation-attempt"] })
      await qc.invalidateQueries({ queryKey: ["membership", "commissions"] })
      await qc.invalidateQueries({ queryKey: ["membership", "withdrawals"] })
    },
  })
}

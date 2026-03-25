import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  deleteAdminGroupComment,
  deleteAdminGroupPost,
  getAdminGroupDetail,
  getAdminUserDetail,
  getAdminOverview,
  listAdminActionLogs,
  listAdminGroupComments,
  listAdminGroupPosts,
  listAdminGroups,
  listAdminUsers,
  updateAdminGroupStatus,
  updateAdminUserRole,
  updateAdminUserStatus,
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

export function useAdminGroups(params?: { search?: string; status?: string; limit?: number }, enabled = true) {
  return useQuery({
    queryKey: ["admin", "groups", params?.search ?? "", params?.status ?? "", params?.limit ?? 100],
    queryFn: () => listAdminGroups(params),
    enabled,
  })
}

export function useAdminGroupDetail(groupId: string, enabled = true) {
  return useQuery({
    queryKey: ["admin", "group-detail", groupId],
    queryFn: () => getAdminGroupDetail(groupId),
    enabled: enabled && Boolean(groupId),
  })
}

export function useAdminGroupPosts(params?: { search?: string; limit?: number }, enabled = true) {
  return useQuery({
    queryKey: ["admin", "content", "posts", params?.search ?? "", params?.limit ?? 100],
    queryFn: () => listAdminGroupPosts(params),
    enabled,
  })
}

export function useAdminGroupComments(params?: { search?: string; limit?: number }, enabled = true) {
  return useQuery({
    queryKey: ["admin", "content", "comments", params?.search ?? "", params?.limit ?? 100],
    queryFn: () => listAdminGroupComments(params),
    enabled,
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

export function useUpdateAdminGroupStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: updateAdminGroupStatus,
    onSuccess: async (group) => {
      await qc.invalidateQueries({ queryKey: ["admin", "overview"] })
      await qc.invalidateQueries({ queryKey: ["admin", "groups"] })
      await qc.invalidateQueries({ queryKey: ["admin", "group-detail", group.groupId] })
      await qc.invalidateQueries({ queryKey: ["admin", "activity"] })
      await qc.invalidateQueries({ queryKey: ["study-groups", "list"] })
      await qc.invalidateQueries({ queryKey: ["study-groups", "detail", group.groupId] })
    },
  })
}

export function useDeleteAdminGroupPost() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteAdminGroupPost,
    onSuccess: async (post) => {
      await qc.invalidateQueries({ queryKey: ["admin", "overview"] })
      await qc.invalidateQueries({ queryKey: ["admin", "content", "posts"] })
      await qc.invalidateQueries({ queryKey: ["admin", "content", "comments"] })
      await qc.invalidateQueries({ queryKey: ["admin", "group-detail", post.groupId] })
      await qc.invalidateQueries({ queryKey: ["admin", "activity"] })
      await qc.invalidateQueries({ queryKey: ["study-groups", "detail", post.groupId] })
      await qc.invalidateQueries({ queryKey: ["study-groups", "posts", post.groupId] })
      await qc.invalidateQueries({ queryKey: ["study-groups", "comments", post.groupId] })
      await qc.invalidateQueries({ queryKey: ["study-groups", "list"] })
    },
  })
}

export function useDeleteAdminGroupComment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteAdminGroupComment,
    onSuccess: async (comment) => {
      await qc.invalidateQueries({ queryKey: ["admin", "overview"] })
      await qc.invalidateQueries({ queryKey: ["admin", "content", "comments"] })
      await qc.invalidateQueries({ queryKey: ["admin", "content", "posts"] })
      await qc.invalidateQueries({ queryKey: ["admin", "group-detail", comment.groupId] })
      await qc.invalidateQueries({ queryKey: ["admin", "activity"] })
      await qc.invalidateQueries({ queryKey: ["study-groups", "detail", comment.groupId] })
      await qc.invalidateQueries({ queryKey: ["study-groups", "comments", comment.groupId] })
      await qc.invalidateQueries({ queryKey: ["study-groups", "posts", comment.groupId] })
      await qc.invalidateQueries({ queryKey: ["study-groups", "list"] })
    },
  })
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  createStudyGroup,
  createStudyGroupJoinRequest,
  createStudyGroupPostComment,
  createStudyGroupPost,
  deleteStudyGroupPostComment,
  deleteStudyGroupPost,
  getStudyGroup,
  inviteStudyGroupMember,
  joinStudyGroup,
  leaveStudyGroup,
  listStudyGroupPostComments,
  listStudyGroupJoinRequests,
  listStudyGroupMembers,
  listStudyGroupPosts,
  listStudyGroups,
  removeStudyGroupMember,
  reviewStudyGroupJoinRequest,
  updateStudyGroupMemberRole,
  updateStudyGroup,
  uploadStudyGroupAvatar,
} from "@/ui/api/studyGroups"

async function invalidateStudyGroupQueries(qc: ReturnType<typeof useQueryClient>, groupId?: string) {
  await qc.invalidateQueries({ queryKey: ["study-groups", "list"] })
  await qc.invalidateQueries({ queryKey: ["admin", "groups"] })
  if (!groupId) return
  await qc.invalidateQueries({ queryKey: ["admin", "group-detail", groupId] })
  await qc.invalidateQueries({ queryKey: ["study-groups", "detail", groupId] })
  await qc.invalidateQueries({ queryKey: ["study-groups", "members", groupId] })
  await qc.invalidateQueries({ queryKey: ["study-groups", "join-requests", groupId] })
  await qc.invalidateQueries({ queryKey: ["study-groups", "posts", groupId] })
  await qc.invalidateQueries({ queryKey: ["study-groups", "comments", groupId] })
}

export function useStudyGroups(enabled = true) {
  return useQuery({
    queryKey: ["study-groups", "list"],
    queryFn: listStudyGroups,
    enabled,
    staleTime: 20_000,
  })
}

export function useStudyGroup(groupId?: string, enabled = true) {
  return useQuery({
    queryKey: ["study-groups", "detail", groupId],
    queryFn: () => getStudyGroup(String(groupId)),
    enabled: enabled && Boolean(groupId),
  })
}

export function useStudyGroupMembers(groupId?: string, enabled = true) {
  return useQuery({
    queryKey: ["study-groups", "members", groupId],
    queryFn: () => listStudyGroupMembers(String(groupId)),
    enabled: enabled && Boolean(groupId),
  })
}

export function useStudyGroupPosts(groupId?: string, enabled = true) {
  return useQuery({
    queryKey: ["study-groups", "posts", groupId],
    queryFn: () => listStudyGroupPosts(String(groupId)),
    enabled: enabled && Boolean(groupId),
  })
}

export function useStudyGroupComments(groupId?: string, enabled = true) {
  return useQuery({
    queryKey: ["study-groups", "comments", groupId],
    queryFn: () => listStudyGroupPostComments(String(groupId)),
    enabled: enabled && Boolean(groupId),
  })
}

export function useStudyGroupJoinRequests(groupId?: string, enabled = true) {
  return useQuery({
    queryKey: ["study-groups", "join-requests", groupId],
    queryFn: () => listStudyGroupJoinRequests(String(groupId)),
    enabled: enabled && Boolean(groupId),
  })
}

export function useCreateStudyGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createStudyGroup,
    onSuccess: async (group) => {
      await invalidateStudyGroupQueries(qc, group.groupId)
    },
  })
}

export function useUpdateStudyGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: updateStudyGroup,
    onSuccess: async (group) => {
      await invalidateStudyGroupQueries(qc, group.groupId)
    },
  })
}

export function useUploadStudyGroupAvatar() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: uploadStudyGroupAvatar,
    onSuccess: async (group) => {
      await invalidateStudyGroupQueries(qc, group.groupId)
    },
  })
}

export function useJoinStudyGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: joinStudyGroup,
    onSuccess: async (group) => {
      await invalidateStudyGroupQueries(qc, group.groupId)
    },
  })
}

export function useLeaveStudyGroup() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: leaveStudyGroup,
    onSuccess: async (_data, groupId) => {
      await invalidateStudyGroupQueries(qc, groupId)
    },
  })
}

export function useCreateStudyGroupJoinRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createStudyGroupJoinRequest,
    onSuccess: async (request) => {
      await invalidateStudyGroupQueries(qc, request.groupId)
    },
  })
}

export function useCreateStudyGroupPost() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createStudyGroupPost,
    onSuccess: async (post) => {
      await invalidateStudyGroupQueries(qc, post.groupId)
    },
  })
}

export function useCreateStudyGroupPostComment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createStudyGroupPostComment,
    onSuccess: async (comment) => {
      await invalidateStudyGroupQueries(qc, comment.groupId)
    },
  })
}

export function useDeleteStudyGroupPost() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteStudyGroupPost,
    onSuccess: async (post) => {
      await invalidateStudyGroupQueries(qc, post.groupId)
      await qc.invalidateQueries({ queryKey: ["admin", "overview"] })
      await qc.invalidateQueries({ queryKey: ["admin", "content", "posts"] })
      await qc.invalidateQueries({ queryKey: ["admin", "content", "comments"] })
    },
  })
}

export function useDeleteStudyGroupPostComment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteStudyGroupPostComment,
    onSuccess: async (comment) => {
      await invalidateStudyGroupQueries(qc, comment.groupId)
      await qc.invalidateQueries({ queryKey: ["admin", "overview"] })
      await qc.invalidateQueries({ queryKey: ["admin", "content", "posts"] })
      await qc.invalidateQueries({ queryKey: ["admin", "content", "comments"] })
    },
  })
}

export function useUpdateStudyGroupMemberRole() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: updateStudyGroupMemberRole,
    onSuccess: async (_member, params) => {
      await invalidateStudyGroupQueries(qc, params.groupId)
    },
  })
}

export function useRemoveStudyGroupMember() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: removeStudyGroupMember,
    onSuccess: async (_data, params) => {
      await invalidateStudyGroupQueries(qc, params.groupId)
    },
  })
}

export function useInviteStudyGroupMember() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: inviteStudyGroupMember,
    onSuccess: async (_member, params) => {
      await invalidateStudyGroupQueries(qc, params.groupId)
    },
  })
}

export function useReviewStudyGroupJoinRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: reviewStudyGroupJoinRequest,
    onSuccess: async (request) => {
      await invalidateStudyGroupQueries(qc, request.groupId)
    },
  })
}

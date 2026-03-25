import { z } from "zod"

import { apiRequest } from "@/ui/api/http"

export const StudyGroupSchema = z.object({
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
  memberRole: z.string().nullable(),
  joinRequestStatus: z.string().nullable(),
})

export type StudyGroup = z.infer<typeof StudyGroupSchema>

export const StudyGroupMemberSchema = z.object({
  userId: z.string(),
  publicUid: z.string(),
  nickname: z.string(),
  avatarUrl: z.string().nullable(),
  role: z.string(),
  joinedAt: z.string(),
})

export type StudyGroupMember = z.infer<typeof StudyGroupMemberSchema>

export const StudyGroupPostSchema = z.object({
  postId: z.string(),
  groupId: z.string(),
  authorUserId: z.string(),
  authorPublicUid: z.string(),
  authorNickname: z.string(),
  authorAvatarUrl: z.string().nullable(),
  kind: z.string(),
  content: z.string(),
  createdAt: z.string(),
  updatedAt: z.string(),
})

export type StudyGroupPost = z.infer<typeof StudyGroupPostSchema>

export const StudyGroupPostCommentSchema = z.object({
  commentId: z.string(),
  groupId: z.string(),
  postId: z.string(),
  authorUserId: z.string(),
  authorPublicUid: z.string(),
  authorNickname: z.string(),
  authorAvatarUrl: z.string().nullable(),
  content: z.string(),
  createdAt: z.string(),
  updatedAt: z.string(),
})

export type StudyGroupPostComment = z.infer<typeof StudyGroupPostCommentSchema>

export const StudyGroupJoinRequestSchema = z.object({
  requestId: z.string(),
  groupId: z.string(),
  requesterUserId: z.string(),
  requesterPublicUid: z.string(),
  requesterNickname: z.string(),
  requesterAvatarUrl: z.string().nullable(),
  message: z.string(),
  status: z.string(),
  createdAt: z.string(),
  reviewedAt: z.string().nullable(),
  reviewedByUserId: z.string().nullable(),
})

export type StudyGroupJoinRequest = z.infer<typeof StudyGroupJoinRequestSchema>

const StudyGroupListSchema = z.array(StudyGroupSchema)
const StudyGroupMemberListSchema = z.array(StudyGroupMemberSchema)
const StudyGroupPostListSchema = z.array(StudyGroupPostSchema)
const StudyGroupPostCommentListSchema = z.array(StudyGroupPostCommentSchema)
const StudyGroupJoinRequestListSchema = z.array(StudyGroupJoinRequestSchema)

export function listStudyGroups() {
  return apiRequest({
    path: "/study-groups",
    responseSchema: StudyGroupListSchema,
  })
}

export function createStudyGroup(params: {
  name: string
  description: string
  visibility: string
  joinPolicy: string
}) {
  return apiRequest({
    path: "/study-groups",
    method: "POST",
    body: params,
    responseSchema: StudyGroupSchema,
  })
}

export function getStudyGroup(groupId: string) {
  return apiRequest({
    path: `/study-groups/${encodeURIComponent(groupId)}`,
    responseSchema: StudyGroupSchema,
  })
}

export function updateStudyGroup(params: {
  groupId: string
  name: string
  description: string
  visibility: string
  joinPolicy: string
}) {
  return apiRequest({
    path: `/study-groups/${encodeURIComponent(params.groupId)}`,
    method: "PATCH",
    body: {
      name: params.name,
      description: params.description,
      visibility: params.visibility,
      joinPolicy: params.joinPolicy,
    },
    responseSchema: StudyGroupSchema,
  })
}

export function uploadStudyGroupAvatar(params: { groupId: string; file: File }) {
  return apiRequest({
    path: `/study-groups/${encodeURIComponent(params.groupId)}/avatar`,
    method: "PUT",
    body: params.file,
    headers: { "Content-Type": params.file.type || "application/octet-stream" },
    responseSchema: StudyGroupSchema,
  })
}

export function joinStudyGroup(groupId: string) {
  return apiRequest({
    path: `/study-groups/${encodeURIComponent(groupId)}/join`,
    method: "POST",
    responseSchema: StudyGroupSchema,
  })
}

export function leaveStudyGroup(groupId: string) {
  return apiRequest({
    path: `/study-groups/${encodeURIComponent(groupId)}/leave`,
    method: "POST",
    responseSchema: z.null(),
  })
}

export function listStudyGroupMembers(groupId: string) {
  return apiRequest({
    path: `/study-groups/${encodeURIComponent(groupId)}/members`,
    responseSchema: StudyGroupMemberListSchema,
  })
}

export function updateStudyGroupMemberRole(params: { groupId: string; userId: string; role: string }) {
  return apiRequest({
    path: `/study-groups/${encodeURIComponent(params.groupId)}/members/${encodeURIComponent(params.userId)}`,
    method: "PATCH",
    body: { role: params.role },
    responseSchema: StudyGroupMemberSchema,
  })
}

export function removeStudyGroupMember(params: { groupId: string; userId: string }) {
  return apiRequest({
    path: `/study-groups/${encodeURIComponent(params.groupId)}/members/${encodeURIComponent(params.userId)}`,
    method: "DELETE",
    responseSchema: z.null(),
  })
}

export function inviteStudyGroupMember(params: { groupId: string; publicUid: string; role: string }) {
  return apiRequest({
    path: `/study-groups/${encodeURIComponent(params.groupId)}/members/invite`,
    method: "POST",
    body: {
      publicUid: params.publicUid,
      role: params.role,
    },
    responseSchema: StudyGroupMemberSchema,
  })
}

export function listStudyGroupJoinRequests(groupId: string) {
  return apiRequest({
    path: `/study-groups/${encodeURIComponent(groupId)}/join-requests`,
    responseSchema: StudyGroupJoinRequestListSchema,
  })
}

export function createStudyGroupJoinRequest(params: { groupId: string; message: string }) {
  return apiRequest({
    path: `/study-groups/${encodeURIComponent(params.groupId)}/join-requests`,
    method: "POST",
    body: {
      message: params.message,
    },
    responseSchema: StudyGroupJoinRequestSchema,
  })
}

export function reviewStudyGroupJoinRequest(params: { groupId: string; requestId: string; status: string }) {
  return apiRequest({
    path: `/study-groups/${encodeURIComponent(params.groupId)}/join-requests/${encodeURIComponent(params.requestId)}`,
    method: "PATCH",
    body: {
      status: params.status,
    },
    responseSchema: StudyGroupJoinRequestSchema,
  })
}

export function listStudyGroupPosts(groupId: string) {
  return apiRequest({
    path: `/study-groups/${encodeURIComponent(groupId)}/posts`,
    responseSchema: StudyGroupPostListSchema,
  })
}

export function listStudyGroupPostComments(groupId: string) {
  return apiRequest({
    path: `/study-groups/${encodeURIComponent(groupId)}/comments`,
    responseSchema: StudyGroupPostCommentListSchema,
  })
}

export function createStudyGroupPost(params: {
  groupId: string
  kind: string
  content: string
}) {
  return apiRequest({
    path: `/study-groups/${encodeURIComponent(params.groupId)}/posts`,
    method: "POST",
    body: {
      kind: params.kind,
      content: params.content,
    },
    responseSchema: StudyGroupPostSchema,
  })
}

export function deleteStudyGroupPost(params: { groupId: string; postId: string }) {
  return apiRequest({
    path: `/study-groups/${encodeURIComponent(params.groupId)}/posts/${encodeURIComponent(params.postId)}`,
    method: "DELETE",
    responseSchema: StudyGroupPostSchema,
  })
}

export function createStudyGroupPostComment(params: {
  groupId: string
  postId: string
  content: string
}) {
  return apiRequest({
    path: `/study-groups/${encodeURIComponent(params.groupId)}/posts/${encodeURIComponent(params.postId)}/comments`,
    method: "POST",
    body: {
      content: params.content,
    },
    responseSchema: StudyGroupPostCommentSchema,
  })
}

export function deleteStudyGroupPostComment(params: { groupId: string; commentId: string }) {
  return apiRequest({
    path: `/study-groups/${encodeURIComponent(params.groupId)}/comments/${encodeURIComponent(params.commentId)}`,
    method: "DELETE",
    responseSchema: StudyGroupPostCommentSchema,
  })
}

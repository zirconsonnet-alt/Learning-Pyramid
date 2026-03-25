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

const AdminUserListSchema = z.array(AdminUserSchema)
const AdminGroupListSchema = z.array(StudyGroupSchema)
const AdminGroupPostListSchema = z.array(AdminGroupPostSchema)
const AdminGroupCommentListSchema = z.array(AdminGroupCommentSchema)
const AdminActionLogListSchema = z.array(AdminActionLogSchema)

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

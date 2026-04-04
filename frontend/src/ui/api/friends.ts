import { z } from "zod"

import { apiRequest } from "@/ui/api/http"

export const FriendUserSchema = z.object({
  userId: z.string(),
  publicUid: z.string(),
  nickname: z.string(),
  bio: z.string().nullable(),
  avatarUrl: z.string().nullable(),
})

export type FriendUser = z.infer<typeof FriendUserSchema>

export const FriendSchema = FriendUserSchema.extend({
  friendedAt: z.string(),
})

export type Friend = z.infer<typeof FriendSchema>

export const FriendRequestSchema = z.object({
  requestId: z.string(),
  status: z.string(),
  message: z.string().nullable(),
  createdAt: z.string(),
  handledAt: z.string().nullable(),
  handledByUserId: z.string().nullable(),
  user: FriendUserSchema,
})

export type FriendRequest = z.infer<typeof FriendRequestSchema>

export const FriendLearningStatsSchema = z.object({
  projectCount: z.number(),
  learningCount: z.number(),
  reviewCount: z.number(),
  totalActions: z.number(),
  studyDays: z.number(),
  lastStudyAt: z.string().nullable(),
})

export type FriendLearningStats = z.infer<typeof FriendLearningStatsSchema>

export const FriendProfileSchema = FriendUserSchema.extend({
  stats: FriendLearningStatsSchema,
})

export type FriendProfile = z.infer<typeof FriendProfileSchema>

export const FriendLeaderboardEntrySchema = z.object({
  user: FriendUserSchema,
  isSelf: z.boolean(),
  friendedAt: z.string().nullable(),
  stats: FriendLearningStatsSchema,
})

export type FriendLeaderboardEntry = z.infer<typeof FriendLeaderboardEntrySchema>

const FriendListSchema = z.array(FriendSchema)
const FriendRequestListSchema = z.array(FriendRequestSchema)
const FriendLeaderboardSchema = z.array(FriendLeaderboardEntrySchema)

function buildQueryPath(basePath: string, params?: Record<string, string | number | undefined>) {
  const search = new URLSearchParams()
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value === undefined || value === null) return
    const text = String(value).trim()
    if (!text) return
    search.set(key, text)
  })
  const query = search.toString()
  if (!query) return basePath
  return `${basePath}?${query}`
}

export function listFriends(params?: { limit?: number }) {
  const path = buildQueryPath("/friends", { limit: params?.limit && params.limit > 0 ? params.limit : undefined })
  return apiRequest({
    path,
    responseSchema: FriendListSchema,
  })
}

export function getFriendProfile(friendUserId: string) {
  return apiRequest({
    path: `/friends/${encodeURIComponent(friendUserId)}/profile`,
    responseSchema: FriendProfileSchema,
  })
}

export function listFriendLeaderboard() {
  return apiRequest({
    path: "/friends/leaderboard",
    responseSchema: FriendLeaderboardSchema,
  })
}

export function listFriendRequests(params?: { box?: "incoming" | "outgoing"; limit?: number }) {
  const box = params?.box && params.box.trim() ? params.box.trim().toLowerCase() : "incoming"
  const path = buildQueryPath("/friends/requests", {
    box,
    limit: params?.limit && params.limit > 0 ? params.limit : undefined,
  })
  return apiRequest({
    path,
    responseSchema: FriendRequestListSchema,
  })
}

export function createFriendRequest(params: { publicUid: string; message?: string }) {
  return apiRequest({
    path: "/friends/requests",
    method: "POST",
    body: {
      publicUid: params.publicUid,
      message: params.message ?? "",
    },
    responseSchema: FriendRequestSchema,
  })
}

export function acceptFriendRequest(requestId: string) {
  return apiRequest({
    path: `/friends/requests/${encodeURIComponent(requestId)}/accept`,
    method: "POST",
    responseSchema: FriendRequestSchema,
  })
}

export function rejectFriendRequest(requestId: string) {
  return apiRequest({
    path: `/friends/requests/${encodeURIComponent(requestId)}/reject`,
    method: "POST",
    responseSchema: FriendRequestSchema,
  })
}

export function cancelFriendRequest(requestId: string) {
  return apiRequest({
    path: `/friends/requests/${encodeURIComponent(requestId)}/cancel`,
    method: "POST",
    responseSchema: FriendRequestSchema,
  })
}

export function deleteFriend(friendUserId: string) {
  return apiRequest({
    path: `/friends/${encodeURIComponent(friendUserId)}`,
    method: "DELETE",
    responseSchema: z.null(),
  })
}

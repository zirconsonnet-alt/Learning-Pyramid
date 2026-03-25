import { z } from "zod"

import { apiRequest } from "@/ui/api/http"

export const UserProfileSchema = z.object({
  userId: z.string(),
  email: z.string(),
  publicUid: z.string(),
  nickname: z.string(),
  bio: z.string(),
  avatarUrl: z.string().nullable(),
  status: z.string(),
  createdAt: z.string(),
  updatedAt: z.string(),
})

export type UserProfile = z.infer<typeof UserProfileSchema>

export const PublicUserLookupSchema = z.object({
  userId: z.string(),
  publicUid: z.string(),
  nickname: z.string(),
  bio: z.string(),
  avatarUrl: z.string().nullable(),
})

export type PublicUserLookup = z.infer<typeof PublicUserLookupSchema>

export function getMyProfile() {
  return apiRequest({
    path: "/profile/me",
    responseSchema: UserProfileSchema,
  })
}

export function updateMyProfile(params: { nickname: string; bio: string }) {
  return apiRequest({
    path: "/profile/me",
    method: "PATCH",
    body: params,
    responseSchema: UserProfileSchema,
  })
}

export function changeMyPassword(params: { currentPassword: string; newPassword: string }) {
  return apiRequest({
    path: "/profile/me/password",
    method: "POST",
    body: params,
    responseSchema: z.null(),
  })
}

export function uploadMyAvatar(file: File) {
  return apiRequest({
    path: "/profile/me/avatar",
    method: "PUT",
    body: file,
    headers: { "Content-Type": file.type || "application/octet-stream" },
    responseSchema: UserProfileSchema,
  })
}

export function findUserByUid(publicUid: string) {
  return apiRequest({
    path: `/users/by-uid/${encodeURIComponent(publicUid)}`,
    responseSchema: PublicUserLookupSchema,
  })
}

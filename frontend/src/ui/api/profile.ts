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

export const UserLlmSettingsSchema = z.object({
  baseUrl: z.string(),
  modelName: z.string(),
  promptAssemblyMode: z.enum(["system", "user_concat"]),
  savedApiKeyConfigured: z.boolean(),
  savedApiKeyPreview: z.string().nullable(),
  llmConfigured: z.boolean(),
  storyGenerationConfigured: z.boolean(),
  llmSource: z.enum(["user", "global", "env", "none"]),
})

export type UserLlmSettings = z.infer<typeof UserLlmSettingsSchema>

export const UserAsrSettingsSchema = z.object({
  baseUrl: z.string(),
  modelName: z.string(),
  savedApiKeyConfigured: z.boolean(),
  savedApiKeyPreview: z.string().nullable(),
  asrConfigured: z.boolean(),
  asrSource: z.enum(["user", "env", "none"]),
})

export type UserAsrSettings = z.infer<typeof UserAsrSettingsSchema>

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

export function getMyLlmSettings() {
  return apiRequest({
    path: "/profile/me/llm-settings",
    responseSchema: UserLlmSettingsSchema,
  })
}

export function updateMyLlmSettings(params: {
  baseUrl?: string
  modelName?: string
  apiKey?: string
  promptAssemblyMode?: "system" | "user_concat"
  clearApiKey?: boolean
}) {
  return apiRequest({
    path: "/profile/me/llm-settings",
    method: "PUT",
    body: params,
    responseSchema: UserLlmSettingsSchema,
  })
}

export function getMyAsrSettings() {
  return apiRequest({
    path: "/profile/me/asr-settings",
    responseSchema: UserAsrSettingsSchema,
  })
}

export function updateMyAsrSettings(params: {
  baseUrl?: string
  modelName?: string
  apiKey?: string
  clearApiKey?: boolean
}) {
  return apiRequest({
    path: "/profile/me/asr-settings",
    method: "PUT",
    body: params,
    responseSchema: UserAsrSettingsSchema,
  })
}

export function findUserByUid(publicUid: string) {
  return apiRequest({
    path: `/users/by-uid/${encodeURIComponent(publicUid)}`,
    responseSchema: PublicUserLookupSchema,
  })
}

import { z } from "zod"

import { apiRequest, type ApiRequestExecutionOptions } from "@/ui/api/http"

export const AuthUserSchema = z.object({
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
export type AuthUser = z.infer<typeof AuthUserSchema>

const NullableAuthUserSchema = AuthUserSchema.nullable()

export function getCurrentUser(options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: "/auth/me",
    responseSchema: NullableAuthUserSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export function login(params: { email: string; password: string }) {
  return apiRequest({
    path: "/auth/login",
    method: "POST",
    body: params,
    responseSchema: AuthUserSchema,
  })
}

export function register(params: { email: string; password: string }) {
  return apiRequest({
    path: "/auth/register",
    method: "POST",
    body: params,
    responseSchema: AuthUserSchema,
  })
}

export function logout() {
  return apiRequest({
    path: "/auth/logout",
    method: "POST",
    responseSchema: z.null(),
  })
}

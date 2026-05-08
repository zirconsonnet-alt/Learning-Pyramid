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
export const RegisterAuthResultSchema = AuthUserSchema.extend({
  emailVerificationRequired: z.boolean(),
  verificationEmailSent: z.boolean(),
})
export type RegisterAuthResult = z.infer<typeof RegisterAuthResultSchema>
export const SignupHumanCheckChallengeSchema = z.object({
  parameters: z
    .object({
      algorithm: z.string(),
      cost: z.number(),
      expiresAt: z.number().optional(),
    })
    .passthrough(),
  signature: z.string(),
})
export type SignupHumanCheckChallenge = z.infer<typeof SignupHumanCheckChallengeSchema>

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

export function register(params: {
  email: string
  password: string
  inviteCode?: string | null
  humanCheckToken?: string | null
}) {
  return apiRequest({
    path: "/auth/register",
    method: "POST",
    body: {
      email: params.email,
      password: params.password,
      inviteCode: params.inviteCode?.trim() ? params.inviteCode.trim() : undefined,
      humanCheckToken: params.humanCheckToken?.trim() ? params.humanCheckToken.trim() : undefined,
    },
    responseSchema: RegisterAuthResultSchema,
  })
}

export function getSignupHumanCheckChallenge(options?: ApiRequestExecutionOptions) {
  return apiRequest({
    path: "/auth/human-check/challenge",
    responseSchema: SignupHumanCheckChallengeSchema,
    signal: options?.signal,
    timeoutMs: options?.timeoutMs,
  })
}

export function requestEmailVerification(params: { email: string }) {
  return apiRequest({
    path: "/auth/email-verification/request",
    method: "POST",
    body: { email: params.email },
    responseSchema: z.null(),
  })
}

export function confirmEmailVerification(params: { token: string }) {
  return apiRequest({
    path: "/auth/email-verification/confirm",
    method: "POST",
    body: { token: params.token },
    responseSchema: AuthUserSchema,
  })
}

export function requestPasswordReset(params: { email: string }) {
  return apiRequest({
    path: "/auth/password-reset/request",
    method: "POST",
    body: { email: params.email },
    responseSchema: z.null(),
  })
}

export function confirmPasswordReset(params: { token: string; newPassword: string }) {
  return apiRequest({
    path: "/auth/password-reset/confirm",
    method: "POST",
    body: {
      token: params.token,
      newPassword: params.newPassword,
    },
    responseSchema: z.null(),
  })
}

export function logout() {
  return apiRequest({
    path: "/auth/logout",
    method: "POST",
    responseSchema: z.null(),
  })
}

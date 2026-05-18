import { z } from "zod"

import type { ApiRequester } from "./types"

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

const CurrentAuthUserSchema = AuthUserSchema.nullable()

export type AuthLoginInput = {
  email: string
  password: string
}

export function createAuthApi(requester: ApiRequester) {
  return {
    me: () =>
      requester.request({
        path: "/auth/me",
        responseSchema: CurrentAuthUserSchema,
      }),
    login: (body: AuthLoginInput) =>
      requester.request({
        path: "/auth/login",
        method: "POST",
        body,
        responseSchema: AuthUserSchema,
      }),
    logout: () =>
      requester.request({
        path: "/auth/logout",
        method: "POST",
        responseSchema: z.null(),
      }),
  }
}

import { z } from "zod"

import { projectApiPath, type ApiRequester, type ScopedProjectRef } from "./requester"

export const SystemCapabilitiesSchema = z.object({
  appMode: z.enum(["local", "hosted"]),
  asrEnabled: z.boolean(),
  serverMediaStreamEnabled: z.boolean(),
  browserLocalMediaEnabled: z.boolean(),
  baiduNetdiskEnabled: z.boolean(),
  authEnabled: z.boolean(),
  allowSignup: z.boolean(),
  signupInviteRequired: z.boolean(),
  passwordResetEnabled: z.boolean(),
  emailVerificationEnabled: z.boolean(),
  signupHumanCheckEnabled: z.boolean(),
  signupHumanCheckProvider: z.literal("altcha").nullable(),
  signupHumanCheckChallengeUrl: z.string().nullable(),
  llmConfigured: z.boolean(),
  storyGenerationConfigured: z.boolean(),
  llmSource: z.enum(["user", "global", "env", "none"]),
})

export const AskProjectLlmResultSchema = z.object({
  content: z.string(),
})

export type SystemCapabilities = z.infer<typeof SystemCapabilitiesSchema>
export type AskProjectLlmResult = z.infer<typeof AskProjectLlmResultSchema>

export type ProjectLlmImageInput = {
  imageDataUrl: string
  label?: string
  mimeType?: string
  timeMs?: number
}

export type AskProjectLlmInput = {
  imageInputs?: ProjectLlmImageInput[]
  learningObjectNodeId?: string
  learningTaskNodeId?: string
  modelName?: string
  prompt: string
  recallPointId?: string
  supplementalContext?: string
  systemPrompt?: string
  temperature?: number
}

export function createSystemApi(requester: ApiRequester) {
  return {
    getCapabilities: () =>
      requester.request({
        path: "/system/capabilities",
        responseSchema: SystemCapabilitiesSchema,
      }),
    askProjectLlm: (scope: ScopedProjectRef, body: AskProjectLlmInput) =>
      requester.request({
        path: projectApiPath(scope, "/llm/ask"),
        method: "POST",
        body,
        responseSchema: AskProjectLlmResultSchema,
      }),
  }
}

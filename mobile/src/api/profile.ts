import { z } from "zod"

import type { ApiRequester } from "./requester"

const PromptAssemblyModeSchema = z.enum(["system", "user_concat"])

export const UserLlmSettingsSchema = z.object({
  baseUrl: z.string(),
  modelName: z.string(),
  promptAssemblyMode: PromptAssemblyModeSchema,
  savedApiKeyConfigured: z.boolean(),
  savedApiKeyPreview: z.string().nullable(),
  llmConfigured: z.boolean(),
  storyGenerationConfigured: z.boolean(),
  llmSource: z.enum(["user", "global", "env", "none"]),
})

export const UserAsrSettingsSchema = z.object({
  baseUrl: z.string(),
  modelName: z.string(),
  savedApiKeyConfigured: z.boolean(),
  savedApiKeyPreview: z.string().nullable(),
  asrConfigured: z.boolean(),
  asrSource: z.enum(["user", "env", "none"]),
})

const PomodoroPlanSchema = z.object({
  id: z.string().optional().default(""),
  enabled: z.boolean(),
  startTime: z.string(),
  focusMinutes: z.number().int(),
  breakMinutes: z.number().int(),
  pomodoroCount: z.number().int(),
  projectRefs: z
    .array(
      z
        .object({
          subjectId: z.string(),
          scopedProjectId: z.string(),
        })
        .nullable(),
    )
    .default([]),
  breakPrompt: z.string().optional().default(""),
  focusPrompts: z.array(z.string()).default([]),
})

const PomodoroDaySchema = z.object({
  plans: z.array(PomodoroPlanSchema).default([]),
})

const PomodoroMicroBreaksSchema = z.object({
  enabled: z.boolean(),
  minIntervalSeconds: z.number().int(),
  maxIntervalSeconds: z.number().int(),
  durationSeconds: z.number().int(),
})

const PomodoroSettingsSchema = z.object({
  enabled: z.boolean(),
  transitionSoundEnabled: z.boolean().optional().default(false),
  defaultFocusPrompt: z.string().optional().default(""),
  defaultBreakPrompt: z.string().optional().default(""),
  microBreaks: PomodoroMicroBreaksSchema,
  weeklySchedule: z.object({
    mon: PomodoroDaySchema,
    tue: PomodoroDaySchema,
    wed: PomodoroDaySchema,
    thu: PomodoroDaySchema,
    fri: PomodoroDaySchema,
    sat: PomodoroDaySchema,
    sun: PomodoroDaySchema,
  }),
})

export const UserGlobalSettingsSchema = z.object({
  theme: z.string(),
  pomodoro: PomodoroSettingsSchema.optional(),
  defaultProjectReviewTemplate: z
    .array(z.object({ kind: z.enum(["CONVERGENCE", "REVIEW_TASK"]), count: z.number().int().optional() }))
    .optional(),
  learningPlans: z.unknown().optional(),
  updatedAt: z.string().nullable().optional(),
})

export type PromptAssemblyMode = z.infer<typeof PromptAssemblyModeSchema>
export type UserLlmSettings = z.infer<typeof UserLlmSettingsSchema>
export type UserAsrSettings = z.infer<typeof UserAsrSettingsSchema>
export type UserGlobalSettings = z.infer<typeof UserGlobalSettingsSchema>

export type UpdateUserLlmSettingsInput = {
  baseUrl?: string
  modelName?: string
  apiKey?: string
  promptAssemblyMode?: PromptAssemblyMode
  clearApiKey?: boolean
}

export type UpdateUserAsrSettingsInput = {
  baseUrl?: string
  modelName?: string
  apiKey?: string
  clearApiKey?: boolean
}

const emptyPomodoroDay = { plans: [] }
const defaultPomodoroSettings = {
  enabled: false,
  transitionSoundEnabled: false,
  defaultFocusPrompt: "",
  defaultBreakPrompt: "",
  microBreaks: {
    enabled: true,
    minIntervalSeconds: 180,
    maxIntervalSeconds: 300,
    durationSeconds: 10,
  },
  weeklySchedule: {
    mon: emptyPomodoroDay,
    tue: emptyPomodoroDay,
    wed: emptyPomodoroDay,
    thu: emptyPomodoroDay,
    fri: emptyPomodoroDay,
    sat: emptyPomodoroDay,
    sun: emptyPomodoroDay,
  },
}

const DEFAULT_PROJECT_REVIEW_TEMPLATE = [{ kind: "REVIEW_TASK" as const }, { kind: "CONVERGENCE" as const }]

export function buildUpdateUserGlobalSettingsBody(current: UserGlobalSettings | null | undefined, theme: string) {
  return {
    theme,
    pomodoro: current?.pomodoro ?? defaultPomodoroSettings,
    defaultProjectReviewTemplate: current?.defaultProjectReviewTemplate ?? DEFAULT_PROJECT_REVIEW_TEMPLATE,
  }
}

export function createProfileApi(requester: ApiRequester) {
  return {
    getMyLlmSettings: () =>
      requester.request({
        path: "/profile/me/llm-settings",
        responseSchema: UserLlmSettingsSchema,
      }),
    updateMyLlmSettings: (body: UpdateUserLlmSettingsInput) =>
      requester.request({
        path: "/profile/me/llm-settings",
        method: "PUT",
        body,
        responseSchema: UserLlmSettingsSchema,
      }),
    getMyAsrSettings: () =>
      requester.request({
        path: "/profile/me/asr-settings",
        responseSchema: UserAsrSettingsSchema,
      }),
    updateMyAsrSettings: (body: UpdateUserAsrSettingsInput) =>
      requester.request({
        path: "/profile/me/asr-settings",
        method: "PUT",
        body,
        responseSchema: UserAsrSettingsSchema,
      }),
    getMyGlobalSettings: () =>
      requester.request({
        path: "/profile/me/global-settings",
        responseSchema: UserGlobalSettingsSchema,
      }),
    updateMyGlobalSettings: (body: ReturnType<typeof buildUpdateUserGlobalSettingsBody>) =>
      requester.request({
        path: "/profile/me/global-settings",
        method: "PUT",
        body,
        responseSchema: UserGlobalSettingsSchema,
      }),
  }
}

import { z } from "zod"

import { apiRequest } from "@/ui/api/http"
import { DEFAULT_PROJECT_REVIEW_TEMPLATE } from "@/ui/store/globalConfigStore"
import { ReviewChainTemplateItemSchema } from "@/ui/api/projectConfig"

const UserPomodoroPlanSchema = z.object({
  id: z.string().optional().default(""),
  enabled: z.boolean(),
  startTime: z.string(),
  focusMinutes: z.number().int().min(1).max(180),
  breakMinutes: z.number().int().min(1).max(60),
  pomodoroCount: z.number().int().min(1).max(12),
  projectRefs: z
    .array(
      z
        .object({
          subjectId: z.string().min(1),
          projectId: z.string().min(1),
        })
        .nullable(),
    )
    .max(12)
    .default([]),
  breakPrompt: z.string().max(200).optional().default(""),
  focusPrompts: z.array(z.string().max(200)).max(12).default([]),
})

const LegacyUserPomodoroDaySchema = UserPomodoroPlanSchema.transform((plan) => ({
  plans: plan.enabled ? [plan] : [],
}))

const UserPomodoroDaySchema = z.union([
  z.object({
    plans: z.array(UserPomodoroPlanSchema).default([]),
  }),
  LegacyUserPomodoroDaySchema,
])

const DEFAULT_USER_POMODORO_MICRO_BREAKS = {
  enabled: false,
  minIntervalSeconds: 180,
  maxIntervalSeconds: 300,
  durationSeconds: 10,
}

const UserPomodoroMicroBreaksSchema = z
  .object({
    enabled: z.boolean(),
    minIntervalSeconds: z.number().int().min(30).max(3600),
    maxIntervalSeconds: z.number().int().min(30).max(3600),
    durationSeconds: z.number().int().min(5).max(300),
  })
  .refine((settings) => settings.maxIntervalSeconds >= settings.minIntervalSeconds, {
    message: "maxIntervalSeconds must be greater than or equal to minIntervalSeconds",
    path: ["maxIntervalSeconds"],
  })

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

export const SyncedLearningPlanSchema = z.object({
  planId: z.string(),
  projectId: z.string(),
  title: z.string(),
  targetKind: z.enum(["PROJECT", "LEARNING_OBJECT_NODES"]),
  learningObjectNodeIds: z.array(z.string()).default([]),
  targetDays: z.number().int().min(1).max(3650),
  createdDateKey: z.string(),
  dueDateKey: z.string(),
  archivedAt: z.number().int().nonnegative().nullable().default(null),
  updatedAt: z.number().int().nonnegative(),
})

export const SyncedLearningPlanProgressSnapshotSchema = z.object({
  planId: z.string(),
  dateKey: z.string(),
  progressRatio: z.number().min(0).max(1),
  updatedAt: z.number().int().nonnegative(),
})

export const SyncedLearningPlansSchema = z.object({
  plans: z.array(SyncedLearningPlanSchema).default([]),
  progressSnapshots: z.array(SyncedLearningPlanProgressSnapshotSchema).default([]),
})

export type SyncedLearningPlans = z.infer<typeof SyncedLearningPlansSchema>

export const UserGlobalSettingsSchema = z.object({
  theme: z.string(),
  pomodoro: z.object({
    enabled: z.boolean(),
    transitionSoundEnabled: z.boolean().optional().default(false),
    defaultFocusPrompt: z.string().max(200).optional().default(""),
    defaultBreakPrompt: z.string().max(200).optional().default(""),
    microBreaks: UserPomodoroMicroBreaksSchema.optional().default(DEFAULT_USER_POMODORO_MICRO_BREAKS),
    weeklySchedule: z.object({
      mon: UserPomodoroDaySchema,
      tue: UserPomodoroDaySchema,
      wed: UserPomodoroDaySchema,
      thu: UserPomodoroDaySchema,
      fri: UserPomodoroDaySchema,
      sat: UserPomodoroDaySchema,
      sun: UserPomodoroDaySchema,
    }),
  }),
  defaultProjectReviewTemplate: z.array(ReviewChainTemplateItemSchema).min(1),
  learningPlans: SyncedLearningPlansSchema.optional().default({ plans: [], progressSnapshots: [] }),
  updatedAt: z.string().nullable().optional(),
})

export type UserGlobalSettings = z.infer<typeof UserGlobalSettingsSchema>

export const StudyMetricRangeSchema = z.object({
  startMs: z.number().int().nonnegative(),
  endMs: z.number().int().positive(),
})

export const DailyStudyMetricEntrySchema = z.object({
  projectId: z.string(),
  dateKey: z.string(),
  schemaVersion: z.number().int().positive().default(2),
  webPresenceMs: z.number().int().nonnegative().default(0),
  videoMs: z.number().int().nonnegative().default(0),
  recallEntryMs: z.number().int().nonnegative().default(0),
  reviewMs: z.number().int().nonnegative().default(0),
  aiQaMs: z.number().int().nonnegative().default(0),
  distractionMs: z.number().int().nonnegative().default(0),
  presenceRanges: z.array(StudyMetricRangeSchema).default([]),
  videoRanges: z.array(StudyMetricRangeSchema).default([]),
  recallEntryRanges: z.array(StudyMetricRangeSchema).default([]),
  reviewRanges: z.array(StudyMetricRangeSchema).default([]),
  aiQaRanges: z.array(StudyMetricRangeSchema).default([]),
  isPartitionComplete: z.boolean().default(false),
  effectiveMs: z.number().int().nonnegative().default(0),
  watchMs: z.number().int().nonnegative().default(0),
  composeMs: z.number().int().nonnegative().default(0),
  qaMs: z.number().int().nonnegative().default(0),
  effectiveRanges: z.array(StudyMetricRangeSchema).default([]),
  watchRanges: z.array(StudyMetricRangeSchema).default([]),
  composeRanges: z.array(StudyMetricRangeSchema).default([]),
  qaRanges: z.array(StudyMetricRangeSchema).default([]),
  updatedAt: z.string().optional(),
})

export type StudyMetricRange = z.infer<typeof StudyMetricRangeSchema>
export type DailyStudyMetricEntry = z.infer<typeof DailyStudyMetricEntrySchema>

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

export function getMyGlobalSettings() {
  return apiRequest({
    path: "/profile/me/global-settings",
    responseSchema: UserGlobalSettingsSchema,
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

export function updateMyGlobalSettings(params: {
  theme?: string | null
  pomodoro: {
    enabled: boolean
    transitionSoundEnabled?: boolean
    defaultFocusPrompt?: string
    defaultBreakPrompt?: string
    microBreaks?: z.input<typeof UserPomodoroMicroBreaksSchema>
    weeklySchedule: {
      mon: z.input<typeof UserPomodoroDaySchema>
      tue: z.input<typeof UserPomodoroDaySchema>
      wed: z.input<typeof UserPomodoroDaySchema>
      thu: z.input<typeof UserPomodoroDaySchema>
      fri: z.input<typeof UserPomodoroDaySchema>
      sat: z.input<typeof UserPomodoroDaySchema>
      sun: z.input<typeof UserPomodoroDaySchema>
    }
  }
  defaultProjectReviewTemplate?: Array<{ kind: "CONVERGENCE" | "REVIEW_TASK"; count?: number }>
}) {
  return apiRequest({
    path: "/profile/me/global-settings",
    method: "PUT",
    body: {
      ...params,
      defaultProjectReviewTemplate: params.defaultProjectReviewTemplate ?? DEFAULT_PROJECT_REVIEW_TEMPLATE,
    },
    responseSchema: UserGlobalSettingsSchema,
  })
}

export function getMyLearningPlans() {
  return apiRequest({
    path: "/profile/me/learning-plans",
    responseSchema: SyncedLearningPlansSchema,
  })
}

export function updateMyLearningPlans(params: SyncedLearningPlans) {
  return apiRequest({
    path: "/profile/me/learning-plans",
    method: "PUT",
    body: params,
    responseSchema: SyncedLearningPlansSchema,
  })
}

export function findUserByUid(publicUid: string) {
  return apiRequest({
    path: `/users/by-uid/${encodeURIComponent(publicUid)}`,
    responseSchema: PublicUserLookupSchema,
  })
}

export function syncMyStudyMetrics(params: {
  projectIds: string[]
  dateFrom?: string
  dateTo?: string
  entries: DailyStudyMetricEntry[]
}) {
  return apiRequest({
    path: "/profile/me/study-metrics/sync",
    method: "POST",
    body: params,
    responseSchema: z.array(DailyStudyMetricEntrySchema),
  })
}

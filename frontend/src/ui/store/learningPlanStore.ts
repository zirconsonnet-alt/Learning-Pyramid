import { create } from "zustand"
import { persist } from "zustand/middleware"

import type { SyncedLearningPlans } from "@/ui/api/profile"

export type LearningPlanTargetKind = "PROJECT" | "LEARNING_OBJECT_NODES"

export type LearningPlan = {
  planId: string
  projectId: string
  title: string
  targetKind: LearningPlanTargetKind
  learningObjectNodeIds: string[]
  targetDays: number
  createdDateKey: string
  dueDateKey: string
  archivedAt: number | null
  updatedAt: number
}

export type LearningPlanProgressSnapshot = {
  dateKey: string
  progressRatio: number
  updatedAt: number
}

type LearningPlanState = {
  plansById: Record<string, LearningPlan>
  progressSnapshotsByPlanId: Record<string, Record<string, LearningPlanProgressSnapshot>>
  upsertPlan: (plan: LearningPlan) => void
  archivePlan: (planId: string) => void
  recordProgressSnapshot: (planId: string, dateKey: string, progressRatio: number) => void
  mergeSyncedLearningPlans: (payload: SyncedLearningPlans) => boolean
  reset: () => void
}

function clampProgressRatio(value: number) {
  if (!Number.isFinite(value)) return 0
  return Math.max(0, Math.min(1, value))
}

export function makeLearningPlanId(projectId: string) {
  const suffix =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
  return `plan:${projectId}:${suffix}`
}

export function normalizePlanTargetDays(value: number) {
  if (!Number.isFinite(value)) return 1
  return Math.max(1, Math.min(3650, Math.round(value)))
}

export function addDaysToDateKey(dateKey: string, days: number) {
  const [year, month, day] = dateKey.split("-").map((part) => Number(part))
  const date = new Date(year || 1970, (month || 1) - 1, day || 1)
  date.setDate(date.getDate() + Math.max(0, Math.floor(days)))
  const nextYear = date.getFullYear()
  const nextMonth = String(date.getMonth() + 1).padStart(2, "0")
  const nextDay = String(date.getDate()).padStart(2, "0")
  return `${nextYear}-${nextMonth}-${nextDay}`
}

export function diffDateKeysInclusive(startDateKey: string, endDateKey: string) {
  const start = Date.parse(`${startDateKey}T00:00:00`)
  const end = Date.parse(`${endDateKey}T00:00:00`)
  if (!Number.isFinite(start) || !Number.isFinite(end)) return 1
  return Math.max(1, Math.floor((end - start) / 86_400_000) + 1)
}

export const useLearningPlanStore = create<LearningPlanState>()(
  persist(
    (set) => ({
      plansById: {},
      progressSnapshotsByPlanId: {},
      upsertPlan: (plan) =>
        set((state) => ({
          plansById: {
            ...state.plansById,
            [plan.planId]: {
              ...plan,
              title: plan.title.trim() || "学习计划",
              targetDays: normalizePlanTargetDays(plan.targetDays),
              learningObjectNodeIds: Array.from(new Set(plan.learningObjectNodeIds.filter(Boolean))),
              archivedAt: plan.archivedAt ?? null,
              updatedAt: Date.now(),
            },
          },
        })),
      archivePlan: (planId) =>
        set((state) => {
          const plan = state.plansById[planId]
          if (!plan) return state
          return {
            plansById: {
              ...state.plansById,
              [planId]: {
                ...plan,
                archivedAt: Date.now(),
                updatedAt: Date.now(),
              },
            },
          }
        }),
      recordProgressSnapshot: (planId, dateKey, progressRatio) =>
        set((state) => {
          const nextRatio = clampProgressRatio(progressRatio)
          const current = state.progressSnapshotsByPlanId[planId]?.[dateKey]
          if (current && Math.abs(current.progressRatio - nextRatio) < 0.001) return state
          return {
            progressSnapshotsByPlanId: {
              ...state.progressSnapshotsByPlanId,
              [planId]: {
                ...(state.progressSnapshotsByPlanId[planId] ?? {}),
                [dateKey]: {
                  dateKey,
                  progressRatio: nextRatio,
                  updatedAt: Date.now(),
                },
              },
            },
          }
        }),
      mergeSyncedLearningPlans: (payload) => {
        let changed = false
        set((state) => {
          const next = mergeSyncedLearningPlansIntoState(state, payload)
          changed = next !== state
          return next
        })
        return changed
      },
      reset: () =>
        set({
          plansById: {},
          progressSnapshotsByPlanId: {},
        }),
    }),
    {
      name: "plm-learning-plans",
      version: 1,
    },
  ),
)

export function selectActiveLearningPlans(plansById: Record<string, LearningPlan>, projectId: string) {
  return Object.values(plansById)
    .filter((plan) => plan.projectId === projectId && !plan.archivedAt)
    .sort((left, right) => left.dueDateKey.localeCompare(right.dueDateKey) || left.createdDateKey.localeCompare(right.createdDateKey))
}

export function learningPlansToSyncPayload(
  plansById: Record<string, LearningPlan>,
  progressSnapshotsByPlanId: Record<string, Record<string, LearningPlanProgressSnapshot>>,
): SyncedLearningPlans {
  return {
    plans: Object.values(plansById).sort((left, right) => left.planId.localeCompare(right.planId)),
    progressSnapshots: Object.entries(progressSnapshotsByPlanId)
      .flatMap(([planId, snapshotsByDate]) =>
        Object.values(snapshotsByDate).map((snapshot) => ({
          planId,
          dateKey: snapshot.dateKey,
          progressRatio: clampProgressRatio(snapshot.progressRatio),
          updatedAt: snapshot.updatedAt,
        })),
      )
      .sort((left, right) => left.planId.localeCompare(right.planId) || left.dateKey.localeCompare(right.dateKey)),
  }
}

function mergeSyncedLearningPlansIntoState(state: LearningPlanState, payload: SyncedLearningPlans): LearningPlanState {
  let changed = false
  const plansById = { ...state.plansById }
  for (const remotePlan of payload.plans) {
    const localPlan = plansById[remotePlan.planId]
    if (!localPlan || remotePlan.updatedAt > localPlan.updatedAt) {
      plansById[remotePlan.planId] = {
        ...remotePlan,
        title: remotePlan.title.trim() || "学习计划",
        targetDays: normalizePlanTargetDays(remotePlan.targetDays),
        learningObjectNodeIds: Array.from(new Set(remotePlan.learningObjectNodeIds.filter(Boolean))),
      }
      changed = true
    }
  }

  const progressSnapshotsByPlanId = { ...state.progressSnapshotsByPlanId }
  for (const remoteSnapshot of payload.progressSnapshots) {
    const snapshotsByDate = progressSnapshotsByPlanId[remoteSnapshot.planId] ?? {}
    const localSnapshot = snapshotsByDate[remoteSnapshot.dateKey]
    if (localSnapshot && localSnapshot.updatedAt >= remoteSnapshot.updatedAt) continue
    progressSnapshotsByPlanId[remoteSnapshot.planId] = {
      ...snapshotsByDate,
      [remoteSnapshot.dateKey]: {
        dateKey: remoteSnapshot.dateKey,
        progressRatio: clampProgressRatio(remoteSnapshot.progressRatio),
        updatedAt: remoteSnapshot.updatedAt,
      },
    }
    changed = true
  }

  if (!changed) return state
  return {
    ...state,
    plansById,
    progressSnapshotsByPlanId,
  }
}

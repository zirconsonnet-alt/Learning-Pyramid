import { create } from "zustand"
import { persist } from "zustand/middleware"

import type { ReviewChainTemplateItem } from "@/ui/api/projectConfig"

export const DEFAULT_PROJECT_REVIEW_TEMPLATE: ReviewChainTemplateItem[] = [{ kind: "REVIEW_TASK" }, { kind: "CONVERGENCE" }]

function normalizeReviewTaskCount(value: unknown) {
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed < 1) return 1
  return parsed
}

export function cloneReviewChainTemplate(template: ReviewChainTemplateItem[]) {
  return template.map((item) => {
    if (item.kind === "REVIEW_TASK") {
      const count = normalizeReviewTaskCount(item.count)
      return count === 1 ? { kind: "REVIEW_TASK" as const } : { kind: "REVIEW_TASK" as const, count }
    }
    return { kind: "CONVERGENCE" as const }
  })
}

export function normalizeProjectReviewTemplate(input: unknown): ReviewChainTemplateItem[] {
  if (!Array.isArray(input) || input.length === 0) {
    return cloneReviewChainTemplate(DEFAULT_PROJECT_REVIEW_TEMPLATE)
  }

  const normalized: ReviewChainTemplateItem[] = []
  let hasConvergence = false

  for (const rawItem of input) {
    if (!rawItem || typeof rawItem !== "object") continue
    const item = rawItem as { kind?: unknown; count?: unknown }
    if (item.kind === "CONVERGENCE") {
      normalized.push({ kind: "CONVERGENCE" })
      hasConvergence = true
      continue
    }
    if (item.kind === "REVIEW_TASK") {
      const count = normalizeReviewTaskCount(item.count)
      normalized.push(count === 1 ? { kind: "REVIEW_TASK" } : { kind: "REVIEW_TASK", count })
    }
  }

  if (normalized.length === 0) {
    return cloneReviewChainTemplate(DEFAULT_PROJECT_REVIEW_TEMPLATE)
  }
  if (!hasConvergence) {
    normalized.unshift({ kind: "CONVERGENCE" })
  }
  return normalized
}

type GlobalConfigState = {
  defaultProjectReviewTemplate: ReviewChainTemplateItem[]
  setDefaultProjectReviewTemplate: (template: ReviewChainTemplateItem[]) => void
  resetDefaultProjectReviewTemplate: () => void
}

export const useGlobalConfigStore = create<GlobalConfigState>()(
  persist(
    (set) => ({
      defaultProjectReviewTemplate: cloneReviewChainTemplate(DEFAULT_PROJECT_REVIEW_TEMPLATE),
      setDefaultProjectReviewTemplate: (template) =>
        set({
          defaultProjectReviewTemplate: normalizeProjectReviewTemplate(template),
        }),
      resetDefaultProjectReviewTemplate: () =>
        set({
          defaultProjectReviewTemplate: cloneReviewChainTemplate(DEFAULT_PROJECT_REVIEW_TEMPLATE),
        }),
    }),
    {
      name: "plm-global-config",
      merge: (persistedState, currentState) => {
        const raw =
          persistedState && typeof persistedState === "object" && "defaultProjectReviewTemplate" in persistedState
            ? persistedState.defaultProjectReviewTemplate
            : undefined
        return {
          ...currentState,
          defaultProjectReviewTemplate: normalizeProjectReviewTemplate(raw),
        }
      },
    },
  ),
)

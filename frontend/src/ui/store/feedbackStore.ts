import { create } from "zustand"

export type FeedbackTone = "success" | "error" | "info"

export type FeedbackItem = {
  id: string
  title: string
  message?: string
  tone: FeedbackTone
  durationMs: number
}

type FeedbackStore = {
  items: FeedbackItem[]
  push: (item: Omit<FeedbackItem, "id" | "durationMs"> & { id?: string; durationMs?: number }) => string
  dismiss: (id: string) => void
  clear: () => void
}

const DEFAULT_FEEDBACK_DURATION_MS = 4_500

export const useFeedbackStore = create<FeedbackStore>()((set) => ({
  items: [],
  push: (item) => {
    const id = item.id ?? `feedback-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    set((state) => ({
      items: [
        ...state.items,
        {
          id,
          title: item.title,
          message: item.message,
          tone: item.tone,
          durationMs: item.durationMs ?? DEFAULT_FEEDBACK_DURATION_MS,
        },
      ],
    }))
    return id
  },
  dismiss: (id) =>
    set((state) => ({
      items: state.items.filter((item) => item.id !== id),
    })),
  clear: () => set({ items: [] }),
}))

export function showSuccessFeedback(title: string, message?: string) {
  return useFeedbackStore.getState().push({ tone: "success", title, message })
}

export function showErrorFeedback(title: string, message?: string) {
  return useFeedbackStore.getState().push({ tone: "error", title, message, durationMs: 6_000 })
}

export function showInfoFeedback(title: string, message?: string) {
  return useFeedbackStore.getState().push({ tone: "info", title, message })
}

import { create } from "zustand"
import { persist } from "zustand/middleware"

type AppState = {
  selectedProjectId: string | null
  setSelectedProjectId: (projectId: string | null) => void
  reset: () => void
}

const initialAppState = {
  selectedProjectId: null as string | null,
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      ...initialAppState,
      setSelectedProjectId: (projectId) => set({ selectedProjectId: projectId }),
      reset: () => set(initialAppState),
    }),
    { name: "plm-app" },
  ),
)

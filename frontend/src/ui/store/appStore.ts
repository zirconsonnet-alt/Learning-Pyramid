import { create } from "zustand"
import { persist } from "zustand/middleware"

type AppState = {
  selectedProjectId: string | null
  setSelectedProjectId: (projectId: string | null) => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      selectedProjectId: null,
      setSelectedProjectId: (projectId) => set({ selectedProjectId: projectId }),
    }),
    { name: "plm-app" },
  ),
)


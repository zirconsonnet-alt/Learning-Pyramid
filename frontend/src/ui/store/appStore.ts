import { create } from "zustand"
import { persist } from "zustand/middleware"

type AppState = {
  selectedProjectId: string | null
  recentProjectIds: string[]
  setSelectedProjectId: (projectId: string | null) => void
  removeRecentProjectId: (projectId: string) => void
  reset: () => void
}

const initialAppState = {
  selectedProjectId: null as string | null,
  recentProjectIds: [] as string[],
}

function touchRecentProjectIds(recentProjectIds: string[], projectId: string) {
  return [projectId, ...recentProjectIds.filter((item) => item !== projectId)].slice(0, 24)
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      ...initialAppState,
      setSelectedProjectId: (projectId) =>
        set((state) => ({
          selectedProjectId: projectId,
          recentProjectIds: projectId ? touchRecentProjectIds(state.recentProjectIds, projectId) : state.recentProjectIds,
        })),
      removeRecentProjectId: (projectId) =>
        set((state) => ({
          recentProjectIds: state.recentProjectIds.filter((item) => item !== projectId),
          selectedProjectId: state.selectedProjectId === projectId ? null : state.selectedProjectId,
        })),
      reset: () => set(initialAppState),
    }),
    { name: "plm-app" },
  ),
)

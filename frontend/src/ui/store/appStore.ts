import { create } from "zustand"
import { persist } from "zustand/middleware"

type AppState = {
  selectedSubjectId: string | null
  selectedProjectId: string | null
  recentProjectIds: string[]
  setSelectedSubjectId: (subjectId: string | null) => void
  setSelectedProjectId: (projectId: string | null) => void
  removeRecentProjectId: (projectId: string) => void
  reset: () => void
}

const initialAppState = {
  selectedSubjectId: null as string | null,
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
      setSelectedSubjectId: (subjectId) =>
        set(() => ({
          selectedSubjectId: subjectId,
        })),
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

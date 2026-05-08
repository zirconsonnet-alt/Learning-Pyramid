import { create } from "zustand"
import { persist } from "zustand/middleware"

type AppState = {
  selectedSubjectId: string | null
  selectedWorkbenchProjectId: string | null
  recentSubjectIds: string[]
  recentWorkbenchProjectIds: string[]
  setSelectedSubjectId: (subjectId: string | null) => void
  setSelectedWorkbenchProjectId: (projectId: string | null) => void
  removeRecentSubjectId: (subjectId: string) => void
  removeRecentWorkbenchProjectId: (projectId: string) => void
  reset: () => void
}

const initialAppState = {
  selectedSubjectId: null as string | null,
  selectedWorkbenchProjectId: null as string | null,
  recentSubjectIds: [] as string[],
  recentWorkbenchProjectIds: [] as string[],
}

function touchRecentIds(recentIds: string[], id: string) {
  return [id, ...recentIds.filter((item) => item !== id)].slice(0, 24)
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      ...initialAppState,
      setSelectedSubjectId: (subjectId) =>
        set((state) => ({
          selectedSubjectId: subjectId,
          recentSubjectIds: subjectId ? touchRecentIds(state.recentSubjectIds, subjectId) : state.recentSubjectIds,
        })),
      setSelectedWorkbenchProjectId: (projectId) =>
        set((state) => ({
          selectedWorkbenchProjectId: projectId,
          recentWorkbenchProjectIds: projectId ? touchRecentIds(state.recentWorkbenchProjectIds, projectId) : state.recentWorkbenchProjectIds,
        })),
      removeRecentSubjectId: (subjectId) =>
        set((state) => ({
          recentSubjectIds: state.recentSubjectIds.filter((item) => item !== subjectId),
          selectedSubjectId: state.selectedSubjectId === subjectId ? null : state.selectedSubjectId,
        })),
      removeRecentWorkbenchProjectId: (projectId) =>
        set((state) => ({
          recentWorkbenchProjectIds: state.recentWorkbenchProjectIds.filter((item) => item !== projectId),
          selectedWorkbenchProjectId: state.selectedWorkbenchProjectId === projectId ? null : state.selectedWorkbenchProjectId,
        })),
      reset: () => set(initialAppState),
    }),
    { name: "plm-app" },
  ),
)

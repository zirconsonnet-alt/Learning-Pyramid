import { create } from "zustand"
import { persist } from "zustand/middleware"

type AppState = {
  selectedSubjectId: string | null
  selectedWorkbenchProjectId: string | null
  selectedWorkbenchProjectRef: ProjectReference | null
  recentSubjectIds: string[]
  recentWorkbenchProjectIds: string[]
  recentWorkbenchProjectRefs: ProjectReference[]
  setSelectedSubjectId: (subjectId: string | null) => void
  setSelectedWorkbenchProjectId: (projectId: string | null) => void
  setSelectedWorkbenchProjectRef: (projectRef: ProjectReference | null) => void
  removeRecentSubjectId: (subjectId: string) => void
  removeRecentWorkbenchProjectId: (projectId: string) => void
  removeRecentWorkbenchProjectRef: (projectRef: ProjectReference) => void
  reset: () => void
}

export type ProjectReference = {
  subjectId: string
  scopedProjectId: string
}

const initialAppState = {
  selectedSubjectId: null as string | null,
  selectedWorkbenchProjectId: null as string | null,
  selectedWorkbenchProjectRef: null as ProjectReference | null,
  recentSubjectIds: [] as string[],
  recentWorkbenchProjectIds: [] as string[],
  recentWorkbenchProjectRefs: [] as ProjectReference[],
}

function touchRecentIds(recentIds: string[], id: string) {
  return [id, ...recentIds.filter((item) => item !== id)].slice(0, 24)
}

function projectRefKey(projectRef: ProjectReference) {
  return `${projectRef.subjectId}:${projectRef.scopedProjectId}`
}

function touchRecentProjectRefs(recentRefs: ProjectReference[], projectRef: ProjectReference) {
  const key = projectRefKey(projectRef)
  return [projectRef, ...recentRefs.filter((item) => projectRefKey(item) !== key)].slice(0, 24)
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
      setSelectedWorkbenchProjectRef: (projectRef) =>
        set((state) => ({
          selectedSubjectId: projectRef?.subjectId ?? state.selectedSubjectId,
          selectedWorkbenchProjectId: projectRef?.scopedProjectId ?? null,
          selectedWorkbenchProjectRef: projectRef,
          recentSubjectIds: projectRef ? touchRecentIds(state.recentSubjectIds, projectRef.subjectId) : state.recentSubjectIds,
          recentWorkbenchProjectRefs: projectRef
            ? touchRecentProjectRefs(state.recentWorkbenchProjectRefs, projectRef)
            : state.recentWorkbenchProjectRefs,
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
      removeRecentWorkbenchProjectRef: (projectRef) =>
        set((state) => {
          const key = projectRefKey(projectRef)
          return {
            recentWorkbenchProjectRefs: state.recentWorkbenchProjectRefs.filter((item) => projectRefKey(item) !== key),
            selectedWorkbenchProjectRef:
              state.selectedWorkbenchProjectRef && projectRefKey(state.selectedWorkbenchProjectRef) === key
                ? null
                : state.selectedWorkbenchProjectRef,
            selectedWorkbenchProjectId:
              state.selectedWorkbenchProjectRef && projectRefKey(state.selectedWorkbenchProjectRef) === key
                ? null
                : state.selectedWorkbenchProjectId,
          }
        }),
      reset: () => set(initialAppState),
    }),
    { name: "plm-app" },
  ),
)

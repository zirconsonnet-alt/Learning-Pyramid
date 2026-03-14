import { create } from "zustand"
import { persist } from "zustand/middleware"

export type DraftRecallPoint = {
  localId: string
  instanceId: string
  position: string
  questionText: string
  answerText: string
  createdAt: number
  updatedAt: number
}

type ProjectWorkbenchState = {
  roots: string[]
  selectedInstanceId: string | null
  drafts: DraftRecallPoint[]
  taskTitle: string
}

type WorkbenchState = {
  byProjectId: Record<string, ProjectWorkbenchState>
  ensure: (projectId: string) => void
  clearAll: () => void
  resetProject: (projectId: string) => void
  setRoots: (projectId: string, roots: string[]) => void
  setSelectedInstanceId: (projectId: string, instanceId: string | null) => void
  addDraft: (projectId: string, draft: DraftRecallPoint) => void
  updateDraft: (
    projectId: string,
    localId: string,
    patch: Partial<Pick<DraftRecallPoint, "questionText" | "answerText" | "position">>,
  ) => void
  removeDraft: (projectId: string, localId: string) => void
  clearDraftsForInstance: (projectId: string, instanceId: string) => void
  setTaskTitle: (projectId: string, title: string) => void
}

function emptyProjectState(): ProjectWorkbenchState {
  return { roots: [], selectedInstanceId: null, drafts: [], taskTitle: "" }
}

export const useWorkbenchStore = create<WorkbenchState>()(
  persist(
    (set) => ({
      byProjectId: {},
      clearAll: () => set({ byProjectId: {} }),
      ensure: (projectId) =>
        set((s) =>
          s.byProjectId[projectId] ? s : { byProjectId: { ...s.byProjectId, [projectId]: emptyProjectState() } },
        ),
      resetProject: (projectId) =>
        set((s) => {
          if (!s.byProjectId[projectId]) return s
          const next = { ...s.byProjectId }
          delete next[projectId]
          return { byProjectId: next }
        }),
      setRoots: (projectId, roots) =>
        set((s) => ({
          byProjectId: {
            ...s.byProjectId,
            [projectId]: { ...(s.byProjectId[projectId] ?? emptyProjectState()), roots },
          },
        })),
      setSelectedInstanceId: (projectId, selectedInstanceId) =>
        set((s) => ({
          byProjectId: {
            ...s.byProjectId,
            [projectId]: { ...(s.byProjectId[projectId] ?? emptyProjectState()), selectedInstanceId },
          },
        })),
      addDraft: (projectId, draft) =>
        set((s) => {
          const ps = s.byProjectId[projectId] ?? emptyProjectState()
          return { byProjectId: { ...s.byProjectId, [projectId]: { ...ps, drafts: [...ps.drafts, draft] } } }
        }),
      updateDraft: (projectId, localId, patch) =>
        set((s) => {
          const ps = s.byProjectId[projectId] ?? emptyProjectState()
          const drafts = ps.drafts.map((d) => (d.localId === localId ? { ...d, ...patch, updatedAt: Date.now() } : d))
          return { byProjectId: { ...s.byProjectId, [projectId]: { ...ps, drafts } } }
        }),
      removeDraft: (projectId, localId) =>
        set((s) => {
          const ps = s.byProjectId[projectId] ?? emptyProjectState()
          return {
            byProjectId: { ...s.byProjectId, [projectId]: { ...ps, drafts: ps.drafts.filter((d) => d.localId !== localId) } },
          }
        }),
      clearDraftsForInstance: (projectId, instanceId) =>
        set((s) => {
          const ps = s.byProjectId[projectId] ?? emptyProjectState()
          return {
            byProjectId: {
              ...s.byProjectId,
              [projectId]: { ...ps, drafts: ps.drafts.filter((d) => d.instanceId !== instanceId) },
            },
          }
        }),
      setTaskTitle: (projectId, taskTitle) =>
        set((s) => ({
          byProjectId: {
            ...s.byProjectId,
            [projectId]: { ...(s.byProjectId[projectId] ?? emptyProjectState()), taskTitle },
          },
        })),
    }),
    { name: "plm-workbench" },
  ),
)

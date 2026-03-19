import { create } from "zustand"
import { persist } from "zustand/middleware"

import { appendImageBlock, removeImageBlockAt, richText, setRichContentText, type RichContent } from "@/ui/api/richContent"

export type DraftRecallPoint = {
  localId: string
  instanceId: string
  position: string
  question: RichContent
  answer: RichContent
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
  updateDraftPosition: (projectId: string, localId: string, position: string) => void
  updateDraftText: (projectId: string, localId: string, field: "question" | "answer", text: string) => void
  appendDraftImage: (projectId: string, localId: string, field: "question" | "answer", assetId: string) => void
  removeDraftImage: (projectId: string, localId: string, field: "question" | "answer", imageIndex: number) => void
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
      updateDraftPosition: (projectId, localId, position) =>
        set((s) => {
          const ps = s.byProjectId[projectId] ?? emptyProjectState()
          const drafts = ps.drafts.map((d) => (d.localId === localId ? { ...d, position, updatedAt: Date.now() } : d))
          return { byProjectId: { ...s.byProjectId, [projectId]: { ...ps, drafts } } }
        }),
      updateDraftText: (projectId, localId, field, text) =>
        set((s) => {
          const ps = s.byProjectId[projectId] ?? emptyProjectState()
          const drafts = ps.drafts.map((d) =>
            d.localId === localId ? { ...d, [field]: setRichContentText(d[field], text), updatedAt: Date.now() } : d,
          )
          return { byProjectId: { ...s.byProjectId, [projectId]: { ...ps, drafts } } }
        }),
      appendDraftImage: (projectId, localId, field, assetId) =>
        set((s) => {
          const ps = s.byProjectId[projectId] ?? emptyProjectState()
          const drafts = ps.drafts.map((d) =>
            d.localId === localId ? { ...d, [field]: appendImageBlock(d[field], assetId), updatedAt: Date.now() } : d,
          )
          return { byProjectId: { ...s.byProjectId, [projectId]: { ...ps, drafts } } }
        }),
      removeDraftImage: (projectId, localId, field, imageIndex) =>
        set((s) => {
          const ps = s.byProjectId[projectId] ?? emptyProjectState()
          const drafts = ps.drafts.map((d) =>
            d.localId === localId
              ? { ...d, [field]: removeImageBlockAt(d[field], imageIndex), updatedAt: Date.now() }
              : d,
          )
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
    {
      name: "plm-workbench",
      version: 2,
      migrate: (persistedState: unknown, version) => {
        if (!persistedState || typeof persistedState !== "object" || version >= 2) return persistedState as WorkbenchState
        const raw = persistedState as {
          byProjectId?: Record<
            string,
            {
              roots?: unknown
              selectedInstanceId?: unknown
              taskTitle?: unknown
              drafts?: Array<Record<string, unknown>>
            }
          >
        }
        const byProjectId: WorkbenchState["byProjectId"] = {}
        for (const [projectId, projectState] of Object.entries(raw.byProjectId ?? {})) {
          byProjectId[projectId] = {
            roots: Array.isArray(projectState.roots)
              ? projectState.roots.filter((it: unknown): it is string => typeof it === "string")
              : [],
            selectedInstanceId:
              typeof projectState.selectedInstanceId === "string" ? projectState.selectedInstanceId : null,
            taskTitle: typeof projectState.taskTitle === "string" ? projectState.taskTitle : "",
            drafts: Array.isArray(projectState.drafts)
              ? projectState.drafts.map((draft) => ({
                  localId: typeof draft.localId === "string" ? draft.localId : `${Date.now()}`,
                  instanceId: typeof draft.instanceId === "string" ? draft.instanceId : "",
                  position: typeof draft.position === "string" ? draft.position : "",
                  question:
                    Array.isArray(draft.question)
                      ? (draft.question as RichContent)
                      : richText(typeof draft.questionText === "string" ? draft.questionText : ""),
                  answer:
                    Array.isArray(draft.answer)
                      ? (draft.answer as RichContent)
                      : richText(typeof draft.answerText === "string" ? draft.answerText : ""),
                  createdAt: typeof draft.createdAt === "number" ? draft.createdAt : Date.now(),
                  updatedAt: typeof draft.updatedAt === "number" ? draft.updatedAt : Date.now(),
                }))
              : [],
          }
        }
        return { byProjectId } as WorkbenchState
      },
    },
  ),
)

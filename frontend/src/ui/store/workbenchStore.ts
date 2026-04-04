import { create } from "zustand"
import { persist } from "zustand/middleware"

import { appendImageBlock, removeImageBlockAt, richText, setRichContentText, type RichContent } from "@/ui/api/richContent"

export type DraftRecallPoint = {
  localId: string
  instanceId: string | null
  position: string | null
  question: RichContent
  answer: RichContent
  createdAt: number
  updatedAt: number
}

export const WORKBENCH_GLOBAL_SCOPE_KEY = "__project__"

export function getWorkbenchTaskScopeKey(instanceId: string | null) {
  return instanceId ?? WORKBENCH_GLOBAL_SCOPE_KEY
}

type ProjectWorkbenchState = {
  roots: string[]
  selectedInstanceId: string | null
  drafts: DraftRecallPoint[]
  taskTitlesByInstanceId: Record<string, string>
}

type WorkbenchState = {
  byProjectId: Record<string, ProjectWorkbenchState>
  ensure: (projectId: string) => void
  clearAll: () => void
  resetProject: (projectId: string) => void
  setRoots: (projectId: string, roots: string[]) => void
  setSelectedInstanceId: (projectId: string, instanceId: string | null) => void
  addDraft: (projectId: string, draft: DraftRecallPoint) => void
  updateDraftPosition: (projectId: string, localId: string, position: string | null) => void
  updateDraftText: (projectId: string, localId: string, field: "question" | "answer", text: string) => void
  appendDraftImage: (projectId: string, localId: string, field: "question" | "answer", assetId: string) => void
  removeDraftImage: (projectId: string, localId: string, field: "question" | "answer", imageIndex: number) => void
  removeDraft: (projectId: string, localId: string) => void
  clearDraftsForInstance: (projectId: string, instanceId: string | null) => void
  setTaskTitle: (projectId: string, instanceId: string | null, title: string) => void
}

function emptyProjectState(): ProjectWorkbenchState {
  return { roots: [], selectedInstanceId: null, drafts: [], taskTitlesByInstanceId: {} }
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
          const scopeKey = getWorkbenchTaskScopeKey(instanceId)
          const nextTaskTitlesByInstanceId = { ...ps.taskTitlesByInstanceId }
          delete nextTaskTitlesByInstanceId[scopeKey]
          return {
            byProjectId: {
              ...s.byProjectId,
              [projectId]: {
                ...ps,
                drafts: ps.drafts.filter((d) => d.instanceId !== instanceId),
                taskTitlesByInstanceId: nextTaskTitlesByInstanceId,
              },
            },
          }
        }),
      setTaskTitle: (projectId, instanceId, taskTitle) =>
        set((s) => {
          const ps = s.byProjectId[projectId] ?? emptyProjectState()
          const scopeKey = getWorkbenchTaskScopeKey(instanceId)
          return {
            byProjectId: {
              ...s.byProjectId,
              [projectId]: {
                ...ps,
                taskTitlesByInstanceId: { ...ps.taskTitlesByInstanceId, [scopeKey]: taskTitle },
              },
            },
          }
        }),
    }),
    {
      name: "plm-workbench",
      version: 4,
      migrate: (persistedState: unknown, version) => {
        if (!persistedState || typeof persistedState !== "object" || version >= 4) return persistedState as WorkbenchState
        const raw = persistedState as {
          byProjectId?: Record<
            string,
            {
              roots?: unknown
              selectedInstanceId?: unknown
              taskTitle?: unknown
              taskTitlesByInstanceId?: unknown
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
            taskTitlesByInstanceId:
              projectState.taskTitlesByInstanceId && typeof projectState.taskTitlesByInstanceId === "object"
                ? Object.fromEntries(
                    Object.entries(projectState.taskTitlesByInstanceId as Record<string, unknown>).filter(
                      (entry): entry is [string, string] => typeof entry[0] === "string" && typeof entry[1] === "string",
                    ),
                  )
                : typeof projectState.selectedInstanceId === "string" &&
                    typeof projectState.taskTitle === "string" &&
                    projectState.taskTitle
                  ? { [projectState.selectedInstanceId]: projectState.taskTitle }
                  : {},
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
        for (const projectState of Object.values(byProjectId)) {
          projectState.taskTitlesByInstanceId = Object.fromEntries(
            Object.entries(projectState.taskTitlesByInstanceId).map(([key, value]) => [key || WORKBENCH_GLOBAL_SCOPE_KEY, value]),
          )
          projectState.drafts = projectState.drafts.map((draft) => ({
            ...draft,
            instanceId: draft.instanceId || null,
            position: draft.position || null,
          }))
        }
        return { byProjectId } as WorkbenchState
      },
    },
  ),
)

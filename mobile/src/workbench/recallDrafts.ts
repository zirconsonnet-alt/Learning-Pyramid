import type { SubmitLearningTaskItem } from "../api/learningTasks"
import {
  normalizeRichContent,
  richContentHasMeaning,
  setRichContentText,
  type RichContent,
} from "../api/richContent"
import {
  projectTypeRequiresAnchor,
  projectTypeUsesResolvableCourseAnchor,
  type ProjectType,
} from "../api/projectConfig"

export type MobileRecallDraft = {
  localId: string
  question: RichContent
  answer: RichContent
  instanceId: string | null
  position: string | null
  references: string[]
  createdAt: number
  updatedAt: number
}

export type CreateRecallDraftInput = {
  projectType: ProjectType
  instanceId: string | null
  currentMs: number
  localId: string
  now: number
}

export function createRecallDraft(input: CreateRecallDraftInput): MobileRecallDraft {
  if (!Number.isFinite(input.currentMs)) throw new Error("播放时间无效")
  const anchorMs = Math.max(0, Math.floor(input.currentMs))
  const position =
    input.projectType === "COURSE" ? `t=${anchorMs}` : input.projectType === "BOOK" ? "" : null
  return {
    localId: input.localId,
    instanceId: input.projectType === "LOOSE_POINTS" ? null : input.instanceId,
    position,
    question: [],
    answer: [],
    references: [],
    createdAt: input.now,
    updatedAt: input.now,
  }
}

function formatCourseAnchorMs(ms: number) {
  const totalSec = Math.max(0, Math.floor(ms / 1000))
  const h = Math.floor(totalSec / 3600)
  const m = Math.floor((totalSec % 3600) / 60)
  const s = totalSec % 60
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
  return `${m}:${String(s).padStart(2, "0")}`
}

function parseCourseAnchorTime(value: string): number | null {
  const trimmed = value.trim()
  const rawMs = trimmed.match(/^t=(\d+)$/i)
  if (rawMs) return Number(rawMs[1])

  const parts = trimmed.split(":")
  if (parts.length < 2 || parts.length > 3 || parts.some((part) => !/^\d+$/.test(part))) return null
  const values = parts.map(Number)
  const [h, m, s] = parts.length === 3 ? values : [0, values[0], values[1]]
  if (m > 59 || s > 59) return null
  return ((h * 3600) + (m * 60) + s) * 1000
}

export function formatCourseAnchorPositionForInput(position: string | null) {
  if (!position) return ""
  const ms = parseCourseAnchorTime(position)
  return ms === null ? position : formatCourseAnchorMs(ms)
}

export function normalizeAnchorPositionForSubmit(position: string | null, projectType: ProjectType) {
  const trimmed = position?.trim() ?? ""
  if (!trimmed) return null
  if (!projectTypeUsesResolvableCourseAnchor(projectType)) return trimmed
  const ms = parseCourseAnchorTime(trimmed) ?? (/^\d+$/.test(trimmed) ? Number(trimmed) : null)
  return ms === null ? trimmed : `t=${ms}`
}

export function getIncompleteDraftReason(draft: MobileRecallDraft, projectType: ProjectType): string | null {
  if (!richContentHasMeaning(draft.question)) return "题面不能为空"
  if (!richContentHasMeaning(draft.answer)) return "答案不能为空"
  if (projectTypeRequiresAnchor(projectType)) {
    if (!draft.instanceId?.trim()) return "缺少学习对象"
    if (!draft.position?.trim()) return "缺少锚点"
  }
  return null
}

export function buildSubmitLearningTaskItems(
  drafts: MobileRecallDraft[],
  projectType: ProjectType,
): SubmitLearningTaskItem[] {
  return drafts.map((draft) => {
    const reason = getIncompleteDraftReason(draft, projectType)
    if (reason) throw new Error(reason)
    const anchorPosition = normalizeAnchorPositionForSubmit(draft.position, projectType)
    return {
      question: normalizeRichContent(draft.question),
      answer: normalizeRichContent(draft.answer),
      anchor:
        projectTypeRequiresAnchor(projectType) && draft.instanceId && anchorPosition
          ? { instanceId: draft.instanceId, position: anchorPosition }
          : null,
      references: draft.references,
    }
  })
}

export function setDraftRichText(
  draft: MobileRecallDraft,
  field: "question" | "answer",
  text: string,
): MobileRecallDraft {
  return {
    ...draft,
    [field]: setRichContentText(draft[field], text),
  }
}

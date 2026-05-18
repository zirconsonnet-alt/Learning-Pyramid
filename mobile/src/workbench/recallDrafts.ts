import type { SubmitLearningTaskItem } from "../api/learningTasks"
import type { RichContent } from "../api/richContent"

export type MobileRecallDraft = {
  localId: string
  questionText: string
  answerText: string
  instanceId: string
  position: string
  createdAt: number
  updatedAt: number
}

export type CreateRecallDraftInput = {
  instanceId: string
  currentMs: number
  localId: string
  now: number
}

export function createRecallDraft(input: CreateRecallDraftInput): MobileRecallDraft {
  if (!Number.isFinite(input.currentMs)) throw new Error("播放时间无效")
  const anchorMs = Math.max(0, Math.floor(input.currentMs))
  return {
    localId: input.localId,
    instanceId: input.instanceId,
    position: `t=${anchorMs}`,
    questionText: "",
    answerText: "",
    createdAt: input.now,
    updatedAt: input.now,
  }
}

export function recallDraftTextToRichContent(text: string): RichContent {
  const trimmed = text.trim()
  if (!trimmed) throw new Error("文本不能为空")
  return [{ kind: "TEXT", text: trimmed }]
}

export function getIncompleteDraftReason(draft: MobileRecallDraft): string | null {
  if (!draft.questionText.trim()) return "题面不能为空"
  if (!draft.answerText.trim()) return "答案不能为空"
  if (!draft.instanceId.trim()) return "缺少学习对象"
  if (!draft.position.trim()) return "缺少锚点"
  return null
}

export function buildSubmitLearningTaskItems(drafts: MobileRecallDraft[]): SubmitLearningTaskItem[] {
  return drafts.map((draft) => {
    const reason = getIncompleteDraftReason(draft)
    if (reason) throw new Error(reason)
    return {
      question: recallDraftTextToRichContent(draft.questionText),
      answer: recallDraftTextToRichContent(draft.answerText),
      anchor: { instanceId: draft.instanceId, position: draft.position },
      references: [],
    }
  })
}

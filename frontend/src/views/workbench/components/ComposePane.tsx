import { useRef } from "react"
import { BookPlus, CircleCheckBig } from "lucide-react"

import { ApiError } from "@/ui/api/http"
import type { Instance } from "@/ui/api/instances"
import { richContentHasMeaning, richText } from "@/ui/api/richContent"
import { RichContentEditor } from "@/ui/components/RichContentEditor"
import { ContentEmptyState } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useSubmitLearningTask } from "@/ui/queries/workbench"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { useWorkbenchStore, type DraftRecallPoint } from "@/ui/store/workbenchStore"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function newLocalId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}_${Math.random().toString(16).slice(2)}`
}

function parseAnchorMs(position: string): number | null {
  const m = position.match(/^t=(\d+)$/)
  if (!m) return null
  const n = Number(m[1])
  return Number.isFinite(n) ? n : null
}

function msToClock(ms: number) {
  const totalSec = Math.floor(ms / 1000)
  const h = Math.floor(totalSec / 3600)
  const m = Math.floor((totalSec % 3600) / 60)
  const s = totalSec % 60
  const msPart = ms % 1000
  const hh = h > 0 ? `${h}:` : ""
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m)
  const ss = String(s).padStart(2, "0")
  return `${hh}${mm}:${ss}.${String(msPart).padStart(3, "0")}`
}

function isDraftComplete(draft: DraftRecallPoint) {
  return richContentHasMeaning(draft.question) && richContentHasMeaning(draft.answer)
}

export function ComposePane({
  projectId,
  selectedInstanceId,
  instance,
  currentMs,
  queueHasGate,
}: {
  projectId: string
  selectedInstanceId: string | null
  instance: Instance | null
  currentMs: number
  queueHasGate: boolean
}) {
  const ps = useWorkbenchStore((s) => s.byProjectId[projectId])
  const addDraft = useWorkbenchStore((s) => s.addDraft)
  const updateDraftText = useWorkbenchStore((s) => s.updateDraftText)
  const appendDraftImage = useWorkbenchStore((s) => s.appendDraftImage)
  const removeDraftImage = useWorkbenchStore((s) => s.removeDraftImage)
  const removeDraft = useWorkbenchStore((s) => s.removeDraft)
  const clearDraftsForInstance = useWorkbenchStore((s) => s.clearDraftsForInstance)
  const setTaskTitle = useWorkbenchStore((s) => s.setTaskTitle)
  const cardRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const questionRefs = useRef<Record<string, HTMLTextAreaElement | null>>({})
  const answerRefs = useRef<Record<string, HTMLTextAreaElement | null>>({})

  const submit = useSubmitLearningTask(projectId)

  const drafts = (ps?.drafts ?? []).filter((d) => (selectedInstanceId ? d.instanceId === selectedInstanceId : true))
  const taskTitle = ps?.taskTitle ?? ""

  function createDraft(instanceId: string, ms: number): DraftRecallPoint {
    const position = `t=${ms}`
    const now = Date.now()
    return {
      localId: newLocalId(),
      instanceId,
      position,
      question: richText(""),
      answer: richText(""),
      createdAt: now,
      updatedAt: now,
    }
  }

  function onAdd() {
    if (!selectedInstanceId) return
    const draft = createDraft(selectedInstanceId, currentMs)
    addDraft(projectId, draft)
  }

  async function onSubmit() {
    if (queueHasGate) return
    const title = taskTitle.trim()
    if (!title) return
    if (drafts.some((d) => !richContentHasMeaning(d.question) || !richContentHasMeaning(d.answer))) return
    const items = drafts.map((d) => ({
      question: d.question,
      answer: d.answer,
      anchor: { instanceId: d.instanceId, position: d.position },
    }))
    if (items.length === 0) return
    try {
      await submit.mutateAsync({ title, items })
      if (selectedInstanceId) clearDraftsForInstance(projectId, selectedInstanceId)
      showSuccessFeedback("学习任务已提交", `“${title}” 已提交，共包含 ${items.length} 个复述点。`)
    } catch (err) {
      showErrorFeedback("提交学习任务失败", formatApiError(err))
    }
  }

  function focusDraft(draft: DraftRecallPoint) {
    cardRefs.current[draft.localId]?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    })

    const questionFilled = richContentHasMeaning(draft.question)
    const answerFilled = richContentHasMeaning(draft.answer)
    const target =
      !questionFilled
        ? questionRefs.current[draft.localId]
        : !answerFilled
          ? answerRefs.current[draft.localId]
          : questionRefs.current[draft.localId]

    window.setTimeout(() => target?.focus(), 160)
  }

  return (
    <Card className="theme-card-main">
      <CardHeader className="theme-card-header flex-row items-start justify-between gap-3 space-y-0">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#edf4ff] text-primary">
            <BookPlus className="h-5 w-5" />
          </div>
          <div className="space-y-1">
            <CardTitle>复述点录入</CardTitle>
            <p className="text-sm text-muted-foreground">
              围绕当前视频持续记录锚点、问题和答案，再统一提交为学习任务。
            </p>
          </div>
        </div>
        {instance ? <div className="theme-meta">{instance.materialDisplayName}</div> : null}
        <Button onClick={onAdd} disabled={!selectedInstanceId}>
          添加复述点
        </Button>
      </CardHeader>
      <CardContent className="space-y-4 pt-5">
        {queueHasGate ? (
          <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 text-sm">
            门禁：队列非空时禁止提交学习。请先完成“复习”。
          </div>
        ) : null}

        {drafts.length > 0 ? (
          <div className="theme-canvas rounded-[1.2rem] border border-border/60 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="text-sm font-semibold text-foreground">填写进度</div>
              <div className="theme-meta shrink-0">{drafts.length} 个复述点</div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {drafts.map((draft, index) => {
                const completed = isDraftComplete(draft)
                return (
                  <button
                    key={`draft-progress-${draft.localId}`}
                    type="button"
                    onClick={() => focusDraft(draft)}
                    className={
                      completed
                        ? "flex size-10 items-center justify-center rounded-xl border border-primary/20 bg-primary text-sm font-semibold text-primary-foreground shadow-[0_12px_24px_-20px_rgba(30,58,95,0.55)] transition-transform hover:-translate-y-0.5"
                        : "flex size-10 items-center justify-center rounded-xl border border-border/80 bg-white text-sm font-semibold text-[#60748f] transition-colors hover:border-primary/25 hover:text-primary"
                    }
                    title={completed ? `第 ${index + 1} 个复述点，已填写` : `第 ${index + 1} 个复述点，尚未填写完成`}
                    aria-label={completed ? `第 ${index + 1} 个复述点，已填写` : `第 ${index + 1} 个复述点，尚未填写完成`}
                  >
                    {index + 1}
                  </button>
                )
              })}
            </div>
          </div>
        ) : null}

        {drafts.length === 0 ? (
          <ContentEmptyState
            icon={BookPlus}
            title={selectedInstanceId ? "还没有开始录入复述点" : "先选择一个视频再开始录入"}
            message={
              selectedInstanceId
                ? "点击上方“添加复述点”，就能从当前播放位置开始填写问题和答案。"
                : "请先从左侧内容目录里选择一个视频，随后就能开始录入复述点。"
            }
          />
        ) : null}

        <div className="space-y-3">
          {drafts.map((d) => {
            const ms = parseAnchorMs(d.position)
            return (
              <div
                key={d.localId}
                ref={(node) => {
                  cardRefs.current[d.localId] = node
                }}
                className="theme-status-surface rounded-[1.2rem] border border-border/70 p-4"
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="theme-meta">
                    锚点：{ms === null ? d.position : msToClock(ms)}（{d.position}）
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => removeDraft(projectId, d.localId)}>
                    删除
                  </Button>
                </div>
                <div className="mt-2 grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label>问题</Label>
                    <div
                      ref={(node) => {
                        const textarea = node?.querySelector("textarea") ?? null
                        questionRefs.current[d.localId] = textarea
                      }}
                    >
                      <RichContentEditor
                        projectId={projectId}
                        field="question"
                        value={d.question}
                        placeholder="请输入问题/提示语"
                        onTextChange={(text) => updateDraftText(projectId, d.localId, "question", text)}
                        onAppendImage={(assetId) => appendDraftImage(projectId, d.localId, "question", assetId)}
                        onRemoveImage={(imageIndex) => removeDraftImage(projectId, d.localId, "question", imageIndex)}
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label>答案</Label>
                    <div
                      ref={(node) => {
                        const textarea = node?.querySelector("textarea") ?? null
                        answerRefs.current[d.localId] = textarea
                      }}
                    >
                      <RichContentEditor
                        projectId={projectId}
                        field="answer"
                        value={d.answer}
                        placeholder="请输入答案/复述内容"
                        onTextChange={(text) => updateDraftText(projectId, d.localId, "answer", text)}
                        onAppendImage={(assetId) => appendDraftImage(projectId, d.localId, "answer", assetId)}
                        onRemoveImage={(imageIndex) => removeDraftImage(projectId, d.localId, "answer", imageIndex)}
                      />
                    </div>
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        <div className="theme-canvas grid gap-3 rounded-[1.2rem] border border-border/60 p-4">
          <div>
            <Label htmlFor="taskTitle">学习任务标题</Label>
            <Input
              id="taskTitle"
              value={taskTitle}
              onChange={(e) => setTaskTitle(projectId, e.target.value)}
              placeholder={instance ? `${instance.materialDisplayName} - 学习任务` : "例如：第一节 - 学习任务"}
            />
          </div>
          <div>
            <Button
              onClick={() => void onSubmit()}
              disabled={
                queueHasGate ||
                submit.isPending ||
                !taskTitle.trim() ||
                drafts.length === 0 ||
                drafts.some((d) => !richContentHasMeaning(d.question) || !richContentHasMeaning(d.answer))
              }
            >
              {submit.isPending ? "提交中..." : "提交学习"}
            </Button>
            {!submit.isPending &&
            drafts.length > 0 &&
            !drafts.some((d) => !richContentHasMeaning(d.question) || !richContentHasMeaning(d.answer)) ? (
              <div className="mt-2 flex items-center gap-2 text-sm text-emerald-700">
                <CircleCheckBig className="h-4 w-4" />
                所有复述点已填写完成，可以提交。
              </div>
            ) : null}
            {submit.error ? <p className="mt-2 text-sm text-destructive">{formatApiError(submit.error)}</p> : null}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

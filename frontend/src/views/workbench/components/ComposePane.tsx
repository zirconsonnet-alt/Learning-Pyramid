import { useEffect, useMemo, useRef, useState } from "react"
import { useQueries } from "@tanstack/react-query"
import { BookPlus, ChevronLeft, ChevronRight } from "lucide-react"

import { ApiError } from "@/ui/api/http"
import { listRecallPointsByLearningTaskNode } from "@/ui/api/learningTaskNodes"
import type { Instance } from "@/ui/api/instances"
import { richContentHasMeaning, richText } from "@/ui/api/richContent"
import { RichContentEditor } from "@/ui/components/RichContentEditor"
import { ContentEmptyState } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { formatInstanceReference, simplifyMaterialDisplayName } from "@/ui/displayIdentifiers"
import { useLearningTaskNodes } from "@/ui/queries/learningTasks"
import { useSubmitLearningTask } from "@/ui/queries/workbench"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { useWorkbenchStore, type DraftRecallPoint } from "@/ui/store/workbenchStore"
import { cn } from "@/ui/utils"

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

function buildRecommendedTaskTitle(instanceDisplayName: string, previousLearningCount: number) {
  return previousLearningCount <= 0 ? instanceDisplayName : `${instanceDisplayName}（${previousLearningCount + 1}）`
}

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
  const lastRecommendedTitleRef = useRef("")
  const [activeDraftId, setActiveDraftId] = useState<string | null>(null)

  const submit = useSubmitLearningTask(projectId)
  const learningTaskNodesQ = useLearningTaskNodes(projectId)

  const drafts = (ps?.drafts ?? []).filter((d) => (selectedInstanceId ? d.instanceId === selectedInstanceId : true))
  const taskTitle = selectedInstanceId ? ps?.taskTitlesByInstanceId?.[selectedInstanceId] ?? "" : ""
  const leafNodeIds = useMemo(
    () =>
      (learningTaskNodesQ.data ?? [])
        .filter((node) => node.kind === "leaf")
        .map((node) => node.nodeId),
    [learningTaskNodesQ.data],
  )
  const learningTaskRecallPointQs = useQueries({
    queries: leafNodeIds.map((nodeId) => ({
      queryKey: ["recallPointsByTaskNode", projectId, nodeId],
      queryFn: () => listRecallPointsByLearningTaskNode(projectId, nodeId),
      enabled: !!projectId && !!selectedInstanceId,
    })),
  })
  const previousLearningCountForInstance = useMemo(() => {
    if (!selectedInstanceId) return 0
    let count = 0
    for (const query of learningTaskRecallPointQs) {
      const recallPoints = query.data ?? []
      if (recallPoints.length === 0) continue
      if (recallPoints.every((rp) => rp.anchor.instanceId === selectedInstanceId)) count += 1
    }
    return count
  }, [learningTaskRecallPointQs, selectedInstanceId])
  const recommendedTaskTitle = useMemo(() => {
    if (!instance) return ""
    const instanceTitle = simplifyMaterialDisplayName(
      formatInstanceReference(instance.instanceId, instance.materialDisplayName),
      "未命名材料",
    )
    return buildRecommendedTaskTitle(instanceTitle, previousLearningCountForInstance)
  }, [instance, previousLearningCountForInstance])

  useEffect(() => {
    const previousRecommendedTitle = lastRecommendedTitleRef.current
    const trimmedTitle = taskTitle.trim()
    const shouldAdoptRecommended = !trimmedTitle || taskTitle === previousRecommendedTitle
    if (!selectedInstanceId) {
      lastRecommendedTitleRef.current = ""
      return
    }
    if (recommendedTaskTitle && shouldAdoptRecommended && taskTitle !== recommendedTaskTitle) {
      setTaskTitle(projectId, selectedInstanceId, recommendedTaskTitle)
    }
    lastRecommendedTitleRef.current = recommendedTaskTitle
  }, [projectId, recommendedTaskTitle, selectedInstanceId, setTaskTitle, taskTitle])

  function onAdd() {
    if (!selectedInstanceId) return
    const draft = createDraft(selectedInstanceId, currentMs)
    addDraft(projectId, draft)
    setActiveDraftId(draft.localId)
    window.setTimeout(() => focusDraftFields(draft), 80)
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

  const canSubmit =
    !queueHasGate &&
    !submit.isPending &&
    !!taskTitle.trim() &&
    drafts.length > 0 &&
    !drafts.some((d) => !richContentHasMeaning(d.question) || !richContentHasMeaning(d.answer))

  const completedDraftCount = drafts.filter((draft) => isDraftComplete(draft)).length
  const completionPercent = drafts.length > 0 ? Math.round((completedDraftCount / drafts.length) * 100) : 0
  const resolvedActiveDraftId = drafts.some((draft) => draft.localId === activeDraftId) ? activeDraftId : (drafts[0]?.localId ?? null)
  const activeDraftIndex = resolvedActiveDraftId ? drafts.findIndex((draft) => draft.localId === resolvedActiveDraftId) : -1
  const activeDraft = activeDraftIndex >= 0 ? drafts[activeDraftIndex] : null

  function focusDraftFields(draft: DraftRecallPoint) {
    const questionFilled = richContentHasMeaning(draft.question)
    const answerFilled = richContentHasMeaning(draft.answer)
    const target =
      !questionFilled
        ? questionRefs.current[draft.localId]
        : !answerFilled
          ? answerRefs.current[draft.localId]
          : questionRefs.current[draft.localId]

    cardRefs.current[draft.localId]?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    })
    target?.focus()
  }

  function focusDraft(draft: DraftRecallPoint) {
    setActiveDraftId(draft.localId)
    window.setTimeout(() => focusDraftFields(draft), 80)
  }

  function goToDraft(index: number) {
    const nextDraft = drafts[index]
    if (!nextDraft) return
    setActiveDraftId(nextDraft.localId)
  }

  return (
    <Card className="theme-card-main">
      <CardHeader className="theme-card-header flex-row items-start justify-between gap-3 space-y-0">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-[#e2e8f0] bg-[#f5f7fa] text-primary">
            <BookPlus className="h-5 w-5" />
          </div>
          <div>
            <CardTitle>复述点录入</CardTitle>
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
          <div className="space-y-4">
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-end gap-2">
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 rounded-full"
                    onClick={() => goToDraft(activeDraftIndex - 1)}
                    disabled={activeDraftIndex <= 0}
                    aria-label="上一张复述点卡片"
                    title="上一张"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </Button>
                  <div className="theme-meta shrink-0">
                    {activeDraftIndex >= 0 ? `${activeDraftIndex + 1} / ${drafts.length}` : `${drafts.length} 个复述点`}
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 rounded-full"
                    onClick={() => goToDraft(activeDraftIndex + 1)}
                    disabled={activeDraftIndex < 0 || activeDraftIndex >= drafts.length - 1}
                    aria-label="下一张复述点卡片"
                    title="下一张"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-[#e8edf4]">
                <div className="h-full rounded-full bg-primary transition-[width] duration-300" style={{ width: `${completionPercent}%` }} />
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {drafts.map((draft, index) => {
                const completed = isDraftComplete(draft)
                const isActive = draft.localId === resolvedActiveDraftId
                return (
                  <button
                    key={`draft-progress-${draft.localId}`}
                    type="button"
                    onClick={() => focusDraft(draft)}
                    aria-current={isActive ? "true" : undefined}
                    className={cn(
                      "flex size-10 items-center justify-center rounded-xl border text-sm font-semibold transition-all",
                      completed
                        ? "border-primary/20 bg-primary text-primary-foreground shadow-[0_12px_24px_-20px_rgba(30,58,95,0.55)] hover:-translate-y-0.5"
                        : "border-[#d9e2eb] bg-white text-[#5e738b] hover:border-primary/25 hover:text-primary",
                      isActive && "ring-2 ring-primary/25 ring-offset-2 ring-offset-background",
                    )}
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

        {drafts.length === 0 && selectedInstanceId ? (
          <div className="rounded-[1.2rem] border border-dashed border-[#dbe3ec] bg-[#fbfcfe] px-4 py-5 text-[15px] font-medium text-[#52657b]">
            暂无复述点
          </div>
        ) : null}

        {drafts.length === 0 && !selectedInstanceId ? (
          <ContentEmptyState
            icon={BookPlus}
            title="先选择一个视频再开始录入"
            message="请先从左侧内容目录里选择一个视频，随后就能开始录入复述点。"
          />
        ) : null}

        {activeDraft ? (
          <div
            key={activeDraft.localId}
            ref={(node) => {
              cardRefs.current[activeDraft.localId] = node
            }}
            className="theme-status-surface rounded-[1.2rem] border border-border/70 p-4"
          >
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex flex-wrap items-center gap-2">
                <div className="theme-meta">
                  第 {activeDraftIndex + 1} 个复述点
                </div>
                <div className="theme-meta">
                  锚点：{(() => {
                    const ms = parseAnchorMs(activeDraft.position)
                    return `${ms === null ? activeDraft.position : msToClock(ms)}（${activeDraft.position}）`
                  })()}
                </div>
              </div>
              <Button variant="ghost" size="sm" onClick={() => removeDraft(projectId, activeDraft.localId)}>
                删除
              </Button>
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>问题</Label>
                <div
                  ref={(node) => {
                    const textarea = node?.querySelector("textarea") ?? null
                    questionRefs.current[activeDraft.localId] = textarea
                  }}
                >
                  <RichContentEditor
                    projectId={projectId}
                    field="question"
                    value={activeDraft.question}
                    placeholder="请输入问题/提示语"
                    onTextChange={(text) => updateDraftText(projectId, activeDraft.localId, "question", text)}
                    onAppendImage={(assetId) => appendDraftImage(projectId, activeDraft.localId, "question", assetId)}
                    onRemoveImage={(imageIndex) => removeDraftImage(projectId, activeDraft.localId, "question", imageIndex)}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label>答案</Label>
                <div
                  ref={(node) => {
                    const textarea = node?.querySelector("textarea") ?? null
                    answerRefs.current[activeDraft.localId] = textarea
                  }}
                >
                  <RichContentEditor
                    projectId={projectId}
                    field="answer"
                    value={activeDraft.answer}
                    placeholder="请输入答案/复述内容"
                    onTextChange={(text) => updateDraftText(projectId, activeDraft.localId, "answer", text)}
                    onAppendImage={(assetId) => appendDraftImage(projectId, activeDraft.localId, "answer", assetId)}
                    onRemoveImage={(imageIndex) => removeDraftImage(projectId, activeDraft.localId, "answer", imageIndex)}
                  />
                </div>
              </div>
            </div>
          </div>
        ) : null}

        <div className="border-t border-[#e2e8ef] pt-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center">
            <Label htmlFor="taskTitle" className="shrink-0 text-sm font-medium text-[#475569] md:w-[6.5rem]">
              任务标题
            </Label>
            <Input
              id="taskTitle"
              value={taskTitle}
              onChange={(e) => {
                if (!selectedInstanceId) return
                setTaskTitle(projectId, selectedInstanceId, e.target.value)
              }}
              onKeyDown={(e) => {
                if (e.key !== "Enter" || e.nativeEvent.isComposing) return
                e.preventDefault()
                if (canSubmit) {
                  void onSubmit()
                } else if (!taskTitle.trim() && recommendedTaskTitle && selectedInstanceId) {
                  setTaskTitle(projectId, selectedInstanceId, recommendedTaskTitle)
                }
              }}
              className="h-11 flex-1 bg-white"
              placeholder={instance ? recommendedTaskTitle : "例如：第一节"}
            />
            <Button
              className="h-11 shrink-0 rounded-xl px-5 md:min-w-[7rem]"
              onClick={() => void onSubmit()}
              disabled={!canSubmit}
            >
              {submit.isPending ? "提交中..." : "提交学习"}
            </Button>
          </div>
          {submit.error ? <p className="mt-2 text-sm text-destructive">{formatApiError(submit.error)}</p> : null}
          {!submit.isPending &&
          !submit.error &&
          drafts.length > 0 &&
          !drafts.some((d) => !richContentHasMeaning(d.question) || !richContentHasMeaning(d.answer)) ? (
            <p className="mt-2 text-xs text-[#64748b]">已准备好提交，共 {drafts.length} 个复述点，已完成 {completedDraftCount} 个。</p>
          ) : null}
        </div>
      </CardContent>
    </Card>
  )
}

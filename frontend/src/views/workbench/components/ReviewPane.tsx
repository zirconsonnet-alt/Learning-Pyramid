import { useEffect, useMemo, useState } from "react"
import {
  ArrowUpRight,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  Lightbulb,
  PlayCircle,
  Undo2,
} from "lucide-react"
import { Link } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import type { RecallPoint } from "@/ui/api/review"
import {
  appendImageBlock,
  normalizeRichContent,
  removeImageBlockAt,
  richContentHasMeaning,
  richText,
  setRichContentText,
} from "@/ui/api/richContent"
import type { Instance } from "@/ui/api/instances"
import { RichContentEditor } from "@/ui/components/RichContentEditor"
import { RichContentRenderer } from "@/ui/components/RichContentRenderer"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { formatInstanceReference } from "@/ui/displayIdentifiers"
import { completeGuideWalkthroughStep } from "@/ui/guideWalkthrough/guideWalkthroughController"
import { useCommitReviewTask, useReviewBundle } from "@/ui/queries/workbench"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import {
  EMPTY_REVIEW_SESSION,
  clearPersistedReviewSession,
  loadReviewSessionStateByHeadId,
  saveReviewSessionStateByHeadId,
  type ReviewSessionState,
} from "@/ui/store/reviewSessionStore"
import { touchDailyStudyActivity } from "@/ui/store/workbenchDailyStats"
import { cn } from "@/ui/utils"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
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
  const hh = h > 0 ? `${h}:` : ""
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m)
  const ss = String(s).padStart(2, "0")
  return `${hh}${mm}:${ss}`
}

function simplifyMaterialName(value: string) {
  const normalized = value.trim()
  if (!normalized) return "内容待确认"
  const leaf = normalized.split("/").at(-1)?.split("\\").at(-1) ?? normalized
  return leaf.replace(/\.[a-z0-9]+$/i, "") || leaf
}

function formatAnchorLabel(instanceId: string, displayName: string | null | undefined, position: string) {
  const title = simplifyMaterialName(formatInstanceReference(instanceId, displayName))
  const ms = parseAnchorMs(position)
  return `${title} · ${ms === null ? position : msToClock(ms)}`
}

const REVIEW_ACTIVITY_WINDOW_MS = 75_000

function isRecallPoint(value: RecallPoint | undefined): value is RecallPoint {
  return Boolean(value)
}

export function ReviewPane({
  projectId,
  headId,
  instances,
  onOpenAnchor,
}: {
  projectId: string
  headId: string
  instances: Instance[]
  onOpenAnchor?: (a: { instanceId: string; position: string }) => void
}) {
  const { reviewTaskQ, rangeQ, recallPointQs } = useReviewBundle(projectId, headId)
  const commit = useCommitReviewTask(projectId)

  function touchReviewActivity() {
    touchDailyStudyActivity(projectId, "review", REVIEW_ACTIVITY_WINDOW_MS)
  }

  const [sessionStateByHeadId, setSessionStateByHeadId] = useState<Record<string, ReviewSessionState>>(() =>
    loadReviewSessionStateByHeadId(projectId),
  )
  const sessionState = sessionStateByHeadId[headId] ?? EMPTY_REVIEW_SESSION
  const answers = sessionState.answers
  const showAnswer = sessionState.showAnswer
  const writtenAnswerDrafts = sessionState.writtenAnswerDrafts
  const submittedWrittenAnswers = sessionState.submittedWrittenAnswers
  const skippedWrittenAnswers = sessionState.skippedWrittenAnswers
  const insightDrafts = sessionState.insightDrafts
  const showInsightEditor = sessionState.showInsightEditor

  useEffect(() => {
    setSessionStateByHeadId(loadReviewSessionStateByHeadId(projectId))
  }, [projectId])

  function updateSessionState(updater: (current: ReviewSessionState) => ReviewSessionState) {
    setSessionStateByHeadId((state) => {
      const current = state[headId] ?? EMPTY_REVIEW_SESSION
      const nextState = {
        ...state,
        [headId]: updater(current),
      }
      saveReviewSessionStateByHeadId(projectId, nextState)
      return nextState
    })
  }

  function hasUnlockedAnswer(rpId: string) {
    return submittedWrittenAnswers[rpId] !== undefined || skippedWrittenAnswers[rpId] === true
  }

  const loading =
    reviewTaskQ.isLoading ||
    rangeQ.isLoading ||
    recallPointQs.some((q) => q.isLoading) ||
    !reviewTaskQ.data ||
    !rangeQ.data
  const error = reviewTaskQ.error || rangeQ.error || recallPointQs.find((q) => q.error)?.error
  const recallPointIds = rangeQ.data?.recallPointIds ?? []
  const totalCount = recallPointIds.length
  const answeredCount = recallPointIds.filter((id) => answers[id] !== undefined).length
  const rememberedCount = recallPointIds.filter((id) => answers[id] === 1).length
  const forgottenCount = recallPointIds.filter((id) => answers[id] === 0).length
  const completionPercent = totalCount > 0 ? Math.round((answeredCount / totalCount) * 100) : 0
  const canSubmit = totalCount > 0 && recallPointIds.every((id) => answers[id] !== undefined)

  const recallPointById = useMemo(
    () =>
      Object.fromEntries(
        recallPointQs
          .map((query) => query.data)
          .filter(isRecallPoint)
          .map((item) => [item.recallPointId, item]),
      ),
    [recallPointQs],
  )
  const resolvedActiveRecallPointId = recallPointIds.includes(sessionState.activeRecallPointId ?? "")
    ? sessionState.activeRecallPointId
    : (recallPointIds[0] ?? null)
  const activeRecallPointIndex = resolvedActiveRecallPointId ? recallPointIds.findIndex((id) => id === resolvedActiveRecallPointId) : -1
  const activeRecallPoint = resolvedActiveRecallPointId ? recallPointById[resolvedActiveRecallPointId] ?? null : null

  useEffect(() => {
    if (!resolvedActiveRecallPointId || totalCount <= 0 || loading || error) return
    touchReviewActivity()
  }, [error, loading, resolvedActiveRecallPointId, totalCount])

  function chooseAnswer(rpId: string, nextValue: 0 | 1) {
    if (!hasUnlockedAnswer(rpId)) return
    touchReviewActivity()
    updateSessionState((current) => ({
      ...current,
      answers: { ...current.answers, [rpId]: nextValue },
    }))
  }

  function setActiveRecallPoint(rpId: string) {
    touchReviewActivity()
    updateSessionState((current) => ({
      ...current,
      activeRecallPointId: rpId,
    }))
  }

  function goToRecallPoint(index: number) {
    const nextId = recallPointIds[index]
    if (!nextId) return
    setActiveRecallPoint(nextId)
  }

  function chooseAnswerAndAdvance(rpId: string, nextValue: 0 | 1) {
    chooseAnswer(rpId, nextValue)
    completeGuideWalkthroughStep("mark-review-result")
    if (activeRecallPointIndex >= 0 && activeRecallPointIndex < totalCount - 1) {
      goToRecallPoint(activeRecallPointIndex + 1)
    }
  }

  function updateWrittenAnswerText(rpId: string, text: string) {
    updateSessionState((current) => ({
      ...current,
      writtenAnswerDrafts: {
        ...current.writtenAnswerDrafts,
        [rpId]: setRichContentText(current.writtenAnswerDrafts[rpId] ?? [], text),
      },
    }))
  }

  function appendWrittenAnswerImage(rpId: string, assetId: string) {
    touchReviewActivity()
    updateSessionState((current) => ({
      ...current,
      writtenAnswerDrafts: {
        ...current.writtenAnswerDrafts,
        [rpId]: appendImageBlock(current.writtenAnswerDrafts[rpId] ?? [], assetId),
      },
    }))
  }

  function removeWrittenAnswerImage(rpId: string, imageIndex: number) {
    touchReviewActivity()
    updateSessionState((current) => ({
      ...current,
      writtenAnswerDrafts: {
        ...current.writtenAnswerDrafts,
        [rpId]: removeImageBlockAt(current.writtenAnswerDrafts[rpId] ?? [], imageIndex),
      },
    }))
  }

  function submitWrittenAnswer(rpId: string) {
    const submittedContent = normalizeRichContent(writtenAnswerDrafts[rpId] ?? [])
    if (!richContentHasMeaning(submittedContent)) return
    touchReviewActivity()
    updateSessionState((current) => {
      const nextSkippedWrittenAnswers = { ...current.skippedWrittenAnswers }
      delete nextSkippedWrittenAnswers[rpId]
      return {
        ...current,
        writtenAnswerDrafts: {
          ...current.writtenAnswerDrafts,
          [rpId]: submittedContent,
        },
        submittedWrittenAnswers: {
          ...current.submittedWrittenAnswers,
          [rpId]: submittedContent,
        },
        showAnswer: { ...current.showAnswer, [rpId]: true },
        skippedWrittenAnswers: nextSkippedWrittenAnswers,
      }
    })
    completeGuideWalkthroughStep("submit-review-answer")
  }

  function skipWrittenAnswer(rpId: string) {
    touchReviewActivity()
    updateSessionState((current) => ({
      ...current,
      showAnswer: { ...current.showAnswer, [rpId]: true },
      skippedWrittenAnswers: {
        ...current.skippedWrittenAnswers,
        [rpId]: true,
      },
    }))
    completeGuideWalkthroughStep("submit-review-answer")
  }

  function toggleInsightEditor(rpId: string, hasDraftInsight: boolean) {
    touchReviewActivity()
    updateSessionState((current) => ({
      ...current,
      showInsightEditor: {
        ...current.showInsightEditor,
        [rpId]: !(current.showInsightEditor[rpId] || hasDraftInsight),
      },
    }))
  }

  function updateInsightDraft(rpId: string, value: string) {
    touchReviewActivity()
    updateSessionState((current) => ({
      ...current,
      insightDrafts: {
        ...current.insightDrafts,
        [rpId]: value,
      },
    }))
  }

  function clearAnswer(rpId: string) {
    touchReviewActivity()
    updateSessionState((current) => {
      const nextAnswers = { ...current.answers }
      delete nextAnswers[rpId]
      return {
        ...current,
        answers: nextAnswers,
      }
    })
  }

  async function onSubmit() {
    if (!rangeQ.data) return
    const canRecall = rangeQ.data.recallPointIds.map((id) => answers[id])
    if (canRecall.some((value) => value === undefined)) return
    const appendedInsights = rangeQ.data.recallPointIds.flatMap((rpId) => {
      const text = insightDrafts[rpId]?.trim()
      return text ? [{ recallPointId: rpId, insight: richText(text) }] : []
    })

    try {
      touchReviewActivity()
      await commit.mutateAsync({
        reviewTaskId: headId,
        canRecall: canRecall as number[],
        appendedInsights,
      })
      clearPersistedReviewSession(projectId, headId)
      setSessionStateByHeadId((state) => {
        const nextState = { ...state }
        delete nextState[headId]
        return nextState
      })
      showSuccessFeedback(
        "复习结果已提交",
        `本轮已提交 ${totalCount} 题，其中记得 ${rememberedCount} 题，不记得 ${forgottenCount} 题${
          appendedInsights.length > 0 ? `，并追加了 ${appendedInsights.length} 条理解。` : "。"
        }`,
      )
      completeGuideWalkthroughStep("submit-review")
    } catch (err) {
      showErrorFeedback("提交复习结果失败", formatApiError(err))
    }
  }

  return (
    <Card data-guide-tour="review-pane" className="theme-card-main">
      <CardHeader className="theme-card-header flex-col gap-4 space-y-0 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="theme-icon-surface h-10 w-10">
            <ClipboardCheck className="h-5 w-5" />
          </div>
          <div>
            <CardTitle>复习任务</CardTitle>
          </div>
        </div>

        <div className="min-w-[180px] space-y-2">
          <div className="flex items-center justify-between gap-3 text-sm">
            <span className="theme-meta">{totalCount} 题</span>
            <span className="font-medium text-[color:var(--theme-subtle-text)]">
              已完成 {answeredCount} / {totalCount}
            </span>
          </div>
          <div className="theme-progress-track h-2 overflow-hidden rounded-full">
            <div
              className="theme-progress-fill h-full rounded-full transition-[width] duration-300"
              style={{ width: `${completionPercent}%` }}
            />
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 pt-5">
        {loading ? <p className="text-sm text-muted-foreground">加载复习内容中...</p> : null}
        {error ? <p className="text-sm text-destructive">{formatApiError(error)}</p> : null}

        {rangeQ.data ? (
          <div className="space-y-3">
            <div className="space-y-4">
              <div className="sr-only">
                作答进度：已作答 {answeredCount} / {totalCount}，当前是第 {Math.max(activeRecallPointIndex + 1, 0)} 题。
              </div>
              <div className="flex flex-wrap gap-2">
                {recallPointIds.map((rpId, index) => {
                  const chosen = answers[rpId]
                  const isRemembered = chosen === 1
                  const isForgotten = chosen === 0
                  const isActive = rpId === resolvedActiveRecallPointId
                  return (
                    <button
                      key={`review-progress-${rpId}`}
                      type="button"
                      onClick={() => setActiveRecallPoint(rpId)}
                      aria-current={isActive ? "true" : undefined}
                      className={cn(
                        "flex size-10 items-center justify-center rounded-xl border text-sm font-semibold transition-all",
                        isRemembered && "border-emerald-200 bg-emerald-600 text-white shadow-[0_12px_24px_-20px_rgba(5,150,105,0.5)]",
                        isForgotten && "border-amber-200 bg-amber-50 text-amber-700",
                        chosen === undefined && "[border-color:var(--theme-soft-border)] [background:var(--theme-soft-bg)] text-[color:var(--theme-subtle-text)] hover:border-primary/25 hover:text-primary",
                        isActive && "ring-2 ring-primary/25 ring-offset-2 ring-offset-background",
                      )}
                      title={
                        isRemembered
                          ? `第 ${index + 1} 题，已标记为记得`
                          : isForgotten
                            ? `第 ${index + 1} 题，已标记为不记得`
                            : `第 ${index + 1} 题，尚未作答`
                      }
                    >
                      {index + 1}
                    </button>
                  )
                })}
              </div>
            </div>

            {activeRecallPoint ? (() => {
              const rpId = activeRecallPoint.recallPointId
              const chosen = answers[rpId]
              const isRemembered = chosen === 1
              const isForgotten = chosen === 0
              const writtenAnswerDraft = writtenAnswerDrafts[rpId] ?? []
              const submittedWrittenAnswer = submittedWrittenAnswers[rpId]
              const isSkippedWrittenAnswer = skippedWrittenAnswers[rpId] === true
              const hasSubmittedWrittenAnswer = submittedWrittenAnswer !== undefined || isSkippedWrittenAnswer
              const canSubmitWrittenAnswer = richContentHasMeaning(writtenAnswerDraft)
              const answerVisible = hasSubmittedWrittenAnswer && (showAnswer[rpId] ?? false)
              const draftInsight = insightDrafts[rpId] ?? ""
              const hasDraftInsight = draftInsight.trim().length > 0
              const insightEditorVisible = showInsightEditor[rpId] || hasDraftInsight
              const hasNextRecallPoint = activeRecallPointIndex >= 0 && activeRecallPointIndex < totalCount - 1
              const activeAnchor = activeRecallPoint.anchor
              const inst = activeAnchor ? instances.find((i) => i.instanceId === activeAnchor.instanceId) ?? null : null
              const anchorLabel = activeAnchor
                ? formatAnchorLabel(
                    activeAnchor.instanceId,
                    inst?.materialDisplayName,
                    activeAnchor.position,
                  )
                : "未绑定锚点"

              return (
                <div className="grid gap-3">
                  <div key={rpId} className="relative overflow-visible">
                    <div className="sr-only" aria-live="polite">
                      {activeRecallPointIndex >= 0 ? `第 ${activeRecallPointIndex + 1} 题 / 共 ${totalCount} 题` : `${totalCount} 题`}
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="absolute inset-y-0 -left-4 z-10 h-auto w-4 rounded-none border-0 bg-transparent p-0 text-[color:var(--theme-subtle-text)] shadow-none outline-none hover:bg-transparent hover:text-foreground focus-visible:ring-0 focus-visible:ring-offset-0 sm:-left-5 sm:w-5"
                      onClick={() => goToRecallPoint(activeRecallPointIndex - 1)}
                      disabled={activeRecallPointIndex <= 0}
                      aria-label="上一题"
                      title="上一题"
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="absolute inset-y-0 -right-4 z-10 h-auto w-4 rounded-none border-0 bg-transparent p-0 text-[color:var(--theme-subtle-text)] shadow-none outline-none hover:bg-transparent hover:text-foreground focus-visible:ring-0 focus-visible:ring-offset-0 sm:-right-5 sm:w-5"
                      onClick={() => goToRecallPoint(activeRecallPointIndex + 1)}
                      disabled={activeRecallPointIndex < 0 || activeRecallPointIndex >= totalCount - 1}
                      aria-label="下一题"
                      title="下一题"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>

                    <div className="theme-status-surface rounded-[1.15rem] border border-[color:var(--theme-status-border)] px-4 py-4 sm:px-5">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                            <span>第 {activeRecallPointIndex + 1} 题</span>
                            {isRemembered ? (
                              <span className="rounded-full bg-emerald-50 px-2 py-0.5 tracking-[0.08em] text-emerald-700">已标记为记得</span>
                            ) : null}
                            {isForgotten ? (
                              <span className="rounded-full bg-amber-50 px-2 py-0.5 tracking-[0.08em] text-amber-700">已标记为不记得</span>
                            ) : null}
                          </div>

                          <Link
                            to={`/p/${projectId}/recall-points/${rpId}`}
                            className="group mt-2 block rounded-2xl px-2 py-1 -mx-2 -my-1 transition hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                            title="打开复述点详情"
                          >
                            <div className="text-[15px] font-semibold leading-6 text-foreground transition group-hover:text-primary">
                              <RichContentRenderer projectId={projectId} value={activeRecallPoint.question} />
                            </div>
                            <div className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-primary/85">
                              查看复述点详情
                              <ArrowUpRight className="h-3.5 w-3.5" />
                            </div>
                          </Link>

                          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                            {activeAnchor ? (
                              <Link
                                to={`/p/${projectId}/instances/${activeAnchor.instanceId}`}
                                className="theme-pill-default rounded-full px-2.5 py-1 font-medium transition hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                                title="打开视频实例详情"
                              >
                                {anchorLabel}
                              </Link>
                            ) : (
                              <span className="theme-pill-default rounded-full px-2.5 py-1 font-medium">
                                {anchorLabel}
                              </span>
                            )}
                            {activeRecallPoint.insights.length > 0 ? (
                              <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 font-medium text-amber-700">
                                <Lightbulb className="h-3.5 w-3.5" />
                                已有 {activeRecallPoint.insights.length} 条理解
                              </span>
                            ) : null}
                          </div>
                        </div>
                      </div>

                      <div className="mt-3 flex flex-wrap gap-2">
                        {onOpenAnchor && activeAnchor ? (
                          <Button
                            variant="outline"
                            size="sm"
                            className="rounded-full"
                            onClick={() => {
                              touchReviewActivity()
                              onOpenAnchor(activeAnchor)
                            }}
                          >
                            <PlayCircle className="h-4 w-4" />
                            回到锚点
                          </Button>
                        ) : null}

                        <Button variant="ghost" size="sm" className="rounded-full" onClick={() => toggleInsightEditor(rpId, hasDraftInsight)}>
                          <Lightbulb className="h-4 w-4" />
                          {insightEditorVisible ? "收起理解" : "追加理解"}
                        </Button>
                      </div>

                      <div className="mt-4">
                        <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">你的答案</div>
                        <RichContentEditor
                          projectId={projectId}
                          field="answer"
                          value={writtenAnswerDraft}
                          disabled={hasSubmittedWrittenAnswer}
                          placeholder="先写下自己的答案，提交后会自动展开标准答案。"
                          onTextChange={(text) => updateWrittenAnswerText(rpId, text)}
                          onAppendImage={(assetId) => appendWrittenAnswerImage(rpId, assetId)}
                          onRemoveImage={(imageIndex) => removeWrittenAnswerImage(rpId, imageIndex)}
                          onUserActivity={touchReviewActivity}
                          textareaClassName="min-h-[140px] resize-y rounded-xl [border-color:var(--theme-subtle-border)] [background:var(--theme-subtle-bg)] text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/15 disabled:cursor-not-allowed disabled:opacity-75"
                          imageClassName="h-28 w-full max-w-[220px] rounded-xl border [border-color:var(--theme-subtle-border)] [background:var(--theme-subtle-bg)] object-cover"
                        />
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          {hasSubmittedWrittenAnswer ? (
                            <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                              <CheckCircle2 className="h-4 w-4" />
                              {isSkippedWrittenAnswer ? "已跳过" : "已提交答案"}
                            </span>
                          ) : (
                            <>
                              <Button
                                data-guide-tour="submit-review-answer-button"
                                type="button"
                                variant="default"
                                size="sm"
                                className="rounded-xl"
                                onClick={() => submitWrittenAnswer(rpId)}
                                disabled={!canSubmitWrittenAnswer}
                              >
                                提交答案
                              </Button>
                              <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                className="rounded-xl"
                                onClick={() => skipWrittenAnswer(rpId)}
                              >
                                跳过
                              </Button>
                            </>
                          )}
                          {hasSubmittedWrittenAnswer ? (
                            <span className="text-xs text-muted-foreground">
                              {isSkippedWrittenAnswer ? "已跳过，已展开答案，可判断记忆状态。" : "已提交，已展开答案，可判断记忆状态。"}
                            </span>
                          ) : null}
                        </div>
                      </div>

                      {answerVisible ? (
                        <div className="theme-canvas mt-3 rounded-2xl border border-[color:var(--theme-soft-border)] p-3 text-sm">
                          <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">答案</div>
                          <RichContentRenderer projectId={projectId} value={activeRecallPoint.answer} />
                        </div>
                      ) : null}

                      {insightEditorVisible ? (
                        <div className="theme-soft-surface mt-3 p-3">
                          <textarea
                            value={draftInsight}
                            onChange={(event) => updateInsightDraft(rpId, event.target.value)}
                            onFocus={touchReviewActivity}
                            rows={3}
                            placeholder="补充这道复习点的新理解、易错点、联想线索或自己的话解释。"
                            className="min-h-[96px] w-full resize-y border-0 bg-transparent p-0 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:ring-0"
                          />
                        </div>
                      ) : null}

                      <div data-guide-tour="review-memory-choice-buttons" className="mt-4 flex flex-wrap items-center gap-2">
                        <Button
                          variant={isRemembered ? "default" : "outline"}
                          size="sm"
                          className={cn("min-w-[96px] rounded-full", isRemembered ? "bg-emerald-600 hover:bg-emerald-700" : "")}
                          onClick={() => chooseAnswerAndAdvance(rpId, 1)}
                          disabled={!hasSubmittedWrittenAnswer}
                        >
                          记得
                        </Button>
                        <Button
                          variant={isForgotten ? "secondary" : "outline"}
                          size="sm"
                          className={cn(
                            "min-w-[96px] rounded-full",
                            isForgotten ? "border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100" : "",
                          )}
                          onClick={() => chooseAnswerAndAdvance(rpId, 0)}
                          disabled={!hasSubmittedWrittenAnswer}
                        >
                          不记得
                        </Button>
                        {chosen !== undefined ? (
                          <Button variant="ghost" size="sm" className="rounded-full text-muted-foreground" onClick={() => clearAnswer(rpId)}>
                            <Undo2 className="h-4 w-4" />
                            撤销选择
                          </Button>
                        ) : null}
                      </div>

                      {chosen !== undefined ? (
                        <div
                          className={cn(
                            "mt-3 flex items-center gap-2 rounded-2xl px-3 py-2 text-xs font-medium",
                            isRemembered ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700",
                          )}
                        >
                          <CheckCircle2 className="h-4 w-4" />
                          {isRemembered
                            ? hasNextRecallPoint
                              ? "这题已标记为“记得”，作答后会自动切到下一题。"
                              : "这题已标记为“记得”，已经是最后一题，可以直接提交。"
                            : hasNextRecallPoint
                              ? "这题已标记为“不记得”，作答后会自动切到下一题。"
                              : "这题已标记为“不记得”，已经是最后一题，可以直接提交。"}
                        </div>
                      ) : null}
                    </div>
                  </div>
                </div>
              )
            })() : (
              <div className="theme-subtle-surface border-dashed px-4 py-6 text-sm text-muted-foreground">
                当前题目载入中...
              </div>
            )}
          </div>
        ) : null}

        {rangeQ.data ? (
          <div className="flex flex-col items-center gap-2 pt-2">
            <Button data-guide-tour="submit-review-button" onClick={() => void onSubmit()} disabled={commit.isPending || !canSubmit} className="min-w-[140px]">
              {commit.isPending ? "提交中..." : "提交本轮复习"}
            </Button>
            {commit.error ? <p className="text-center text-sm text-destructive">{formatApiError(commit.error)}</p> : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

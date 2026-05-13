import { useMemo, useState } from "react"
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  Lightbulb,
  SlidersHorizontal,
  Undo2,
} from "lucide-react"
import { Link, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import type { ScopedProjectRef } from "@/ui/api/projectScope"
import { type RecallPoint, type ReviewRecommendationItem } from "@/ui/api/review"
import { normalizeRichContent, richContentHasMeaning, setRichContentText, type RichContent } from "@/ui/api/richContent"
import { RichContentRenderer } from "@/ui/components/RichContentRenderer"
import { RichContentEditor } from "@/ui/components/RichContentEditor"
import { ContentEmptyState, ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/ui/components/ui/dialog"
import { Input } from "@/ui/components/ui/input"
import { formatInstanceReference } from "@/ui/displayIdentifiers"
import { buildScopedProjectPath } from "@/ui/projectPaths"
import { useProject } from "@/ui/queries/projects"
import { useAllReviewRecommendations } from "@/ui/queries/reviewRecommendations"
import { cn } from "@/ui/utils"

type SessionAnswer = "remembered" | "forgotten"

type ReviewWorkspaceEntry = {
  recallPoint: RecallPoint
  rankLabel: string | null
  recommendation: ReviewRecommendationItem
}

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function formatDateTime(value: string | null) {
  if (!value) return "未复习"
  const dt = new Date(value)
  return Number.isNaN(dt.getTime()) ? value : dt.toLocaleString()
}

function formatReviewResult(value: "CAN_RECALL" | "CANNOT_RECALL" | null) {
  if (value === "CAN_RECALL") return "最近一次：会"
  if (value === "CANNOT_RECALL") return "最近一次：不会"
  return "还没有正式复习记录"
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

function formatStatValue(value: number | null, suffix = "") {
  return value === null ? "-" : `${value.toFixed(1)}${suffix}`
}

function formatAnchorLabel(recallPoint: RecallPoint) {
  if (!recallPoint.anchor) return "未绑定锚点"
  return `${formatInstanceReference(recallPoint.anchor.instanceId)} · ${recallPoint.anchor.position}`
}

function clampThresholdPercent(value: number) {
  if (!Number.isFinite(value)) return 70
  return Math.max(1, Math.min(99, Math.round(value)))
}

function StatBlock({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="min-w-0 border-t border-border/60 pt-3 sm:border-l sm:border-t-0 sm:pl-4 sm:first:border-l-0">
      <div className="text-xs font-medium text-muted-foreground">{label}</div>
      <div className="mt-1 truncate text-2xl font-semibold text-foreground">{value}</div>
      <div className="mt-1 truncate text-xs text-muted-foreground">{detail}</div>
    </div>
  )
}

export function ReviewRecommendationsPage() {
  const { subjectId = "", scopedProjectId } = useParams()
  const pid = scopedProjectId ?? ""
  const projectScope: ScopedProjectRef | null = subjectId && pid ? { subjectId, scopedProjectId: pid } : null
  const [selectedRecallPointId, setSelectedRecallPointId] = useState<string | null>(null)
  const [revealedAnswerIds, setRevealedAnswerIds] = useState<Record<string, boolean>>({})
  const [sessionAnswers, setSessionAnswers] = useState<Record<string, SessionAnswer>>({})
  const [writtenAnswerDrafts, setWrittenAnswerDrafts] = useState<Record<string, RichContent>>({})
  const [submittedWrittenAnswers, setSubmittedWrittenAnswers] = useState<Record<string, boolean>>({})
  const [insightDrafts, setInsightDrafts] = useState<Record<string, string>>({})
  const [showInsightEditor, setShowInsightEditor] = useState<Record<string, boolean>>({})
  const [workspaceRecommendationsByProjectId, setWorkspaceRecommendationsByProjectId] = useState<Record<string, ReviewRecommendationItem[]>>({})
  const [recommendationThresholdPercent, setRecommendationThresholdPercent] = useState(70)
  const [thresholdDraft, setThresholdDraft] = useState("70")
  const [thresholdDialogOpen, setThresholdDialogOpen] = useState(false)
  const allReviewRecommendationsQ = useAllReviewRecommendations(projectScope)
  const { projectTitle } = useProject(projectScope)
  const workspaceRecommendations = useMemo(
    () => workspaceRecommendationsByProjectId[pid] ?? [],
    [pid, workspaceRecommendationsByProjectId],
  )
  const effectiveWorkspaceRecommendations = useMemo(() => {
    if (workspaceRecommendations.length > 0 || !allReviewRecommendationsQ.data) return workspaceRecommendations
    const threshold = recommendationThresholdPercent / 100
    return allReviewRecommendationsQ.data.items.filter((item) => item.estimatedMemoryStrength < threshold)
  }, [allReviewRecommendationsQ.data, recommendationThresholdPercent, workspaceRecommendations])

  const reviewWorkspaceEntries = useMemo<ReviewWorkspaceEntry[]>(
    () =>
      effectiveWorkspaceRecommendations.map((item, index) => ({
        recallPoint: item.recallPoint,
        rankLabel: `#${index + 1}`,
        recommendation: item,
      })),
    [effectiveWorkspaceRecommendations],
  )
  const reviewWorkspaceIdSet = useMemo(
    () => new Set(reviewWorkspaceEntries.map((entry) => entry.recallPoint.recallPointId)),
    [reviewWorkspaceEntries],
  )
  const answeredRecallPointIds = useMemo(
    () => new Set(Object.keys(sessionAnswers).filter((recallPointId) => sessionAnswers[recallPointId] !== undefined)),
    [sessionAnswers],
  )
  const activeRecallPointId =
    selectedRecallPointId && reviewWorkspaceIdSet.has(selectedRecallPointId)
      ? selectedRecallPointId
      : reviewWorkspaceEntries[0]?.recallPoint.recallPointId ?? null
  const activeEntry = reviewWorkspaceEntries.find((entry) => entry.recallPoint.recallPointId === activeRecallPointId) ?? null
  const activeReviewEntryIndex = activeEntry
    ? reviewWorkspaceEntries.findIndex((entry) => entry.recallPoint.recallPointId === activeEntry.recallPoint.recallPointId)
    : -1
  const answeredCount = reviewWorkspaceEntries.filter((entry) => sessionAnswers[entry.recallPoint.recallPointId] !== undefined).length
  const completionPercent = reviewWorkspaceEntries.length > 0 ? Math.round((answeredCount / reviewWorkspaceEntries.length) * 100) : 0

  if (!subjectId || !pid) {
    return (
      <div className="space-y-4">
        <ContentNotice
          title="当前页面缺少项目上下文"
          message="当前链接缺少项目信息。请先返回项目列表，再重新进入推荐复习。"
          action={
            <Button asChild>
              <Link to="/subjects">返回学科中心</Link>
            </Button>
          }
        />
      </div>
    )
  }

  function applyRecommendationThreshold() {
    if (!allReviewRecommendationsQ.data) return
    const nextThresholdPercent = clampThresholdPercent(Number(thresholdDraft))
    const threshold = nextThresholdPercent / 100
    const answeredEntries = effectiveWorkspaceRecommendations.filter((item) => answeredRecallPointIds.has(item.recallPoint.recallPointId))
    const answeredIds = new Set(answeredEntries.map((item) => item.recallPoint.recallPointId))
    const nextUnansweredEntries = allReviewRecommendationsQ.data.items.filter(
      (item) => !answeredIds.has(item.recallPoint.recallPointId) && item.estimatedMemoryStrength < threshold,
    )

    setRecommendationThresholdPercent(nextThresholdPercent)
    setThresholdDraft(String(nextThresholdPercent))
    setWorkspaceRecommendationsByProjectId((current) => ({ ...current, [pid]: [...answeredEntries, ...nextUnansweredEntries] }))
    setThresholdDialogOpen(false)
  }

  function chooseSessionAnswer(recallPointId: string, answer: SessionAnswer) {
    if (!submittedWrittenAnswers[recallPointId]) return
    setRevealedAnswerIds((current) => ({ ...current, [recallPointId]: true }))
    setSessionAnswers((current) => ({ ...current, [recallPointId]: answer }))
    if (activeReviewEntryIndex >= 0 && activeReviewEntryIndex < reviewWorkspaceEntries.length - 1) {
      goToReviewEntry(activeReviewEntryIndex + 1)
    }
  }

  function updateWrittenAnswerText(recallPointId: string, text: string) {
    setWrittenAnswerDrafts((current) => ({
      ...current,
      [recallPointId]: setRichContentText(current[recallPointId] ?? [], text),
    }))
  }

  function appendWrittenAnswerImage(recallPointId: string) {
    setWrittenAnswerDrafts((current) => current)
    void recallPointId
  }

  function removeWrittenAnswerImage(recallPointId: string) {
    setWrittenAnswerDrafts((current) => current)
    void recallPointId
  }

  function submitWrittenAnswer(recallPointId: string) {
    const submittedContent = normalizeRichContent(writtenAnswerDrafts[recallPointId] ?? [])
    if (!richContentHasMeaning(submittedContent)) return
    setWrittenAnswerDrafts((current) => ({ ...current, [recallPointId]: submittedContent }))
    setSubmittedWrittenAnswers((current) => ({ ...current, [recallPointId]: true }))
    setRevealedAnswerIds((current) => ({ ...current, [recallPointId]: true }))
  }

  function skipWrittenAnswer(recallPointId: string) {
    setSubmittedWrittenAnswers((current) => ({ ...current, [recallPointId]: true }))
    setRevealedAnswerIds((current) => ({ ...current, [recallPointId]: true }))
  }

  function toggleInsightEditor(recallPointId: string) {
    setShowInsightEditor((current) => ({ ...current, [recallPointId]: !current[recallPointId] }))
  }

  function updateInsightDraft(recallPointId: string, value: string) {
    setInsightDrafts((current) => ({ ...current, [recallPointId]: value }))
  }

  function clearSessionAnswer(recallPointId: string) {
    setSessionAnswers((current) => {
      const next = { ...current }
      delete next[recallPointId]
      return next
    })
  }

  function goToReviewEntry(index: number) {
    const next = reviewWorkspaceEntries[index]
    if (!next) return
    setSelectedRecallPointId(next.recallPoint.recallPointId)
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-lg font-semibold">推荐复习</h1>
          <p className="text-sm text-muted-foreground">
            项目：<span className="font-medium text-foreground">{projectTitle}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" asChild>
            <Link to={buildScopedProjectPath(subjectId, pid, "/workbench")}>返回工作台</Link>
          </Button>
          <Button variant="outline" onClick={() => setThresholdDialogOpen(true)} disabled={allReviewRecommendationsQ.isFetching}>
            <SlidersHorizontal className="h-4 w-4" />
            更新推荐阈值
          </Button>
        </div>
      </div>

      {allReviewRecommendationsQ.isLoading ? <LoadingNotice title="正在加载推荐复习" message="正在根据复习历史和掌握概率计算当前批次。" /> : null}
      {allReviewRecommendationsQ.error ? <ErrorNotice title="推荐复习加载失败" message={formatApiError(allReviewRecommendationsQ.error)} /> : null}
      {!allReviewRecommendationsQ.isLoading && !allReviewRecommendationsQ.error && allReviewRecommendationsQ.data && allReviewRecommendationsQ.data.totalCount === 0 ? (
        <ContentEmptyState
          title="当前没有推荐复习"
          message="可以回到工作台继续生成复述点。"
        />
      ) : null}

      <Card className="theme-card-main">
        <CardHeader className="theme-card-header flex-col gap-4 space-y-0 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="theme-icon-surface h-10 w-10">
              <ClipboardCheck className="h-5 w-5" />
            </div>
            <div>
              <CardTitle>复习任务</CardTitle>
              <div className="mt-1 text-sm text-muted-foreground">
                当前阈值：记忆强度低于 {recommendationThresholdPercent}%
              </div>
            </div>
          </div>

          <div className="min-w-[180px] space-y-2">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="theme-meta">{reviewWorkspaceEntries.length} 题</span>
              <span className="font-medium text-[color:var(--theme-subtle-text)]">
                已完成 {answeredCount} / {reviewWorkspaceEntries.length}
              </span>
            </div>
            <div className="theme-progress-track h-2 overflow-hidden rounded-full">
              <div className="theme-progress-fill h-full rounded-full transition-[width] duration-300" style={{ width: `${completionPercent}%` }} />
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 pt-5">
          {!activeEntry ? (
            <div className="py-16 text-center text-sm text-muted-foreground">当前阈值下没有需要复习的复述点。</div>
          ) : (
            <div className="space-y-4">
              <div className="sr-only">
                作答进度：已作答 {answeredCount} / {reviewWorkspaceEntries.length}，当前是第 {activeReviewEntryIndex + 1} 题。
              </div>
              <div className="flex flex-wrap gap-2">
                {reviewWorkspaceEntries.map((entry, index) => {
                  const rpId = entry.recallPoint.recallPointId
                  const answer = sessionAnswers[rpId]
                  const isActive = rpId === activeEntry.recallPoint.recallPointId
                  return (
                    <button
                      key={`recommended-review-progress-${rpId}`}
                      type="button"
                      onClick={() => setSelectedRecallPointId(rpId)}
                      aria-current={isActive ? "true" : undefined}
                      className={cn(
                        "flex size-10 items-center justify-center rounded-xl border text-sm font-semibold transition-all",
                        answer === "remembered" && "border-emerald-200 bg-emerald-600 text-white shadow-[0_12px_24px_-20px_rgba(5,150,105,0.5)]",
                        answer === "forgotten" && "border-amber-200 bg-amber-50 text-amber-700",
                        answer === undefined && "[border-color:var(--theme-soft-border)] [background:var(--theme-soft-bg)] text-[color:var(--theme-subtle-text)] hover:border-primary/25 hover:text-primary",
                        isActive && "ring-2 ring-primary/25 ring-offset-2 ring-offset-background",
                      )}
                      title={`第 ${index + 1} 题`}
                    >
                      {index + 1}
                    </button>
                  )
                })}
              </div>

              {(() => {
                const rpId = activeEntry.recallPoint.recallPointId
                const answer = sessionAnswers[rpId]
                const isRemembered = answer === "remembered"
                const isForgotten = answer === "forgotten"
                const writtenAnswerDraft = writtenAnswerDrafts[rpId] ?? []
                const hasSubmittedWrittenAnswer = submittedWrittenAnswers[rpId] === true
                const canSubmitWrittenAnswer = richContentHasMeaning(writtenAnswerDraft)
                const answerVisible = hasSubmittedWrittenAnswer && (revealedAnswerIds[rpId] ?? false)
                const insightEditorVisible = showInsightEditor[rpId] || Boolean(insightDrafts[rpId]?.trim())
                const hasNextRecallPoint = activeReviewEntryIndex >= 0 && activeReviewEntryIndex < reviewWorkspaceEntries.length - 1

                return (
                  <div className="relative overflow-visible">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="absolute inset-y-0 -left-4 z-10 h-auto w-4 rounded-none border-0 bg-transparent p-0 text-[color:var(--theme-subtle-text)] shadow-none outline-none hover:bg-transparent hover:text-foreground focus-visible:ring-0 focus-visible:ring-offset-0 sm:-left-5 sm:w-5"
                      onClick={() => goToReviewEntry(activeReviewEntryIndex - 1)}
                      disabled={activeReviewEntryIndex <= 0}
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
                      onClick={() => goToReviewEntry(activeReviewEntryIndex + 1)}
                      disabled={activeReviewEntryIndex < 0 || activeReviewEntryIndex >= reviewWorkspaceEntries.length - 1}
                      aria-label="下一题"
                      title="下一题"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Button>

                    <div className="theme-status-surface rounded-[1.15rem] border border-[color:var(--theme-status-border)] px-4 py-4 sm:px-5">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                            <span>第 {activeReviewEntryIndex + 1} 题</span>
                          </div>

                          <Link
                            to={buildScopedProjectPath(subjectId, pid, `/recall-points/${rpId}`)}
                            className="-mx-2 -my-1 mt-2 block rounded-2xl px-2 py-1 transition hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                            title="打开复述点详情"
                          >
                            <div className="text-[15px] font-semibold leading-6 text-foreground transition hover:text-primary">
                              <RichContentRenderer subjectId={subjectId} projectId={pid} value={activeEntry.recallPoint.question} />
                            </div>
                          </Link>

                          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                            {activeEntry.recallPoint.anchor ? (
                              <Link
                                to={buildScopedProjectPath(subjectId, pid, `/instances/${activeEntry.recallPoint.anchor.instanceId}`)}
                                className="theme-pill-default rounded-full px-2.5 py-1 font-medium transition hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                                title="回到锚点"
                              >
                                {formatAnchorLabel(activeEntry.recallPoint)}
                              </Link>
                            ) : (
                              <span className="theme-pill-default rounded-full px-2.5 py-1 font-medium">{formatAnchorLabel(activeEntry.recallPoint)}</span>
                            )}
                            {activeEntry.recallPoint.insights.length > 0 ? (
                              <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 font-medium text-amber-700">
                                <Lightbulb className="h-3.5 w-3.5" />
                                已有 {activeEntry.recallPoint.insights.length} 条理解
                              </span>
                            ) : null}
                            <Button variant="ghost" size="sm" className="rounded-full" onClick={() => toggleInsightEditor(rpId)}>
                              <Lightbulb className="h-4 w-4" />
                              {insightEditorVisible ? "收起理解" : "追加理解"}
                            </Button>
                            <span className="theme-pill-default rounded-full px-2.5 py-1 font-medium">
                              系统推荐 {activeEntry.rankLabel} · {formatStatValue(activeEntry.recommendation.reviewRecommendationIndex)}
                            </span>
                          </div>
                        </div>
                      </div>

                      <div className="mt-4">
                        <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">你的答案</div>
                        <RichContentEditor
                          subjectId={subjectId}
                          projectId={pid}
                          field="answer"
                          value={writtenAnswerDraft}
                          disabled={hasSubmittedWrittenAnswer}
                          placeholder="先写下自己的答案，提交后会自动展开标准答案。"
                          onTextChange={(text) => updateWrittenAnswerText(rpId, text)}
                          onAppendImage={() => appendWrittenAnswerImage(rpId)}
                          onRemoveImage={() => removeWrittenAnswerImage(rpId)}
                          onUserActivity={() => undefined}
                          textareaClassName="min-h-[140px] resize-y rounded-xl [border-color:var(--theme-subtle-border)] [background:var(--theme-subtle-bg)] text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/15 disabled:cursor-not-allowed disabled:opacity-75"
                          imageClassName="h-28 w-full max-w-[220px] rounded-xl border [border-color:var(--theme-subtle-border)] [background:var(--theme-subtle-bg)] object-cover"
                        />
                        {!hasSubmittedWrittenAnswer ? (
                          <div className="mt-2 flex flex-wrap items-center gap-2">
                            <Button type="button" variant="default" size="sm" className="rounded-xl" onClick={() => submitWrittenAnswer(rpId)} disabled={!canSubmitWrittenAnswer}>
                              提交答案
                            </Button>
                            <Button type="button" variant="outline" size="sm" className="rounded-xl" onClick={() => skipWrittenAnswer(rpId)}>
                              跳过
                            </Button>
                          </div>
                        ) : null}
                      </div>

                      {answerVisible ? (
                        <div className="mt-3">
                          <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">答案</div>
                          <div className="theme-canvas rounded-2xl border border-[color:var(--theme-soft-border)] p-3 text-sm">
                            <RichContentRenderer subjectId={subjectId} projectId={pid} value={activeEntry.recallPoint.answer} />
                          </div>
                        </div>
                      ) : null}

                      {insightEditorVisible ? (
                        <div className="theme-soft-surface mt-3 p-3">
                          <textarea
                            value={insightDrafts[rpId] ?? ""}
                            onChange={(event) => updateInsightDraft(rpId, event.target.value)}
                            rows={3}
                            placeholder="补充这道复习点的新理解、易错点、联想线索或自己的话解释。"
                            className="min-h-[96px] w-full resize-y border-0 bg-transparent p-0 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:ring-0"
                          />
                        </div>
                      ) : null}

                      <div className="mt-4 flex flex-wrap items-center gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          className={cn(
                            "min-w-[96px] rounded-full !border-emerald-200 !bg-emerald-50 !text-emerald-700 hover:!border-emerald-300 hover:!bg-emerald-100 hover:!text-emerald-800",
                            isRemembered ? "!bg-emerald-600 !text-white hover:!bg-emerald-700 hover:!text-white" : "",
                          )}
                          onClick={() => chooseSessionAnswer(rpId, "remembered")}
                          disabled={!hasSubmittedWrittenAnswer}
                        >
                          记得
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          className={cn(
                            "min-w-[96px] rounded-full !border-red-200 !bg-red-50 !text-red-700 hover:!border-red-300 hover:!bg-red-100 hover:!text-red-800",
                            isForgotten ? "!bg-red-600 !text-white hover:!bg-red-700 hover:!text-white" : "",
                          )}
                          onClick={() => chooseSessionAnswer(rpId, "forgotten")}
                          disabled={!hasSubmittedWrittenAnswer}
                        >
                          不记得
                        </Button>
                        {answer !== undefined ? (
                          <Button variant="ghost" size="sm" className="rounded-full text-muted-foreground" onClick={() => clearSessionAnswer(rpId)}>
                            <Undo2 className="h-4 w-4" />
                            撤销选择
                          </Button>
                        ) : null}
                      </div>

                      {answer !== undefined ? (
                        <div
                          className={cn(
                            "mt-3 flex items-center gap-2 rounded-2xl px-3 py-2 text-xs font-medium",
                            isRemembered ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700",
                          )}
                        >
                          <CheckCircle2 className="h-4 w-4" />
                          {isRemembered
                            ? hasNextRecallPoint
                              ? "这题已标记为“记得”，回答后自动切到下一题。"
                              : "这题已标记为“记得”，已经是最后一题。"
                            : hasNextRecallPoint
                              ? "这题已标记为“不记得”，回答后自动切到下一题。"
                              : "这题已标记为“不记得”，已经是最后一题。"}
                        </div>
                      ) : null}

                      <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                        <StatBlock label="推荐指数" value={activeEntry.recommendation.reviewRecommendationIndex.toFixed(1)} detail="当前复述点" />
                        <StatBlock label="记忆强度" value={formatPercent(activeEntry.recommendation.estimatedMemoryStrength)} detail="当前复述点" />
                        <StatBlock
                          label="最近复习"
                          value={formatReviewResult(activeEntry.recommendation.lastReviewResult).replace("最近一次：", "")}
                          detail={formatDateTime(activeEntry.recommendation.lastReviewedAt)}
                        />
                      </div>
                    </div>
                  </div>
                )
              })()}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={thresholdDialogOpen} onOpenChange={setThresholdDialogOpen}>
        <DialogContent className="max-w-md rounded-[1.6rem] border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)]">
          <DialogHeader>
            <DialogTitle>更新推荐阈值</DialogTitle>
            <DialogDescription>
              设置记忆强度阈值。按阈值更新后，只会替换还没答过的复述点；已经点过记得或不记得的内容会保留。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <label htmlFor="recommendation-threshold" className="text-sm font-medium text-foreground">
              记忆强度低于
            </label>
            <div className="flex items-center gap-2">
              <Input
                id="recommendation-threshold"
                type="number"
                min={1}
                max={99}
                step={1}
                value={thresholdDraft}
                onChange={(event) => setThresholdDraft(event.target.value)}
              />
              <span className="text-sm text-muted-foreground">%</span>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setThresholdDialogOpen(false)}>
              取消
            </Button>
            <Button type="button" onClick={applyRecommendationThreshold} disabled={!allReviewRecommendationsQ.data}>
              更新
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

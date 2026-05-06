import { useDeferredValue, useEffect, useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  ClipboardCheck,
  Lightbulb,
  PlayCircle,
  Plus,
  Search,
  Undo2,
} from "lucide-react"
import { Link, useParams, useSearchParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { searchRecallPoints, type RecallPoint, type ReviewRecommendationItem } from "@/ui/api/review"
import { normalizeRichContent, richContentHasMeaning, richContentToPlainText, setRichContentText, type RichContent } from "@/ui/api/richContent"
import { RichContentRenderer } from "@/ui/components/RichContentRenderer"
import { RichContentEditor } from "@/ui/components/RichContentEditor"
import { ContentEmptyState, ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { formatInstanceReference, formatRecallPointReference } from "@/ui/displayIdentifiers"
import { useProject } from "@/ui/queries/projects"
import { useReviewRecommendations } from "@/ui/queries/reviewRecommendations"
import { cn } from "@/ui/utils"

type SessionAnswer = "remembered" | "forgotten"

type ReviewWorkspaceEntry = {
  recallPoint: RecallPoint
  source: "recommended" | "manual"
  rankLabel: string | null
  recommendation: ReviewRecommendationItem | null
}

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function parseOffset(raw: string | null) {
  const n = Number(raw ?? "0")
  if (!Number.isFinite(n) || n < 0) return 0
  return Math.floor(n)
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

function getRecallPointQuestionPreview(recallPoint: RecallPoint) {
  return richContentToPlainText(recallPoint.question).trim() || "题面为空"
}

function getRecallPointAnswerPreview(recallPoint: RecallPoint) {
  return richContentToPlainText(recallPoint.answer).trim() || "答案为空"
}

function formatAnchorLabel(recallPoint: RecallPoint) {
  if (!recallPoint.anchor) return "未绑定锚点"
  return `${formatInstanceReference(recallPoint.anchor.instanceId)} · ${recallPoint.anchor.position}`
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
  const { projectId } = useParams()
  const pid = projectId ?? ""
  const [searchParams, setSearchParams] = useSearchParams()
  const offset = parseOffset(searchParams.get("offset"))
  const [recallPointSearchQuery, setRecallPointSearchQuery] = useState("")
  const deferredRecallPointSearchQuery = useDeferredValue(recallPointSearchQuery.trim())
  const [manualReviewRecallPoints, setManualReviewRecallPoints] = useState<RecallPoint[]>([])
  const [excludedRecallPointIds, setExcludedRecallPointIds] = useState<string[]>([])
  const [activeRecallPointId, setActiveRecallPointId] = useState<string | null>(null)
  const [revealedAnswerIds, setRevealedAnswerIds] = useState<Record<string, boolean>>({})
  const [sessionAnswers, setSessionAnswers] = useState<Record<string, SessionAnswer>>({})
  const [writtenAnswerDrafts, setWrittenAnswerDrafts] = useState<Record<string, RichContent>>({})
  const [submittedWrittenAnswers, setSubmittedWrittenAnswers] = useState<Record<string, boolean>>({})
  const [insightDrafts, setInsightDrafts] = useState<Record<string, string>>({})
  const [showInsightEditor, setShowInsightEditor] = useState<Record<string, boolean>>({})
  const reviewRecommendationsQ = useReviewRecommendations(pid, { offset })
  const recallPointSearchQ = useQuery({
    queryKey: ["recommendedReviewRecallPointSearch", pid, deferredRecallPointSearchQuery],
    queryFn: ({ signal }) =>
      searchRecallPoints(
        pid,
        { q: deferredRecallPointSearchQuery || undefined, limit: 12 },
        { signal },
      ),
    enabled: !!pid && deferredRecallPointSearchQuery.length >= 2,
    placeholderData: (previous) => previous,
    staleTime: 30_000,
  })
  const { projectTitle } = useProject(pid)

  useEffect(() => {
    setRecallPointSearchQuery("")
    setManualReviewRecallPoints([])
    setExcludedRecallPointIds([])
    setActiveRecallPointId(null)
    setRevealedAnswerIds({})
    setSessionAnswers({})
    setWrittenAnswerDrafts({})
    setSubmittedWrittenAnswers({})
    setInsightDrafts({})
    setShowInsightEditor({})
  }, [pid])

  const page = reviewRecommendationsQ.data
  const items = page?.items ?? []
  const startNumber = (page?.offset ?? offset) + 1
  const endNumber = page?.offset !== undefined ? page.offset + items.length : offset + items.length
  const reviewWorkspaceEntries = useMemo<ReviewWorkspaceEntry[]>(() => {
    const excluded = new Set(excludedRecallPointIds)
    const seen = new Set<string>()
    const entries: ReviewWorkspaceEntry[] = []

    items.forEach((item, index) => {
      const recallPointId = item.recallPoint.recallPointId
      if (excluded.has(recallPointId) || seen.has(recallPointId)) return
      seen.add(recallPointId)
      entries.push({
        recallPoint: item.recallPoint,
        source: "recommended",
        rankLabel: `#${startNumber + index}`,
        recommendation: item,
      })
    })

    manualReviewRecallPoints.forEach((recallPoint) => {
      if (seen.has(recallPoint.recallPointId)) return
      seen.add(recallPoint.recallPointId)
      entries.push({
        recallPoint,
        source: "manual",
        rankLabel: null,
        recommendation: null,
      })
    })

    return entries
  }, [excludedRecallPointIds, items, manualReviewRecallPoints, startNumber])
  const reviewWorkspaceIdSet = useMemo(
    () => new Set(reviewWorkspaceEntries.map((entry) => entry.recallPoint.recallPointId)),
    [reviewWorkspaceEntries],
  )
  const activeEntry = reviewWorkspaceEntries.find((entry) => entry.recallPoint.recallPointId === activeRecallPointId) ?? null
  const activeReviewEntryIndex = activeEntry
    ? reviewWorkspaceEntries.findIndex((entry) => entry.recallPoint.recallPointId === activeEntry.recallPoint.recallPointId)
    : -1
  const answeredCount = reviewWorkspaceEntries.filter((entry) => sessionAnswers[entry.recallPoint.recallPointId] !== undefined).length
  const completionPercent = reviewWorkspaceEntries.length > 0 ? Math.round((answeredCount / reviewWorkspaceEntries.length) * 100) : 0

  useEffect(() => {
    if (reviewWorkspaceEntries.length === 0) {
      if (activeRecallPointId !== null) setActiveRecallPointId(null)
      return
    }
    if (!activeRecallPointId || !reviewWorkspaceIdSet.has(activeRecallPointId)) {
      setActiveRecallPointId(reviewWorkspaceEntries[0].recallPoint.recallPointId)
    }
  }, [activeRecallPointId, reviewWorkspaceEntries, reviewWorkspaceIdSet])

  if (!pid) {
    return (
      <div className="space-y-4">
        <ContentNotice
          title="当前页面缺少项目上下文"
          message="当前链接缺少项目信息。请先返回项目列表，再重新进入推荐复习。"
          action={
            <Button asChild>
              <Link to="/projects">返回项目列表</Link>
            </Button>
          }
        />
      </div>
    )
  }

  function jumpTo(nextOffset: number) {
    const next = new URLSearchParams(searchParams)
    if (nextOffset <= 0) {
      next.delete("offset")
    } else {
      next.set("offset", String(nextOffset))
    }
    setSearchParams(next)
    window.scrollTo({ top: 0, behavior: "smooth" })
  }

  function addRecallPointToReview(recallPoint: RecallPoint) {
    setManualReviewRecallPoints((current) =>
      current.some((item) => item.recallPointId === recallPoint.recallPointId) ? current : [recallPoint, ...current],
    )
    setExcludedRecallPointIds((current) => current.filter((id) => id !== recallPoint.recallPointId))
    setActiveRecallPointId(recallPoint.recallPointId)
  }

  function removeRecallPointFromReview(recallPointId: string) {
    const isRecommended = items.some((item) => item.recallPoint.recallPointId === recallPointId)
    setManualReviewRecallPoints((current) => current.filter((item) => item.recallPointId !== recallPointId))
    if (isRecommended) {
      setExcludedRecallPointIds((current) => (current.includes(recallPointId) ? current : [...current, recallPointId]))
    }
    setRevealedAnswerIds((current) => {
      const next = { ...current }
      delete next[recallPointId]
      return next
    })
    setSessionAnswers((current) => {
      const next = { ...current }
      delete next[recallPointId]
      return next
    })
    setWrittenAnswerDrafts((current) => {
      const next = { ...current }
      delete next[recallPointId]
      return next
    })
    setSubmittedWrittenAnswers((current) => {
      const next = { ...current }
      delete next[recallPointId]
      return next
    })
    setInsightDrafts((current) => {
      const next = { ...current }
      delete next[recallPointId]
      return next
    })
    setShowInsightEditor((current) => {
      const next = { ...current }
      delete next[recallPointId]
      return next
    })
    if (activeRecallPointId === recallPointId) setActiveRecallPointId(null)
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
    setActiveRecallPointId(next.recallPoint.recallPointId)
  }

  const searchResults = recallPointSearchQ.data ?? []
  const searchIsReady = deferredRecallPointSearchQuery.length >= 2
  const canGoPrevious = offset > 0 && !reviewRecommendationsQ.isLoading
  const canGoNext = page?.nextOffset != null && !reviewRecommendationsQ.isLoading

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-lg font-semibold">推荐复习</h1>
          <p className="text-sm text-muted-foreground">
            项目：<span className="font-medium text-foreground">{projectTitle}</span>
          </p>
          <p className="text-sm text-muted-foreground">从系统推荐开始，也可以搜索复述点加入这次复习。</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" asChild>
            <Link to={`/p/${pid}/workbench`}>返回工作台</Link>
          </Button>
          <Button variant="outline" onClick={() => void reviewRecommendationsQ.refetch()} disabled={reviewRecommendationsQ.isFetching}>
            {reviewRecommendationsQ.isFetching ? "刷新中..." : "刷新推荐"}
          </Button>
        </div>
      </div>

      {reviewRecommendationsQ.isLoading ? <LoadingNotice title="正在加载推荐复习" message="正在根据复习历史和遗忘曲线计算当前批次。" /> : null}
      {reviewRecommendationsQ.error ? <ErrorNotice title="推荐复习加载失败" message={formatApiError(reviewRecommendationsQ.error)} /> : null}
      {!reviewRecommendationsQ.isLoading && !reviewRecommendationsQ.error && page && page.totalCount === 0 && manualReviewRecallPoints.length === 0 ? (
        <ContentEmptyState
          title="当前没有推荐复习"
          message="可以先从左侧搜索复述点加入复习，或者回到工作台继续生成复述点。"
        />
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(20rem,0.82fr)_minmax(0,1.6fr)]">
        <aside className="space-y-4">
          <Card className="theme-card-main">
            <CardHeader className="theme-card-header">
              <CardTitle>复述点搜索</CardTitle>
              <CardDescription>输入关键词搜索题面、答案或锚点，把需要补练的复述点加入本次复习。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={recallPointSearchQuery}
                  onChange={(event) => setRecallPointSearchQuery(event.target.value)}
                  className="pl-10"
                  placeholder="搜索复述点关键词"
                />
              </div>

              <div className="space-y-1">
                {!searchIsReady ? <div className="px-1 text-sm text-muted-foreground">输入至少 2 个字符开始搜索。</div> : null}
                {searchIsReady && recallPointSearchQ.isFetching ? <div className="px-1 text-sm text-muted-foreground">搜索中...</div> : null}
                {searchIsReady && recallPointSearchQ.error ? (
                  <div className="px-1 text-sm text-destructive">{formatApiError(recallPointSearchQ.error)}</div>
                ) : null}
                {searchIsReady && !recallPointSearchQ.isFetching && !recallPointSearchQ.error && searchResults.length === 0 ? (
                  <div className="px-1 text-sm text-muted-foreground">没有匹配的复述点。</div>
                ) : null}

                {searchResults.map((recallPoint) => {
                  const isAdded = reviewWorkspaceIdSet.has(recallPoint.recallPointId)
                  return (
                    <div key={recallPoint.recallPointId} className="flex items-start gap-3 border-t border-border/60 px-1 py-3 first:border-t-0">
                      <div className="min-w-0 flex-1">
                        <div className="text-xs font-medium text-muted-foreground">{formatRecallPointReference(recallPoint.recallPointId)}</div>
                        <div className="mt-1 truncate text-sm font-medium text-foreground">{getRecallPointQuestionPreview(recallPoint)}</div>
                        <div className="mt-1 truncate text-xs text-muted-foreground">{getRecallPointAnswerPreview(recallPoint)}</div>
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        variant={isAdded ? "outline" : "default"}
                        disabled={isAdded}
                        onClick={() => addRecallPointToReview(recallPoint)}
                      >
                        {isAdded ? (
                          <>
                            <Check className="h-4 w-4" />
                            已加入
                          </>
                        ) : (
                          <>
                            <Plus className="h-4 w-4" />
                            加入复习
                          </>
                        )}
                      </Button>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>

          <Card className="theme-card-main">
            <CardHeader className="theme-card-header">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle>本次复习</CardTitle>
                  <CardDescription>
                    {page
                      ? page.totalCount > 0
                        ? `推荐第 ${startNumber}-${endNumber} 条，共 ${page.totalCount} 条。`
                        : "当前没有系统推荐，仍可手动加入复述点。"
                      : "读取当前推荐批次。"}
                  </CardDescription>
                </div>
                <div className="text-right text-xs text-muted-foreground">
                  <div className="font-medium text-foreground">{reviewWorkspaceEntries.length} 个</div>
                  <div>已加入</div>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between gap-2">
                <Button variant="outline" size="sm" onClick={() => jumpTo(Math.max(offset - (page?.limit ?? 20), 0))} disabled={!canGoPrevious}>
                  <ChevronLeft className="h-4 w-4" />
                  上一批
                </Button>
                <Button size="sm" onClick={() => jumpTo(page?.nextOffset ?? offset)} disabled={!canGoNext}>
                  继续推荐
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </div>

              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${completionPercent}%` }} />
              </div>

              {reviewWorkspaceEntries.length === 0 ? (
                <div className="px-1 py-6 text-sm text-muted-foreground">左侧搜索复述点，或者等待推荐批次加载后开始复习。</div>
              ) : (
                <div className="space-y-0">
                  {reviewWorkspaceEntries.map((entry) => {
                    const recallPoint = entry.recallPoint
                    const answer = sessionAnswers[recallPoint.recallPointId]
                    const isActive = recallPoint.recallPointId === activeRecallPointId
                    return (
                      <div
                        key={recallPoint.recallPointId}
                        className={cn(
                          "flex items-stretch gap-2 border-t border-border/60 first:border-t-0",
                          isActive ? "text-primary" : "text-foreground",
                        )}
                      >
                        <button
                          type="button"
                          className="min-w-0 flex-1 py-3 text-left"
                          onClick={() => setActiveRecallPointId(recallPoint.recallPointId)}
                        >
                          <div className="flex items-center gap-2">
                            <span className="truncate text-sm font-medium">{formatRecallPointReference(recallPoint.recallPointId)}</span>
                            <span className="shrink-0 text-xs text-muted-foreground">{entry.source === "recommended" ? entry.rankLabel : "手动"}</span>
                          </div>
                          <div className="mt-1 truncate text-xs text-muted-foreground">{getRecallPointQuestionPreview(recallPoint)}</div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            {answer === "remembered" ? "已标记：记得" : answer === "forgotten" ? "已标记：不记得" : "未判断"}
                          </div>
                        </button>
                        <Button type="button" variant="ghost" size="sm" className="self-center" onClick={() => removeRecallPointFromReview(recallPoint.recallPointId)}>
                          移除
                        </Button>
                      </div>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </aside>

        <div>
          <Card className="theme-card-main">
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
                <div className="py-16 text-center text-sm text-muted-foreground">从左侧推荐列表或搜索结果中选择一个复述点开始。</div>
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
                          onClick={() => setActiveRecallPointId(rpId)}
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
                                {isRemembered ? <span className="rounded-full bg-emerald-50 px-2 py-0.5 tracking-[0.08em] text-emerald-700">已标记为记得</span> : null}
                                {isForgotten ? <span className="rounded-full bg-amber-50 px-2 py-0.5 tracking-[0.08em] text-amber-700">已标记为不记得</span> : null}
                              </div>

                              <Link
                                to={`/p/${pid}/recall-points/${rpId}`}
                                className="group mt-2 block rounded-2xl px-2 py-1 -mx-2 -my-1 transition hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                                title="打开复述点详情"
                              >
                                <div className="text-[15px] font-semibold leading-6 text-foreground transition group-hover:text-primary">
                                  <RichContentRenderer projectId={pid} value={activeEntry.recallPoint.question} />
                                </div>
                                <div className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-primary/85">
                                  查看复述点详情
                                  <ArrowUpRight className="h-3.5 w-3.5" />
                                </div>
                              </Link>

                              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                                <span className="theme-pill-default rounded-full px-2.5 py-1 font-medium">{formatAnchorLabel(activeEntry.recallPoint)}</span>
                                {activeEntry.recallPoint.insights.length > 0 ? (
                                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 font-medium text-amber-700">
                                    <Lightbulb className="h-3.5 w-3.5" />
                                    已有 {activeEntry.recallPoint.insights.length} 条理解
                                  </span>
                                ) : null}
                                {activeEntry.recommendation ? (
                                  <span className="theme-pill-default rounded-full px-2.5 py-1 font-medium">
                                    系统推荐 {activeEntry.rankLabel} · {formatStatValue(activeEntry.recommendation.reviewRecommendationIndex)}
                                  </span>
                                ) : null}
                              </div>
                            </div>
                          </div>

                          <div className="mt-3 flex flex-wrap gap-2">
                            {activeEntry.recallPoint.anchor ? (
                              <Button variant="outline" size="sm" className="rounded-full" asChild>
                                <Link to={`/p/${pid}/instances/${activeEntry.recallPoint.anchor.instanceId}`}>
                                  <PlayCircle className="h-4 w-4" />
                                  回到锚点
                                </Link>
                              </Button>
                            ) : null}
                            <Button variant="ghost" size="sm" className="rounded-full" onClick={() => toggleInsightEditor(rpId)}>
                              <Lightbulb className="h-4 w-4" />
                              {insightEditorVisible ? "收起理解" : "追加理解"}
                            </Button>
                          </div>

                          <div className="mt-4">
                            <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">你的答案</div>
                            <RichContentEditor
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
                            <div className="mt-2 flex flex-wrap items-center gap-2">
                              {hasSubmittedWrittenAnswer ? (
                                <span className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                                  <CheckCircle2 className="h-4 w-4" />
                                  已提交答案
                                </span>
                              ) : (
                                <>
                                  <Button type="button" variant="default" size="sm" className="rounded-xl" onClick={() => submitWrittenAnswer(rpId)} disabled={!canSubmitWrittenAnswer}>
                                    提交答案
                                  </Button>
                                  <Button type="button" variant="outline" size="sm" className="rounded-xl" onClick={() => skipWrittenAnswer(rpId)}>
                                    跳过
                                  </Button>
                                </>
                              )}
                              <span className="text-xs text-muted-foreground">
                                {hasSubmittedWrittenAnswer ? "已展开答案，可判断记忆状态。" : "先提交自己的答案或跳过，再判断记忆状态。"}
                              </span>
                            </div>
                          </div>

                          {answerVisible ? (
                            <div className="theme-canvas mt-3 rounded-2xl border border-[color:var(--theme-soft-border)] p-3 text-sm">
                              <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">答案</div>
                              <RichContentRenderer projectId={pid} value={activeEntry.recallPoint.answer} />
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
                              variant={isRemembered ? "default" : "outline"}
                              size="sm"
                              className={cn("min-w-[96px] rounded-full", isRemembered ? "bg-emerald-600 hover:bg-emerald-700" : "")}
                              onClick={() => chooseSessionAnswer(rpId, "remembered")}
                              disabled={!hasSubmittedWrittenAnswer}
                            >
                              记得
                            </Button>
                            <Button
                              variant={isForgotten ? "secondary" : "outline"}
                              size="sm"
                              className={cn("min-w-[96px] rounded-full", isForgotten ? "border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100" : "")}
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
                            <StatBlock label="推荐指数" value={activeEntry.recommendation ? activeEntry.recommendation.reviewRecommendationIndex.toFixed(1) : "-"} detail="当前复述点" />
                            <StatBlock label="记忆强度" value={activeEntry.recommendation ? formatPercent(activeEntry.recommendation.estimatedMemoryStrength) : "-"} detail="当前复述点" />
                            <StatBlock
                              label="最近复习"
                              value={activeEntry.recommendation ? formatReviewResult(activeEntry.recommendation.lastReviewResult).replace("最近一次：", "") : "-"}
                              detail={activeEntry.recommendation ? formatDateTime(activeEntry.recommendation.lastReviewedAt) : "暂无推荐统计"}
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
        </div>
      </div>
    </div>
  )
}

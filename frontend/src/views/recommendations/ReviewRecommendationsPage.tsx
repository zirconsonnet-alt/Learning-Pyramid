import { useDeferredValue, useEffect, useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { ArrowRight, Check, CheckCircle2, ChevronLeft, Plus, Search, XCircle } from "lucide-react"
import { Link, useParams, useSearchParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { searchRecallPoints, type RecallPoint, type ReviewRecommendationItem } from "@/ui/api/review"
import { richContentToPlainText } from "@/ui/api/richContent"
import { RichContentRenderer } from "@/ui/components/RichContentRenderer"
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
  const rememberedCount = reviewWorkspaceEntries.filter((entry) => sessionAnswers[entry.recallPoint.recallPointId] === "remembered").length
  const forgottenCount = reviewWorkspaceEntries.filter((entry) => sessionAnswers[entry.recallPoint.recallPointId] === "forgotten").length
  const completionPercent = reviewWorkspaceEntries.length > 0 ? Math.round((answeredCount / reviewWorkspaceEntries.length) * 100) : 0
  const recommendationStats = reviewWorkspaceEntries.map((entry) => entry.recommendation).filter((item): item is ReviewRecommendationItem => item !== null)
  const averageRecommendationIndex =
    recommendationStats.length > 0
      ? recommendationStats.reduce((sum, item) => sum + item.reviewRecommendationIndex, 0) / recommendationStats.length
      : null
  const averageMemoryStrength =
    recommendationStats.length > 0
      ? recommendationStats.reduce((sum, item) => sum + item.estimatedMemoryStrength, 0) / recommendationStats.length
      : null

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
    if (activeRecallPointId === recallPointId) setActiveRecallPointId(null)
  }

  function revealAnswer(recallPointId: string) {
    setRevealedAnswerIds((current) => ({ ...current, [recallPointId]: true }))
  }

  function chooseSessionAnswer(recallPointId: string, answer: SessionAnswer) {
    setRevealedAnswerIds((current) => ({ ...current, [recallPointId]: true }))
    setSessionAnswers((current) => ({ ...current, [recallPointId]: answer }))
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

        <div className="space-y-4">
          <Card className="theme-card-main">
            <CardHeader className="theme-card-header">
              <CardTitle>复习统计</CardTitle>
              <CardDescription>右侧统计会随本次加入的复述点和本地判断同步变化。</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <StatBlock label="本次复习" value={String(reviewWorkspaceEntries.length)} detail={`推荐 ${items.length} · 手动 ${manualReviewRecallPoints.length}`} />
              <StatBlock label="已完成" value={`${answeredCount}/${reviewWorkspaceEntries.length}`} detail={`记得 ${rememberedCount} · 不记得 ${forgottenCount}`} />
              <StatBlock label="推荐指数" value={formatStatValue(averageRecommendationIndex)} detail="已加入推荐项均值" />
              <StatBlock label="记忆强度" value={averageMemoryStrength === null ? "-" : formatPercent(averageMemoryStrength)} detail="已加入推荐项均值" />
            </CardContent>
          </Card>

          <Card className="theme-card-main">
            <CardHeader className="theme-card-header flex-col gap-4 space-y-0 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <CardTitle>复习工作区</CardTitle>
                <CardDescription>
                  {activeEntry
                    ? `当前 ${activeReviewEntryIndex + 1}/${reviewWorkspaceEntries.length} · ${formatRecallPointReference(activeEntry.recallPoint.recallPointId)}`
                    : "先从左侧选择或加入一个复述点。"}
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={() => goToReviewEntry(activeReviewEntryIndex - 1)} disabled={activeReviewEntryIndex <= 0}>
                  <ChevronLeft className="h-4 w-4" />
                  上一个
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => goToReviewEntry(activeReviewEntryIndex + 1)}
                  disabled={activeReviewEntryIndex < 0 || activeReviewEntryIndex >= reviewWorkspaceEntries.length - 1}
                >
                  下一个
                  <ArrowRight className="h-4 w-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {!activeEntry ? (
                <div className="py-16 text-center text-sm text-muted-foreground">从左侧推荐列表或搜索结果中选择一个复述点开始。</div>
              ) : (
                <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(16rem,0.72fr)]">
                  <section className="space-y-4">
                    <div className="space-y-2 border-t border-border/60 pt-4 first:border-t-0">
                      <div className="text-xs font-medium text-muted-foreground">问题</div>
                      <RichContentRenderer projectId={pid} value={activeEntry.recallPoint.question} />
                    </div>

                    <div className="space-y-3 border-t border-border/60 pt-4">
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-xs font-medium text-muted-foreground">答案</div>
                        {!revealedAnswerIds[activeEntry.recallPoint.recallPointId] ? (
                          <Button type="button" size="sm" variant="outline" onClick={() => revealAnswer(activeEntry.recallPoint.recallPointId)}>
                            显示答案
                          </Button>
                        ) : null}
                      </div>
                      {revealedAnswerIds[activeEntry.recallPoint.recallPointId] ? (
                        <RichContentRenderer projectId={pid} value={activeEntry.recallPoint.answer} />
                      ) : (
                        <div className="text-sm text-muted-foreground">先在脑中复述，再点开答案核对。</div>
                      )}
                    </div>
                  </section>

                  <section className="space-y-5 border-t border-border/60 pt-4 lg:border-l lg:border-t-0 lg:pl-5 lg:pt-0">
                    <div className="space-y-3">
                      <div className="text-sm font-medium">复习判断</div>
                      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1">
                        <Button
                          type="button"
                          variant={sessionAnswers[activeEntry.recallPoint.recallPointId] === "remembered" ? "default" : "outline"}
                          onClick={() => chooseSessionAnswer(activeEntry.recallPoint.recallPointId, "remembered")}
                        >
                          <CheckCircle2 className="h-4 w-4" />
                          记得
                        </Button>
                        <Button
                          type="button"
                          variant={sessionAnswers[activeEntry.recallPoint.recallPointId] === "forgotten" ? "destructive" : "outline"}
                          onClick={() => chooseSessionAnswer(activeEntry.recallPoint.recallPointId, "forgotten")}
                        >
                          <XCircle className="h-4 w-4" />
                          不记得
                        </Button>
                      </div>
                    </div>

                    <div className="space-y-3 text-sm">
                      <div className="flex items-center justify-between gap-3 border-t border-border/60 pt-3">
                        <span className="text-muted-foreground">来源</span>
                        <span className="font-medium text-foreground">{activeEntry.source === "recommended" ? `系统推荐 ${activeEntry.rankLabel}` : "手动加入"}</span>
                      </div>
                      <div className="flex items-center justify-between gap-3 border-t border-border/60 pt-3">
                        <span className="text-muted-foreground">推荐指数</span>
                        <span className="font-medium text-foreground">
                          {activeEntry.recommendation ? activeEntry.recommendation.reviewRecommendationIndex.toFixed(1) : "-"}
                        </span>
                      </div>
                      <div className="flex items-center justify-between gap-3 border-t border-border/60 pt-3">
                        <span className="text-muted-foreground">记忆强度</span>
                        <span className="font-medium text-foreground">
                          {activeEntry.recommendation ? formatPercent(activeEntry.recommendation.estimatedMemoryStrength) : "-"}
                        </span>
                      </div>
                      <div className="border-t border-border/60 pt-3">
                        <div className="text-muted-foreground">最近复习</div>
                        <div className="mt-1 font-medium text-foreground">
                          {activeEntry.recommendation
                            ? `${formatReviewResult(activeEntry.recommendation.lastReviewResult)} · ${formatDateTime(activeEntry.recommendation.lastReviewedAt)}`
                            : "暂无推荐统计"}
                        </div>
                      </div>
                      <div className="border-t border-border/60 pt-3">
                        <div className="text-muted-foreground">锚点</div>
                        <div className="mt-1 font-medium text-foreground">{formatAnchorLabel(activeEntry.recallPoint)}</div>
                      </div>
                    </div>

                    <Button variant="outline" size="sm" asChild>
                      <Link to={`/p/${pid}/recall-points/${activeEntry.recallPoint.recallPointId}`}>打开复述点详情</Link>
                    </Button>
                  </section>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}

import { type ReactNode, useEffect, useMemo, useState } from "react"
import { useQueries } from "@tanstack/react-query"
import { ArrowRight, CheckCircle2, ChevronLeft, RefreshCw, XCircle } from "lucide-react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import type { RecallPoint, ReviewTask } from "@/ui/api/review"
import { getRangeSnapshot, getRecallPoint, getReviewTask } from "@/ui/api/review"
import { RichContentRenderer } from "@/ui/components/RichContentRenderer"
import { ContentEmptyState, ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import {
  formatConvergenceReference,
  formatInstanceReference,
  formatRangeReference,
  formatRecallPointReference,
  formatReviewTaskReference,
} from "@/ui/displayIdentifiers"
import { useProject } from "@/ui/queries/projects"
import { useConvergence } from "@/ui/queries/reviewChains"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function formatTs(iso: string | null) {
  if (!iso) return "-"
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString()
}

function describeConvergenceState(state: string) {
  if (state === "IN_PROGRESS") return "进行中"
  if (state === "TERMINATED") return "已完成"
  return state
}

function describeReviewTaskState(state: string) {
  if (state === "PENDING") return "待执行"
  if (state === "DONE") return "已完成"
  return state
}

function formatReviewOutcome(value: "remembered" | "forgotten" | null) {
  if (value === "remembered") return "最近一次：会"
  if (value === "forgotten") return "最近一次：不会"
  return "还没有正式复习记录"
}

function formatAnchorLabel(recallPoint: RecallPoint) {
  if (!recallPoint.anchor) return "未绑定锚点"
  return `${formatInstanceReference(recallPoint.anchor.instanceId)} · ${recallPoint.anchor.position}`
}

type ConvergenceReviewEntry = {
  recallPoint: RecallPoint
  reviewTask: ReviewTask
  reviewTaskId: string
  roundIndex: number
  outcome: "remembered" | "forgotten" | null
}

export function ConvergencePage() {
  const { projectId, convergenceId } = useParams()
  const navigate = useNavigate()
  const pid = projectId ?? ""
  const cid = convergenceId ?? ""
  const { projectTitle } = useProject(pid)
  const convergenceQ = useConvergence(pid, cid)
  const [activeRecallPointId, setActiveRecallPointId] = useState<string | null>(null)
  const [revealedAnswerIds, setRevealedAnswerIds] = useState<Record<string, boolean>>({})

  const reviewTaskQs = useQueries({
    queries:
      convergenceQ.data?.reviewTaskIds.map((reviewTaskId) => ({
        queryKey: ["reviewTask", pid, reviewTaskId],
        queryFn: () => getReviewTask(pid, reviewTaskId),
        enabled: !!pid,
      })) ?? [],
  })
  const inputRangeQs = useQueries({
    queries: reviewTaskQs.map((query) => {
      const inputRangeId = query.data?.inputRangeId ?? ""
      return {
        queryKey: ["range", pid, inputRangeId],
        queryFn: () => getRangeSnapshot(pid, inputRangeId),
        enabled: !!pid && !!inputRangeId,
      }
    }),
  })
  const resultRangeQs = useQueries({
    queries: reviewTaskQs.map((query) => {
      const resultRangeId = query.data?.resultRangeId ?? ""
      return {
        queryKey: ["range", pid, resultRangeId],
        queryFn: () => getRangeSnapshot(pid, resultRangeId),
        enabled: !!pid && !!resultRangeId,
      }
    }),
  })
  const reviewRecallPointRefs = useMemo(
    () =>
      inputRangeQs.flatMap((query, roundIndex) =>
        (query.data?.recallPointIds ?? []).map((recallPointId) => ({
          recallPointId,
          roundIndex,
        })),
      ),
    [inputRangeQs],
  )
  const recallPointQs = useQueries({
    queries: reviewRecallPointRefs.map((item) => ({
      queryKey: ["recallPoint", pid, item.recallPointId],
      queryFn: () => getRecallPoint(pid, item.recallPointId),
      enabled: !!pid && !!item.recallPointId,
    })),
  })

  if (!pid || !cid) {
    return (
      <div className="space-y-4">
        <ContentNotice
          title="当前页面缺少收敛上下文"
          message="当前链接缺少收敛信息。请先返回复习链，再从对应队列项重新进入。"
          action={<Button onClick={() => navigate(-1)}>返回</Button>}
        />
      </div>
    )
  }

  const reviewTaskIds = convergenceQ.data?.reviewTaskIds ?? []
  const reviewEntries = useMemo<ConvergenceReviewEntry[]>(() => {
    return reviewRecallPointRefs.flatMap((item, index) => {
      const reviewTask = reviewTaskQs[item.roundIndex]?.data
      const recallPoint = recallPointQs[index]?.data
      if (!reviewTask || !recallPoint) return []
      const resultRecallPointIds = new Set(resultRangeQs[item.roundIndex]?.data?.recallPointIds ?? [])
      const outcome =
        reviewTask.state === "DONE"
          ? resultRecallPointIds.has(recallPoint.recallPointId)
            ? "forgotten"
            : "remembered"
          : null
      return [{
        recallPoint,
        reviewTask,
        reviewTaskId: reviewTaskIds[item.roundIndex] ?? reviewTask.reviewTaskId,
        roundIndex: item.roundIndex,
        outcome,
      }]
    })
  }, [recallPointQs, resultRangeQs, reviewRecallPointRefs, reviewTaskIds, reviewTaskQs])
  const activeEntry =
    reviewEntries.find((entry) => entry.recallPoint.recallPointId === activeRecallPointId) ??
    reviewEntries[0] ??
    null
  const activeEntryIndex = activeEntry
    ? reviewEntries.findIndex((entry) => entry.recallPoint.recallPointId === activeEntry.recallPoint.recallPointId)
    : -1
  const reviewWorkspaceLoading =
    reviewTaskQs.some((query) => query.isLoading) ||
    inputRangeQs.some((query) => query.isLoading) ||
    recallPointQs.some((query) => query.isLoading)
  const reviewWorkspaceError =
    reviewTaskQs.find((query) => query.error)?.error ??
    inputRangeQs.find((query) => query.error)?.error ??
    recallPointQs.find((query) => query.error)?.error ??
    null

  useEffect(() => {
    if (reviewEntries.length === 0) {
      setActiveRecallPointId(null)
      return
    }
    if (!activeRecallPointId || !reviewEntries.some((entry) => entry.recallPoint.recallPointId === activeRecallPointId)) {
      setActiveRecallPointId(reviewEntries[0].recallPoint.recallPointId)
    }
  }, [activeRecallPointId, reviewEntries])

  function goToReviewEntry(index: number) {
    const next = reviewEntries[index]
    if (!next) return
    setActiveRecallPointId(next.recallPoint.recallPointId)
  }

  function revealAnswer(recallPointId: string) {
    setRevealedAnswerIds((current) => ({ ...current, [recallPointId]: true }))
  }

  const backAction = (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      className="-ml-2 h-8 rounded-full px-2 text-[#60748c] hover:bg-[#f3f7fb] hover:text-foreground"
      onClick={() => navigate(-1)}
    >
      <ChevronLeft className="h-4 w-4" />
      返回
    </Button>
  )
  const summaryPanel = convergenceQ.data ? (
    <div className="space-y-3">
      <ConvergenceSummaryCard
        topAction={backAction}
        header={<h1 className="truncate text-lg font-semibold">收敛详情</h1>}
        description={
          <>
            项目：<span className="font-medium text-foreground">{projectTitle}</span>
          </>
        }
        items={[
          { label: "状态", value: describeConvergenceState(convergenceQ.data.state) },
          { label: "当前引用", value: formatConvergenceReference(cid) },
          { label: "轮次数", value: convergenceQ.data.roundCount },
          { label: "已生成复习任务", value: reviewTaskIds.length },
          { label: "种子范围", value: formatRangeReference(convergenceQ.data.seedRangeId) },
        ]}
      />
      <Button variant="outline" className="w-full rounded-full" onClick={() => void convergenceQ.refetch()} disabled={convergenceQ.isFetching}>
        <RefreshCw className="h-4 w-4" />
        {convergenceQ.isFetching ? "刷新中..." : "刷新"}
      </Button>
    </div>
  ) : null

  return (
    <div className="space-y-4">
      {convergenceQ.isLoading ? <LoadingNotice title="正在加载收敛详情" message="正在读取收敛状态和已生成轮次。" /> : null}
      {convergenceQ.error ? <ErrorNotice title="收敛加载失败" message={formatApiError(convergenceQ.error)} /> : null}
      {!convergenceQ.isLoading && !convergenceQ.error && !convergenceQ.data ? (
        <ContentNotice
          title="未找到这个收敛步骤"
          message="这个收敛步骤可能已经失效，或当前链接中的 ID 已经过期。"
          action={<Button variant="outline" onClick={() => navigate(-1)}>返回上一页</Button>}
        />
      ) : null}

      {convergenceQ.data ? (
        <div className="grid gap-4 xl:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)] xl:items-start">
          {summaryPanel ? <aside className="xl:sticky xl:top-28 xl:self-start">{summaryPanel}</aside> : <div />}
          <div className="min-w-0">
            <ConvergenceReviewWorkspaceCard
              title="复习工作区"
              description="按轮次顺序查看这一步收敛已经产出的复习任务，并进入每一轮的复习详情。"
              isLoading={reviewWorkspaceLoading}
              error={reviewWorkspaceError}
              emptyState={
                reviewTaskIds.length === 0 || (!reviewWorkspaceLoading && reviewEntries.length === 0) ? (
                  <ContentEmptyState
                    title="这一步收敛还没有生成复习任务"
                    message="首次推进收敛后，生成出来的第 1 轮及后续各轮复习任务会按顺序显示在这里。"
                  />
                ) : null
              }
              activeEntry={activeEntry}
              activeEntryIndex={activeEntryIndex}
              entryCount={reviewEntries.length}
              revealed={activeEntry ? Boolean(revealedAnswerIds[activeEntry.recallPoint.recallPointId]) : false}
              onPrevious={() => goToReviewEntry(activeEntryIndex - 1)}
              onNext={() => goToReviewEntry(activeEntryIndex + 1)}
              onRevealAnswer={() => activeEntry ? revealAnswer(activeEntry.recallPoint.recallPointId) : undefined}
              projectId={pid}
            />
          </div>
        </div>
      ) : null}
    </div>
  )
}

type SummaryItem = {
  label: string
  value: ReactNode
}

function ConvergenceSummaryCard({
  description,
  header,
  items,
  topAction,
}: {
  description?: ReactNode
  header: ReactNode
  items: SummaryItem[]
  topAction?: ReactNode
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        {topAction ? <div className="flex items-center">{topAction}</div> : null}
        <div className="min-w-0">{header}</div>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-3">
          {items.map((item) => (
            <div
              key={item.label}
              className="min-w-[10rem] flex-1 rounded-xl border border-[#dbe4ee] bg-[#f8fafc] px-4 py-3 shadow-[0_10px_24px_-24px_rgba(15,23,42,0.6)]"
            >
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#64748b]">{item.label}</div>
              <div className="mt-1.5 break-words text-sm font-semibold text-slate-900">{item.value}</div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function ConvergenceReviewWorkspaceCard({
  activeEntry,
  activeEntryIndex,
  description,
  emptyState,
  entryCount,
  error,
  isLoading,
  onNext,
  onPrevious,
  onRevealAnswer,
  projectId,
  revealed,
  title,
}: {
  activeEntry: ConvergenceReviewEntry | null
  activeEntryIndex: number
  description?: string
  emptyState?: ReactNode
  entryCount: number
  error?: unknown
  isLoading?: boolean
  onNext: () => void
  onPrevious: () => void
  onRevealAnswer: () => void
  projectId: string
  revealed: boolean
  title: string
}) {
  return (
    <Card className="theme-card-main">
      <CardHeader className="theme-card-header flex-col gap-4 space-y-0 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle>{title}</CardTitle>
          <CardDescription>
            {activeEntry
              ? `当前 ${activeEntryIndex + 1}/${entryCount} · ${formatRecallPointReference(activeEntry.recallPoint.recallPointId)}`
              : description}
          </CardDescription>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={onPrevious} disabled={activeEntryIndex <= 0}>
            <ChevronLeft className="h-4 w-4" />
            上一个
          </Button>
          <Button variant="outline" size="sm" onClick={onNext} disabled={activeEntryIndex < 0 || activeEntryIndex >= entryCount - 1}>
            下一个
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? <LoadingNotice title="正在加载轮次任务" message="正在读取每一轮复习任务的状态和时间信息。" /> : null}
        {error ? <ErrorNotice title="复习工作区加载失败" message={formatApiError(error)} /> : null}
        {!isLoading && !error && emptyState ? emptyState : null}
        {!isLoading && !error && activeEntry ? (
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(16rem,0.72fr)]">
            <section className="space-y-4">
              <div className="space-y-2 border-t border-border/60 pt-4 first:border-t-0">
                <div className="text-xs font-medium text-muted-foreground">问题</div>
                <RichContentRenderer projectId={projectId} value={activeEntry.recallPoint.question} />
              </div>

              <div className="space-y-3 border-t border-border/60 pt-4">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-xs font-medium text-muted-foreground">答案</div>
                  {!revealed ? (
                    <Button type="button" size="sm" variant="outline" onClick={onRevealAnswer}>
                      显示答案
                    </Button>
                  ) : null}
                </div>
                {revealed ? (
                  <RichContentRenderer projectId={projectId} value={activeEntry.recallPoint.answer} />
                ) : (
                  <div className="text-sm text-muted-foreground">先在脑中复述，再点开答案核对。</div>
                )}
              </div>
            </section>

            <section className="space-y-5 border-t border-border/60 pt-4 lg:border-l lg:border-t-0 lg:pl-5 lg:pt-0">
              <div className="space-y-3">
                <div className="text-sm font-medium">复习判断</div>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-1">
                  <Button type="button" variant={activeEntry.outcome === "remembered" ? "default" : "outline"}>
                    <CheckCircle2 className="h-4 w-4" />
                    记得
                  </Button>
                  <Button type="button" variant={activeEntry.outcome === "forgotten" ? "destructive" : "outline"}>
                    <XCircle className="h-4 w-4" />
                    不记得
                  </Button>
                </div>
              </div>

              <div className="space-y-3 text-sm">
                <div className="flex items-center justify-between gap-3 border-t border-border/60 pt-3">
                  <span className="text-muted-foreground">来源</span>
                  <span className="font-medium text-foreground">第 {activeEntry.roundIndex + 1} 轮</span>
                </div>
                <div className="flex items-center justify-between gap-3 border-t border-border/60 pt-3">
                  <span className="text-muted-foreground">复习任务</span>
                  <Link className="font-medium text-primary underline-offset-4 hover:underline" to={`/p/${projectId}/review-tasks/${activeEntry.reviewTaskId}`}>
                    {formatReviewTaskReference(activeEntry.reviewTaskId)}
                  </Link>
                </div>
                <div className="flex items-center justify-between gap-3 border-t border-border/60 pt-3">
                  <span className="text-muted-foreground">任务状态</span>
                  <span className="font-medium text-foreground">{describeReviewTaskState(activeEntry.reviewTask.state)}</span>
                </div>
                <div className="border-t border-border/60 pt-3">
                  <div className="text-muted-foreground">最近复习</div>
                  <div className="mt-1 font-medium text-foreground">
                    {formatReviewOutcome(activeEntry.outcome)} · {formatTs(activeEntry.reviewTask.executedAt)}
                  </div>
                </div>
                <div className="border-t border-border/60 pt-3">
                  <div className="text-muted-foreground">锚点</div>
                  <div className="mt-1 font-medium text-foreground">{formatAnchorLabel(activeEntry.recallPoint)}</div>
                </div>
              </div>

              <Button variant="outline" size="sm" asChild>
                <Link to={`/p/${projectId}/recall-points/${activeEntry.recallPoint.recallPointId}`}>打开复述点详情</Link>
              </Button>
            </section>
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

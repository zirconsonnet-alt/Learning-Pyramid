import { type ReactNode } from "react"
import { useQueries } from "@tanstack/react-query"
import { ChevronLeft, RefreshCw } from "lucide-react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import type { ProjectScope } from "@/ui/api/projectScope"
import type { ReviewTask } from "@/ui/api/review"
import { getRangeSnapshot, getReviewTask } from "@/ui/api/review"
import { ContentEmptyState, ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import {
  formatConvergenceReference,
  formatRangeReference,
  formatReviewTaskReference,
} from "@/ui/displayIdentifiers"
import { buildScopedProjectPath } from "@/ui/projectPaths"
import { useProject } from "@/ui/queries/projects"
import { useConvergence } from "@/ui/queries/reviewChains"
import { cn } from "@/ui/utils"

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

type ConvergenceRoundEntry = {
  inputCount: number | null
  resultCount: number | null
  reviewTask: ReviewTask
  reviewTaskId: string
  roundIndex: number
}

export function ConvergencePage() {
  const { subjectId = "", projectId, convergenceId } = useParams()
  const navigate = useNavigate()
  const pid = projectId ?? ""
  const cid = convergenceId ?? ""
  const projectScope: ProjectScope | null = subjectId && pid ? { subjectId, projectId: pid } : null
  const { projectTitle } = useProject(projectScope)
  const convergenceQ = useConvergence(projectScope, cid)

  const reviewTaskQs = useQueries({
    queries:
      convergenceQ.data?.reviewTaskIds.map((reviewTaskId) => ({
        queryKey: ["reviewTask", subjectId, pid, reviewTaskId],
        queryFn: () => getReviewTask(projectScope as ProjectScope, reviewTaskId),
        enabled: !!projectScope,
      })) ?? [],
  })
  const inputRangeQs = useQueries({
    queries: reviewTaskQs.map((query) => {
      const inputRangeId = query.data?.inputRangeId ?? ""
      return {
        queryKey: ["range", subjectId, pid, inputRangeId],
        queryFn: () => getRangeSnapshot(projectScope as ProjectScope, inputRangeId),
        enabled: !!projectScope && !!inputRangeId,
      }
    }),
  })
  const resultRangeQs = useQueries({
    queries: reviewTaskQs.map((query) => {
      const resultRangeId = query.data?.resultRangeId ?? ""
      return {
        queryKey: ["range", subjectId, pid, resultRangeId],
        queryFn: () => getRangeSnapshot(projectScope as ProjectScope, resultRangeId),
        enabled: !!projectScope && !!resultRangeId,
      }
    }),
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
  const roundEntries: ConvergenceRoundEntry[] = reviewTaskQs.flatMap((query, roundIndex) => {
    const reviewTask = query.data
    if (!reviewTask) return []
    return [
      {
        inputCount: inputRangeQs[roundIndex]?.data?.recallPointIds.length ?? null,
        resultCount: reviewTask.resultRangeId ? (resultRangeQs[roundIndex]?.data?.recallPointIds.length ?? null) : null,
        reviewTask,
        reviewTaskId: reviewTaskIds[roundIndex] ?? reviewTask.reviewTaskId,
        roundIndex,
      },
    ]
  })
  const roundListLoading = reviewTaskQs.some((query) => query.isLoading) || inputRangeQs.some((query) => query.isLoading)
  const roundListError =
    reviewTaskQs.find((query) => query.error)?.error ??
    inputRangeQs.find((query) => query.error)?.error ??
    resultRangeQs.find((query) => query.error)?.error ??
    null

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
            <ConvergenceRoundListCard
              title="复习轮次"
              isLoading={roundListLoading}
              error={roundListError}
              emptyState={
                reviewTaskIds.length === 0 || (!roundListLoading && roundEntries.length === 0) ? (
                  <ContentEmptyState
                    title="这一步收敛还没有生成复习任务"
                    message="首次推进收敛后，生成出来的第 1 轮及后续轮次会按顺序显示在这里。"
                  />
                ) : null
              }
              entries={roundEntries}
              subjectId={subjectId}
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

function ConvergenceRoundListCard({
  description,
  emptyState,
  entries,
  error,
  isLoading,
  projectId,
  subjectId,
  title,
}: {
  description?: string
  emptyState?: ReactNode
  entries: ConvergenceRoundEntry[]
  error?: unknown
  isLoading?: boolean
  projectId: string
  subjectId: string
  title: string
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div>
          <CardTitle>{title}</CardTitle>
          {description ? <CardDescription>{description}</CardDescription> : null}
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? <LoadingNotice title="正在加载轮次任务" message="正在读取每一轮复习任务的状态和时间信息。" /> : null}
        {error ? <ErrorNotice title="复习轮次加载失败" message={formatApiError(error)} /> : null}
        {!isLoading && !error && emptyState ? emptyState : null}
        {!isLoading && !error && entries.length > 0 ? (
          <div className="space-y-3">
            {entries.map((entry) => (
              <div
                key={entry.reviewTaskId}
                className={cn(
                  "rounded-[1rem] border border-[#dbe4ee] bg-[#fbfdff] p-4 shadow-[0_12px_28px_-28px_rgba(15,23,42,0.6)]",
                  entry.reviewTask.state === "DONE" && "bg-emerald-50/40",
                )}
              >
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                  <div className="min-w-0 flex-1 space-y-3">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="rounded-full bg-[#eef5ff] px-2.5 py-1 font-medium text-primary">
                        第 {entry.roundIndex + 1} 轮
                      </span>
                      <span className="rounded-full border border-[#dbe4ee] bg-white px-2.5 py-1 font-medium text-slate-600">
                        {formatReviewTaskReference(entry.reviewTaskId)}
                      </span>
                      <span
                        className={cn(
                          "rounded-full border px-2.5 py-1 font-medium",
                          entry.reviewTask.state === "DONE"
                            ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                            : "border-slate-200 bg-slate-50 text-slate-600",
                        )}
                      >
                        {describeReviewTaskState(entry.reviewTask.state)}
                      </span>
                    </div>
                    <div className="grid gap-3 text-xs text-muted-foreground md:grid-cols-4">
                      <RoundMetric label="输入范围" value={formatRangeReference(entry.reviewTask.inputRangeId)} />
                      <RoundMetric label="输入题数" value={entry.inputCount ?? "读取中..."} />
                      <RoundMetric
                        label="结果范围"
                        value={entry.reviewTask.resultRangeId ? formatRangeReference(entry.reviewTask.resultRangeId) : "-"}
                      />
                      <RoundMetric label="结果题数" value={entry.resultCount ?? (entry.reviewTask.resultRangeId ? "读取中..." : "-")} />
                      <RoundMetric label="执行时间" value={formatTs(entry.reviewTask.executedAt)} />
                    </div>
                  </div>
                  <div className="flex shrink-0 flex-wrap gap-2 md:w-[11rem] md:flex-col md:items-stretch">
                    <Button size="sm" className="rounded-full md:w-full" asChild>
                      <Link to={buildScopedProjectPath(subjectId, projectId, `/review-tasks/${entry.reviewTaskId}`)}>查看复习任务</Link>
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

function RoundMetric({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-xl border border-[#dbe4ee] bg-[#f8fafc] p-3">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#64748b]">{label}</div>
      <div className="mt-1.5 break-words text-sm font-semibold text-slate-900">{value}</div>
    </div>
  )
}

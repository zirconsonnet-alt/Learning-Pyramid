import { type ReactNode } from "react"
import { useQueries } from "@tanstack/react-query"
import { GitBranch, RefreshCw } from "lucide-react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import type { ScopedProjectRef } from "@/ui/api/projectScope"
import type { Convergence, ReviewTask } from "@/ui/api/review"
import { getConvergence, getReviewTask } from "@/ui/api/review"
import { ContentEmptyState, ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { buildScopedProjectPath } from "@/ui/projectPaths"
import { useReviewChain, useReviewChainBinding } from "@/ui/queries/reviewChains"
import { cn } from "@/ui/utils"
import { DetailSummaryCard } from "@/views/shared/DetailSummaryCard"

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

function describeReviewChainState(state: string) {
  if (state === "IN_PROGRESS") return "进行中"
  if (state === "TERMINATED") return "已完成"
  return state
}

function describeQueueItemKind(kind: "CONVERGENCE" | "REVIEW_TASK") {
  return kind === "REVIEW_TASK" ? "复习任务" : "收敛步骤"
}

function describeReviewTaskState(state: string) {
  if (state === "PENDING") return "待执行"
  if (state === "DONE") return "已完成"
  return state
}

function describeConvergenceState(state: string) {
  if (state === "IN_PROGRESS") return "进行中"
  if (state === "TERMINATED") return "已完成"
  return state
}

function reviewTaskDetailPath(subjectId: string, projectId: string, reviewTaskId: string) {
  return buildScopedProjectPath(subjectId, projectId, `/review-tasks/${reviewTaskId}`)
}

function convergenceDetailPath(subjectId: string, projectId: string, convergenceId: string) {
  return buildScopedProjectPath(subjectId, projectId, `/convergences/${convergenceId}`)
}

export function ReviewChainPage() {
  const { subjectId = "", scopedProjectId, reviewChainId } = useParams()
  const navigate = useNavigate()
  const pid = scopedProjectId ?? ""
  const chainId = reviewChainId ?? ""
  const projectScope: ScopedProjectRef | null = subjectId && pid ? { subjectId, scopedProjectId: pid } : null
  const chainQ = useReviewChain(projectScope, chainId)
  const bindingQ = useReviewChainBinding(projectScope, chainId)

  const itemDetails = useQueries({
    queries:
      chainQ.data?.queue.map((item) =>
        item.kind === "REVIEW_TASK"
          ? {
              queryKey: ["reviewTask", subjectId, pid, item.id],
              queryFn: () => getReviewTask(projectScope as ScopedProjectRef, item.id),
              enabled: !!projectScope,
            }
          : {
              queryKey: ["convergence", subjectId, pid, item.id],
              queryFn: () => getConvergence(projectScope as ScopedProjectRef, item.id),
              enabled: !!projectScope,
            },
      ) ?? [],
  })

  if (!subjectId || !pid || !chainId) {
    return (
      <div className="space-y-4">
        <ContentNotice
          title="当前页面缺少复习链上下文"
          message="当前链接缺少复习链信息。请先返回项目列表，再从任务树或工作台重新进入。"
          action={<Button onClick={() => navigate("/subjects")}>返回学科中心</Button>}
        />
      </div>
    )
  }

  const queue = chainQ.data?.queue ?? []
  const headItem = chainQ.data && chainQ.data.headIndex < queue.length ? queue[chainQ.data.headIndex] : null
  const headReviewTaskPath = headItem?.kind === "REVIEW_TASK" ? reviewTaskDetailPath(subjectId, pid, headItem.id) : null
  const headConvergencePath = headItem?.kind === "CONVERGENCE" ? convergenceDetailPath(subjectId, pid, headItem.id) : null
  const headLabel = headItem ? describeQueueItemKind(headItem.kind) : "已完成"
  const headValue = headItem ? (
    headReviewTaskPath ? (
      <Link className="text-primary underline-offset-4 hover:underline" to={headReviewTaskPath}>
        {headLabel}
      </Link>
    ) : headConvergencePath ? (
      <Link className="text-primary underline-offset-4 hover:underline" to={headConvergencePath}>
        {headLabel}
      </Link>
    ) : (
      headLabel
    )
  ) : (
    "已完成"
  )
  const entryValue = bindingQ.data ? (
    <Link
      className="text-primary underline-offset-4 hover:underline"
      to={buildScopedProjectPath(subjectId, pid, `/learning-task-nodes/${bindingQ.data.entryNodeId}`)}
    >
      {bindingQ.data.entryNodeTitle}
    </Link>
  ) : bindingQ.isLoading ? (
    "读取中..."
  ) : (
    "暂未关联"
  )
  const summaryPanel = chainQ.data ? (
    <div className="space-y-3">
      <DetailSummaryCard
        icon={GitBranch}
        title="复习链"
        items={[
          { label: "状态", value: describeReviewChainState(chainQ.data.state) },
          { label: "队列长度", value: chainQ.data.queue.length },
          {
            label: "目标层级",
            value: bindingQ.data ? `L${bindingQ.data.targetLayerIndex}` : bindingQ.isLoading ? "读取中..." : "-",
          },
          { label: "关联入口", value: entryValue },
          { label: "当前任务", value: headValue },
        ]}
      />
      {bindingQ.error ? <ErrorNotice title="复习链绑定加载失败" message={formatApiError(bindingQ.error)} /> : null}
      <Button variant="outline" className="w-full rounded-full" onClick={() => void chainQ.refetch()} disabled={chainQ.isFetching}>
        <RefreshCw className="h-4 w-4" />
        {chainQ.isFetching ? "刷新中..." : "刷新"}
      </Button>
    </div>
  ) : null

  return (
    <div className="space-y-4">
      {chainQ.isLoading ? <LoadingNotice title="正在加载复习链" message="正在读取队列 head、执行状态以及各个队列项详情。" /> : null}
      {chainQ.error ? <ErrorNotice title="复习链加载失败" message={formatApiError(chainQ.error)} /> : null}
      {!chainQ.isLoading && !chainQ.error && !chainQ.data ? (
        <ContentNotice
          title="未找到这条复习链"
          message="这条复习链可能已经被清理，或当前入口已失效。请返回工作台继续处理当前项目。"
          action={
            <Button variant="outline" asChild>
              <Link to={buildScopedProjectPath(subjectId, pid, "/workbench")}>返回工作台</Link>
            </Button>
          }
        />
      ) : null}

      {chainQ.data ? (
        <div className="grid gap-4 xl:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)] xl:items-start">
          {summaryPanel ? <aside className="xl:sticky xl:top-28 xl:self-start">{summaryPanel}</aside> : <div />}
          <div className="min-w-0">
            <ReviewChainQueueListCard title="复习链队列">
              {queue.map((item, index) => {
                const detailQ = itemDetails[index]
                const isDone = index < chainQ.data.headIndex
                const isHead = index === chainQ.data.headIndex
                const reviewTask = item.kind === "REVIEW_TASK" ? (detailQ?.data as ReviewTask | undefined) : undefined
                const convergence = item.kind === "CONVERGENCE" ? (detailQ?.data as Convergence | undefined) : undefined
                const detailPath =
                  item.kind === "REVIEW_TASK" ? reviewTaskDetailPath(subjectId, pid, item.id) : convergenceDetailPath(subjectId, pid, item.id)

                return (
                  <div
                    key={`${item.kind}:${item.id}`}
                    className={cn(
                      "rounded-[1rem] border border-[#dbe4ee] bg-[#fbfdff] p-4 shadow-[0_12px_28px_-28px_rgba(15,23,42,0.6)]",
                      isHead && "border-primary bg-primary/5",
                      isDone && "opacity-70",
                    )}
                  >
                    <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                      <div className="min-w-0 flex-1 space-y-3">
                        <div className="flex flex-wrap items-center gap-2 text-xs">
                          <span className="rounded-full bg-[#eef5ff] px-2.5 py-1 font-medium text-primary">
                            第 {index + 1} 项
                          </span>
                          <span className="rounded-full border border-[#dbe4ee] bg-[#f8fafc] px-2.5 py-1 font-medium text-slate-600">
                            {describeQueueItemKind(item.kind)}
                          </span>
                          <span
                            className={cn(
                              "rounded-full border px-2.5 py-1 font-medium",
                              isHead
                                ? "border-blue-200 bg-blue-50 text-blue-700"
                                : isDone
                                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                                  : "border-slate-200 bg-slate-50 text-slate-600",
                            )}
                          >
                            {isHead ? "当前 head" : isDone ? "已推进" : "待执行"}
                          </span>
                        </div>

                        {detailQ?.isLoading ? <p className="text-xs text-muted-foreground">加载详情中...</p> : null}
                        {detailQ?.error ? <p className="text-xs text-destructive">{formatApiError(detailQ.error)}</p> : null}

                        {item.kind === "REVIEW_TASK" && reviewTask ? (
                          <div className="grid gap-3 text-xs text-muted-foreground md:grid-cols-2">
                            <QueueItemMetric label="状态" value={describeReviewTaskState(reviewTask.state)} />
                            <QueueItemMetric label="执行时间" value={formatTs(reviewTask.executedAt)} />
                          </div>
                        ) : null}

                        {item.kind === "CONVERGENCE" && convergence ? (
                          <div className="grid gap-3 text-xs text-muted-foreground md:grid-cols-2">
                            <QueueItemMetric label="状态" value={describeConvergenceState(convergence.state)} />
                            <QueueItemMetric label="轮次" value={convergence.roundCount} />
                          </div>
                        ) : null}
                      </div>

                      <div className="flex shrink-0 flex-wrap gap-2 md:w-[11rem] md:flex-col md:items-stretch">
                        <Button size="sm" className="rounded-full md:w-full" asChild>
                          <Link to={detailPath}>查看详情</Link>
                        </Button>
                      </div>
                    </div>
                  </div>
                )
              })}

              {queue.length === 0 ? (
                <ContentEmptyState
                  title="当前复习链还没有队列项"
                  message="这个项目生成复习任务或收敛步骤后，队列会显示在这里。"
                />
              ) : null}
            </ReviewChainQueueListCard>
          </div>
        </div>
      ) : null}
    </div>
  )
}

function ReviewChainQueueListCard({
  children,
  description,
  title,
}: {
  children: ReactNode
  description?: string
  title: string
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle>{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent>
        <div className="space-y-3">{children}</div>
      </CardContent>
    </Card>
  )
}

function QueueItemMetric({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-xl border border-[#dbe4ee] bg-[#f8fafc] p-3">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#64748b]">{label}</div>
      <div className="mt-1.5 break-words text-sm font-semibold text-slate-900">{value}</div>
    </div>
  )
}

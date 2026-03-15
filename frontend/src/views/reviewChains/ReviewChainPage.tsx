import { useQueries } from "@tanstack/react-query"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import type { Convergence, ReviewTask } from "@/ui/api/review"
import { getConvergence, getReviewTask } from "@/ui/api/review"
import { ContentEmptyState, ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import {
  formatConvergenceReference,
  formatRangeReference,
  formatReviewChainReference,
  formatReviewTaskReference,
} from "@/ui/displayIdentifiers"
import { useProject } from "@/ui/queries/projects"
import { useReviewChain } from "@/ui/queries/reviewChains"
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

function formatQueueItemReference(kind: "CONVERGENCE" | "REVIEW_TASK", id: string) {
  return kind === "REVIEW_TASK" ? formatReviewTaskReference(id) : formatConvergenceReference(id)
}

export function ReviewChainPage() {
  const { projectId, reviewChainId } = useParams()
  const navigate = useNavigate()
  const pid = projectId ?? ""
  const chainId = reviewChainId ?? ""
  const { projectTitle } = useProject(pid)
  const chainQ = useReviewChain(pid, chainId)

  const itemDetails = useQueries({
    queries:
      chainQ.data?.queue.map((item) =>
        item.kind === "REVIEW_TASK"
          ? {
              queryKey: ["reviewTask", pid, item.id],
              queryFn: () => getReviewTask(pid, item.id),
              enabled: !!pid,
            }
          : {
              queryKey: ["convergence", pid, item.id],
              queryFn: () => getConvergence(pid, item.id),
              enabled: !!pid,
            },
      ) ?? [],
  })

  if (!pid || !chainId) {
    return (
      <div className="space-y-4">
        <ContentNotice
          title="当前页面缺少复习链上下文"
          message="当前链接缺少复习链信息。请先返回项目列表，再从任务树或工作台重新进入。"
          action={<Button onClick={() => navigate("/projects")}>返回项目列表</Button>}
        />
      </div>
    )
  }

  const queue = chainQ.data?.queue ?? []
  const headItem = chainQ.data && chainQ.data.headIndex < queue.length ? queue[chainQ.data.headIndex] : null

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <h1 className="text-lg font-semibold">复习链</h1>
        <p className="text-sm text-muted-foreground">
          项目：<span className="font-medium text-foreground">{projectTitle}</span>
        </p>
        <p className="text-sm text-muted-foreground">
          当前引用：<span className="font-medium text-foreground">{formatReviewChainReference(chainId)}</span>
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>链状态</CardTitle>
          <CardDescription>查看当前 head、队列长度和每个队列项的详情。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {chainQ.isLoading ? <LoadingNotice title="正在加载复习链" message="正在读取队列 head、执行状态以及各个队列项详情。" /> : null}
          {chainQ.error ? <ErrorNotice title="复习链加载失败" message={formatApiError(chainQ.error)} /> : null}
          {!chainQ.isLoading && !chainQ.error && !chainQ.data ? (
            <ContentNotice
              title="未找到这条复习链"
              message="这条复习链可能已经被清理，或当前入口已失效。请返回工作台继续处理当前项目。"
              action={
                <Button variant="outline" asChild>
                  <Link to={`/p/${pid}/workbench`}>返回工作台</Link>
                </Button>
              }
            />
          ) : null}

          {chainQ.data ? (
            <>
              <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-md border bg-muted/30 p-3">
                  <div className="text-xs text-muted-foreground">状态</div>
                  <div className="mt-1 font-medium text-foreground">{describeReviewChainState(chainQ.data.state)}</div>
                </div>
                <div className="rounded-md border bg-muted/30 p-3">
                  <div className="text-xs text-muted-foreground">队列长度</div>
                  <div className="mt-1 font-medium text-foreground">{chainQ.data.queue.length}</div>
                </div>
                <div className="rounded-md border bg-muted/30 p-3">
                  <div className="text-xs text-muted-foreground">当前 head</div>
                  <div className="mt-1 font-medium text-foreground">
                    {headItem ? `${describeQueueItemKind(headItem.kind)} · ${formatQueueItemReference(headItem.kind, headItem.id)}` : "已完成"}
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                {queue.map((item, index) => {
                  const detailQ = itemDetails[index]
                  const isDone = index < chainQ.data.headIndex
                  const isHead = index === chainQ.data.headIndex
                  const reviewTask = item.kind === "REVIEW_TASK" ? (detailQ?.data as ReviewTask | undefined) : undefined
                  const convergence = item.kind === "CONVERGENCE" ? (detailQ?.data as Convergence | undefined) : undefined

                  return (
                    <div
                      key={`${item.kind}:${item.id}`}
                      className={cn(
                        "rounded-md border p-3",
                        isHead && "border-primary bg-primary/5",
                        isDone && "opacity-70",
                      )}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="text-xs text-muted-foreground">队列位次 #{index + 1}</div>
                          <div className="mt-1 flex items-center gap-2">
                            <span className="rounded-full border px-2 py-0.5 text-xs">{describeQueueItemKind(item.kind)}</span>
                            <span className="text-xs text-muted-foreground">{formatQueueItemReference(item.kind, item.id)}</span>
                          </div>
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {isHead ? "当前 head" : isDone ? "已推进" : "待执行"}
                        </div>
                      </div>

                      {detailQ?.isLoading ? <p className="mt-2 text-xs text-muted-foreground">加载详情中...</p> : null}
                      {detailQ?.error ? <p className="mt-2 text-xs text-destructive">{formatApiError(detailQ.error)}</p> : null}

                      {item.kind === "REVIEW_TASK" && reviewTask ? (
                        <div className="mt-2 grid gap-2 text-xs text-muted-foreground md:grid-cols-3">
                          <div>状态：<span className="text-foreground">{describeReviewTaskState(reviewTask.state)}</span></div>
                          <div>创建时间：<span className="text-foreground">{formatTs(reviewTask.createdAt)}</span></div>
                          <div>输入范围：<span className="text-foreground">{formatRangeReference(reviewTask.inputRangeId)}</span></div>
                        </div>
                      ) : null}

                      {item.kind === "CONVERGENCE" && convergence ? (
                        <div className="mt-2 grid gap-2 text-xs text-muted-foreground md:grid-cols-3">
                          <div>状态：<span className="text-foreground">{describeConvergenceState(convergence.state)}</span></div>
                          <div>轮次：<span className="text-foreground">{convergence.roundCount}</span></div>
                          <div>种子范围：<span className="text-foreground">{formatRangeReference(convergence.seedRangeId)}</span></div>
                        </div>
                      ) : null}
                    </div>
                  )
                })}

                {queue.length === 0 ? (
                  <ContentEmptyState
                    title="当前复习链还没有队列项"
                    message="这个项目生成复习任务或收敛步骤后，队列会显示在这里。"
                  />
                ) : null}
              </div>

              <div className="pt-1">
                <Button variant="outline" asChild>
                  <Link to={`/p/${pid}/workbench`}>返回工作台</Link>
                </Button>
              </div>
            </>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}

import { useQueries } from "@tanstack/react-query"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import type { Convergence, ReviewTask } from "@/ui/api/review"
import { getConvergence, getReviewTask } from "@/ui/api/review"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
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
      <div className="space-y-2">
        <p className="text-sm text-muted-foreground">缺少 projectId 或 reviewChainId。</p>
        <Button onClick={() => navigate("/projects")}>返回项目列表</Button>
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
          链：<span className="font-mono text-foreground">{chainId}</span>
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>链状态</CardTitle>
          <CardDescription>查看当前 head、队列长度和每个队列项的详情。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {chainQ.isLoading ? <p className="text-sm text-muted-foreground">加载中...</p> : null}
          {chainQ.error ? <p className="text-sm text-destructive">{formatApiError(chainQ.error)}</p> : null}

          {chainQ.data ? (
            <>
              <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-md border bg-muted/30 p-3">
                  <div className="text-xs text-muted-foreground">状态</div>
                  <div className="mt-1 font-medium text-foreground">{chainQ.data.state}</div>
                </div>
                <div className="rounded-md border bg-muted/30 p-3">
                  <div className="text-xs text-muted-foreground">队列长度</div>
                  <div className="mt-1 font-medium text-foreground">{chainQ.data.queue.length}</div>
                </div>
                <div className="rounded-md border bg-muted/30 p-3">
                  <div className="text-xs text-muted-foreground">当前 head</div>
                  <div className="mt-1 font-medium text-foreground">
                    {headItem ? `${headItem.kind} · ${headItem.id}` : "已完成"}
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
                            <span className="rounded-full border px-2 py-0.5 text-xs">{item.kind}</span>
                            <span className="font-mono text-xs text-muted-foreground">{item.id}</span>
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
                          <div>状态：<span className="text-foreground">{reviewTask.state}</span></div>
                          <div>创建时间：<span className="text-foreground">{formatTs(reviewTask.createdAt)}</span></div>
                          <div>输入范围：<span className="font-mono text-foreground">{reviewTask.inputRangeId}</span></div>
                        </div>
                      ) : null}

                      {item.kind === "CONVERGENCE" && convergence ? (
                        <div className="mt-2 grid gap-2 text-xs text-muted-foreground md:grid-cols-3">
                          <div>状态：<span className="text-foreground">{convergence.state}</span></div>
                          <div>轮次：<span className="text-foreground">{convergence.roundCount}</span></div>
                          <div>种子范围：<span className="font-mono text-foreground">{convergence.seedRangeId}</span></div>
                        </div>
                      ) : null}
                    </div>
                  )
                })}

                {queue.length === 0 ? <p className="text-sm text-muted-foreground">当前复习链为空。</p> : null}
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

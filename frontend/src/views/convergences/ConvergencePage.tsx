import { useQueries } from "@tanstack/react-query"
import { useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import type { ReviewTask } from "@/ui/api/review"
import { getReviewTask } from "@/ui/api/review"
import { ContentEmptyState, ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import {
  formatConvergenceReference,
  formatRangeReference,
  formatReviewTaskReference,
} from "@/ui/displayIdentifiers"
import { useProject } from "@/ui/queries/projects"
import { useConvergence } from "@/ui/queries/reviewChains"
import { ReviewTaskSummaryCard } from "@/views/reviewTasks/components/ReviewTaskSummaryCard"

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

export function ConvergencePage() {
  const { projectId, convergenceId } = useParams()
  const navigate = useNavigate()
  const pid = projectId ?? ""
  const cid = convergenceId ?? ""
  const { projectTitle } = useProject(pid)
  const convergenceQ = useConvergence(pid, cid)

  const reviewTaskQs = useQueries({
    queries:
      convergenceQ.data?.reviewTaskIds.map((reviewTaskId) => ({
        queryKey: ["reviewTask", pid, reviewTaskId],
        queryFn: () => getReviewTask(pid, reviewTaskId),
        enabled: !!pid,
      })) ?? [],
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

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">收敛详情</h1>
          <p className="text-sm text-muted-foreground">
            项目：<span className="font-medium text-foreground">{projectTitle}</span>
          </p>
          <p className="text-sm text-muted-foreground">
            当前引用：<span className="font-medium text-foreground">{formatConvergenceReference(cid)}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => navigate(-1)}>
            返回
          </Button>
          <Button variant="outline" onClick={() => void convergenceQ.refetch()} disabled={convergenceQ.isFetching}>
            {convergenceQ.isFetching ? "刷新中..." : "刷新"}
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>收敛概览</CardTitle>
          <CardDescription>收敛会按轮次生成复习任务；下面会直接列出它已经生成的所有复习任务。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
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
            <div className="grid gap-3 md:grid-cols-4">
              <div className="rounded-md border bg-muted/30 p-3">
                <div className="text-xs text-muted-foreground">状态</div>
                <div className="mt-1 font-medium text-foreground">{describeConvergenceState(convergenceQ.data.state)}</div>
              </div>
              <div className="rounded-md border bg-muted/30 p-3">
                <div className="text-xs text-muted-foreground">轮次数</div>
                <div className="mt-1 font-medium text-foreground">{convergenceQ.data.roundCount}</div>
              </div>
              <div className="rounded-md border bg-muted/30 p-3">
                <div className="text-xs text-muted-foreground">已生成复习任务</div>
                <div className="mt-1 font-medium text-foreground">{reviewTaskIds.length}</div>
              </div>
              <div className="rounded-md border bg-muted/30 p-3">
                <div className="text-xs text-muted-foreground">种子范围</div>
                <div className="mt-1 font-medium text-foreground">{formatRangeReference(convergenceQ.data.seedRangeId)}</div>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>已生成复习任务</CardTitle>
          <CardDescription>按轮次顺序查看这一步收敛已经产出的复习任务，并进入每一轮的复习详情。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {convergenceQ.data && reviewTaskQs.some((query) => query.isLoading) ? (
            <LoadingNotice title="正在加载轮次任务" message="正在读取每一轮复习任务的状态和时间信息。" />
          ) : null}

          {reviewTaskQs.map((query, index) => {
            const reviewTaskId = reviewTaskIds[index]

            if (query.error) {
              return (
                <div key={reviewTaskId} className="rounded-md border border-destructive/20 p-3 text-sm text-destructive">
                  第 {index + 1} 轮 {formatReviewTaskReference(reviewTaskId)} 加载失败：{formatApiError(query.error)}
                </div>
              )
            }

            const reviewTask = query.data as ReviewTask | undefined
            if (!reviewTask) return null

            return (
              <ReviewTaskSummaryCard
                key={reviewTaskId}
                fields={[
                  { label: "创建时间", value: formatTs(reviewTask.createdAt) },
                  { label: "执行时间", value: formatTs(reviewTask.executedAt) },
                  { label: "输入范围", value: formatRangeReference(reviewTask.inputRangeId) },
                ]}
                kicker={`第 ${index + 1} 轮`}
                projectId={pid}
                reviewTaskId={reviewTaskId}
                stateLabel={describeReviewTaskState(reviewTask.state)}
              />
            )
          })}

          {convergenceQ.data && reviewTaskIds.length === 0 ? (
            <ContentEmptyState
              title="这一步收敛还没有生成复习任务"
              message="首次推进收敛后，生成出来的第 1 轮及后续各轮复习任务会按顺序显示在这里。"
            />
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}

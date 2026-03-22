import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { RichContentRenderer } from "@/ui/components/RichContentRenderer"
import { ContentEmptyState, ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import {
  formatInstanceReference,
  formatRangeReference,
  formatRecallPointReference,
  formatReviewTaskReference,
} from "@/ui/displayIdentifiers"
import { useProject } from "@/ui/queries/projects"
import { useReviewTaskDetails } from "@/ui/queries/reviewTasks"

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

function describeReviewTaskState(state: string) {
  if (state === "PENDING") return "待执行"
  if (state === "DONE") return "已完成"
  return state
}

function describeReviewOutcome(state: "PENDING" | "CAN_RECALL" | "CANNOT_RECALL") {
  if (state === "CAN_RECALL") return "会"
  if (state === "CANNOT_RECALL") return "不会"
  return "待复习"
}

function reviewOutcomeClasses(state: "PENDING" | "CAN_RECALL" | "CANNOT_RECALL") {
  if (state === "CAN_RECALL") return "border-emerald-200 bg-emerald-50 text-emerald-700"
  if (state === "CANNOT_RECALL") return "border-amber-200 bg-amber-50 text-amber-700"
  return "border-slate-200 bg-slate-50 text-slate-600"
}

function firstError(items: unknown[]) {
  for (const item of items) {
    if (item) return item
  }
  return null
}

export function ReviewTaskPage() {
  const { projectId, reviewTaskId } = useParams()
  const navigate = useNavigate()
  const pid = projectId ?? ""
  const rtid = reviewTaskId ?? ""
  const { projectTitle } = useProject(pid)
  const { reviewTaskQ, inputRangeQ, resultRangeQ, recallPointQs } = useReviewTaskDetails(pid, rtid)

  if (!pid || !rtid) {
    return (
      <div className="space-y-4">
        <ContentNotice
          title="当前页面缺少复习任务上下文"
          message="当前链接缺少复习任务信息。请返回上一页，或从任务节点详情页重新进入。"
          action={<Button onClick={() => navigate(-1)}>返回</Button>}
        />
      </div>
    )
  }

  const detailLoading =
    !!reviewTaskQ.data &&
    (inputRangeQ.isLoading ||
      (!!reviewTaskQ.data.resultRangeId && resultRangeQ.isLoading) ||
      recallPointQs.some((query) => query.isLoading))
  const detailError = firstError([inputRangeQ.error, resultRangeQ.error, ...recallPointQs.map((query) => query.error)])
  const failedRecallPointIds = new Set(resultRangeQ.data?.recallPointIds ?? [])
  const inputRecallPointIds = inputRangeQ.data?.recallPointIds ?? []
  const cannotRecallCount = reviewTaskQ.data?.state === "DONE" ? failedRecallPointIds.size : null
  const canRecallCount =
    reviewTaskQ.data?.state === "DONE" && inputRangeQ.data ? inputRangeQ.data.recallPointIds.length - failedRecallPointIds.size : null

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">复习任务</h1>
          <p className="text-sm text-muted-foreground">
            项目：<span className="font-medium text-foreground">{projectTitle}</span>
          </p>
          <p className="text-sm text-muted-foreground">
            当前引用：<span className="font-medium text-foreground">{formatReviewTaskReference(rtid)}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => navigate(-1)}>
            返回
          </Button>
          <Button variant="outline" onClick={() => void reviewTaskQ.refetch()} disabled={reviewTaskQ.isFetching}>
            {reviewTaskQ.isFetching ? "刷新中..." : "刷新"}
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>任务概览</CardTitle>
          <CardDescription>查看这次复习的状态、输入范围和结果范围。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {reviewTaskQ.isLoading ? <LoadingNotice title="正在加载复习任务" message="正在读取复习任务元数据和对应范围。" /> : null}
          {reviewTaskQ.error ? <ErrorNotice title="复习任务加载失败" message={formatApiError(reviewTaskQ.error)} /> : null}
          {!reviewTaskQ.isLoading && !reviewTaskQ.error && !reviewTaskQ.data ? (
            <ContentNotice
              title="未找到这个复习任务"
              message="这条复习任务可能已经被清理，或当前链接中的 ID 已经过期。"
              action={<Button variant="outline" onClick={() => navigate(-1)}>返回上一页</Button>}
            />
          ) : null}

          {reviewTaskQ.data ? (
            <>
              <div className="grid gap-3 md:grid-cols-3">
                <div className="rounded-md border bg-muted/30 p-3">
                  <div className="text-xs text-muted-foreground">状态</div>
                  <div className="mt-1 font-medium text-foreground">{describeReviewTaskState(reviewTaskQ.data.state)}</div>
                </div>
                <div className="rounded-md border bg-muted/30 p-3">
                  <div className="text-xs text-muted-foreground">创建时间</div>
                  <div className="mt-1 font-medium text-foreground">{formatTs(reviewTaskQ.data.createdAt)}</div>
                </div>
                <div className="rounded-md border bg-muted/30 p-3">
                  <div className="text-xs text-muted-foreground">执行时间</div>
                  <div className="mt-1 font-medium text-foreground">{formatTs(reviewTaskQ.data.executedAt)}</div>
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-4">
                <div className="rounded-md border p-3">
                  <div className="text-xs text-muted-foreground">输入范围</div>
                  <div className="mt-1 text-sm font-medium text-foreground">{formatRangeReference(reviewTaskQ.data.inputRangeId)}</div>
                </div>
                <div className="rounded-md border p-3">
                  <div className="text-xs text-muted-foreground">结果范围</div>
                  <div className="mt-1 text-sm font-medium text-foreground">{formatRangeReference(reviewTaskQ.data.resultRangeId)}</div>
                </div>
                <div className="rounded-md border p-3">
                  <div className="text-xs text-muted-foreground">复述点总数</div>
                  <div className="mt-1 text-sm font-medium text-foreground">{inputRecallPointIds.length || "-"}</div>
                </div>
                <div className="rounded-md border p-3">
                  <div className="text-xs text-muted-foreground">结果摘要</div>
                  <div className="mt-1 text-sm font-medium text-foreground">
                    {reviewTaskQ.data.state === "DONE"
                      ? `会 ${canRecallCount ?? 0} / 不会 ${cannotRecallCount ?? 0}`
                      : "尚未提交结果"}
                  </div>
                </div>
              </div>

              {reviewTaskQ.data.state === "DONE" && !reviewTaskQ.data.resultRangeId ? (
                <ContentEmptyState
                  title="这次复习全部判定为会"
                  message="结果范围为空，说明这次输入范围里的复述点都被判定为“会”。"
                />
              ) : null}
            </>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>复习结果详情</CardTitle>
          <CardDescription>按这次复习的输入顺序展开每个复述点，以及对应的会/不会判定。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {reviewTaskQ.data && detailLoading ? <LoadingNotice title="正在加载复习详情" message="正在读取输入范围和每个复述点内容。" /> : null}
          {detailError ? <ErrorNotice title="复习详情加载失败" message={formatApiError(detailError)} /> : null}

          {!detailLoading && !detailError && reviewTaskQ.data && inputRecallPointIds.length === 0 ? (
            <ContentEmptyState
              title="这次复习没有可展示的复述点"
              message="当前任务没有解析出输入范围，暂时无法展示逐题映射。"
            />
          ) : null}

          {!detailLoading && !detailError
            ? inputRecallPointIds.map((recallPointId, index) => {
                const recallPointQ = recallPointQs[index]
                const recallPoint = recallPointQ?.data

                if (recallPointQ?.isLoading) {
                  return (
                    <div key={recallPointId} className="rounded-md border p-3 text-sm text-muted-foreground">
                      正在加载 {formatRecallPointReference(recallPointId)} ...
                    </div>
                  )
                }

                if (recallPointQ?.error) {
                  return (
                    <div key={recallPointId} className="rounded-md border border-destructive/20 p-3 text-sm text-destructive">
                      {formatRecallPointReference(recallPointId)} 加载失败：{formatApiError(recallPointQ.error)}
                    </div>
                  )
                }

                if (!recallPoint) return null

                const outcome =
                  reviewTaskQ.data?.state !== "DONE"
                    ? "PENDING"
                    : failedRecallPointIds.has(recallPointId)
                      ? "CANNOT_RECALL"
                      : "CAN_RECALL"

                return (
                  <div key={recallPointId} className="rounded-xl border p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="text-xs text-muted-foreground">序号 #{index + 1}</div>
                        <div className="font-medium text-foreground">{formatRecallPointReference(recallPointId)}</div>
                        <div className="text-xs text-muted-foreground">
                          锚点：<span className="text-foreground">{formatInstanceReference(recallPoint.anchor.instanceId)}</span>
                          <span className="mx-1">·</span>
                          <span className="text-foreground">{recallPoint.anchor.position}</span>
                        </div>
                      </div>
                      <div className={`rounded-full border px-3 py-1 text-xs font-medium ${reviewOutcomeClasses(outcome)}`}>
                        {describeReviewOutcome(outcome)}
                      </div>
                    </div>

                    <div className="mt-4 grid gap-4 lg:grid-cols-2">
                      <div className="space-y-2 rounded-md border bg-muted/20 p-3">
                        <div className="text-xs font-medium text-muted-foreground">问题</div>
                        <RichContentRenderer projectId={pid} value={recallPoint.question} />
                      </div>
                      <div className="space-y-2 rounded-md border bg-muted/20 p-3">
                        <div className="text-xs font-medium text-muted-foreground">答案</div>
                        <RichContentRenderer projectId={pid} value={recallPoint.answer} />
                      </div>
                    </div>

                    <div className="mt-3">
                      <Button size="sm" variant="outline" asChild>
                        <Link to={`/p/${pid}/recall-points/${recallPointId}`}>查看复述点详情</Link>
                      </Button>
                    </div>
                  </div>
                )
              })
            : null}
        </CardContent>
      </Card>
    </div>
  )
}

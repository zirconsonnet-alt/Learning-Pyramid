import { type ReactNode } from "react"
import { ClipboardCheck, RefreshCw } from "lucide-react"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import type { ScopedProjectRef } from "@/ui/api/projectScope"
import { RichContentRenderer } from "@/ui/components/RichContentRenderer"
import { ContentEmptyState, ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { buildScopedProjectPath } from "@/ui/projectPaths"
import { useReviewTaskDetails } from "@/ui/queries/reviewTasks"
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
  const { subjectId = "", scopedProjectId, reviewTaskId } = useParams()
  const navigate = useNavigate()
  const pid = scopedProjectId ?? ""
  const rtid = reviewTaskId ?? ""
  const projectScope: ScopedProjectRef | null = subjectId && pid ? { subjectId, scopedProjectId: pid } : null
  const { reviewTaskQ, reviewTaskBindingQ, inputRangeQ, resultRangeQ, recallPointQs } = useReviewTaskDetails(projectScope, rtid)

  if (!subjectId || !pid || !rtid) {
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
  const resultSummary =
    reviewTaskQ.data?.state === "DONE" ? `会 ${canRecallCount ?? 0} / 不会 ${cannotRecallCount ?? 0}` : "尚未提交结果"
  const entryValue = reviewTaskBindingQ.data ? (
    reviewTaskBindingQ.data.kind === "CONVERGENCE" && reviewTaskBindingQ.data.convergenceId ? (
      <Link
        className="text-primary underline-offset-4 hover:underline"
        to={buildScopedProjectPath(subjectId, pid, `/convergences/${reviewTaskBindingQ.data.convergenceId}`)}
      >
        查看收敛
      </Link>
    ) : (
      <Link
        className="text-primary underline-offset-4 hover:underline"
        to={buildScopedProjectPath(subjectId, pid, `/review-chains/${reviewTaskBindingQ.data.reviewChainId}`)}
      >
        查看复习链
      </Link>
    )
  ) : reviewTaskBindingQ.isLoading ? (
    "读取中..."
  ) : (
    "暂未关联"
  )
  const summaryPanel = reviewTaskQ.data ? (
    <div className="space-y-3">
      <DetailSummaryCard
        icon={ClipboardCheck}
        title="复习任务"
        items={[
          { label: "状态", value: describeReviewTaskState(reviewTaskQ.data.state) },
          { label: "复述点", value: inputRecallPointIds.length || "-" },
          { label: "结果摘要", value: resultSummary },
          { label: "关联入口", value: entryValue },
          { label: "创建时间", value: formatTs(reviewTaskQ.data.createdAt) },
          { label: "执行时间", value: formatTs(reviewTaskQ.data.executedAt) },
        ]}
      />
      {reviewTaskBindingQ.error ? <ErrorNotice title="关联入口加载失败" message={formatApiError(reviewTaskBindingQ.error)} /> : null}
      <Button variant="outline" className="w-full rounded-full" onClick={() => void reviewTaskQ.refetch()} disabled={reviewTaskQ.isFetching}>
        <RefreshCw className="h-4 w-4" />
        {reviewTaskQ.isFetching ? "刷新中..." : "刷新"}
      </Button>
    </div>
  ) : null

  return (
    <div className="space-y-4">
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
        <div className="grid gap-4 xl:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)] xl:items-start">
          {summaryPanel ? <aside className="xl:sticky xl:top-28 xl:self-start">{summaryPanel}</aside> : <div />}
          <div className="min-w-0">
            <ReviewTaskResultListCard
              title="复习结果详情"
              isLoading={detailLoading}
              error={detailError}
              emptyState={
                inputRecallPointIds.length === 0 ? (
                  <ContentEmptyState
                    title="这次复习没有可展示的复述点"
                    message="当前任务没有解析出输入范围，暂时无法展示逐题映射。"
                  />
                ) : reviewTaskQ.data.state === "DONE" && !reviewTaskQ.data.resultRangeId ? (
                  <ContentEmptyState
                    title="这次复习全部判定为会"
                    message="结果范围为空，说明这次输入范围里的复述点都被判定为“会”。"
                  />
                ) : null
              }
            >
              {!detailLoading && !detailError
                ? inputRecallPointIds.map((recallPointId, index) => {
                    const recallPointQ = recallPointQs[index]
                    const recallPoint = recallPointQ?.data

                    if (recallPointQ?.isLoading) {
                      return (
                        <div key={recallPointId} className="rounded-[1rem] border border-[#dbe4ee] bg-[#fbfdff] p-4 text-sm text-muted-foreground">
                          正在加载复述点...
                        </div>
                      )
                    }

                    if (recallPointQ?.error) {
                      return (
                        <div key={recallPointId} className="rounded-[1rem] border border-destructive/20 bg-destructive/5 p-4 text-sm text-destructive">
                          复述点加载失败：{formatApiError(recallPointQ.error)}
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
                      <div key={recallPointId} className="rounded-[1rem] border border-[#dbe4ee] bg-[#fbfdff] p-4 shadow-[0_12px_28px_-28px_rgba(15,23,42,0.6)]">
                        <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                          <div className="min-w-0 flex-1 space-y-3">
                            <div className="flex flex-wrap items-center gap-2 text-xs">
                              <span className="rounded-full bg-[#eef5ff] px-2.5 py-1 font-medium text-primary">第 {index + 1} 条</span>
                              <span className={`rounded-full border px-2.5 py-1 font-medium ${reviewOutcomeClasses(outcome)}`}>
                                {describeReviewOutcome(outcome)}
                              </span>
                            </div>

                            <div className="text-xs text-muted-foreground">
                              {recallPoint.anchor ? (
                                <>
                                  锚点：<span className="text-foreground">{recallPoint.anchor.position}</span>
                                </>
                              ) : (
                                <>锚点：<span className="text-foreground">未绑定锚点</span></>
                              )}
                            </div>

                            <div className="grid gap-4 lg:grid-cols-2">
                              <div className="space-y-2 rounded-xl border border-[#dbe4ee] bg-[#f8fafc] p-3">
                                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#64748b]">问题</div>
                                <RichContentRenderer subjectId={subjectId} projectId={pid} value={recallPoint.question} />
                              </div>
                              <div className="space-y-2 rounded-xl border border-[#dbe4ee] bg-[#f8fafc] p-3">
                                <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#64748b]">答案</div>
                                <RichContentRenderer subjectId={subjectId} projectId={pid} value={recallPoint.answer} />
                              </div>
                            </div>
                          </div>

                          <div className="flex shrink-0 flex-wrap gap-2 md:w-[11rem] md:flex-col md:items-stretch">
                            <Button size="sm" className="rounded-full md:w-full" asChild>
                              <Link to={buildScopedProjectPath(subjectId, pid, `/recall-points/${recallPointId}`)}>查看详情</Link>
                            </Button>
                          </div>
                        </div>
                      </div>
                    )
                  })
                : null}
            </ReviewTaskResultListCard>
          </div>
        </div>
      ) : null}
    </div>
  )
}

function ReviewTaskResultListCard({
  children,
  emptyState,
  error,
  isLoading,
  title,
}: {
  children: ReactNode
  emptyState?: ReactNode
  error?: unknown
  isLoading?: boolean
  title: string
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? <LoadingNotice title="正在加载复习详情" message="正在读取输入范围和每个复述点内容。" /> : null}
        {error ? <ErrorNotice title="复习详情加载失败" message={formatApiError(error)} /> : null}
        {!isLoading && !error && emptyState ? emptyState : null}
        <div className="space-y-3">{children}</div>
      </CardContent>
    </Card>
  )
}

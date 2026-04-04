import { useMemo } from "react"

import { ApiError } from "@/ui/api/http"
import { ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { useRecallPointReviewProjection } from "@/ui/queries/reviewRecommendations"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function formatDateTime(value: string | null) {
  if (!value) return "未复习"
  const dt = new Date(value)
  return Number.isNaN(dt.getTime()) ? value : dt.toLocaleString()
}

function formatReviewResult(value: "CAN_RECALL" | "CANNOT_RECALL" | null) {
  if (value === "CAN_RECALL") return "会"
  if (value === "CANNOT_RECALL") return "不会"
  return "未复习"
}

function ReviewCurveChart(props: {
  weightedSuccessRatio: number
  forgettingCurveDecayPerDay: number
  calculatedAt: string
  lastReviewedAt: string | null
  history: Array<{ occurredAt: string; result: "CAN_RECALL" | "CANNOT_RECALL" }>
}) {
  const { weightedSuccessRatio, forgettingCurveDecayPerDay, calculatedAt, lastReviewedAt, history } = props

  const chart = useMemo(() => {
    const width = 720
    const height = 260
    const padding = { top: 18, right: 18, bottom: 28, left: 34 }
    const calculatedAtMs = new Date(calculatedAt).getTime()
    const historyPoints = history
      .map((item) => ({
        at: new Date(item.occurredAt).getTime(),
        value: item.result === "CAN_RECALL" ? 1 : 0,
        result: item.result,
      }))
      .filter((item) => Number.isFinite(item.at))
    const curveStartMs = lastReviewedAt ? new Date(lastReviewedAt).getTime() : Number.NaN

    const validTimes = [
      ...historyPoints.map((item) => item.at),
      Number.isFinite(curveStartMs) ? curveStartMs : null,
      Number.isFinite(calculatedAtMs) ? calculatedAtMs : null,
    ].filter((value): value is number => value !== null)

    if (validTimes.length === 0) return null

    const xMin = Math.min(...validTimes)
    let xMax = Math.max(...validTimes)
    if (xMax <= xMin) xMax = xMin + 1

    const plotWidth = width - padding.left - padding.right
    const plotHeight = height - padding.top - padding.bottom
    const x = (value: number) => padding.left + ((value - xMin) / (xMax - xMin)) * plotWidth
    const y = (value: number) => padding.top + (1 - value) * plotHeight

    const curvePoints =
      Number.isFinite(curveStartMs) && curveStartMs <= calculatedAtMs
        ? Array.from({ length: 24 }, (_, index) => {
            const ratio = index / 23
            const at = curveStartMs + (calculatedAtMs - curveStartMs) * ratio
            const ageDays = (at - curveStartMs) / 86400000
            const value = Math.max(0, Math.min(1, weightedSuccessRatio * Math.exp(-forgettingCurveDecayPerDay * ageDays)))
            return { at, value }
          })
        : []

    const path =
      curvePoints.length > 1
        ? curvePoints.map((point, index) => `${index === 0 ? "M" : "L"} ${x(point.at).toFixed(2)} ${y(point.value).toFixed(2)}`).join(" ")
        : ""

    return { width, height, padding, x, y, historyPoints, curvePoints, path, xMin, xMax }
  }, [calculatedAt, forgettingCurveDecayPerDay, history, lastReviewedAt, weightedSuccessRatio])

  if (!chart) return null

  return (
    <div className="space-y-3">
      <div className="theme-canvas rounded-[1.2rem] border border-[color:var(--theme-soft-border)] p-3">
        <svg viewBox={`0 0 ${chart.width} ${chart.height}`} className="h-64 w-full rounded-[1rem] bg-[color:var(--theme-card-main-bg)]">
          {[0, 0.5, 1].map((tick) => (
            <g key={tick}>
              <line x1={chart.padding.left} x2={chart.width - chart.padding.right} y1={chart.y(tick)} y2={chart.y(tick)} stroke="#d7e1ec" strokeDasharray="4 4" />
              <text x={8} y={chart.y(tick) + 4} fontSize="11" fill="#64748b">
                {tick === 1 ? "1.0" : tick === 0.5 ? "0.5" : "0.0"}
              </text>
            </g>
          ))}
          {chart.path ? <path d={chart.path} fill="none" stroke="#0284c7" strokeWidth="3" strokeLinecap="round" /> : null}
          {chart.historyPoints.map((point, index) => (
            <circle
              key={`${point.at}-${index}`}
              cx={chart.x(point.at)}
              cy={chart.y(point.value)}
              r="5"
              fill={point.result === "CAN_RECALL" ? "#10b981" : "#f59e0b"}
              stroke="white"
              strokeWidth="2"
            />
          ))}
        </svg>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
        <span>绿色点表示“会”，橙色点表示“不会”，蓝线表示按最近一次正式复习往当前时刻衰减的记忆曲线。</span>
        <span>基于最近 {history.length} 条参与计算的记录。</span>
      </div>
    </div>
  )
}

export function ReviewProjectionCard(props: { projectId: string; recallPointId: string }) {
  const { projectId, recallPointId } = props
  const projectionQ = useRecallPointReviewProjection(projectId, recallPointId)
  const projection = projectionQ.data

  return (
    <Card className="theme-card-main overflow-hidden">
      <CardHeader className="theme-card-header">
        <CardTitle>复习曲线与推荐指数</CardTitle>
        <CardDescription>基于遗忘曲线加权法，按最近正式复习记录估算当前记忆强度与复习紧迫度。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4 pt-5">
        {projectionQ.isLoading ? <LoadingNotice title="正在计算复习曲线" message="正在读取历史会/不会记录并生成当前推荐指数。" /> : null}
        {projectionQ.error ? <ErrorNotice title="复习曲线加载失败" message={formatApiError(projectionQ.error)} /> : null}

        {projection ? (
          <>
            <div className="grid gap-3 md:grid-cols-4">
              <div className="theme-status-surface rounded-[1.15rem] border border-[color:var(--theme-status-border)] p-4">
                <div className="text-xs text-muted-foreground">推荐指数</div>
                <div className="mt-1 text-lg font-semibold text-foreground">{projection.reviewRecommendationIndex.toFixed(1)}</div>
              </div>
              <div className="theme-soft-surface rounded-[1.15rem] p-4">
                <div className="text-xs text-muted-foreground">记忆强度</div>
                <div className="mt-1 text-lg font-semibold text-foreground">{(projection.estimatedMemoryStrength * 100).toFixed(1)}%</div>
              </div>
              <div className="theme-soft-surface rounded-[1.15rem] p-4">
                <div className="text-xs text-muted-foreground">最近结果</div>
                <div className="mt-1 text-lg font-semibold text-foreground">{formatReviewResult(projection.lastReviewResult)}</div>
              </div>
              <div className="theme-soft-surface rounded-[1.15rem] p-4">
                <div className="text-xs text-muted-foreground">最近时间</div>
                <div className="mt-1 text-sm font-semibold text-foreground">{formatDateTime(projection.lastReviewedAt)}</div>
              </div>
            </div>

            <div className="grid gap-3 md:grid-cols-3">
              <div className="theme-soft-surface rounded-[1.1rem] p-4 text-sm">
                <div className="text-xs text-muted-foreground">历史记录总数</div>
                <div className="mt-1 font-medium text-foreground">{projection.reviewCount}</div>
              </div>
              <div className="theme-soft-surface rounded-[1.1rem] p-4 text-sm">
                <div className="text-xs text-muted-foreground">参与计算窗口</div>
                <div className="mt-1 font-medium text-foreground">
                  最近 {projection.historyWindowSize === 0 ? 0 : projection.history.length} 条
                </div>
              </div>
              <div className="theme-soft-surface rounded-[1.1rem] p-4 text-sm">
                <div className="text-xs text-muted-foreground">衰减率 λ / 天</div>
                <div className="mt-1 font-medium text-foreground">{projection.forgettingCurveDecayPerDay.toFixed(2)}</div>
              </div>
            </div>

            {projection.history.length === 0 ? (
              <div className="theme-soft-surface rounded-[1.2rem] p-4">
                <div className="text-sm font-medium text-foreground">这条复述点还没有正式复习记录</div>
                <div className="mt-1 text-sm leading-6 text-muted-foreground">
                  当前推荐指数会按未复习状态显示为高优先级；当正式复习任务提交后，这里会开始出现曲线和历史点。
                </div>
              </div>
            ) : (
              <ReviewCurveChart
                calculatedAt={projection.calculatedAt}
                lastReviewedAt={projection.lastReviewedAt}
                weightedSuccessRatio={projection.weightedSuccessRatio}
                forgettingCurveDecayPerDay={projection.forgettingCurveDecayPerDay}
                history={projection.history}
              />
            )}

            <div className="space-y-2">
              <div className="text-sm font-medium text-foreground">参与计算的历史记录</div>
              <div className="space-y-2">
                {projection.history.length === 0 ? (
                  <div className="text-sm text-muted-foreground">暂无正式复习历史。</div>
                ) : (
                  projection.history.map((item, index) => (
                    <div
                      key={`${item.reviewTaskId}-${item.occurredAt}-${index}`}
                      className="theme-soft-surface flex flex-wrap items-center justify-between gap-2 rounded-[1rem] px-3 py-3 text-sm"
                    >
                      <div className="text-muted-foreground">
                        #{index + 1} · {formatDateTime(item.occurredAt)}
                      </div>
                      <div className="font-medium text-foreground">{formatReviewResult(item.result)}</div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </>
        ) : null}
      </CardContent>
    </Card>
  )
}

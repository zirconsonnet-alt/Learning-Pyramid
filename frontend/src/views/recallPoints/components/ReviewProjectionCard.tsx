import { useMemo } from "react"

import { ApiError } from "@/ui/api/http"
import { ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
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

function formatXAxisDate(value: number) {
  return new Date(value).toLocaleDateString(undefined, { month: "numeric", day: "numeric" })
}

function buildXAxisTicks(xMin: number, xMax: number) {
  if (!Number.isFinite(xMin) || !Number.isFinite(xMax)) return []
  if (xMax <= xMin) return [{ at: xMin, label: formatXAxisDate(xMin) }]
  return Array.from({ length: 4 }, (_, index) => {
    const ratio = index / 3
    const at = xMin + (xMax - xMin) * ratio
    return { at, label: formatXAxisDate(at) }
  })
}

function buildConvolvedReviewCurve(props: {
  calculatedAtMs: number
  estimatedMemoryStrength: number
  forgettingCurveDecayPerDay: number
  historyPoints: Array<{ at: number; value: number; result: "CAN_RECALL" | "CANNOT_RECALL" }>
}) {
  const { calculatedAtMs, estimatedMemoryStrength, forgettingCurveDecayPerDay, historyPoints } = props
  if (!Number.isFinite(calculatedAtMs) || historyPoints.length === 0) return []

  const firstHistoryAtMs = historyPoints[0]?.at
  if (!Number.isFinite(firstHistoryAtMs)) return []

  const endMs = Math.max(firstHistoryAtMs, calculatedAtMs)
  const sampleCount = Math.max(96, historyPoints.length * 24)
  const curvePoints = Array.from({ length: sampleCount }, (_, index) => {
    const ratio = sampleCount <= 1 ? 0 : index / (sampleCount - 1)
    const at = firstHistoryAtMs + (endMs - firstHistoryAtMs) * ratio
    const recordsAtPoint = historyPoints.filter((item) => item.at <= at)
    if (recordsAtPoint.length === 0) return { at, value: 0 }

    let successWeight = 0
    let totalWeight = 0
    for (const record of recordsAtPoint) {
      const ageDays = Math.max(0, (at - record.at) / 86400000)
      const weight = Math.exp(-forgettingCurveDecayPerDay * ageDays)
      totalWeight += weight
      if (record.result === "CAN_RECALL") successWeight += weight
    }

    const weightedSuccessRatio = totalWeight <= 0 ? 0 : successWeight / totalWeight
    const lastRecordAt = recordsAtPoint[recordsAtPoint.length - 1]?.at ?? at
    const freshnessAgeDays = Math.max(0, (at - lastRecordAt) / 86400000)
    const freshness = Math.exp(-forgettingCurveDecayPerDay * freshnessAgeDays)
    const value = Math.max(0, Math.min(1, weightedSuccessRatio * freshness))
    return { at, value }
  })

  const lastPoint = curvePoints[curvePoints.length - 1]
  if (lastPoint && Number.isFinite(estimatedMemoryStrength)) {
    lastPoint.value = Math.max(0, Math.min(1, estimatedMemoryStrength))
  }
  return curvePoints
}

function ReviewCurveChart(props: {
  weightedSuccessRatio: number
  estimatedMemoryStrength: number
  forgettingCurveDecayPerDay: number
  calculatedAt: string
  lastReviewedAt: string | null
  history: Array<{ occurredAt: string; result: "CAN_RECALL" | "CANNOT_RECALL" }>
}) {
  const { estimatedMemoryStrength, forgettingCurveDecayPerDay, calculatedAt, history } = props

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
      .sort((a, b) => a.at - b.at)

    const curvePoints = buildConvolvedReviewCurve({
      calculatedAtMs,
      estimatedMemoryStrength,
      forgettingCurveDecayPerDay,
      historyPoints,
    })

    const validTimes = [
      ...historyPoints.map((item) => item.at),
      ...curvePoints.map((item) => item.at),
      Number.isFinite(calculatedAtMs) ? calculatedAtMs : null,
    ].filter((value): value is number => value !== null)

    if (validTimes.length === 0) return null

    const xMin = Math.min(...validTimes)
    let xMax = Math.max(...validTimes)
    if (xMax <= xMin) xMax = xMin + 1
    const xAxisTicks = buildXAxisTicks(xMin, xMax)

    const plotWidth = width - padding.left - padding.right
    const plotHeight = height - padding.top - padding.bottom
    const x = (value: number) => padding.left + ((value - xMin) / (xMax - xMin)) * plotWidth
    const y = (value: number) => padding.top + (1 - value) * plotHeight

    const path =
      curvePoints.length > 1
        ? curvePoints.map((point, index) => `${index === 0 ? "M" : "L"} ${x(point.at).toFixed(2)} ${y(point.value).toFixed(2)}`).join(" ")
        : ""

    return { width, height, padding, x, y, historyPoints, curvePoints, path, xMin, xMax, xAxisTicks }
  }, [calculatedAt, estimatedMemoryStrength, forgettingCurveDecayPerDay, history])

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
          {chart.xAxisTicks.map((tick, index) => (
            <g key={`${tick.at}-${index}`}>
              <line x1={chart.x(tick.at)} x2={chart.x(tick.at)} y1={chart.height - chart.padding.bottom} y2={chart.height - chart.padding.bottom + 5} stroke="#d7e1ec" />
              <text
                x={chart.x(tick.at)}
                y={chart.height - 8}
                textAnchor={index === 0 ? "start" : index === chart.xAxisTicks.length - 1 ? "end" : "middle"}
                fontSize="11"
                fill="#64748b"
              >
                {tick.label}
              </text>
            </g>
          ))}
        </svg>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-muted-foreground">
        <span>绿色点表示“会”，橙色点表示“不会”，蓝线表示从第一次复习到现在的卷积记忆曲线。</span>
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
                estimatedMemoryStrength={projection.estimatedMemoryStrength}
                weightedSuccessRatio={projection.weightedSuccessRatio}
                forgettingCurveDecayPerDay={projection.forgettingCurveDecayPerDay}
                history={projection.history}
              />
            )}
          </>
        ) : null}
      </CardContent>
    </Card>
  )
}

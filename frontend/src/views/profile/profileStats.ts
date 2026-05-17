import type { AuditLogEvent } from "@/ui/api/auditLog"
import { getLocalDateKey } from "@/ui/store/workbenchDailyStats"

export type DailyStatPoint = {
  dateKey: string
  shortLabel: string
  weekdayLabel: string
  effectiveMs: number
  watchMs: number
  composeMs: number
  reviewMs: number
  qaMs: number
  learningCount: number
  reviewCount: number
  totalActions: number
}

export type ProjectActivitySnapshot = {
  projectId: string
  title: string
  state: string
  learningCount: number
  reviewCount: number
  totalActions: number
  lastStudyAt: string | null
}

export function formatDurationCompact(ms: number) {
  if (!Number.isFinite(ms) || ms <= 0) return "0m"
  const totalMinutes = Math.floor(ms / 60_000)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours <= 0) return `${Math.max(1, minutes)}m`
  if (minutes === 0) return `${hours}h`
  return `${hours}h ${minutes}m`
}

export function formatDateTimeLabel(iso: string) {
  const value = new Date(iso)
  if (Number.isNaN(value.getTime())) return iso
  return value.toLocaleString()
}

export function formatDateKeyShortLabel(dateKey: string) {
  const value = new Date(`${dateKey}T00:00:00`)
  if (Number.isNaN(value.getTime())) return dateKey
  return `${value.getMonth() + 1}.${value.getDate()}`
}

export function formatDateKeyWeekdayLabel(dateKey: string) {
  const value = new Date(`${dateKey}T00:00:00`)
  if (Number.isNaN(value.getTime())) return ""
  return value.toLocaleDateString("zh-CN", { weekday: "short" })
}

export function buildRecentDateKeys(days: number) {
  const keys: string[] = []
  const cursor = new Date()
  cursor.setHours(0, 0, 0, 0)

  for (let offset = days - 1; offset >= 0; offset -= 1) {
    const next = new Date(cursor)
    next.setDate(cursor.getDate() - offset)
    keys.push(getLocalDateKey(next))
  }

  return keys
}

export function buildDateKeySpan(startDateKey: string, endDateKey = getLocalDateKey()) {
  const start = new Date(`${startDateKey}T00:00:00`)
  const end = new Date(`${endDateKey}T00:00:00`)

  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start > end) {
    return [endDateKey]
  }

  const keys: string[] = []
  const cursor = new Date(start)

  while (cursor <= end) {
    keys.push(getLocalDateKey(cursor))
    cursor.setDate(cursor.getDate() + 1)
  }

  return keys
}

export function isSuccessfulStudyEvent(event: AuditLogEvent) {
  if (event.result !== "OK" && event.result !== "SUCCESS") return false
  return event.kind === "SUBMIT_LEARNING_TASK" || event.kind === "EXECUTOR_COMMIT_REVIEW_TASK"
}

export function isLearningSubmitEvent(event: AuditLogEvent) {
  return event.kind === "SUBMIT_LEARNING_TASK"
}

export function isReviewCommitEvent(event: AuditLogEvent) {
  return event.kind === "EXECUTOR_COMMIT_REVIEW_TASK"
}

export function getLastStudyAt(events: AuditLogEvent[]) {
  let latest: string | null = null
  for (const event of events) {
    if (!isSuccessfulStudyEvent(event)) continue
    if (!latest || Date.parse(event.occurredAt) > Date.parse(latest)) {
      latest = event.occurredAt
    }
  }
  return latest
}

export function formatLastStudyText(occurredAt: string | null) {
  if (!occurredAt) {
    return {
      text: "还没有学习记录",
      className: "text-muted-foreground",
    }
  }

  const dt = new Date(occurredAt)
  if (Number.isNaN(dt.getTime())) {
    return {
      text: "学习时间未知",
      className: "text-muted-foreground",
    }
  }

  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const targetStart = new Date(dt.getFullYear(), dt.getMonth(), dt.getDate())
  const dayDiff = Math.max(0, Math.floor((todayStart.getTime() - targetStart.getTime()) / 86_400_000))

  if (dayDiff === 0) {
    return {
      text: "今天学习过",
      className: "text-primary",
    }
  }

  if (dayDiff === 1) {
    return {
      text: "昨天学习过",
      className: "text-[color:var(--theme-subtle-text)]",
    }
  }

  if (dayDiff <= 7) {
    return {
      text: `上次学习 ${dayDiff} 天前`,
      className: "text-[color:var(--theme-subtle-text)]",
    }
  }

  return {
    text: `已 ${dayDiff} 天未推进`,
    className: "text-[color:var(--theme-warm-text)]",
  }
}

export function buildCurveGeometry<T extends { dateKey: string }>(
  points: T[],
  width: number,
  height: number,
  getValue: (point: T) => number,
  options: { paddingX?: number; paddingTop?: number; paddingBottom?: number } = {},
) {
  const paddingX = options.paddingX ?? 44
  const paddingTop = options.paddingTop ?? 16
  const paddingBottom = options.paddingBottom ?? 34
  const innerWidth = width - paddingX * 2
  const innerHeight = height - paddingTop - paddingBottom
  const maxValue = Math.max(...points.map((point) => Math.max(0, getValue(point))), 1)

  const nodes = points.map((point, index) => {
    const metricValue = Math.max(0, getValue(point))
    const x = points.length === 1 ? width / 2 : paddingX + (innerWidth * index) / (points.length - 1)
    const ratio = maxValue <= 0 ? 0 : metricValue / maxValue
    const y = paddingTop + innerHeight - ratio * innerHeight
    return {
      ...point,
      metricValue,
      x,
      y,
      columnHeight: Math.max(10, ratio * innerHeight),
    }
  })

  const linePath = nodes.map((node, index) => `${index === 0 ? "M" : "L"} ${node.x.toFixed(2)} ${node.y.toFixed(2)}`).join(" ")
  const firstNode = nodes[0]
  const lastNode = nodes.at(-1)
  const areaPath =
    firstNode && lastNode
      ? `${linePath} L ${lastNode.x.toFixed(2)} ${(height - paddingBottom).toFixed(2)} L ${firstNode.x.toFixed(2)} ${(height - paddingBottom).toFixed(2)} Z`
      : ""

  return {
    nodes,
    linePath,
    areaPath,
    baselineY: height - paddingBottom,
    gridLines: Array.from({ length: 4 }, (_, index) => paddingTop + (innerHeight * index) / 3),
  }
}

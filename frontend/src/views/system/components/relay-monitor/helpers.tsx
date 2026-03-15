import { ApiError } from "@/ui/api/http"
import { TonePill } from "./shared"

export function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) return "未记录"
  const dt = new Date(value)
  return Number.isNaN(dt.getTime()) ? value : dt.toLocaleString()
}

export function formatBytes(value: number | null | undefined) {
  const size = Math.max(0, Number(value ?? 0))
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`
  return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

export function formatPercent(value: number | null | undefined) {
  if (value == null) return "暂无"
  return `${(Number(value) * 100).toFixed(1)}%`
}

export function formatBucketSeconds(value: number | null | undefined) {
  const seconds = Math.max(0, Number(value ?? 0))
  if (!seconds) return "未采样"
  if (seconds % 3600 === 0) return `${seconds / 3600} 小时`
  if (seconds % 60 === 0) return `${seconds / 60} 分钟`
  return `${seconds} 秒`
}

export function formatCountSummary(values: Record<string, number> | null | undefined, empty = "暂无") {
  const entries = Object.entries(values ?? {})
  if (!entries.length) return empty
  return entries.map(([key, count]) => `${key}=${count}`).join(" / ")
}

export function describeSourceKind(value: string | null | undefined) {
  const normalized = value?.trim().toUpperCase()
  if (normalized === "DESKTOP_AGENT_MANIFEST") return "桌面连接器"
  if (normalized === "SERVER_FS") return "服务器文件系统"
  return value?.trim() || "未设置"
}

export function describeProjectReference(projectTitle: string | null | undefined, projectId: string | null | undefined, empty = "未关联项目") {
  if (projectTitle?.trim()) return projectTitle.trim()
  if (projectId?.trim()) return `项目 ${projectId.trim()}`
  return empty
}

export function describeAgentReference(agentId: string | null | undefined, empty = "未关联桌面连接器") {
  return agentId?.trim() ? `连接器 ${agentId.trim()}` : empty
}

export function describeInstanceReference(instanceId: string | null | undefined, empty = "实例未关联") {
  return instanceId?.trim() ? `实例 ${instanceId.trim()}` : empty
}

export function renderStateBadge(value: string) {
  const tone =
    value === "FAILED" || value === "CANCELLED" || value === "ERROR"
      ? "rose"
      : value === "WARNING" || value === "RETRYING" || value === "DEGRADED"
        ? "amber"
        : value === "COMPLETED" || value === "HEALTHY"
          ? "emerald"
          : value === "ONLINE" || value === "RUNNING" || value === "OPENING" || value === "CONNECTED"
            ? "sky"
            : "slate"
  return (
    <TonePill tone={tone} className="text-[11px]">
      {value}
    </TonePill>
  )
}

export function normalizeFilterText(value: string) {
  const normalized = value.trim()
  return normalized ? normalized : undefined
}

export const selectClassName =
  "h-10 w-full rounded-xl border border-input bg-white/90 px-3 text-sm text-foreground shadow-[0_10px_24px_-24px_rgba(15,23,42,0.22)]"

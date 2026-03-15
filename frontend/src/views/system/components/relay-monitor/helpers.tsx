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

function truncateDisplay(value: string, max = 64) {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value
}

function shortenOpaqueId(value: string | null | undefined, digits = 8) {
  const normalized = value?.trim()
  if (!normalized) return ""
  const lastSegment = normalized.includes("_") ? normalized.split("_").at(-1) ?? normalized : normalized
  if (/^\d+$/.test(lastSegment)) return `#${lastSegment}`
  return `#${lastSegment.slice(-digits)}`
}

export function describeStateLabel(value: string | null | undefined) {
  const normalized = value?.trim().toUpperCase()
  if (!normalized) return "未记录"
  if (normalized === "ERROR") return "错误"
  if (normalized === "WARNING") return "告警"
  if (normalized === "INFO") return "信息"
  if (normalized === "FAILED") return "失败"
  if (normalized === "CANCELLED") return "已取消"
  if (normalized === "COMPLETED") return "已完成"
  if (normalized === "HEALTHY") return "正常"
  if (normalized === "DEGRADED") return "降级"
  if (normalized === "ONLINE") return "在线"
  if (normalized === "OFFLINE") return "离线"
  if (normalized === "UNBOUND") return "未绑定"
  if (normalized === "RUNNING") return "运行中"
  if (normalized === "OPENING") return "准备中"
  if (normalized === "CONNECTED") return "已连接"
  if (normalized === "DISCONNECTED") return "未连接"
  if (normalized === "RETRYING") return "重试中"
  if (normalized === "ACTIVE") return "活跃"
  return value?.trim() || "未记录"
}

export function describeDiagnosticCategory(value: string | null | undefined) {
  const normalized = value?.trim().toLowerCase()
  if (!normalized) return "未分类"
  if (normalized === "hls") return "HLS"
  if (normalized === "relay") return "中继"
  if (normalized === "service") return "服务"
  if (normalized === "probe") return "探测"
  if (normalized === "manifest") return "清单同步"
  return value?.trim() || "未分类"
}

export function describeEventType(value: string | null | undefined) {
  const normalized = value?.trim().toLowerCase()
  if (!normalized) return "未分类事件"
  if (normalized === "stream_opened") return "中继流已打开"
  if (normalized === "stream_failed") return "中继流失败"
  if (normalized === "session_failed") return "回放会话失败"
  if (normalized === "hls_failed") return "HLS 转码失败"
  if (normalized === "hls_job_failed") return "HLS 任务失败"
  if (normalized === "hls_job_requested") return "已请求 HLS 转码"
  if (normalized === "hls_job_running") return "HLS 任务进行中"
  if (normalized === "hls_manifest_uploaded") return "已上传 HLS 播放清单"
  return value?.trim().replaceAll("_", " ") || "未分类事件"
}

export function describeStreamMode(value: string | null | undefined) {
  const normalized = value?.trim().toLowerCase()
  if (!normalized) return "未记录"
  if (normalized === "relay_progressive") return "渐进流"
  if (normalized === "relay_hls") return "HLS 中继"
  if (normalized === "local_file") return "本地文件"
  return value?.trim() || "未记录"
}

export function describeOperationalMessage(value: string | null | undefined, empty = "暂无") {
  const normalized = value?.trim()
  if (!normalized) return empty
  if (normalized.startsWith("413 Client Error: Request Entity Too Large")) return "上传的 HLS 分片超过服务器允许的大小"
  if (normalized.startsWith("ffmpeg failed")) return "FFmpeg 转码失败"
  if (normalized === "Desktop agent relay stream opened") return "桌面连接器中继流已打开"
  if (normalized === "Requested desktop agent HLS transcode") return "已请求桌面连接器执行 HLS 转码"
  if (normalized === "HLS job running") return "HLS 转码任务进行中"
  if (normalized.startsWith("Uploaded HLS manifest ")) return `已上传 HLS 播放清单 ${normalized.slice("Uploaded HLS manifest ".length)}`
  if (normalized === "desktop agent disconnected during relay") return "桌面连接器在中继过程中断开连接"
  if (normalized === "desktop agent stream became idle") return "桌面连接器中继流在传输过程中进入空闲状态"
  if (normalized === "desktop agent disconnected during HLS job") return "桌面连接器在 HLS 转码过程中断开连接"
  if (normalized === "desktop agent HLS job cancelled") return "HLS 转码任务已取消"
  if (normalized === "desktop agent HLS job expired") return "HLS 转码任务已过期"
  return normalized
}

export function formatCountSummary(
  values: Record<string, number> | null | undefined,
  empty = "暂无",
  formatKey?: (key: string) => string,
) {
  const entries = Object.entries(values ?? {})
  if (!entries.length) return empty
  return entries.map(([key, count]) => `${formatKey ? formatKey(key) : key}=${count}`).join(" / ")
}

export function describeSourceKind(value: string | null | undefined) {
  const normalized = value?.trim().toUpperCase()
  if (normalized === "DESKTOP_AGENT_MANIFEST") return "桌面连接器"
  if (normalized === "SERVER_FS") return "服务器文件系统"
  return value?.trim() || "未设置"
}

export function describeProjectReference(projectTitle: string | null | undefined, projectId: string | null | undefined, empty = "未关联项目") {
  if (projectTitle?.trim()) return projectTitle.trim()
  if (projectId?.trim()) return `项目 ${shortenOpaqueId(projectId, 6)}`
  return empty
}

export function describeAgentReference(agentId: string | null | undefined, empty = "未关联桌面连接器") {
  return agentId?.trim() ? `连接器 ${shortenOpaqueId(agentId)}` : empty
}

export function describeInstanceReference(instanceId: string | null | undefined, empty = "实例未关联") {
  return instanceId?.trim() ? `实例 ${shortenOpaqueId(instanceId, 6)}` : empty
}

export function describeJobReference(jobId: string | null | undefined, empty = "未关联任务") {
  return jobId?.trim() ? `任务 ${shortenOpaqueId(jobId)}` : empty
}

export function describeStreamReference(streamId: string | null | undefined, empty = "未关联会话") {
  return streamId?.trim() ? `会话 ${shortenOpaqueId(streamId)}` : empty
}

export function describeEventReference(eventId: string | null | undefined, empty = "未关联事件") {
  return eventId?.trim() ? `事件 ${shortenOpaqueId(eventId)}` : empty
}

export function describeCacheReference(cacheKey: string | null | undefined, empty = "未关联缓存") {
  const normalized = cacheKey?.trim()
  if (!normalized) return empty
  return `缓存 ${truncateDisplay(normalized, 12)}`
}

function describeDetailKey(key: string) {
  if (key === "rangeStart") return "起始字节"
  if (key === "rangeEnd") return "结束字节"
  if (key === "streamId") return "会话"
  if (key === "artifactBytes") return "产物体积"
  if (key === "artifactCount") return "产物数"
  if (key === "cacheKey") return "缓存"
  if (key === "jobId") return "任务"
  if (key === "artifactPath") return "文件"
  if (key === "sizeBytes") return "文件大小"
  if (key === "decisionReason") return "切换原因"
  if (key === "profile") return "转码配置"
  return key
}

function describeDetailValue(key: string, value: unknown) {
  if (value == null) return "未提供"
  if (typeof value === "boolean") return value ? "是" : "否"
  if (typeof value === "number") {
    if (key.toLowerCase().includes("bytes") || key.toLowerCase().includes("size")) return formatBytes(value)
    return String(value)
  }
  if (typeof value === "string") {
    if (key === "streamId") return describeStreamReference(value)
    if (key === "jobId") return describeJobReference(value)
    if (key === "cacheKey") return describeCacheReference(value)
    if (key === "decisionReason") return truncateDisplay(value.replaceAll(":", " / ").replaceAll("_", " "), 48)
    return describeOperationalMessage(value, value)
  }
  try {
    return truncateDisplay(JSON.stringify(value), 120)
  } catch {
    return String(value)
  }
}

export function formatDiagnosticDetails(details: Record<string, unknown> | null | undefined) {
  const entries = Object.entries(details ?? {})
  if (!entries.length) return ""
  return entries.map(([key, value]) => `${describeDetailKey(key)}：${describeDetailValue(key, value)}`).join(" / ")
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
      {describeStateLabel(value)}
    </TonePill>
  )
}

export function normalizeFilterText(value: string) {
  const normalized = value.trim()
  return normalized ? normalized : undefined
}

export const selectClassName =
  "h-10 w-full rounded-xl border border-input bg-white/90 px-3 text-sm text-foreground shadow-[0_10px_24px_-24px_rgba(15,23,42,0.22)]"

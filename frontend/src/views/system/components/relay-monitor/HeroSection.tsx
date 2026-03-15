import { Activity, AlertTriangle, BellRing, Clock3, CloudUpload, HardDrive, RadioTower, ShieldCheck, Waypoints } from "lucide-react"

import type { RelayMonitor, SystemRuntime } from "@/ui/api/system"
import { Card, CardContent } from "@/ui/components/ui/card"
import type { DashboardTone } from "@/views/system/components/dashboardTheme"

import { formatBucketSeconds, formatBytes, formatDateTime, formatPercent, renderStateBadge } from "./helpers"
import { MetaChip, MetricTile, OpsSignalTile, StatusField, StatusSidebar, SystemBoard, WatchlistPanel } from "./shared"

type RelayRuntime = SystemRuntime["desktopAgentRelay"]

export function RelayMonitorHeroSection({
  monitor,
  globalRelay,
  runtimeReady,
  runtimeHealthState,
  connectedAgentCount,
  activeStreamCount,
  activeHlsJobCount,
  boundOnlineProjectCount,
  boundOfflineProjectCount,
  errorCount,
  warningCount,
  healthNarrative,
  webhookNarrative,
  priorityActions,
}: {
  monitor: RelayMonitor | undefined
  globalRelay: RelayRuntime | undefined
  runtimeReady: boolean | undefined
  runtimeHealthState: string
  connectedAgentCount: number
  activeStreamCount: number
  activeHlsJobCount: number
  boundOnlineProjectCount: number
  boundOfflineProjectCount: number
  errorCount: number
  warningCount: number
  healthNarrative: string
  webhookNarrative: string
  priorityActions: string[]
}) {
  const alertWebhook = globalRelay?.alertWebhook
  const alertCount = monitor?.alerts.length ?? 0
  const topAlert = monitor?.alerts[0]
  const alertSignalTone: DashboardTone = errorCount > 0 ? "rose" : alertCount > 0 || warningCount > 0 ? "amber" : "emerald"
  const webhookSignalTone: DashboardTone = !alertWebhook?.configured
    ? "slate"
    : alertWebhook.lastError || alertWebhook.failingChannelCount > 0
      ? "amber"
      : alertWebhook.healthyChannelCount >= alertWebhook.channelCount
        ? "emerald"
        : "sky"
  const backlogSignalTone: DashboardTone =
    (globalRelay?.queuedCommandCount ?? 0) > 0 || (globalRelay?.pendingProbeCount ?? 0) > 0 ? "amber" : "emerald"
  const impactSignalTone: DashboardTone = boundOfflineProjectCount > 0 ? "amber" : "emerald"
  const alertSignalValue = alertCount > 0 ? `${alertCount} 条` : "无高优先级"
  const alertSignalDetail =
    alertCount > 0
      ? `最近 1 小时有 ${alertCount} 条高优先级告警；${errorCount} 错误 / ${warningCount} 告警。${topAlert ? ` 最新：${topAlert.title}` : ""}`
      : `${errorCount} 错误 / ${warningCount} 告警；当前没有新的高优先级站内告警。`
  const webhookSignalValue = alertWebhook?.configured
    ? `${alertWebhook.healthyChannelCount}/${alertWebhook.channelCount} 健康`
    : "未配置"
  const webhookSignalDetail =
    alertWebhook?.configured
      ? alertWebhook.lastError
        ? `最近投递仍有错误。最近尝试 ${formatDateTime(alertWebhook.lastAttemptAt)}。`
        : `最近成功投递 ${formatDateTime(alertWebhook.lastSuccessAt)}。`
      : webhookNarrative
  const backlogSignalValue = `${globalRelay?.queuedCommandCount ?? 0} 条排队`
  const backlogSignalDetail = `待处理探测 ${globalRelay?.pendingProbeCount ?? 0}；活跃流 ${activeStreamCount}；活跃 HLS ${activeHlsJobCount}。`
  const impactSignalValue = boundOfflineProjectCount > 0 ? `${boundOfflineProjectCount} 个受影响` : "暂无影响项目"
  const impactSignalDetail =
    boundOfflineProjectCount > 0
      ? `离线绑定项目 ${boundOfflineProjectCount} 个；在线绑定 ${boundOnlineProjectCount} 个。`
      : `当前绑定在线项目 ${boundOnlineProjectCount} 个，未发现离线绑定项目。`

  return (
    <Card className="theme-card-main overflow-hidden border-white/80 bg-[radial-gradient(circle_at_top_left,rgba(221,234,255,0.86),rgba(255,255,255,0)_36%),linear-gradient(145deg,rgba(255,255,255,0.96),rgba(245,247,251,0.92))]">
      <CardContent className="grid gap-6 p-6 sm:p-7 xl:grid-cols-[1.08fr_0.92fr]">
        <div className="space-y-5">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2">
              <MetaChip icon={Waypoints} strong>
                中继监控
              </MetaChip>
              <MetaChip icon={runtimeReady ? ShieldCheck : AlertTriangle}>{`运行时${runtimeReady ? "正常" : "降级"}`}</MetaChip>
              <MetaChip icon={RadioTower}>{`设备 ${monitor?.agentCount ?? 0} · 项目 ${monitor?.projectCount ?? 0}`}</MetaChip>
            </div>
            <div className="space-y-2">
              <h1 className="text-2xl font-semibold tracking-tight text-slate-950 sm:text-[2rem]">中继健康状态、异常影响和关键趋势一屏可见。</h1>
              <p className="max-w-3xl text-sm leading-6 text-slate-600">先确认当前状态，再决定要处理告警、设备绑定还是传输趋势。</p>
            </div>
          </div>

          <div className="grid gap-3 lg:grid-cols-3">
            <MetricTile
              icon={RadioTower}
              label="在线桌面连接器"
              value={connectedAgentCount}
              detail={`绑定在线项目 ${boundOnlineProjectCount} 个，离线项目 ${boundOfflineProjectCount} 个。`}
              tone={connectedAgentCount > 0 ? "sky" : "amber"}
            />
            <MetricTile
              icon={Activity}
              label="实时交付"
              value={activeStreamCount + activeHlsJobCount}
              detail={`活跃流 ${activeStreamCount}，活跃 HLS 任务 ${activeHlsJobCount}。`}
              tone={activeStreamCount + activeHlsJobCount > 0 ? "teal" : "slate"}
            />
            <MetricTile
              icon={AlertTriangle}
              label="受影响项目"
              value={boundOfflineProjectCount}
              detail={boundOfflineProjectCount > 0 ? "这些项目仍绑定到离线设备。" : "当前没有离线绑定项目。"}
              tone={boundOfflineProjectCount > 0 ? "amber" : "emerald"}
            />
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            <MetricTile
              icon={CloudUpload}
              label="上行流量"
              value={formatBytes(monitor?.streamSummary.bytesFromAgentTotal)}
              detail={`浏览器下行 ${formatBytes(monitor?.streamSummary.bytesToViewerTotal)}。`}
              tone="slate"
            />
            <MetricTile
              icon={HardDrive}
              label="HLS 缓存命中率"
              value={formatPercent(globalRelay?.hlsCacheHitRate)}
              detail={`命中 ${globalRelay?.hlsCacheHitCount ?? 0} / Miss ${globalRelay?.hlsCacheMissCount ?? 0} / 请求 ${globalRelay?.hlsCacheRequestCount ?? 0}`}
              tone={globalRelay?.hlsCacheHitRate != null && globalRelay.hlsCacheHitRate >= 0.8 ? "emerald" : "amber"}
            />
          </div>
        </div>

        <StatusSidebar
          eyebrow="当前健康度"
          title="当前健康状态"
          badge={
            <>
              {renderStateBadge(runtimeHealthState)}
              <MetaChip icon={Clock3}>最近样本 {formatDateTime(monitor?.trends.latestCapturedAt)}</MetaChip>
            </>
          }
        >
          <p className="text-sm leading-6 text-slate-600">{healthNarrative}</p>

          <div className="grid gap-3 sm:grid-cols-2">
            <OpsSignalTile icon={AlertTriangle} label="站内告警" value={alertSignalValue} detail={alertSignalDetail} tone={alertSignalTone} />
            <OpsSignalTile icon={BellRing} label="外部通道" value={webhookSignalValue} detail={webhookSignalDetail} tone={webhookSignalTone} />
            <OpsSignalTile icon={Activity} label="运行积压" value={backlogSignalValue} detail={backlogSignalDetail} tone={backlogSignalTone} />
            <OpsSignalTile icon={RadioTower} label="影响范围" value={impactSignalValue} detail={impactSignalDetail} tone={impactSignalTone} />
          </div>

          <WatchlistPanel
            title="待处理队列"
            description="当前最值得优先处理的动作会集中列在这里。"
            tone={alertSignalTone}
            bodyClassName="space-y-3"
          >
              {priorityActions.map((action, index) => (
                <div key={`${index}-${action}`} className="flex items-start gap-3 rounded-xl border bg-white/92 p-3">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">{index + 1}</span>
                  <div className="text-xs leading-5 text-slate-600">{action}</div>
                </div>
              ))}
          </WatchlistPanel>

          <SystemBoard
            eyebrow="运行快照"
            title="值班快照"
            description="当前监测范围、排队、缓存和最近回收情况都汇总在这里。"
            tone={backlogSignalTone}
            bodyClassName="grid gap-3 sm:grid-cols-2"
          >
              <StatusField label="监测范围" value={`设备 ${monitor?.agentCount ?? 0} · 项目 ${monitor?.projectCount ?? 0}`} emphasize />
              <StatusField label="最近成功告警" value={formatDateTime(alertWebhook?.lastSuccessAt)} />
              <StatusField label="命令排队" value={`${globalRelay?.queuedCommandCount ?? 0} 条`} />
              <StatusField label="探测待处理" value={`${globalRelay?.pendingProbeCount ?? 0} 条`} />
              <StatusField label="缓存占用" value={formatBytes(globalRelay?.hlsCacheBytes)} />
              <StatusField label="最近回收" value={formatDateTime(globalRelay?.lastReapedAt)} />
          </SystemBoard>

          <SystemBoard
            eyebrow="采样设置"
            title="采样范围"
            description={`采样周期 ${formatBucketSeconds(monitor?.trends.sampleBucketSeconds)}，保留 ${monitor?.trends.retentionDays ?? 0} 天，历史起点 ${formatDateTime(monitor?.trends.historyStartAt)}。`}
            tone="slate"
          >
            <div className="flex flex-wrap gap-2">
              <MetaChip icon={Clock3}>{`周期 ${formatBucketSeconds(monitor?.trends.sampleBucketSeconds)}`}</MetaChip>
              <MetaChip icon={ShieldCheck}>{`保留 ${monitor?.trends.retentionDays ?? 0} 天`}</MetaChip>
              <MetaChip icon={Activity}>{`最近样本 ${formatDateTime(monitor?.trends.latestCapturedAt)}`}</MetaChip>
            </div>
          </SystemBoard>
        </StatusSidebar>
      </CardContent>
    </Card>
  )
}

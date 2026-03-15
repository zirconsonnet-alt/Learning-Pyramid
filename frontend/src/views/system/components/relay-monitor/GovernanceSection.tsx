import { BellRing, HardDrive, RefreshCcw, ShieldCheck } from "lucide-react"

import type { SystemRuntime } from "@/ui/api/system"
import { Card, CardContent, CardHeader } from "@/ui/components/ui/card"

import { formatBucketSeconds, formatCountSummary, formatDateTime } from "./helpers"
import { CompactMetric, MetaChip, NarrativePanel, SectionHeader, SystemBoard } from "./shared"

type RelayRuntime = SystemRuntime["desktopAgentRelay"]

export function RelayGovernanceSection({ globalRelay }: { globalRelay: RelayRuntime | undefined }) {
  const alertWebhook = globalRelay?.alertWebhook
  const totalReaped = (globalRelay?.reapedStreamCount ?? 0) + (globalRelay?.reapedProbeCount ?? 0) + (globalRelay?.reapedHlsJobCount ?? 0)
  const webhookTone = alertWebhook?.lastError ? "amber" : alertWebhook?.configured ? "emerald" : "slate"
  const janitorTone = totalReaped > 0 || (globalRelay?.hlsCachePrunedCount ?? 0) > 0 ? "amber" : "slate"

  return (
    <Card className="theme-card overflow-hidden">
        <CardHeader className="theme-card-header gap-4">
          <SectionHeader
            icon={ShieldCheck}
            eyebrow="治理概览"
            title="运行治理"
            description="这里会汇总样本保留、后台回收和外部告警通道状态，方便快速判断治理链路是否正常。"
          />
        </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <CompactMetric
            label="样本保留"
            value={`${globalRelay?.metricSampleRetentionDays ?? 0} 天`}
            detail={`Bucket ${formatBucketSeconds(globalRelay?.metricSampleBucketSeconds)}`}
            tone={(globalRelay?.metricSampleRetentionDays ?? 0) > 0 ? "emerald" : "slate"}
          />
          <CompactMetric
            label="持久化样本"
            value={globalRelay?.persistedMetricSampleCount ?? 0}
            detail={`项目 ${globalRelay?.sampledMetricProjectCount ?? 0} 个`}
          />
          <CompactMetric
            label="诊断留存"
            value={globalRelay?.persistedDiagnosticEventCount ?? 0}
            detail={`已裁剪 ${globalRelay?.prunedDiagnosticEventCount ?? 0} 条`}
          />
          <CompactMetric
            label="Webhook 健康"
            value={alertWebhook?.configured ? `${alertWebhook.healthyChannelCount}/${alertWebhook.channelCount}` : "未配置"}
            detail={alertWebhook?.configured ? `Retrying ${alertWebhook.retryingChannelCount} / Failing ${alertWebhook.failingChannelCount}` : "当前没有外部告警通道"}
            tone={webhookTone}
          />
        </div>

        <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
          <div className="space-y-3">
            <NarrativePanel
              icon={alertWebhook?.configured ? BellRing : ShieldCheck}
              title="告警通道状态"
              description={
                alertWebhook?.configured
                  ? alertWebhook.lastError
                    ? `外部告警通道最近投递仍有错误，最近尝试时间 ${formatDateTime(alertWebhook.lastAttemptAt)}。`
                    : `外部告警通道已配置，最近成功时间 ${formatDateTime(alertWebhook.lastSuccessAt)}。`
                  : "当前没有配置外部告警通道，所有异常只会停留在站内监控页面。"
              }
              tone={webhookTone}
            />

            <NarrativePanel
              icon={totalReaped > 0 ? RefreshCcw : HardDrive}
              title="Janitor / Cache 状态"
              description={
                totalReaped > 0 || (globalRelay?.hlsCachePrunedCount ?? 0) > 0
                  ? `最近已回收 ${totalReaped} 个过期对象，Cache 已裁剪 ${globalRelay?.hlsCachePrunedCount ?? 0} 次。`
                  : "最近没有新的 janitor 回收或 cache 裁剪动作。"
              }
              tone={janitorTone}
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <SystemBoard
              eyebrow="样本保留"
              title="采样与诊断留存"
              description="看清当前各类持久化样本的数量和保留面，判断历史是否够支撑排障回溯。"
              tone={(globalRelay?.metricSampleRetentionDays ?? 0) > 0 ? "emerald" : "slate"}
              bodyClassName="space-y-2 text-xs leading-5 text-slate-600"
            >
                <div>{`Metric 样本 ${globalRelay?.persistedMetricSampleCount ?? 0} 条`}</div>
                <div>{`诊断事件 ${globalRelay?.persistedDiagnosticEventCount ?? 0} 条`}</div>
                <div>{`HLS 审计 ${globalRelay?.persistedHlsJobAuditCount ?? 0} 条`}</div>
                <div>{`过期 HLS 同步 ${globalRelay?.persistedExpiredHlsJobCount ?? 0} 条`}</div>
            </SystemBoard>

            <SystemBoard
              eyebrow="回收与裁剪"
              title="回收与裁剪"
              description="集中看 stream、probe、HLS 和 cache 的回收动作，判断后台清理链路有没有在正常工作。"
              tone={janitorTone}
              bodyClassName="space-y-2 text-xs leading-5 text-slate-600"
            >
                <div>{`回收 Stream ${globalRelay?.reapedStreamCount ?? 0}`}</div>
                <div>{`回收 Probe ${globalRelay?.reapedProbeCount ?? 0}`}</div>
                <div>{`回收 HLS ${globalRelay?.reapedHlsJobCount ?? 0}`}</div>
                <div>{`裁剪样本 ${globalRelay?.prunedMetricSampleCount ?? 0}`}</div>
                <div>{`裁剪 Cache ${globalRelay?.hlsCachePrunedCount ?? 0}`}</div>
            </SystemBoard>

            <SystemBoard
              eyebrow="告警投递"
              title="投递与抑制"
              description="查看外部告警通道发了多少、失败多少、被抑制多少，避免只看到站内异常却没发出去。"
              tone={webhookTone}
              bodyClassName="space-y-2 text-xs leading-5 text-slate-600"
            >
                <div>{`已发送 ${alertWebhook?.sentCount ?? 0}`}</div>
                <div>{`失败 ${alertWebhook?.failedCount ?? 0}`}</div>
                <div>{`抑制 ${alertWebhook?.suppressedCount ?? 0}`}</div>
                <div>{`最近告警批次 ${alertWebhook?.lastAlertCount ?? 0}`}</div>
                <div>{`回退 ${alertWebhook?.retryBackoffSeconds ?? 0}s -> ${alertWebhook?.retryMaxBackoffSeconds ?? 0}s`}</div>
            </SystemBoard>
          </div>
        </div>

        <SystemBoard
          eyebrow="治理快照"
          title="治理快照"
          description="把回收时间、最近投递、cache 条目和原因分布收在一起，方便快速判断治理链路有没有积累异常。"
          tone="slate"
          bodyClassName="space-y-3"
        >
          <div className="flex flex-wrap gap-2">
            <MetaChip icon={RefreshCcw}>{`最近回收 ${formatDateTime(globalRelay?.lastReapedAt)}`}</MetaChip>
            <MetaChip icon={BellRing}>{`最近投递 ${formatDateTime(alertWebhook?.lastAttemptAt)}`}</MetaChip>
            <MetaChip icon={HardDrive}>{`Cache 条目 ${globalRelay?.hlsCacheEntryCount ?? 0}`}</MetaChip>
          </div>
          <div className="text-xs leading-6 text-slate-600">
            回收原因：{formatCountSummary(globalRelay?.reapReasonCounts, "暂无回收原因记录")}
          </div>
          <div className="text-xs leading-6 text-slate-600">
            HLS 终态原因：{formatCountSummary(globalRelay?.hlsJobReasonCounts, "最近没有持久化的 HLS 终态原因")}
          </div>
        </SystemBoard>
      </CardContent>
    </Card>
  )
}

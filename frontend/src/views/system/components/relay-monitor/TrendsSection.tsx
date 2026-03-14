import { type ReactNode } from "react"
import { Activity, FolderTree, HardDrive, RadioTower, Waves } from "lucide-react"

import type { RelayMonitor } from "@/ui/api/system"
import { Card, CardContent, CardHeader } from "@/ui/components/ui/card"
import { cn } from "@/ui/utils"

import { formatBucketSeconds, formatBytes, formatDateTime } from "./helpers"
import { CompactMetric, MetaChip, SectionHeader, TrendSparkline } from "./shared"

type CockpitTone = "sky" | "teal" | "amber" | "slate"

function cockpitPanelClass(tone: CockpitTone) {
  if (tone === "sky") return "border-sky-200/80 bg-[linear-gradient(180deg,rgba(239,246,255,0.96),rgba(255,255,255,0.9))]"
  if (tone === "teal") return "border-teal-200/80 bg-[linear-gradient(180deg,rgba(240,253,250,0.96),rgba(255,255,255,0.9))]"
  if (tone === "amber") return "border-amber-200/80 bg-[linear-gradient(180deg,rgba(255,251,235,0.96),rgba(255,255,255,0.9))]"
  return "border-slate-200/80 bg-[linear-gradient(180deg,rgba(248,250,252,0.96),rgba(255,255,255,0.92))]"
}

function CockpitPanel({
  title,
  description,
  tone = "slate",
  chips,
  children,
}: {
  title: string
  description: string
  tone?: CockpitTone
  chips?: string[]
  children: ReactNode
}) {
  return (
    <div className={cn("rounded-[1.25rem] border p-4 shadow-[0_18px_40px_-32px_rgba(15,23,42,0.16)]", cockpitPanelClass(tone))}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-slate-950">{title}</div>
          <div className="mt-1 text-xs leading-5 text-slate-600">{description}</div>
        </div>
        {chips?.length ? (
          <div className="flex flex-wrap gap-2">
            {chips.map((chip) => (
              <MetaChip key={chip}>{chip}</MetaChip>
            ))}
          </div>
        ) : null}
      </div>
      <div className="mt-4">{children}</div>
    </div>
  )
}

export function RelayTrendsSection({ monitor }: { monitor: RelayMonitor | undefined }) {
  const trend6h = monitor?.trends.timelines.last6Hours ?? []
  const trend24h = monitor?.trends.timelines.lastDay ?? []
  const trend7d = monitor?.trends.timelines.last7Days ?? []
  const trend30d = monitor?.trends.timelines.last30Days ?? []
  const windows = monitor?.trends.windows

  const capacitySignals: Array<{ title: string; detail: string; tone: "amber" | "emerald" | "slate" }> = []
  if ((windows?.lastDay.failedStreams ?? 0) > 0) {
    capacitySignals.push({
      title: "24h Stream 失败",
      detail: `最近 24 小时有 ${windows?.lastDay.failedStreams ?? 0} 个失败 stream，需要结合事件流继续定位。`,
      tone: "amber",
    })
  }
  if ((windows?.lastDay.failedHlsJobs ?? 0) > 0) {
    capacitySignals.push({
      title: "24h HLS 失败",
      detail: `最近 24 小时有 ${windows?.lastDay.failedHlsJobs ?? 0} 个失败 HLS job，需要结合转码审计继续排查。`,
      tone: "amber",
    })
  }
  if ((windows?.last30Days.peakCacheBytes ?? 0) > 0 && (windows?.last30Days.latestCacheBytes ?? 0) >= (windows?.last30Days.peakCacheBytes ?? 0) * 0.8) {
    capacitySignals.push({
      title: "缓存仍在高位",
      detail: `当前缓存 ${formatBytes(windows?.last30Days.latestCacheBytes)}，接近 30 天峰值 ${formatBytes(windows?.last30Days.peakCacheBytes)}。`,
      tone: "amber",
    })
  }
  if ((monitor?.trends.sampleCount ?? 0) === 0) {
    capacitySignals.push({
      title: "采样尚未建立",
      detail: "当前还没有保留下来的 metric sample，趋势判断会偏弱。",
      tone: "slate",
    })
  }
  if (!capacitySignals.length) {
    capacitySignals.push({
      title: "容量态势平稳",
      detail: "最近的流量、缓存和 HLS 活动没有表现出明显异常。",
      tone: "emerald",
    })
  }

  return (
    <Card className="theme-card-main overflow-hidden border-white/80 bg-[radial-gradient(circle_at_top_left,rgba(226,236,248,0.84),rgba(255,255,255,0)_36%),linear-gradient(180deg,rgba(255,255,255,0.98),rgba(245,247,251,0.94))]">
      <CardHeader className="theme-card-header gap-4">
        <SectionHeader
          icon={Waves}
          eyebrow="Capacity Cockpit"
          title="趋势与容量"
          description="把周期采样做成容量驾驶舱：先看风险信号和窗口摘要，再看分时段曲线，最后再判断 retention 是否足够支撑排障。"
        />
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-4 xl:grid-cols-[0.92fr_1.08fr]">
          <div className="theme-status-surface p-4 sm:p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Capacity Watchlist</div>
                <div className="mt-1 text-lg font-semibold text-slate-950">容量风险信号</div>
              </div>
              <MetaChip icon={Activity}>{`样本 ${monitor?.trends.sampleCount ?? 0}`}</MetaChip>
            </div>
            <div className="mt-4 space-y-3">
              {capacitySignals.map((signal) => (
                <div
                  key={`${signal.title}-${signal.detail}`}
                  className={cn(
                    "rounded-[1rem] border px-3 py-3",
                    signal.tone === "amber"
                      ? "border-amber-200/80 bg-amber-50/80"
                      : signal.tone === "emerald"
                        ? "border-emerald-200/80 bg-emerald-50/80"
                        : "border-slate-200/80 bg-white/88",
                  )}
                >
                  <div className="text-sm font-medium text-slate-950">{signal.title}</div>
                  <div className="mt-1 text-xs leading-5 text-slate-600">{signal.detail}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <CompactMetric
              label="近 6 小时传输"
              value={`上行 ${formatBytes(windows?.last6Hours.uploadBytes)}`}
              detail={`下行 ${formatBytes(windows?.last6Hours.viewerBytes)}；失败 stream ${windows?.last6Hours.failedStreams ?? 0}`}
              tone={(windows?.last6Hours.failedStreams ?? 0) > 0 ? "amber" : "slate"}
            />
            <CompactMetric
              label="近 24 小时 HLS"
              value={formatBytes(windows?.lastDay.artifactBytes)}
              detail={`完成 ${windows?.lastDay.completedHlsJobs ?? 0} / 失败 ${windows?.lastDay.failedHlsJobs ?? 0}`}
              tone={(windows?.lastDay.failedHlsJobs ?? 0) > 0 ? "amber" : "slate"}
            />
            <CompactMetric
              label="近 7 天活跃峰值"
              value={`${windows?.last7Days.peakActiveStreams ?? 0} / ${windows?.last7Days.peakActiveHlsJobs ?? 0}`}
              detail="峰值 Stream / HLS Job"
            />
            <CompactMetric
              label="近 30 天缓存"
              value={formatBytes(windows?.last30Days.peakCacheBytes)}
              detail={`当前 ${formatBytes(windows?.last30Days.latestCacheBytes)}；项目 ${monitor?.trends.sampledProjectCount ?? 0}`}
              tone={(windows?.last30Days.latestCacheBytes ?? 0) > 0 && (windows?.last30Days.latestCacheBytes ?? 0) >= (windows?.last30Days.peakCacheBytes ?? 0) * 0.8 ? "amber" : "slate"}
            />
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-2">
          <CockpitPanel
            title="近 6 小时实时流量"
            description="适合判断上行和浏览器下行是否同步，以及短时间内是否出现吞吐骤降。"
            tone="teal"
            chips={[`Bucket ${formatBucketSeconds(monitor?.trends.sampleBucketSeconds)}`, `点数 ${trend6h.length}`]}
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <div className="text-xs text-slate-600">上行到服务端</div>
                <TrendSparkline values={trend6h.map((item) => item.uploadBytes)} stroke="#0f766e" />
              </div>
              <div className="space-y-2">
                <div className="text-xs text-slate-600">下行到浏览器</div>
                <TrendSparkline values={trend6h.map((item) => item.viewerBytes)} stroke="#2563eb" />
              </div>
            </div>
          </CockpitPanel>

          <CockpitPanel
            title="近 24 小时活动强度"
            description="观察活跃 stream、活跃 HLS 和缓存体积是否一起抬升，方便判断是流量高峰还是积压。"
            tone="amber"
            chips={[`峰值 Stream ${windows?.lastDay.peakActiveStreams ?? 0}`, `峰值 HLS ${windows?.lastDay.peakActiveHlsJobs ?? 0}`]}
          >
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="space-y-2">
                <div className="text-xs text-slate-600">活跃 Stream</div>
                <TrendSparkline values={trend24h.map((item) => item.activeStreamCount)} stroke="#0f766e" />
              </div>
              <div className="space-y-2">
                <div className="text-xs text-slate-600">活跃 HLS Job</div>
                <TrendSparkline values={trend24h.map((item) => item.activeHlsJobCount)} stroke="#ea580c" />
              </div>
              <div className="space-y-2">
                <div className="text-xs text-slate-600">缓存体积</div>
                <TrendSparkline values={trend24h.map((item) => item.cacheBytes)} stroke="#475569" />
              </div>
            </div>
          </CockpitPanel>

          <CockpitPanel
            title="近 7 天吞吐与失败"
            description="按更长窗口看周内波动，适合判断失败是否只是瞬时尖刺，还是持续的容量/稳定性问题。"
            tone="sky"
            chips={[`完成 Stream ${windows?.last7Days.completedStreams ?? 0}`, `失败 Stream ${windows?.last7Days.failedStreams ?? 0}`]}
          >
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="space-y-2">
                <div className="text-xs text-slate-600">上行</div>
                <TrendSparkline values={trend7d.map((item) => item.uploadBytes)} stroke="#0f766e" />
              </div>
              <div className="space-y-2">
                <div className="text-xs text-slate-600">下行</div>
                <TrendSparkline values={trend7d.map((item) => item.viewerBytes)} stroke="#2563eb" />
              </div>
              <div className="space-y-2">
                <div className="text-xs text-slate-600">失败 Stream</div>
                <TrendSparkline values={trend7d.map((item) => item.failedStreams)} stroke="#be123c" />
              </div>
            </div>
          </CockpitPanel>

          <CockpitPanel
            title="近 30 天缓存与 HLS"
            description="按天聚合的长期容量视角，适合看缓存高水位、HLS 产物量以及长期的失败分布。"
            tone="slate"
            chips={[`峰值缓存 ${formatBytes(windows?.last30Days.peakCacheBytes)}`, `点数 ${trend30d.length}`]}
          >
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="space-y-2">
                <div className="text-xs text-slate-600">缓存体积</div>
                <TrendSparkline values={trend30d.map((item) => item.cacheBytes)} stroke="#475569" />
              </div>
              <div className="space-y-2">
                <div className="text-xs text-slate-600">HLS 产物</div>
                <TrendSparkline values={trend30d.map((item) => item.artifactBytes)} stroke="#ea580c" />
              </div>
              <div className="space-y-2">
                <div className="text-xs text-slate-600">失败 HLS</div>
                <TrendSparkline values={trend30d.map((item) => item.failedHlsJobs)} stroke="#be123c" />
              </div>
            </div>
          </CockpitPanel>
        </div>

        <div className="rounded-[1.15rem] border border-slate-200/80 bg-slate-50/88 p-4">
          <div className="flex flex-wrap gap-2">
            <MetaChip icon={Waves}>{`采样周期 ${formatBucketSeconds(monitor?.trends.sampleBucketSeconds)}`}</MetaChip>
            <MetaChip icon={HardDrive}>{`保留 ${monitor?.trends.retentionDays ?? 0} 天`}</MetaChip>
            <MetaChip icon={FolderTree}>{`项目 ${monitor?.trends.sampledProjectCount ?? 0}`}</MetaChip>
            <MetaChip icon={RadioTower}>{`最近样本 ${formatDateTime(monitor?.trends.latestCapturedAt)}`}</MetaChip>
          </div>
          <div className="mt-3 text-xs leading-6 text-slate-600">
            历史起点 {formatDateTime(monitor?.trends.historyStartAt)}；最近样本 {formatDateTime(monitor?.trends.latestCapturedAt)}；总样本 {monitor?.trends.sampleCount ?? 0}。
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

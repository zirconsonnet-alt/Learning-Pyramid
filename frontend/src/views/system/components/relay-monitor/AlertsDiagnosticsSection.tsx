import { Activity, AlertTriangle, CheckCircle2, Siren } from "lucide-react"

import type { RelayMonitor } from "@/ui/api/system"
import { Card, CardContent, CardHeader } from "@/ui/components/ui/card"

import { formatCountSummary, formatDateTime, renderStateBadge } from "./helpers"
import { BoardEntryCard, CompactMetric, ControlDeck, EmptyState, EntryNote, MetaChip, NarrativePanel, SectionHeader, SystemBoard } from "./shared"

function alertTone(severity: "error" | "warning") {
  return severity === "error" ? ("rose" as const) : ("amber" as const)
}

function eventTone(level: string) {
  const normalized = level.trim().toUpperCase()
  if (normalized === "ERROR") return "rose" as const
  if (normalized === "WARNING") return "amber" as const
  if (normalized === "INFO") return "sky" as const
  return "slate" as const
}

export function RelayAlertsDiagnosticsSection({ monitor }: { monitor: RelayMonitor | undefined }) {
  const errorCount = monitor?.diagnosticSummary.errorCount ?? 0
  const warningCount = monitor?.diagnosticSummary.warningCount ?? 0
  const alertCount = monitor?.alerts.length ?? 0
  const topAlert = monitor?.alerts[0]
  const topEvent = monitor?.recentDiagnostics[0]

  return (
    <div className="grid gap-4 xl:grid-cols-[1.02fr_0.98fr]">
      <Card className="theme-card overflow-hidden">
        <CardHeader className="theme-card-header gap-4">
          <SectionHeader
            icon={Siren}
            eyebrow="Incident Board"
            title="当前告警"
            description="把最近 1 小时的高优先级问题整理成待处理 inbox，优先看影响面和重复出现次数。"
          />
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <CompactMetric label="高优先级告警" value={alertCount} tone={alertCount > 0 ? "amber" : "emerald"} />
            <CompactMetric label="ERROR 事件" value={errorCount} tone={errorCount > 0 ? "rose" : "slate"} />
            <CompactMetric label="WARNING 事件" value={warningCount} tone={warningCount > 0 ? "amber" : "slate"} />
            <CompactMetric
              label="当前焦点"
              value={topAlert ? topAlert.code : "清空"}
              detail={topAlert ? `最近出现 ${topAlert.count} 次` : "最近 1 小时没有新的高优先级告警。"}
              tone={topAlert ? (topAlert.severity === "error" ? "rose" : "amber") : "emerald"}
            />
          </div>

          <NarrativePanel
            icon={topAlert ? AlertTriangle : CheckCircle2}
            title="当前值班判断"
            description={
              topAlert
                ? `最新一条需要优先处理的告警是“${topAlert.title}”，最新时间 ${formatDateTime(topAlert.observedAt)}。`
                : "当前告警 inbox 已清空，可以把注意力转向趋势、绑定和历史诊断。"
            }
            tone={topAlert ? (topAlert.severity === "error" ? "rose" : "amber") : "emerald"}
          />

          <SystemBoard
            eyebrow="Incident Mix"
            title="类别与事件类型分布"
            description="把当前告警背后的类别和事件类型拆开看，方便判断是单点故障还是同类问题在扩散。"
            tone={topAlert ? alertTone(topAlert.severity) : "slate"}
            bodyClassName="space-y-2 text-xs leading-6 text-slate-600"
          >
            <div>类别分布：{formatCountSummary(monitor?.diagnosticSummary.eventsByCategory)}</div>
            <div>事件类型：{formatCountSummary(monitor?.diagnosticSummary.eventsByType)}</div>
          </SystemBoard>

          {monitor?.alerts.length ? (
            <div className="space-y-3">
              {monitor.alerts.map((alert) => (
                <BoardEntryCard
                  key={`${alert.code}:${alert.agentId ?? "na"}:${alert.observedAt}`}
                  title={alert.title}
                  meta={
                    <>
                      <MetaChip>{alert.code}</MetaChip>
                      {alert.agentId ? <MetaChip>{`Agent ${alert.agentId}`}</MetaChip> : null}
                      {alert.projectId ? <MetaChip>{`Project ${alert.projectId}`}</MetaChip> : null}
                    </>
                  }
                  headerRight={
                    <div className="text-right text-xs text-slate-600">
                      <div className="font-medium text-slate-950">{`最近出现 ${alert.count} 次`}</div>
                      <div className="mt-1">{formatDateTime(alert.observedAt)}</div>
                    </div>
                  }
                  tone={alertTone(alert.severity)}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="text-sm leading-6 text-slate-700">{alert.message}</div>
                    <div className="shrink-0">{renderStateBadge(alert.severity.toUpperCase())}</div>
                  </div>
                </BoardEntryCard>
              ))}
            </div>
          ) : (
            <EmptyState message="最近 1 小时没有新的 error / warning 诊断告警。" />
          )}
        </CardContent>
      </Card>

      <Card className="theme-card overflow-hidden">
        <CardHeader className="theme-card-header gap-4">
          <SectionHeader
            icon={Activity}
            eyebrow="Event Stream"
            title="最近诊断"
            description="把结构化诊断事件按事件流展示，适合快速判断是 HLS、probe、manifest-sync 还是 session 层问题。"
          />
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <CompactMetric label="当前载入" value={monitor?.recentDiagnostics.length ?? 0} />
            <CompactMetric label="级别分布" value={formatCountSummary(monitor?.diagnosticSummary.eventsByLevel)} />
            <CompactMetric label="类别数" value={Object.keys(monitor?.diagnosticSummary.eventsByCategory ?? {}).length} />
            <CompactMetric
              label="最新事件"
              value={topEvent?.eventType ?? "暂无"}
              detail={topEvent ? formatDateTime(topEvent.createdAt) : "当前没有最近诊断事件。"}
            />
          </div>

          <ControlDeck
            title={topEvent ? topEvent.eventType : "事件流聚焦"}
            description={
              topEvent
                ? `最近一条事件来自 ${topEvent.agentId}，类别 ${topEvent.category}，类型 ${topEvent.eventType}。`
                : "当前筛选范围下没有可展示的结构化诊断事件。"
            }
            badge={topEvent ? <MetaChip>{topEvent.level}</MetaChip> : null}
            tone={topEvent ? eventTone(topEvent.level) : "slate"}
            bodyClassName="flex flex-wrap gap-2"
          >
            {topEvent ? (
              <>
                <MetaChip>{topEvent.category}</MetaChip>
                <MetaChip>{`Agent ${topEvent.agentId}`}</MetaChip>
                {topEvent.projectId ? <MetaChip>{`Project ${topEvent.projectId}`}</MetaChip> : null}
              </>
            ) : (
              <div className="text-xs leading-5 text-slate-600">调整左侧诊断控制台后，这里会聚焦到当前窗口中的最新一条事件。</div>
            )}
          </ControlDeck>

          {monitor?.recentDiagnostics.length ? (
            <div className="space-y-3">
              {monitor.recentDiagnostics.map((event) => (
                <BoardEntryCard
                  key={event.eventId}
                  title={event.message}
                  meta={
                    <>
                      <MetaChip>{event.category}</MetaChip>
                      <MetaChip>{event.eventType}</MetaChip>
                      <MetaChip>{`Agent ${event.agentId}`}</MetaChip>
                      {event.projectId ? <MetaChip>{`Project ${event.projectId}`}</MetaChip> : null}
                    </>
                  }
                  headerRight={renderStateBadge(event.level)}
                  tone={eventTone(event.level)}
                  bodyClassName="space-y-3"
                >
                  <div className="grid gap-2 text-xs text-slate-600 sm:grid-cols-2">
                    <div>{`时间 ${formatDateTime(event.createdAt)}`}</div>
                    <div>{event.instanceId ? `实例 ${event.instanceId}` : "实例未关联"}</div>
                    <div>{event.relativePath ? `文件 ${event.relativePath}` : "文件路径未关联"}</div>
                    <div>{`事件 ID ${event.eventId}`}</div>
                  </div>

                  {Object.keys(event.details ?? {}).length > 0 ? (
                    <EntryNote tone={eventTone(event.level)}>
                      {Object.entries(event.details)
                        .map(([key, value]) => `${key}=${String(value)}`)
                        .join(" / ")}
                    </EntryNote>
                  ) : null}
                </BoardEntryCard>
              ))}
            </div>
          ) : (
            <EmptyState message="当前没有最近诊断事件。" />
          )}
        </CardContent>
      </Card>
    </div>
  )
}

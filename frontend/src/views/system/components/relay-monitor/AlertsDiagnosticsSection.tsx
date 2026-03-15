import { Activity, AlertTriangle, CheckCircle2, Siren } from "lucide-react"

import type { RelayMonitor } from "@/ui/api/system"
import { Card, CardContent, CardHeader } from "@/ui/components/ui/card"

import {
  describeAgentReference,
  describeDiagnosticCategory,
  describeEventReference,
  describeEventType,
  describeInstanceReference,
  describeOperationalMessage,
  describeProjectReference,
  describeStateLabel,
  formatCountSummary,
  formatDateTime,
  formatDiagnosticDetails,
  renderStateBadge,
} from "./helpers"
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
            eyebrow="告警概览"
            title="当前告警"
            description="最近 1 小时的重要异常会集中显示，便于先确认影响面和重复次数。"
          />
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <CompactMetric label="高优先级告警" value={alertCount} tone={alertCount > 0 ? "amber" : "emerald"} />
            <CompactMetric label="错误事件" value={errorCount} tone={errorCount > 0 ? "rose" : "slate"} />
            <CompactMetric label="告警事件" value={warningCount} tone={warningCount > 0 ? "amber" : "slate"} />
            <CompactMetric
              label="当前重点"
              value={topAlert ? describeEventType(topAlert.code) : "已清空"}
              detail={topAlert ? `${topAlert.title}；最近出现 ${topAlert.count} 次` : "最近 1 小时没有新的高优先级告警。"}
              tone={topAlert ? (topAlert.severity === "error" ? "rose" : "amber") : "emerald"}
            />
          </div>

          <NarrativePanel
            icon={topAlert ? AlertTriangle : CheckCircle2}
            title="当前值班判断"
            description={
              topAlert
                ? `最新一条需要优先处理的告警是“${topAlert.title}”，最新时间 ${formatDateTime(topAlert.observedAt)}。`
                : "当前高优先级告警已清空，可以把注意力转向趋势、绑定和历史诊断。"
            }
            tone={topAlert ? (topAlert.severity === "error" ? "rose" : "amber") : "emerald"}
          />

          <SystemBoard
            eyebrow="告警分布"
            title="类别与事件类型分布"
            description="当前告警按类别和事件类型汇总，便于判断是单点故障还是同类问题在扩散。"
            tone={topAlert ? alertTone(topAlert.severity) : "slate"}
            bodyClassName="space-y-2 text-xs leading-6 text-slate-600"
          >
            <div>类别分布：{formatCountSummary(monitor?.diagnosticSummary.eventsByCategory, "暂无", describeDiagnosticCategory)}</div>
            <div>事件类型：{formatCountSummary(monitor?.diagnosticSummary.eventsByType, "暂无", describeEventType)}</div>
          </SystemBoard>

          {monitor?.alerts.length ? (
            <div className="space-y-3">
              {monitor.alerts.map((alert) => (
                <BoardEntryCard
                  key={`${alert.code}:${alert.agentId ?? "na"}:${alert.observedAt}`}
                  title={alert.title}
                  meta={
                    <>
                      <MetaChip>{describeEventType(alert.code)}</MetaChip>
                      {alert.agentId ? <MetaChip>{describeAgentReference(alert.agentId)}</MetaChip> : null}
                      {alert.projectId ? <MetaChip>{describeProjectReference(undefined, alert.projectId)}</MetaChip> : null}
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
                    <div className="text-sm leading-6 text-slate-700">{describeOperationalMessage(alert.message)}</div>
                    <div className="shrink-0">{renderStateBadge(alert.severity.toUpperCase())}</div>
                  </div>
                </BoardEntryCard>
              ))}
            </div>
          ) : (
            <EmptyState message="最近 1 小时没有新的错误或告警诊断事件。" />
          )}
        </CardContent>
      </Card>

      <Card className="theme-card overflow-hidden">
        <CardHeader className="theme-card-header gap-4">
          <SectionHeader
            icon={Activity}
            eyebrow="事件流"
            title="最近诊断"
            description="按时间查看最近诊断事件，便于判断问题出在 HLS、探测、清单同步还是会话层。"
          />
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <CompactMetric label="当前载入" value={monitor?.recentDiagnostics.length ?? 0} />
            <CompactMetric label="级别分布" value={formatCountSummary(monitor?.diagnosticSummary.eventsByLevel, "暂无", describeStateLabel)} />
            <CompactMetric label="类别数" value={Object.keys(monitor?.diagnosticSummary.eventsByCategory ?? {}).length} />
            <CompactMetric
              label="最新事件"
              value={topEvent ? describeEventType(topEvent.eventType) : "暂无"}
              detail={topEvent ? formatDateTime(topEvent.createdAt) : "当前没有最近诊断事件。"}
            />
          </div>

          <ControlDeck
            eyebrow="当前重点"
            title={topEvent ? describeEventType(topEvent.eventType) : "当前事件"}
            description={
              topEvent
                ? `最近一条事件来自 ${describeAgentReference(topEvent.agentId)}，类别 ${describeDiagnosticCategory(topEvent.category)}，类型 ${describeEventType(topEvent.eventType)}。`
                : "当前筛选范围下没有可展示的结构化诊断事件。"
            }
            badge={topEvent ? renderStateBadge(topEvent.level) : null}
            tone={topEvent ? eventTone(topEvent.level) : "slate"}
            bodyClassName="flex flex-wrap gap-2"
          >
            {topEvent ? (
              <>
                <MetaChip>{describeDiagnosticCategory(topEvent.category)}</MetaChip>
                <MetaChip>{describeAgentReference(topEvent.agentId)}</MetaChip>
                {topEvent.projectId ? <MetaChip>{describeProjectReference(undefined, topEvent.projectId)}</MetaChip> : null}
              </>
            ) : (
              <div className="text-xs leading-5 text-slate-600">当前筛选范围内还没有事件。可以扩大时间窗口或清空筛选后再查看。</div>
            )}
          </ControlDeck>

          {monitor?.recentDiagnostics.length ? (
            <div className="space-y-3">
              {monitor.recentDiagnostics.map((event) => (
                <BoardEntryCard
                  key={event.eventId}
                  title={describeOperationalMessage(event.message)}
                  meta={
                    <>
                      <MetaChip>{describeDiagnosticCategory(event.category)}</MetaChip>
                      <MetaChip>{describeEventType(event.eventType)}</MetaChip>
                      <MetaChip>{describeAgentReference(event.agentId)}</MetaChip>
                      {event.projectId ? <MetaChip>{describeProjectReference(undefined, event.projectId)}</MetaChip> : null}
                    </>
                  }
                  headerRight={renderStateBadge(event.level)}
                  tone={eventTone(event.level)}
                  bodyClassName="space-y-3"
                >
                  <div className="grid gap-2 text-xs text-slate-600 sm:grid-cols-2">
                    <div>{`时间 ${formatDateTime(event.createdAt)}`}</div>
                    <div>{describeInstanceReference(event.instanceId)}</div>
                    <div>{event.relativePath ? `文件 ${event.relativePath}` : "文件路径未关联"}</div>
                    <div>{describeEventReference(event.eventId)}</div>
                  </div>

                  {Object.keys(event.details ?? {}).length > 0 ? (
                    <EntryNote tone={eventTone(event.level)}>
                      {formatDiagnosticDetails(event.details)}
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

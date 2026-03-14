import { AlertTriangle, Clock3, Download, RotateCcw, Search, ShieldCheck } from "lucide-react"

import type { RelayMonitor } from "@/ui/api/system"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"

import { renderStateBadge, selectClassName } from "./helpers"
import { CompactMetric, ControlDeck, MetaChip, SectionHeader } from "./shared"

export function RelayMonitorFiltersCard({
  monitor,
  runtimeHealthState,
  alertCount,
  boundOfflineProjectCount,
  priorityHeadline,
  diagnosticSinceHours,
  diagnosticLimit,
  diagnosticLevel,
  diagnosticCategory,
  diagnosticEventType,
  diagnosticSearchText,
  filterChips,
  hasDiagnosticFilters,
  filterNarrative,
  onSinceHoursChange,
  onLimitChange,
  onLevelChange,
  onCategoryChange,
  onEventTypeChange,
  onSearchTextChange,
  onReset,
  onApplyPreset,
  onExport,
}: {
  monitor: RelayMonitor | undefined
  runtimeHealthState: string
  alertCount: number
  boundOfflineProjectCount: number
  priorityHeadline: string
  diagnosticSinceHours: string
  diagnosticLimit: string
  diagnosticLevel: string
  diagnosticCategory: string
  diagnosticEventType: string
  diagnosticSearchText: string
  filterChips: string[]
  hasDiagnosticFilters: boolean
  filterNarrative: string
  onSinceHoursChange: (value: string) => void
  onLimitChange: (value: string) => void
  onLevelChange: (value: string) => void
  onCategoryChange: (value: string) => void
  onEventTypeChange: (value: string) => void
  onSearchTextChange: (value: string) => void
  onReset: () => void
  onApplyPreset: (preset: "default" | "errors" | "warnings" | "history") => void
  onExport: () => void
}) {
  const trimmedCategory = diagnosticCategory.trim()
  const trimmedEventType = diagnosticEventType.trim()
  const trimmedQuery = diagnosticSearchText.trim()
  const isDefaultPreset = !hasDiagnosticFilters
  const isErrorPreset =
    diagnosticSinceHours === "24" &&
    diagnosticLimit === "24" &&
    diagnosticLevel === "ERROR" &&
    !trimmedCategory &&
    !trimmedEventType &&
    !trimmedQuery
  const isWarningPreset =
    diagnosticSinceHours === "72" &&
    diagnosticLimit === "24" &&
    diagnosticLevel === "WARNING" &&
    !trimmedCategory &&
    !trimmedEventType &&
    !trimmedQuery
  const isHistoryPreset =
    diagnosticSinceHours === "168" &&
    diagnosticLimit === "50" &&
    !diagnosticLevel &&
    !trimmedCategory &&
    !trimmedEventType &&
    !trimmedQuery
  const postureTone =
    runtimeHealthState === "ERROR"
      ? "rose"
      : runtimeHealthState === "WARNING" || runtimeHealthState === "DEGRADED"
        ? "amber"
        : "emerald"
  const incidentTone = alertCount > 0 ? "rose" : boundOfflineProjectCount > 0 ? "amber" : "emerald"

  return (
    <Card className="theme-card-main overflow-hidden border-white/80 bg-[radial-gradient(circle_at_top_right,rgba(226,236,248,0.8),rgba(255,255,255,0)_34%),linear-gradient(180deg,rgba(255,255,255,0.98),rgba(246,248,252,0.94))]">
      <CardHeader className="theme-card-header gap-4">
        <SectionHeader
          icon={Search}
          eyebrow="Ops Control Bar"
          title="诊断控制台"
          description="把诊断检索做成值班控制台：先看当前态势，再用快速预设缩小排查范围，然后再补精确搜索。"
          actions={
            <>
              <Button variant="outline" onClick={onReset} disabled={!hasDiagnosticFilters}>
                <RotateCcw className="size-4" />
                重置筛选
              </Button>
              <Button variant="outline" onClick={onExport}>
                <Download className="size-4" />
                导出 JSONL
              </Button>
            </>
          }
        />
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-3 xl:grid-cols-[1.05fr_0.95fr]">
          <ControlDeck
            title="当前巡检焦点"
            badge={renderStateBadge(runtimeHealthState)}
            tone={postureTone}
            className="sm:p-5"
            bodyClassName="space-y-4"
          >
            <div className="rounded-[1rem] border border-white/80 bg-white/85 p-3 text-sm leading-6 text-slate-600">{priorityHeadline}</div>

            <div className="flex flex-wrap gap-2">
              <MetaChip icon={Clock3}>{`窗口 ${diagnosticSinceHours}h`}</MetaChip>
              <MetaChip icon={Search}>{`展示 ${diagnosticLimit} 条`}</MetaChip>
              <MetaChip icon={alertCount > 0 ? AlertTriangle : ShieldCheck}>{alertCount > 0 ? `${alertCount} 条高优先级告警` : "当前无高优先级告警"}</MetaChip>
            </div>

            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">快速预设</div>
              <div className="mt-2 flex flex-wrap gap-2">
                <Button size="sm" variant={isDefaultPreset ? "default" : "outline"} onClick={() => onApplyPreset("default")}>
                  默认巡检
                </Button>
                <Button size="sm" variant={isErrorPreset ? "default" : "outline"} onClick={() => onApplyPreset("errors")}>
                  错误优先
                </Button>
                <Button size="sm" variant={isWarningPreset ? "default" : "outline"} onClick={() => onApplyPreset("warnings")}>
                  告警扫描
                </Button>
                <Button size="sm" variant={isHistoryPreset ? "default" : "outline"} onClick={() => onApplyPreset("history")}>
                  7 天回溯
                </Button>
              </div>
            </div>

            <div className="rounded-[1rem] border border-slate-200/80 bg-slate-50/82 p-3">
              <div className="flex items-center gap-2 text-sm font-medium text-slate-950">
                <Search className="size-4 text-primary" />
                当前筛选
              </div>
              <div className="mt-1 text-xs leading-5 text-slate-600">{filterNarrative}</div>
              <div className="mt-3 flex flex-wrap gap-2">
                {filterChips.length ? (
                  filterChips.map((chip) => <MetaChip key={chip}>{chip}</MetaChip>)
                ) : (
                  <div className="text-sm text-muted-foreground">当前使用默认巡检视图：最近 24 小时、12 条结果、不过滤级别和关键字。</div>
                )}
              </div>
            </div>
          </ControlDeck>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-2">
            <CompactMetric label="当前态势" value={runtimeHealthState} detail="来自 runtime、站内告警和离线绑定项目的综合判断。" tone={postureTone} />
            <CompactMetric
              label="匹配事件"
              value={monitor?.diagnosticSummary.eventCount ?? 0}
              detail={`${monitor?.recentDiagnostics.length ?? 0} 条已载入到当前视图。`}
            />
            <CompactMetric
              label="错误 / 告警"
              value={`${monitor?.diagnosticSummary.errorCount ?? 0} / ${monitor?.diagnosticSummary.warningCount ?? 0}`}
              detail={alertCount > 0 ? `最近 1 小时还有 ${alertCount} 条高优先级站内告警。` : "当前没有新的高优先级站内告警。"}
              tone={incidentTone}
            />
            <CompactMetric
              label="导出视图"
              value={`${Math.max(Number(diagnosticLimit), 500)} 条`}
              detail="导出会复用当前筛选，并把结果窗口放宽到至少 500 条。"
            />
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
          <div className="space-y-2">
            <Label htmlFor="diagnostic-since-hours">时间窗口</Label>
            <select
              id="diagnostic-since-hours"
              className={selectClassName}
              value={diagnosticSinceHours}
              onChange={(e) => onSinceHoursChange(e.target.value)}
            >
              <option value="24">最近 24 小时</option>
              <option value="72">最近 72 小时</option>
              <option value="168">最近 7 天</option>
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="diagnostic-limit">展示条数</Label>
            <select
              id="diagnostic-limit"
              className={selectClassName}
              value={diagnosticLimit}
              onChange={(e) => onLimitChange(e.target.value)}
            >
              <option value="12">12 条</option>
              <option value="24">24 条</option>
              <option value="50">50 条</option>
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="diagnostic-level">级别</Label>
            <select
              id="diagnostic-level"
              className={selectClassName}
              value={diagnosticLevel}
              onChange={(e) => onLevelChange(e.target.value)}
            >
              <option value="">全部级别</option>
              <option value="ERROR">ERROR</option>
              <option value="WARNING">WARNING</option>
              <option value="INFO">INFO</option>
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="diagnostic-category">类别</Label>
            <Input
              id="diagnostic-category"
              value={diagnosticCategory}
              onChange={(e) => onCategoryChange(e.target.value)}
              placeholder="例如 hls / probe"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="diagnostic-event-type">事件类型</Label>
            <Input
              id="diagnostic-event-type"
              value={diagnosticEventType}
              onChange={(e) => onEventTypeChange(e.target.value)}
              placeholder="例如 hls_failed"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="diagnostic-query">关键字</Label>
            <Input
              id="diagnostic-query"
              value={diagnosticSearchText}
              onChange={(e) => onSearchTextChange(e.target.value)}
              placeholder="message / path / agent / details"
            />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

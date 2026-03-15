import { useDeferredValue } from "react"
import { Waypoints } from "lucide-react"
import { Link, useSearchParams } from "react-router-dom"

import { getRelayDiagnosticsExportUrl } from "@/ui/api/system"
import { ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader } from "@/ui/components/ui/card"
import { useRelayMonitor, useSystemCapabilities, useSystemRuntime } from "@/ui/queries/system"
import { RelayAlertsDiagnosticsSection } from "@/views/system/components/relay-monitor/AlertsDiagnosticsSection"
import { RelayBindingsSection } from "@/views/system/components/relay-monitor/BindingsSection"
import { RelayMonitorFiltersCard } from "@/views/system/components/relay-monitor/FiltersCard"
import { RelayGovernanceSection } from "@/views/system/components/relay-monitor/GovernanceSection"
import { RelayMonitorHeroSection } from "@/views/system/components/relay-monitor/HeroSection"
import { RelayHlsIssuesSection } from "@/views/system/components/relay-monitor/HlsIssuesSection"
import { RelayTrendsSection } from "@/views/system/components/relay-monitor/TrendsSection"
import { formatApiError, normalizeFilterText } from "@/views/system/components/relay-monitor/helpers"
import { SectionHeader } from "@/views/system/components/relay-monitor/shared"

function getQueryString(searchParams: URLSearchParams, key: string, defaultValue = "") {
  return searchParams.get(key)?.trim() || defaultValue
}

type DiagnosticPreset = "default" | "errors" | "warnings" | "history"

export function RelayMonitorPage() {
  const capabilitiesQ = useSystemCapabilities()
  const isHostedMode = capabilitiesQ.data?.appMode === "hosted"
  const [searchParams, setSearchParams] = useSearchParams()

  const diagnosticSinceHours = getQueryString(searchParams, "since", "24")
  const diagnosticLimit = getQueryString(searchParams, "limit", "12")
  const diagnosticLevel = getQueryString(searchParams, "level")
  const diagnosticCategory = getQueryString(searchParams, "category")
  const diagnosticEventType = getQueryString(searchParams, "eventType")
  const diagnosticSearchText = getQueryString(searchParams, "query")
  const deferredDiagnosticSearchText = useDeferredValue(diagnosticSearchText)

  function updateSearchParam(key: string, value: string, defaultValue = "") {
    const nextSearchParams = new URLSearchParams(searchParams)
    const normalized = value.trim()
    if (!normalized || normalized === defaultValue) nextSearchParams.delete(key)
    else nextSearchParams.set(key, normalized)
    setSearchParams(nextSearchParams, { replace: true })
  }

  function resetFilters() {
    const nextSearchParams = new URLSearchParams(searchParams)
    nextSearchParams.delete("since")
    nextSearchParams.delete("limit")
    nextSearchParams.delete("level")
    nextSearchParams.delete("category")
    nextSearchParams.delete("eventType")
    nextSearchParams.delete("query")
    setSearchParams(nextSearchParams, { replace: true })
  }

  function applyDiagnosticPreset(preset: DiagnosticPreset) {
    if (preset === "default") {
      resetFilters()
      return
    }

    const nextSearchParams = new URLSearchParams(searchParams)
    nextSearchParams.delete("category")
    nextSearchParams.delete("eventType")
    nextSearchParams.delete("query")

    if (preset === "errors") {
      nextSearchParams.delete("since")
      nextSearchParams.set("limit", "24")
      nextSearchParams.set("level", "ERROR")
    } else if (preset === "warnings") {
      nextSearchParams.set("since", "72")
      nextSearchParams.set("limit", "24")
      nextSearchParams.set("level", "WARNING")
    } else if (preset === "history") {
      nextSearchParams.set("since", "168")
      nextSearchParams.set("limit", "50")
      nextSearchParams.delete("level")
    }

    setSearchParams(nextSearchParams, { replace: true })
  }

  const monitorFilters = {
    diagnosticSinceHours: Number(diagnosticSinceHours),
    diagnosticLimit: Number(diagnosticLimit),
    alertSinceHours: 1,
    diagnosticLevel: normalizeFilterText(diagnosticLevel) ?? null,
    diagnosticCategory: normalizeFilterText(diagnosticCategory) ?? null,
    diagnosticEventType: normalizeFilterText(diagnosticEventType) ?? null,
    diagnosticQuery: normalizeFilterText(deferredDiagnosticSearchText) ?? null,
  }
  const exportUrl = getRelayDiagnosticsExportUrl({
    diagnosticSinceHours: Number(diagnosticSinceHours),
    diagnosticLimit: Math.max(Number(diagnosticLimit), 500),
    diagnosticLevel: normalizeFilterText(diagnosticLevel) ?? null,
    diagnosticCategory: normalizeFilterText(diagnosticCategory) ?? null,
    diagnosticEventType: normalizeFilterText(diagnosticEventType) ?? null,
    diagnosticQuery: normalizeFilterText(diagnosticSearchText) ?? null,
  })
  const runtimeQ = useSystemRuntime(isHostedMode)
  const monitorQ = useRelayMonitor(monitorFilters, isHostedMode)

  if (capabilitiesQ.isLoading) {
    return <LoadingNotice title="正在加载 Relay Monitor" message="正在确认当前部署能力和桌面中继监控数据。" />
  }

  if (!isHostedMode) {
    return (
      <Card className="theme-card overflow-hidden">
        <CardHeader className="theme-card-header gap-4">
          <SectionHeader
            icon={Waypoints}
            eyebrow="Hosted 模式"
            title="中继监控"
            description="当前部署不是 hosted 模式，没有桌面中继运行时可监控。"
          />
        </CardHeader>
        <CardContent>
          <Button asChild variant="outline">
            <Link to="/projects">返回项目列表</Link>
          </Button>
        </CardContent>
      </Card>
    )
  }

  const globalRelay = runtimeQ.data?.desktopAgentRelay
  const monitor = monitorQ.data
  const connectedAgentCount = globalRelay?.connectedAgentCount ?? 0
  const activeStreamCount = globalRelay?.activeStreamCount ?? 0
  const activeHlsJobCount = globalRelay?.activeHlsJobCount ?? 0
  const boundOnlineProjectCount = monitor?.bindingSummary.boundOnlineProjectCount ?? 0
  const boundOfflineProjectCount = monitor?.bindingSummary.boundOfflineProjectCount ?? 0
  const alertCount = monitor?.alerts.length ?? 0
  const errorCount = monitor?.diagnosticSummary.errorCount ?? 0
  const warningCount = monitor?.diagnosticSummary.warningCount ?? 0

  const runtimeHealthState =
    monitorQ.error || runtimeQ.error ? "ERROR" : alertCount > 0 || boundOfflineProjectCount > 0 ? "WARNING" : runtimeQ.data?.ready ? "HEALTHY" : "DEGRADED"
  const topAlert = monitor?.alerts[0]
  const healthNarrative =
    monitorQ.error || runtimeQ.error
      ? "监控接口返回了错误，当前摘要可能不完整。请先查看页面底部错误信息和最近诊断。"
      : topAlert
        ? `最近 1 小时有 ${alertCount} 条高优先级告警，最新一条是“${topAlert.title}”。`
        : boundOfflineProjectCount > 0
          ? `${boundOfflineProjectCount} 个项目仍绑定到离线设备，建议优先检查桌面连接器在线状态。`
          : "当前没有新的高优先级告警，桌面连接器、HLS 转码和 relay 运行面整体稳定。"

  const filterChips: string[] = []
  if (diagnosticSinceHours !== "24") filterChips.push(`时间窗口 ${diagnosticSinceHours}h`)
  if (diagnosticLimit !== "12") filterChips.push(`展示 ${diagnosticLimit} 条`)
  if (normalizeFilterText(diagnosticLevel)) filterChips.push(`级别 ${diagnosticLevel}`)
  if (normalizeFilterText(diagnosticCategory)) filterChips.push(`类别 ${diagnosticCategory}`)
  if (normalizeFilterText(diagnosticEventType)) filterChips.push(`事件 ${diagnosticEventType}`)
  if (normalizeFilterText(diagnosticSearchText)) filterChips.push(`关键字 ${diagnosticSearchText.trim()}`)

  const hasDiagnosticFilters = filterChips.length > 0
  const webhookNarrative = globalRelay?.alertWebhook?.configured
    ? globalRelay.alertWebhook.lastError
      ? `已配置 ${globalRelay.alertWebhook.channelCount} 个外部通道，但最近一次投递仍有错误。`
      : `已配置 ${globalRelay.alertWebhook.channelCount} 个外部通道，最近一次成功投递已记录。`
    : "当前没有配置外部告警通道，问题只会停留在站内监控面板。"
  const filterNarrative = hasDiagnosticFilters
    ? `当前诊断视图正在使用 ${filterChips.length} 个筛选条件，适合做定向排查。`
    : "当前诊断视图保持默认范围，适合做账号级巡检。"
  const bindingNarrative =
    boundOfflineProjectCount > 0
      ? `${boundOfflineProjectCount} 个项目仍绑定到离线设备，建议优先处理这些项目的播放可用性。`
      : "当前所有桌面连接器绑定项目都处于在线或未绑定状态。"
  const hlsNarrative =
    (monitor?.hlsSummary.activityWindows.lastDay.failedCount ?? 0) > 0
      ? `近 24 小时内有 ${monitor?.hlsSummary.activityWindows.lastDay.failedCount ?? 0} 个 HLS job 失败，需要结合失败原因继续跟踪。`
      : "近 24 小时没有新的 HLS 失败，转码链路整体平稳。"
  const issueNarrative =
    (monitor?.streamSummary.failedSessionCount ?? 0) > 0 || (monitor?.streamSummary.cancelledSessionCount ?? 0) > 0
      ? `最近存在 ${monitor?.streamSummary.failedSessionCount ?? 0} 个失败会话和 ${monitor?.streamSummary.cancelledSessionCount ?? 0} 个取消会话。`
      : "最近没有新的失败或取消 relay 会话。"
  const priorityActions: string[] = []
  if (boundOfflineProjectCount > 0) {
    priorityActions.push(`先检查 ${boundOfflineProjectCount} 个离线绑定项目对应的桌面连接器在线状态和项目绑定关系。`)
  }
  if (alertCount > 0 && topAlert) {
    priorityActions.push(`查看最近 1 小时的高优先级告警，优先处理最新一条“${topAlert.title}”。`)
  }
  if ((monitor?.streamSummary.failedSessionCount ?? 0) > 0 || (monitor?.hlsSummary.activityWindows.lastDay.failedCount ?? 0) > 0) {
    priorityActions.push("继续核查最近失败的 relay 会话和 HLS job，确认是桌面连接器断线、浏览器中断还是转码失败。")
  }
  if (globalRelay?.alertWebhook?.configured && globalRelay.alertWebhook.lastError) {
    priorityActions.push("修复外部告警通道最近一次投递错误，避免异常只停留在站内监控面板。")
  }
  if (!priorityActions.length) {
    priorityActions.push("当前没有新的高优先级动作，继续巡检在线连接器、实时交付和诊断趋势即可。")
  }
  const priorityHeadline = priorityActions[0] ?? "当前没有新的高优先级动作。"

  return (
    <div className="space-y-5 pb-4">
      <RelayMonitorHeroSection
        monitor={monitor}
        globalRelay={globalRelay}
        runtimeReady={runtimeQ.data?.ready}
        runtimeHealthState={runtimeHealthState}
        connectedAgentCount={connectedAgentCount}
        activeStreamCount={activeStreamCount}
        activeHlsJobCount={activeHlsJobCount}
        boundOnlineProjectCount={boundOnlineProjectCount}
        boundOfflineProjectCount={boundOfflineProjectCount}
        errorCount={errorCount}
        warningCount={warningCount}
        healthNarrative={healthNarrative}
        webhookNarrative={webhookNarrative}
        priorityActions={priorityActions}
      />

      <RelayMonitorFiltersCard
        monitor={monitor}
        runtimeHealthState={runtimeHealthState}
        alertCount={alertCount}
        boundOfflineProjectCount={boundOfflineProjectCount}
        priorityHeadline={priorityHeadline}
        diagnosticSinceHours={diagnosticSinceHours}
        diagnosticLimit={diagnosticLimit}
        diagnosticLevel={diagnosticLevel}
        diagnosticCategory={diagnosticCategory}
        diagnosticEventType={diagnosticEventType}
        diagnosticSearchText={diagnosticSearchText}
        filterChips={filterChips}
        hasDiagnosticFilters={hasDiagnosticFilters}
        filterNarrative={filterNarrative}
        onSinceHoursChange={(value) => updateSearchParam("since", value, "24")}
        onLimitChange={(value) => updateSearchParam("limit", value, "12")}
        onLevelChange={(value) => updateSearchParam("level", value)}
        onCategoryChange={(value) => updateSearchParam("category", value)}
        onEventTypeChange={(value) => updateSearchParam("eventType", value)}
        onSearchTextChange={(value) => updateSearchParam("query", value)}
        onReset={resetFilters}
        onApplyPreset={applyDiagnosticPreset}
        onExport={() => globalThis.window?.open(exportUrl, "_blank", "noopener,noreferrer")}
      />
      <RelayAlertsDiagnosticsSection monitor={monitor} />
      <RelayBindingsSection
        monitor={monitor}
        connectedAgentCount={connectedAgentCount}
        activeStreamCount={activeStreamCount}
        activeHlsJobCount={activeHlsJobCount}
        bindingNarrative={bindingNarrative}
        boundOfflineProjectCount={boundOfflineProjectCount}
      />
      <RelayTrendsSection monitor={monitor} />
      <RelayHlsIssuesSection monitor={monitor} hlsNarrative={hlsNarrative} issueNarrative={issueNarrative} />
      <RelayGovernanceSection globalRelay={globalRelay} />

      {monitorQ.error ? <ErrorNotice title="Relay Monitor 数据加载失败" message={formatApiError(monitorQ.error)} /> : null}
      {runtimeQ.error ? <ErrorNotice title="Relay Runtime 摘要加载失败" message={formatApiError(runtimeQ.error)} /> : null}
    </div>
  )
}

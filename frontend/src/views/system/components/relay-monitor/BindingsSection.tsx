import { AlertTriangle, CheckCircle2, Film, FolderTree, MonitorCog, RadioTower } from "lucide-react"

import type { RelayMonitor } from "@/ui/api/system"
import { Card, CardContent, CardHeader } from "@/ui/components/ui/card"

import { describeAgentReference, describeSourceKind, formatDateTime, renderStateBadge } from "./helpers"
import { BoardEntryCard, CompactMetric, EmptyState, EntryNote, MetaChip, NarrativePanel, SectionHeader, SystemBoard, WatchlistItem, WatchlistPanel } from "./shared"

function bindingTone(state: "ONLINE" | "OFFLINE" | "UNBOUND") {
  if (state === "ONLINE") return "emerald" as const
  if (state === "OFFLINE") return "amber" as const
  return "slate" as const
}

function agentTone(connected: boolean, status: string) {
  if (connected && status === "ONLINE") return "emerald" as const
  if (status === "ONLINE") return "sky" as const
  return "slate" as const
}

export function RelayBindingsSection({
  monitor,
  connectedAgentCount,
  activeStreamCount,
  activeHlsJobCount,
  bindingNarrative,
  boundOfflineProjectCount,
}: {
  monitor: RelayMonitor | undefined
  connectedAgentCount: number
  activeStreamCount: number
  activeHlsJobCount: number
  bindingNarrative: string
  boundOfflineProjectCount: number
}) {
  const projectBindings = monitor?.projectBindings ?? []
  const offlineBindings = projectBindings.filter((binding) => binding.bindingState === "OFFLINE")
  const unboundProjects = projectBindings.filter((binding) => binding.bindingState === "UNBOUND")

  return (
    <div className="grid gap-4 xl:grid-cols-[1.08fr_0.92fr]">
      <Card className="theme-card overflow-hidden">
        <CardHeader className="theme-card-header gap-4">
          <SectionHeader
            icon={FolderTree}
            eyebrow="项目影响"
            title="项目绑定设备"
            description="先看哪些项目受设备状态影响，再看它们当前到底绑到了哪台桌面连接器。"
          />
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <CompactMetric label="桌面连接器项目" value={monitor?.bindingSummary.desktopAgentProjectCount ?? 0} />
            <CompactMetric label="绑定在线" value={monitor?.bindingSummary.boundOnlineProjectCount ?? 0} tone="emerald" />
            <CompactMetric label="绑定离线" value={monitor?.bindingSummary.boundOfflineProjectCount ?? 0} tone="rose" />
            <CompactMetric label="服务器文件系统" value={monitor?.bindingSummary.serverFsProjectCount ?? 0} />
            <CompactMetric label="旧绑定待清理" value={monitor?.bindingSummary.supersededBindingCount ?? 0} tone="amber" />
          </div>

          <NarrativePanel
            icon={boundOfflineProjectCount > 0 ? AlertTriangle : CheckCircle2}
            title="绑定健康度"
            description={bindingNarrative}
            tone={boundOfflineProjectCount > 0 ? "amber" : "emerald"}
          />

          <div className="grid gap-3 xl:grid-cols-[0.95fr_1.05fr]">
            <SystemBoard
              title="影响看板"
              description="这里会汇总需要优先处理的离线绑定和待接入项目。"
              tone={offlineBindings.length > 0 ? "amber" : unboundProjects.length > 0 ? "slate" : "emerald"}
              bodyClassName="grid gap-3 sm:grid-cols-3 xl:grid-cols-1"
            >
                <CompactMetric label="离线绑定项目" value={offlineBindings.length} tone={offlineBindings.length > 0 ? "amber" : "emerald"} />
                <CompactMetric label="未绑定项目" value={unboundProjects.length} tone={unboundProjects.length > 0 ? "slate" : "emerald"} />
                <CompactMetric
                  label="需清理旧绑定"
                  value={monitor?.bindingSummary.supersededBindingCount ?? 0}
                  tone={(monitor?.bindingSummary.supersededBindingCount ?? 0) > 0 ? "amber" : "emerald"}
                />
            </SystemBoard>

            <WatchlistPanel
              title="优先处理"
              description={
                offlineBindings.length
                  ? `当前有 ${offlineBindings.length} 个项目绑定到离线设备，应优先确认客户端在线状态。`
                  : "当前没有离线绑定项目。"
              }
              tone={offlineBindings.length > 0 ? "amber" : "emerald"}
              bodyClassName="space-y-2"
            >
                {offlineBindings.length ? (
                  offlineBindings.slice(0, 3).map((binding) => (
                    <WatchlistItem
                      key={`watch-${binding.projectId}`}
                      title={binding.projectTitle}
                      detail={binding.deviceName ?? binding.desktopAgentId ?? "未知设备"}
                      tone="amber"
                    />
                  ))
                ) : (
                  <WatchlistItem title="当前绑定平稳" detail="当前没有需要立即处理的离线绑定项目。" tone="emerald" />
                )}
            </WatchlistPanel>
          </div>

          {projectBindings.length ? (
            <div className="space-y-3">
              {projectBindings.map((binding) => (
                <BoardEntryCard
                  key={binding.projectId}
                  title={binding.projectTitle}
                  meta={
                    <>
                      <MetaChip>{describeSourceKind(binding.sourceKind)}</MetaChip>
                      {binding.sourceRootLabel ? <MetaChip>{`标签：${binding.sourceRootLabel}`}</MetaChip> : null}
                    </>
                  }
                  headerRight={
                    <div className="flex flex-col items-end gap-2 text-right text-xs text-slate-600">
                      {renderStateBadge(binding.bindingState)}
                      <div>
                        <div className="font-medium text-slate-950">{binding.deviceName ?? "未绑定设备"}</div>
                        <div className="mt-1">{binding.appVersion ?? "未知版本"}</div>
                      </div>
                    </div>
                  }
                  tone={bindingTone(binding.bindingState)}
                  bodyClassName="space-y-3"
                >
                  <div className="grid gap-2 text-xs text-slate-600 sm:grid-cols-2 xl:grid-cols-4">
                    <div>{describeAgentReference(binding.desktopAgentId)}</div>
                    <div>{`最近心跳 ${formatDateTime(binding.lastSeenAt)}`}</div>
                    <div>{`配对时间 ${formatDateTime(binding.pairedAt)}`}</div>
                    <div>{binding.connected ? "当前设备已连接 relay" : "当前设备未连接 relay"}</div>
                  </div>

                  {binding.supersededByAgentId ? (
                    <EntryNote tone="amber" className="text-amber-900">
                      当前项目仍绑定旧连接器，较新的同机连接器是 {binding.supersededByAgentId}。
                    </EntryNote>
                  ) : null}
                </BoardEntryCard>
              ))}
            </div>
          ) : (
            <EmptyState message="当前账号下还没有项目绑定摘要。" />
          )}
        </CardContent>
      </Card>

      <Card className="theme-card overflow-hidden">
        <CardHeader className="theme-card-header gap-4">
          <SectionHeader
            icon={MonitorCog}
            eyebrow="设备列表"
            title="我的桌面连接器"
            description="按设备查看当前账号下的桌面连接器，直接确认在线、连接和负载状态。"
          />
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <MetaChip icon={RadioTower}>{`在线 ${connectedAgentCount} / 总计 ${monitor?.agentCount ?? 0}`}</MetaChip>
            <MetaChip icon={AlertTriangle}>{`活跃 Stream ${activeStreamCount}`}</MetaChip>
            <MetaChip icon={Film}>{`活跃 HLS ${activeHlsJobCount}`}</MetaChip>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            <CompactMetric label="在线连接 relay" value={connectedAgentCount} tone={connectedAgentCount > 0 ? "emerald" : "slate"} />
            <CompactMetric label="活跃 Stream" value={activeStreamCount} tone={activeStreamCount > 0 ? "sky" : "slate"} />
            <CompactMetric label="活跃 HLS" value={activeHlsJobCount} tone={activeHlsJobCount > 0 ? "amber" : "slate"} />
          </div>

          {monitor?.agents.length ? (
            <div className="space-y-3">
              {monitor.agents.map((agent) => (
                <BoardEntryCard
                  key={agent.agentId}
                  title={agent.deviceName}
                  meta={
                    <>
                      <MetaChip>{agent.platform}</MetaChip>
                      <MetaChip>{agent.appVersion}</MetaChip>
                      <MetaChip>{agent.agentId}</MetaChip>
                    </>
                  }
                  headerRight={
                    <div className="flex flex-wrap gap-2">
                      {renderStateBadge(agent.status)}
                      {renderStateBadge(agent.connected ? "CONNECTED" : "DISCONNECTED")}
                    </div>
                  }
                  tone={agentTone(agent.connected, agent.status)}
                  bodyClassName="space-y-3"
                >
                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    <CompactMetric label="队列命令" value={agent.queuedCommandCount} />
                    <CompactMetric label="活跃 Stream / Probe" value={`${agent.activeStreamCount} / ${agent.pendingProbeCount}`} />
                    <CompactMetric label="HLS Job" value={`${agent.activeHlsJobCount} 活跃 / ${agent.hlsJobCount} 累计`} />
                  </div>

                  <div className="grid gap-2 text-xs text-slate-600 sm:grid-cols-2">
                    <div>{`最近心跳 ${formatDateTime(agent.lastSeenAt)}`}</div>
                    <div>{`配对时间 ${formatDateTime(agent.pairedAt)}`}</div>
                  </div>
                </BoardEntryCard>
              ))}
            </div>
          ) : (
            <EmptyState message="当前账号下还没有已配对的桌面连接器。" />
          )}
        </CardContent>
      </Card>
    </div>
  )
}

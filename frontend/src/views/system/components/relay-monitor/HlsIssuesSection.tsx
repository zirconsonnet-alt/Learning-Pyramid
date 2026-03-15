import { AlertTriangle, BellRing, CheckCircle2, Film } from "lucide-react"

import type { RelayMonitor } from "@/ui/api/system"
import { Card, CardContent, CardHeader } from "@/ui/components/ui/card"

import {
  describeAgentReference,
  describeCacheReference,
  describeInstanceReference,
  describeJobReference,
  describeOperationalMessage,
  describeProjectReference,
  describeStateLabel,
  describeStreamMode,
  formatBytes,
  formatCountSummary,
  formatDateTime,
  renderStateBadge,
} from "./helpers"
import { BoardEntryCard, CompactMetric, EmptyState, EntryNote, MetaChip, NarrativePanel, SectionHeader, SystemBoard } from "./shared"

function jobTone(state: string) {
  const normalized = state.trim().toUpperCase()
  if (normalized === "FAILED") return "rose" as const
  if (normalized === "CANCELLED") return "amber" as const
  if (normalized === "RUNNING" || normalized === "ACTIVE") return "sky" as const
  if (normalized === "COMPLETED") return "emerald" as const
  return "slate" as const
}

function issueTone(status: "FAILED" | "CANCELLED") {
  return status === "FAILED" ? ("rose" as const) : ("amber" as const)
}

export function RelayHlsIssuesSection({
  monitor,
  hlsNarrative,
  issueNarrative,
}: {
  monitor: RelayMonitor | undefined
  hlsNarrative: string
  issueNarrative: string
}) {
  const recentFailedJob =
    monitor?.recentHlsJobs.find((job) => job.state.trim().toUpperCase() === "FAILED")
    ?? monitor?.recentHlsJobs.find((job) => job.message)
    ?? null
  const recentFailedIssue = monitor?.recentIssues[0] ?? null

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
      <Card className="theme-card overflow-hidden">
        <CardHeader className="theme-card-header gap-4">
          <SectionHeader
            icon={Film}
            eyebrow="转码概览"
            title="HLS 转码审计"
            description="最近的转码活动、失败情况和任务时间线都集中显示在这里。"
          />
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <CompactMetric label="任务总数" value={monitor?.hlsSummary.jobCount ?? 0} />
            <CompactMetric label="活跃 HLS 任务" value={monitor?.hlsSummary.activeHlsJobCount ?? 0} tone={(monitor?.hlsSummary.activeHlsJobCount ?? 0) > 0 ? "sky" : "slate"} />
            <CompactMetric
              label="近 1 小时"
              value={`${monitor?.hlsSummary.activityWindows.lastHour.jobCount ?? 0} 个`}
              detail={formatBytes(monitor?.hlsSummary.activityWindows.lastHour.artifactBytes)}
            />
            <CompactMetric
              label="近 24 小时失败"
              value={monitor?.hlsSummary.activityWindows.lastDay.failedCount ?? 0}
              detail={`取消 ${monitor?.hlsSummary.activityWindows.lastDay.cancelledCount ?? 0} 个`}
              tone={(monitor?.hlsSummary.activityWindows.lastDay.failedCount ?? 0) > 0 ? "rose" : "emerald"}
            />
          </div>

          <div className="grid gap-3 xl:grid-cols-[0.92fr_1.08fr]">
            <SystemBoard
              title="当前关注项"
              description="需要继续跟踪的失败或异常转码任务会显示在这里。"
              tone={recentFailedJob ? jobTone(recentFailedJob.state) : "emerald"}
              bodyClassName="space-y-3"
            >
                <CompactMetric
                  label="24h 失败率"
                  value={`${monitor?.hlsSummary.activityWindows.lastDay.failedCount ?? 0} / ${monitor?.hlsSummary.activityWindows.lastDay.jobCount ?? 0}`}
                  tone={(monitor?.hlsSummary.activityWindows.lastDay.failedCount ?? 0) > 0 ? "amber" : "emerald"}
                />
                <CompactMetric
                  label="主要失败原因"
                  value={describeOperationalMessage(Object.keys(monitor?.hlsSummary.issueReasonCounts ?? {})[0] ?? "", "暂无")}
                  detail={formatCountSummary(monitor?.hlsSummary.issueReasonCounts, "当前没有记录到失败原因", describeOperationalMessage)}
                  tone={Object.keys(monitor?.hlsSummary.issueReasonCounts ?? {}).length ? "amber" : "slate"}
                />
                <CompactMetric
                  label="当前焦点任务"
                  value={recentFailedJob ? describeStateLabel(recentFailedJob.state) : "清空"}
                  detail={recentFailedJob ? recentFailedJob.relativePath : "当前没有失败中的 HLS 转码任务。"}
                  tone={recentFailedJob ? "rose" : "emerald"}
                />
            </SystemBoard>

            <div className="space-y-3">
              <NarrativePanel
                icon={(monitor?.hlsSummary.activityWindows.lastDay.failedCount ?? 0) > 0 ? AlertTriangle : CheckCircle2}
                title="最近转码态势"
                description={hlsNarrative}
                tone={(monitor?.hlsSummary.activityWindows.lastDay.failedCount ?? 0) > 0 ? "amber" : "emerald"}
              />

              <SystemBoard
                eyebrow="转码快照"
                title="转码分布与时间窗"
                description="状态分布、问题原因和 1 小时 / 24 小时窗口都汇总在这里。"
                tone={(monitor?.hlsSummary.activityWindows.lastDay.failedCount ?? 0) > 0 ? "amber" : "slate"}
                bodyClassName="space-y-2 text-xs leading-6 text-slate-600"
              >
                <div>状态分布：{formatCountSummary(monitor?.hlsSummary.jobsByState, "暂无", describeStateLabel)}</div>
                <div>问题原因：{formatCountSummary(monitor?.hlsSummary.issueReasonCounts, "暂无", describeOperationalMessage)}</div>
                <div>
                  近 1 小时：完成 {monitor?.hlsSummary.activityWindows.lastHour.completedCount ?? 0} / 失败{" "}
                  {monitor?.hlsSummary.activityWindows.lastHour.failedCount ?? 0} / 取消{" "}
                  {monitor?.hlsSummary.activityWindows.lastHour.cancelledCount ?? 0}
                </div>
                <div>
                  近 24 小时：完成 {monitor?.hlsSummary.activityWindows.lastDay.completedCount ?? 0} / 失败{" "}
                  {monitor?.hlsSummary.activityWindows.lastDay.failedCount ?? 0} / 取消{" "}
                  {monitor?.hlsSummary.activityWindows.lastDay.cancelledCount ?? 0}
                </div>
              </SystemBoard>
            </div>
          </div>

          {monitor?.recentHlsJobs.length ? (
            <div className="space-y-3">
              {monitor.recentHlsJobs.map((job) => (
                <BoardEntryCard
                  key={job.jobId}
                  title={<div className="truncate">{job.relativePath}</div>}
                  meta={
                    <>
                      <MetaChip>{describeJobReference(job.jobId)}</MetaChip>
                      <MetaChip>{describeInstanceReference(job.instanceId)}</MetaChip>
                      <MetaChip>{describeCacheReference(job.cacheKey)}</MetaChip>
                    </>
                  }
                  headerRight={renderStateBadge(job.state)}
                  tone={jobTone(job.state)}
                  bodyClassName="space-y-3"
                >
                  <div className="grid gap-2 text-xs text-slate-600 sm:grid-cols-2 xl:grid-cols-4">
                    <div>{`创建 ${formatDateTime(job.createdAt)}`}</div>
                    <div>{`更新 ${formatDateTime(job.updatedAt)}`}</div>
                    <div>{`过期 ${formatDateTime(job.expiresAt)}`}</div>
                    <div>{job.finishedAt ? `结束 ${formatDateTime(job.finishedAt)}` : "当前仍在处理或等待结束"}</div>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    <CompactMetric label="产物数" value={job.artifactCount} />
                    <CompactMetric label="产物体积" value={formatBytes(job.artifactBytes)} />
                    <CompactMetric label="最近上传" value={job.lastArtifactAt ? formatDateTime(job.lastArtifactAt) : "未上传"} />
                  </div>

                  {job.message ? (
                    <EntryNote tone={jobTone(job.state)} className={job.state.trim().toUpperCase() === "FAILED" ? "text-rose-700" : undefined}>
                      {describeOperationalMessage(job.message)}
                    </EntryNote>
                  ) : null}
                </BoardEntryCard>
              ))}
            </div>
          ) : (
            <EmptyState message="当前没有可见的 HLS 转码任务。" />
          )}
        </CardContent>
      </Card>

      <Card className="theme-card overflow-hidden">
        <CardHeader className="theme-card-header gap-4">
          <SectionHeader
            icon={AlertTriangle}
            eyebrow="会话概览"
            title="最近中继问题"
            description="失败或取消的中继会话会集中显示，便于确认失败原因和受影响项目。"
          />
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <CompactMetric label="会话总数" value={monitor?.streamSummary.sessionCount ?? 0} />
            <CompactMetric
              label="失败 / 取消"
              value={`${monitor?.streamSummary.failedSessionCount ?? 0} / ${monitor?.streamSummary.cancelledSessionCount ?? 0}`}
              tone={(monitor?.streamSummary.failedSessionCount ?? 0) > 0 ? "rose" : (monitor?.streamSummary.cancelledSessionCount ?? 0) > 0 ? "amber" : "emerald"}
            />
            <CompactMetric label="已完成" value={monitor?.streamSummary.completedSessionCount ?? 0} tone="emerald" />
            <CompactMetric label="进行中" value={monitor?.streamSummary.activeSessionCount ?? 0} tone="sky" />
          </div>

          <div className="grid gap-3 xl:grid-cols-[0.92fr_1.08fr]">
            <SystemBoard
              title="当前关注项"
              description="最近失败或取消的会话会集中显示在这里。"
              tone={recentFailedIssue ? issueTone(recentFailedIssue.status) : "emerald"}
              bodyClassName="space-y-3"
            >
                <CompactMetric
                  label="问题原因分布"
                  value={describeOperationalMessage(Object.keys(monitor?.streamSummary.issueReasonCounts ?? {})[0] ?? "", "暂无")}
                  detail={formatCountSummary(monitor?.streamSummary.issueReasonCounts, "当前没有问题原因记录", describeOperationalMessage)}
                  tone={Object.keys(monitor?.streamSummary.issueReasonCounts ?? {}).length ? "amber" : "slate"}
                />
                <CompactMetric
                  label="当前焦点会话"
                  value={recentFailedIssue ? describeStateLabel(recentFailedIssue.status) : "清空"}
                  detail={
                    recentFailedIssue
                      ? `${describeProjectReference(recentFailedIssue.projectTitle, recentFailedIssue.projectId)} / ${describeInstanceReference(recentFailedIssue.instanceId)}`
                      : "最近没有失败或取消的中继会话。"
                  }
                  tone={recentFailedIssue ? (recentFailedIssue.status === "FAILED" ? "rose" : "amber") : "emerald"}
                />
                <CompactMetric
                  label="最新失败原因"
                  value={describeOperationalMessage(recentFailedIssue?.failureReason, "暂无")}
                  detail={recentFailedIssue ? formatDateTime(recentFailedIssue.finishedAt ?? recentFailedIssue.updatedAt) : "当前没有需要继续跟踪的会话失败。"}
                  tone={recentFailedIssue?.failureReason ? "rose" : "slate"}
                />
            </SystemBoard>

            <div className="space-y-3">
              <SystemBoard
                eyebrow="问题分布"
                title="问题原因分布"
                description="当前会话故障原因会集中汇总在这里。"
                tone={recentFailedIssue ? issueTone(recentFailedIssue.status) : "slate"}
                bodyClassName="text-xs leading-6 text-slate-600"
              >
                <div>{formatCountSummary(monitor?.streamSummary.issueReasonCounts, "暂无", describeOperationalMessage)}</div>
              </SystemBoard>

              <NarrativePanel
                icon={(monitor?.streamSummary.failedSessionCount ?? 0) > 0 ? AlertTriangle : BellRing}
                title="近期回放稳定性"
                description={issueNarrative}
                tone={(monitor?.streamSummary.failedSessionCount ?? 0) > 0 ? "amber" : "emerald"}
              />
            </div>
          </div>

          {monitor?.recentIssues.length ? (
            <div className="space-y-3">
              {monitor.recentIssues.map((issue) => (
                <BoardEntryCard
                  key={issue.streamId}
                  title={
                    <>
                      {describeProjectReference(issue.projectTitle, issue.projectId)} / {describeInstanceReference(issue.instanceId)}
                    </>
                  }
                  meta={
                    <>
                      <MetaChip>{describeProjectReference(issue.projectTitle, issue.projectId)}</MetaChip>
                      <MetaChip>{describeAgentReference(issue.agentId)}</MetaChip>
                      <MetaChip>{describeStreamMode(issue.mode)}</MetaChip>
                    </>
                  }
                  headerRight={renderStateBadge(issue.status)}
                  tone={issueTone(issue.status)}
                  bodyClassName="space-y-3"
                >
                  <div className="grid gap-2 text-xs text-slate-600 sm:grid-cols-2 xl:grid-cols-4">
                    <div>{`开始 ${formatDateTime(issue.createdAt)}`}</div>
                    <div>{`结束 ${formatDateTime(issue.finishedAt ?? issue.updatedAt)}`}</div>
                    <div>{`连接器上行 ${formatBytes(issue.bytesFromAgent)}`}</div>
                    <div>{`浏览器下行 ${formatBytes(issue.bytesToViewer)}`}</div>
                  </div>

                  <div className="grid gap-2 text-xs text-slate-600 sm:grid-cols-2">
                    <div>{describeStreamMode(issue.mode)}</div>
                    <div>{describeInstanceReference(issue.instanceId)}</div>
                  </div>

                  {issue.failureReason ? (
                    <EntryNote tone={issueTone(issue.status)} className={issue.status === "FAILED" ? "text-rose-700 text-sm leading-6" : "text-sm leading-6"}>
                      {describeOperationalMessage(issue.failureReason)}
                    </EntryNote>
                  ) : null}
                </BoardEntryCard>
              ))}
            </div>
          ) : (
            <EmptyState message="最近没有失败或取消的中继会话。" />
          )}
        </CardContent>
      </Card>
    </div>
  )
}

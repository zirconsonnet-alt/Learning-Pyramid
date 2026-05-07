import { type ReactNode } from "react"
import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BookOpenCheck,
  CheckCircle2,
  CreditCard,
  DatabaseBackup,
  Gauge,
  History,
  ShieldAlert,
  ShieldCheck,
  UserRoundCog,
  UsersRound,
  WalletCards,
  type LucideIcon,
} from "lucide-react"

import { ApiError } from "@/ui/api/http"
import { getSystemDataSafetyStatus, type DataSafetyStatus } from "@/ui/api/system"
import { ContentEmptyState, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { useAdminActionLogs, useAdminMembershipOverview, useAdminOverview } from "@/ui/queries/admin"
import { cn } from "@/ui/utils"
import { AdminNav } from "@/views/admin/AdminNav"
import { formatDurationCompact } from "@/views/profile/profileStats"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function formatCompactNumber(value: number) {
  if (!Number.isFinite(value)) return "0"
  return new Intl.NumberFormat("zh-CN").format(value)
}

function formatPercent(numerator: number, denominator: number) {
  if (!Number.isFinite(numerator) || !Number.isFinite(denominator) || denominator <= 0) return "0%"
  return `${Math.round((numerator / denominator) * 100)}%`
}

function formatMoneyCent(value: number) {
  if (!Number.isFinite(value) || value <= 0) return "¥0"
  const yuan = value / 100
  return `¥${yuan.toLocaleString("zh-CN", { maximumFractionDigits: value % 100 === 0 ? 0 : 2 })}`
}

function formatDateTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function describeDataSafetyState(status?: DataSafetyStatus) {
  if (!status) return { label: "读取中", detail: "正在读取持久化存储与受保护数据状态。", tone: "default" as const }
  if (status.state === "ok") return { label: "正常", detail: "暂无阻断级数据安全发现。", tone: "accent" as const }
  if (status.state === "warning") return { label: "需复核", detail: "存在非阻断发现，建议在发布前复核。", tone: "warning" as const }
  if (status.state === "blocked") return { label: "阻断发布", detail: "存在阻断级发现，请先处理数据安全问题。", tone: "danger" as const }
  return { label: "未知", detail: "当前无法确认数据安全状态，按阻断处理。", tone: "danger" as const }
}

function StatusPill(props: { children: ReactNode; tone?: "default" | "accent" | "warning" | "danger" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium",
        props.tone === "accent"
          ? "border-primary/20 bg-[hsl(var(--primary)/0.08)] text-primary"
          : props.tone === "warning"
            ? "border-amber-200 bg-amber-50 text-amber-800"
            : props.tone === "danger"
              ? "border-destructive/20 bg-destructive/10 text-destructive"
              : "theme-meta",
      )}
    >
      {props.children}
    </span>
  )
}

function MetricTile({
  icon: Icon,
  label,
  value,
  detail,
  tone = "default",
}: {
  icon: LucideIcon
  label: string
  value: ReactNode
  detail: ReactNode
  tone?: "default" | "accent" | "warning"
}) {
  return (
    <div
      className={cn(
        "theme-soft-surface p-4",
        tone === "accent" && "border-primary/20 bg-[hsl(var(--primary)/0.07)]",
        tone === "warning" && "border-amber-200 bg-amber-50/80",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">{label}</div>
          <div className="text-2xl font-semibold tracking-tight text-foreground">{value}</div>
        </div>
        <div
          className={cn(
            "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl",
            tone === "accent"
              ? "bg-primary text-primary-foreground"
              : tone === "warning"
                ? "bg-amber-100 text-amber-800"
                : "bg-[color:var(--theme-icon-bg)] text-[color:var(--theme-icon-text)]",
          )}
        >
          <Icon className="h-4 w-4" />
        </div>
      </div>
      <div className="mt-3 text-xs leading-5 text-muted-foreground">{detail}</div>
    </div>
  )
}

function ActionTile({
  icon: Icon,
  title,
  detail,
  to,
  action,
}: {
  icon: LucideIcon
  title: string
  detail: string
  to: string
  action: string
}) {
  return (
    <Link
      to={to}
      className="theme-soft-surface group flex min-h-[8.5rem] flex-col justify-between p-4 transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/25 hover:bg-white"
    >
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[color:var(--theme-icon-bg)] text-[color:var(--theme-icon-text)] transition-colors group-hover:bg-primary group-hover:text-primary-foreground">
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="text-sm font-semibold text-foreground">{title}</div>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">{detail}</p>
        </div>
      </div>
      <span className="mt-4 inline-flex items-center gap-1.5 text-xs font-semibold text-primary">
        {action}
        <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
      </span>
    </Link>
  )
}

function RiskItem({
  icon: Icon,
  title,
  detail,
  tone = "default",
}: {
  icon: LucideIcon
  title: string
  detail: ReactNode
  tone?: "default" | "accent" | "warning" | "danger"
}) {
  return (
    <div
      className={cn(
        "rounded-[1.1rem] border px-4 py-3",
        tone === "accent"
          ? "border-primary/20 bg-[hsl(var(--primary)/0.07)]"
          : tone === "warning"
            ? "border-amber-200 bg-amber-50/80"
            : tone === "danger"
              ? "border-destructive/20 bg-destructive/10"
              : "border-border/70 bg-white/70",
      )}
    >
      <div className="flex gap-3">
        <div
          className={cn(
            "mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl",
            tone === "accent"
              ? "bg-primary text-primary-foreground"
              : tone === "warning"
                ? "bg-amber-100 text-amber-800"
                : tone === "danger"
                  ? "bg-destructive/10 text-destructive"
                  : "bg-[color:var(--theme-icon-bg)] text-[color:var(--theme-icon-text)]",
          )}
        >
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="text-sm font-semibold text-foreground">{title}</div>
          <div className="mt-1 text-xs leading-5 text-muted-foreground">{detail}</div>
        </div>
      </div>
    </div>
  )
}

export function AdminPage() {
  const overviewQ = useAdminOverview()
  const membershipQ = useAdminMembershipOverview()
  const activityQ = useAdminActionLogs({ limit: 8 })
  const dataSafetyQ = useQuery({
    queryKey: ["adminDataSafetyStatus"],
    queryFn: () => getSystemDataSafetyStatus(),
    staleTime: 60_000,
    refetchInterval: 60_000,
  })

  if (overviewQ.isLoading && !overviewQ.data) {
    return <LoadingNotice title="正在加载后台数据" message="稍等一下，我们正在汇总用户、会员与数据安全状态。" />
  }

  if (overviewQ.error && !overviewQ.data) {
    return <ErrorNotice title="后台管理加载失败" message={formatApiError(overviewQ.error)} />
  }

  const overview = overviewQ.data
  const membership = membershipQ.data
  const dataSafety = describeDataSafetyState(dataSafetyQ.data)
  const dataSafetyFindingCount = dataSafetyQ.data?.findings.length ?? 0
  const activeRate = overview ? formatPercent(overview.activeUsers, overview.users) : "0%"
  const learningRate = overview ? formatPercent(overview.studyUsers, overview.users) : "0%"
  const recentLearningRate = overview ? formatPercent(overview.studyUsers7d, overview.studyUsers) : "0%"
  const paidAmount = membership ? formatMoneyCent(membership.totalPaidAmountCent) : "读取中"
  const pendingOrders = membership?.pendingOrders ?? 0
  const payoutQueueCent = membership ? membership.withdrawableCommissionCent + membership.reservedWithdrawalCent : 0
  const hasMembershipRisk = pendingOrders > 0 || payoutQueueCent > 0

  return (
    <div className="space-y-6">
      <div className="space-y-4">
        <section className="overflow-hidden rounded-[2rem] border [border-color:var(--theme-card-main-border)] [background:radial-gradient(circle_at_top_left,hsl(var(--primary)/0.12),transparent_34%),var(--theme-card-main-bg)] p-5 shadow-[var(--theme-card-main-shadow)] sm:p-6">
          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(300px,0.45fr)]">
            <div className="min-w-0 space-y-4">
              <div className="space-y-2">
                <div className="text-sm text-muted-foreground">后台管理 / 运营控制台</div>
                <h1 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">运营控制台</h1>
                <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
                  这里聚合当前后台真正需要盯住的信号：用户活跃、会员运营、数据安全和最近操作记录。连续处理用户问题时，进入独立用户页会更专注。
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <StatusPill tone={dataSafety.tone}>数据安全：{dataSafety.label}</StatusPill>
                <StatusPill tone={hasMembershipRisk ? "warning" : "accent"}>会员待办：{hasMembershipRisk ? "需要处理" : "平稳"}</StatusPill>
                <StatusPill>日志窗口：最近 8 条</StatusPill>
              </div>
            </div>
            <div className="theme-status-surface grid gap-3 p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-foreground">今日重点</div>
                  <div className="mt-1 text-xs text-muted-foreground">先处理阻断，再处理交易和权限。</div>
                </div>
                <Gauge className="h-5 w-5 text-primary" />
              </div>
              <div className="grid gap-2">
                <div className="flex items-center justify-between rounded-xl bg-white/70 px-3 py-2 text-xs">
                  <span className="text-muted-foreground">发布阻断</span>
                  <span className="font-semibold text-foreground">{dataSafetyQ.data?.releaseBlocked ? "是" : "否"}</span>
                </div>
                <div className="flex items-center justify-between rounded-xl bg-white/70 px-3 py-2 text-xs">
                  <span className="text-muted-foreground">待支付订单</span>
                  <span className="font-semibold text-foreground">{formatCompactNumber(pendingOrders)}</span>
                </div>
                <div className="flex items-center justify-between rounded-xl bg-white/70 px-3 py-2 text-xs">
                  <span className="text-muted-foreground">活跃用户占比</span>
                  <span className="font-semibold text-foreground">{activeRate}</span>
                </div>
              </div>
            </div>
          </div>
        </section>

        <AdminNav />
      </div>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricTile
          icon={UsersRound}
          label="注册用户"
          value={overview ? formatCompactNumber(overview.users) : "0"}
          detail={`活跃账号 ${overview ? formatCompactNumber(overview.activeUsers) : "0"} 个，活跃率 ${activeRate}。`}
          tone="accent"
        />
        <MetricTile
          icon={BookOpenCheck}
          label="学习转化"
          value={learningRate}
          detail={`${overview ? formatCompactNumber(overview.studyUsers) : "0"} 个账号已有学习同步，近 7 日留存 ${recentLearningRate}。`}
        />
        <MetricTile
          icon={Activity}
          label="有效学习"
          value={overview ? formatDurationCompact(overview.effectiveStudyMs) : "0m"}
          detail={`内容接触 ${overview ? formatDurationCompact(overview.watchMs) : "0m"}，复习 ${overview ? formatDurationCompact(overview.reviewMs) : "0m"}。`}
        />
        <MetricTile
          icon={CreditCard}
          label="会员收入"
          value={paidAmount}
          detail={`${membership ? formatCompactNumber(membership.activeMemberships) : "0"} 个有效会员，${membership ? formatCompactNumber(membership.paidOrders) : "0"} 笔已支付订单。`}
          tone={pendingOrders > 0 ? "warning" : "default"}
        />
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.72fr)]">
        <Card>
          <CardHeader>
            <CardTitle>平台治理</CardTitle>
            <CardDescription>把后台入口按当前系统职责重新收拢：会员运营、用户权限、数据安全巡检各司其职。</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <ActionTile
              icon={CreditCard}
              title="会员运营"
              detail="查看订单、邀请、优惠券、佣金和微信提现，处理支付同步、退款和提现异常。"
              to="/admin/membership"
              action="进入会员后台"
            />
            <ActionTile
              icon={UserRoundCog}
              title="用户与权限"
              detail="按邮箱、昵称、UID、状态和角色筛选用户，并处理账号状态与管理员授权。"
              to="/admin/users"
              action="进入用户后台"
            />
            <div className="theme-soft-surface flex min-h-[8.5rem] flex-col justify-between p-4">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[color:var(--theme-icon-bg)] text-[color:var(--theme-icon-text)]">
                  <DatabaseBackup className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-semibold text-foreground">数据安全状态</div>
                  <p className="mt-1 text-xs leading-5 text-muted-foreground">
                    {dataSafety.detail}
                    {dataSafetyQ.data ? ` 受保护数据类 ${dataSafetyQ.data.protectedClasses.length} 项。` : ""}
                  </p>
                </div>
              </div>
              <StatusPill tone={dataSafety.tone}>{dataSafety.label}</StatusPill>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>风险巡检</CardTitle>
            <CardDescription>这里先给出后台最该优先看的信号，避免总览页被长列表淹没。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <RiskItem
              icon={dataSafetyQ.data?.releaseBlocked ? ShieldAlert : ShieldCheck}
              title={dataSafetyQ.data?.releaseBlocked ? "数据安全阻断发布" : "数据安全可继续观察"}
              detail={
                dataSafetyQ.error
                  ? `读取失败：${formatApiError(dataSafetyQ.error)}`
                  : dataSafetyQ.data
                    ? `${dataSafety.detail} 当前发现 ${dataSafetyFindingCount} 条。`
                    : "正在读取数据安全状态。"
              }
              tone={dataSafety.tone}
            />
            <RiskItem
              icon={WalletCards}
              title={pendingOrders > 0 ? "存在待支付订单" : "待支付订单无积压"}
              detail={
                membershipQ.error
                  ? `会员概览读取失败：${formatApiError(membershipQ.error)}`
                  : `当前待支付订单 ${formatCompactNumber(pendingOrders)} 笔，可在会员运营页继续筛选处理。`
              }
              tone={pendingOrders > 0 ? "warning" : "accent"}
            />
            <RiskItem
              icon={payoutQueueCent > 0 ? AlertTriangle : CheckCircle2}
              title={payoutQueueCent > 0 ? "佣金提现需要复核" : "佣金提现队列平稳"}
              detail={
                membershipQ.error
                  ? "暂时无法读取提现队列。"
                  : `可提现和预留中的佣金合计 ${formatMoneyCent(payoutQueueCent)}。`
              }
              tone={payoutQueueCent > 0 ? "warning" : "accent"}
            />
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-6 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>数据安全状态</CardTitle>
            <CardDescription>
              {dataSafetyQ.data
                ? `当前状态：${dataSafetyQ.data.state}，阻断发布：${dataSafetyQ.data.releaseBlocked ? "是" : "否"}`
                : dataSafetyQ.isLoading
                  ? "正在读取数据安全状态"
                  : "暂时无法读取数据安全状态"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
            {dataSafetyQ.data?.findings.length ? (
              dataSafetyQ.data.findings.slice(0, 4).map((finding) => (
                <div key={`${finding.code}-${finding.expectedLocation}`} className="theme-soft-surface p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusPill tone={finding.severity === "blocking" ? "danger" : finding.severity === "warning" ? "warning" : "default"}>
                      {finding.severity}
                    </StatusPill>
                    <span className="text-xs font-semibold text-foreground">{finding.code}</span>
                  </div>
                  <div className="mt-2 text-xs leading-5 text-muted-foreground">{finding.message}</div>
                </div>
              ))
            ) : (
              <div className="theme-soft-surface p-4">
                暂无阻断级数据安全发现。后台会每 60 秒刷新一次，用于提醒运维和发布前检查。
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>最近后台操作</CardTitle>
            <CardDescription>保留最近的管理员操作轨迹，方便回溯谁在什么时间处理了哪些内容。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {activityQ.error ? <ErrorNotice title="操作日志加载失败" message={formatApiError(activityQ.error)} /> : null}
            {!activityQ.error && activityQ.isLoading ? <LoadingNotice title="正在加载操作日志" message="后台正在同步最近的管理员操作记录。" /> : null}
            {!activityQ.error && !activityQ.isLoading && (activityQ.data?.length ?? 0) === 0 ? (
              <ContentEmptyState title="还没有后台操作记录" message="等管理员执行用户、会员或其他后台动作后，这里会自动显示。" />
            ) : null}

            {activityQ.data?.map((item) => (
              <div key={item.logId} className="theme-soft-surface p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <History className="h-4 w-4 text-primary" />
                  <div className="text-sm font-semibold text-foreground">{item.actorNickname}</div>
                  <StatusPill>{item.actionType}</StatusPill>
                  <span className="text-xs text-muted-foreground">{formatDateTime(item.createdAt)}</span>
                </div>
                <div className="mt-2 text-xs text-muted-foreground">
                  目标：{item.targetKind} · {item.targetId}
                </div>
                <p className="mt-3 text-sm leading-6 text-muted-foreground">{item.summary}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </section>
    </div>
  )
}

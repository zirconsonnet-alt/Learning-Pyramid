import { type ComponentPropsWithoutRef, type ReactNode } from "react"
import { CircleDashed, type LucideIcon } from "lucide-react"

import { CardDescription, CardTitle } from "@/ui/components/ui/card"
import { cn } from "@/ui/utils"
import { dashboardToneClasses, dashboardTonePillClasses, type DashboardTone } from "@/views/system/components/dashboardTheme"

function buildSparklinePath(values: number[], width = 220, height = 52) {
  if (!values.length) return ""
  const max = Math.max(...values, 1)
  const min = Math.min(...values, 0)
  const span = Math.max(1, max - min)
  return values
    .map((value, index) => {
      const x = values.length === 1 ? width / 2 : (index / (values.length - 1)) * width
      const y = height - ((value - min) / span) * height
      return `${index === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`
    })
    .join(" ")
}

export function TrendSparkline({ values, stroke }: { values: number[]; stroke: string }) {
  const path = buildSparklinePath(values)
  if (!path) return <div className="h-[52px] rounded-xl border border-dashed bg-white/60" />
  return (
    <svg viewBox="0 0 220 52" className="h-[52px] w-full overflow-visible rounded-xl border bg-white/70 p-2">
      <path d={path} fill="none" stroke={stroke} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function MetaChip({
  icon: Icon,
  strong = false,
  children,
  className,
}: {
  icon?: LucideIcon
  strong?: boolean
  children: ReactNode
  className?: string
}) {
  return (
    <span className={cn(strong ? "theme-meta-strong" : "theme-meta", "gap-1.5", className)}>
      {Icon ? <Icon className="size-3.5" /> : null}
      {children}
    </span>
  )
}

export function TonePill({
  tone = "slate",
  children,
  className,
}: {
  tone?: DashboardTone
  children: ReactNode
  className?: string
}) {
  return <span className={cn("inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium", dashboardTonePillClasses(tone), className)}>{children}</span>
}

export function SectionHeader({
  icon: Icon,
  eyebrow,
  title,
  description,
  actions,
}: {
  icon: LucideIcon
  eyebrow: string
  title: string
  description: string
  actions?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="flex min-w-0 items-start gap-3">
        <div className="mt-0.5 rounded-2xl bg-[#eef4ff] p-2.5 text-primary">
          <Icon className="size-4.5" />
        </div>
        <div className="min-w-0 space-y-1">
          <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">{eyebrow}</div>
          <CardTitle className="text-lg">{title}</CardTitle>
          <CardDescription className="max-w-3xl leading-6">{description}</CardDescription>
        </div>
      </div>
      {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
    </div>
  )
}

export function SystemBoard({
  eyebrow,
  title,
  description,
  tone = "slate",
  headerRight,
  children,
  className,
  bodyClassName,
}: {
  eyebrow?: string
  title: string
  description?: ReactNode
  tone?: DashboardTone
  headerRight?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
}) {
  const styles = dashboardToneClasses(tone)
  return (
    <div className={cn("rounded-[1.15rem] border p-4", styles.panel, className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          {eyebrow ? <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">{eyebrow}</div> : null}
          <div className={cn("text-sm font-medium text-slate-950", eyebrow && "mt-1")}>{title}</div>
          {description ? <div className="mt-1 text-xs leading-5 text-slate-600">{description}</div> : null}
        </div>
        {headerRight ? <div className="shrink-0">{headerRight}</div> : null}
      </div>
      <div className={cn("mt-4", bodyClassName)}>{children}</div>
    </div>
  )
}

export function ControlDeck({
  eyebrow = "当前重点",
  title,
  description,
  badge,
  tone = "slate",
  children,
  className,
  bodyClassName,
}: {
  eyebrow?: string
  title: string
  description?: ReactNode
  badge?: ReactNode
  tone?: DashboardTone
  children: ReactNode
  className?: string
  bodyClassName?: string
}) {
  return (
    <SystemBoard
      eyebrow={eyebrow}
      title={title}
      description={description}
      tone={tone}
      headerRight={badge}
      className={className}
      bodyClassName={bodyClassName}
    >
      {children}
    </SystemBoard>
  )
}

export function WatchlistPanel({
  title,
  description,
  tone = "slate",
  children,
  className,
  bodyClassName,
}: {
  title: string
  description?: ReactNode
  tone?: DashboardTone
  children: ReactNode
  className?: string
  bodyClassName?: string
}) {
  return (
    <SystemBoard title={title} description={description} tone={tone} className={className} bodyClassName={bodyClassName}>
      {children}
    </SystemBoard>
  )
}

export function StatusSidebar({
  eyebrow,
  title,
  badge,
  children,
  className,
  bodyClassName,
}: {
  eyebrow: string
  title: string
  badge?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
}) {
  return (
    <div className={cn("theme-status-surface p-5 sm:p-6", className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">{eyebrow}</div>
          <div className="text-xl font-semibold text-slate-950">{title}</div>
        </div>
        {badge ? <div className="flex flex-wrap items-center gap-2">{badge}</div> : null}
      </div>
      <div className={cn("mt-4 flex flex-col gap-4", bodyClassName)}>{children}</div>
    </div>
  )
}

export function BoardEntryCard({
  title,
  meta,
  headerRight,
  tone = "slate",
  children,
  className,
  bodyClassName,
}: {
  title: ReactNode
  meta?: ReactNode
  headerRight?: ReactNode
  tone?: DashboardTone
  children?: ReactNode
  className?: string
  bodyClassName?: string
}) {
  const styles = dashboardToneClasses(tone)
  return (
    <div className={cn("rounded-[1.25rem] border p-4 shadow-[0_16px_36px_-30px_rgba(15,23,42,0.18)]", styles.panel, className)}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-950">{title}</div>
          {meta ? <div className="mt-2 flex flex-wrap gap-2">{meta}</div> : null}
        </div>
        {headerRight ? <div className="shrink-0">{headerRight}</div> : null}
      </div>
      {children ? <div className={cn("mt-3", bodyClassName)}>{children}</div> : null}
    </div>
  )
}

export function EntryNote({
  children,
  tone = "slate",
  className,
}: {
  children: ReactNode
  tone?: DashboardTone
  className?: string
}) {
  const styles = dashboardToneClasses(tone)
  return <div className={cn("rounded-[1rem] border p-3 text-xs leading-5 text-slate-700", styles.panel, className)}>{children}</div>
}

export function SelectableTileButton({
  title,
  description,
  detail,
  selected = false,
  className,
  type,
  ...props
}: {
  title: ReactNode
  description?: ReactNode
  detail?: ReactNode
  selected?: boolean
  className?: string
} & ComponentPropsWithoutRef<"button">) {
  return (
    <button
      type={type ?? "button"}
      className={cn(
        "rounded-[1rem] border px-3 py-2 text-left text-xs transition-all duration-200",
        selected
          ? "border-primary/20 bg-primary/5 text-primary ring-1 ring-primary/10"
          : "border-border/70 bg-muted/15 text-[#4b5d75] hover:border-primary/15 hover:bg-primary/5 hover:text-primary",
        className,
      )}
      {...props}
    >
      <div className={cn("font-medium", selected ? "text-primary" : "text-slate-900")}>{title}</div>
      {description ? <div className="mt-1 leading-5">{description}</div> : null}
      {detail ? <div className="mt-1 leading-5">{detail}</div> : null}
    </button>
  )
}

export function MetricTile({
  icon: Icon,
  label,
  value,
  detail,
  tone = "slate",
  className,
}: {
  icon: LucideIcon
  label: string
  value: ReactNode
  detail?: ReactNode
  tone?: DashboardTone
  className?: string
}) {
  const styles = dashboardToneClasses(tone)
  return (
    <div className={cn("rounded-[1.35rem] border p-4 shadow-[0_18px_40px_-30px_rgba(15,23,42,0.18)]", styles.panel, className)}>
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">{label}</div>
          <div className="text-2xl font-semibold tracking-tight text-slate-950">{value}</div>
        </div>
        <div className={cn("rounded-2xl p-2.5", styles.icon)}>
          <Icon className="size-4.5" />
        </div>
      </div>
      {detail ? <div className="mt-3 text-xs leading-5 text-slate-600">{detail}</div> : null}
    </div>
  )
}

export function CompactMetric({
  label,
  value,
  detail,
  tone = "slate",
}: {
  label: string
  value: ReactNode
  detail?: ReactNode
  tone?: DashboardTone
}) {
  const styles = dashboardToneClasses(tone)
  return (
    <div className={cn("rounded-[1.1rem] border p-4", styles.panel)}>
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className="mt-2 text-lg font-semibold text-slate-950">{value}</div>
      {detail ? <div className="mt-1 text-xs leading-5 text-slate-600">{detail}</div> : null}
    </div>
  )
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-3 rounded-[1.15rem] border border-dashed border-border/80 bg-white/70 p-5 text-sm text-muted-foreground">
      <div className="rounded-2xl bg-slate-100 p-2 text-slate-500">
        <CircleDashed className="size-4" />
      </div>
      <span>{message}</span>
    </div>
  )
}

export function NarrativePanel({
  icon: Icon,
  title,
  description,
  tone = "slate",
}: {
  icon: LucideIcon
  title: string
  description: string
  tone?: DashboardTone
}) {
  const styles = dashboardToneClasses(tone)
  return (
    <div className={cn("flex items-start gap-3 rounded-[1.15rem] border p-4", styles.panel)}>
      <div className={cn("rounded-2xl p-2.5", styles.icon)}>
        <Icon className="size-4.5" />
      </div>
      <div className="min-w-0">
        <div className="text-sm font-medium text-slate-950">{title}</div>
        <div className="mt-1 text-xs leading-5 text-slate-600">{description}</div>
      </div>
    </div>
  )
}

export function OpsSignalTile({
  icon: Icon,
  label,
  value,
  detail,
  tone = "slate",
  className,
}: {
  icon: LucideIcon
  label: string
  value: ReactNode
  detail: ReactNode
  tone?: DashboardTone
  className?: string
}) {
  const styles = dashboardToneClasses(tone)
  return (
    <div className={cn("rounded-[1.15rem] border p-4", styles.panel, className)}>
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</div>
          <div className="text-lg font-semibold text-slate-950">{value}</div>
        </div>
        <div className={cn("rounded-2xl p-2.5", styles.icon)}>
          <Icon className="size-4.5" />
        </div>
      </div>
      <div className="mt-3 text-xs leading-5 text-slate-600">{detail}</div>
    </div>
  )
}

export function WatchlistItem({
  title,
  detail,
  tone = "slate",
  className,
}: {
  title: string
  detail: ReactNode
  tone?: DashboardTone
  className?: string
}) {
  const styles = dashboardToneClasses(tone)
  return (
    <div className={cn("rounded-[1rem] border px-3 py-3", styles.panel, className)}>
      <div className="text-sm font-medium text-slate-950">{title}</div>
      <div className="mt-1 text-xs leading-5 text-slate-600">{detail}</div>
    </div>
  )
}

export function StatusField({
  label,
  value,
  emphasize = false,
}: {
  label: string
  value: ReactNode
  emphasize?: boolean
}) {
  return (
    <div className="rounded-[1rem] border border-slate-200/80 bg-white/92 p-3">
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <div className={cn("mt-2 text-sm text-slate-700", emphasize && "font-semibold text-slate-950")}>{value}</div>
    </div>
  )
}

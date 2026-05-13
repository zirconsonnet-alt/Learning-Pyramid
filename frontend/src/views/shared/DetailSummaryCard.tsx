import type { ReactNode } from "react"
import type { LucideIcon } from "lucide-react"

import { Card, CardContent, CardDescription, CardHeader } from "@/ui/components/ui/card"

type SummaryItem = {
  label: string
  value: ReactNode
}

export function DetailSummaryTitle({ icon: Icon, title }: { icon: LucideIcon; title: ReactNode }) {
  return (
    <div className="space-y-4">
      <div className="flex min-w-0 items-center gap-3">
        <div
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] text-primary shadow-[var(--theme-soft-shadow)]"
          data-testid="detail-summary-title-icon"
        >
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0">{title}</div>
      </div>
      <div className="h-px bg-[color:var(--theme-soft-border)]" data-testid="detail-summary-title-divider" />
    </div>
  )
}

export function DetailSummaryHeading({ icon, title }: { icon: LucideIcon; title: string }) {
  return (
    <DetailSummaryTitle
      icon={icon}
      title={<h1 className="truncate text-lg font-semibold text-foreground">{title}</h1>}
    />
  )
}

export function DetailSummaryCard({
  description,
  header,
  icon,
  items,
  title,
}: {
  description?: ReactNode
  header?: ReactNode
  icon?: LucideIcon
  items: SummaryItem[]
  title?: string
}) {
  return (
    <Card data-testid="detail-summary-card">
      <CardHeader className="pb-3">
        {header ?? (icon && title ? <DetailSummaryHeading icon={icon} title={title} /> : null)}
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-3">
          {items.map((item) => (
            <div
              key={item.label}
              className="min-w-[10rem] flex-1 rounded-xl border border-[#dbe4ee] bg-[#f8fafc] px-4 py-3 shadow-[0_10px_24px_-24px_rgba(15,23,42,0.6)]"
            >
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#64748b]">{item.label}</div>
              <div className="mt-1.5 break-words text-sm font-semibold text-slate-900">{item.value}</div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

import { CircleAlert, CircleDashed, LoaderCircle, type LucideIcon } from "lucide-react"
import { type ReactNode } from "react"

import { cn } from "@/ui/utils"

type ContentNoticeTone = "neutral" | "info" | "danger"

function contentNoticeToneClasses(tone: ContentNoticeTone) {
  if (tone === "info") {
    return {
      panel: "border-sky-200/80 bg-sky-50/70",
      icon: "bg-sky-100 text-sky-700",
    }
  }
  if (tone === "danger") {
    return {
      panel: "border-destructive/20 bg-destructive/5",
      icon: "bg-destructive/10 text-destructive",
    }
  }
  return {
    panel: "border-border/80 bg-muted/15",
    icon: "bg-slate-100 text-slate-500",
  }
}

export function ContentNotice({
  title,
  message,
  icon: Icon = CircleDashed,
  tone = "neutral",
  action,
  className,
  iconClassName,
}: {
  title: string
  message: string
  icon?: LucideIcon
  tone?: ContentNoticeTone
  action?: ReactNode
  className?: string
  iconClassName?: string
}) {
  const toneClasses = contentNoticeToneClasses(tone)
  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-[1rem] border px-4 py-4",
        toneClasses.panel,
        className,
      )}
    >
      <div className={cn("rounded-2xl p-2", toneClasses.icon)}>
        <Icon className={cn("h-4 w-4", iconClassName)} />
      </div>
      <div className="min-w-0 space-y-1">
        <p className="text-sm font-medium text-foreground">{title}</p>
        <p className="text-sm leading-6 text-muted-foreground">{message}</p>
        {action ? <div className="pt-1">{action}</div> : null}
      </div>
    </div>
  )
}

export function LoadingNotice({
  title = "正在加载",
  message = "正在准备当前视图内容。",
  className,
}: {
  title?: string
  message?: string
  className?: string
}) {
  return (
    <ContentNotice
      title={title}
      message={message}
      icon={LoaderCircle}
      tone="info"
      iconClassName="animate-spin"
      className={className}
    />
  )
}

export function ErrorNotice({
  title = "加载失败",
  message,
  className,
  action,
}: {
  title?: string
  message: string
  className?: string
  action?: ReactNode
}) {
  return (
    <ContentNotice
      title={title}
      message={message}
      icon={CircleAlert}
      tone="danger"
      className={className}
      action={action}
    />
  )
}

export function ContentEmptyState({
  title,
  message,
  icon: Icon = CircleDashed,
  className,
}: {
  title: string
  message: string
  icon?: LucideIcon
  className?: string
}) {
  return (
    <ContentNotice title={title} message={message} icon={Icon} className={cn("border-dashed", className)} />
  )
}

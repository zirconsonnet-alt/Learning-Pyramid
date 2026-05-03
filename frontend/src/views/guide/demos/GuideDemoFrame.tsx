import type { ReactNode } from "react"
import { AlertTriangle } from "lucide-react"

import { cn } from "@/ui/utils"

export type GuideDemoFallbackReason = "invalid-directive" | "unknown-scene" | "unsupported-state" | "unsupported-highlight"

export type GuideDemoFrameProps = {
  title: string
  caption?: string
  stateLabel?: string
  stateDescription?: string
  children?: ReactNode
  fallbackReason?: GuideDemoFallbackReason
  maintainerHint?: string
}

const fallbackMessages: Record<GuideDemoFallbackReason, string> = {
  "invalid-directive": "这段指南场景配置不完整，暂时无法显示。",
  "unknown-scene": "这个指南场景暂时不可用，正文说明仍可继续阅读。",
  "unsupported-state": "这个指南场景状态暂时不可用，正文说明仍可继续阅读。",
  "unsupported-highlight": "这个指南场景可以显示，但当前高亮目标已降级。",
}

export function GuideDemoFrame({
  title,
  caption,
  stateLabel,
  stateDescription,
  children,
  fallbackReason,
  maintainerHint,
}: GuideDemoFrameProps) {
  const isBlockingFallback = fallbackReason && fallbackReason !== "unsupported-highlight"

  return (
    <section className="overflow-hidden rounded-[1.1rem] border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-soft-bg)] shadow-[var(--theme-soft-shadow)]">
      <div className="border-b border-[color:var(--theme-soft-border)] px-4 py-3 sm:px-5">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="text-base font-semibold text-foreground">{title}</div>
            {stateLabel ? <div className="mt-1 text-xs leading-5 text-[color:var(--theme-subtle-text)]">{stateLabel}</div> : null}
          </div>
          {fallbackReason ? (
            <div className="inline-flex w-fit items-center gap-1.5 rounded-lg border border-[color:var(--theme-warm-border)] bg-[color:var(--theme-warm-bg)] px-2.5 py-1 text-xs font-medium text-[color:var(--theme-warm-text)]">
              <AlertTriangle className="h-3.5 w-3.5" />
              场景提示
            </div>
          ) : null}
        </div>
        {stateDescription ? <p className="mt-2 text-sm leading-6 text-[color:var(--theme-subtle-text)]">{stateDescription}</p> : null}
      </div>

      <div className={cn("px-4 py-4 sm:px-5", isBlockingFallback ? "bg-[color:var(--theme-subtle-bg)]" : "")}>
        {isBlockingFallback ? (
          <div className="rounded-lg border border-dashed border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] px-4 py-5 text-sm leading-6 text-[color:var(--theme-subtle-text)]">
            {fallbackMessages[fallbackReason]}
          </div>
        ) : (
          children
        )}
      </div>

      {fallbackReason === "unsupported-highlight" || caption || maintainerHint ? (
        <div className="space-y-2 border-t border-[color:var(--theme-soft-border)] px-4 py-3 text-sm leading-6 text-[color:var(--theme-subtle-text)] sm:px-5">
          {fallbackReason === "unsupported-highlight" ? <p>{fallbackMessages[fallbackReason]}</p> : null}
          {caption ? <p>{caption}</p> : null}
          {maintainerHint ? <p className="text-xs leading-5">维护提示：{maintainerHint}</p> : null}
        </div>
      ) : null}
    </section>
  )
}

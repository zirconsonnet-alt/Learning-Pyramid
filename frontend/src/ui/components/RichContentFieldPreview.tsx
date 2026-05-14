import { useState } from "react"

import { richContentHasMeaning, type RichContent } from "@/ui/api/richContent"
import { RichContentRenderer } from "@/ui/components/RichContentRenderer"
import { cn } from "@/ui/utils"

export function RichContentFieldPreview({
  label,
  subjectId,
  projectId,
  value,
  labelClassName,
  previewClassName,
}: {
  label: string
  subjectId: string
  projectId: string
  value: RichContent
  labelClassName?: string
  previewClassName?: string
}) {
  const [isOpen, setIsOpen] = useState(false)
  const hasContent = richContentHasMeaning(value)

  return (
    <div className={cn("relative mb-2 flex items-center gap-2", labelClassName)}>
      <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">{label}</div>
      <button
        type="button"
        aria-label={`${label}预览`}
        onMouseEnter={() => setIsOpen(true)}
        onMouseLeave={() => setIsOpen(false)}
        onFocus={() => setIsOpen(true)}
        onBlur={() => setIsOpen(false)}
        className="rounded-md px-1.5 py-0.5 text-[11px] font-medium tracking-normal text-primary underline decoration-primary/30 underline-offset-4 transition hover:decoration-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      >
        预览
      </button>
      {isOpen ? (
        <div
          role="tooltip"
          aria-label={`${label}渲染预览`}
          className={cn(
            "absolute left-0 top-6 z-30 max-h-80 w-[min(32rem,calc(100vw-4rem))] overflow-auto rounded-xl border border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] p-4 text-left shadow-[0_18px_50px_-30px_rgba(15,23,42,0.45)]",
            previewClassName,
          )}
        >
          {hasContent ? (
            <RichContentRenderer
              subjectId={subjectId}
              projectId={projectId}
              value={value}
              className="space-y-3"
              textClassName="text-sm leading-6 text-foreground"
              imageClassName="max-h-56 rounded-xl border border-border/70 bg-muted/20 object-contain"
            />
          ) : (
            <div className="text-sm text-muted-foreground">暂无内容</div>
          )}
        </div>
      ) : null}
    </div>
  )
}

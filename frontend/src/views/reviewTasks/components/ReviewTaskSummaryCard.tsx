import { Link } from "react-router-dom"

import { Button } from "@/ui/components/ui/button"
import { formatReviewTaskReference } from "@/ui/displayIdentifiers"
import { cn } from "@/ui/utils"

type ReviewTaskField = {
  label: string
  value: string
}

export function ReviewTaskSummaryCard({
  projectId,
  reviewTaskId,
  stateLabel,
  kicker,
  tag,
  statusText,
  fields,
  className,
}: {
  projectId: string
  reviewTaskId: string
  stateLabel: string
  kicker: string
  tag?: string
  statusText?: string
  fields: ReviewTaskField[]
  className?: string
}) {
  return (
    <div className={cn("rounded-md border p-3", className)}>
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-xs text-muted-foreground">{kicker}</div>
          <div className="mt-1 flex items-center gap-2">
            {tag ? <span className="rounded-full border px-2 py-0.5 text-xs">{tag}</span> : null}
            <Link
              className="text-xs font-medium text-primary hover:underline"
              to={`/p/${projectId}/review-tasks/${reviewTaskId}`}
            >
              {formatReviewTaskReference(reviewTaskId)}
            </Link>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {statusText ? <div className="text-xs text-muted-foreground">{statusText}</div> : null}
          <Button size="sm" variant="outline" asChild>
            <Link to={`/p/${projectId}/review-tasks/${reviewTaskId}`}>查看详情</Link>
          </Button>
        </div>
      </div>

      <div className="mt-2 grid gap-2 text-xs text-muted-foreground md:grid-cols-2 xl:grid-cols-4">
        <div>
          状态：<span className="text-foreground">{stateLabel}</span>
        </div>
        {fields.map((field) => (
          <div key={field.label}>
            {field.label}：<span className="text-foreground">{field.value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

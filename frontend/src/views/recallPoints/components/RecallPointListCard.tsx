import { Link } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { type RecallPoint } from "@/ui/api/review"
import { richContentToPlainText } from "@/ui/api/richContent"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

export function RecallPointListCard({
  description,
  error,
  isLoading,
  items,
  projectId,
  title = "复述点",
}: {
  description?: string
  error?: unknown
  isLoading?: boolean
  items: RecallPoint[]
  projectId: string
  title?: string
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent>
        {isLoading ? <p className="text-sm text-muted-foreground">加载中...</p> : null}
        {error ? <p className="text-sm text-destructive">{formatApiError(error)}</p> : null}
        {!isLoading && !error && items.length === 0 ? <p className="text-sm text-muted-foreground">暂无复述点。</p> : null}
        <div className="divide-y rounded-md border">
          {items.map((rp) => (
            <Link
              key={rp.recallPointId}
              to={`/p/${projectId}/recall-points/${rp.recallPointId}`}
              className="block px-4 py-3 hover:bg-accent/60"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="truncate font-medium">{richContentToPlainText(rp.question)}</div>
                  <div className="mt-1 truncate font-mono text-xs text-muted-foreground">{rp.recallPointId}</div>
                </div>
                <div className="shrink-0 text-right text-xs text-muted-foreground">
                  <div>{rp.anchor.instanceId}</div>
                  <div>{rp.anchor.position}</div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

import { useState } from "react"

import { ApiError } from "@/ui/api/http"
import type { Instance } from "@/ui/api/instances"
import { richContentToPlainText } from "@/ui/api/richContent"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { useCommitReviewTask, useReviewBundle } from "@/ui/queries/workbench"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function parseAnchorMs(position: string): number | null {
  const m = position.match(/^t=(\d+)$/)
  if (!m) return null
  const n = Number(m[1])
  return Number.isFinite(n) ? n : null
}

function msToClock(ms: number) {
  const totalSec = Math.floor(ms / 1000)
  const h = Math.floor(totalSec / 3600)
  const m = Math.floor((totalSec % 3600) / 60)
  const s = totalSec % 60
  const msPart = ms % 1000
  const hh = h > 0 ? `${h}:` : ""
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m)
  const ss = String(s).padStart(2, "0")
  return `${hh}${mm}:${ss}.${String(msPart).padStart(3, "0")}`
}

export function ReviewPane({
  projectId,
  headId,
  instances,
  onOpenAnchor,
}: {
  projectId: string
  headId: string
  instances: Instance[]
  onOpenAnchor?: (a: { instanceId: string; position: string }) => void
}) {
  const { reviewTaskQ, rangeQ, recallPointQs } = useReviewBundle(projectId, headId)
  const commit = useCommitReviewTask(projectId)

  const [answers, setAnswers] = useState<Record<string, 0 | 1>>({})
  const [showAnswer, setShowAnswer] = useState<Record<string, boolean>>({})

  const loading =
    reviewTaskQ.isLoading ||
    rangeQ.isLoading ||
    recallPointQs.some((q) => q.isLoading) ||
    !reviewTaskQ.data ||
    !rangeQ.data
  const error = reviewTaskQ.error || rangeQ.error || recallPointQs.find((q) => q.error)?.error

  async function onSubmit() {
    if (!rangeQ.data) return
    const ids = rangeQ.data.recallPointIds
    const canRecall = ids.map((id) => (answers[id] ?? null))
    if (canRecall.some((v) => v === null)) return
    await commit.mutateAsync({ reviewTaskId: headId, canRecall: canRecall as number[] })
  }

  return (
    <Card className="theme-card-main">
      <CardHeader className="theme-card-header flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle>复习</CardTitle>
        {rangeQ.data ? <div className="theme-meta">{rangeQ.data.recallPointIds.length} 题</div> : null}
      </CardHeader>
      <CardContent className="space-y-4 pt-5">
        {loading ? <p className="text-sm text-muted-foreground">加载复习内容中...</p> : null}
        {error ? <p className="text-sm text-destructive">{formatApiError(error)}</p> : null}

        {rangeQ.data ? (
          <div className="space-y-3">
            {rangeQ.data.recallPointIds.map((rpId) => {
              const rp = recallPointQs.find((q) => q.data?.recallPointId === rpId)?.data
              if (!rp) return null
              const chosen = answers[rpId]
              const show = showAnswer[rpId] ?? false
              const inst = instances.find((i) => i.instanceId === rp.anchor.instanceId) ?? null
              const ms = parseAnchorMs(rp.anchor.position)
              return (
                <div key={rpId} className="theme-status-surface rounded-[1.2rem] border border-border/70 p-4">
                  <div className="text-sm font-medium">Q：{richContentToPlainText(rp.question)}</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    锚点：{inst ? inst.materialDisplayName : rp.anchor.instanceId} /{" "}
                    {ms === null ? rp.anchor.position : msToClock(ms)}
                  </div>
                  {onOpenAnchor ? (
                    <div className="mt-2">
                      <Button variant="outline" size="sm" onClick={() => onOpenAnchor(rp.anchor)}>
                        在视频中打开
                      </Button>
                    </div>
                  ) : null}
                  <div className="mt-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="rounded-full"
                      onClick={() => setShowAnswer((s) => ({ ...s, [rpId]: !show }))}
                    >
                      {show ? "隐藏答案" : "显示答案"}
                    </Button>
                    {show ? (
                      <div className="theme-canvas mt-2 rounded-2xl border border-border/60 p-3 text-sm">
                        A：{richContentToPlainText(rp.answer)}
                      </div>
                    ) : null}
                  </div>
                  <div className="mt-3 flex gap-2">
                    <Button
                      variant={chosen === 1 ? "default" : "outline"}
                      size="sm"
                      onClick={() => setAnswers((s) => ({ ...s, [rpId]: 1 }))}
                    >
                      会
                    </Button>
                    <Button
                      variant={chosen === 0 ? "secondary" : "outline"}
                      size="sm"
                      onClick={() => setAnswers((s) => ({ ...s, [rpId]: 0 }))}
                    >
                      不会
                    </Button>
                  </div>
                </div>
              )
            })}
          </div>
        ) : null}

        {rangeQ.data ? (
          <div className="pt-2">
            <Button
              onClick={() => void onSubmit()}
              disabled={commit.isPending || rangeQ.data.recallPointIds.some((id) => answers[id] === undefined)}
            >
              {commit.isPending ? "提交中..." : "提交复习"}
            </Button>
            {commit.error ? <p className="mt-2 text-sm text-destructive">{formatApiError(commit.error)}</p> : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

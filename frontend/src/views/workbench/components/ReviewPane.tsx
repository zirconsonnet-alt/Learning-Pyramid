import { useEffect, useState } from "react"
import { ArrowUpRight, CheckCircle2, ClipboardCheck, Eye, EyeOff, Lightbulb, PlayCircle, Undo2 } from "lucide-react"
import { Link } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { richText } from "@/ui/api/richContent"
import type { Instance } from "@/ui/api/instances"
import { RichContentRenderer } from "@/ui/components/RichContentRenderer"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { formatInstanceReference } from "@/ui/displayIdentifiers"
import { useCommitReviewTask, useReviewBundle } from "@/ui/queries/workbench"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { cn } from "@/ui/utils"

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
  const hh = h > 0 ? `${h}:` : ""
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m)
  const ss = String(s).padStart(2, "0")
  return `${hh}${mm}:${ss}`
}

function simplifyMaterialName(value: string) {
  const normalized = value.trim()
  if (!normalized) return "材料待确认"
  const leaf = normalized.split("/").at(-1)?.split("\\").at(-1) ?? normalized
  return leaf.replace(/\.[a-z0-9]+$/i, "") || leaf
}

function formatAnchorLabel(instanceId: string, displayName: string | null | undefined, position: string) {
  const title = simplifyMaterialName(formatInstanceReference(instanceId, displayName))
  const ms = parseAnchorMs(position)
  return `${title} · ${ms === null ? position : msToClock(ms)}`
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
  const [insightDrafts, setInsightDrafts] = useState<Record<string, string>>({})
  const [showInsightEditor, setShowInsightEditor] = useState<Record<string, boolean>>({})

  useEffect(() => {
    setAnswers({})
    setShowAnswer({})
    setInsightDrafts({})
    setShowInsightEditor({})
  }, [headId])

  const loading =
    reviewTaskQ.isLoading ||
    rangeQ.isLoading ||
    recallPointQs.some((q) => q.isLoading) ||
    !reviewTaskQ.data ||
    !rangeQ.data
  const error = reviewTaskQ.error || rangeQ.error || recallPointQs.find((q) => q.error)?.error
  const recallPointIds = rangeQ.data?.recallPointIds ?? []
  const totalCount = recallPointIds.length
  const answeredCount = recallPointIds.filter((id) => answers[id] !== undefined).length
  const rememberedCount = recallPointIds.filter((id) => answers[id] === 1).length
  const forgottenCount = recallPointIds.filter((id) => answers[id] === 0).length
  const draftedInsightCount = recallPointIds.filter((id) => insightDrafts[id]?.trim()).length
  const completionPercent = totalCount > 0 ? Math.round((answeredCount / totalCount) * 100) : 0
  const canSubmit = totalCount > 0 && recallPointIds.every((id) => answers[id] !== undefined)

  function chooseAnswer(rpId: string, nextValue: 0 | 1) {
    setAnswers((state) => ({ ...state, [rpId]: nextValue }))
    if (nextValue === 0) {
      setShowAnswer((state) => ({ ...state, [rpId]: true }))
    }
  }

  function clearAnswer(rpId: string) {
    setAnswers((state) => {
      const next = { ...state }
      delete next[rpId]
      return next
    })
  }

  async function onSubmit() {
    if (!rangeQ.data) return
    const canRecall = rangeQ.data.recallPointIds.map((id) => answers[id])
    if (canRecall.some((value) => value === undefined)) return
    const appendedInsights = rangeQ.data.recallPointIds.flatMap((rpId) => {
      const text = insightDrafts[rpId]?.trim()
      return text ? [{ recallPointId: rpId, insight: richText(text) }] : []
    })

    try {
      await commit.mutateAsync({
        reviewTaskId: headId,
        canRecall: canRecall as number[],
        appendedInsights,
      })
      showSuccessFeedback(
        "复习结果已提交",
        `本轮已提交 ${totalCount} 题，其中记得 ${rememberedCount} 题，不记得 ${forgottenCount} 题${
          appendedInsights.length > 0 ? `，并追加了 ${appendedInsights.length} 条理解。` : "。"
        }`,
      )
    } catch (err) {
      showErrorFeedback("提交复习结果失败", formatApiError(err))
    }
  }

  return (
    <Card className="theme-card-main">
      <CardHeader className="theme-card-header flex-col gap-4 space-y-0 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-[#e2e8f0] bg-[#f5f7fa] text-primary">
            <ClipboardCheck className="h-5 w-5" />
          </div>
          <div className="space-y-1">
            <CardTitle>复习任务</CardTitle>
            <p className="text-sm text-muted-foreground">先主动回忆，再决定记得或不记得；需要时可补看答案、回到视频、追加理解。</p>
          </div>
        </div>

        <div className="min-w-[180px] space-y-2">
          <div className="flex items-center justify-between gap-3 text-sm">
            <span className="theme-meta">{totalCount} 题</span>
            <span className="font-medium text-slate-700">
              已完成 {answeredCount} / {totalCount}
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-[#e8edf4]">
            <div
              className="h-full rounded-full bg-primary transition-[width] duration-300"
              style={{ width: `${completionPercent}%` }}
            />
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 pt-5">
        {loading ? <p className="text-sm text-muted-foreground">加载复习内容中...</p> : null}
        {error ? <p className="text-sm text-destructive">{formatApiError(error)}</p> : null}

        {rangeQ.data ? (
          <div className="space-y-3">
            {rangeQ.data.recallPointIds.map((rpId, index) => {
              const rp = recallPointQs.find((q) => q.data?.recallPointId === rpId)?.data
              if (!rp) return null

              const chosen = answers[rpId]
              const isRemembered = chosen === 1
              const isForgotten = chosen === 0
              const answerVisible = showAnswer[rpId] ?? false
              const draftInsight = insightDrafts[rpId] ?? ""
              const hasDraftInsight = draftInsight.trim().length > 0
              const insightEditorVisible = showInsightEditor[rpId] || hasDraftInsight
              const inst = instances.find((i) => i.instanceId === rp.anchor.instanceId) ?? null
              const anchorLabel = formatAnchorLabel(rp.anchor.instanceId, inst?.materialDisplayName, rp.anchor.position)

              return (
                <div key={rpId} className="theme-status-surface rounded-[1.15rem] border border-[#e2e8ef] px-4 py-3">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                        <span>第 {index + 1} 题</span>
                        {isRemembered ? (
                          <span className="rounded-full bg-emerald-50 px-2 py-0.5 tracking-[0.08em] text-emerald-700">已标记为记得</span>
                        ) : null}
                        {isForgotten ? (
                          <span className="rounded-full bg-amber-50 px-2 py-0.5 tracking-[0.08em] text-amber-700">已标记为不记得</span>
                        ) : null}
                      </div>

                      <Link
                        to={`/p/${projectId}/recall-points/${rpId}`}
                        className="group mt-2 block rounded-2xl px-2 py-1 -mx-2 -my-1 transition hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                        title="打开复述点详情"
                      >
                        <div className="text-[15px] font-semibold leading-6 text-slate-900 transition group-hover:text-primary">
                          <RichContentRenderer projectId={projectId} value={rp.question} />
                        </div>
                        <div className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-primary/85">
                          查看复述点详情
                          <ArrowUpRight className="h-3.5 w-3.5" />
                        </div>
                      </Link>

                      <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                        <span className="rounded-full border border-[#dbe4ee] bg-white px-2.5 py-1 font-medium text-slate-600">{anchorLabel}</span>
                        {rp.insights.length > 0 ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 font-medium text-amber-700">
                            <Lightbulb className="h-3.5 w-3.5" />
                            已有 {rp.insights.length} 条理解
                          </span>
                        ) : null}
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 flex flex-wrap gap-2">
                    {onOpenAnchor ? (
                      <Button variant="outline" size="sm" className="rounded-full" onClick={() => onOpenAnchor(rp.anchor)}>
                        <PlayCircle className="h-4 w-4" />
                        回到视频
                      </Button>
                    ) : null}

                    <Button
                      variant="ghost"
                      size="sm"
                      className="rounded-full"
                      onClick={() => setShowAnswer((state) => ({ ...state, [rpId]: !answerVisible }))}
                    >
                      {answerVisible ? (
                        <>
                          <EyeOff className="h-4 w-4" />
                          收起答案
                        </>
                      ) : (
                        <>
                          <Eye className="h-4 w-4" />
                          查看答案
                        </>
                      )}
                    </Button>

                    <Button
                      variant="ghost"
                      size="sm"
                      className="rounded-full"
                      onClick={() =>
                        setShowInsightEditor((state) => ({
                          ...state,
                          [rpId]: !(state[rpId] || hasDraftInsight),
                        }))
                      }
                    >
                      <Lightbulb className="h-4 w-4" />
                      {insightEditorVisible ? "收起理解" : "追加理解"}
                    </Button>
                  </div>

                  {answerVisible ? (
                    <div className="theme-canvas mt-3 rounded-2xl border border-[#e2e8ef] p-3 text-sm">
                      <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">答案</div>
                      <RichContentRenderer projectId={projectId} value={rp.answer} />
                    </div>
                  ) : null}

                  {insightEditorVisible ? (
                    <div className="mt-3 rounded-2xl border border-[#e2e8ef] bg-white p-3">
                      <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">追加理解</div>
                      <textarea
                        value={draftInsight}
                        onChange={(event) =>
                          setInsightDrafts((state) => ({
                            ...state,
                            [rpId]: event.target.value,
                          }))
                        }
                        rows={3}
                        placeholder="补充这道复习点的新理解、易错点、联想线索或自己的话解释。"
                        className="w-full resize-y rounded-2xl border border-[#dbe4ee] bg-[#fbfdff] px-3 py-2 text-sm text-slate-700 outline-none transition placeholder:text-slate-400 focus:border-primary focus:ring-2 focus:ring-primary/15"
                      />
                      <div className="mt-2 text-xs text-muted-foreground">提交本轮复习时，这段内容会作为新的“理解”追加到对应复述点。</div>
                    </div>
                  ) : null}

                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    <Button
                      variant={isRemembered ? "default" : "outline"}
                      size="sm"
                      className={cn("min-w-[96px] rounded-full", isRemembered ? "bg-emerald-600 hover:bg-emerald-700" : "")}
                      onClick={() => chooseAnswer(rpId, 1)}
                    >
                      记得
                    </Button>
                    <Button
                      variant={isForgotten ? "secondary" : "outline"}
                      size="sm"
                      className={cn(
                        "min-w-[96px] rounded-full",
                        isForgotten ? "border-amber-200 bg-amber-50 text-amber-700 hover:bg-amber-100" : "",
                      )}
                      onClick={() => chooseAnswer(rpId, 0)}
                    >
                      不记得
                    </Button>
                    {chosen !== undefined ? (
                      <Button variant="ghost" size="sm" className="rounded-full text-muted-foreground" onClick={() => clearAnswer(rpId)}>
                        <Undo2 className="h-4 w-4" />
                        撤销选择
                      </Button>
                    ) : null}
                  </div>

                  {chosen !== undefined ? (
                    <div
                      className={cn(
                        "mt-3 flex items-center gap-2 rounded-2xl px-3 py-2 text-xs font-medium",
                        isRemembered ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700",
                      )}
                    >
                      <CheckCircle2 className="h-4 w-4" />
                      {isRemembered
                        ? "这题已标记为“记得”，可以继续下一题。"
                        : "这题已标记为“不记得”，建议先核对答案，再补一句自己的理解。"}
                    </div>
                  ) : null}
                </div>
              )
            })}
          </div>
        ) : null}

        {rangeQ.data ? (
          <div className="rounded-[1.2rem] border border-[#dfe7f0] bg-[#f8fbff] p-4">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="space-y-2 text-sm">
                <div className="font-semibold text-slate-900">本轮复习摘要</div>
                <div className="flex flex-wrap items-center gap-3 text-muted-foreground">
                  <span>记得 {rememberedCount} 题</span>
                  <span>不记得 {forgottenCount} 题</span>
                  <span>追加理解 {draftedInsightCount} 条</span>
                </div>
                {canSubmit ? (
                  <div className="flex items-center gap-2 text-emerald-700">
                    <CheckCircle2 className="h-4 w-4" />
                    当前题目都已完成选择，可以提交本轮复习。
                  </div>
                ) : (
                  <div className="text-muted-foreground">还有 {totalCount - answeredCount} 题未判断，完成后即可提交。</div>
                )}
              </div>

              <Button onClick={() => void onSubmit()} disabled={commit.isPending || !canSubmit} className="min-w-[140px]">
                {commit.isPending ? "提交中..." : "提交本轮复习"}
              </Button>
            </div>

            {commit.error ? <p className="mt-3 text-sm text-destructive">{formatApiError(commit.error)}</p> : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

import { ArrowRight, ChevronLeft } from "lucide-react"
import { Link, useParams, useSearchParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { RichContentRenderer } from "@/ui/components/RichContentRenderer"
import { ContentEmptyState, ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { formatInstanceReference, formatRecallPointReference } from "@/ui/displayIdentifiers"
import { useProject } from "@/ui/queries/projects"
import { useReviewRecommendations } from "@/ui/queries/reviewRecommendations"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function parseOffset(raw: string | null) {
  const n = Number(raw ?? "0")
  if (!Number.isFinite(n) || n < 0) return 0
  return Math.floor(n)
}

function formatDateTime(value: string | null) {
  if (!value) return "未复习"
  const dt = new Date(value)
  return Number.isNaN(dt.getTime()) ? value : dt.toLocaleString()
}

function formatReviewResult(value: "CAN_RECALL" | "CANNOT_RECALL" | null) {
  if (value === "CAN_RECALL") return "最近一次：会"
  if (value === "CANNOT_RECALL") return "最近一次：不会"
  return "还没有正式复习记录"
}

export function ReviewRecommendationsPage() {
  const { projectId } = useParams()
  const pid = projectId ?? ""
  const [searchParams, setSearchParams] = useSearchParams()
  const offset = parseOffset(searchParams.get("offset"))
  const reviewRecommendationsQ = useReviewRecommendations(pid, { offset })
  const { projectTitle } = useProject(pid)

  if (!pid) {
    return (
      <div className="space-y-4">
        <ContentNotice
          title="当前页面缺少项目上下文"
          message="当前链接缺少项目信息。请先返回项目列表，再重新进入推荐复习。"
          action={
            <Button asChild>
              <Link to="/projects">返回项目列表</Link>
            </Button>
          }
        />
      </div>
    )
  }

  const page = reviewRecommendationsQ.data
  const items = page?.items ?? []
  const startNumber = (page?.offset ?? offset) + 1
  const endNumber = page?.offset !== undefined ? page.offset + items.length : offset + items.length

  function jumpTo(nextOffset: number) {
    const next = new URLSearchParams(searchParams)
    if (nextOffset <= 0) {
      next.delete("offset")
    } else {
      next.set("offset", String(nextOffset))
    }
    setSearchParams(next)
    window.scrollTo({ top: 0, behavior: "smooth" })
  }

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">推荐复习</h1>
          <p className="text-sm text-muted-foreground">
            项目：<span className="font-medium text-foreground">{projectTitle}</span>
          </p>
          <p className="text-sm text-muted-foreground">这里只做只读复习浏览，不会生成复习任务，也不会写入新的会/不会结果。</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" asChild>
            <Link to={`/p/${pid}/workbench`}>返回工作台</Link>
          </Button>
          <Button variant="outline" onClick={() => void reviewRecommendationsQ.refetch()} disabled={reviewRecommendationsQ.isFetching}>
            {reviewRecommendationsQ.isFetching ? "刷新中..." : "刷新"}
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>本批推荐</CardTitle>
          <CardDescription>
            {page
              ? page.totalCount > 0
                ? `当前展示第 ${startNumber}-${endNumber} 条，共 ${page.totalCount} 条推荐复习。`
                : "当前还没有可展示的推荐复习。"
              : "按当前配置读取一批推荐复习复述点。"}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm text-muted-foreground">
            每批大小：<span className="font-medium text-foreground">{page?.limit ?? "-"}</span>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => jumpTo(Math.max(offset - (page?.limit ?? 20), 0))} disabled={offset <= 0 || reviewRecommendationsQ.isLoading}>
              上一批
            </Button>
            <Button onClick={() => jumpTo(page?.nextOffset ?? offset)} disabled={page?.nextOffset == null || reviewRecommendationsQ.isLoading}>
              继续推荐
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {reviewRecommendationsQ.isLoading ? <LoadingNotice title="正在加载推荐复习" message="正在根据复习历史和遗忘曲线计算当前批次。" /> : null}
      {reviewRecommendationsQ.error ? <ErrorNotice title="推荐复习加载失败" message={formatApiError(reviewRecommendationsQ.error)} /> : null}

      {!reviewRecommendationsQ.isLoading && !reviewRecommendationsQ.error && page && page.totalCount === 0 ? (
        <ContentEmptyState
          title="当前没有推荐复习"
          message="可能是项目里还没有足够的活跃复述点，或者当前推荐门槛配置把列表过滤掉了。"
        />
      ) : null}

      {!reviewRecommendationsQ.isLoading && !reviewRecommendationsQ.error && page && page.totalCount > 0 && items.length === 0 ? (
        <ContentEmptyState
          title="已经看到最后一批"
          message="当前偏移量已经超过推荐列表尾部了。你可以返回上一批，或者从头再看。"
        />
      ) : null}

      <div className="space-y-3">
        {items.map((item, index) => {
          const recallPoint = item.recallPoint
          return (
            <Card key={recallPoint.recallPointId}>
              <CardHeader className="pb-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-1">
                    <CardTitle className="text-base">{formatRecallPointReference(recallPoint.recallPointId)}</CardTitle>
                    <CardDescription>
                      排名 #{startNumber + index} · 推荐指数 {item.reviewRecommendationIndex.toFixed(1)} / 100 · 记忆强度 {(item.estimatedMemoryStrength * 100).toFixed(1)}%
                    </CardDescription>
                    <div className="text-xs text-muted-foreground">
                      {formatReviewResult(item.lastReviewResult)} · {formatDateTime(item.lastReviewedAt)} · 历史记录 {item.reviewCount} 条
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" asChild>
                      <Link to={`/p/${pid}/recall-points/${recallPoint.recallPointId}`}>
                        详情
                      </Link>
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="grid gap-4 lg:grid-cols-2">
                <div className="space-y-2 rounded-xl border bg-muted/20 p-4">
                  <div className="text-xs font-medium text-muted-foreground">问题</div>
                  <RichContentRenderer projectId={pid} value={recallPoint.question} />
                </div>
                <div className="space-y-2 rounded-xl border bg-muted/20 p-4">
                  <div className="text-xs font-medium text-muted-foreground">答案</div>
                  <RichContentRenderer projectId={pid} value={recallPoint.answer} />
                </div>
                <div className="text-xs text-muted-foreground lg:col-span-2">
                  {recallPoint.anchor ? (
                    <>
                      锚点：<span className="text-foreground">{formatInstanceReference(recallPoint.anchor.instanceId)}</span>
                      <span className="mx-1">·</span>
                      <span className="text-foreground">{recallPoint.anchor.position}</span>
                    </>
                  ) : (
                    <>锚点：<span className="text-foreground">未绑定锚点</span></>
                  )}
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {page && page.totalCount > 0 ? (
        <div className="flex items-center justify-between gap-3 rounded-xl border bg-muted/20 px-4 py-3 text-sm">
          <div className="text-muted-foreground">
            当前是只读推荐复习批次。真正会写入“会/不会”结果的，仍然只有正式复习任务页。
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => jumpTo(Math.max(offset - (page.limit ?? 20), 0))} disabled={offset <= 0}>
              <ChevronLeft className="h-4 w-4" />
              上一批
            </Button>
            <Button size="sm" onClick={() => jumpTo(page.nextOffset ?? offset)} disabled={page.nextOffset == null}>
              继续推荐
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}

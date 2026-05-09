import { ImageIcon, PlayCircle, Sparkles } from "lucide-react"
import { Link } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { type RecallPoint } from "@/ui/api/review"
import { richContentImageAssetIds, richContentToPlainText } from "@/ui/api/richContent"
import { ContentEmptyState, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { buildCurrentProjectPath } from "@/ui/projectPaths"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function formatInstanceLabel(instanceId: string | null | undefined, instanceTitleById?: Record<string, string>) {
  if (!instanceId) return "未绑定锚点"
  const title = instanceTitleById?.[instanceId]?.trim()
  return title || "关联内容"
}

function buildWorkbenchHref(projectId: string, instanceId: string, position: string) {
  const params = new URLSearchParams({ instanceId, position })
  return buildCurrentProjectPath(projectId, `/workbench?${params.toString()}`)
}

export function RecallPointListCard({
  description,
  error,
  headerAction,
  isLoading,
  items,
  instanceTitleById,
  projectId,
  title = "复述点",
}: {
  description?: string
  error?: unknown
  headerAction?: React.ReactNode
  isLoading?: boolean
  items: RecallPoint[]
  instanceTitleById?: Record<string, string>
  projectId: string
  title?: string
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <CardTitle>{title}</CardTitle>
            {description ? <CardDescription>{description}</CardDescription> : null}
          </div>
          {headerAction ? <div className="shrink-0">{headerAction}</div> : null}
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? <LoadingNotice title="正在加载复述点列表" message="正在整理这个节点下的复述点和锚点信息。" /> : null}
        {error ? <ErrorNotice title="复述点列表加载失败" message={formatApiError(error)} /> : null}
        {!isLoading && !error && items.length === 0 ? (
          <ContentEmptyState
            icon={Sparkles}
            title="这个节点还没有复述点"
            message="先在工作台录入复述点，或等待上游节点同步完成；完成后结果会显示在这里。"
          />
        ) : null}
        <div className="space-y-3">
          {items.map((rp, index) => {
            const questionPreview = richContentToPlainText(rp.question)
            const answerPreview = richContentToPlainText(rp.answer)
            const imageCount = richContentImageAssetIds(rp.question).length + richContentImageAssetIds(rp.answer).length
            const instanceLabel = formatInstanceLabel(rp.anchor?.instanceId, instanceTitleById)
            return (
              <div key={rp.recallPointId} className="rounded-[1rem] border border-[#dbe4ee] bg-[#fbfdff] p-4 shadow-[0_12px_28px_-28px_rgba(15,23,42,0.6)]">
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                  <div className="min-w-0 flex-1 space-y-3">
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="rounded-full bg-[#eef5ff] px-2.5 py-1 font-medium text-primary">第 {index + 1} 条</span>
                      <span className="rounded-full border border-[#dbe4ee] bg-[#f8fafc] px-2.5 py-1 font-medium text-slate-600">
                        {instanceLabel}
                      </span>
                      {imageCount > 0 ? (
                        <span className="inline-flex items-center gap-1 rounded-full border border-[#dbe4ee] bg-[#fffaf0] px-2.5 py-1 font-medium text-amber-700">
                          <ImageIcon className="h-3.5 w-3.5" />
                          {imageCount} 张图片
                        </span>
                      ) : null}
                      {rp.insights.length > 0 ? (
                        <span className="rounded-full border border-[#dbe4ee] bg-[#f8fafc] px-2.5 py-1 font-medium text-slate-600">
                          {rp.insights.length} 条理解
                        </span>
                      ) : null}
                    </div>

                    <div className="space-y-2 border-l-2 border-[#dbeafe] pl-4">
                      <div>
                        <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">问题</div>
                        <div className="text-[15px] font-semibold leading-6 text-slate-900">{questionPreview || "未填写问题"}</div>
                      </div>
                      <div>
                        <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">答案</div>
                        <div className="text-sm leading-6 text-slate-600">{answerPreview || "未填写答案"}</div>
                      </div>
                    </div>
                  </div>

                  <div className="flex shrink-0 flex-wrap gap-2 md:w-[11rem] md:flex-col md:items-stretch">
                    <Button size="sm" className="rounded-full md:w-full" asChild>
                      <Link to={buildCurrentProjectPath(projectId, `/recall-points/${rp.recallPointId}`)}>
                        查看详情
                      </Link>
                    </Button>
                    {rp.anchor ? (
                      <Button variant="outline" size="sm" className="rounded-full md:w-full" asChild>
                        <Link to={buildWorkbenchHref(projectId, rp.anchor.instanceId, rp.anchor.position)}>
                          <PlayCircle className="h-4 w-4" />
                          打开工作台
                        </Link>
                      </Button>
                    ) : null}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}

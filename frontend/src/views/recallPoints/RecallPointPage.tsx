import { ArrowLeft, PencilLine, Save, Sparkles, Trash2, X } from "lucide-react"
import { useMemo, useState, type ReactNode } from "react"
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import {
  appendImageBlock,
  removeImageBlockAt,
  richContentHasMeaning,
  setRichContentText,
  type RichContent,
} from "@/ui/api/richContent"
import { deleteRecallPoint, editRecallPoint, getRecallPoint, type RecallPoint } from "@/ui/api/review"
import { ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { RichContentEditor } from "@/ui/components/RichContentEditor"
import { RichContentRenderer } from "@/ui/components/RichContentRenderer"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { formatInstanceReference, formatRecallPointReference } from "@/ui/displayIdentifiers"
import { projectTypeRequiresAnchor } from "@/ui/projectTypes"
import { useProjectConfig } from "@/ui/queries/workbench"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { buildAiChatPath } from "@/views/ai/chatRouting"
import { ReviewProjectionCard } from "@/views/recallPoints/components/ReviewProjectionCard"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function parseAnchorMs(position: string): number | null {
  const match = position.match(/^t=(\d+)$/)
  if (!match) return null
  const value = Number(match[1])
  return Number.isFinite(value) ? value : null
}

function msToClock(ms: number) {
  const totalSeconds = Math.floor(ms / 1000)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  const hh = hours > 0 ? `${hours}:` : ""
  const mm = hours > 0 ? String(minutes).padStart(2, "0") : String(minutes)
  const ss = String(seconds).padStart(2, "0")
  return `${hh}${mm}:${ss}`
}

function formatAnchorPosition(position: string | null | undefined) {
  const normalized = position?.trim()
  if (!normalized) return "-"
  const ms = parseAnchorMs(normalized)
  return ms === null ? normalized : msToClock(ms)
}

function renderRichContentPreview(projectId: string, value: RichContent, emptyText: string) {
  return richContentHasMeaning(value) ? (
    <RichContentRenderer projectId={projectId} value={value} />
  ) : (
    <div className="text-sm leading-6 text-muted-foreground">{emptyText}</div>
  )
}

export function RecallPointPage() {
  const { projectId, recallPointId } = useParams()
  const pid = projectId ?? ""
  const rpid = recallPointId ?? ""
  const navigate = useNavigate()

  const qKey = useMemo(() => ["recallPoint", pid, rpid], [pid, rpid])
  const q = useQuery({
    queryKey: qKey,
    queryFn: () => getRecallPoint(pid, rpid),
    enabled: !!pid && !!rpid,
  })

  const recallPoint = q.data ?? null

  if (!pid || !rpid) {
    return (
      <div className="space-y-4">
        <ContentNotice
          title="当前页面缺少复述点上下文"
          message="当前链接缺少复述点信息。请返回上一页，或重新从复述点列表进入。"
          action={<Button onClick={() => navigate(-1)}>返回</Button>}
        />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {q.isLoading ? <LoadingNotice title="正在加载复述点" message="正在读取这条复述点的题面、答案和历史理解记录。" /> : null}
      {q.error ? <ErrorNotice title="复述点加载失败" message={formatApiError(q.error)} /> : null}
      {!q.isLoading && !q.error && !recallPoint ? (
        <ContentNotice
          title="未找到这条复述点"
          message="这条复述点可能已经被移除，或者当前链接里的 ID 已经过期。你可以返回上一页重新选择。"
          action={
            <Button variant="outline" onClick={() => navigate(-1)}>
              返回上一页
            </Button>
          }
        />
      ) : null}

      {recallPoint ? (
        <RecallPointDetailLayout
          key={`${recallPoint.recallPointId}:${q.dataUpdatedAt}`}
          projectId={pid}
          recallPointId={rpid}
          qKey={qKey}
          recallPoint={recallPoint}
        />
      ) : null}
    </div>
  )
}

function RecallPointDetailLayout({
  projectId,
  recallPointId,
  qKey,
  recallPoint,
}: {
  projectId: string
  recallPointId: string
  qKey: readonly string[]
  recallPoint: RecallPoint
}) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const projectConfigQ = useProjectConfig(projectId)
  const projectType = projectConfigQ.data?.projectType ?? "COURSE"
  const requiresAnchor = projectTypeRequiresAnchor(projectType)
  const [question, setQuestion] = useState<RichContent>(() => recallPoint.question)
  const [answer, setAnswer] = useState<RichContent>(() => recallPoint.answer)
  const [positionText, setPositionText] = useState(() => recallPoint.anchor?.position ?? "")
  const [editingAnchor, setEditingAnchor] = useState(false)
  const [editingContent, setEditingContent] = useState(false)
  const referenceRecallPointQs = useQueries({
    queries: recallPoint.references.map((referenceId) => ({
      queryKey: ["recallPoint", projectId, referenceId],
      queryFn: () => getRecallPoint(projectId, referenceId),
      enabled: !!projectId,
    })),
  })

  const deleteM = useMutation({
    mutationFn: () => deleteRecallPoint(projectId, recallPointId),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["recallPoint", projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPoints", projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPointSearch", projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPointsByInstance", projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPointsByTaskNode", projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPointsByObjectNode", projectId] }),
        qc.invalidateQueries({ queryKey: ["reviewRecommendations", projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPointReviewProjection", projectId] }),
      ])
      showSuccessFeedback("复述点已删除", "这条复述点已被标记为墓碑，并从当前内容视图中移除。")
      navigate(-1)
    },
    onError: (err) => {
      showErrorFeedback("删除复述点失败", formatApiError(err))
    },
  })

  const editM = useMutation({
    mutationFn: async () => {
      const pos = positionText.trim()
      if (!richContentHasMeaning(question) || !richContentHasMeaning(answer)) return
      if (requiresAnchor && (!recallPoint.anchor || !pos)) return
      await editRecallPoint(projectId, recallPointId, {
        question,
        answer,
        anchor: requiresAnchor && recallPoint.anchor ? { instanceId: recallPoint.anchor.instanceId, position: pos } : null,
      })
    },
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: qKey }),
        qc.invalidateQueries({ queryKey: ["recallPoints", projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPointSearch", projectId] }),
        qc.invalidateQueries({ queryKey: ["reviewRecommendations", projectId] }),
      ])
      showSuccessFeedback("复述点已保存", "复述点内容已经更新。")
    },
    onError: (err) => {
      showErrorFeedback("保存复述点失败", formatApiError(err))
    },
  })

  const canEdit = recallPoint.state === "ACTIVE" && !editM.isPending
  const canSave =
    recallPoint.state === "ACTIVE" &&
    richContentHasMeaning(question) &&
    richContentHasMeaning(answer) &&
    (!requiresAnchor || !!positionText.trim())

  function openAnchorEditor() {
    if (!canEdit || !requiresAnchor) return
    setEditingAnchor(true)
  }

  function cancelAnchorEditor() {
    setPositionText(recallPoint.anchor?.position ?? "")
    setEditingAnchor(false)
  }

  function openContentEditor() {
    if (!canEdit) return
    setEditingContent(true)
  }

  function cancelContentEditor() {
    setQuestion(recallPoint.question)
    setAnswer(recallPoint.answer)
    setEditingContent(false)
  }

  async function saveChanges() {
    await editM.mutateAsync()
    setEditingAnchor(false)
    setEditingContent(false)
  }

  const backAction = (
    <Button
      variant="ghost"
      size="sm"
      className="-ml-2 h-8 rounded-full px-2 text-[#60748c] hover:bg-[#f3f7fb] hover:text-foreground"
      onClick={() => navigate(-1)}
    >
      <ArrowLeft className="h-4 w-4" />
      返回
    </Button>
  )

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)] xl:items-start">
      <aside className="xl:sticky xl:top-28 xl:self-start">
        <div className="space-y-3">
          <RecallPointSummaryCard
            topAction={backAction}
            header={<h1 className="truncate text-lg font-semibold">复述点详情</h1>}
            description="元信息、锚点和复习状态集中在这里。"
            items={[
              { label: "当前引用", value: formatRecallPointReference(recallPointId) },
              {
                label: "内容实例",
                value: recallPoint.anchor ? formatInstanceReference(recallPoint.anchor.instanceId, undefined, "未关联内容实例") : "未绑定内容实例",
              },
              {
                label: "锚点",
                value:
                  requiresAnchor ? (
                    <button
                      type="button"
                      className="rounded-full px-2 py-1 text-sm font-semibold text-foreground transition hover:bg-primary/5 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      onClick={openAnchorEditor}
                      disabled={!canEdit}
                    >
                      {formatAnchorPosition(positionText)}
                    </button>
                  ) : (
                    "未绑定锚点"
                  ),
              },
            ]}
          />

          {requiresAnchor && editingAnchor ? (
            <Card>
              <CardContent className="space-y-3 pt-5">
                <Label htmlFor="anchorPos" className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">锚点</Label>
                <Input id="anchorPos" value={positionText} onChange={(event) => setPositionText(event.target.value)} disabled={!canEdit} className="h-11 rounded-xl border-[color:var(--theme-soft-border)] bg-background" />
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" onClick={() => void saveChanges()} disabled={!canSave || editM.isPending}>
                    <Save className="h-4 w-4" />
                    {editM.isPending ? "保存中..." : "保存"}
                  </Button>
                  <Button size="sm" variant="outline" onClick={cancelAnchorEditor} disabled={editM.isPending}>
                    <X className="h-4 w-4" />
                    取消
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : !requiresAnchor ? (
            <Card>
              <CardContent className="pt-5 text-sm text-muted-foreground">
                当前项目类型不要求为复述点绑定锚点，所以这条记录会以项目级零散知识点形式保存。
              </CardContent>
            </Card>
          ) : null}

          <Button variant="outline" asChild className="w-full rounded-full">
            <Link to={buildAiChatPath(projectId, { kind: "recall", nodeId: recallPointId })}>
              <Sparkles className="h-4 w-4" />
              AI问答
            </Link>
          </Button>
          {recallPoint.state === "ACTIVE" ? (
            <Button
              variant="destructive"
              disabled={deleteM.isPending}
              className="w-full rounded-full"
              onClick={() => {
                if (!window.confirm("删除后会将这条复述点标记为墓碑，并从当前内容视图中移除。确定继续吗？")) return
                deleteM.mutate()
              }}
            >
              <Trash2 className="h-4 w-4" />
              {deleteM.isPending ? "删除中..." : "删除"}
            </Button>
          ) : null}
        </div>
      </aside>

      <section className="space-y-5 xl:min-w-0">
        <RecallPointContentCard
          canEdit={canEdit}
          canSave={canSave}
          editError={editM.error}
          editingContent={editingContent}
          isSaving={editM.isPending}
          projectId={projectId}
          question={question}
          answer={answer}
          requiresAnchor={requiresAnchor}
          positionText={positionText}
          recallPoint={recallPoint}
          onAppendAnswerImage={(assetId) => setAnswer((prev) => appendImageBlock(prev, assetId))}
          onAppendQuestionImage={(assetId) => setQuestion((prev) => appendImageBlock(prev, assetId))}
          onCancelContentEditor={cancelContentEditor}
          onOpenAnchorEditor={openAnchorEditor}
          onOpenContentEditor={openContentEditor}
          onRemoveAnswerImage={(imageIndex) => setAnswer((prev) => removeImageBlockAt(prev, imageIndex))}
          onRemoveQuestionImage={(imageIndex) => setQuestion((prev) => removeImageBlockAt(prev, imageIndex))}
          onSaveChanges={saveChanges}
          onSetAnswerText={(text) => setAnswer((prev) => setRichContentText(prev, text))}
          onSetQuestionText={(text) => setQuestion((prev) => setRichContentText(prev, text))}
        />

        <Card>
          <CardHeader className="pb-3">
            <CardTitle>引用关系</CardTitle>
            <CardDescription>这条复述点引用到的其他复述点不会写进题面或答案文本里。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {recallPoint.references.length === 0 ? (
              <div className="text-sm text-muted-foreground">暂无引用关系。</div>
            ) : (
              recallPoint.references.map((referenceId, index) => {
                const query = referenceRecallPointQs[index]
                const referenced = query?.data
                return (
                  <div key={referenceId} className="rounded-[1rem] border border-[#dbe4ee] bg-[#fbfdff] p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-xs text-muted-foreground">引用 #{index + 1}</div>
                        <div className="mt-1 text-sm font-medium text-foreground">{formatRecallPointReference(referenceId)}</div>
                      </div>
                      <Button asChild type="button" variant="outline" size="sm" className="rounded-full">
                        <Link to={`/p/${projectId}/recall-points/${referenceId}`}>打开</Link>
                      </Button>
                    </div>
                    {query?.isLoading ? <div className="mt-3 text-sm text-muted-foreground">正在加载引用内容...</div> : null}
                    {query?.error ? <div className="mt-3 text-sm text-destructive">加载失败：{formatApiError(query.error)}</div> : null}
                    {referenced ? (
                      <div className="mt-3 space-y-3">
                        <div>
                          <div className="text-xs text-muted-foreground">题面</div>
                          <div className="mt-1 text-sm leading-6 text-foreground">
                            {renderRichContentPreview(projectId, referenced.question, "题面为空。")}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs text-muted-foreground">答案</div>
                          <div className="mt-1 text-sm leading-6 text-foreground">
                            {renderRichContentPreview(projectId, referenced.answer, "答案为空。")}
                          </div>
                        </div>
                      </div>
                    ) : null}
                  </div>
                )
              })
            )}
          </CardContent>
        </Card>

        <ReviewProjectionCard projectId={projectId} recallPointId={recallPointId} />

        <Card>
          <CardHeader className="pb-3">
            <CardTitle>历史理解</CardTitle>
            <CardDescription>正式复习时追加的理解会沉淀在这里。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {recallPoint.insights.length === 0 ? (
              <div className="text-sm text-muted-foreground">暂无历史理解。</div>
            ) : (
              recallPoint.insights.map((item, index) => (
                <div key={index} className="rounded-[1rem] border border-[#dbe4ee] bg-[#fbfdff] p-4">
                  <div className="text-xs text-muted-foreground">#{index + 1}</div>
                  <RichContentRenderer projectId={projectId} value={item} className="mt-2 text-sm leading-6" />
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  )
}

type SummaryItem = {
  label: string
  value: ReactNode
}

function RecallPointSummaryCard({
  description,
  header,
  items,
  topAction,
}: {
  description?: ReactNode
  header: ReactNode
  items: SummaryItem[]
  topAction?: ReactNode
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        {topAction ? <div className="flex items-center">{topAction}</div> : null}
        <div className="min-w-0">{header}</div>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-3">
          {items.map((item) => (
            <div key={item.label} className="min-w-[10rem] flex-1 rounded-xl border border-[#dbe4ee] bg-[#f8fafc] px-4 py-3 shadow-[0_10px_24px_-24px_rgba(15,23,42,0.6)]">
              <div className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#64748b]">{item.label}</div>
              <div className="mt-1.5 break-words text-sm font-semibold text-slate-900">{item.value}</div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function RecallPointContentCard({
  answer,
  canEdit,
  canSave,
  editError,
  editingContent,
  isSaving,
  onAppendAnswerImage,
  onAppendQuestionImage,
  onCancelContentEditor,
  onOpenAnchorEditor,
  onOpenContentEditor,
  onRemoveAnswerImage,
  onRemoveQuestionImage,
  onSaveChanges,
  onSetAnswerText,
  onSetQuestionText,
  positionText,
  projectId,
  question,
  recallPoint,
  requiresAnchor,
}: {
  answer: RichContent
  canEdit: boolean
  canSave: boolean
  editError: unknown
  editingContent: boolean
  isSaving: boolean
  onAppendAnswerImage: (assetId: string) => void
  onAppendQuestionImage: (assetId: string) => void
  onCancelContentEditor: () => void
  onOpenAnchorEditor: () => void
  onOpenContentEditor: () => void
  onRemoveAnswerImage: (imageIndex: number) => void
  onRemoveQuestionImage: (imageIndex: number) => void
  onSaveChanges: () => Promise<void>
  onSetAnswerText: (text: string) => void
  onSetQuestionText: (text: string) => void
  positionText: string
  projectId: string
  question: RichContent
  recallPoint: RecallPoint
  requiresAnchor: boolean
}) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle>当前内容</CardTitle>
            <CardDescription>按复习任务里的阅读顺序展示题面和答案。</CardDescription>
          </div>
          {canEdit && !editingContent ? (
            <Button size="sm" variant="outline" className="rounded-full" onClick={onOpenContentEditor}>
              <PencilLine className="h-4 w-4" />
              修改内容
            </Button>
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {editingContent ? (
          <div className="space-y-5">
            <div className="space-y-3">
              <Label className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">题面</Label>
              <RichContentEditor projectId={projectId} field="question" value={question} disabled={!canEdit} placeholder="输入问题/提示语" className="space-y-3" textareaClassName="min-h-[120px] rounded-[1rem] border-[#dbe4ee] bg-[#fbfdff] px-4 py-3 text-sm leading-6 text-foreground placeholder:text-muted-foreground" imageClassName="h-24 w-24 rounded-[0.95rem] border-[#dbe4ee] bg-[#fbfdff]" onTextChange={onSetQuestionText} onAppendImage={onAppendQuestionImage} onRemoveImage={onRemoveQuestionImage} />
            </div>
            <div className="space-y-3">
              <Label className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">答案</Label>
              <RichContentEditor projectId={projectId} field="answer" value={answer} disabled={!canEdit} placeholder="输入答案/复述内容" className="space-y-3" textareaClassName="min-h-[160px] rounded-[1rem] border-[#dbe4ee] bg-[#fbfdff] px-4 py-3 text-sm leading-6 text-foreground placeholder:text-muted-foreground" imageClassName="h-24 w-24 rounded-[0.95rem] border-[#dbe4ee] bg-[#fbfdff]" onTextChange={onSetAnswerText} onAppendImage={onAppendAnswerImage} onRemoveImage={onRemoveAnswerImage} />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => void onSaveChanges()} disabled={!canSave || isSaving}>
                <Save className="h-4 w-4" />
                {isSaving ? "保存中..." : "保存修改"}
              </Button>
              <Button variant="outline" onClick={onCancelContentEditor} disabled={isSaving}>
                <X className="h-4 w-4" />
                取消
              </Button>
            </div>
          </div>
        ) : (
          <>
            <div className="rounded-[1rem] border border-[#dbe4ee] bg-[#fbfdff] p-4">
              <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#64748b]">
                <span>题面</span>
                {requiresAnchor ? (
                  <button type="button" className="rounded-full border border-[#dbe4ee] bg-white px-2.5 py-1 normal-case tracking-normal text-slate-900 transition hover:bg-primary/5 hover:text-primary" onClick={onOpenAnchorEditor} disabled={!canEdit}>
                    {formatAnchorPosition(positionText)}
                  </button>
                ) : null}
              </div>
              <div className="mt-3 text-[15px] font-semibold leading-7 text-foreground">
                {renderRichContentPreview(projectId, question, "题面为空。")}
              </div>
            </div>

            <div className="rounded-[1rem] border border-[#dbe4ee] bg-[#fbfdff] p-4">
              <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#64748b]">
                <span>答案</span>
                <span className="rounded-full border border-[#dbe4ee] bg-white px-2.5 py-1 normal-case tracking-normal text-slate-900">
                  {recallPoint.anchor ? formatInstanceReference(recallPoint.anchor.instanceId, undefined, "未关联内容实例") : "未绑定内容实例"}
                </span>
              </div>
              <div className="mt-3 text-sm leading-6 text-foreground">
                {renderRichContentPreview(projectId, answer, "答案为空。")}
              </div>
            </div>
          </>
        )}
        {editError ? <p className="text-sm text-destructive">{formatApiError(editError)}</p> : null}
      </CardContent>
    </Card>
  )
}

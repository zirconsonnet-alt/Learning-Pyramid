import { MessageSquareText, PencilLine, Save, Sparkles, Trash2, X } from "lucide-react"
import { useMemo, useState } from "react"
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import type { ScopedProjectRef } from "@/ui/api/projectScope"
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
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { buildScopedProjectPath } from "@/ui/projectPaths"
import { projectTypeRequiresAnchor } from "@/ui/projectTypes"
import { useInstances, useProjectConfig } from "@/ui/queries/workbench"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { buildAiChatPath } from "@/views/ai/chatRouting"
import { ReviewProjectionCard } from "@/views/recallPoints/components/ReviewProjectionCard"
import { DetailSummaryCard } from "@/views/shared/DetailSummaryCard"

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

function parseClockAnchorMs(value: string): number | null {
  const parts = value.trim().split(":")
  if (parts.length < 2 || parts.length > 3) return null
  if (!parts.every((part) => /^\d+$/.test(part))) return null

  const numbers = parts.map((part) => Number(part))
  if (numbers.some((part) => !Number.isFinite(part))) return null

  const [hours, minutes, seconds] = parts.length === 3 ? numbers : [0, numbers[0], numbers[1]]
  if (minutes < 0 || minutes > 59 || seconds < 0 || seconds > 59) return null
  return ((hours * 3600) + (minutes * 60) + seconds) * 1000
}

function normalizeAnchorInputToPosition(value: string): string {
  const normalized = value.trim()
  if (!normalized) return ""
  const existingPositionMs = parseAnchorMs(normalized)
  if (existingPositionMs !== null) return `t=${existingPositionMs}`
  const clockMs = parseClockAnchorMs(normalized)
  return clockMs === null ? normalized : `t=${clockMs}`
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

function buildRecallPointDetailPath(subjectId: string, projectId: string, recallPointId: string) {
  return buildScopedProjectPath(subjectId, projectId, `/recall-points/${recallPointId}`)
}

function renderRichContentPreview(subjectId: string, projectId: string, value: RichContent, emptyText: string) {
  return richContentHasMeaning(value) ? (
    <RichContentRenderer subjectId={subjectId} projectId={projectId} value={value} />
  ) : (
    <div className="text-sm leading-6 text-muted-foreground">{emptyText}</div>
  )
}

export function RecallPointPage() {
  const { subjectId = "", scopedProjectId, recallPointId } = useParams()
  const pid = scopedProjectId ?? ""
  const rpid = recallPointId ?? ""
  const projectScope = subjectId && pid ? { subjectId, scopedProjectId: pid } : null
  const navigate = useNavigate()

  const qKey = useMemo(() => ["recallPoint", subjectId, pid, rpid], [subjectId, pid, rpid])
  const q = useQuery({
    queryKey: qKey,
    queryFn: () => getRecallPoint(projectScope as ScopedProjectRef, rpid),
    enabled: !!projectScope && !!rpid,
  })

  const recallPoint = q.data ?? null

  if (!subjectId || !pid || !rpid) {
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
          subjectId={subjectId}
          projectId={pid}
          projectScope={projectScope as ScopedProjectRef}
          recallPointId={rpid}
          qKey={qKey}
          recallPoint={recallPoint}
        />
      ) : null}
    </div>
  )
}

function RecallPointDetailLayout({
  subjectId,
  projectId,
  projectScope,
  recallPointId,
  qKey,
  recallPoint,
}: {
  subjectId: string
  projectId: string
  projectScope: ScopedProjectRef
  recallPointId: string
  qKey: readonly string[]
  recallPoint: RecallPoint
}) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const projectConfigQ = useProjectConfig(projectScope)
  const instancesQ = useInstances(projectScope)
  const projectType = projectConfigQ.data?.projectType ?? "COURSE"
  const requiresAnchor = projectTypeRequiresAnchor(projectType)
  const [question, setQuestion] = useState<RichContent>(() => recallPoint.question)
  const [answer, setAnswer] = useState<RichContent>(() => recallPoint.answer)
  const [positionText, setPositionText] = useState(() => recallPoint.anchor?.position ?? "")
  const [anchorDraft, setAnchorDraft] = useState(() => formatAnchorPosition(recallPoint.anchor?.position))
  const [editingAnchor, setEditingAnchor] = useState(false)
  const [editingContent, setEditingContent] = useState(false)
  const referenceRecallPointQs = useQueries({
    queries: recallPoint.references.map((referenceId) => ({
      queryKey: ["recallPoint", subjectId, projectId, referenceId],
      queryFn: () => getRecallPoint(projectScope, referenceId),
      enabled: !!projectId,
    })),
  })
  const referenceRecallPoints = useMemo(
    () => recallPoint.references.map((referenceId, index) => ({ referenceId, recallPoint: referenceRecallPointQs[index]?.data ?? null })),
    [recallPoint.references, referenceRecallPointQs],
  )

  const deleteM = useMutation({
    mutationFn: () => deleteRecallPoint(projectScope, recallPointId),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["recallPoint", subjectId, projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPoints", subjectId, projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPointSearch", subjectId, projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPointsByInstance", subjectId, projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPointsByTaskNode", subjectId, projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPointsByObjectNode", subjectId, projectId] }),
        qc.invalidateQueries({ queryKey: ["reviewRecommendations", subjectId, projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPointReviewProjection", subjectId, projectId] }),
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
      const pos = normalizeAnchorInputToPosition(editingAnchor ? anchorDraft : positionText)
      if (!richContentHasMeaning(question) || !richContentHasMeaning(answer)) return
      if (requiresAnchor && (!recallPoint.anchor || !pos)) return
      await editRecallPoint(projectScope, recallPointId, {
        question,
        answer,
        anchor: requiresAnchor && recallPoint.anchor ? { instanceId: recallPoint.anchor.instanceId, position: pos } : null,
      })
    },
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: qKey }),
        qc.invalidateQueries({ queryKey: ["recallPoints", subjectId, projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPointSearch", subjectId, projectId] }),
        qc.invalidateQueries({ queryKey: ["reviewRecommendations", subjectId, projectId] }),
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
    (!requiresAnchor || !!normalizeAnchorInputToPosition(editingAnchor ? anchorDraft : positionText))
  const anchorInstance = useMemo(
    () => (recallPoint.anchor ? (instancesQ.data ?? []).find((instance) => instance.instanceId === recallPoint.anchor?.instanceId) ?? null : null),
    [instancesQ.data, recallPoint.anchor],
  )
  const anchorInstanceValue = recallPoint.anchor ? (
    <Link className="text-primary underline-offset-4 hover:underline" to={buildScopedProjectPath(subjectId, projectId, `/instances/${recallPoint.anchor.instanceId}`)}>
      {anchorInstance?.materialDisplayName ?? (instancesQ.isLoading ? "读取中..." : "未找到内容实例")}
    </Link>
  ) : (
    "未绑定内容实例"
  )

  function openAnchorEditor() {
    if (!canEdit || !requiresAnchor) return
    setAnchorDraft(formatAnchorPosition(positionText))
    setEditingAnchor(true)
  }

  function cancelAnchorEditor() {
    setPositionText(recallPoint.anchor?.position ?? "")
    setAnchorDraft(formatAnchorPosition(recallPoint.anchor?.position))
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
    if (editingAnchor) setPositionText(normalizeAnchorInputToPosition(anchorDraft))
    setEditingAnchor(false)
    setEditingContent(false)
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(18rem,22rem)_minmax(0,1fr)] xl:items-start">
      <aside className="xl:sticky xl:top-28 xl:self-start">
        <div className="space-y-3">
          <DetailSummaryCard
            icon={MessageSquareText}
            title="复述点"
            items={[
              {
                label: "内容实例",
                value: anchorInstanceValue,
              },
              {
                label: "锚点",
                value:
                  requiresAnchor ? (
                    <div className="flex flex-wrap items-center gap-2">
                      {editingAnchor ? (
                        <>
                          <Input
                            value={anchorDraft}
                            onChange={(event) => setAnchorDraft(event.target.value)}
                            disabled={!canEdit}
                            placeholder="0:43"
                            aria-label="锚点时间"
                            className="h-9 max-w-[7.5rem] rounded-full border-[#dbe4ee] bg-white px-3 text-sm font-semibold"
                          />
                          <Button size="sm" onClick={() => void saveChanges()} disabled={!canSave || editM.isPending} className="rounded-full">
                            <Save className="h-4 w-4" />
                            {editM.isPending ? "保存中..." : "保存锚点"}
                          </Button>
                          <Button size="sm" variant="outline" onClick={cancelAnchorEditor} disabled={editM.isPending} className="rounded-full">
                            <X className="h-4 w-4" />
                            取消
                          </Button>
                        </>
                      ) : (
                        <>
                          <span className="rounded-full bg-primary/8 px-2.5 py-1 text-sm font-semibold text-primary">{formatAnchorPosition(positionText)}</span>
                          {canEdit ? (
                            <Button type="button" size="sm" variant="outline" onClick={openAnchorEditor} className="rounded-full">
                              <PencilLine className="h-4 w-4" />
                              修改锚点
                            </Button>
                          ) : null}
                        </>
                      )}
                    </div>
                  ) : (
                    "未绑定锚点"
                  ),
              },
            ]}
          />

          {!requiresAnchor ? (
            <Card>
              <CardContent className="pt-5 text-sm text-muted-foreground">
                当前项目类型不要求为复述点绑定锚点，所以这条记录会以项目级零散知识点形式保存。
              </CardContent>
            </Card>
          ) : null}

          <Button variant="outline" asChild className="w-full rounded-full">
            <Link to={buildAiChatPath(subjectId, projectId, { kind: "recall", nodeId: recallPointId })}>
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
          subjectId={subjectId}
          canEdit={canEdit}
          canSave={canSave}
          editError={editM.error}
          editingContent={editingContent}
          isSaving={editM.isPending}
          projectId={projectId}
          question={question}
          answer={answer}
          referenceRecallPoints={referenceRecallPoints}
          onAppendAnswerImage={(assetId) => setAnswer((prev) => appendImageBlock(prev, assetId))}
          onAppendQuestionImage={(assetId) => setQuestion((prev) => appendImageBlock(prev, assetId))}
          onCancelContentEditor={cancelContentEditor}
          onOpenContentEditor={openContentEditor}
          onRemoveAnswerImage={(imageIndex) => setAnswer((prev) => removeImageBlockAt(prev, imageIndex))}
          onRemoveQuestionImage={(imageIndex) => setQuestion((prev) => removeImageBlockAt(prev, imageIndex))}
          onSaveChanges={saveChanges}
          onSetAnswerText={(text) => setAnswer((prev) => setRichContentText(prev, text))}
          onSetQuestionText={(text) => setQuestion((prev) => setRichContentText(prev, text))}
        />

        <ReviewProjectionCard subjectId={subjectId} projectId={projectId} recallPointId={recallPointId} />

        <Card>
          <CardHeader className="pb-3">
            <CardTitle>历史理解</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {recallPoint.insights.length === 0 ? (
              <div className="text-sm text-muted-foreground">暂无历史理解。</div>
            ) : (
              recallPoint.insights.map((item, index) => (
                <div key={index} className="rounded-[1rem] border border-[#dbe4ee] bg-[#fbfdff] p-4">
                  <div className="text-xs text-muted-foreground">#{index + 1}</div>
                  <RichContentRenderer subjectId={subjectId} projectId={projectId} value={item} className="mt-2 text-sm leading-6" />
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </section>
    </div>
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
  onOpenContentEditor,
  onRemoveAnswerImage,
  onRemoveQuestionImage,
  onSaveChanges,
  onSetAnswerText,
  onSetQuestionText,
  projectId,
  question,
  referenceRecallPoints,
  subjectId,
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
  onOpenContentEditor: () => void
  onRemoveAnswerImage: (imageIndex: number) => void
  onRemoveQuestionImage: (imageIndex: number) => void
  onSaveChanges: () => Promise<void>
  onSetAnswerText: (text: string) => void
  onSetQuestionText: (text: string) => void
  projectId: string
  question: RichContent
  referenceRecallPoints: Array<{ referenceId: string; recallPoint: RecallPoint | null }>
  subjectId: string
}) {
  const referencesCount = referenceRecallPoints.length

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle>当前内容</CardTitle>
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
              <RichContentEditor subjectId={subjectId} projectId={projectId} field="question" value={question} disabled={!canEdit} placeholder="输入问题/提示语" className="space-y-3" textareaClassName="min-h-[120px] rounded-[1rem] border-[#dbe4ee] bg-[#fbfdff] px-4 py-3 text-sm leading-6 text-foreground placeholder:text-muted-foreground" imageClassName="h-24 w-24 rounded-[0.95rem] border-[#dbe4ee] bg-[#fbfdff]" onTextChange={onSetQuestionText} onAppendImage={onAppendQuestionImage} onRemoveImage={onRemoveQuestionImage} />
            </div>
            <div className="space-y-3">
              <Label className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">答案</Label>
              <RichContentEditor subjectId={subjectId} projectId={projectId} field="answer" value={answer} disabled={!canEdit} placeholder="输入答案/复述内容" className="space-y-3" textareaClassName="min-h-[160px] rounded-[1rem] border-[#dbe4ee] bg-[#fbfdff] px-4 py-3 text-sm leading-6 text-foreground placeholder:text-muted-foreground" imageClassName="h-24 w-24 rounded-[0.95rem] border-[#dbe4ee] bg-[#fbfdff]" onTextChange={onSetAnswerText} onAppendImage={onAppendAnswerImage} onRemoveImage={onRemoveAnswerImage} />
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
              </div>
              <div className="mt-3 text-[15px] font-semibold leading-7 text-foreground">
                {renderRichContentPreview(subjectId, projectId, question, "题面为空。")}
              </div>
            </div>

            <div className="rounded-[1rem] border border-[#dbe4ee] bg-[#fbfdff] p-4">
              <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#64748b]">
                <span>答案</span>
                {referencesCount > 0 ? (
                  <span className="rounded-full border border-[#dbe4ee] bg-white px-2.5 py-1 normal-case tracking-normal text-slate-900">
                    引用 {referencesCount}
                  </span>
                ) : null}
              </div>
              <div className="mt-3 text-sm leading-6 text-foreground">
                {renderRichContentPreview(subjectId, projectId, answer, "答案为空。")}
              </div>
            </div>

            {referencesCount > 0 ? (
              <div className="rounded-[1rem] border border-[#dbe4ee] bg-[#fbfdff] p-4">
                <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#64748b]">
                  <span>引用</span>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {referenceRecallPoints.map((item, index) => (
                    <Link
                      key={item.referenceId}
                      to={buildRecallPointDetailPath(subjectId, projectId, item.referenceId)}
                      className="rounded-full border border-[#dbe4ee] bg-white px-3 py-1.5 text-sm font-medium text-slate-900 transition hover:bg-primary/5 hover:text-primary"
                    >
                      引用 {index + 1}
                    </Link>
                  ))}
                </div>
              </div>
            ) : null}
          </>
        )}
        {editError ? <p className="text-sm text-destructive">{formatApiError(editError)}</p> : null}
      </CardContent>
    </Card>
  )
}

import { ArrowLeft, PencilLine, Sparkles, Trash2 } from "lucide-react"
import { useEffect, useMemo, useState } from "react"
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query"
import { Link, useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { listLearningObjectNodes, type LearningObjectNode } from "@/ui/api/learningObjects"
import {
  appendImageBlock,
  removeImageBlockAt,
  richContentHasMeaning,
  setRichContentText,
  type RichContent,
} from "@/ui/api/richContent"
import { deleteRecallPoint, editRecallPoint, getRecallPoint, collectRecallPointToMistakeMaterial, type RecallPoint } from "@/ui/api/review"
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
import { useSubjectContext } from "@/ui/queries/subjects"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { cn } from "@/ui/utils"
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

function formatRecallPointStateLabel(state: RecallPoint["state"] | null | undefined) {
  return state === "ACTIVE" ? "可编辑" : "已删除"
}

function formatMistakeStatusLabel(status: RecallPoint["mistakeStatus"] | null | undefined) {
  if (status === "RESOLVING") return "正在攻克"
  if (status === "RESOLVED") return "已解决"
  return "待解决"
}

function flattenLeafNodes(nodes: LearningObjectNode[]) {
  return nodes
    .filter((node): node is Extract<LearningObjectNode, { kind: "leaf" }> => node.kind === "leaf")
    .sort((left, right) => {
      const leftKey = `${left.relativePath ?? ""}::${left.title}::${left.nodeId}`
      const rightKey = `${right.relativePath ?? ""}::${right.title}::${right.nodeId}`
      return leftKey.localeCompare(rightKey, "zh-Hans-CN", { numeric: true, sensitivity: "base" })
    })
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
  const subjectContextQ = useSubjectContext(projectId, !!projectId)
  const projectType = projectConfigQ.data?.projectType ?? "COURSE"
  const requiresAnchor = projectTypeRequiresAnchor(projectType)
  const isMistakeMaterial = projectType === "MISTAKE_BOOK"
  const [question, setQuestion] = useState<RichContent>(() => recallPoint.question)
  const [answer, setAnswer] = useState<RichContent>(() => recallPoint.answer)
  const [positionText, setPositionText] = useState(() => recallPoint.anchor?.position ?? "")
  const [mistakeStatus, setMistakeStatus] = useState<RecallPoint["mistakeStatus"]>(() => recallPoint.mistakeStatus ?? "OPEN")
  const [mistakeNote, setMistakeNote] = useState(() => recallPoint.mistakeNote ?? "")
  const [collectNote, setCollectNote] = useState("")

  const mistakeMaterials = useMemo(
    () =>
      (subjectContextQ.data?.materials ?? []).filter(
        (item) => item.materialType === "MISTAKE_BOOK" && item.compatibilityProjectId && item.compatibilityProjectId !== projectId,
      ),
    [projectId, subjectContextQ.data?.materials],
  )
  const [selectedMistakeMaterialId, setSelectedMistakeMaterialId] = useState("")
  const selectedMistakeMaterial = useMemo(
    () => mistakeMaterials.find((item) => item.materialId === selectedMistakeMaterialId) ?? mistakeMaterials[0] ?? null,
    [mistakeMaterials, selectedMistakeMaterialId],
  )
  const selectedMistakeProjectId = selectedMistakeMaterial?.compatibilityProjectId ?? ""
  const targetNodesQ = useQuery({
    queryKey: ["learningObjectNodes", selectedMistakeProjectId],
    queryFn: () => listLearningObjectNodes(selectedMistakeProjectId),
    enabled: !isMistakeMaterial && !!selectedMistakeProjectId,
  })
  const targetLeafNodes = useMemo(() => flattenLeafNodes(targetNodesQ.data ?? []), [targetNodesQ.data])
  const referenceRecallPointQs = useQueries({
    queries: recallPoint.references.map((referenceId) => ({
      queryKey: ["recallPoint", projectId, referenceId],
      queryFn: () => getRecallPoint(projectId, referenceId),
      enabled: !!projectId,
    })),
  })
  const [selectedTargetNodeId, setSelectedTargetNodeId] = useState("")

  const sourceDetailPath =
    recallPoint.sourceProjectId && recallPoint.sourceRecallPointId
      ? `/p/${recallPoint.sourceProjectId}/recall-points/${recallPoint.sourceRecallPointId}`
      : null
  useEffect(() => {
    if (mistakeMaterials.length === 0) {
      setSelectedMistakeMaterialId("")
      return
    }
    setSelectedMistakeMaterialId((current) =>
      mistakeMaterials.some((item) => item.materialId === current) ? current : mistakeMaterials[0]?.materialId ?? "",
    )
  }, [mistakeMaterials])

  useEffect(() => {
    if (targetLeafNodes.length === 0) {
      setSelectedTargetNodeId("")
      return
    }
    setSelectedTargetNodeId((current) =>
      targetLeafNodes.some((item) => item.nodeId === current) ? current : targetLeafNodes[0]?.nodeId ?? "",
    )
  }, [targetLeafNodes])

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

  const collectM = useMutation({
    mutationFn: async () => {
      if (!selectedMistakeMaterial) return
      return collectRecallPointToMistakeMaterial(projectId, recallPointId, {
        targetMaterialId: selectedMistakeMaterial.materialId,
        targetNodeId: selectedTargetNodeId || null,
        mistakeNote: collectNote.trim() || null,
      })
    },
    onSuccess: async (result) => {
      if (!result) return
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["subjectContext", projectId] }),
        qc.invalidateQueries({ queryKey: ["learningObjectNodes", result.target_project_id] }),
        qc.invalidateQueries({ queryKey: ["instances", result.target_project_id] }),
        qc.invalidateQueries({ queryKey: ["queue", result.target_project_id] }),
        qc.invalidateQueries({ queryKey: ["layers", result.target_project_id] }),
      ])
      const targetLeaf = targetLeafNodes.find((item) => item.nodeId === result.target_node_id)
      showSuccessFeedback(
        "已收进错题材料",
        `这条复述点已经进入“${selectedMistakeMaterial?.title ?? "错题材料"}”${targetLeaf ? ` · ${targetLeaf.title}` : ""}。`,
      )
      setCollectNote("")
    },
    onError: (err) => {
      showErrorFeedback("收进错题材料失败", formatApiError(err))
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
        mistakeStatus: isMistakeMaterial ? mistakeStatus ?? "OPEN" : null,
        mistakeNote: isMistakeMaterial ? mistakeNote : null,
      })
    },
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: qKey }),
        qc.invalidateQueries({ queryKey: ["recallPoints", projectId] }),
        qc.invalidateQueries({ queryKey: ["recallPointSearch", projectId] }),
        qc.invalidateQueries({ queryKey: ["reviewRecommendations", projectId] }),
      ])
      showSuccessFeedback("复述点已保存", "题面、答案和锚点位置已经更新。")
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

  return (
    <div className="grid gap-5 xl:grid-cols-[22rem_minmax(0,1fr)]">
      <aside className="xl:sticky xl:top-28 xl:self-start">
        <Card className="theme-card-main overflow-hidden">
          <CardHeader className="theme-card-header">
            <div className="flex items-center">
              <Button
                variant="ghost"
                size="sm"
                className="-ml-2 h-8 rounded-full px-2 text-[#60748c] hover:bg-[#f3f7fb] hover:text-foreground"
                onClick={() => navigate(-1)}
              >
                <ArrowLeft className="h-4 w-4" />
                返回
              </Button>
            </div>
            <div className="flex items-center gap-3">
              <div className="theme-icon-surface h-10 w-10">
                <PencilLine className="h-5 w-5" />
              </div>
              <div>
                <CardTitle>概览与修改</CardTitle>
                <CardDescription>{canEdit ? "元信息和修改集中在这里。" : "当前复述点只保留浏览视图。"}</CardDescription>
              </div>
            </div>
          </CardHeader>

          <CardContent className="space-y-5 pt-5 xl:max-h-[calc(100dvh-10rem)] xl:overflow-y-auto xl:overscroll-contain xl:pr-3">
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between gap-3 border-b border-border/60 pb-3">
                <span className="text-muted-foreground">状态</span>
                <span
                  className={cn(
                    "rounded-full border px-2.5 py-1 text-xs font-medium",
                    recallPoint.state === "ACTIVE"
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                      : "border-amber-200 bg-amber-50 text-amber-700",
                  )}
                >
                  {formatRecallPointStateLabel(recallPoint.state)}
                </span>
              </div>
              <div className="flex items-start justify-between gap-3 border-b border-border/60 pb-3">
                <span className="text-muted-foreground">材料</span>
                <span className="max-w-[11rem] text-right font-medium text-foreground">
                  {recallPoint.anchor ? formatInstanceReference(recallPoint.anchor.instanceId, undefined, "未关联材料实例") : "未绑定材料实例"}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">锚点</span>
                <span className="font-medium text-foreground">{requiresAnchor ? formatAnchorPosition(positionText) : "未绑定锚点"}</span>
              </div>
            </div>

            {requiresAnchor ? (
              <div className="space-y-2">
                <Label htmlFor="anchorPos" className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  锚点位置
                </Label>
                <Input
                  id="anchorPos"
                  value={positionText}
                  onChange={(event) => setPositionText(event.target.value)}
                  disabled={!canEdit}
                  className="h-11 rounded-xl border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)]"
                />
              </div>
            ) : (
              <div className="rounded-[1rem] border border-border/70 bg-muted/15 px-4 py-3 text-sm text-muted-foreground">
                当前项目类型不要求为复述点绑定锚点，所以这条记录会以项目级零散知识点形式保存。
              </div>
            )}

            {isMistakeMaterial ? (
              <div className="space-y-4 rounded-[1rem] border border-border/70 bg-muted/10 px-4 py-4">
                <div className="space-y-2">
                  <Label htmlFor="mistakeStatus" className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                    错题状态
                  </Label>
                  <select
                    id="mistakeStatus"
                    value={mistakeStatus ?? "OPEN"}
                    disabled={!canEdit}
                    onChange={(event) => setMistakeStatus(event.target.value as RecallPoint["mistakeStatus"])}
                    className="h-11 w-full rounded-xl border bg-background px-3 text-sm"
                  >
                    <option value="OPEN">待解决</option>
                    <option value="RESOLVING">正在攻克</option>
                    <option value="RESOLVED">已解决</option>
                  </select>
                  <p className="text-xs text-muted-foreground">当前状态：{formatMistakeStatusLabel(mistakeStatus)}</p>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="mistakeNote" className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                    整理备注
                  </Label>
                  <textarea
                    id="mistakeNote"
                    value={mistakeNote}
                    onChange={(event) => setMistakeNote(event.target.value)}
                    disabled={!canEdit}
                    rows={4}
                    className="min-h-[7rem] w-full resize-y rounded-[1rem] border border-border/70 bg-background px-4 py-3 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/15"
                    placeholder="例如：总在链式法则这里丢符号；下次先写出内外层。"
                  />
                </div>

                {recallPoint.sourceMaterialTitle || recallPoint.sourceAnchorLabel || sourceDetailPath ? (
                  <div className="space-y-2 rounded-[0.95rem] border border-border/70 bg-background px-4 py-3 text-sm">
                    <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">来源</div>
                    <div className="text-foreground">{recallPoint.sourceMaterialTitle || "原始材料"}</div>
                    {recallPoint.sourceAnchorLabel ? <div className="text-xs leading-5 text-muted-foreground">{recallPoint.sourceAnchorLabel}</div> : null}
                    {sourceDetailPath ? (
                      <Button asChild type="button" variant="outline" size="sm" className="rounded-full">
                        <Link to={sourceDetailPath}>打开原始复述点</Link>
                      </Button>
                    ) : null}
                  </div>
                ) : null}
              </div>
            ) : null}

            <div className="space-y-3">
              <Label className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">题面</Label>
              <RichContentEditor
                projectId={projectId}
                field="question"
                value={question}
                disabled={!canEdit}
                placeholder="输入问题/提示语"
                className="space-y-3"
                textareaClassName="min-h-[120px] rounded-[1rem] border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] px-4 py-3 text-sm leading-6 text-foreground placeholder:text-muted-foreground"
                imageClassName="h-24 w-24 rounded-[0.95rem] border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)]"
                onTextChange={(text) => setQuestion((prev) => setRichContentText(prev, text))}
                onAppendImage={(assetId) => setQuestion((prev) => appendImageBlock(prev, assetId))}
                onRemoveImage={(imageIndex) => setQuestion((prev) => removeImageBlockAt(prev, imageIndex))}
              />
            </div>

            <div className="space-y-3">
              <Label className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">答案</Label>
              <RichContentEditor
                projectId={projectId}
                field="answer"
                value={answer}
                disabled={!canEdit}
                placeholder="输入答案/复述内容"
                className="space-y-3"
                textareaClassName="min-h-[160px] rounded-[1rem] border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)] px-4 py-3 text-sm leading-6 text-foreground placeholder:text-muted-foreground"
                imageClassName="h-24 w-24 rounded-[0.95rem] border-[color:var(--theme-soft-border)] bg-[color:var(--theme-card-main-bg)]"
                onTextChange={(text) => setAnswer((prev) => setRichContentText(prev, text))}
                onAppendImage={(assetId) => setAnswer((prev) => appendImageBlock(prev, assetId))}
                onRemoveImage={(imageIndex) => setAnswer((prev) => removeImageBlockAt(prev, imageIndex))}
              />
            </div>

            <div className="space-y-3 border-t border-border/60 pt-4">
              <Button onClick={() => editM.mutate()} disabled={!canSave || editM.isPending} className="w-full rounded-full">
                {editM.isPending ? "保存中..." : "保存修改"}
              </Button>
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
              {editM.error ? <p className="text-sm text-destructive">{formatApiError(editM.error)}</p> : null}
            </div>
          </CardContent>
        </Card>
      </aside>

      <section className="space-y-5 xl:min-w-0">
        <Card className="theme-card-main overflow-hidden">
          <CardHeader className="theme-card-header">
            <CardTitle>当前内容</CardTitle>
            <CardDescription>按复习任务里的阅读顺序展示题面和答案。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 pt-5">
            <div className="rounded-[1.15rem] border border-[color:var(--theme-status-border)] bg-[color:var(--theme-card-main-bg)] px-4 py-4">
              <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                <span>题面</span>
                {requiresAnchor ? (
                  <span className="rounded-full border border-border/70 px-2.5 py-1 normal-case tracking-normal text-foreground">
                    {formatAnchorPosition(positionText)}
                  </span>
                ) : null}
              </div>
              <div className="mt-3 text-[15px] font-semibold leading-7 text-foreground">
                {renderRichContentPreview(projectId, question, "题面为空。")}
              </div>
            </div>

            <div className="theme-canvas rounded-[1.15rem] border border-[color:var(--theme-soft-border)] p-4">
              <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                <span>答案</span>
                <span className="rounded-full border border-border/70 px-2.5 py-1 normal-case tracking-normal text-foreground">
                  {recallPoint.anchor ? formatInstanceReference(recallPoint.anchor.instanceId, undefined, "未关联材料实例") : "未绑定材料实例"}
                </span>
              </div>
              <div className="mt-3 text-sm leading-6 text-foreground">
                {renderRichContentPreview(projectId, answer, "答案为空。")}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="theme-card-main overflow-hidden">
          <CardHeader className="theme-card-header">
            <CardTitle>引用关系</CardTitle>
            <CardDescription>这条复述点引用到的其他复述点不会写进题面或答案文本里。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 pt-5">
            {recallPoint.references.length === 0 ? (
              <div className="text-sm text-muted-foreground">暂无引用关系。</div>
            ) : (
              recallPoint.references.map((referenceId, index) => {
                const query = referenceRecallPointQs[index]
                const referenced = query?.data
                return (
                  <div key={referenceId} className="rounded-[1rem] border border-border/70 bg-muted/15 px-4 py-4">
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

        {!isMistakeMaterial ? (
          <Card className="theme-card-main overflow-hidden">
            <CardHeader className="theme-card-header">
              <CardTitle>收进错题材料</CardTitle>
              <CardDescription>把这条复述点沉淀到同一学科下的错题材料里，后面可以继续整理和复习。</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 pt-5">
              {mistakeMaterials.length > 0 ? (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="targetMistakeMaterial">目标错题材料</Label>
                    <select
                      id="targetMistakeMaterial"
                      value={selectedMistakeMaterialId}
                      onChange={(event) => setSelectedMistakeMaterialId(event.target.value)}
                      disabled={collectM.isPending}
                      className="h-11 w-full rounded-xl border bg-background px-3 text-sm"
                    >
                      {mistakeMaterials.map((material) => (
                        <option key={material.materialId} value={material.materialId}>
                          {material.title}
                        </option>
                      ))}
                    </select>
                  </div>

                  {targetLeafNodes.length > 0 ? (
                    <div className="space-y-2">
                      <Label htmlFor="targetMistakeNode">归档节点</Label>
                      <select
                        id="targetMistakeNode"
                        value={selectedTargetNodeId}
                        onChange={(event) => setSelectedTargetNodeId(event.target.value)}
                        disabled={collectM.isPending || targetNodesQ.isLoading}
                        className="h-11 w-full rounded-xl border bg-background px-3 text-sm"
                      >
                        {targetLeafNodes.map((node) => (
                          <option key={node.nodeId} value={node.nodeId}>
                            {node.title}
                          </option>
                        ))}
                      </select>
                    </div>
                  ) : (
                    <div className="rounded-[1rem] border border-border/70 bg-muted/15 px-4 py-3 text-sm text-muted-foreground">
                      {targetNodesQ.isLoading ? "正在读取错题材料结构..." : "目标错题材料还没有目录时，系统会自动创建一个“待整理”入口来承接这条错题。"}
                    </div>
                  )}

                  <div className="space-y-2">
                    <Label htmlFor="collectMistakeNote">备注</Label>
                    <textarea
                      id="collectMistakeNote"
                      value={collectNote}
                      onChange={(event) => setCollectNote(event.target.value)}
                      disabled={collectM.isPending}
                      rows={3}
                      className="min-h-[6rem] w-full resize-y rounded-[1rem] border border-border/70 bg-background px-4 py-3 text-sm leading-6 text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-2 focus:ring-primary/15"
                      placeholder="例如：这题总把分部积分的首项选错。"
                    />
                  </div>

                  <div className="flex justify-end">
                    <Button
                      type="button"
                      onClick={() => collectM.mutate()}
                      disabled={collectM.isPending || !selectedMistakeMaterial}
                      className="rounded-full"
                    >
                      {collectM.isPending ? "收集中..." : "收进错题材料"}
                    </Button>
                  </div>
                </>
              ) : (
                <div className="rounded-[1rem] border border-border/70 bg-muted/15 px-4 py-4 text-sm text-muted-foreground">
                  当前学科下还没有错题材料。先去学科设置里创建一个错题材料，这里就能直接收题了。
                  {subjectContextQ.data ? (
                    <div className="mt-3">
                      <Button asChild type="button" variant="outline" size="sm" className="rounded-full">
                        <Link to={`/p/${subjectContextQ.data.subjectProjectId}/settings`}>去学科设置创建</Link>
                      </Button>
                    </div>
                  ) : null}
                </div>
              )}
              {targetNodesQ.error ? <p className="text-sm text-destructive">{formatApiError(targetNodesQ.error)}</p> : null}
              {collectM.error ? <p className="text-sm text-destructive">{formatApiError(collectM.error)}</p> : null}
            </CardContent>
          </Card>
        ) : null}

        <Card className="theme-card-main overflow-hidden">
          <CardHeader className="theme-card-header">
            <CardTitle>历史理解</CardTitle>
            <CardDescription>正式复习时追加的理解会沉淀在这里。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 pt-5">
            {recallPoint.insights.length === 0 ? (
              <div className="text-sm text-muted-foreground">暂无历史理解。</div>
            ) : (
              recallPoint.insights.map((item, index) => (
                <div key={index} className="rounded-[1rem] border border-border/70 bg-muted/15 px-4 py-4">
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

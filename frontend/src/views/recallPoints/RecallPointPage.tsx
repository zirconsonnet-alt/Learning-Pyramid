import { Sparkles, Trash2 } from "lucide-react"
import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import {
  appendImageBlock,
  removeImageBlockAt,
  richContentHasMeaning,
  richText,
  type RichContent,
} from "@/ui/api/richContent"
import { deleteRecallPoint, editRecallPoint, getRecallPoint, type RecallPoint } from "@/ui/api/review"
import { RichContentEditor } from "@/ui/components/RichContentEditor"
import { RichContentRenderer } from "@/ui/components/RichContentRenderer"
import { ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { formatInstanceReference, formatRecallPointReference } from "@/ui/displayIdentifiers"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useProject } from "@/ui/queries/projects"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"
import { setRichContentText } from "@/ui/api/richContent"

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

export function RecallPointPage() {
  const { projectId, recallPointId } = useParams()
  const pid = projectId ?? ""
  const rpid = recallPointId ?? ""
  const nav = useNavigate()
  const qc = useQueryClient()
  const { projectTitle } = useProject(pid)

  const qKey = useMemo(() => ["recallPoint", pid, rpid], [pid, rpid])
  const q = useQuery({
    queryKey: qKey,
    queryFn: () => getRecallPoint(pid, rpid),
    enabled: !!pid && !!rpid,
  })
  const deleteM = useMutation({
    mutationFn: () => deleteRecallPoint(pid, rpid),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["recallPoint", pid] }),
        qc.invalidateQueries({ queryKey: ["recallPointsByInstance", pid] }),
        qc.invalidateQueries({ queryKey: ["recallPointsByTaskNode", pid] }),
        qc.invalidateQueries({ queryKey: ["recallPointsByObjectNode", pid] }),
      ])
      showSuccessFeedback("复述点已删除", "这条复述点已被标记为墓碑，并从当前内容视图中移除。")
      nav(-1)
    },
    onError: (err) => {
      showErrorFeedback("删除复述点失败", formatApiError(err))
    },
  })

  const rp = q.data ?? null

  if (!pid || !rpid) {
    return (
      <div className="space-y-4">
        <ContentNotice
          title="当前页面缺少复述点上下文"
          message="当前链接缺少复述点信息。请返回上一页，或重新从复述点列表进入。"
          action={<Button onClick={() => nav(-1)}>返回</Button>}
        />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">复述点</h1>
          <p className="text-sm text-muted-foreground">
            项目：<span className="font-medium text-foreground">{projectTitle}</span>
          </p>
          <p className="text-sm text-muted-foreground">
            当前引用：<span className="font-medium text-foreground">{formatRecallPointReference(rpid, "复述点待确认")}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          {rp?.state === "ACTIVE" ? (
            <Button
              variant="destructive"
              disabled={deleteM.isPending}
              onClick={() => {
                if (!window.confirm("删除后会将这条复述点标记为墓碑，并从当前内容视图中移除。确定继续吗？")) return
                deleteM.mutate()
              }}
            >
              <Trash2 className="h-4 w-4" />
              {deleteM.isPending ? "删除中..." : "删除"}
            </Button>
          ) : null}
          <Button variant="outline" onClick={() => nav(-1)}>
            返回
          </Button>
          <Button variant="outline" onClick={() => void q.refetch()} disabled={!pid || !rpid || q.isFetching}>
            {q.isFetching ? "刷新中..." : "刷新"}
          </Button>
        </div>
      </div>

      {q.isLoading ? <LoadingNotice title="正在加载复述点" message="正在读取这条复述点的题面、答案和历史理解记录。" /> : null}
      {q.error ? <ErrorNotice title="复述点加载失败" message={formatApiError(q.error)} /> : null}
      {!q.isLoading && !q.error && !rp ? (
        <ContentNotice
          title="未找到这条复述点"
          message="这条复述点可能已经被移除，或者当前链接里的 ID 已经过期。你可以返回上一页重新选择。"
          action={<Button variant="outline" onClick={() => nav(-1)}>返回上一页</Button>}
        />
      ) : null}

      {rp ? (
        <Card>
          <CardHeader>
            <CardTitle>编辑</CardTitle>
            <CardDescription>
              {rp.state === "DELETED" ? "这条复述点已逻辑删除，仅保留历史引用；当前页面不再允许编辑。" : "更新问题、答案和锚点位置。"}
            </CardDescription>
          </CardHeader>
          <RecallPointEditor key={rp.recallPointId} projectId={pid} recallPointId={rpid} qKey={qKey} recallPoint={rp} />
        </Card>
      ) : null}

      {rp ? (
        <Card>
          <CardHeader>
            <CardTitle>历史理解</CardTitle>
            <CardDescription>历史理解记录（只读；在复习提交后追加）。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            {rp.insights.length === 0 ? (
              <div className="flex items-start gap-3 rounded-xl border border-dashed border-border/80 bg-muted/15 px-4 py-4 text-muted-foreground">
                <div className="rounded-2xl bg-slate-100 p-2 text-slate-500">
                  <Sparkles className="h-4 w-4" />
                </div>
                <div className="space-y-1">
                  <p className="font-medium text-foreground">这条复述点还没有历史理解记录</p>
                  <p className="leading-6 text-muted-foreground">
                    后续复习产生新的理解、误区或补充后，记录会继续追加在这里。
                  </p>
                </div>
              </div>
            ) : null}
            {rp.insights.map((it, idx) => (
              <div key={idx} className="rounded-md border bg-muted/20 px-3 py-2">
                <div className="text-xs text-muted-foreground">#{idx + 1}</div>
                <RichContentRenderer projectId={pid} value={it} className="mt-1" />
              </div>
            ))}
          </CardContent>
        </Card>
      ) : null}
    </div>
  )
}

function RecallPointEditor({
  projectId,
  recallPointId,
  qKey,
  recallPoint,
}: {
  projectId: string
  recallPointId: string
  qKey: readonly string[]
  recallPoint: RecallPoint | null
}) {
  const qc = useQueryClient()
  const [question, setQuestion] = useState<RichContent>(() => (recallPoint ? recallPoint.question : richText("")))
  const [answer, setAnswer] = useState<RichContent>(() => (recallPoint ? recallPoint.answer : richText("")))
  const [positionText, setPositionText] = useState(() => recallPoint?.anchor.position ?? "")

  const editM = useMutation({
    mutationFn: async () => {
      if (!recallPoint) throw new Error("RecallPoint not loaded")
      const pos = positionText.trim()
      if (!richContentHasMeaning(question) || !richContentHasMeaning(answer) || !pos) return
      await editRecallPoint(projectId, recallPointId, {
        question,
        answer,
        anchor: { instanceId: recallPoint.anchor.instanceId, position: pos },
      })
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: qKey })
      showSuccessFeedback("复述点已保存", "题面、答案和锚点位置已经更新。")
    },
    onError: (err) => {
      showErrorFeedback("保存复述点失败", formatApiError(err))
    },
  })

  const canSave =
    !!projectId &&
    !!recallPointId &&
    !!recallPoint &&
    recallPoint.state === "ACTIVE" &&
    richContentHasMeaning(question) &&
    richContentHasMeaning(answer) &&
    !!positionText.trim()

  return (
    <CardContent className="space-y-4">
      <div className="grid gap-2">
        <Label htmlFor="anchorInstance">关联材料实例</Label>
        <Input id="anchorInstance" value={formatInstanceReference(recallPoint?.anchor.instanceId ?? "", undefined, "未关联材料实例")} disabled />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="anchorPos">锚点位置</Label>
        <Input id="anchorPos" value={positionText} onChange={(e) => setPositionText(e.target.value)} disabled={!recallPoint || recallPoint.state !== "ACTIVE" || editM.isPending} />
      </div>
      <div className="grid gap-3">
        <Label>问题内容</Label>
        <RichContentEditor
          projectId={projectId}
          field="question"
          value={question}
          disabled={!recallPoint || recallPoint.state !== "ACTIVE" || editM.isPending}
          placeholder="请输入问题/提示语，或直接 Ctrl+V 粘贴图片"
          onTextChange={(text) => setQuestion((prev) => setRichContentText(prev, text))}
          onAppendImage={(assetId) => setQuestion((prev) => appendImageBlock(prev, assetId))}
          onRemoveImage={(imageIndex) => setQuestion((prev) => removeImageBlockAt(prev, imageIndex))}
        />
      </div>
      <div className="grid gap-3">
        <Label>答案内容</Label>
        <RichContentEditor
          projectId={projectId}
          field="answer"
          value={answer}
          disabled={!recallPoint || recallPoint.state !== "ACTIVE" || editM.isPending}
          placeholder="请输入答案/复述内容，或直接 Ctrl+V 粘贴图片"
          onTextChange={(text) => setAnswer((prev) => setRichContentText(prev, text))}
          onAppendImage={(assetId) => setAnswer((prev) => appendImageBlock(prev, assetId))}
          onRemoveImage={(imageIndex) => setAnswer((prev) => removeImageBlockAt(prev, imageIndex))}
        />
      </div>
      <Button onClick={() => editM.mutate()} disabled={!canSave || editM.isPending}>
        {editM.isPending ? "保存中..." : "保存"}
      </Button>
      {editM.error ? <p className="text-sm text-destructive">{formatApiError(editM.error)}</p> : null}
    </CardContent>
  )
}

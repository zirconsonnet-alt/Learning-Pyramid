import { Sparkles } from "lucide-react"
import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { richContentToPlainText, richText } from "@/ui/api/richContent"
import { editRecallPoint, getRecallPoint, type RecallPoint } from "@/ui/api/review"
import { ContentNotice, ErrorNotice, LoadingNotice } from "@/ui/components/contentEmptyState"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useProject } from "@/ui/queries/projects"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"

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
  const { projectTitle } = useProject(pid)

  const qKey = useMemo(() => ["recallPoint", pid, rpid], [pid, rpid])
  const q = useQuery({
    queryKey: qKey,
    queryFn: () => getRecallPoint(pid, rpid),
    enabled: !!pid && !!rpid,
  })

  const rp = q.data ?? null

  if (!pid || !rpid) {
    return (
      <div className="space-y-4">
        <ContentNotice
          title="当前页面缺少复述点上下文"
          message="这个详情页需要同时提供项目 ID 和复述点 ID。你可以先回到上一个页面，或重新从复述点列表进入。"
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
            recallPointId：<span className="font-mono text-foreground">{rpid || "-"}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
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
            <CardDescription>更新 question / answer / anchor.position（不会触发调度副作用）。</CardDescription>
          </CardHeader>
          <RecallPointEditor key={rp.recallPointId} projectId={pid} recallPointId={rpid} qKey={qKey} recallPoint={rp} />
        </Card>
      ) : null}

      {rp ? (
        <Card>
          <CardHeader>
            <CardTitle>历史理解</CardTitle>
            <CardDescription>insights（只读；在复习提交时追加）。</CardDescription>
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
                    当这条复述点在后续复习里被提交新的理解、误区或补充说明后，这里会自动累积对应的 insights。
                  </p>
                </div>
              </div>
            ) : null}
            {rp.insights.map((it, idx) => (
              <div key={idx} className="rounded-md border bg-muted/20 px-3 py-2">
                <div className="text-xs text-muted-foreground">#{idx + 1}</div>
                <div className="mt-1 whitespace-pre-wrap">{richContentToPlainText(it)}</div>
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
  const [questionText, setQuestionText] = useState(() => (recallPoint ? richContentToPlainText(recallPoint.question) : ""))
  const [answerText, setAnswerText] = useState(() => (recallPoint ? richContentToPlainText(recallPoint.answer) : ""))
  const [positionText, setPositionText] = useState(() => recallPoint?.anchor.position ?? "")

  const editM = useMutation({
    mutationFn: async () => {
      if (!recallPoint) throw new Error("RecallPoint not loaded")
      const qText = questionText.trim()
      const aText = answerText.trim()
      const pos = positionText.trim()
      if (!qText || !aText || !pos) return
      await editRecallPoint(projectId, recallPointId, {
        question: richText(qText),
        answer: richText(aText),
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

  const canSave = !!projectId && !!recallPointId && !!recallPoint && !!questionText.trim() && !!answerText.trim() && !!positionText.trim()

  return (
    <CardContent className="space-y-3">
      <div className="grid gap-2">
        <Label htmlFor="anchorInstance">anchor.instanceId</Label>
        <Input id="anchorInstance" value={recallPoint?.anchor.instanceId ?? ""} disabled />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="anchorPos">anchor.position</Label>
        <Input id="anchorPos" value={positionText} onChange={(e) => setPositionText(e.target.value)} disabled={!recallPoint || editM.isPending} />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="qText">question（TEXT）</Label>
        <textarea
          id="qText"
          className="min-h-[80px] w-full rounded-md border bg-background px-3 py-2 text-sm"
          value={questionText}
          onChange={(e) => setQuestionText(e.target.value)}
          disabled={!recallPoint || editM.isPending}
        />
      </div>
      <div className="grid gap-2">
        <Label htmlFor="aText">answer（TEXT）</Label>
        <textarea
          id="aText"
          className="min-h-[80px] w-full rounded-md border bg-background px-3 py-2 text-sm"
          value={answerText}
          onChange={(e) => setAnswerText(e.target.value)}
          disabled={!recallPoint || editM.isPending}
        />
      </div>
      <Button onClick={() => editM.mutate()} disabled={!canSave || editM.isPending}>
        {editM.isPending ? "保存中..." : "保存"}
      </Button>
      {editM.error ? <p className="text-sm text-destructive">{formatApiError(editM.error)}</p> : null}
    </CardContent>
  )
}

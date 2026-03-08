import { useEffect, useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate, useParams } from "react-router-dom"

import { ApiError } from "@/ui/api/http"
import { richContentToPlainText, richText } from "@/ui/api/richContent"
import { editRecallPoint, getRecallPoint } from "@/ui/api/review"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { Input } from "@/ui/components/ui/input"
import { Label } from "@/ui/components/ui/label"
import { useProject } from "@/ui/queries/projects"

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

  const rp = q.data ?? null

  const [questionText, setQuestionText] = useState("")
  const [answerText, setAnswerText] = useState("")
  const [positionText, setPositionText] = useState("")

  useEffect(() => {
    if (!rp) return
    setQuestionText(richContentToPlainText(rp.question))
    setAnswerText(richContentToPlainText(rp.answer))
    setPositionText(rp.anchor.position)
  }, [rp?.recallPointId])

  const editM = useMutation({
    mutationFn: async () => {
      if (!rp) throw new Error("RecallPoint not loaded")
      const qText = questionText.trim()
      const aText = answerText.trim()
      const pos = positionText.trim()
      if (!qText || !aText || !pos) return
      await editRecallPoint(pid, rpid, {
        question: richText(qText),
        answer: richText(aText),
        anchor: { instanceId: rp.anchor.instanceId, position: pos },
      })
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: qKey })
    },
  })

  const canSave = !!pid && !!rpid && !!rp && !!questionText.trim() && !!answerText.trim() && !!positionText.trim()

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

      {q.isLoading ? <p className="text-sm text-muted-foreground">加载中...</p> : null}
      {q.error ? <p className="text-sm text-destructive">{formatApiError(q.error)}</p> : null}

      <Card>
        <CardHeader>
          <CardTitle>编辑</CardTitle>
          <CardDescription>更新 question / answer / anchor.position（不会触发调度副作用）。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-2">
            <Label htmlFor="anchorInstance">anchor.instanceId</Label>
            <Input id="anchorInstance" value={rp?.anchor.instanceId ?? ""} disabled />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="anchorPos">anchor.position</Label>
            <Input id="anchorPos" value={positionText} onChange={(e) => setPositionText(e.target.value)} disabled={!rp || editM.isPending} />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="qText">question（TEXT）</Label>
            <textarea
              id="qText"
              className="min-h-[80px] w-full rounded-md border bg-background px-3 py-2 text-sm"
              value={questionText}
              onChange={(e) => setQuestionText(e.target.value)}
              disabled={!rp || editM.isPending}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="aText">answer（TEXT）</Label>
            <textarea
              id="aText"
              className="min-h-[80px] w-full rounded-md border bg-background px-3 py-2 text-sm"
              value={answerText}
              onChange={(e) => setAnswerText(e.target.value)}
              disabled={!rp || editM.isPending}
            />
          </div>
          <Button onClick={() => editM.mutate()} disabled={!canSave || editM.isPending}>
            {editM.isPending ? "保存中..." : "保存"}
          </Button>
          {editM.error ? <p className="text-sm text-destructive">{formatApiError(editM.error)}</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>历史理解</CardTitle>
          <CardDescription>insights（只读；在复习提交时追加）。</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {(rp?.insights ?? []).length === 0 ? <p className="text-muted-foreground">暂无。</p> : null}
          {(rp?.insights ?? []).map((it, idx) => (
            <div key={idx} className="rounded-md border bg-muted/20 px-3 py-2">
              <div className="text-xs text-muted-foreground">#{idx + 1}</div>
              <div className="mt-1 whitespace-pre-wrap">{richContentToPlainText(it)}</div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}

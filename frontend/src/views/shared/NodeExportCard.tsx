import { useState } from "react"

import { requestAsr, type AsrArtifact } from "@/ui/api/asr"
import { ApiError } from "@/ui/api/http"
import { type RecallPoint } from "@/ui/api/review"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { useSystemCapabilities } from "@/ui/queries/system"
import { showErrorFeedback, showInfoFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"

type NodeExportCardProps = {
  projectId: string
  nodeTitle: string
  recallPoints: RecallPoint[]
  exportRecallPoints: () => Promise<RecallPoint[]>
  exportAsr: () => Promise<AsrArtifact[]>
}

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
}

function parseAnchorCenterMs(position: string) {
  const match = String(position).trim().match(/^t=(\d+)$/)
  if (!match) return null
  const value = Number(match[1])
  return Number.isFinite(value) ? value : null
}

function sanitizeFilenamePart(value: string) {
  const trimmed = value.trim()
  const normalized = trimmed.replace(/[\\/:*?"<>|]+/g, "-").replace(/\s+/g, "-")
  return normalized || "node"
}

function downloadJson(filename: string, payload: unknown) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export function NodeExportCard(props: NodeExportCardProps) {
  const { projectId, nodeTitle, recallPoints, exportRecallPoints, exportAsr } = props
  const capabilitiesQ = useSystemCapabilities()
  const [statusText, setStatusText] = useState<string | null>(null)
  const [errorText, setErrorText] = useState<string | null>(null)
  const [isExportingRecall, setIsExportingRecall] = useState(false)
  const [isExportingAsr, setIsExportingAsr] = useState(false)
  const asrEnabled = capabilitiesQ.data?.asrEnabled ?? true

  async function onExportRecallPoints() {
    setErrorText(null)
    setStatusText(null)
    setIsExportingRecall(true)
    try {
      const items = await exportRecallPoints()
      const fileStem = sanitizeFilenamePart(nodeTitle)
      downloadJson(`${fileStem}-recall-points.json`, {
        exportedAt: new Date().toISOString(),
        nodeTitle,
        recallPoints: items,
      })
      const message = items.length > 0 ? `已导出 ${items.length} 条复述点。` : "当前节点还没有复述点，已导出空结果。"
      setStatusText(message)
      showSuccessFeedback("复述点 JSON 已导出", message)
    } catch (err) {
      const message = formatApiError(err)
      setErrorText(message)
      showErrorFeedback("导出复述点失败", message)
    } finally {
      setIsExportingRecall(false)
    }
  }

  async function onExportAsr() {
    setErrorText(null)
    setStatusText(null)
    setIsExportingAsr(true)
    try {
      showInfoFeedback("开始生成 ASR", `正在为“${nodeTitle}”下的 ${recallPoints.length} 条复述点准备转写结果。`)
      const missingAnchorIds = recallPoints
        .filter((item) => parseAnchorCenterMs(item.anchor.position) === null)
        .map((item) => item.recallPointId)
      if (missingAnchorIds.length > 0) {
        throw new Error(`以下复述点缺少 t=<ms> 锚点，无法自动请求 ASR：${missingAnchorIds.join(", ")}`)
      }

      for (let index = 0; index < recallPoints.length; index += 1) {
        const item = recallPoints[index]
        const centerMs = parseAnchorCenterMs(item.anchor.position)
        if (centerMs === null) continue
        setStatusText(`正在生成 ASR ${index + 1}/${recallPoints.length}...`)
        await requestAsr(projectId, {
          recallPointId: item.recallPointId,
          centerMs,
          preMs: 30_000,
          postMs: 30_000,
          provider: "WHISPER",
        })
      }

      const items = await exportAsr()
      const fileStem = sanitizeFilenamePart(nodeTitle)
      downloadJson(`${fileStem}-asr.json`, {
        exportedAt: new Date().toISOString(),
        nodeTitle,
        asrArtifacts: items,
      })
      const message = `已导出 ${items.length} 条 ASR 转写结果。`
      setStatusText(message)
      showSuccessFeedback("ASR JSON 已导出", message)
    } catch (err) {
      const message = formatApiError(err)
      setErrorText(message)
      showErrorFeedback("导出 ASR 失败", message)
    } finally {
      setIsExportingAsr(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{asrEnabled ? "导出与 ASR" : "导出"}</CardTitle>
        <CardDescription>
          {asrEnabled
            ? "导出当前节点覆盖的复述点数据，并按复述点锚点批量生成或复用 ASR 转写结果。"
            : "导出当前节点覆盖的复述点数据。当前部署已禁用 ASR。"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className={`grid gap-3 ${asrEnabled ? "md:grid-cols-2" : ""}`}>
          <div className="rounded-md border bg-muted/30 p-3">
            <div className="text-xs text-muted-foreground">覆盖复述点</div>
            <div className="mt-1 font-medium text-foreground">{recallPoints.length}</div>
          </div>
          {asrEnabled ? (
            <div className="rounded-md border bg-muted/30 p-3">
              <div className="text-xs text-muted-foreground">ASR 窗口</div>
              <div className="mt-1 font-medium text-foreground">center ± 30s</div>
            </div>
          ) : null}
        </div>

        {recallPoints.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border/80 bg-muted/15 px-4 py-4 text-sm text-muted-foreground">
            当前节点还没有可导出的复述点。先完成节点绑定、生成复述点后，再导出 JSON 或发起 ASR。
          </div>
        ) : null}

        <div className="flex flex-wrap gap-3">
          <Button onClick={() => void onExportRecallPoints()} disabled={isExportingRecall || recallPoints.length === 0}>
            {isExportingRecall ? "导出中..." : "导出复述点 JSON"}
          </Button>
          {asrEnabled ? (
            <Button
              variant="outline"
              onClick={() => void onExportAsr()}
              disabled={isExportingAsr || recallPoints.length === 0}
            >
              {isExportingAsr ? "处理中..." : "生成并导出 ASR JSON"}
            </Button>
          ) : null}
        </div>

        {asrEnabled ? (
          <p className="text-xs text-muted-foreground">
            ASR 导出会对当前节点下每个复述点调用一次 `request_asr`；已存在的缓存结果会被直接复用。
          </p>
        ) : null}
        {statusText ? <div className="rounded-md border bg-muted/20 px-3 py-2 text-sm text-muted-foreground">{statusText}</div> : null}
        {errorText ? <div className="rounded-md border border-destructive/20 bg-destructive/5 px-3 py-2 text-sm text-destructive">{errorText}</div> : null}
      </CardContent>
    </Card>
  )
}

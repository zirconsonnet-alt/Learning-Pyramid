import { useState } from "react"

import { requestAsr, type AsrArtifact } from "@/ui/api/asr"
import { ApiError } from "@/ui/api/http"
import { type RecallPoint } from "@/ui/api/review"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/ui/components/ui/card"

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
  const [statusText, setStatusText] = useState<string | null>(null)
  const [errorText, setErrorText] = useState<string | null>(null)
  const [isExportingRecall, setIsExportingRecall] = useState(false)
  const [isExportingAsr, setIsExportingAsr] = useState(false)

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
      setStatusText(`已导出 ${items.length} 条复述点。`)
    } catch (err) {
      setErrorText(formatApiError(err))
    } finally {
      setIsExportingRecall(false)
    }
  }

  async function onExportAsr() {
    setErrorText(null)
    setStatusText(null)
    setIsExportingAsr(true)
    try {
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
      setStatusText(`已导出 ${items.length} 条 ASR 转写结果。`)
    } catch (err) {
      setErrorText(formatApiError(err))
    } finally {
      setIsExportingAsr(false)
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>导出与 ASR</CardTitle>
        <CardDescription>导出当前节点覆盖的复述点数据，并按复述点锚点批量生成或复用 ASR 转写结果。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-md border bg-muted/30 p-3">
            <div className="text-xs text-muted-foreground">覆盖复述点</div>
            <div className="mt-1 font-medium text-foreground">{recallPoints.length}</div>
          </div>
          <div className="rounded-md border bg-muted/30 p-3">
            <div className="text-xs text-muted-foreground">ASR 窗口</div>
            <div className="mt-1 font-medium text-foreground">center ± 30s</div>
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          <Button onClick={() => void onExportRecallPoints()} disabled={isExportingRecall}>
            {isExportingRecall ? "导出中..." : "导出复述点 JSON"}
          </Button>
          <Button
            variant="outline"
            onClick={() => void onExportAsr()}
            disabled={isExportingAsr || recallPoints.length === 0}
          >
            {isExportingAsr ? "处理中..." : "生成并导出 ASR JSON"}
          </Button>
        </div>

        <p className="text-xs text-muted-foreground">
          ASR 导出会对当前节点下每个复述点调用一次 `request_asr`；已存在的缓存结果会被直接复用。
        </p>
        {statusText ? <p className="text-sm text-muted-foreground">{statusText}</p> : null}
        {errorText ? <p className="text-sm text-destructive">{errorText}</p> : null}
      </CardContent>
    </Card>
  )
}

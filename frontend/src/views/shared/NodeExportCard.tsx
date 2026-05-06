import { useState } from "react"
import { Download, FileJson } from "lucide-react"

import { ApiError } from "@/ui/api/http"
import { type RecallPoint } from "@/ui/api/review"
import { Button } from "@/ui/components/ui/button"
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/ui/components/ui/dialog"
import { showErrorFeedback, showSuccessFeedback } from "@/ui/store/feedbackStore"

type NodeExportCardProps = {
  projectId: string
  nodeTitle: string
  recallPoints: RecallPoint[]
  exportRecallPoints: () => Promise<RecallPoint[]>
}

function formatApiError(err: unknown) {
  if (err instanceof ApiError) return `${err.code}: ${err.message}`
  if (err instanceof Error) return err.message
  return "未知错误"
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
  const { nodeTitle, recallPoints, exportRecallPoints } = props
  const [open, setOpen] = useState(false)
  const [statusText, setStatusText] = useState<string | null>(null)
  const [errorText, setErrorText] = useState<string | null>(null)
  const [isExportingRecall, setIsExportingRecall] = useState(false)
  const canExport = recallPoints.length > 0 && !isExportingRecall

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
      setOpen(false)
      showSuccessFeedback("复述点 JSON 已导出", message)
    } catch (err) {
      const message = formatApiError(err)
      setErrorText(message)
      showErrorFeedback("导出复述点失败", message)
    } finally {
      setIsExportingRecall(false)
    }
  }

  return (
    <>
      <Button type="button" variant="outline" size="sm" className="rounded-full" onClick={() => setOpen(true)} disabled={!canExport}>
        <Download className="h-4 w-4" />
        导出
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-xl rounded-[1.6rem] border-[#dbe4ee] bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(246,249,253,0.96))] p-0">
          <div className="space-y-5 p-6">
            <DialogHeader className="space-y-2 text-left">
              <DialogTitle>导出复述点</DialogTitle>
            </DialogHeader>

            <div className="grid gap-3">
              <div className="rounded-[1.1rem] border border-[#dbe4ee] bg-white/90 p-4">
                <div className="text-xs uppercase tracking-[0.14em] text-[#8a9ab0]">覆盖复述点</div>
                <div className="mt-2 text-2xl font-semibold tracking-tight text-[#17314b]">{recallPoints.length}</div>
              </div>
            </div>

            {statusText ? <div className="rounded-[1rem] border border-[#dbe4ee] bg-white/80 px-4 py-3 text-sm text-[#5c6f86]">{statusText}</div> : null}
            {errorText ? <div className="rounded-[1rem] border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">{errorText}</div> : null}
          </div>

          <DialogFooter className="flex-col items-stretch gap-3 border-t border-[#e2e8ef] bg-white/70 px-6 py-4 sm:items-end">
            <div className="text-sm text-[#5c6f86]">
              导出格式：<span className="font-semibold text-[#17314b]">JSON, MD, PDF</span>
            </div>
            <Button type="button" onClick={() => void onExportRecallPoints()} disabled={isExportingRecall || recallPoints.length === 0}>
              <FileJson className="h-4 w-4" />
              {isExportingRecall ? "导出中..." : "导出"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

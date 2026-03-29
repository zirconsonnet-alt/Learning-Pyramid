import { useState } from "react"
import { Download, FileJson } from "lucide-react"

import { ApiError } from "@/ui/api/http"
import { type RecallPoint } from "@/ui/api/review"
import { Button } from "@/ui/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/ui/components/ui/dialog"
import { SUPPORTED_SUBTITLE_EXTENSIONS_LABEL } from "@/ui/subtitles/subtitleSupport"
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
              <DialogDescription>导出当前节点覆盖的复述点数据。视频字幕不再由 ASR 生成，而是直接读取视频同目录下的同名字幕文件。</DialogDescription>
            </DialogHeader>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-[1.1rem] border border-[#dbe4ee] bg-white/90 p-4">
                <div className="text-xs uppercase tracking-[0.14em] text-[#8a9ab0]">覆盖复述点</div>
                <div className="mt-2 text-2xl font-semibold tracking-tight text-[#17314b]">{recallPoints.length}</div>
              </div>
              <div className="rounded-[1.1rem] border border-[#dbe4ee] bg-white/90 p-4">
                <div className="text-xs uppercase tracking-[0.14em] text-[#8a9ab0]">字幕来源</div>
                <div className="mt-2 text-sm font-semibold tracking-tight text-[#17314b]">同目录同名字幕文件</div>
              </div>
            </div>

            {statusText ? <div className="rounded-[1rem] border border-[#dbe4ee] bg-white/80 px-4 py-3 text-sm text-[#5c6f86]">{statusText}</div> : null}
            {errorText ? <div className="rounded-[1rem] border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">{errorText}</div> : null}

            <div className="rounded-[1rem] border border-dashed border-[#dbe4ee] bg-[#fbfdff] px-4 py-3 text-xs leading-6 text-[#6a7b90]">
              系统现在只会识别视频同目录下的同名字幕文件（{SUPPORTED_SUBTITLE_EXTENSIONS_LABEL}），并把它用于播放器字幕或 AI 上下文；不会再用后端 ffmpeg 或浏览器 ffmpeg.wasm 生成转写结果。
            </div>
          </div>

          <DialogFooter className="border-t border-[#e2e8ef] bg-white/70 px-6 py-4">
            <Button type="button" onClick={() => void onExportRecallPoints()} disabled={isExportingRecall || recallPoints.length === 0}>
              <FileJson className="h-4 w-4" />
              {isExportingRecall ? "导出中..." : "导出复述点 JSON"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}

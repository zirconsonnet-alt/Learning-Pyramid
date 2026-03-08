import { useEffect, useMemo, useRef } from "react"

import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import type { Instance } from "@/ui/api/instances"

export function VideoPane({
  projectId,
  instance,
  setCurrentMs,
  seekTo,
  onSeekApplied,
}: {
  projectId: string
  instance: Instance | null
  setCurrentMs: (v: number) => void
  seekTo?: { instanceId: string; ms: number; nonce: number } | null
  onSeekApplied?: (nonce: number) => void
}) {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const pendingSeekRef = useRef<{ instanceId: string; ms: number; nonce: number } | null>(null)
  const lastAppliedNonceRef = useRef<number | null>(null)
  const instanceId = instance?.instanceId ?? null

  const src = useMemo(() => {
    if (!instance) return null
    return `/api/projects/${projectId}/media/instances/${instance.instanceId}`
  }, [instance, projectId])

  useEffect(() => {
    if (!seekTo) return
    if (lastAppliedNonceRef.current === seekTo.nonce) return
    pendingSeekRef.current = seekTo
    const v = videoRef.current
    if (!instanceId || instanceId !== seekTo.instanceId) return
    if (!v || v.readyState < 1) return
    v.currentTime = Math.max(0, seekTo.ms / 1000)
    setCurrentMs(seekTo.ms)
    pendingSeekRef.current = null
    lastAppliedNonceRef.current = seekTo.nonce
    onSeekApplied?.(seekTo.nonce)
  }, [instanceId, onSeekApplied, seekTo, setCurrentMs])

  function handleTimeUpdate() {
    const v = videoRef.current
    if (!v) return
    setCurrentMs(Math.max(0, Math.floor(v.currentTime * 1000)))
  }

  function seekToMs(ms: number) {
    const v = videoRef.current
    if (!v) return
    v.currentTime = Math.max(0, ms / 1000)
  }

  function tryApplyPendingSeek() {
    const req = pendingSeekRef.current
    if (!req) return
    if (!instance || instance.instanceId !== req.instanceId) return
    const v = videoRef.current
    if (!v) return
    if (v.readyState < 1) return
    seekToMs(req.ms)
    setCurrentMs(req.ms)
    pendingSeekRef.current = null
    lastAppliedNonceRef.current = req.nonce
    onSeekApplied?.(req.nonce)
  }

  return (
    <Card className="theme-card-main overflow-hidden">
      <CardHeader className="theme-card-header flex-row items-center justify-between gap-3 space-y-0">
        <CardTitle>视频</CardTitle>
        {instance ? (
          <div className="theme-meta">{instance.materialDisplayName}</div>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-4 pt-5">
        {src ? (
          <video
            ref={videoRef}
            className="w-full rounded-[1.2rem] border border-slate-900/10 bg-[#0f172a]"
            src={src}
            controls
            playsInline
            onLoadedMetadata={tryApplyPendingSeek}
            onCanPlay={tryApplyPendingSeek}
            onTimeUpdate={handleTimeUpdate}
            onSeeked={handleTimeUpdate}
          />
        ) : (
          <div className="theme-canvas rounded-[1.2rem] border border-border/60 p-5 text-sm text-muted-foreground">
            请先在左侧选择一个视频实例。
          </div>
        )}
      </CardContent>
    </Card>
  )
}

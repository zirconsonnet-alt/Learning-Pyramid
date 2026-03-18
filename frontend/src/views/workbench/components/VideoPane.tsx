import { useEffect, useMemo, useRef, useState } from "react"
import { Film, VideoOff } from "lucide-react"

import type { Instance } from "@/ui/api/instances"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { resolveProjectFile, useProjectDirectoryBinding } from "@/ui/localMedia/projectDirectory"
import { useSystemCapabilities } from "@/ui/queries/system"
import { clearPlaybackResumeMs, loadPlaybackResumeMs, savePlaybackResumeMs } from "@/ui/store/playbackResume"

function isRelativeMaterialId(materialId: string) {
  const normalized = String(materialId).replace(/\\/g, "/").trim()
  if (!normalized) return false
  if (normalized.startsWith("/")) return false
  if (/^[A-Za-z]:\//.test(normalized)) return false
  return !normalized.split("/").some((part) => part === "." || part === "..")
}

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
  const restoreSavedPositionRef = useRef(true)
  const lastPersistedPlaybackSecondRef = useRef<number | null>(null)

  const [localSrc, setLocalSrc] = useState<string | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)
  const [mediaElementError, setMediaElementError] = useState<string | null>(null)

  const instanceId = instance?.instanceId ?? null
  const capabilitiesQ = useSystemCapabilities()
  const directoryBinding = useProjectDirectoryBinding(projectId)
  const isHostedMode = capabilitiesQ.data?.appMode === "hosted"
  const serverMediaStreamEnabled = capabilitiesQ.data?.serverMediaStreamEnabled ?? false
  const browserLocalMediaEnabled = capabilitiesQ.data?.browserLocalMediaEnabled ?? false

  useEffect(() => {
    setMediaElementError(null)
    restoreSavedPositionRef.current = true
    lastPersistedPlaybackSecondRef.current = null
  }, [instance?.instanceId, localSrc, serverMediaStreamEnabled])

  useEffect(() => {
    let cancelled = false
    let objectUrl: string | null = null

    async function loadLocalMedia() {
      if (serverMediaStreamEnabled || !instance) {
        if (!cancelled) {
          setLocalSrc(null)
          setLocalError(null)
        }
        return
      }
      if (!browserLocalMediaEnabled) {
        setLocalSrc(null)
        setLocalError("当前部署未启用浏览器本地媒体访问。")
        return
      }
      if (directoryBinding.permission === "missing") {
        setLocalSrc(null)
        setLocalError("尚未绑定本地素材目录。请到项目设置里完成授权。")
        return
      }
      if (directoryBinding.permission === "prompt") {
        setLocalSrc(null)
        setLocalError("已记录本地素材目录，但当前浏览器还未授予读取权限。请到项目设置里重新授权。")
        return
      }
      if (directoryBinding.permission === "denied") {
        setLocalSrc(null)
        setLocalError("浏览器已拒绝本地素材目录访问。请到项目设置里重新授权。")
        return
      }
      if (!isRelativeMaterialId(instance.materialId)) {
        setLocalSrc(null)
        setLocalError("当前实例仍是旧的绝对路径语义，无法在网页模式下直接解析。")
        return
      }

      try {
        const file = await resolveProjectFile(projectId, instance.materialId)
        if (!file) {
          setLocalSrc(null)
          setLocalError("未能在已授权目录下找到该视频文件。请检查目录是否正确，必要时重新选择目录。")
          return
        }
        objectUrl = URL.createObjectURL(file)
        if (cancelled) {
          URL.revokeObjectURL(objectUrl)
          return
        }
        setLocalSrc(objectUrl)
        setLocalError(null)
      } catch (err) {
        setLocalSrc(null)
        setLocalError(err instanceof Error ? err.message : "读取本地视频失败")
      }
    }

    void loadLocalMedia()

    return () => {
      cancelled = true
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl)
      }
    }
  }, [
    browserLocalMediaEnabled,
    directoryBinding.permission,
    instance,
    projectId,
    serverMediaStreamEnabled,
  ])

  const src = useMemo(() => {
    if (!instance) return null
    if (serverMediaStreamEnabled) {
      return `/api/projects/${projectId}/media/instances/${instance.instanceId}`
    }
    return localSrc
  }, [instance, localSrc, projectId, serverMediaStreamEnabled])

  const playbackError = useMemo(() => {
    if (!instance) return null
    if (mediaElementError) return mediaElementError
    if (!serverMediaStreamEnabled) return localError
    return null
  }, [instance, localError, mediaElementError, serverMediaStreamEnabled])

  useEffect(() => {
    if (!seekTo) return
    if (lastAppliedNonceRef.current === seekTo.nonce) return
    pendingSeekRef.current = seekTo
    const video = videoRef.current
    if (!instanceId || instanceId !== seekTo.instanceId) return
    if (!video || video.readyState < 1) return
    video.currentTime = Math.max(0, seekTo.ms / 1000)
    setCurrentMs(seekTo.ms)
    pendingSeekRef.current = null
    lastAppliedNonceRef.current = seekTo.nonce
    onSeekApplied?.(seekTo.nonce)
  }, [instanceId, onSeekApplied, seekTo, setCurrentMs])

  function handleTimeUpdate() {
    const video = videoRef.current
    if (!video) return
    const nextMs = Math.max(0, Math.floor(video.currentTime * 1000))
    setCurrentMs(nextMs)
    if (!instanceId) return
    const currentSecond = Math.floor(nextMs / 1000)
    if (lastPersistedPlaybackSecondRef.current === currentSecond) return
    lastPersistedPlaybackSecondRef.current = currentSecond
    savePlaybackResumeMs(projectId, instanceId, nextMs)
  }

  function seekToMs(ms: number) {
    const video = videoRef.current
    if (!video) return
    video.currentTime = Math.max(0, ms / 1000)
  }

  function tryApplyPendingSeek() {
    const req = pendingSeekRef.current
    if (!req || !instance || instance.instanceId !== req.instanceId) return
    const video = videoRef.current
    if (!video || video.readyState < 1) return
    seekToMs(req.ms)
    setCurrentMs(req.ms)
    pendingSeekRef.current = null
    lastAppliedNonceRef.current = req.nonce
    onSeekApplied?.(req.nonce)
  }

  function tryRestoreSavedPlaybackPosition() {
    if (!restoreSavedPositionRef.current || !instanceId) return
    const savedMs = loadPlaybackResumeMs(projectId, instanceId)
    restoreSavedPositionRef.current = false
    if (savedMs === null) return
    const video = videoRef.current
    if (!video) return
    const durationMs = Number.isFinite(video.duration) && video.duration > 0 ? Math.floor(video.duration * 1000) : null
    const targetMs = durationMs === null ? savedMs : Math.min(savedMs, Math.max(0, durationMs - 1000))
    if (targetMs <= 0) return
    seekToMs(targetMs)
    setCurrentMs(targetMs)
  }

  function handleLoadedMetadata() {
    setMediaElementError(null)
    tryApplyPendingSeek()
    tryRestoreSavedPlaybackPosition()
  }

  function handleCanPlay() {
    tryApplyPendingSeek()
    tryRestoreSavedPlaybackPosition()
  }

  function handleVideoError() {
    const video = videoRef.current
    const mediaError = video?.error
    if (!mediaError) {
      setMediaElementError("当前浏览器无法播放该视频。")
      return
    }
    const messageByCode: Record<number, string> = {
      1: "视频加载被中断。",
      2: "视频下载失败。",
      3: "视频解码失败。",
      4: "当前浏览器不支持该视频格式。",
    }
    setMediaElementError(messageByCode[mediaError.code] ?? "当前浏览器无法播放该视频。")
  }

  function handleEnded() {
    if (!instanceId) return
    clearPlaybackResumeMs(projectId, instanceId)
    lastPersistedPlaybackSecondRef.current = null
  }

  const shouldRenderVideo = Boolean(src)

  return (
    <Card className="theme-card-main overflow-hidden">
      <CardHeader className="theme-card-header flex-row items-start justify-between gap-3 space-y-0">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#edf4ff] text-primary">
            <Film className="h-5 w-5" />
          </div>
          <div className="space-y-1">
            <CardTitle>当前视频</CardTitle>
            <p className="text-sm text-muted-foreground">
              {instance ? "围绕当前实例完成播放、锚点定位和复述点录入。" : "先从左侧内容目录里选择一个视频实例。"}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {isHostedMode ? <div className="theme-meta">Hosted</div> : null}
          {instance ? <div className="theme-meta">{instance.materialDisplayName}</div> : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-4 pt-5">
        {shouldRenderVideo ? (
          <video
            ref={videoRef}
            className="w-full rounded-[1.2rem] border border-slate-900/10 bg-[#0f172a]"
            src={src ?? undefined}
            controls
            playsInline
            onLoadedData={() => setMediaElementError(null)}
            onLoadedMetadata={handleLoadedMetadata}
            onCanPlay={handleCanPlay}
            onError={handleVideoError}
            onEnded={handleEnded}
            onTimeUpdate={handleTimeUpdate}
            onSeeked={handleTimeUpdate}
          />
        ) : (
          <div className="theme-canvas rounded-[1.2rem] border border-border/60 p-6 text-sm text-muted-foreground">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-white/80 text-[#5f7188]">
                <VideoOff className="h-5 w-5" />
              </div>
              <div className="space-y-1.5">
                <div className="text-sm font-medium text-foreground">当前视频还未进入可播放状态</div>
                <div>
                  {instance
                    ? playbackError ?? (!serverMediaStreamEnabled ? "正在准备播放资源..." : "当前视频暂时不可用。")
                    : "请先在左侧选择一个视频实例。"}
                </div>
              </div>
            </div>
          </div>
        )}
        {shouldRenderVideo && playbackError ? <div className="text-sm text-amber-700">{playbackError}</div> : null}
      </CardContent>
    </Card>
  )
}

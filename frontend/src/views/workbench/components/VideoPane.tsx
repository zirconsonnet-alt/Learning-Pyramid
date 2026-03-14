import { useEffect, useMemo, useRef, useState } from "react"
import { Film, RadioTower, VideoOff } from "lucide-react"

import type { PlaybackDescriptor } from "@/ui/api/mediaPlayback"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import type { Instance } from "@/ui/api/instances"
import { ApiError } from "@/ui/api/http"
import { resolveProjectFile, useProjectDirectoryBinding } from "@/ui/localMedia/projectDirectory"
import { useSystemCapabilities } from "@/ui/queries/system"
import { usePlaybackDescriptor } from "@/ui/queries/workbench"
import { clearPlaybackResumeMs, loadPlaybackResumeMs, savePlaybackResumeMs } from "@/ui/store/playbackResume"

function isRelativeMaterialId(materialId: string) {
  const normalized = String(materialId).replace(/\\/g, "/").trim()
  if (!normalized) return false
  if (normalized.startsWith("/")) return false
  if (/^[A-Za-z]:\//.test(normalized)) return false
  return !normalized.split("/").some((part) => part === "." || part === "..")
}

function browserSupportsNativeHls() {
  if (typeof document === "undefined") return false
  const video = document.createElement("video")
  return Boolean(video.canPlayType("application/vnd.apple.mpegurl"))
}

function browserPrefersResilientHls() {
  if (typeof navigator === "undefined") return false
  const hintedNavigator = navigator as Navigator & { userAgentData?: { mobile?: boolean } }
  if (hintedNavigator.userAgentData?.mobile) return true
  const userAgent = String(navigator.userAgent ?? "").toLowerCase()
  return /android|iphone|ipad|ipod|mobile|harmonyos/.test(userAgent)
}

const MOBILE_HLS_FALLBACK_DELAY_MS = 6_000

function supportsProgressiveHostedFallback(descriptor: PlaybackDescriptor | null | undefined) {
  if (!descriptor || descriptor.mode !== "relay_hls") return false
  return descriptor.decisionReason === "prefer_hls:progressive_supported"
}

function shouldWaitForHostedHls(descriptor: PlaybackDescriptor | null | undefined) {
  if (!descriptor) return false
  if (!supportsProgressiveHostedFallback(descriptor)) return false
  return !descriptor.ready && (!descriptor.reason || descriptor.reason === "transcode_pending")
}

function isHostedHlsTerminalFailure(descriptor: PlaybackDescriptor | null | undefined) {
  if (!descriptor) return false
  if (!supportsProgressiveHostedFallback(descriptor)) return false
  return !descriptor.ready && Boolean(descriptor.reason && descriptor.reason !== "transcode_pending")
}

function formatHostedHlsReason(reason: string | null | undefined) {
  const normalized = String(reason ?? "").trim()
  if (!normalized || normalized === "transcode_pending") return "正在准备 HLS 转码流..."
  if (normalized === "transcode_failed") return "HLS 转码失败。"
  if (normalized === "transcode_cancelled") return "HLS 转码已取消。"
  return `HLS 转码失败: ${normalized}`
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
  const [managedHlsError, setManagedHlsError] = useState<string | null>(null)
  const [mediaElementError, setMediaElementError] = useState<string | null>(null)
  const [forceHostedHls, setForceHostedHls] = useState(false)
  const [disablePreferredHls, setDisablePreferredHls] = useState(false)
  const [hlsReloadNonce, setHlsReloadNonce] = useState(0)
  const instanceId = instance?.instanceId ?? null
  const capabilitiesQ = useSystemCapabilities()
  const directoryBinding = useProjectDirectoryBinding(projectId)
  const isHostedMode = capabilitiesQ.data?.appMode === "hosted"
  const serverMediaStreamEnabled = capabilitiesQ.data?.serverMediaStreamEnabled ?? false
  const browserLocalMediaEnabled = capabilitiesQ.data?.browserLocalMediaEnabled ?? false
  const mobilePrefersHostedHls = useMemo(() => browserPrefersResilientHls(), [])
  const preferHostedHls = forceHostedHls || (mobilePrefersHostedHls && !disablePreferredHls)
  const playbackDescriptorQ = usePlaybackDescriptor(projectId, instanceId, isHostedMode, { preferHls: preferHostedHls })
  const playbackDescriptor = playbackDescriptorQ.data
  const canFallbackToProgressive = supportsProgressiveHostedFallback(playbackDescriptor)
  const nativeHlsSupported = useMemo(() => browserSupportsNativeHls(), [])
  const wantsManagedHls = useMemo(() => {
    if (!instance || !isHostedMode) return false
    return Boolean(
      playbackDescriptor &&
        playbackDescriptor.mode === "relay_hls" &&
        playbackDescriptor.ready &&
        playbackDescriptor.manifestUrl &&
        !nativeHlsSupported,
    )
  }, [instance, isHostedMode, nativeHlsSupported, playbackDescriptor])

  const managedHlsManifestUrl = useMemo(() => {
    return wantsManagedHls ? playbackDescriptor?.manifestUrl ?? null : null
  }, [playbackDescriptor, wantsManagedHls])

  const src = useMemo(() => {
    if (!instance) return null
    if (isHostedMode) {
      if (!playbackDescriptor) return null
      if (playbackDescriptor.mode === "relay_hls") {
        if (!playbackDescriptor.ready) return null
        return nativeHlsSupported ? playbackDescriptor.manifestUrl ?? null : null
      }
      return playbackDescriptor.url ?? null
    }
    if (serverMediaStreamEnabled) {
      return `/api/projects/${projectId}/media/instances/${instance.instanceId}`
    }
    return localSrc
  }, [
    instance,
    isHostedMode,
    localSrc,
    nativeHlsSupported,
    playbackDescriptor,
    projectId,
    serverMediaStreamEnabled,
  ])
  const shouldRenderVideo = Boolean(src || (wantsManagedHls && !managedHlsError))

  useEffect(() => {
    const video = videoRef.current
    if (!video || !managedHlsManifestUrl) {
      setManagedHlsError(null)
      return
    }
    let cancelled = false
    let cleanup: (() => void) | null = null
    setManagedHlsError(null)
    void import("hls.js/light")
      .then(({ default: Hls }) => {
        if (cancelled) return
        if (!Hls.isSupported()) {
          if (canFallbackToProgressive && !forceHostedHls) {
            setDisablePreferredHls(true)
            return
          }
          setManagedHlsError("当前浏览器不支持 HLS 播放。")
          return
        }
        let networkRecoveryCount = 0
        let mediaRecoveryCount = 0
        const hls = new Hls({
          enableWorker: true,
          lowLatencyMode: false,
        })
        const handleError = (_event: string, data: { fatal?: boolean; details?: string; type?: string }) => {
          if (!data.fatal || cancelled) return
          if (data.type === Hls.ErrorTypes.NETWORK_ERROR && networkRecoveryCount < 3) {
            networkRecoveryCount += 1
            window.setTimeout(() => {
              if (cancelled) return
              setManagedHlsError(null)
              hls.startLoad()
            }, 500 * networkRecoveryCount)
            return
          }
          if (data.type === Hls.ErrorTypes.MEDIA_ERROR && mediaRecoveryCount < 1) {
            mediaRecoveryCount += 1
            setManagedHlsError(null)
            hls.recoverMediaError()
            return
          }
          if (canFallbackToProgressive && !forceHostedHls) {
            setManagedHlsError(null)
            setMediaElementError(null)
            setDisablePreferredHls(true)
            hls.destroy()
            return
          }
          setManagedHlsError(`HLS 播放失败: ${data.details ?? data.type ?? "unknown_error"}`)
          hls.destroy()
        }
        hls.on(Hls.Events.ERROR, handleError)
        hls.loadSource(managedHlsManifestUrl)
        hls.attachMedia(video)
        cleanup = () => {
          hls.off(Hls.Events.ERROR, handleError)
          hls.destroy()
          video.removeAttribute("src")
          video.load()
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return
        if (canFallbackToProgressive && !forceHostedHls) {
          setDisablePreferredHls(true)
          return
        }
        setManagedHlsError(err instanceof Error ? err.message : "HLS 播放初始化失败")
      })
    return () => {
      cancelled = true
      cleanup?.()
    }
  }, [canFallbackToProgressive, forceHostedHls, hlsReloadNonce, managedHlsManifestUrl])

  useEffect(() => {
    if (!isHostedMode || !instanceId) return

    function requestPlaybackRecovery() {
      const video = videoRef.current
      if (video && instanceId) {
        savePlaybackResumeMs(projectId, instanceId, Math.max(0, Math.floor(video.currentTime * 1000)))
      }
      setManagedHlsError(null)
      setMediaElementError(null)
      setHlsReloadNonce((value) => value + 1)
      void playbackDescriptorQ.refetch()
    }

    function handleOnline() {
      if (!managedHlsError && !mediaElementError) return
      requestPlaybackRecovery()
    }

    function handleVisibilityChange() {
      if (document.visibilityState !== "visible") return
      if (!managedHlsError && !mediaElementError && !(playbackDescriptor?.mode === "relay_hls" && !playbackDescriptor.ready)) return
      requestPlaybackRecovery()
    }

    window.addEventListener("online", handleOnline)
    document.addEventListener("visibilitychange", handleVisibilityChange)
    return () => {
      window.removeEventListener("online", handleOnline)
      document.removeEventListener("visibilitychange", handleVisibilityChange)
    }
  }, [
    instanceId,
    isHostedMode,
    managedHlsError,
    mediaElementError,
    playbackDescriptor?.mode,
    playbackDescriptor?.ready,
    playbackDescriptorQ,
    projectId,
  ])

  useEffect(() => {
    setForceHostedHls(false)
    setDisablePreferredHls(false)
  }, [instance?.instanceId])

  useEffect(() => {
    if (!isHostedMode || !mobilePrefersHostedHls || forceHostedHls || disablePreferredHls) return
    if (isHostedHlsTerminalFailure(playbackDescriptor)) {
      setManagedHlsError(null)
      setMediaElementError(null)
      setDisablePreferredHls(true)
      return
    }
    if (!shouldWaitForHostedHls(playbackDescriptor)) return
    const timeoutId = window.setTimeout(() => {
      setManagedHlsError(null)
      setMediaElementError(null)
      setDisablePreferredHls(true)
    }, MOBILE_HLS_FALLBACK_DELAY_MS)
    return () => {
      window.clearTimeout(timeoutId)
    }
  }, [disablePreferredHls, forceHostedHls, isHostedMode, mobilePrefersHostedHls, playbackDescriptor])

  useEffect(() => {
    setMediaElementError(null)
    restoreSavedPositionRef.current = true
    lastPersistedPlaybackSecondRef.current = null
  }, [instance?.instanceId, src, managedHlsManifestUrl])

  useEffect(() => {
    let cancelled = false
    let objectUrl: string | null = null

    async function loadLocalMedia() {
      if (isHostedMode || serverMediaStreamEnabled || !instance) {
        if (!cancelled) {
          setLocalSrc(null)
          setLocalError(null)
        }
        return
      }
      const currentInstance = instance
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
      if (!currentInstance || !isRelativeMaterialId(currentInstance.materialId)) {
        setLocalSrc(null)
        setLocalError("当前实例仍是旧的绝对路径语义，无法在网页模式下直接解析。")
        return
      }

      try {
        const file = await resolveProjectFile(projectId, currentInstance.materialId)
        if (!file) {
          setLocalSrc(null)
          setLocalError("未能在已授权目录下找到该视频文件。请检查目录是否正确，或重新扫描后再试。")
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
    isHostedMode,
    instance,
    projectId,
    serverMediaStreamEnabled,
  ])

  const hostedError = useMemo(() => {
    if (!isHostedMode || !instance) return null
    if (playbackDescriptorQ.isLoading) return null
    if (playbackDescriptorQ.error) {
      const err = playbackDescriptorQ.error
      return err instanceof ApiError ? `${err.code}: ${err.message}` : err instanceof Error ? err.message : "加载播放地址失败"
    }
    if (managedHlsError) return managedHlsError
    if (mediaElementError) return mediaElementError
    if (playbackDescriptor?.mode === "relay_hls") {
      if (!playbackDescriptor.ready) return formatHostedHlsReason(playbackDescriptor.reason)
      if (nativeHlsSupported || wantsManagedHls) return null
      return "当前浏览器不支持 HLS 播放。"
    }
    if (!playbackDescriptor?.url) return "当前视频暂时不可用。"
    return null
  }, [
    instance,
    isHostedMode,
    managedHlsError,
    mediaElementError,
    nativeHlsSupported,
    playbackDescriptor,
    playbackDescriptorQ.error,
    playbackDescriptorQ.isLoading,
    wantsManagedHls,
  ])

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
    const nextMs = Math.max(0, Math.floor(v.currentTime * 1000))
    setCurrentMs(nextMs)
    if (!instanceId) return
    const currentSecond = Math.floor(nextMs / 1000)
    if (lastPersistedPlaybackSecondRef.current === currentSecond) return
    lastPersistedPlaybackSecondRef.current = currentSecond
    savePlaybackResumeMs(projectId, instanceId, nextMs)
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

  function tryRestoreSavedPlaybackPosition() {
    if (!restoreSavedPositionRef.current || !instanceId) return
    const savedMs = loadPlaybackResumeMs(projectId, instanceId)
    restoreSavedPositionRef.current = false
    if (savedMs === null) return
    const v = videoRef.current
    if (!v) return
    const durationMs = Number.isFinite(v.duration) && v.duration > 0 ? Math.floor(v.duration * 1000) : null
    const targetMs =
      durationMs === null
        ? savedMs
        : Math.min(savedMs, Math.max(0, durationMs - 1000))
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
    const v = videoRef.current
    const mediaError = v?.error
    const descriptor = playbackDescriptor
    if (isHostedMode && canFallbackToProgressive && preferHostedHls && !forceHostedHls) {
      setManagedHlsError(null)
      setMediaElementError(null)
      setDisablePreferredHls(true)
      return
    }
    if (
      isHostedMode &&
      descriptor?.mode === "relay_progressive" &&
      !preferHostedHls &&
      (mediaError?.code === 2 || mediaError?.code === 3 || mediaError?.code === 4)
    ) {
      setMediaElementError(null)
      setForceHostedHls(true)
      return
    }
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
          {isHostedMode ? <div className="theme-meta inline-flex gap-1"><RadioTower className="h-3.5 w-3.5" /> Hosted</div> : null}
          {instance ? <div className="theme-meta">{instance.materialDisplayName}</div> : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-4 pt-5">
        {shouldRenderVideo ? (
          <video
            ref={videoRef}
            className="w-full rounded-[1.2rem] border border-slate-900/10 bg-[#0f172a]"
            src={managedHlsManifestUrl ? undefined : src ?? undefined}
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
                    ? (isHostedMode ? hostedError : localError) ??
                      (isHostedMode && playbackDescriptorQ.isLoading ? "正在连接桌面连接器..." : "当前视频暂时不可用。")
                    : "请先在左侧选择一个视频实例。"}
                </div>
              </div>
            </div>
          </div>
        )}
        {shouldRenderVideo && hostedError ? <div className="text-sm text-amber-700">{hostedError}</div> : null}
      </CardContent>
    </Card>
  )
}

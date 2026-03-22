import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react"
import {
  Maximize2,
  Minimize2,
  NotebookPen,
  Pause,
  Play,
  RotateCcw,
  RotateCw,
  VideoOff,
  Volume2,
  VolumeX,
  X,
} from "lucide-react"

import type { Instance } from "@/ui/api/instances"
import { richText } from "@/ui/api/richContent"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent } from "@/ui/components/ui/card"
import { resolveProjectFile, useProjectDirectoryBinding } from "@/ui/localMedia/projectDirectory"
import { useSystemCapabilities } from "@/ui/queries/system"
import { showInfoFeedback } from "@/ui/store/feedbackStore"
import { clearPlaybackResumeMs, loadPlaybackResumeMs, savePlaybackResumeMs } from "@/ui/store/playbackResume"
import { useWorkbenchStore } from "@/ui/store/workbenchStore"
import { cn } from "@/ui/utils"

const FULLSCREEN_KEYBOARD_SEEK_STEP_MS = 5000
const CHROME_HIDE_DELAY_MS = 1600
const PLAYBACK_RATE_OPTIONS = [0.75, 1, 1.25, 1.5, 2]

type FullscreenCapableVideo = HTMLVideoElement & {
  webkitDisplayingFullscreen?: boolean
}

function isRelativeMaterialId(materialId: string) {
  const normalized = String(materialId).replace(/\\/g, "/").trim()
  if (!normalized) return false
  if (normalized.startsWith("/")) return false
  if (/^[A-Za-z]:\//.test(normalized)) return false
  return !normalized.split("/").some((part) => part === "." || part === "..")
}

function isEditableTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false
  if (target.isContentEditable) return true
  return target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement
}

function isElementInFullscreen(element: Element | null) {
  const fullscreenElement = document.fullscreenElement
  if (!element || !fullscreenElement) return false
  return fullscreenElement === element || fullscreenElement.contains(element)
}

function isVideoInFullscreen(video: HTMLVideoElement) {
  if (isElementInFullscreen(video)) return true
  return Boolean((video as FullscreenCapableVideo).webkitDisplayingFullscreen)
}

function clampPlaybackMs(video: HTMLVideoElement, ms: number) {
  const durationMs = Number.isFinite(video.duration) && video.duration > 0 ? Math.floor(video.duration * 1000) : null
  if (durationMs === null) return Math.max(0, ms)
  return Math.min(Math.max(0, ms), durationMs)
}

function readDurationMs(video: HTMLVideoElement) {
  return Number.isFinite(video.duration) && video.duration > 0 ? Math.floor(video.duration * 1000) : 0
}

function formatPlaybackClock(ms: number) {
  const totalSec = Math.floor(ms / 1000)
  const h = Math.floor(totalSec / 3600)
  const m = Math.floor((totalSec % 3600) / 60)
  const s = totalSec % 60
  const hh = h > 0 ? `${h}:` : ""
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m)
  const ss = String(s).padStart(2, "0")
  return `${hh}${mm}:${ss}`
}

function newLocalId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}_${Math.random().toString(16).slice(2)}`
}

export function VideoPane({
  projectId,
  instance,
  setCurrentMs,
  seekTo,
  onSeekApplied,
  queueHasGate,
}: {
  projectId: string
  instance: Instance | null
  setCurrentMs: (v: number) => void
  seekTo?: { instanceId: string; ms: number; nonce: number } | null
  onSeekApplied?: (nonce: number) => void
  queueHasGate: boolean
}) {
  const playerShellRef = useRef<HTMLDivElement | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const questionInputRef = useRef<HTMLTextAreaElement | null>(null)
  const answerTextareaRef = useRef<HTMLTextAreaElement | null>(null)
  const pendingSeekRef = useRef<{ instanceId: string; ms: number; nonce: number } | null>(null)
  const fullscreenTransitionRef = useRef(false)
  const chromeHideTimerRef = useRef<number | null>(null)
  const lastNonZeroVolumeRef = useRef(1)
  const lastAppliedNonceRef = useRef<number | null>(null)
  const restoreSavedPositionRef = useRef(true)
  const lastPersistedPlaybackSecondRef = useRef<number | null>(null)

  const [playbackMs, setPlaybackMs] = useState(0)
  const [durationMs, setDurationMs] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [volumePercent, setVolumePercent] = useState(100)
  const [playbackRate, setPlaybackRate] = useState(1)
  const [localSrc, setLocalSrc] = useState<string | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)
  const [mediaElementError, setMediaElementError] = useState<string | null>(null)
  const [isShellFullscreen, setIsShellFullscreen] = useState(false)
  const [isChromeAwake, setIsChromeAwake] = useState(true)
  const [isCapturePanelOpen, setIsCapturePanelOpen] = useState(false)
  const [captureAnchorMs, setCaptureAnchorMs] = useState(0)
  const [questionText, setQuestionText] = useState("")
  const [answerText, setAnswerText] = useState("")
  const [captureError, setCaptureError] = useState<string | null>(null)

  const addDraft = useWorkbenchStore((s) => s.addDraft)

  const instanceId = instance?.instanceId ?? null
  const capabilitiesQ = useSystemCapabilities()
  const directoryBinding = useProjectDirectoryBinding(projectId)
  const serverMediaStreamEnabled = capabilitiesQ.data?.serverMediaStreamEnabled ?? false
  const browserLocalMediaEnabled = capabilitiesQ.data?.browserLocalMediaEnabled ?? false
  const displayPlaybackMs = durationMs > 0 ? Math.min(playbackMs, durationMs) : playbackMs
  const progressMax = Math.max(durationMs, 1)
  const playbackProgressPercent = progressMax > 0 ? Math.min(100, Math.max(0, (displayPlaybackMs / progressMax) * 100)) : 0
  const durationLabel = durationMs > 0 ? formatPlaybackClock(durationMs) : "--:--"
  const chromeVisible = isChromeAwake || !isPlaying || isCapturePanelOpen
  const playbackRateLabel = `${Number.isInteger(playbackRate) ? playbackRate.toFixed(0) : playbackRate.toFixed(2).replace(/0$/, "")}x`

  const clearChromeHideTimer = useCallback(() => {
    if (chromeHideTimerRef.current !== null) {
      window.clearTimeout(chromeHideTimerRef.current)
      chromeHideTimerRef.current = null
    }
  }, [])

  const wakeChrome = useCallback(() => {
    clearChromeHideTimer()
    setIsChromeAwake(true)
    if (!isPlaying || isCapturePanelOpen) return
    chromeHideTimerRef.current = window.setTimeout(() => setIsChromeAwake(false), CHROME_HIDE_DELAY_MS)
  }, [clearChromeHideTimer, isCapturePanelOpen, isPlaying])

  const syncPlaybackClock = useCallback(
    (ms: number) => {
      setPlaybackMs(ms)
      setCurrentMs(ms)
    },
    [setCurrentMs],
  )

  const syncVideoUiState = useCallback((video?: HTMLVideoElement | null) => {
    if (!video) return
    setDurationMs(readDurationMs(video))
    setIsPlaying(!video.paused && !video.ended)
    const effectiveMuted = video.muted || video.volume <= 0
    setIsMuted(effectiveMuted)
    setVolumePercent(Math.round(video.volume * 100))
    setPlaybackRate(video.playbackRate)
    if (video.volume > 0) {
      lastNonZeroVolumeRef.current = video.volume
    }
  }, [])

  const persistPlaybackPosition = useCallback(
    (ms: number) => {
      if (!instanceId) return
      const currentSecond = Math.floor(ms / 1000)
      if (lastPersistedPlaybackSecondRef.current === currentSecond) return
      lastPersistedPlaybackSecondRef.current = currentSecond
      savePlaybackResumeMs(projectId, instanceId, ms)
    },
    [instanceId, projectId],
  )

  const requestShellFullscreen = useCallback(async () => {
    const shell = playerShellRef.current
    if (!shell) return false
    if (isElementInFullscreen(shell)) return true
    try {
      await shell.requestFullscreen()
      return true
    } catch {
      return false
    }
  }, [])

  const toggleShellFullscreen = useCallback(async () => {
    const shell = playerShellRef.current
    if (!shell) return
    if (isElementInFullscreen(shell)) {
      try {
        await document.exitFullscreen()
      } catch {
        // Ignore exit failures; keyboard playback still works.
      }
      return
    }
    await requestShellFullscreen()
  }, [requestShellFullscreen])

  const applySeekMs = useCallback(
    (ms: number, options?: { persist?: boolean }) => {
      const video = videoRef.current
      if (!video) return
      const nextMs = clampPlaybackMs(video, ms)
      video.currentTime = nextMs / 1000
      syncPlaybackClock(nextMs)
      if (options?.persist !== false) {
        persistPlaybackPosition(nextMs)
      }
      syncVideoUiState(video)
      wakeChrome()
    },
    [persistPlaybackPosition, syncPlaybackClock, syncVideoUiState, wakeChrome],
  )

  const seekByDelta = useCallback(
    (deltaMs: number) => {
      const video = videoRef.current
      if (!video) return
      applySeekMs(Math.floor(video.currentTime * 1000) + deltaMs)
    },
    [applySeekMs],
  )

  const togglePlayback = useCallback(() => {
    const video = videoRef.current
    if (!video) return
    if (video.paused || video.ended) {
      wakeChrome()
      void video.play().catch(() => {
        // Ignore autoplay-style rejections triggered by browser policy.
      })
      return
    }
    video.pause()
    const pauseMs = clampPlaybackMs(video, Math.floor(video.currentTime * 1000))
    syncPlaybackClock(pauseMs)
    persistPlaybackPosition(pauseMs)
    syncVideoUiState(video)
    wakeChrome()
  }, [persistPlaybackPosition, syncPlaybackClock, syncVideoUiState, wakeChrome])

  const setVideoVolume = useCallback(
    (nextPercent: number) => {
      const video = videoRef.current
      if (!video) return
      const normalized = Math.min(Math.max(0, nextPercent), 100) / 100
      video.volume = normalized
      video.muted = normalized <= 0
      if (normalized > 0) {
        lastNonZeroVolumeRef.current = normalized
      }
      syncVideoUiState(video)
      wakeChrome()
    },
    [syncVideoUiState, wakeChrome],
  )

  const toggleMute = useCallback(() => {
    const video = videoRef.current
    if (!video) return
    if (video.muted || video.volume <= 0) {
      const restoreVolume = Math.min(Math.max(lastNonZeroVolumeRef.current, 0.15), 1)
      video.muted = false
      video.volume = restoreVolume
      lastNonZeroVolumeRef.current = restoreVolume
    } else {
      if (video.volume > 0) {
        lastNonZeroVolumeRef.current = video.volume
      }
      video.muted = true
    }
    syncVideoUiState(video)
    wakeChrome()
  }, [syncVideoUiState, wakeChrome])

  const setVideoPlaybackRate = useCallback(
    (nextRate: number) => {
      const video = videoRef.current
      if (!video) return
      video.playbackRate = nextRate
      setPlaybackRate(nextRate)
      wakeChrome()
    },
    [wakeChrome],
  )

  const closeCapturePanel = useCallback(() => {
    setIsCapturePanelOpen(false)
    setCaptureError(null)
    setQuestionText("")
    setAnswerText("")
  }, [])

  const openCapturePanel = useCallback(
    async (anchorMs?: number, keepFullscreen = false) => {
      if (queueHasGate) {
        showInfoFeedback("当前处于复习模式", "请先完成复习，再继续录入新的复述点。")
        return
      }
      const video = videoRef.current
      if (!video || !instanceId) return

      video.pause()
      const captureMs = clampPlaybackMs(video, anchorMs ?? Math.floor(video.currentTime * 1000))
      syncPlaybackClock(captureMs)
      persistPlaybackPosition(captureMs)
      syncVideoUiState(video)

      if (keepFullscreen) {
        await requestShellFullscreen()
      }
      if (!keepFullscreen && !isElementInFullscreen(playerShellRef.current)) return

      setCaptureAnchorMs(captureMs)
      setQuestionText("")
      setAnswerText("")
      setCaptureError(null)
      setIsCapturePanelOpen(true)
      wakeChrome()
    },
    [
      instanceId,
      persistPlaybackPosition,
      queueHasGate,
      requestShellFullscreen,
      syncPlaybackClock,
      syncVideoUiState,
      wakeChrome,
    ],
  )

  const saveCaptureDraft = useCallback(() => {
    if (!instanceId) {
      setCaptureError("当前还没有选中视频实例。")
      return
    }
    if (queueHasGate) {
      const message = "请先完成复习，再继续录入新的复述点。"
      setCaptureError(message)
      showInfoFeedback("当前处于复习模式", message)
      return
    }
    const normalizedQuestion = questionText.trim()
    const normalizedAnswer = answerText.trim()
    if (!normalizedQuestion || !normalizedAnswer) {
      setCaptureError("问题和答案都要填写。")
      return
    }

    const now = Date.now()
    addDraft(projectId, {
      localId: newLocalId(),
      instanceId,
      position: `t=${captureAnchorMs}`,
      question: richText(normalizedQuestion),
      answer: richText(normalizedAnswer),
      createdAt: now,
      updatedAt: now,
    })
    closeCapturePanel()
  }, [
    addDraft,
    answerText,
    captureAnchorMs,
    closeCapturePanel,
    instanceId,
    projectId,
    questionText,
    queueHasGate,
  ])

  function handleTimeUpdate() {
    const video = videoRef.current
    if (!video) return
    const nextMs = Math.max(0, Math.floor(video.currentTime * 1000))
    syncPlaybackClock(nextMs)
    if (!instanceId) return
    const currentSecond = Math.floor(nextMs / 1000)
    if (lastPersistedPlaybackSecondRef.current === currentSecond) return
    lastPersistedPlaybackSecondRef.current = currentSecond
    savePlaybackResumeMs(projectId, instanceId, nextMs)
  }

  useEffect(() => {
    syncPlaybackClock(0)
    setDurationMs(0)
    setIsPlaying(false)
    setIsMuted(false)
    setVolumePercent(100)
    setPlaybackRate(1)
    setMediaElementError(null)
    setIsShellFullscreen(false)
    setIsChromeAwake(true)
    setIsCapturePanelOpen(false)
    setCaptureAnchorMs(0)
    setQuestionText("")
    setAnswerText("")
    setCaptureError(null)
    pendingSeekRef.current = null
    lastAppliedNonceRef.current = null
    restoreSavedPositionRef.current = true
    lastPersistedPlaybackSecondRef.current = null
    clearChromeHideTimer()
  }, [clearChromeHideTimer, instance?.instanceId, localSrc, serverMediaStreamEnabled, syncPlaybackClock])

  useEffect(() => {
    async function syncFullscreenState() {
      const shell = playerShellRef.current
      const video = videoRef.current
      const fullscreenElement = document.fullscreenElement

      if (
        !fullscreenTransitionRef.current &&
        shell &&
        video &&
        fullscreenElement === video &&
        !isElementInFullscreen(shell)
      ) {
        fullscreenTransitionRef.current = true
        try {
          await document.exitFullscreen()
          await shell.requestFullscreen()
        } catch {
          // Ignore and fall back to the browser's fullscreen state.
        } finally {
          fullscreenTransitionRef.current = false
        }
      }

      setIsShellFullscreen(isElementInFullscreen(shell))
    }

    function handleFullscreenChange() {
      void syncFullscreenState()
    }

    void syncFullscreenState()
    document.addEventListener("fullscreenchange", handleFullscreenChange)
    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange)
    }
  }, [])

  useEffect(() => {
    if (!isCapturePanelOpen) return
    const focusField = () => {
      const field = questionInputRef.current
      if (!field) return
      field.focus()
      const caret = field.value.length
      field.setSelectionRange(caret, caret)
    }

    const rafId = window.requestAnimationFrame(focusField)
    const timeoutId = window.setTimeout(focusField, 120)
    return () => {
      window.cancelAnimationFrame(rafId)
      window.clearTimeout(timeoutId)
    }
  }, [isCapturePanelOpen])

  useEffect(() => {
    if (!isCapturePanelOpen || isShellFullscreen) return
    closeCapturePanel()
  }, [closeCapturePanel, isCapturePanelOpen, isShellFullscreen])

  useEffect(() => {
    clearChromeHideTimer()
    if (!isPlaying || isCapturePanelOpen) {
      setIsChromeAwake(true)
      return
    }
    if (!isChromeAwake) return
    chromeHideTimerRef.current = window.setTimeout(() => setIsChromeAwake(false), CHROME_HIDE_DELAY_MS)
    return clearChromeHideTimer
  }, [clearChromeHideTimer, isCapturePanelOpen, isChromeAwake, isPlaying])

  useEffect(() => clearChromeHideTimer, [clearChromeHideTimer])

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
  }, [browserLocalMediaEnabled, directoryBinding.permission, instance, projectId, serverMediaStreamEnabled])

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
    applySeekMs(seekTo.ms)
    pendingSeekRef.current = null
    lastAppliedNonceRef.current = seekTo.nonce
    onSeekApplied?.(seekTo.nonce)
  }, [applySeekMs, instanceId, onSeekApplied, seekTo])

  function tryApplyPendingSeek() {
    const req = pendingSeekRef.current
    if (!req || !instance || instance.instanceId !== req.instanceId) return
    const video = videoRef.current
    if (!video || video.readyState < 1) return
    applySeekMs(req.ms)
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
    const totalDurationMs =
      Number.isFinite(video.duration) && video.duration > 0 ? Math.floor(video.duration * 1000) : null
    const targetMs = totalDurationMs === null ? savedMs : Math.min(savedMs, Math.max(0, totalDurationMs - 1000))
    if (targetMs <= 0) return
    applySeekMs(targetMs, { persist: false })
  }

  function handleLoadedMetadata() {
    setMediaElementError(null)
    syncVideoUiState(videoRef.current)
    tryApplyPendingSeek()
    tryRestoreSavedPlaybackPosition()
  }

  function handleCanPlay() {
    syncVideoUiState(videoRef.current)
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
    setIsPlaying(false)
  }

  useEffect(() => {
    function handleFullscreenKeyDown(event: KeyboardEvent) {
      const video = videoRef.current
      if (!video || video.readyState < 1) return
      if (!isVideoInFullscreen(video) && !isElementInFullscreen(playerShellRef.current)) return
      if (event.defaultPrevented || event.isComposing) return

      if (event.key === "Escape") {
        if (isCapturePanelOpen) {
          event.preventDefault()
          closeCapturePanel()
        }
        return
      }

      if (event.altKey || event.ctrlKey || event.metaKey) return
      if (isEditableTarget(event.target)) return

      if (event.code === "Space") {
        event.preventDefault()
        togglePlayback()
        return
      }

      if (event.code === "KeyN") {
        event.preventDefault()
        if (event.repeat || !instanceId) return
        void openCapturePanel(undefined, true)
        return
      }

      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return

      event.preventDefault()
      const deltaMs = event.key === "ArrowRight" ? FULLSCREEN_KEYBOARD_SEEK_STEP_MS : -FULLSCREEN_KEYBOARD_SEEK_STEP_MS
      seekByDelta(deltaMs)
    }

    document.addEventListener("keydown", handleFullscreenKeyDown, true)
    return () => {
      document.removeEventListener("keydown", handleFullscreenKeyDown, true)
    }
  }, [
    closeCapturePanel,
    instanceId,
    isCapturePanelOpen,
    openCapturePanel,
    seekByDelta,
    togglePlayback,
  ])

  const shouldRenderVideo = Boolean(src)

  return (
    <Card className="theme-card-main overflow-hidden">
      <CardContent className="space-y-4 p-4">
        {shouldRenderVideo ? (
          <div
            ref={playerShellRef}
            className={cn(
              "group relative overflow-hidden rounded-[1.2rem] border border-slate-900/10 bg-[#050816]",
              isShellFullscreen && "h-full w-full bg-black p-4",
            )}
            onPointerMove={wakeChrome}
            onPointerEnter={wakeChrome}
          >
            <video
              ref={videoRef}
              className={cn(
                "plm-video-player w-full bg-black",
                isShellFullscreen
                  ? "h-[calc(100dvh-2rem)] max-h-full rounded-[1.2rem] border border-white/10 object-contain"
                  : "rounded-[1.2rem] object-contain",
              )}
              src={src ?? undefined}
              playsInline
              preload="metadata"
              disablePictureInPicture
              onClick={() => {
                if (isCapturePanelOpen) return
                togglePlayback()
              }}
              onDoubleClick={() => {
                if (isCapturePanelOpen) return
                void toggleShellFullscreen()
              }}
              onLoadedData={() => {
                setMediaElementError(null)
                syncVideoUiState(videoRef.current)
              }}
              onLoadedMetadata={handleLoadedMetadata}
              onCanPlay={handleCanPlay}
              onDurationChange={() => syncVideoUiState(videoRef.current)}
              onPlay={() => {
                setIsPlaying(true)
                wakeChrome()
              }}
              onPause={() => setIsPlaying(false)}
              onVolumeChange={() => syncVideoUiState(videoRef.current)}
              onError={handleVideoError}
              onEnded={handleEnded}
              onTimeUpdate={handleTimeUpdate}
              onSeeked={handleTimeUpdate}
            />

            {!isPlaying && !isCapturePanelOpen ? (
              <div className="pointer-events-none absolute inset-0 z-[9] flex items-center justify-center">
                <Button
                  type="button"
                  size="icon"
                  className="pointer-events-auto h-10 w-10 rounded-full bg-white/12 text-white shadow-[0_18px_40px_-28px_rgba(15,23,42,0.92)] backdrop-blur-md hover:bg-white/18"
                  onClick={togglePlayback}
                  title="播放"
                >
                  <Play className="h-4 w-4 fill-current" />
                  <span className="sr-only">播放</span>
                </Button>
              </div>
            ) : null}

            <div
              className={cn(
                "pointer-events-none absolute inset-x-0 bottom-0 z-20 px-2 pb-2 transition-opacity duration-200",
                chromeVisible ? "opacity-100" : "opacity-0",
              )}
            >
              <div className="pointer-events-auto text-white [text-shadow:0_1px_8px_rgba(0,0,0,0.55)]">
                <div className="relative -mb-1">
                  <input
                    type="range"
                    min={0}
                    max={progressMax}
                    step={250}
                    value={Math.min(displayPlaybackMs, progressMax)}
                    onChange={(event) => applySeekMs(Number(event.target.value))}
                    disabled={durationMs <= 0}
                    className="plm-video-range plm-video-range-progress w-full"
                    style={{ "--plm-range-progress": `${playbackProgressPercent}%` } as CSSProperties}
                    aria-label="播放进度"
                  />
                </div>

                <div className="mt-0 rounded-[1rem] border border-white/14 bg-[linear-gradient(180deg,rgba(2,6,23,0.72),rgba(2,6,23,0.88))] px-2.5 py-1.5 shadow-[0_18px_44px_-28px_rgba(0,0,0,0.9)] backdrop-blur-xl">
                  <div className="flex items-center gap-1 text-xs sm:gap-1.5 sm:text-sm">
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7 rounded-full text-white hover:bg-white/10"
                      onClick={togglePlayback}
                      title={isPlaying ? "暂停" : "播放"}
                    >
                      {isPlaying ? <Pause className="h-3.5 w-3.5 fill-current" /> : <Play className="h-3.5 w-3.5 fill-current" />}
                      <span className="sr-only">{isPlaying ? "暂停" : "播放"}</span>
                    </Button>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="hidden h-7 w-7 rounded-full text-white/78 hover:bg-white/10 hover:text-white lg:inline-flex"
                      onClick={() => seekByDelta(-FULLSCREEN_KEYBOARD_SEEK_STEP_MS)}
                      title="后退 5 秒"
                    >
                      <RotateCcw className="h-3.5 w-3.5" />
                      <span className="sr-only">后退 5 秒</span>
                    </Button>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="hidden h-7 w-7 rounded-full text-white/78 hover:bg-white/10 hover:text-white lg:inline-flex"
                      onClick={() => seekByDelta(FULLSCREEN_KEYBOARD_SEEK_STEP_MS)}
                      title="前进 5 秒"
                    >
                      <RotateCw className="h-3.5 w-3.5" />
                      <span className="sr-only">前进 5 秒</span>
                    </Button>

                    <div className="ml-1 shrink-0 text-[10px] tabular-nums text-white/84 sm:text-[11px]">
                      {formatPlaybackClock(displayPlaybackMs)} / {durationLabel}
                    </div>

                    <div className="ml-auto flex items-center gap-1 text-white/86">
                      <div className="group/volume relative hidden sm:block">
                        <div className="pointer-events-none absolute bottom-full left-1/2 mb-2 -translate-x-1/2 opacity-0 transition duration-150 group-hover/volume:opacity-100 group-focus-within/volume:opacity-100">
                          <div className="pointer-events-auto rounded-xl border border-white/12 bg-slate-950 p-1 shadow-[0_14px_32px_-20px_rgba(0,0,0,0.9)]">
                            <div className="flex h-28 w-10 items-center justify-center rounded-lg bg-white/[0.04]">
                              <div className="w-20 -rotate-90">
                              <input
                                type="range"
                                min={0}
                                max={100}
                                step={1}
                                value={isMuted ? 0 : volumePercent}
                                onChange={(event) => setVideoVolume(Number(event.target.value))}
                                className="plm-video-range plm-video-range-volume w-20"
                                style={{ "--plm-range-progress": `${isMuted ? 0 : volumePercent}%` } as CSSProperties}
                                aria-label="音量"
                              />
                              </div>
                            </div>
                          </div>
                        </div>
                        <Button
                          type="button"
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7 shrink-0 rounded-full text-white/82 hover:bg-white/10 hover:text-white"
                          onClick={toggleMute}
                          title={isMuted ? "取消静音" : "静音"}
                        >
                          {isMuted ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
                          <span className="sr-only">{isMuted ? "取消静音" : "静音"}</span>
                        </Button>
                      </div>
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 rounded-full text-white/82 hover:bg-white/10 hover:text-white sm:hidden"
                        onClick={toggleMute}
                        title={isMuted ? "取消静音" : "静音"}
                      >
                        {isMuted ? <VolumeX className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
                        <span className="sr-only">{isMuted ? "取消静音" : "静音"}</span>
                      </Button>
                    <div className="group/rate relative">
                      <div className="pointer-events-none absolute bottom-full left-1/2 mb-2 -translate-x-1/2 opacity-0 transition duration-150 group-hover/rate:opacity-100 group-focus-within/rate:opacity-100">
                          <div className="pointer-events-auto min-w-[4.75rem] rounded-xl border border-white/12 bg-slate-950 p-1 shadow-[0_14px_32px_-20px_rgba(0,0,0,0.9)]">
                            {[...PLAYBACK_RATE_OPTIONS].sort((left, right) => right - left).map((rate) => {
                              const active = Math.abs(rate - playbackRate) < 0.001
                              const rateLabel = `${Number.isInteger(rate) ? rate.toFixed(0) : String(rate)}x`
                              return (
                                <button
                                  key={rate}
                                  type="button"
                                  className={cn(
                                    "flex h-7 w-full items-center justify-center rounded-lg px-2 text-[11px] font-medium tabular-nums outline-none transition-colors focus-visible:bg-white/12 focus-visible:text-white",
                                    active ? "bg-white/14 text-white" : "text-white/78 hover:bg-white/10 hover:text-white",
                                  )}
                                  onClick={() => setVideoPlaybackRate(rate)}
                                >
                                  {rateLabel}
                                </button>
                              )
                            })}
                          </div>
                        </div>
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          className="h-7 min-w-[2rem] rounded-full px-1.5 text-[10px] text-white/82 hover:bg-white/10 hover:text-white sm:text-[11px]"
                          title="切换倍速"
                        >
                          {playbackRateLabel}
                        </Button>
                      </div>
                      {isShellFullscreen ? (
                        <Button
                          type="button"
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7 rounded-full text-white hover:bg-white/10"
                          onClick={() => void openCapturePanel()}
                          disabled={!instanceId || queueHasGate}
                          title="记复述点"
                        >
                          <NotebookPen className="h-3.5 w-3.5" />
                          <span className="sr-only">记复述点</span>
                        </Button>
                      ) : null}
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 rounded-full text-white hover:bg-white/10"
                        onClick={() => void toggleShellFullscreen()}
                        title={isShellFullscreen ? "退出全屏" : "进入全屏"}
                      >
                        {isShellFullscreen ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}
                        <span className="sr-only">{isShellFullscreen ? "退出全屏" : "进入全屏"}</span>
                      </Button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {isCapturePanelOpen ? (
              <div className="pointer-events-none absolute inset-0 z-30">
                <div className="pointer-events-auto absolute bottom-12 right-3 w-[min(24rem,calc(100%-1.5rem))] rounded-[1rem] border border-white/12 bg-[linear-gradient(180deg,rgba(15,23,42,0.84),rgba(2,6,23,0.92))] p-4 text-white shadow-[0_28px_64px_-34px_rgba(15,23,42,0.96)] backdrop-blur-xl">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-[11px] uppercase tracking-[0.18em] text-white/42">记复述点</div>
                      <div className="mt-2 inline-flex items-center rounded-full border border-cyan-200/18 bg-cyan-200/10 px-2.5 py-1 text-[11px] text-cyan-100">
                        锚点 {formatPlaybackClock(captureAnchorMs)}
                      </div>
                    </div>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="h-8 w-8 rounded-full text-white/72 hover:bg-white/10 hover:text-white"
                      onClick={closeCapturePanel}
                    >
                      <X className="h-4 w-4" />
                      <span className="sr-only">关闭记复述点</span>
                    </Button>
                  </div>

                  <div className="mt-3 space-y-3">
                    <label className="block">
                      <div className="mb-1 text-xs text-white/62">问题</div>
                      <textarea
                        ref={questionInputRef}
                        value={questionText}
                        rows={3}
                        className="min-h-[84px] w-full rounded-xl border border-white/10 bg-white/[0.05] px-3 py-2 text-sm text-white outline-none placeholder:text-white/28 focus:border-cyan-200/24 focus:bg-white/[0.08]"
                        placeholder="输入复述点问题"
                        onChange={(event) => {
                          setQuestionText(event.target.value)
                          if (captureError) setCaptureError(null)
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Escape") {
                            event.preventDefault()
                            closeCapturePanel()
                            return
                          }
                          if (event.nativeEvent.isComposing) return
                          if (event.key === "Enter" && !(event.ctrlKey || event.metaKey)) {
                            event.preventDefault()
                            answerTextareaRef.current?.focus()
                          }
                        }}
                      />
                    </label>

                    <label className="block">
                      <div className="mb-1 text-xs text-white/62">答案</div>
                      <textarea
                        ref={answerTextareaRef}
                        value={answerText}
                        className="min-h-[124px] w-full rounded-xl border border-white/10 bg-white/[0.05] px-3 py-2 text-sm text-white outline-none placeholder:text-white/28 focus:border-cyan-200/24 focus:bg-white/[0.08]"
                        placeholder="输入答案或你的复述内容"
                        onChange={(event) => {
                          setAnswerText(event.target.value)
                          if (captureError) setCaptureError(null)
                        }}
                        onKeyDown={(event) => {
                          if (event.key === "Escape") {
                            event.preventDefault()
                            closeCapturePanel()
                            return
                          }
                          if (event.nativeEvent.isComposing) return
                          if (event.key === "Enter" && !(event.ctrlKey || event.metaKey)) {
                            event.preventDefault()
                            void saveCaptureDraft()
                          }
                        }}
                      />
                    </label>
                  </div>

                  <div className={cn("mt-2 text-xs", captureError ? "text-rose-200" : "text-white/44")}>
                    {captureError ?? "问题中 Enter 切到答案，Ctrl+Enter 换行；答案中 Enter 保存，Ctrl+Enter 换行，Esc 取消"}
                  </div>

                  <div className="mt-3 flex items-center justify-end gap-2">
                    <Button
                      type="button"
                      variant="ghost"
                      className="text-white/72 hover:bg-white/10 hover:text-white"
                      onClick={closeCapturePanel}
                    >
                      取消
                    </Button>
                    <Button type="button" onClick={() => void saveCaptureDraft()}>
                      保存复述点
                    </Button>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
        ) : (
          <div className="theme-canvas rounded-[1.2rem] border border-border/60 p-6 text-sm text-muted-foreground">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-[#e2e8f0] bg-white text-[#5f7188]">
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

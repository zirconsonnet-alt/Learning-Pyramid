import { type PointerEvent as ReactPointerEvent, useCallback, useEffect, useMemo, useRef, useState } from "react"
import {
  Film,
  GripHorizontal,
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
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/ui/components/ui/card"
import { resolveProjectFile, useProjectDirectoryBinding } from "@/ui/localMedia/projectDirectory"
import { useSystemCapabilities } from "@/ui/queries/system"
import { clearPlaybackResumeMs, loadPlaybackResumeMs, savePlaybackResumeMs } from "@/ui/store/playbackResume"
import { cn } from "@/ui/utils"

const FULLSCREEN_KEYBOARD_SEEK_STEP_MS = 5000
const QUICK_CAPTURE_PANEL_MARGIN = 16
const QUICK_CAPTURE_PANEL_WIDTH = 384
const QUICK_CAPTURE_PANEL_HEIGHT = 312
const QUICK_CAPTURE_PANEL_TOP_OFFSET_FULLSCREEN = 72
const QUICK_CAPTURE_PANEL_TOP_OFFSET_INLINE = 16

type FullscreenCapableVideo = HTMLVideoElement & {
  webkitDisplayingFullscreen?: boolean
}

type QuickCaptureSaveResult = {
  ok: boolean
  message?: string
}

type QuickCapturePanelPosition = {
  x: number
  y: number
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
  const msPart = ms % 1000
  const hh = h > 0 ? `${h}:` : ""
  const mm = h > 0 ? String(m).padStart(2, "0") : String(m)
  const ss = String(s).padStart(2, "0")
  return `${hh}${mm}:${ss}.${String(msPart).padStart(3, "0")}`
}

export function VideoPane({
  projectId,
  instance,
  setCurrentMs,
  seekTo,
  onSeekApplied,
  onQuickCaptureSave,
}: {
  projectId: string
  instance: Instance | null
  setCurrentMs: (v: number) => void
  seekTo?: { instanceId: string; ms: number; nonce: number } | null
  onSeekApplied?: (nonce: number) => void
  onQuickCaptureSave?: (payload: { instanceId: string; ms: number; question: string; answer: string }) => QuickCaptureSaveResult
}) {
  const playerShellRef = useRef<HTMLDivElement | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const quickCapturePanelRef = useRef<HTMLDivElement | null>(null)
  const quickCaptureQuestionRef = useRef<HTMLTextAreaElement | null>(null)
  const pendingSeekRef = useRef<{ instanceId: string; ms: number; nonce: number } | null>(null)
  const quickCaptureDragRef = useRef<{ pointerId: number; offsetX: number; offsetY: number } | null>(null)
  const fullscreenTransitionRef = useRef(false)
  const lastNonZeroVolumeRef = useRef(1)
  const lastAppliedNonceRef = useRef<number | null>(null)
  const restoreSavedPositionRef = useRef(true)
  const lastPersistedPlaybackSecondRef = useRef<number | null>(null)

  const [playbackMs, setPlaybackMs] = useState(0)
  const [durationMs, setDurationMs] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [volumePercent, setVolumePercent] = useState(100)
  const [localSrc, setLocalSrc] = useState<string | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)
  const [mediaElementError, setMediaElementError] = useState<string | null>(null)
  const [isShellFullscreen, setIsShellFullscreen] = useState(false)
  const [isQuickCaptureOpen, setIsQuickCaptureOpen] = useState(false)
  const [quickCaptureAnchorMs, setQuickCaptureAnchorMs] = useState(0)
  const [quickCaptureQuestion, setQuickCaptureQuestion] = useState("")
  const [quickCaptureAnswer, setQuickCaptureAnswer] = useState("")
  const [quickCaptureError, setQuickCaptureError] = useState<string | null>(null)
  const [quickCapturePosition, setQuickCapturePosition] = useState<QuickCapturePanelPosition | null>(null)
  const [isDraggingQuickCapture, setIsDraggingQuickCapture] = useState(false)

  const instanceId = instance?.instanceId ?? null
  const capabilitiesQ = useSystemCapabilities()
  const directoryBinding = useProjectDirectoryBinding(projectId)
  const isHostedMode = capabilitiesQ.data?.appMode === "hosted"
  const serverMediaStreamEnabled = capabilitiesQ.data?.serverMediaStreamEnabled ?? false
  const browserLocalMediaEnabled = capabilitiesQ.data?.browserLocalMediaEnabled ?? false
  const displayPlaybackMs = durationMs > 0 ? Math.min(playbackMs, durationMs) : playbackMs

  const syncPlaybackClock = useCallback((ms: number) => {
    setPlaybackMs(ms)
    setCurrentMs(ms)
  }, [setCurrentMs])

  const syncVideoUiState = useCallback((video?: HTMLVideoElement | null) => {
    if (!video) return
    setDurationMs(readDurationMs(video))
    setIsPlaying(!video.paused && !video.ended)
    const effectiveMuted = video.muted || video.volume <= 0
    setIsMuted(effectiveMuted)
    const nextVolumePercent = Math.round(video.volume * 100)
    setVolumePercent(nextVolumePercent)
    if (video.volume > 0) {
      lastNonZeroVolumeRef.current = video.volume
    }
  }, [])

  useEffect(() => {
    setPlaybackMs(0)
    setDurationMs(0)
    setIsPlaying(false)
    setIsMuted(false)
    setVolumePercent(100)
    setMediaElementError(null)
    restoreSavedPositionRef.current = true
    lastPersistedPlaybackSecondRef.current = null
    setIsQuickCaptureOpen(false)
    setQuickCaptureQuestion("")
    setQuickCaptureAnswer("")
    setQuickCaptureError(null)
    setQuickCapturePosition(null)
    setIsDraggingQuickCapture(false)
    quickCaptureDragRef.current = null
  }, [instance?.instanceId, localSrc, serverMediaStreamEnabled])

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
    if (!isQuickCaptureOpen) return
    setQuickCapturePosition((current) => {
      const shell = playerShellRef.current
      const panel = quickCapturePanelRef.current
      if (!shell) return current
      const panelWidth = panel?.offsetWidth ?? QUICK_CAPTURE_PANEL_WIDTH
      const panelHeight = panel?.offsetHeight ?? QUICK_CAPTURE_PANEL_HEIGHT
      const maxX = Math.max(QUICK_CAPTURE_PANEL_MARGIN, shell.clientWidth - panelWidth - QUICK_CAPTURE_PANEL_MARGIN)
      const maxY = Math.max(QUICK_CAPTURE_PANEL_MARGIN, shell.clientHeight - panelHeight - QUICK_CAPTURE_PANEL_MARGIN)
      const fallbackY = isShellFullscreen ? QUICK_CAPTURE_PANEL_TOP_OFFSET_FULLSCREEN : QUICK_CAPTURE_PANEL_TOP_OFFSET_INLINE
      const base = current ?? {
        x: shell.clientWidth - panelWidth - QUICK_CAPTURE_PANEL_MARGIN,
        y: fallbackY,
      }
      return {
        x: Math.min(Math.max(QUICK_CAPTURE_PANEL_MARGIN, base.x), maxX),
        y: Math.min(Math.max(QUICK_CAPTURE_PANEL_MARGIN, base.y), maxY),
      }
    })

    const focusQuestion = () => {
      const field = quickCaptureQuestionRef.current
      if (!field) return
      field.focus()
      const caret = field.value.length
      field.setSelectionRange(caret, caret)
    }

    const rafId = window.requestAnimationFrame(focusQuestion)
    const timeoutId = window.setTimeout(focusQuestion, 120)
    return () => {
      window.cancelAnimationFrame(rafId)
      window.clearTimeout(timeoutId)
    }
  }, [isQuickCaptureOpen, isShellFullscreen])

  const clampQuickCapturePosition = useCallback(
    (position: QuickCapturePanelPosition, panelSize?: { width: number; height: number }) => {
      const shell = playerShellRef.current
      if (!shell) return position

      const panelWidth = panelSize?.width ?? quickCapturePanelRef.current?.offsetWidth ?? QUICK_CAPTURE_PANEL_WIDTH
      const panelHeight = panelSize?.height ?? quickCapturePanelRef.current?.offsetHeight ?? QUICK_CAPTURE_PANEL_HEIGHT
      const maxX = Math.max(QUICK_CAPTURE_PANEL_MARGIN, shell.clientWidth - panelWidth - QUICK_CAPTURE_PANEL_MARGIN)
      const maxY = Math.max(QUICK_CAPTURE_PANEL_MARGIN, shell.clientHeight - panelHeight - QUICK_CAPTURE_PANEL_MARGIN)

      return {
        x: Math.min(Math.max(QUICK_CAPTURE_PANEL_MARGIN, position.x), maxX),
        y: Math.min(Math.max(QUICK_CAPTURE_PANEL_MARGIN, position.y), maxY),
      }
    },
    [],
  )

  const defaultQuickCapturePosition = useCallback(() => {
    const shell = playerShellRef.current
    if (!shell) {
      return {
        x: QUICK_CAPTURE_PANEL_MARGIN,
        y: QUICK_CAPTURE_PANEL_MARGIN,
      }
    }

    const panelWidth = Math.min(
      QUICK_CAPTURE_PANEL_WIDTH,
      Math.max(280, shell.clientWidth - QUICK_CAPTURE_PANEL_MARGIN * 2),
    )
    const panelHeight = Math.min(
      QUICK_CAPTURE_PANEL_HEIGHT,
      Math.max(240, shell.clientHeight - QUICK_CAPTURE_PANEL_MARGIN * 2),
    )

    return clampQuickCapturePosition(
      {
        x: shell.clientWidth - panelWidth - QUICK_CAPTURE_PANEL_MARGIN,
        y: isShellFullscreen ? QUICK_CAPTURE_PANEL_TOP_OFFSET_FULLSCREEN : QUICK_CAPTURE_PANEL_TOP_OFFSET_INLINE,
      },
      { width: panelWidth, height: panelHeight },
    )
  }, [clampQuickCapturePosition, isShellFullscreen])

  useEffect(() => {
    if (!isQuickCaptureOpen) return

    function syncQuickCapturePosition() {
      setQuickCapturePosition((current) => clampQuickCapturePosition(current ?? defaultQuickCapturePosition()))
    }

    window.addEventListener("resize", syncQuickCapturePosition)
    document.addEventListener("fullscreenchange", syncQuickCapturePosition)
    return () => {
      window.removeEventListener("resize", syncQuickCapturePosition)
      document.removeEventListener("fullscreenchange", syncQuickCapturePosition)
    }
  }, [clampQuickCapturePosition, defaultQuickCapturePosition, isQuickCaptureOpen])

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
    syncPlaybackClock(seekTo.ms)
    pendingSeekRef.current = null
    lastAppliedNonceRef.current = seekTo.nonce
    onSeekApplied?.(seekTo.nonce)
    syncVideoUiState(video)
  }, [instanceId, onSeekApplied, seekTo, syncPlaybackClock, syncVideoUiState])

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

  const persistPlaybackPosition = useCallback((ms: number) => {
    if (!instanceId) return
    const currentSecond = Math.floor(ms / 1000)
    if (lastPersistedPlaybackSecondRef.current === currentSecond) return
    lastPersistedPlaybackSecondRef.current = currentSecond
    savePlaybackResumeMs(projectId, instanceId, ms)
  }, [instanceId, projectId])

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

  const togglePlayback = useCallback(() => {
    const video = videoRef.current
    if (!video) return
    if (video.paused || video.ended) {
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
  }, [persistPlaybackPosition, syncPlaybackClock, syncVideoUiState])

  const closeQuickCapturePanel = useCallback(() => {
    setIsQuickCaptureOpen(false)
    setQuickCaptureError(null)
    setIsDraggingQuickCapture(false)
    quickCaptureDragRef.current = null
  }, [])

  const openQuickCapturePanel = useCallback(async (anchorMs?: number, keepFullscreen = false) => {
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
    setQuickCaptureAnchorMs(captureMs)
    setQuickCaptureQuestion("")
    setQuickCaptureAnswer("")
    setQuickCaptureError(null)
    setQuickCapturePosition((current) => current ?? defaultQuickCapturePosition())
    setIsQuickCaptureOpen(true)
  }, [defaultQuickCapturePosition, instanceId, persistPlaybackPosition, requestShellFullscreen, syncPlaybackClock, syncVideoUiState])

  const saveQuickCapture = useCallback(() => {
    if (!instanceId) {
      setQuickCaptureError("当前还没有选中视频实例。")
      return
    }
    if (!onQuickCaptureSave) {
      setQuickCaptureError("当前快捷录入不可用，请稍后重试。")
      return
    }
    if (!quickCaptureQuestion.trim() && !quickCaptureAnswer.trim()) {
      setQuickCaptureError("至少填写问题或答案中的一项。")
      return
    }
    const result = onQuickCaptureSave({
      instanceId,
      ms: quickCaptureAnchorMs,
      question: quickCaptureQuestion,
      answer: quickCaptureAnswer,
    })
    if (!result.ok) {
      setQuickCaptureError(result.message ?? "当前无法保存这条复述点草稿。")
      return
    }
    closeQuickCapturePanel()
    setQuickCaptureQuestion("")
    setQuickCaptureAnswer("")
  }, [closeQuickCapturePanel, instanceId, onQuickCaptureSave, quickCaptureAnchorMs, quickCaptureAnswer, quickCaptureQuestion])

  function seekToMs(ms: number) {
    const video = videoRef.current
    if (!video) return
    video.currentTime = clampPlaybackMs(video, ms) / 1000
  }

  const applySeekMs = useCallback((ms: number, options?: { persist?: boolean }) => {
    const video = videoRef.current
    if (!video) return
    const nextMs = clampPlaybackMs(video, ms)
    video.currentTime = nextMs / 1000
    syncPlaybackClock(nextMs)
    if (options?.persist !== false) {
      persistPlaybackPosition(nextMs)
    }
    syncVideoUiState(video)
  }, [persistPlaybackPosition, syncPlaybackClock, syncVideoUiState])

  const seekByDelta = useCallback((deltaMs: number) => {
    const video = videoRef.current
    if (!video) return
    const currentMs = Math.floor(video.currentTime * 1000)
    applySeekMs(currentMs + deltaMs)
  }, [applySeekMs])

  const setVideoVolume = useCallback((nextPercent: number) => {
    const video = videoRef.current
    if (!video) return
    const normalized = Math.min(Math.max(0, nextPercent), 100) / 100
    video.volume = normalized
    video.muted = normalized <= 0
    if (normalized > 0) {
      lastNonZeroVolumeRef.current = normalized
    }
    syncVideoUiState(video)
  }, [syncVideoUiState])

  const toggleMute = useCallback(() => {
    const video = videoRef.current
    if (!video) return
    if (video.muted || video.volume <= 0) {
      const restoreVolume = Math.min(Math.max(lastNonZeroVolumeRef.current, 0.1), 1)
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
  }, [syncVideoUiState])

  const beginQuickCaptureDrag = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return
    if (event.target instanceof HTMLElement && event.target.closest("[data-quick-capture-action='ignore']")) {
      return
    }

    const shell = playerShellRef.current
    const panel = quickCapturePanelRef.current
    if (!shell || !panel) return

    const panelRect = panel.getBoundingClientRect()
    quickCaptureDragRef.current = {
      pointerId: event.pointerId,
      offsetX: event.clientX - panelRect.left,
      offsetY: event.clientY - panelRect.top,
    }
    setIsDraggingQuickCapture(true)
    event.currentTarget.setPointerCapture(event.pointerId)
    event.preventDefault()
  }, [])

  const continueQuickCaptureDrag = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = quickCaptureDragRef.current
    const shell = playerShellRef.current
    if (!drag || drag.pointerId !== event.pointerId || !shell) return

    const shellRect = shell.getBoundingClientRect()
    setQuickCapturePosition(
      clampQuickCapturePosition({
        x: event.clientX - shellRect.left - drag.offsetX,
        y: event.clientY - shellRect.top - drag.offsetY,
      }),
    )
  }, [clampQuickCapturePosition])

  const endQuickCaptureDrag = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = quickCaptureDragRef.current
    if (!drag || drag.pointerId !== event.pointerId) return
    quickCaptureDragRef.current = null
    setIsDraggingQuickCapture(false)
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId)
    }
  }, [])

  function tryApplyPendingSeek() {
    const req = pendingSeekRef.current
    if (!req || !instance || instance.instanceId !== req.instanceId) return
    const video = videoRef.current
    if (!video || video.readyState < 1) return
    seekToMs(req.ms)
    syncPlaybackClock(req.ms)
    pendingSeekRef.current = null
    lastAppliedNonceRef.current = req.nonce
    onSeekApplied?.(req.nonce)
    syncVideoUiState(video)
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
    syncPlaybackClock(targetMs)
    syncVideoUiState(video)
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
      const panel = quickCapturePanelRef.current
      if (!video || video.readyState < 1) return
      if (!isVideoInFullscreen(video) && !isElementInFullscreen(playerShellRef.current)) return
      if (event.defaultPrevented || event.isComposing) return
      if (event.key === "Escape" && isQuickCaptureOpen) {
        event.preventDefault()
        closeQuickCapturePanel()
        return
      }
      if (isQuickCaptureOpen) return
      if (event.altKey || event.ctrlKey || event.metaKey) return
      if (panel && event.target instanceof Node && panel.contains(event.target)) return
      if (isEditableTarget(event.target)) return

      if (event.code === "Space") {
        event.preventDefault()
        togglePlayback()
        return
      }

      if (event.code === "KeyN") {
        event.preventDefault()
        if (event.repeat || !instanceId || isQuickCaptureOpen) return
        void openQuickCapturePanel(undefined, true)
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
    closeQuickCapturePanel,
    instanceId,
    isQuickCaptureOpen,
    openQuickCapturePanel,
    seekByDelta,
    togglePlayback,
  ])

  const shouldRenderVideo = Boolean(src)
  const progressMax = Math.max(durationMs, 1)
  const durationLabel = durationMs > 0 ? formatPlaybackClock(durationMs) : "--:--.---"

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
          <div
            ref={playerShellRef}
            className={cn(
              "plm-video-shell relative overflow-hidden rounded-[1.2rem] border border-slate-900/10 bg-[#0f172a]",
              isShellFullscreen && "h-full w-full bg-[#020817] p-4",
            )}
          >
            <video
              ref={videoRef}
              className={cn(
                "plm-video-player w-full bg-[#0f172a]",
                isShellFullscreen
                  ? "h-[calc(100dvh-2rem)] max-h-full rounded-[1.4rem] border border-white/10 object-contain"
                  : "rounded-[1.2rem]",
              )}
              src={src ?? undefined}
              playsInline
              preload="metadata"
              onClick={() => {
                if (isQuickCaptureOpen) return
                togglePlayback()
              }}
              onDoubleClick={() => {
                if (isQuickCaptureOpen) return
                void toggleShellFullscreen()
              }}
              onLoadedData={() => {
                setMediaElementError(null)
                syncVideoUiState(videoRef.current)
              }}
              onLoadedMetadata={handleLoadedMetadata}
              onCanPlay={handleCanPlay}
              onDurationChange={() => syncVideoUiState(videoRef.current)}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
              onVolumeChange={() => syncVideoUiState(videoRef.current)}
              onError={handleVideoError}
              onEnded={handleEnded}
              onTimeUpdate={handleTimeUpdate}
              onSeeked={handleTimeUpdate}
            />

            <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex items-start justify-between gap-3 p-3">
              <div className="pointer-events-auto rounded-2xl border border-white/12 bg-black/45 px-3 py-1.5 text-[11px] text-white/78 backdrop-blur">
                空格 播放/暂停 · ←/→ 快退/快进 5 秒 · N 录入
              </div>
              {instance ? (
                <div className="pointer-events-auto rounded-2xl border border-white/12 bg-black/45 px-3 py-1.5 text-[11px] text-white/72 backdrop-blur">
                  {instance.materialDisplayName}
                </div>
              ) : null}
            </div>

            {!isPlaying && !isQuickCaptureOpen ? (
              <div className="pointer-events-none absolute inset-0 z-[9] flex items-center justify-center">
                <Button
                  type="button"
                  size="icon"
                  className="pointer-events-auto h-16 w-16 rounded-full bg-white/18 text-white shadow-[0_28px_64px_-34px_rgba(15,23,42,0.9)] backdrop-blur hover:bg-white/28"
                  onClick={togglePlayback}
                  title="播放"
                >
                  <Play className="h-6 w-6 fill-current" />
                  <span className="sr-only">播放</span>
                </Button>
              </div>
            ) : null}

            <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 p-3">
              <div className="pointer-events-auto rounded-[1.25rem] border border-white/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.3),rgba(2,6,23,0.72))] px-3 py-3 text-white shadow-[0_24px_56px_-34px_rgba(15,23,42,0.96)] backdrop-blur-md">
                <input
                  type="range"
                  min={0}
                  max={progressMax}
                  step={250}
                  value={Math.min(displayPlaybackMs, progressMax)}
                  onChange={(event) => applySeekMs(Number(event.target.value))}
                  disabled={durationMs <= 0}
                  className="plm-video-range w-full"
                  aria-label="播放进度"
                />
                <div className="mt-3 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      type="button"
                      size="icon"
                      variant="secondary"
                      className="h-10 w-10 rounded-full border-white/12 bg-white/10 text-white hover:bg-white/18"
                      onClick={togglePlayback}
                      title={isPlaying ? "暂停" : "播放"}
                    >
                      {isPlaying ? <Pause className="h-4 w-4 fill-current" /> : <Play className="h-4 w-4 fill-current" />}
                      <span className="sr-only">{isPlaying ? "暂停" : "播放"}</span>
                    </Button>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="h-9 w-9 rounded-full text-white/80 hover:bg-white/10 hover:text-white"
                      onClick={() => seekByDelta(-FULLSCREEN_KEYBOARD_SEEK_STEP_MS)}
                      title="后退 5 秒"
                    >
                      <RotateCcw className="h-4 w-4" />
                      <span className="sr-only">后退 5 秒</span>
                    </Button>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="h-9 w-9 rounded-full text-white/80 hover:bg-white/10 hover:text-white"
                      onClick={() => seekByDelta(FULLSCREEN_KEYBOARD_SEEK_STEP_MS)}
                      title="前进 5 秒"
                    >
                      <RotateCw className="h-4 w-4" />
                      <span className="sr-only">前进 5 秒</span>
                    </Button>
                    <div className="ml-1 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-white/72">
                      {formatPlaybackClock(displayPlaybackMs)} / {durationLabel}
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="h-9 w-9 rounded-full text-white/80 hover:bg-white/10 hover:text-white"
                      onClick={toggleMute}
                      title={isMuted ? "取消静音" : "静音"}
                    >
                      {isMuted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
                      <span className="sr-only">{isMuted ? "取消静音" : "静音"}</span>
                    </Button>
                    <input
                      type="range"
                      min={0}
                      max={100}
                      step={1}
                      value={isMuted ? 0 : volumePercent}
                      onChange={(event) => setVideoVolume(Number(event.target.value))}
                      className="plm-video-range plm-video-range-volume w-24"
                      aria-label="音量"
                    />
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      className="border-white/12 bg-white/10 text-white hover:bg-white/18"
                      onClick={() => void openQuickCapturePanel()}
                      disabled={!instanceId}
                    >
                      <NotebookPen className="h-4 w-4" />
                      快捷录入
                    </Button>
                    <Button
                      type="button"
                      size="icon"
                      variant="secondary"
                      className="h-10 w-10 rounded-full border-white/12 bg-white/10 text-white hover:bg-white/18"
                      onClick={() => void toggleShellFullscreen()}
                      title={isShellFullscreen ? "退出全屏" : "进入全屏"}
                    >
                      {isShellFullscreen ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
                      <span className="sr-only">{isShellFullscreen ? "退出全屏" : "进入全屏"}</span>
                    </Button>
                  </div>
                </div>
              </div>
            </div>

            {isQuickCaptureOpen ? (
              <div className="absolute inset-0 z-20" onPointerDown={closeQuickCapturePanel}>
                <div
                  ref={quickCapturePanelRef}
                  className="pointer-events-auto absolute overflow-hidden rounded-[1.35rem] border border-white/12 bg-[linear-gradient(180deg,rgba(11,18,32,0.94),rgba(15,23,42,0.92))] text-white shadow-[0_34px_72px_-34px_rgba(15,23,42,0.95)] backdrop-blur"
                  style={{
                    left: quickCapturePosition?.x ?? QUICK_CAPTURE_PANEL_MARGIN,
                    top: quickCapturePosition?.y ?? QUICK_CAPTURE_PANEL_MARGIN,
                    width: `min(${QUICK_CAPTURE_PANEL_WIDTH}px, calc(100% - ${QUICK_CAPTURE_PANEL_MARGIN * 2}px))`,
                    maxHeight: `calc(100% - ${QUICK_CAPTURE_PANEL_MARGIN * 2}px)`,
                  }}
                  onPointerDown={(event) => event.stopPropagation()}
                >
                  <div
                    className={cn(
                      "flex cursor-grab touch-none select-none items-center justify-between gap-3 border-b border-white/10 bg-white/[0.05] px-4 py-3",
                      isDraggingQuickCapture && "cursor-grabbing",
                    )}
                    onPointerDown={beginQuickCaptureDrag}
                    onPointerMove={continueQuickCaptureDrag}
                    onPointerUp={endQuickCaptureDrag}
                    onPointerCancel={endQuickCaptureDrag}
                    onLostPointerCapture={endQuickCaptureDrag}
                  >
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-2xl bg-white/10 text-[#dbeafe]">
                        <NotebookPen className="h-4 w-4" />
                      </div>
                      <div>
                        <div className="text-sm font-semibold text-white">快捷录入</div>
                        <div className="text-xs text-white/55">拖动标题栏可以挪位置</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="hidden items-center gap-1 rounded-full border border-white/10 bg-white/[0.04] px-2 py-1 text-[11px] text-white/55 sm:flex">
                        <GripHorizontal className="h-3.5 w-3.5" />
                        拖动
                      </div>
                      <Button
                        type="button"
                        size="icon"
                        variant="ghost"
                        data-quick-capture-action="ignore"
                        className="h-8 w-8 rounded-full text-white/75 hover:bg-white/10 hover:text-white"
                        onClick={closeQuickCapturePanel}
                      >
                        <X className="h-4 w-4" />
                        <span className="sr-only">关闭快捷录入</span>
                      </Button>
                    </div>
                  </div>

                  <div className="grid gap-3 overflow-y-auto px-4 pb-4 pt-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="inline-flex items-center rounded-full border border-cyan-300/18 bg-cyan-300/10 px-2.5 py-1 text-xs font-medium text-cyan-100">
                        锚点 {formatPlaybackClock(quickCaptureAnchorMs)}（t={quickCaptureAnchorMs}）
                      </div>
                      <div className="text-[11px] text-white/50">Ctrl+Enter 保存 · Esc 关闭</div>
                    </div>

                    <label className="grid gap-1.5 text-sm">
                      <span className="text-white/72">问题</span>
                      <textarea
                        ref={quickCaptureQuestionRef}
                        autoFocus
                        className="min-h-[72px] rounded-xl border border-white/12 bg-white/[0.06] px-3 py-2 text-sm text-white outline-none placeholder:text-white/32 focus:border-cyan-200/30 focus:bg-white/[0.08]"
                        value={quickCaptureQuestion}
                        onChange={(event) => {
                          setQuickCaptureQuestion(event.target.value)
                          if (quickCaptureError) setQuickCaptureError(null)
                        }}
                        onKeyDown={(event) => {
                          if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                            event.preventDefault()
                            saveQuickCapture()
                          }
                        }}
                        placeholder="问题/提示语"
                      />
                    </label>

                    <label className="grid gap-1.5 text-sm">
                      <span className="text-white/72">答案</span>
                      <textarea
                        className="min-h-[96px] rounded-xl border border-white/12 bg-white/[0.06] px-3 py-2 text-sm text-white outline-none placeholder:text-white/32 focus:border-cyan-200/30 focus:bg-white/[0.08]"
                        value={quickCaptureAnswer}
                        onChange={(event) => {
                          setQuickCaptureAnswer(event.target.value)
                          if (quickCaptureError) setQuickCaptureError(null)
                        }}
                        onKeyDown={(event) => {
                          if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                            event.preventDefault()
                            saveQuickCapture()
                          }
                        }}
                        placeholder="答案/复述内容"
                      />
                    </label>

                    <div className="flex items-end justify-between gap-3 pt-1">
                      <div className="min-h-[20px] text-xs text-rose-300">
                        {quickCaptureError ?? ""}
                      </div>
                      <div className="flex flex-wrap justify-end gap-2">
                        <Button
                          type="button"
                          variant="ghost"
                          className="text-white/72 hover:bg-white/10 hover:text-white"
                          onClick={closeQuickCapturePanel}
                        >
                          取消
                        </Button>
                        <Button type="button" onClick={saveQuickCapture}>
                          保存草稿
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
          </div>
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

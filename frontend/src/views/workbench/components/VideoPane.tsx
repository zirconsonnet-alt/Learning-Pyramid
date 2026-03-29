import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react"
import { useQueries } from "@tanstack/react-query"
import {
  Captions,
  LoaderCircle,
  Maximize2,
  Minus,
  Minimize2,
  NotebookPen,
  Pause,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  RotateCw,
  TriangleAlert,
  VideoOff,
  Volume2,
  VolumeX,
  X,
} from "lucide-react"

import type { Instance } from "@/ui/api/instances"
import { getRecallPoint, type RecallPoint } from "@/ui/api/review"
import {
  appendImageBlock,
  removeImageBlockAt,
  richContentHasMeaning,
  richText,
  setRichContentText,
  type RichContent,
} from "@/ui/api/richContent"
import { RichContentEditor } from "@/ui/components/RichContentEditor"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent } from "@/ui/components/ui/card"
import { resolveProjectFile, useProjectDirectoryBinding } from "@/ui/localMedia/projectDirectory"
import { useProjectMaterialSourceBinding } from "@/ui/queries/projects"
import { useSystemCapabilities } from "@/ui/queries/system"
import { useRecallPointsByInstance } from "@/ui/queries/workbench"
import { showInfoFeedback } from "@/ui/store/feedbackStore"
import { SUPPORTED_SUBTITLE_EXTENSIONS_LABEL } from "@/ui/subtitles/subtitleSupport"
import { addDailyPlaybackMs } from "@/ui/store/workbenchDailyStats"
import { clearPlaybackResumeMs, loadPlaybackResumeMs, savePlaybackResumeMs } from "@/ui/store/playbackResume"
import { saveVideoDurationMs } from "@/ui/store/videoDurations"
import { useWorkbenchStore } from "@/ui/store/workbenchStore"
import { cn } from "@/ui/utils"
import {
  VideoBarrageDetailCard,
  VideoBarrageLayer,
} from "./videoBarrage"
import { useVideoBarrage } from "./useVideoBarrage"
import { loadVideoBarrageEnabled, VIDEO_BARRAGE_STORAGE_KEY } from "./videoBarrageState"
import {
  loadVideoSubtitleDelayMs,
  loadVideoSubtitleEnabled,
  normalizeVideoSubtitleDelayMs,
  VIDEO_SUBTITLE_DELAY_LIMIT_MS,
  VIDEO_SUBTITLE_DELAY_STEP_MS,
  VIDEO_SUBTITLE_DELAY_STORAGE_KEY,
  VIDEO_SUBTITLE_STORAGE_KEY,
} from "./videoSubtitleState"
import { useVideoSubtitles } from "./useVideoSubtitles"

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

function isShortcutBlockedTarget(target: EventTarget | null) {
  if (!(target instanceof Element)) return false
  if (target instanceof HTMLElement && target.isContentEditable) return true
  if (target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement || target instanceof HTMLSelectElement) {
    return true
  }
  return Boolean(target.closest("input, textarea, select, [contenteditable='true']"))
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

function measureSubtitleDisplayUnits(value: string) {
  let total = 0
  for (const char of value) {
    total += /[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]/.test(char) ? 2 : 1
  }
  return total
}

function sliceSubtitleByDisplayUnits(value: string, maxUnits: number) {
  if (maxUnits <= 0 || !value) return ""
  let total = 0
  let out = ""
  for (const char of value) {
    const width = /[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]/.test(char) ? 2 : 1
    if (total + width > maxUnits) break
    out += char
    total += width
  }
  return out
}

function formatSubtitleLines(text: string | null | undefined) {
  const normalized = String(text ?? "").replace(/\s+/g, " ").trim()
  if (!normalized) return []
  const maxUnitsPerLine = 28
  const segments = normalized
    .split(/(?<=[，。！？；,.!?;:])\s*|\s+/)
    .map((segment) => segment.trim())
    .filter(Boolean)

  if (segments.length === 0) return [normalized]

  const lines: string[] = []
  let current = ""

  for (const segment of segments) {
    const candidate = current ? `${current} ${segment}` : segment
    if (!current || measureSubtitleDisplayUnits(candidate) <= maxUnitsPerLine) {
      current = candidate
      continue
    }
    lines.push(current)
    current = segment
    if (lines.length === 1 && measureSubtitleDisplayUnits(current) > maxUnitsPerLine) {
      break
    }
    if (lines.length >= 2) break
  }
  if (current && lines.length < 2) {
    lines.push(current)
  }

  if (lines.length === 0) {
    return [sliceSubtitleByDisplayUnits(normalized, maxUnitsPerLine)]
  }

  if (lines.length > 2) {
    return lines.slice(0, 2)
  }

  const consumed = lines.join(" ").trim()
  if (consumed.length < normalized.length) {
    const lastIndex = lines.length - 1
    const room = Math.max(8, maxUnitsPerLine - 2)
    lines[lastIndex] = `${sliceSubtitleByDisplayUnits(lines[lastIndex], room).trimEnd()}...`
  } else if (measureSubtitleDisplayUnits(lines[lines.length - 1]) > maxUnitsPerLine) {
    lines[lines.length - 1] = `${sliceSubtitleByDisplayUnits(lines[lines.length - 1], maxUnitsPerLine - 2).trimEnd()}...`
  }

  return lines.slice(0, 2)
}

function formatSubtitleDelayLabel(delayMs: number) {
  if (!delayMs) return "时序 0.00s"
  const seconds = Math.abs(delayMs) / 1000
  const formatted = seconds.toFixed(2)
  return delayMs > 0 ? `延后 ${formatted}s` : `提前 ${formatted}s`
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
  onDurationResolved,
  queueHasGate,
}: {
  projectId: string
  instance: Instance | null
  setCurrentMs: (v: number) => void
  seekTo?: { instanceId: string; ms: number; nonce: number } | null
  onSeekApplied?: (nonce: number) => void
  onDurationResolved?: (instanceId: string, durationMs: number) => void
  queueHasGate: boolean
}) {
  const playerShellRef = useRef<HTMLDivElement | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const barrageLayerRef = useRef<HTMLDivElement | null>(null)
  const questionInputRef = useRef<HTMLTextAreaElement | null>(null)
  const answerTextareaRef = useRef<HTMLTextAreaElement | null>(null)
  const pendingSeekRef = useRef<{ instanceId: string; ms: number; nonce: number } | null>(null)
  const fullscreenTransitionRef = useRef(false)
  const chromeHideTimerRef = useRef<number | null>(null)
  const lastNonZeroVolumeRef = useRef(1)
  const lastAppliedNonceRef = useRef<number | null>(null)
  const restoreSavedPositionRef = useRef(true)
  const lastPersistedPlaybackSecondRef = useRef<number | null>(null)
  const lastPlaybackTrackedAtRef = useRef<number | null>(null)

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
  const [questionContent, setQuestionContent] = useState<RichContent>(() => richText(""))
  const [answerContent, setAnswerContent] = useState<RichContent>(() => richText(""))
  const [captureError, setCaptureError] = useState<string | null>(null)
  const [isBarrageEnabled, setIsBarrageEnabled] = useState(() => loadVideoBarrageEnabled())
  const [isSubtitleEnabled, setIsSubtitleEnabled] = useState(() => loadVideoSubtitleEnabled())
  const [subtitleDelayMs, setSubtitleDelayMs] = useState(() => loadVideoSubtitleDelayMs())
  const [dismissedSubtitleErrorText, setDismissedSubtitleErrorText] = useState<string | null>(null)

  const addDraft = useWorkbenchStore((s) => s.addDraft)

  const instanceId = instance?.instanceId ?? null
  const capabilitiesQ = useSystemCapabilities()
  const materialSourceBindingQ = useProjectMaterialSourceBinding(projectId)
  const directoryBinding = useProjectDirectoryBinding(projectId)
  const serverMediaStreamEnabled = capabilitiesQ.data?.serverMediaStreamEnabled ?? false
  const browserLocalMediaEnabled = capabilitiesQ.data?.browserLocalMediaEnabled ?? false
  const displayPlaybackMs = durationMs > 0 ? Math.min(playbackMs, durationMs) : playbackMs
  const progressMax = Math.max(durationMs, 1)
  const playbackProgressPercent = progressMax > 0 ? Math.min(100, Math.max(0, (displayPlaybackMs / progressMax) * 100)) : 0
  const durationLabel = durationMs > 0 ? formatPlaybackClock(durationMs) : "--:--"
  const chromeVisible = isChromeAwake || !isPlaying || isCapturePanelOpen
  const playbackRateLabel = `${Number.isInteger(playbackRate) ? playbackRate.toFixed(0) : playbackRate.toFixed(2).replace(/0$/, "")}x`
  const recallPointIdsQ = useRecallPointsByInstance(projectId, instanceId ?? "")
  const recallPointQs = useQueries({
    queries: (recallPointIdsQ.data?.recallPointIds ?? []).map((recallPointId) => ({
      queryKey: ["recallPoint", projectId, recallPointId],
      queryFn: () => getRecallPoint(projectId, recallPointId),
      enabled: !!projectId && !!instanceId && !!recallPointId,
      staleTime: 30_000,
    })),
  })
  const recallPoints = useMemo<RecallPoint[]>(
    () => recallPointQs.flatMap((query) => (query.data ? [query.data] : [])),
    [recallPointQs],
  )
  const subtitleState = useVideoSubtitles({
    projectId,
    instance,
    playbackMs: displayPlaybackMs,
    enabled: isSubtitleEnabled && !!materialSourceBindingQ.data?.sourceKind,
    sourceKind: materialSourceBindingQ.data?.sourceKind,
    subtitleDelayMs,
  })
  const subtitleErrorDismissed = !!subtitleState.errorText && subtitleState.errorText === dismissedSubtitleErrorText
  const subtitleStatusText = isSubtitleEnabled
    ? subtitleState.isLoading
      ? "正在查找并读取字幕文件..."
      : subtitleState.errorText && !subtitleErrorDismissed
        ? subtitleState.errorText
        : null
    : null
  const subtitleButtonLabel = subtitleState.isLoading ? "字幕载入" : isSubtitleEnabled ? "字幕开" : "字幕关"
  const subtitleDisplayLines = useMemo(() => formatSubtitleLines(subtitleState.text), [subtitleState.text])
  const subtitleDelayLabel = useMemo(() => formatSubtitleDelayLabel(subtitleDelayMs), [subtitleDelayMs])

  const flushPlaybackDuration = useCallback(() => {
    if (!instanceId) {
      lastPlaybackTrackedAtRef.current = null
      return
    }
    const now = performance.now()
    const previous = lastPlaybackTrackedAtRef.current
    lastPlaybackTrackedAtRef.current = now
    if (previous === null) return
    const deltaMs = Math.max(0, Math.min(now - previous, 5000))
    if (deltaMs > 0) addDailyPlaybackMs(projectId, deltaMs)
  }, [instanceId, projectId])

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
    const nextDurationMs = readDurationMs(video)
    setDurationMs(nextDurationMs)
    if (instanceId && nextDurationMs > 0) {
      saveVideoDurationMs(projectId, instanceId, nextDurationMs)
      onDurationResolved?.(instanceId, nextDurationMs)
    }
    setIsPlaying(!video.paused && !video.ended)
    const effectiveMuted = video.muted || video.volume <= 0
    setIsMuted(effectiveMuted)
    setVolumePercent(Math.round(video.volume * 100))
    setPlaybackRate(video.playbackRate)
    if (video.volume > 0) {
      lastNonZeroVolumeRef.current = video.volume
    }
  }, [instanceId, onDurationResolved, projectId])

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

  const applySubtitleDelayMs = useCallback(
    (nextDelayMs: number, options?: { announce?: boolean }) => {
      const normalized = normalizeVideoSubtitleDelayMs(nextDelayMs)
      setSubtitleDelayMs(normalized)
      if (options?.announce) {
        showInfoFeedback("字幕时序已调整", `${formatSubtitleDelayLabel(normalized)}（范围 ±${(VIDEO_SUBTITLE_DELAY_LIMIT_MS / 1000).toFixed(0)}s）`)
      }
    },
    [],
  )

  const nudgeSubtitleDelay = useCallback(
    (deltaMs: number) => {
      applySubtitleDelayMs(subtitleDelayMs + deltaMs, { announce: true })
    },
    [applySubtitleDelayMs, subtitleDelayMs],
  )

  const resetSubtitleDelay = useCallback(() => {
    if (subtitleDelayMs === 0) return
    applySubtitleDelayMs(0, { announce: true })
  }, [applySubtitleDelayMs, subtitleDelayMs])

  const renderCompactSubtitleDelayControls = useCallback(
    (tone: "default" | "danger" = "default") => {
      if (!isSubtitleEnabled) return null
      return (
        <div className="mt-2 flex items-center justify-center gap-1 md:hidden">
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className={cn(
              "h-7 w-7 rounded-full border text-white/82 hover:bg-white/12 hover:text-white",
              tone === "danger" ? "border-white/14 bg-white/8" : "border-white/12 bg-white/[0.05]",
            )}
            onClick={() => nudgeSubtitleDelay(-VIDEO_SUBTITLE_DELAY_STEP_MS)}
            title={`字幕提前 ${(VIDEO_SUBTITLE_DELAY_STEP_MS / 1000).toFixed(2)}s`}
          >
            <Minus className="h-3.5 w-3.5" />
            <span className="sr-only">字幕提前 {VIDEO_SUBTITLE_DELAY_STEP_MS} 毫秒</span>
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className={cn(
              "h-7 min-w-[6.25rem] rounded-full border px-2 text-[10px] tabular-nums hover:bg-white/12 hover:text-white",
              subtitleDelayMs === 0 ? "text-white/56" : "text-white/82",
              tone === "danger" ? "border-white/14 bg-white/8" : "border-white/12 bg-white/[0.05]",
            )}
            onClick={resetSubtitleDelay}
            disabled={subtitleDelayMs === 0}
            title={subtitleDelayMs === 0 ? "字幕时序已归零" : "重置字幕时序"}
          >
            {subtitleDelayLabel}
          </Button>
          <Button
            type="button"
            size="icon"
            variant="ghost"
            className={cn(
              "h-7 w-7 rounded-full border text-white/82 hover:bg-white/12 hover:text-white",
              tone === "danger" ? "border-white/14 bg-white/8" : "border-white/12 bg-white/[0.05]",
            )}
            onClick={() => nudgeSubtitleDelay(VIDEO_SUBTITLE_DELAY_STEP_MS)}
            title={`字幕延后 ${(VIDEO_SUBTITLE_DELAY_STEP_MS / 1000).toFixed(2)}s`}
          >
            <Plus className="h-3.5 w-3.5" />
            <span className="sr-only">字幕延后 {VIDEO_SUBTITLE_DELAY_STEP_MS} 毫秒</span>
          </Button>
        </div>
      )
    },
    [isSubtitleEnabled, nudgeSubtitleDelay, resetSubtitleDelay, subtitleDelayLabel, subtitleDelayMs],
  )

  const toggleSubtitles = useCallback(() => {
    if (!instanceId) return
    if (materialSourceBindingQ.isLoading) {
      showInfoFeedback("正在准备字幕", "素材来源信息还在加载，稍后再试。")
      return
    }
    if (materialSourceBindingQ.error || !materialSourceBindingQ.data?.sourceKind) {
      showInfoFeedback("字幕暂不可用", "当前项目的素材来源信息不可用，暂时无法检查同目录字幕文件。")
      return
    }
    if (materialSourceBindingQ.data.sourceKind === "BROWSER_LOCAL" && directoryBinding.permission !== "granted") {
      showInfoFeedback("字幕暂不可用", "浏览器还没有本地目录读取权限，暂时无法检查视频同目录下的字幕文件。")
      return
    }
    setIsSubtitleEnabled((current) => {
      const next = !current
      if (next) {
        showInfoFeedback("字幕已开启", `系统会检查视频同目录下的同名字幕文件（${SUPPORTED_SUBTITLE_EXTENSIONS_LABEL}）。全屏时可按 [ / ] 微调时序，按 \\ 归零。`)
      }
      return next
    })
  }, [directoryBinding.permission, instanceId, materialSourceBindingQ.data?.sourceKind, materialSourceBindingQ.error, materialSourceBindingQ.isLoading])

  const closeCapturePanel = useCallback(() => {
    setIsCapturePanelOpen(false)
    setCaptureError(null)
    setQuestionContent(richText(""))
    setAnswerContent(richText(""))
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
      setQuestionContent(richText(""))
      setAnswerContent(richText(""))
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
    if (!richContentHasMeaning(questionContent) || !richContentHasMeaning(answerContent)) {
      setCaptureError("问题和答案都要填写，可输入文字或粘贴图片。")
      return
    }

    const now = Date.now()
    addDraft(projectId, {
      localId: newLocalId(),
      instanceId,
      position: `t=${captureAnchorMs}`,
      question: questionContent,
      answer: answerContent,
      createdAt: now,
      updatedAt: now,
    })
    closeCapturePanel()
  }, [
    addDraft,
    answerContent,
    captureAnchorMs,
    closeCapturePanel,
    instanceId,
    projectId,
    questionContent,
    queueHasGate,
  ])

  function handleTimeUpdate() {
    const video = videoRef.current
    if (!video) return
    if (!video.paused && !video.ended) {
      flushPlaybackDuration()
    }
    const nextMs = Math.max(0, Math.floor(video.currentTime * 1000))
    syncPlaybackClock(nextMs)
    if (!instanceId) return
    const currentSecond = Math.floor(nextMs / 1000)
    if (lastPersistedPlaybackSecondRef.current === currentSecond) return
    lastPersistedPlaybackSecondRef.current = currentSecond
    savePlaybackResumeMs(projectId, instanceId, nextMs)
  }

  useEffect(() => {
    if (typeof window === "undefined") return
    try {
      window.localStorage.setItem(VIDEO_BARRAGE_STORAGE_KEY, isBarrageEnabled ? "1" : "0")
    } catch {
      // Ignore storage write failures and keep playback responsive.
    }
  }, [isBarrageEnabled])

  useEffect(() => {
    if (typeof window === "undefined") return
    try {
      window.localStorage.setItem(VIDEO_SUBTITLE_STORAGE_KEY, isSubtitleEnabled ? "1" : "0")
    } catch {
      // Ignore storage write failures and keep playback responsive.
    }
  }, [isSubtitleEnabled])

  useEffect(() => {
    if (typeof window === "undefined") return
    try {
      window.localStorage.setItem(VIDEO_SUBTITLE_DELAY_STORAGE_KEY, String(subtitleDelayMs))
    } catch {
      // Ignore storage write failures and keep playback responsive.
    }
  }, [subtitleDelayMs])

  useEffect(() => {
    if (!isSubtitleEnabled || !subtitleState.errorText) {
      setDismissedSubtitleErrorText(null)
    }
  }, [isSubtitleEnabled, subtitleState.errorText])

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
    setQuestionContent(richText(""))
    setAnswerContent(richText(""))
    setCaptureError(null)
    pendingSeekRef.current = null
    lastAppliedNonceRef.current = null
    restoreSavedPositionRef.current = true
    lastPersistedPlaybackSecondRef.current = null
    lastPlaybackTrackedAtRef.current = null
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

  const { hoveredBarrage } = useVideoBarrage({
    projectId,
    instanceId,
    recallPoints,
    playerShellRef,
    videoRef,
    barrageLayerRef,
    sourceKey: src ?? "",
    isEnabled: isBarrageEnabled,
    isCapturePanelOpen,
  })

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
      if (isShortcutBlockedTarget(event.target)) return

      if (event.code === "Space") {
        event.preventDefault()
        togglePlayback()
        return
      }

      if ((event.key === "c" || event.key === "C") && !isCapturePanelOpen) {
        event.preventDefault()
        toggleSubtitles()
        return
      }

      if ((event.key === "[" || event.code === "BracketLeft") && !isCapturePanelOpen) {
        event.preventDefault()
        if (!isSubtitleEnabled) return
        nudgeSubtitleDelay(-VIDEO_SUBTITLE_DELAY_STEP_MS)
        wakeChrome()
        return
      }

      if ((event.key === "]" || event.code === "BracketRight") && !isCapturePanelOpen) {
        event.preventDefault()
        if (!isSubtitleEnabled) return
        nudgeSubtitleDelay(VIDEO_SUBTITLE_DELAY_STEP_MS)
        wakeChrome()
        return
      }

      if ((event.key === "\\" || event.code === "Backslash") && !isCapturePanelOpen) {
        event.preventDefault()
        if (!isSubtitleEnabled) return
        resetSubtitleDelay()
        wakeChrome()
        return
      }

      if ((event.key === "Enter" || event.code === "NumpadEnter") && !isCapturePanelOpen) {
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
    isSubtitleEnabled,
    nudgeSubtitleDelay,
    openCapturePanel,
    resetSubtitleDelay,
    seekByDelta,
    toggleSubtitles,
    togglePlayback,
    wakeChrome,
  ])

  const shouldRenderVideo = Boolean(src)

  return (
    <Card className="theme-card-main overflow-hidden">
      <CardContent className="space-y-4 p-4">
        {shouldRenderVideo ? (
          <div
            ref={playerShellRef}
            className={cn(
              "group relative h-[clamp(18rem,52vh,36rem)] overflow-hidden rounded-[1.2rem] border border-slate-900/10 bg-[#050816] sm:h-[clamp(20rem,56vh,40rem)]",
              isShellFullscreen && "h-full w-full bg-black p-4",
            )}
            onPointerMove={wakeChrome}
            onPointerEnter={wakeChrome}
          >
            <video
              ref={videoRef}
              className={cn(
                "plm-video-player h-full w-full bg-black",
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
                lastPlaybackTrackedAtRef.current = performance.now()
                setIsPlaying(true)
                wakeChrome()
              }}
              onPause={() => {
                flushPlaybackDuration()
                lastPlaybackTrackedAtRef.current = null
                setIsPlaying(false)
              }}
              onVolumeChange={() => syncVideoUiState(videoRef.current)}
              onError={handleVideoError}
              onEnded={() => {
                flushPlaybackDuration()
                lastPlaybackTrackedAtRef.current = null
                handleEnded()
              }}
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

            <VideoBarrageLayer
              layerRef={barrageLayerRef}
              isEnabled={isBarrageEnabled}
              isCapturePanelOpen={isCapturePanelOpen}
            />
            <VideoBarrageDetailCard
              projectId={projectId}
              hoveredBarrage={hoveredBarrage}
              isEnabled={isBarrageEnabled}
              isCapturePanelOpen={isCapturePanelOpen}
            />

            {subtitleState.text ? (
              <div className="pointer-events-none absolute inset-x-0 bottom-16 z-[18] flex justify-center px-4">
                <div
                  className={cn(
                    "max-w-[min(78ch,calc(100%-1rem))] rounded-[1rem] border border-white/18 bg-black/48 px-4 py-2.5 text-center text-white shadow-[0_18px_42px_-28px_rgba(0,0,0,0.92)] backdrop-blur-xl",
                  )}
                >
                  {subtitleDisplayLines.map((line, index) => (
                    <div
                      key={`${index}:${line}`}
                      className={cn(
                        "text-sm font-medium leading-6 [text-shadow:0_1px_8px_rgba(0,0,0,0.55)] sm:text-[15px]",
                        index > 0 && "mt-0.5",
                      )}
                    >
                      {line}
                    </div>
                  ))}
                  {renderCompactSubtitleDelayControls()}
                </div>
              </div>
            ) : null}

            {!subtitleState.text && subtitleStatusText ? (
              <div className="pointer-events-none absolute inset-x-0 bottom-16 z-[18] flex justify-center px-4">
                <div
                  className={cn(
                    "pointer-events-auto max-w-[min(34rem,calc(100%-1rem))] rounded-[1rem] border px-4 py-3 shadow-[0_18px_42px_-28px_rgba(0,0,0,0.92)] backdrop-blur-xl",
                    subtitleState.errorText
                      ? "border-rose-300/18 bg-rose-950/54 text-rose-100"
                      : "border-white/12 bg-slate-950/68 text-white/78",
                  )}
                >
                  <div className="flex items-center justify-center gap-2 text-center text-xs leading-6 sm:text-sm">
                    {subtitleState.errorText ? (
                      <TriangleAlert className="h-4 w-4 shrink-0" />
                    ) : (
                      <LoaderCircle className="h-4 w-4 shrink-0 animate-spin" />
                    )}
                    <span>{subtitleStatusText}</span>
                  </div>
                  <div className="mt-2 flex items-center justify-center gap-2">
                    {subtitleState.errorText ? (
                      <div className="flex flex-col items-center justify-center">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          className="h-8 gap-1.5 rounded-full border-white/18 bg-white/8 px-3 text-xs text-white hover:bg-white/14"
                          onClick={() => {
                            setDismissedSubtitleErrorText(null)
                            subtitleState.retry()
                          }}
                          disabled={subtitleState.isLoading}
                        >
                          <RefreshCw className={cn("h-3.5 w-3.5", subtitleState.isLoading && "animate-spin")} />
                          {subtitleState.isLoading ? "重试中..." : "重试字幕"}
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          className="mt-2 h-8 gap-1.5 rounded-full px-3 text-xs text-white/78 hover:bg-white/10 hover:text-white"
                          onClick={() => setDismissedSubtitleErrorText(subtitleState.errorText ?? null)}
                        >
                          <X className="h-3.5 w-3.5" />
                          关闭提示
                        </Button>
                        {renderCompactSubtitleDelayControls("danger")}
                      </div>
                    ) : (
                      <div>
                        <div className="text-[11px] text-white/54">
                          系统只会读取视频同目录下的同名字幕文件，不会再用 ASR 或 ffmpeg 自动生成字幕。
                        </div>
                        {renderCompactSubtitleDelayControls()}
                      </div>
                    )}
                  </div>
                </div>
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
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className={cn(
                          "h-7 min-w-[4.5rem] gap-1.5 rounded-full px-2 text-[10px] sm:text-[11px]",
                          isSubtitleEnabled
                            ? "border border-emerald-200/18 bg-emerald-300/18 text-emerald-50 hover:bg-emerald-300/24"
                            : "border border-white/10 text-white/72 hover:bg-white/10 hover:text-white",
                        )}
                        aria-pressed={isSubtitleEnabled}
                        onClick={toggleSubtitles}
                        disabled={!instanceId}
                        title={
                          isSubtitleEnabled
                            ? "字幕已开启，点击关闭 (全屏时按 C；[ / ] 微调时序，\\ 归零)"
                            : `字幕已关闭，点击开启后会检查同目录同名字幕文件 (${SUPPORTED_SUBTITLE_EXTENSIONS_LABEL})`
                        }
                      >
                        {subtitleState.isLoading ? (
                          <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Captions className="h-3.5 w-3.5" />
                        )}
                        {subtitleButtonLabel}
                      </Button>
                      {isSubtitleEnabled ? (
                        <div className="hidden items-center gap-1 rounded-full border border-white/12 bg-white/[0.06] px-1 py-1 text-[10px] text-white/76 md:flex">
                          <Button
                            type="button"
                            size="icon"
                            variant="ghost"
                            className="h-6 w-6 rounded-full text-white/78 hover:bg-white/10 hover:text-white"
                            onClick={() => nudgeSubtitleDelay(-VIDEO_SUBTITLE_DELAY_STEP_MS)}
                            title={`字幕提前 ${(VIDEO_SUBTITLE_DELAY_STEP_MS / 1000).toFixed(2)}s ([)`}
                          >
                            <Minus className="h-3.5 w-3.5" />
                            <span className="sr-only">字幕提前 {VIDEO_SUBTITLE_DELAY_STEP_MS} 毫秒</span>
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            className={cn(
                              "h-6 min-w-[6.5rem] rounded-full px-2 text-[10px] tabular-nums hover:bg-white/10 hover:text-white",
                              subtitleDelayMs === 0 ? "text-white/54" : "text-white/82",
                            )}
                            onClick={resetSubtitleDelay}
                            disabled={subtitleDelayMs === 0}
                            title={
                              subtitleDelayMs === 0
                                ? "字幕时序已归零"
                                : "重置字幕时序 (\\)"
                            }
                          >
                            {subtitleDelayLabel}
                          </Button>
                          <Button
                            type="button"
                            size="icon"
                            variant="ghost"
                            className="h-6 w-6 rounded-full text-white/78 hover:bg-white/10 hover:text-white"
                            onClick={() => nudgeSubtitleDelay(VIDEO_SUBTITLE_DELAY_STEP_MS)}
                            title={`字幕延后 ${(VIDEO_SUBTITLE_DELAY_STEP_MS / 1000).toFixed(2)}s (])`}
                          >
                            <Plus className="h-3.5 w-3.5" />
                            <span className="sr-only">字幕延后 {VIDEO_SUBTITLE_DELAY_STEP_MS} 毫秒</span>
                          </Button>
                        </div>
                      ) : null}
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className={cn(
                          "h-7 min-w-[4.5rem] rounded-full px-2 text-[10px] sm:text-[11px]",
                          isBarrageEnabled
                            ? "border border-cyan-200/18 bg-cyan-300/18 text-cyan-50 hover:bg-cyan-300/24"
                            : "border border-white/10 text-white/72 hover:bg-white/10 hover:text-white",
                        )}
                        aria-pressed={isBarrageEnabled}
                        onClick={() => setIsBarrageEnabled((current) => !current)}
                        title={isBarrageEnabled ? "弹幕已开启，点击关闭" : "弹幕已关闭，点击开启"}
                      >
                        {isBarrageEnabled ? "弹幕开" : "弹幕关"}
                      </Button>
                      {isShellFullscreen ? (
                        <Button
                          type="button"
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 rounded-full text-white hover:bg-white/10"
                        onClick={() => void openCapturePanel()}
                        disabled={!instanceId || queueHasGate}
                        title="记复述点 (Enter)"
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
                      title="关闭记复述点"
                    >
                      <X className="h-4 w-4" />
                      <span className="sr-only">关闭记复述点</span>
                    </Button>
                  </div>

                  <div className="mt-3 space-y-3">
                    <label className="block">
                      <div className="mb-1 text-xs text-white/62">问题</div>
                      <RichContentEditor
                        projectId={projectId}
                        field="question"
                        value={questionContent}
                        textareaRef={questionInputRef}
                        placeholder="输入复述点问题，或直接 Ctrl+V 粘贴图片"
                        textareaClassName="min-h-[84px] rounded-xl border-white/10 bg-white/[0.05] px-3 py-2 text-sm text-white outline-none placeholder:text-white/28 focus:border-cyan-200/24 focus:bg-white/[0.08]"
                        imageClassName="h-24 w-24 rounded-xl border-white/10 bg-white/[0.06] object-cover"
                        onTextChange={(text) => {
                          setQuestionContent((prev) => setRichContentText(prev, text))
                          if (captureError) setCaptureError(null)
                        }}
                        onAppendImage={(assetId) => {
                          setQuestionContent((prev) => appendImageBlock(prev, assetId))
                          if (captureError) setCaptureError(null)
                        }}
                        onRemoveImage={(imageIndex) => {
                          setQuestionContent((prev) => removeImageBlockAt(prev, imageIndex))
                          if (captureError) setCaptureError(null)
                        }}
                        onTextKeyDown={(event) => {
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
                      <RichContentEditor
                        projectId={projectId}
                        field="answer"
                        value={answerContent}
                        textareaRef={answerTextareaRef}
                        placeholder="输入答案或你的复述内容，或直接 Ctrl+V 粘贴图片"
                        textareaClassName="min-h-[124px] rounded-xl border-white/10 bg-white/[0.05] px-3 py-2 text-sm text-white outline-none placeholder:text-white/28 focus:border-cyan-200/24 focus:bg-white/[0.08]"
                        imageClassName="h-24 w-24 rounded-xl border-white/10 bg-white/[0.06] object-cover"
                        onTextChange={(text) => {
                          setAnswerContent((prev) => setRichContentText(prev, text))
                          if (captureError) setCaptureError(null)
                        }}
                        onAppendImage={(assetId) => {
                          setAnswerContent((prev) => appendImageBlock(prev, assetId))
                          if (captureError) setCaptureError(null)
                        }}
                        onRemoveImage={(imageIndex) => {
                          setAnswerContent((prev) => removeImageBlockAt(prev, imageIndex))
                          if (captureError) setCaptureError(null)
                        }}
                        onTextKeyDown={(event) => {
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
                    {captureError ?? "全屏时 Enter 可打开录入；问题中 Enter 切到答案，答案中 Enter 保存，Ctrl+Enter 换行，Ctrl+V 粘贴图片会先上传到服务器。"}
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
              <div className="theme-icon-surface mt-0.5 h-10 w-10 shrink-0">
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

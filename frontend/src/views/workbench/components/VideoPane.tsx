import { useCallback, useEffect, useMemo, useRef, useState } from "react"
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
import { richContentHasMeaning, richContentText, richText } from "@/ui/api/richContent"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent } from "@/ui/components/ui/card"
import { resolveProjectFile, useProjectDirectoryBinding } from "@/ui/localMedia/projectDirectory"
import { useSystemCapabilities } from "@/ui/queries/system"
import { showInfoFeedback } from "@/ui/store/feedbackStore"
import { clearPlaybackResumeMs, loadPlaybackResumeMs, savePlaybackResumeMs } from "@/ui/store/playbackResume"
import { useWorkbenchStore, type DraftRecallPoint } from "@/ui/store/workbenchStore"
import { cn } from "@/ui/utils"

const FULLSCREEN_KEYBOARD_SEEK_STEP_MS = 5000
const CHROME_HIDE_DELAY_MS = 1600
const BARRAGE_ANIMATION_DURATION_MS = 9000
const BARRAGE_INLINE_LANES = 3
const BARRAGE_FULLSCREEN_LANES = 5
const BARRAGE_TOP_OFFSET_PX = 18
const BARRAGE_LANE_HEIGHT_PX = 42
const PLAYBACK_RATE_OPTIONS = [0.75, 1, 1.25, 1.5, 2]

type FullscreenCapableVideo = HTMLVideoElement & {
  webkitDisplayingFullscreen?: boolean
}

type BarrageDraft = {
  localId: string
  anchorMs: number
  questionText: string
  questionLabel: string
  hasAnswer: boolean
}

type ActiveBarrageItem = {
  id: string
  localId: string
  questionText: string
  questionLabel: string
  lane: number
  hasAnswer: boolean
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

function parseAnchorMs(position: string): number | null {
  const match = position.match(/^t=(\d+)$/)
  if (!match) return null
  const value = Number(match[1])
  return Number.isFinite(value) ? value : null
}

function newLocalId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}_${Math.random().toString(16).slice(2)}`
}

function truncateLabel(text: string, max = 22) {
  const normalized = text.replace(/\s+/g, " ").trim()
  if (normalized.length <= max) return normalized
  return `${normalized.slice(0, max)}...`
}

function draftQuestionText(draft: DraftRecallPoint) {
  const text = richContentText(draft.question).replace(/\s+/g, " ").trim()
  if (text) return text
  return richContentHasMeaning(draft.question) ? "图片问题" : ""
}

function draftAnswerText(draft: DraftRecallPoint) {
  return richContentText(draft.answer)
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
  const questionInputRef = useRef<HTMLInputElement | null>(null)
  const answerTextareaRef = useRef<HTMLTextAreaElement | null>(null)
  const pendingSeekRef = useRef<{ instanceId: string; ms: number; nonce: number } | null>(null)
  const fullscreenTransitionRef = useRef(false)
  const chromeHideTimerRef = useRef<number | null>(null)
  const lastNonZeroVolumeRef = useRef(1)
  const lastAppliedNonceRef = useRef<number | null>(null)
  const lastPlaybackMsRef = useRef(0)
  const restoreSavedPositionRef = useRef(true)
  const lastPersistedPlaybackSecondRef = useRef<number | null>(null)
  const spawnedDraftKeysRef = useRef<Set<string>>(new Set())
  const barrageLaneCursorRef = useRef(0)

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
  const [isQuestionComposerOpen, setIsQuestionComposerOpen] = useState(false)
  const [questionAnchorMs, setQuestionAnchorMs] = useState(0)
  const [questionText, setQuestionText] = useState("")
  const [questionError, setQuestionError] = useState<string | null>(null)
  const [answerDraftId, setAnswerDraftId] = useState<string | null>(null)
  const [answerText, setAnswerText] = useState("")
  const [answerError, setAnswerError] = useState<string | null>(null)
  const [activeBarrageItems, setActiveBarrageItems] = useState<ActiveBarrageItem[]>([])

  const projectDrafts = useWorkbenchStore((s) => s.byProjectId[projectId]?.drafts ?? [])
  const addDraft = useWorkbenchStore((s) => s.addDraft)
  const updateDraftText = useWorkbenchStore((s) => s.updateDraftText)

  const instanceId = instance?.instanceId ?? null
  const capabilitiesQ = useSystemCapabilities()
  const directoryBinding = useProjectDirectoryBinding(projectId)
  const serverMediaStreamEnabled = capabilitiesQ.data?.serverMediaStreamEnabled ?? false
  const browserLocalMediaEnabled = capabilitiesQ.data?.browserLocalMediaEnabled ?? false

  const instanceDrafts = useMemo(
    () => (instanceId ? projectDrafts.filter((draft) => draft.instanceId === instanceId) : []),
    [instanceId, projectDrafts],
  )

  const draftById = useMemo(() => {
    const map: Record<string, DraftRecallPoint> = {}
    for (const draft of instanceDrafts) map[draft.localId] = draft
    return map
  }, [instanceDrafts])

  const barrageDrafts = useMemo(
    () =>
      instanceDrafts
        .map((draft) => {
          const anchorMs = parseAnchorMs(draft.position)
          const questionTextValue = draftQuestionText(draft)
          if (anchorMs === null || !questionTextValue) return null
          return {
            localId: draft.localId,
            anchorMs,
            questionText: questionTextValue,
            questionLabel: truncateLabel(questionTextValue),
            hasAnswer: richContentHasMeaning(draft.answer),
          } satisfies BarrageDraft
        })
        .filter((draft): draft is BarrageDraft => draft !== null)
        .sort((left, right) => left.anchorMs - right.anchorMs),
    [instanceDrafts],
  )

  const answerDraft = answerDraftId ? draftById[answerDraftId] ?? null : null
  const answerDraftAnchorMs = answerDraft ? parseAnchorMs(answerDraft.position) ?? 0 : 0
  const barrageLaneCount = isShellFullscreen ? BARRAGE_FULLSCREEN_LANES : BARRAGE_INLINE_LANES
  const displayPlaybackMs = durationMs > 0 ? Math.min(playbackMs, durationMs) : playbackMs
  const progressMax = Math.max(durationMs, 1)
  const durationLabel = durationMs > 0 ? formatPlaybackClock(durationMs) : "--:--.---"
  const chromeVisible = isChromeAwake || !isPlaying || isQuestionComposerOpen || answerDraftId !== null
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
    if (!isPlaying || isQuestionComposerOpen || answerDraftId !== null) return
    chromeHideTimerRef.current = window.setTimeout(() => setIsChromeAwake(false), CHROME_HIDE_DELAY_MS)
  }, [answerDraftId, clearChromeHideTimer, isPlaying, isQuestionComposerOpen])

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

  const cyclePlaybackRate = useCallback(() => {
    const currentIndex = PLAYBACK_RATE_OPTIONS.findIndex((rate) => Math.abs(rate - playbackRate) < 0.001)
    const nextIndex = currentIndex >= 0 ? (currentIndex + 1) % PLAYBACK_RATE_OPTIONS.length : 1
    setVideoPlaybackRate(PLAYBACK_RATE_OPTIONS[nextIndex] ?? 1)
  }, [playbackRate, setVideoPlaybackRate])

  const closeQuestionComposer = useCallback(() => {
    setIsQuestionComposerOpen(false)
    setQuestionError(null)
    setQuestionText("")
  }, [])

  const closeAnswerEditor = useCallback(() => {
    setAnswerDraftId(null)
    setAnswerError(null)
    setAnswerText("")
  }, [])

  const openQuestionComposer = useCallback(
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

      closeAnswerEditor()
      setQuestionAnchorMs(captureMs)
      setQuestionText("")
      setQuestionError(null)
      setIsQuestionComposerOpen(true)
      wakeChrome()
    },
    [
      closeAnswerEditor,
      instanceId,
      persistPlaybackPosition,
      queueHasGate,
      requestShellFullscreen,
      syncPlaybackClock,
      syncVideoUiState,
      wakeChrome,
    ],
  )

  const openAnswerEditor = useCallback(
    (localId: string, seekToAnchor = false) => {
      const draft = draftById[localId]
      if (!draft) return
      const video = videoRef.current
      const anchorMs = parseAnchorMs(draft.position)

      if (video) {
        video.pause()
        if (seekToAnchor && anchorMs !== null) {
          const nextMs = clampPlaybackMs(video, anchorMs)
          video.currentTime = nextMs / 1000
          syncPlaybackClock(nextMs)
          persistPlaybackPosition(nextMs)
        } else {
          const pauseMs = clampPlaybackMs(video, Math.floor(video.currentTime * 1000))
          syncPlaybackClock(pauseMs)
          persistPlaybackPosition(pauseMs)
        }
        syncVideoUiState(video)
      }

      closeQuestionComposer()
      setAnswerDraftId(draft.localId)
      setAnswerText(draftAnswerText(draft))
      setAnswerError(null)
      wakeChrome()
    },
    [
      closeQuestionComposer,
      draftById,
      persistPlaybackPosition,
      syncPlaybackClock,
      syncVideoUiState,
      wakeChrome,
    ],
  )

  const spawnBarrageItem = useCallback(
    (draft: BarrageDraft) => {
      const lane = barrageLaneCursorRef.current % barrageLaneCount
      barrageLaneCursorRef.current += 1
      const nextItem: ActiveBarrageItem = {
        id: `${draft.localId}_${Date.now()}_${Math.random().toString(16).slice(2)}`,
        localId: draft.localId,
        questionText: draft.questionText,
        questionLabel: draft.questionLabel,
        lane,
        hasAnswer: draft.hasAnswer,
      }
      setActiveBarrageItems((items) => [...items.filter((item) => item.localId !== draft.localId), nextItem])
    },
    [barrageLaneCount],
  )

  const saveQuestionDraft = useCallback(() => {
    if (!instanceId) {
      setQuestionError("当前还没有选中视频实例。")
      return
    }
    if (queueHasGate) {
      const message = "请先完成复习，再继续录入新的复述点。"
      setQuestionError(message)
      showInfoFeedback("当前处于复习模式", message)
      return
    }
    const normalizedQuestion = questionText.trim()
    if (!normalizedQuestion) {
      setQuestionError("先写下一个复述点问题。")
      return
    }

    const localId = newLocalId()
    const now = Date.now()
    addDraft(projectId, {
      localId,
      instanceId,
      position: `t=${questionAnchorMs}`,
      question: richText(normalizedQuestion),
      answer: richText(""),
      createdAt: now,
      updatedAt: now,
    })
    spawnedDraftKeysRef.current.add(localId)
    spawnBarrageItem({
      localId,
      anchorMs: questionAnchorMs,
      questionText: normalizedQuestion,
      questionLabel: truncateLabel(normalizedQuestion),
      hasAnswer: false,
    })
    closeQuestionComposer()
  }, [
    addDraft,
    closeQuestionComposer,
    instanceId,
    projectId,
    questionAnchorMs,
    questionText,
    queueHasGate,
    spawnBarrageItem,
  ])

  const saveAnswer = useCallback(() => {
    if (!answerDraftId) return
    if (!answerText.trim()) {
      setAnswerError("请先填写答案。")
      return
    }
    updateDraftText(projectId, answerDraftId, "answer", answerText)
    setActiveBarrageItems((items) =>
      items.map((item) => (item.localId === answerDraftId ? { ...item, hasAnswer: true } : item)),
    )
    closeAnswerEditor()
  }, [answerDraftId, answerText, closeAnswerEditor, projectId, updateDraftText])

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
    setIsQuestionComposerOpen(false)
    setQuestionAnchorMs(0)
    setQuestionText("")
    setQuestionError(null)
    setAnswerDraftId(null)
    setAnswerText("")
    setAnswerError(null)
    setActiveBarrageItems([])
    pendingSeekRef.current = null
    lastAppliedNonceRef.current = null
    lastPlaybackMsRef.current = 0
    restoreSavedPositionRef.current = true
    lastPersistedPlaybackSecondRef.current = null
    spawnedDraftKeysRef.current = new Set()
    barrageLaneCursorRef.current = 0
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
    if (!isQuestionComposerOpen) return
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
  }, [isQuestionComposerOpen])

  useEffect(() => {
    if (!answerDraftId) return
    const focusField = () => {
      const field = answerTextareaRef.current
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
  }, [answerDraftId])

  useEffect(() => {
    clearChromeHideTimer()
    if (!isPlaying || isQuestionComposerOpen || answerDraftId !== null) {
      setIsChromeAwake(true)
      return
    }
    if (!isChromeAwake) return
    chromeHideTimerRef.current = window.setTimeout(() => setIsChromeAwake(false), CHROME_HIDE_DELAY_MS)
    return clearChromeHideTimer
  }, [answerDraftId, clearChromeHideTimer, isChromeAwake, isPlaying, isQuestionComposerOpen])

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

  useEffect(() => {
    setActiveBarrageItems((items) =>
      items.flatMap((item) => {
        const draft = draftById[item.localId]
        if (!draft) return []
        const questionTextValue = draftQuestionText(draft)
        if (!questionTextValue) return []
        return [
          {
            ...item,
            questionText: questionTextValue,
            questionLabel: truncateLabel(questionTextValue),
            hasAnswer: richContentHasMeaning(draft.answer),
          },
        ]
      }),
    )
  }, [draftById])

  useEffect(() => {
    if (answerDraftId && !draftById[answerDraftId]) {
      closeAnswerEditor()
    }
  }, [answerDraftId, closeAnswerEditor, draftById])

  useEffect(() => {
    const currentMs = displayPlaybackMs
    const previousMs = lastPlaybackMsRef.current

    if (currentMs < previousMs - 1200) {
      spawnedDraftKeysRef.current = new Set(
        barrageDrafts.filter((draft) => draft.anchorMs < Math.max(0, currentMs - 250)).map((draft) => draft.localId),
      )
    }

    if (currentMs >= previousMs) {
      const thresholdStart = Math.max(0, previousMs - 120)
      for (const draft of barrageDrafts) {
        if (draft.anchorMs <= thresholdStart || draft.anchorMs > currentMs) continue
        if (spawnedDraftKeysRef.current.has(draft.localId)) continue
        spawnedDraftKeysRef.current.add(draft.localId)
        spawnBarrageItem(draft)
      }
    }

    lastPlaybackMsRef.current = currentMs
  }, [barrageDrafts, displayPlaybackMs, spawnBarrageItem])

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
        if (answerDraftId) {
          event.preventDefault()
          closeAnswerEditor()
          return
        }
        if (isQuestionComposerOpen) {
          event.preventDefault()
          closeQuestionComposer()
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
        void openQuestionComposer(undefined, true)
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
    answerDraftId,
    closeAnswerEditor,
    closeQuestionComposer,
    instanceId,
    isQuestionComposerOpen,
    openQuestionComposer,
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
              controlsList="nofullscreen nodownload noremoteplayback"
              onClick={() => {
                if (isQuestionComposerOpen || answerDraftId) return
                togglePlayback()
              }}
              onDoubleClick={() => {
                if (isQuestionComposerOpen || answerDraftId) return
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

            <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-[calc(100%-5rem)] overflow-hidden">
              {activeBarrageItems.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={cn(
                    "plm-barrage-item pointer-events-auto absolute inline-flex max-w-[min(72vw,26rem)] items-center gap-2 rounded-full border px-3 py-1.5 text-sm shadow-[0_10px_30px_-22px_rgba(15,23,42,0.95)] backdrop-blur-md transition-colors hover:border-white/28 hover:bg-white/22",
                    item.hasAnswer
                      ? "border-white/16 bg-white/14 text-white"
                      : "border-[#fda4af]/25 bg-[#fb7185]/18 text-[#fff1f4]",
                  )}
                  style={{
                    top: `${BARRAGE_TOP_OFFSET_PX + item.lane * BARRAGE_LANE_HEIGHT_PX}px`,
                    animationDuration: `${BARRAGE_ANIMATION_DURATION_MS}ms`,
                  }}
                  title={item.questionText}
                  onClick={() => openAnswerEditor(item.localId)}
                  onAnimationEnd={() =>
                    setActiveBarrageItems((items) => items.filter((activeItem) => activeItem.id !== item.id))
                  }
                >
                  <span className="max-w-[18rem] truncate text-left">{item.questionLabel}</span>
                  <span
                    className={cn(
                      "rounded-full px-1.5 py-0.5 text-[10px]",
                      item.hasAnswer ? "bg-white/14 text-white/70" : "bg-white/16 text-white/86",
                    )}
                  >
                    {item.hasAnswer ? "已答" : "待答"}
                  </span>
                </button>
              ))}
            </div>

            {!isPlaying && !isQuestionComposerOpen && !answerDraftId ? (
              <div className="pointer-events-none absolute inset-0 z-[9] flex items-center justify-center">
                <Button
                  type="button"
                  size="icon"
                  className="pointer-events-auto h-14 w-14 rounded-full bg-white/16 text-white shadow-[0_24px_60px_-32px_rgba(15,23,42,0.92)] backdrop-blur-md hover:bg-white/24"
                  onClick={togglePlayback}
                  title="播放"
                >
                  <Play className="h-5 w-5 fill-current" />
                  <span className="sr-only">播放</span>
                </Button>
              </div>
            ) : null}

            <div
              className={cn(
                "pointer-events-none absolute inset-x-0 bottom-0 z-20 px-3 pb-3 transition-opacity duration-200",
                chromeVisible ? "opacity-100" : "opacity-0",
              )}
            >
              <div className="pointer-events-auto rounded-[1.15rem] border border-white/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.16),rgba(2,6,23,0.74))] px-4 pb-3 pt-2 text-white shadow-[0_20px_40px_-28px_rgba(15,23,42,0.96)] backdrop-blur-md">
                <div className="relative">
                  <div className="pointer-events-none absolute inset-x-1 top-1/2 z-20 h-4 -translate-y-1/2">
                    {barrageDrafts.map((draft) => {
                      const ratio = Math.min(Math.max(draft.anchorMs / progressMax, 0), 1)
                      return (
                        <button
                          key={draft.localId}
                          type="button"
                          className={cn(
                            "pointer-events-auto absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/75 shadow-sm",
                            draft.hasAnswer ? "bg-white/80" : "bg-[#fb7185]",
                          )}
                          style={{ left: `${ratio * 100}%` }}
                          onClick={() => openAnswerEditor(draft.localId, true)}
                          title={`${draft.questionText} @ ${formatPlaybackClock(draft.anchorMs)}`}
                        />
                      )
                    })}
                  </div>
                  <input
                    type="range"
                    min={0}
                    max={progressMax}
                    step={250}
                    value={Math.min(displayPlaybackMs, progressMax)}
                    onChange={(event) => applySeekMs(Number(event.target.value))}
                    disabled={durationMs <= 0}
                    className="plm-video-range relative z-10 w-full"
                    aria-label="播放进度"
                  />
                </div>

                <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className="h-9 w-9 rounded-full text-white hover:bg-white/10"
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
                    className="h-9 w-9 rounded-full text-white/82 hover:bg-white/10 hover:text-white"
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
                    className="h-9 w-9 rounded-full text-white/82 hover:bg-white/10 hover:text-white"
                    onClick={() => seekByDelta(FULLSCREEN_KEYBOARD_SEEK_STEP_MS)}
                    title="前进 5 秒"
                  >
                    <RotateCw className="h-4 w-4" />
                    <span className="sr-only">前进 5 秒</span>
                  </Button>
                  <div className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-white/76">
                    {formatPlaybackClock(displayPlaybackMs)} / {durationLabel}
                  </div>

                  <div className="mx-auto hidden h-5 w-px bg-white/10 lg:block" />

                  <Button
                    type="button"
                    size="icon"
                    variant="ghost"
                    className="h-9 w-9 rounded-full text-white/82 hover:bg-white/10 hover:text-white"
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
                    className="plm-video-range plm-video-range-volume w-20 md:w-24"
                    aria-label="音量"
                  />
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="rounded-full px-3 text-white/82 hover:bg-white/10 hover:text-white"
                    onClick={cyclePlaybackRate}
                    title="切换倍速"
                  >
                    {playbackRateLabel}
                  </Button>

                  <div className="ml-auto flex items-center gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      className="rounded-full border-white/12 bg-white/8 text-white hover:bg-white/16"
                      onClick={() => void openQuestionComposer()}
                      disabled={!instanceId || queueHasGate}
                    >
                      <NotebookPen className="h-4 w-4" />
                      记题
                    </Button>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="h-9 w-9 rounded-full text-white hover:bg-white/10"
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

            {isQuestionComposerOpen ? (
              <div className="pointer-events-none absolute inset-x-0 bottom-20 z-30 flex justify-center px-3">
                <div className="pointer-events-auto w-full max-w-3xl rounded-full border border-white/12 bg-[linear-gradient(180deg,rgba(15,23,42,0.74),rgba(2,6,23,0.84))] px-2 py-2 text-white shadow-[0_24px_48px_-30px_rgba(15,23,42,0.96)] backdrop-blur-xl">
                  <div className="flex flex-wrap items-center gap-2">
                    <div className="shrink-0 rounded-full border border-cyan-200/18 bg-cyan-200/10 px-3 py-1 text-xs text-cyan-100">
                      {formatPlaybackClock(questionAnchorMs)}
                    </div>
                    <input
                      ref={questionInputRef}
                      type="text"
                      value={questionText}
                      className="min-w-[12rem] flex-1 bg-transparent px-2 text-sm outline-none placeholder:text-white/35"
                      placeholder="写下复述点问题，回车发成弹幕"
                      onChange={(event) => {
                        setQuestionText(event.target.value)
                        if (questionError) setQuestionError(null)
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Escape") {
                          event.preventDefault()
                          closeQuestionComposer()
                          return
                        }
                        if (event.nativeEvent.isComposing) return
                        if (event.key === "Enter") {
                          event.preventDefault()
                          saveQuestionDraft()
                        }
                      }}
                    />
                    <Button type="button" size="sm" className="rounded-full" onClick={saveQuestionDraft}>
                      发送
                    </Button>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="h-9 w-9 rounded-full text-white/74 hover:bg-white/10 hover:text-white"
                      onClick={closeQuestionComposer}
                    >
                      <X className="h-4 w-4" />
                      <span className="sr-only">关闭记题输入</span>
                    </Button>
                  </div>
                  {questionError ? <div className="px-3 pt-2 text-xs text-rose-200">{questionError}</div> : null}
                </div>
              </div>
            ) : null}

            {answerDraft ? (
              <div className="pointer-events-none absolute inset-0 z-30">
                <div className="pointer-events-auto absolute bottom-24 right-4 w-[min(22rem,calc(100%-2rem))] rounded-[1.15rem] border border-white/12 bg-[linear-gradient(180deg,rgba(15,23,42,0.88),rgba(2,6,23,0.9))] p-4 text-white shadow-[0_28px_64px_-34px_rgba(15,23,42,0.96)] backdrop-blur-xl">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-[11px] uppercase tracking-[0.18em] text-white/42">补答案</div>
                      <div className="mt-2 text-sm font-medium leading-6 text-white">
                        {draftQuestionText(answerDraft) || "未命名问题"}
                      </div>
                      <div className="mt-2 inline-flex items-center rounded-full border border-cyan-200/18 bg-cyan-200/10 px-2.5 py-1 text-[11px] text-cyan-100">
                        锚点 {formatPlaybackClock(answerDraftAnchorMs)}
                      </div>
                    </div>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="h-8 w-8 rounded-full text-white/72 hover:bg-white/10 hover:text-white"
                      onClick={closeAnswerEditor}
                    >
                      <X className="h-4 w-4" />
                      <span className="sr-only">关闭答案输入</span>
                    </Button>
                  </div>

                  <textarea
                    ref={answerTextareaRef}
                    value={answerText}
                    className="mt-3 min-h-[132px] w-full rounded-2xl border border-white/10 bg-white/[0.05] px-3 py-2 text-sm text-white outline-none placeholder:text-white/28 focus:border-cyan-200/24 focus:bg-white/[0.08]"
                    placeholder="补上答案、解释或提示词"
                    onChange={(event) => {
                      setAnswerText(event.target.value)
                      if (answerError) setAnswerError(null)
                    }}
                    onKeyDown={(event) => {
                      if (event.key === "Escape") {
                        event.preventDefault()
                        closeAnswerEditor()
                        return
                      }
                      if (event.nativeEvent.isComposing) return
                      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                        event.preventDefault()
                        saveAnswer()
                      }
                    }}
                  />

                  <div className={cn("mt-2 text-xs", answerError ? "text-rose-200" : "text-white/44")}>
                    {answerError ?? "Ctrl+Enter 保存 · Esc 关闭"}
                  </div>

                  <div className="mt-3 flex items-center justify-end gap-2">
                    <Button
                      type="button"
                      variant="ghost"
                      className="text-white/72 hover:bg-white/10 hover:text-white"
                      onClick={closeAnswerEditor}
                    >
                      稍后
                    </Button>
                    <Button type="button" onClick={saveAnswer}>
                      保存答案
                    </Button>
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

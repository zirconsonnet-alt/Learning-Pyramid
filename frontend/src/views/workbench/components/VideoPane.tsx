import { forwardRef, useCallback, useDeferredValue, useEffect, useImperativeHandle, useMemo, useRef, useState, type CSSProperties } from "react"
import { useQueries, useQuery } from "@tanstack/react-query"
import Hls from "hls.js"
import {
  Captions,
  Copy,
  LoaderCircle,
  Maximize2,
  MessageSquarePlus,
  Minimize2,
  NotebookPen,
  Pause,
  Play,
  RotateCcw,
  RotateCw,
  Sparkles,
  VideoOff,
  Volume2,
  VolumeX,
  X,
} from "lucide-react"

import type { Instance } from "@/ui/api/instances"
import { ApiError } from "@/ui/api/http"
import { uploadMediaAsset } from "@/ui/api/mediaAssets"
import { resolvePlaybackDescriptorUrl } from "@/ui/api/media"
import { apiUrl } from "@/ui/api/http"
import { projectApiPath, type ScopedProjectRef } from "@/ui/api/projectScope"
import { getRecallPoint, searchRecallPoints, type RecallPoint } from "@/ui/api/review"
import {
  appendImageBlock,
  removeImageBlockAt,
  richContentHasMeaning,
  richContentToPlainText,
  richText,
  setRichContentText,
  type RichContent,
} from "@/ui/api/richContent"
import { MarkdownRichText } from "@/ui/components/MarkdownRichText"
import { RichContentEditor } from "@/ui/components/RichContentEditor"
import { Button } from "@/ui/components/ui/button"
import { Card, CardContent } from "@/ui/components/ui/card"
import { askCourseAgent, type CourseAgentRecallContext } from "@/ui/llm/courseAgent"
import { resolveProjectFile, useProjectDirectoryBinding } from "@/ui/localMedia/projectDirectory"
import {
  captureDisplayedVideoFrame,
  captureDisplayedVideoFrameFile,
  type CapturedVideoFrame,
} from "@/ui/media/videoFrameCapture"
import { playPomodoroMicroBreakReminderSound } from "@/ui/pomodoroAudio"
import { useMembershipSummary } from "@/ui/queries/membership"
import { useProjectMaterialSourceBinding } from "@/ui/queries/projects"
import { useSystemCapabilities } from "@/ui/queries/system"
import type { AiChatCourseEvidence } from "@/ui/store/aiChatStore"
import { formatPomodoroCountdown, getPomodoroSnapshot, getPomodoroUpcomingSegmentPreview, isQuickPomodoroSessionActive, usePomodoroNow, usePomodoroStore } from "@/ui/store/pomodoroStore"
import { useRecallPointsByInstance } from "@/ui/queries/workbench"
import { useInstancePlaybackDescriptor } from "@/ui/queries/workbench"
import { showInfoFeedback } from "@/ui/store/feedbackStore"
import { formatRecallPointReference } from "@/ui/displayIdentifiers"
import { SUPPORTED_SUBTITLE_EXTENSIONS_LABEL } from "@/ui/subtitles/subtitleSupport"
import { recordStudyActivity, touchDailyStudyActivity } from "@/ui/store/workbenchDailyStats"
import { clearPlaybackResumeMs, loadPlaybackResumeMs, savePlaybackResumeMs } from "@/ui/store/playbackResume"
import {
  loadVideoPlaybackRate,
  normalizeVideoPlaybackRate,
  saveVideoPlaybackRate,
  VIDEO_PLAYBACK_RATE_OPTIONS,
} from "@/ui/store/videoPlaybackRate"
import { saveVideoDurationMs } from "@/ui/store/videoDurations"
import { markVideoWatchProgressCompleted, syncVideoWatchProgressRange } from "@/ui/store/videoWatchProgress"
import { useWorkbenchStore } from "@/ui/store/workbenchStore"
import { cn } from "@/ui/utils"
import { MemberOnlyFeatureNotice } from "@/views/membership/membershipUi"
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
import type { VideoPaneHandle } from "../workbenchAiContext"

const FULLSCREEN_KEYBOARD_SEEK_STEP_MS = 5000
const CHROME_HIDE_DELAY_MS = 1600
const PLAYBACK_RATE_OPTIONS = VIDEO_PLAYBACK_RATE_OPTIONS
const WATCH_TRACKING_MAX_CHUNK_MS = 5000
const COMPOSE_ACTIVITY_WINDOW_MS = 60_000
const QA_ACTIVITY_WINDOW_MS = 30_000
const MAX_CAPTURE_REFERENCE_PICKER_ITEMS = 12
const POMODORO_MICRO_BREAK_FORBIDDEN_WINDOW_MS = 3 * 60_000
const POMODORO_TRANSITION_PREVIEW_WINDOW_MS = 10_000

type FullscreenCapableVideo = HTMLVideoElement & {
  webkitDisplayingFullscreen?: boolean
}

type CapturePanelMode = "capture" | "assistant"
type CaptureReferencePickerField = "question" | "answer"
type MicroBreakCancelReason =
  | "fullscreen_exit"
  | "pomodoro_ineligible"
  | "route_change"
  | "settings_disabled"
  | "video_unavailable"

type PomodoroMicroBreakTimerState = {
  status: "idle" | "scheduled" | "resting"
  fullscreenEnteredAtMs: number | null
  targetAtMs: number | null
  forbiddenAfterMs: number | null
  segmentKey: string
  wasPlayingBeforeBreak: boolean
  countdownEndsAtMs: number | null
  cancelReason: MicroBreakCancelReason | null
}

type CourseAssistantTurn = {
  id: string
  role: "user" | "assistant"
  content: string
  createdAt: number
  evidence?: AiChatCourseEvidence[]
}

function createIdleMicroBreakState(cancelReason: MicroBreakCancelReason | null = null): PomodoroMicroBreakTimerState {
  return {
    status: "idle",
    fullscreenEnteredAtMs: null,
    targetAtMs: null,
    forbiddenAfterMs: null,
    segmentKey: "",
    wasPlayingBeforeBreak: false,
    countdownEndsAtMs: null,
    cancelReason,
  }
}

function createRandomMicroBreakDelayMs(settings: { minIntervalSeconds: number; maxIntervalSeconds: number }) {
  const minDelayMs = Math.max(0, Math.floor(settings.minIntervalSeconds * 1000))
  const maxDelayMs = Math.max(minDelayMs, Math.floor(settings.maxIntervalSeconds * 1000))
  if (maxDelayMs === minDelayMs) return minDelayMs
  return minDelayMs + Math.floor(Math.random() * (maxDelayMs - minDelayMs + 1))
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

function formatSubtitleLines(text: string | null | undefined) {
  const normalized = String(text ?? "")
    .replace(/\r\n?/g, "\n")
    .split(/\n+/)
    .map((line) => line.replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .join(" ")
    .trim()
  if (!normalized) return []
  return [normalized]
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

function formatCourseAssistantError(error: unknown) {
  if (error instanceof ApiError) return `${error.code}: ${error.message}`
  if (error instanceof Error) return error.message
  return "视频助手暂时不可用"
}

function formatPlaybackError(error: unknown) {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return "当前视频暂时不可用。"
}

function formatEvidenceTimeRange(startMs: number, endMs: number) {
  return startMs === endMs ? formatPlaybackClock(startMs) : `${formatPlaybackClock(startMs)}-${formatPlaybackClock(endMs)}`
}

async function copyText(text: string) {
  if (!text.trim()) return
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text)
    return
  }
  throw new Error("当前环境不支持剪贴板")
}

export const VideoPane = forwardRef<VideoPaneHandle, {
  subjectId: string
  projectId: string
  instance: Instance | null
  setCurrentMs: (v: number) => void
  seekTo?: { instanceId: string; ms: number; nonce: number } | null
  onSeekApplied?: (nonce: number) => void
  onDurationResolved?: (instanceId: string, durationMs: number) => void
  queueHasGate: boolean
  allowCaptureDrafts?: boolean
  surface?: "detail" | "workbench"
  onAiContextChange?: (context: CourseAgentRecallContext | null) => void
}>(
function VideoPane({
  surface = "workbench",
  subjectId,
  projectId,
  instance,
  setCurrentMs,
  seekTo,
  onSeekApplied,
  onDurationResolved,
  queueHasGate,
  allowCaptureDrafts = true,
  onAiContextChange,
}, ref) {
  const projectScope = useMemo<ScopedProjectRef>(() => ({ subjectId, scopedProjectId: projectId }), [projectId, subjectId])
  const playerShellRef = useRef<HTMLDivElement | null>(null)
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const barrageLayerRef = useRef<HTMLDivElement | null>(null)
  const questionInputRef = useRef<HTMLTextAreaElement | null>(null)
  const answerTextareaRef = useRef<HTMLTextAreaElement | null>(null)
  const assistantInputRef = useRef<HTMLTextAreaElement | null>(null)
  const pendingSeekRef = useRef<{ instanceId: string; ms: number; nonce: number } | null>(null)
  const fullscreenTransitionRef = useRef(false)
  const chromeHideTimerRef = useRef<number | null>(null)
  const lastNonZeroVolumeRef = useRef(1)
  const lastAppliedNonceRef = useRef<number | null>(null)
  const restoreSavedPositionRef = useRef(true)
  const lastPersistedPlaybackSecondRef = useRef<number | null>(null)
  const lastPlaybackTrackedAtRef = useRef<number | null>(null)
  const lastPlaybackTrackedPositionRef = useRef<number | null>(null)
  const lastPlaybackTrackedPositionClockRef = useRef<number | null>(null)
  const assistantAbortRef = useRef<AbortController | null>(null)
  const hlsRef = useRef<Hls | null>(null)
  const lastFrameCaptureShortcutAtRef = useRef(0)
  const microBreakTimeoutRef = useRef<number | null>(null)
  const microBreakIntervalRef = useRef<number | null>(null)
  const microBreakStateRef = useRef<PomodoroMicroBreakTimerState>(createIdleMicroBreakState())

  const [playbackMs, setPlaybackMs] = useState(0)
  const [durationMs, setDurationMs] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [volumePercent, setVolumePercent] = useState(100)
  const [playbackRate, setPlaybackRate] = useState(() => loadVideoPlaybackRate())
  const [localSrc, setLocalSrc] = useState<string | null>(null)
  const [localError, setLocalError] = useState<string | null>(null)
  const [mediaElementError, setMediaElementError] = useState<string | null>(null)
  const [isShellFullscreen, setIsShellFullscreen] = useState(false)
  const [isChromeAwake, setIsChromeAwake] = useState(true)
  const [isCapturePanelOpen, setIsCapturePanelOpen] = useState(false)
  const [capturePanelMode, setCapturePanelMode] = useState<CapturePanelMode>("capture")
  const [captureAnchorMs, setCaptureAnchorMs] = useState(0)
  const [questionContent, setQuestionContent] = useState<RichContent>(() => richText(""))
  const [answerContent, setAnswerContent] = useState<RichContent>(() => richText(""))
  const [captureReferenceIds, setCaptureReferenceIds] = useState<string[]>([])
  const [captureReferencePicker, setCaptureReferencePicker] = useState<{
    field: CaptureReferencePickerField
    query: string
    highlightedIndex: number
  } | null>(null)
  const [captureError, setCaptureError] = useState<string | null>(null)
  const [isFrameCaptureUploading, setIsFrameCaptureUploading] = useState(false)
  const [assistantComposer, setAssistantComposer] = useState("")
  const [assistantTurns, setAssistantTurns] = useState<CourseAssistantTurn[]>([])
  const [assistantStatus, setAssistantStatus] = useState<string | null>(null)
  const [assistantError, setAssistantError] = useState<string | null>(null)
  const [assistantFrame, setAssistantFrame] = useState<CapturedVideoFrame | null>(null)
  const [isAssistantAsking, setIsAssistantAsking] = useState(false)
  const [isBarrageEnabled, setIsBarrageEnabled] = useState(() => loadVideoBarrageEnabled())
  const [isSubtitleEnabled, setIsSubtitleEnabled] = useState(() => loadVideoSubtitleEnabled())
  const [subtitleDelayMs, setSubtitleDelayMs] = useState(() => loadVideoSubtitleDelayMs())
  const [microBreakState, setMicroBreakState] = useState<PomodoroMicroBreakTimerState>(() => createIdleMicroBreakState())
  const [microBreakNow, setMicroBreakNow] = useState(() => Date.now())

  const addDraft = useWorkbenchStore((s) => s.addDraft)
  const pomodoroEnabled = usePomodoroStore((state) => state.enabled)
  const pomodoroWeeklySchedule = usePomodoroStore((state) => state.weeklySchedule)
  const pomodoroQuickPomodoro = usePomodoroStore((state) => state.quickPomodoro)
  const pomodoroMicroBreaks = usePomodoroStore((state) => state.microBreaks)
  const pomodoroQuickClockActive = isQuickPomodoroSessionActive(pomodoroQuickPomodoro)
  const pomodoroNow = usePomodoroNow(pomodoroEnabled || pomodoroQuickClockActive)

  const instanceId = instance?.instanceId ?? null
  const capabilitiesQ = useSystemCapabilities()
  const authEnabled = capabilitiesQ.data?.authEnabled ?? false
  const membershipQ = useMembershipSummary(authEnabled)
  const materialSourceBindingQ = useProjectMaterialSourceBinding(projectScope)
  const playbackDescriptorQ = useInstancePlaybackDescriptor(projectScope, instanceId ?? "", !!instanceId)
  const directoryBinding = useProjectDirectoryBinding(projectId)
  const serverMediaStreamEnabled = capabilitiesQ.data?.serverMediaStreamEnabled ?? false
  const browserLocalMediaEnabled = capabilitiesQ.data?.browserLocalMediaEnabled ?? false
  const effectiveSourceKind = instance?.mediaSourceKind ?? materialSourceBindingQ.data?.sourceKind ?? null
  const playbackKind =
    playbackDescriptorQ.data?.playbackKind ??
    instance?.playbackKind ??
    (effectiveSourceKind === "BAIDU_NETDISK" ? "HLS" : "FILE")
  const playbackDescriptorUrl = playbackDescriptorQ.data?.url ? resolvePlaybackDescriptorUrl(playbackDescriptorQ.data.url) : null
  const displayPlaybackMs = durationMs > 0 ? Math.min(playbackMs, durationMs) : playbackMs
  const progressMax = Math.max(durationMs, 1)
  const playbackProgressPercent = progressMax > 0 ? Math.min(100, Math.max(0, (displayPlaybackMs / progressMax) * 100)) : 0
  const durationLabel = durationMs > 0 ? formatPlaybackClock(durationMs) : "--:--"
  const chromeVisible = isChromeAwake || !isPlaying || isCapturePanelOpen
  const playbackRateLabel = `${Number.isInteger(playbackRate) ? playbackRate.toFixed(0) : playbackRate.toFixed(2).replace(/0$/, "")}x`
  const recallPointIdsQ = useRecallPointsByInstance(projectScope, instanceId ?? "")
  const recallPointQs = useQueries({
    queries: (recallPointIdsQ.data?.recallPointIds ?? []).map((recallPointId) => ({
      queryKey: ["recallPoint", subjectId, projectId, recallPointId],
      queryFn: () => getRecallPoint(projectScope, recallPointId),
      enabled: !!projectId && !!instanceId && !!recallPointId,
      staleTime: 30_000,
    })),
  })
  const recallPoints = useMemo<RecallPoint[]>(
    () => recallPointQs.flatMap((query) => (query.data ? [query.data] : [])),
    [recallPointQs],
  )
  const captureDraftAiContext = useMemo<CourseAgentRecallContext | null>(() => {
    if (!richContentHasMeaning(questionContent) && !richContentHasMeaning(answerContent) && captureReferenceIds.length === 0) return null
    return {
      mode: "capture",
      questionText: richContentToPlainText(questionContent),
      answerText: richContentToPlainText(answerContent),
      referenceIds: captureReferenceIds,
    }
  }, [answerContent, captureReferenceIds, questionContent])
  const subtitleSourceKind = effectiveSourceKind
  const canProbeSubtitles =
    !!instanceId &&
    !!subtitleSourceKind &&
    (subtitleSourceKind !== "BROWSER_LOCAL" || directoryBinding.permission === "granted")
  const subtitleState = useVideoSubtitles({
    subjectId,
    projectId,
    instance,
    playbackMs: displayPlaybackMs,
    subtitlesEnabled: isSubtitleEnabled,
    detectionEnabled: canProbeSubtitles,
    sourceKind: subtitleSourceKind,
    subtitleDelayMs,
  })
  const subtitleMissingText = subtitleState.missingText
  const subtitleErrorText = subtitleState.errorText
  const subtitleHasFile = subtitleState.hasSubtitleFile
  const retrySubtitleLookup = subtitleState.retry
  const subtitleMissing = canProbeSubtitles && !subtitleState.isLoading && !subtitleHasFile && !!subtitleMissingText
  const subtitleButtonDisabled = !instanceId || subtitleMissing
  const subtitleButtonLabel = subtitleState.isLoading ? "字幕载入" : subtitleMissing ? "无字幕" : isSubtitleEnabled ? "字幕开" : "字幕关"
  const subtitleDisplayLines = useMemo(() => formatSubtitleLines(subtitleState.text), [subtitleState.text])
  const llmConfigured = capabilitiesQ.data?.llmConfigured ?? false
  const playerAiMemberBlocked = authEnabled && (membershipQ.isLoading || Boolean(membershipQ.error) || !membershipQ.data?.isActive)
  const canAskCourseAssistant =
    !!instanceId &&
    !!subtitleSourceKind &&
    llmConfigured &&
    !playerAiMemberBlocked &&
    (subtitleSourceKind !== "BROWSER_LOCAL" || directoryBinding.permission === "granted")

  useEffect(() => {
    onAiContextChange?.(captureDraftAiContext)
  }, [captureDraftAiContext, onAiContextChange])

  useImperativeHandle(
    ref,
    () => ({
      async captureCurrentFrameForAi() {
        const video = videoRef.current
        if (!video || video.readyState < 2) return null
        const captured = await captureDisplayedVideoFrame(video, clampPlaybackMs(video, Math.floor(video.currentTime * 1000)))
        return {
          timeMs: captured.timeMs,
          imageDataUrl: captured.imageDataUrl,
          mimeType: "image/jpeg",
        }
      },
    }),
    [],
  )
  const deferredCaptureReferenceQuery = useDeferredValue(captureReferencePicker?.query.trim() ?? "")
  const captureReferenceSearchQ = useQuery({
    queryKey: ["recallPointSearch", subjectId, projectId, deferredCaptureReferenceQuery],
    queryFn: ({ signal }) =>
      searchRecallPoints(
        projectScope,
        { q: deferredCaptureReferenceQuery || undefined, limit: MAX_CAPTURE_REFERENCE_PICKER_ITEMS * 4 },
        { signal },
      ),
    enabled: allowCaptureDrafts && !!projectId && isCapturePanelOpen && capturePanelMode === "capture" && !!captureReferencePicker,
    placeholderData: (previous) => previous,
    staleTime: 30_000,
  })
  const captureReferenceCandidates = useMemo(
    () =>
      (captureReferenceSearchQ.data ?? [])
        .map((item: RecallPoint) => {
          const questionPreview = richContentToPlainText(item.question).trim() || "题面为空"
          const answerPreview = richContentToPlainText(item.answer).trim() || "答案为空"
          return {
            recallPointId: item.recallPointId,
            questionPreview,
            answerPreview,
          }
        })
        .filter((candidate) => !captureReferenceIds.includes(candidate.recallPointId))
        .slice(0, MAX_CAPTURE_REFERENCE_PICKER_ITEMS),
    [captureReferenceIds, captureReferenceSearchQ.data],
  )

  useEffect(() => {
    setCaptureReferencePicker((current) => {
      if (!current) return current
      const maxIndex = Math.max(captureReferenceCandidates.length - 1, 0)
      if (current.highlightedIndex <= maxIndex) return current
      return { ...current, highlightedIndex: maxIndex }
    })
  }, [captureReferenceCandidates.length])

  function focusCaptureField(field: CaptureReferencePickerField) {
    const target = field === "question" ? questionInputRef.current : answerTextareaRef.current
    target?.focus()
  }

  function openCaptureReferencePicker(field: CaptureReferencePickerField) {
    if (capturePanelMode !== "capture") return
    touchComposeActivity()
    setCaptureReferencePicker({ field, query: "", highlightedIndex: 0 })
  }

  function closeCaptureReferencePicker(field?: CaptureReferencePickerField) {
    setCaptureReferencePicker(null)
    if (field) {
      window.setTimeout(() => focusCaptureField(field), 0)
    }
  }

  function addCaptureReference(recallPointId: string) {
    touchComposeActivity()
    setCaptureReferenceIds((current) => (current.includes(recallPointId) ? current : [...current, recallPointId]))
  }

  function confirmCaptureReferencePickerSelection(field: CaptureReferencePickerField) {
    const selected = captureReferenceCandidates[captureReferencePicker?.highlightedIndex ?? 0]
    if (selected) {
      addCaptureReference(selected.recallPointId)
    }
    closeCaptureReferencePicker(field)
  }

  const touchComposeActivity = useCallback(() => {
    touchDailyStudyActivity(projectId, "recallEntry", COMPOSE_ACTIVITY_WINDOW_MS)
  }, [projectId])

  const touchQaActivity = useCallback(() => {
    touchDailyStudyActivity(projectId, "aiQa", QA_ACTIVITY_WINDOW_MS)
  }, [projectId])

  const resetPlaybackCoverageAnchor = useCallback((playbackMs?: number | null) => {
    const nextPlaybackMs = Number.isFinite(playbackMs) ? Math.max(0, Math.floor(playbackMs ?? 0)) : null
    lastPlaybackTrackedPositionRef.current = nextPlaybackMs
    lastPlaybackTrackedPositionClockRef.current = nextPlaybackMs === null ? null : Date.now()
  }, [])

  const flushPlaybackCoverage = useCallback(
    (playbackMs?: number | null) => {
      if (!instanceId) {
        lastPlaybackTrackedPositionRef.current = null
        lastPlaybackTrackedPositionClockRef.current = null
        return
      }

      const nextPlaybackMs = Number.isFinite(playbackMs) ? Math.max(0, Math.floor(playbackMs ?? 0)) : null
      const previousPlaybackMs = lastPlaybackTrackedPositionRef.current
      const previousClockMs = lastPlaybackTrackedPositionClockRef.current
      const now = Date.now()

      lastPlaybackTrackedPositionRef.current = nextPlaybackMs
      lastPlaybackTrackedPositionClockRef.current = nextPlaybackMs === null ? null : now

      if (nextPlaybackMs === null || previousPlaybackMs === null || previousClockMs === null) return

      const playbackDeltaMs = nextPlaybackMs - previousPlaybackMs
      if (playbackDeltaMs <= 250) return

      const video = videoRef.current
      const playbackRate = Math.max(video?.playbackRate ?? 1, 0.25)
      const wallDeltaMs = Math.max(0, now - previousClockMs)
      const maxExpectedAdvanceMs = Math.max(2_500, wallDeltaMs * playbackRate * 2.25 + 1_500)
      if (playbackDeltaMs > maxExpectedAdvanceMs) return

      syncVideoWatchProgressRange(projectScope, projectId, instanceId, previousPlaybackMs, nextPlaybackMs, durationMs > 0 ? durationMs : null)
    },
    [durationMs, instanceId, projectId, projectScope],
  )

  const flushPlaybackDuration = useCallback(() => {
    if (!instanceId) {
      lastPlaybackTrackedAtRef.current = null
      return
    }
    const now = Date.now()
    const previous = lastPlaybackTrackedAtRef.current
    lastPlaybackTrackedAtRef.current = now
    if (previous === null) return
    const boundedStartAtMs = Math.max(previous, now - WATCH_TRACKING_MAX_CHUNK_MS)
    if (now > boundedStartAtMs) {
      recordStudyActivity(projectId, "video", boundedStartAtMs, now)
    }
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

  const applyRememberedPlaybackRate = useCallback((video?: HTMLVideoElement | null) => {
    const rememberedPlaybackRate = loadVideoPlaybackRate()
    if (video) {
      video.playbackRate = rememberedPlaybackRate
    }
    setPlaybackRate(rememberedPlaybackRate)
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
      const currentPlaybackMs = clampPlaybackMs(video, Math.floor(video.currentTime * 1000))
      if (!video.paused && !video.ended) {
        flushPlaybackDuration()
        flushPlaybackCoverage(currentPlaybackMs)
      } else {
        resetPlaybackCoverageAnchor(currentPlaybackMs)
      }
      const nextMs = clampPlaybackMs(video, ms)
      video.currentTime = nextMs / 1000
      syncPlaybackClock(nextMs)
      if (options?.persist !== false) {
        persistPlaybackPosition(nextMs)
      }
      resetPlaybackCoverageAnchor(nextMs)
      syncVideoUiState(video)
      wakeChrome()
    },
    [flushPlaybackCoverage, flushPlaybackDuration, persistPlaybackPosition, resetPlaybackCoverageAnchor, syncPlaybackClock, syncVideoUiState, wakeChrome],
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
    flushPlaybackCoverage(pauseMs)
    syncVideoUiState(video)
    wakeChrome()
  }, [flushPlaybackCoverage, persistPlaybackPosition, syncPlaybackClock, syncVideoUiState, wakeChrome])

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
      const normalizedRate = normalizeVideoPlaybackRate(nextRate)
      video.playbackRate = normalizedRate
      saveVideoPlaybackRate(normalizedRate)
      setPlaybackRate(normalizedRate)
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

  const toggleSubtitles = useCallback(() => {
    if (!instanceId) return
    if (subtitleMissing) return
    if (!effectiveSourceKind && materialSourceBindingQ.isLoading) {
      showInfoFeedback("正在准备字幕", "素材来源信息还在加载，稍后再试。")
      return
    }
    if (materialSourceBindingQ.error || !subtitleSourceKind) {
      showInfoFeedback("字幕暂不可用", "当前项目的素材来源信息不可用，暂时无法检查同目录字幕文件。")
      return
    }
    if (subtitleSourceKind === "BROWSER_LOCAL" && directoryBinding.permission !== "granted") {
      showInfoFeedback("字幕暂不可用", "浏览器还没有本地目录读取权限，暂时无法检查视频同目录下的字幕文件。")
      return
    }
    if (subtitleErrorText && !subtitleHasFile) {
      retrySubtitleLookup()
    }
    setIsSubtitleEnabled((current) => {
      const next = !current
      if (next) {
        showInfoFeedback("字幕已开启", `系统会检查视频同目录下的同名字幕文件（${SUPPORTED_SUBTITLE_EXTENSIONS_LABEL}）。全屏时可按 [ / ] 微调时序，按 \\ 归零。`)
      }
      return next
    })
  }, [directoryBinding.permission, effectiveSourceKind, instanceId, materialSourceBindingQ.error, materialSourceBindingQ.isLoading, retrySubtitleLookup, subtitleErrorText, subtitleHasFile, subtitleMissing, subtitleSourceKind])

  const closeCapturePanel = useCallback(() => {
    assistantAbortRef.current?.abort()
    assistantAbortRef.current = null
    setIsCapturePanelOpen(false)
    setCapturePanelMode("capture")
    setCaptureError(null)
    setQuestionContent(richText(""))
    setAnswerContent(richText(""))
    setCaptureReferenceIds([])
    setCaptureReferencePicker(null)
    setIsFrameCaptureUploading(false)
    setAssistantStatus(null)
    setAssistantError(null)
    setIsAssistantAsking(false)
  }, [])

  const openCapturePanel = useCallback(
    async (anchorMs?: number, keepFullscreen = false, mode: CapturePanelMode = "capture") => {
      if (mode === "capture" && !allowCaptureDrafts) {
        showInfoFeedback("当前页面仅支持播放", "请回到工作台录入新的复述点。")
        return
      }
      if (mode === "capture" && queueHasGate) {
        showInfoFeedback("当前处于复习模式", "请先完成复习，再继续录入新的复述点。")
        return
      }
      if (mode === "assistant") touchQaActivity()
      else touchComposeActivity()
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
      setCapturePanelMode(mode)
      setQuestionContent(richText(""))
      setAnswerContent(richText(""))
      setCaptureReferenceIds([])
      setCaptureReferencePicker(null)
      setIsFrameCaptureUploading(false)
      setCaptureError(null)
      setAssistantFrame(null)
      setAssistantStatus(null)
      setAssistantError(null)
      setIsCapturePanelOpen(true)
      wakeChrome()
    },
    [
      allowCaptureDrafts,
      instanceId,
      persistPlaybackPosition,
      queueHasGate,
      requestShellFullscreen,
      syncPlaybackClock,
      syncVideoUiState,
      touchComposeActivity,
      touchQaActivity,
      wakeChrome,
    ],
  )

  const copyLatestAssistantAnswer = useCallback(async () => {
    const latestAssistantTurn = [...assistantTurns].reverse().find((turn) => turn.role === "assistant")
    if (!latestAssistantTurn?.content.trim()) return
    try {
      touchQaActivity()
      await copyText(latestAssistantTurn.content)
      showInfoFeedback("回答已复制", "视频助手的最新回答已经复制到剪贴板。")
    } catch (error) {
      setAssistantError(formatCourseAssistantError(error))
    }
  }, [assistantTurns, touchQaActivity])

  const submitAssistantQuestion = useCallback(async () => {
    const prompt = assistantComposer.trim()
    const video = videoRef.current

    if (!prompt) {
      setAssistantError("先输入一个问题，再让视频助手帮你看这一段。")
      return
    }
    if (!instance || !instanceId || !subtitleSourceKind || !video) {
      setAssistantError("当前视频上下文还没有准备好。")
      return
    }
    if (!llmConfigured) {
      setAssistantError("当前还没有配置可用的 LLM 服务。")
      return
    }
    if (playerAiMemberBlocked) {
      setAssistantError("视频助手是会员专属功能，请先前往会员中心开通会员。")
      return
    }
    if (subtitleSourceKind === "BROWSER_LOCAL" && directoryBinding.permission !== "granted") {
      setAssistantError("浏览器还没有本地目录读取权限，视频助手暂时无法读取视频与字幕。")
      return
    }
    if (isAssistantAsking) return

    touchQaActivity()
    const historyMessages = assistantTurns.map((turn) => ({
      role: turn.role,
      content: turn.content,
    }))
    const userTurn: CourseAssistantTurn = {
      id: newLocalId(),
      role: "user",
      content: prompt,
      createdAt: Date.now(),
    }
    const assistantTurnId = newLocalId()

    setAssistantTurns((current) => [...current, userTurn])
    setAssistantComposer("")
    setAssistantError(null)
    setAssistantStatus("正在捕获当前画面...")
    setIsAssistantAsking(true)

    const controller = new AbortController()
    assistantAbortRef.current = controller

    try {
      const frame = await captureDisplayedVideoFrame(video, captureAnchorMs)
      if (controller.signal.aborted) return

      setAssistantFrame(frame)
      setAssistantStatus("正在检索相关字幕...")

      const result = await askCourseAgent({
        subjectId,
        projectId,
        instance,
        sourceKind: subtitleSourceKind,
        nodeLabel: instance.materialDisplayName || instance.materialId || "当前视频",
        userPrompt: prompt,
        systemPrompt: "你叫雪豹，是全屏视频助手。",
        anchorMs: captureAnchorMs,
        initialFrame: frame,
        recallContext: captureDraftAiContext,
        historyMessages,
        temperature: 0.2,
        signal: controller.signal,
        timeoutMs: 90_000,
        onStatus: (status) => setAssistantStatus(status),
        onDelta: (_chunk, accumulated) => {
          setAssistantTurns((current) => {
            if (current.some((turn) => turn.id === assistantTurnId)) {
              return current.map((turn) => (turn.id === assistantTurnId ? { ...turn, content: accumulated } : turn))
            }
            return [
              ...current,
              {
                id: assistantTurnId,
                role: "assistant",
                content: accumulated,
                createdAt: Date.now(),
              },
            ]
          })
        },
      })
      if (controller.signal.aborted) return

      setAssistantTurns((current) => {
        if (current.some((turn) => turn.id === assistantTurnId)) {
          return current.map((turn) =>
            turn.id === assistantTurnId ? { ...turn, content: result.content, evidence: result.evidence } : turn,
          )
        }
        return [
          ...current,
          {
            id: assistantTurnId,
            role: "assistant",
            content: result.content,
            createdAt: Date.now(),
            evidence: result.evidence,
          },
        ]
      })
      setAssistantStatus(null)
    } catch (error) {
      if (controller.signal.aborted) return
      setAssistantError(formatCourseAssistantError(error))
      setAssistantStatus(null)
    } finally {
      if (assistantAbortRef.current === controller) {
        assistantAbortRef.current = null
      }
      setIsAssistantAsking(false)
    }
  }, [
    assistantComposer,
    assistantTurns,
    captureAnchorMs,
    captureDraftAiContext,
    directoryBinding.permission,
    instance,
    instanceId,
    isAssistantAsking,
    llmConfigured,
    playerAiMemberBlocked,
    projectId,
    subjectId,
    subtitleSourceKind,
    touchQaActivity,
  ])

  const captureCurrentFrameIntoAnswer = useCallback(async () => {
    if (!allowCaptureDrafts || capturePanelMode !== "capture" || !isCapturePanelOpen || isFrameCaptureUploading) return
    const video = videoRef.current
    if (!video || video.readyState < 2) {
      setCaptureError("当前视频帧尚未就绪，稍等一秒再截取。")
      return
    }

    touchComposeActivity()
    setCaptureError(null)
    setIsFrameCaptureUploading(true)
    try {
      const currentMs = clampPlaybackMs(video, Math.floor(video.currentTime * 1000))
      const captured = await captureDisplayedVideoFrameFile(video, currentMs)
      const uploaded = await uploadMediaAsset(projectScope, captured.file)
      setAnswerContent((prev) => appendImageBlock(prev, uploaded.assetId))
      showInfoFeedback("已插入视频帧", `来自 ${formatPlaybackClock(captured.timeMs)} 的当前画面。`)
    } catch (error) {
      setCaptureError(error instanceof Error ? error.message : "当前视频帧插入失败。")
    } finally {
      setIsFrameCaptureUploading(false)
    }
  }, [allowCaptureDrafts, capturePanelMode, isCapturePanelOpen, isFrameCaptureUploading, projectScope, touchComposeActivity])

  const saveCaptureDraft = useCallback(() => {
    if (!allowCaptureDrafts) {
      setCaptureError("当前页面不能录入复述点。")
      return
    }
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
    touchComposeActivity()
    addDraft(projectId, {
      localId: newLocalId(),
      instanceId,
      position: `t=${captureAnchorMs}`,
      question: questionContent,
      answer: answerContent,
      references: captureReferenceIds,
      createdAt: now,
      updatedAt: now,
    })
    closeCapturePanel()
  }, [
    addDraft,
    allowCaptureDrafts,
    answerContent,
    captureAnchorMs,
    captureReferenceIds,
    closeCapturePanel,
    instanceId,
    projectId,
    questionContent,
    queueHasGate,
    touchComposeActivity,
  ])

  function handleTimeUpdate() {
    const video = videoRef.current
    if (!video) return
    if (!video.paused && !video.ended) {
      flushPlaybackDuration()
    }
    const nextMs = Math.max(0, Math.floor(video.currentTime * 1000))
    if (!video.paused && !video.ended) {
      flushPlaybackCoverage(nextMs)
    }
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
    if (subtitleMissing && isSubtitleEnabled) {
      setIsSubtitleEnabled(false)
    }
  }, [isSubtitleEnabled, subtitleMissing])

  useEffect(() => {
    flushPlaybackDuration()
    syncPlaybackClock(0)
    setDurationMs(0)
    setIsPlaying(false)
    setIsMuted(false)
    setVolumePercent(100)
    setPlaybackRate(loadVideoPlaybackRate())
    setMediaElementError(null)
    setIsShellFullscreen(false)
    setIsChromeAwake(true)
    setIsCapturePanelOpen(false)
    setCapturePanelMode("capture")
    setCaptureAnchorMs(0)
    setQuestionContent(richText(""))
    setAnswerContent(richText(""))
    setCaptureError(null)
    setAssistantComposer("")
    setAssistantTurns([])
    setAssistantStatus(null)
    setAssistantError(null)
    setAssistantFrame(null)
    setIsAssistantAsking(false)
    assistantAbortRef.current?.abort()
    assistantAbortRef.current = null
    pendingSeekRef.current = null
    lastAppliedNonceRef.current = null
    restoreSavedPositionRef.current = true
    lastPersistedPlaybackSecondRef.current = null
    lastPlaybackTrackedAtRef.current = null
    lastPlaybackTrackedPositionRef.current = null
    lastPlaybackTrackedPositionClockRef.current = null
    clearChromeHideTimer()
  }, [clearChromeHideTimer, flushPlaybackDuration, instance?.instanceId, localSrc, resetPlaybackCoverageAnchor, serverMediaStreamEnabled, syncPlaybackClock])

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
      const field = capturePanelMode === "assistant" ? assistantInputRef.current : questionInputRef.current
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
  }, [capturePanelMode, isCapturePanelOpen])

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

  useEffect(
    () => () => {
      const video = videoRef.current
      const currentPlaybackMs = video ? clampPlaybackMs(video, Math.floor(video.currentTime * 1000)) : null
      flushPlaybackCoverage(currentPlaybackMs)
      flushPlaybackDuration()
      lastPlaybackTrackedAtRef.current = null
      lastPlaybackTrackedPositionRef.current = null
      lastPlaybackTrackedPositionClockRef.current = null
    },
    [flushPlaybackCoverage, flushPlaybackDuration],
  )

  useEffect(() => {
    function flushOnBackground() {
      const video = videoRef.current
      const currentPlaybackMs = video ? clampPlaybackMs(video, Math.floor(video.currentTime * 1000)) : null
      flushPlaybackCoverage(currentPlaybackMs)
      flushPlaybackDuration()
      lastPlaybackTrackedAtRef.current = null
      lastPlaybackTrackedPositionRef.current = null
      lastPlaybackTrackedPositionClockRef.current = null
    }

    function handleVisibilityChange() {
      if (document.visibilityState === "hidden") {
        flushOnBackground()
      }
    }

    window.addEventListener("pagehide", flushOnBackground)
    document.addEventListener("visibilitychange", handleVisibilityChange)
    return () => {
      window.removeEventListener("pagehide", flushOnBackground)
      document.removeEventListener("visibilitychange", handleVisibilityChange)
    }
  }, [flushPlaybackCoverage, flushPlaybackDuration])

  useEffect(() => {
    if (!instanceId) return
    const nextDurationMs = playbackDescriptorQ.data?.durationMs
    if (typeof nextDurationMs !== "number" || nextDurationMs <= 0) return
    setDurationMs((current) => (current === nextDurationMs ? current : nextDurationMs))
    onDurationResolved?.(instanceId, nextDurationMs)
  }, [instanceId, onDurationResolved, playbackDescriptorQ.data?.durationMs])

  useEffect(() => {
    let cancelled = false
    let objectUrl: string | null = null

    async function loadLocalMedia() {
      if (!instance || effectiveSourceKind !== "BROWSER_LOCAL" || serverMediaStreamEnabled) {
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
  }, [browserLocalMediaEnabled, directoryBinding.permission, effectiveSourceKind, instance, projectId, serverMediaStreamEnabled])

  const src = useMemo(() => {
    if (!instance) return null
    if (effectiveSourceKind === "BROWSER_LOCAL" && !serverMediaStreamEnabled) {
      return localSrc
    }
    if (playbackDescriptorUrl) {
      return playbackDescriptorUrl
    }
    if (serverMediaStreamEnabled && playbackKind === "FILE") {
      return resolvePlaybackDescriptorUrl(apiUrl(projectApiPath(projectScope, `/media/instances/${instance.instanceId}`)))
    }
    return null
  }, [effectiveSourceKind, instance, localSrc, playbackDescriptorUrl, playbackKind, projectScope, serverMediaStreamEnabled])

  useEffect(() => {
    let cancelled = false
    const video = videoRef.current

    if (hlsRef.current) {
      hlsRef.current.destroy()
      hlsRef.current = null
    }

    async function loadHlsPlayback() {
      if (!video || !src || playbackKind !== "HLS") return
      setMediaElementError(null)
      try {
        const response = await fetch(src, {
          method: "GET",
          credentials: "include",
        })
        const text = await response.text()
        if (cancelled) return
        if (!response.ok) {
          let message = "百度网盘视频流加载失败，请稍后重试。"
          try {
            const parsed = JSON.parse(text) as { error?: { message?: unknown } }
            if (typeof parsed.error?.message === "string" && parsed.error.message.trim()) {
              message = parsed.error.message
            }
          } catch {
            // Keep the default message when the error payload is not JSON.
          }
          setMediaElementError(message)
          return
        }
        if (video.canPlayType("application/vnd.apple.mpegurl")) {
          video.src = src
          return
        }
        if (!Hls.isSupported()) {
          setMediaElementError("当前浏览器不支持 HLS 视频播放。")
          return
        }
        const hls = new Hls({
          enableWorker: true,
          xhrSetup: (xhr) => {
            xhr.withCredentials = true
          },
        })
        hlsRef.current = hls
        hls.on(Hls.Events.ERROR, (_event, data) => {
          if (!data.fatal || cancelled) return
          setMediaElementError(
            data.type === Hls.ErrorTypes.NETWORK_ERROR
              ? "百度网盘视频流加载失败，请稍后重试。"
              : "百度网盘视频播放失败，请刷新后重试。",
          )
          hls.destroy()
          if (hlsRef.current === hls) {
            hlsRef.current = null
          }
        })
        hls.loadSource(src)
        hls.attachMedia(video)
      } catch (error) {
        if (cancelled) return
        setMediaElementError(formatPlaybackError(error))
      }
    }

    void loadHlsPlayback()

    return () => {
      cancelled = true
      if (hlsRef.current) {
        hlsRef.current.destroy()
        hlsRef.current = null
      }
    }
  }, [playbackKind, src])

  const { hoveredBarrage } = useVideoBarrage({
    subjectId,
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
    if (playbackDescriptorQ.error) return formatPlaybackError(playbackDescriptorQ.error)
    if (mediaElementError) return mediaElementError
    if (effectiveSourceKind === "BROWSER_LOCAL" && !serverMediaStreamEnabled) return localError
    return null
  }, [effectiveSourceKind, instance, localError, mediaElementError, playbackDescriptorQ.error, serverMediaStreamEnabled])

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
    applyRememberedPlaybackRate(videoRef.current)
    syncVideoUiState(videoRef.current)
    tryApplyPendingSeek()
    tryRestoreSavedPlaybackPosition()
  }

  function handleCanPlay() {
    applyRememberedPlaybackRate(videoRef.current)
    syncVideoUiState(videoRef.current)
    tryApplyPendingSeek()
    tryRestoreSavedPlaybackPosition()
  }

  function handleVideoError() {
    const video = videoRef.current
    const mediaError = video?.error
    if (!mediaError) {
      setMediaElementError(effectiveSourceKind === "BAIDU_NETDISK" ? "百度网盘视频流播放失败，请稍后重试。" : "当前浏览器无法播放该视频。")
      return
    }
    if (effectiveSourceKind === "BAIDU_NETDISK") {
      const baiduMessageByCode: Record<number, string> = {
        1: "百度网盘视频流加载被中断。",
        2: "百度网盘视频流加载失败，请稍后重试。",
        3: "百度网盘视频流解码失败，请刷新后重试。",
        4: "当前浏览器不支持百度网盘视频播放。",
      }
      setMediaElementError(baiduMessageByCode[mediaError.code] ?? "百度网盘视频流播放失败，请稍后重试。")
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
    const video = videoRef.current
    const completedDurationMs = durationMs > 0 ? durationMs : video ? readDurationMs(video) : 0
    if (completedDurationMs > 0) {
      markVideoWatchProgressCompleted(projectScope, projectId, instanceId, completedDurationMs)
    }
    clearPlaybackResumeMs(projectId, instanceId)
    lastPersistedPlaybackSecondRef.current = null
    lastPlaybackTrackedPositionRef.current = null
    lastPlaybackTrackedPositionClockRef.current = null
    setIsPlaying(false)
  }

  useEffect(() => {
    function handleFullscreenFrameCaptureShortcut(event: KeyboardEvent) {
      if (!allowCaptureDrafts) return false
      const isFrameCaptureModifierKey =
        event.key === "Control" ||
        event.key === "Alt" ||
        event.code === "ControlLeft" ||
        event.code === "ControlRight" ||
        event.code === "AltLeft" ||
        event.code === "AltRight"
      const isFrameCaptureShortcut =
        event.ctrlKey &&
        event.altKey &&
        isFrameCaptureModifierKey &&
        !event.shiftKey &&
        !event.metaKey &&
        !event.repeat
      if (!isFrameCaptureShortcut) return false
      if (!isCapturePanelOpen || capturePanelMode !== "capture") return false
      const video = videoRef.current
      if (!video || video.readyState < 1) return false
      if (!isVideoInFullscreen(video) && !isElementInFullscreen(playerShellRef.current)) return false

      event.preventDefault()
      event.stopPropagation()
      const now = Date.now()
      if (now - lastFrameCaptureShortcutAtRef.current < 350) return true
      lastFrameCaptureShortcutAtRef.current = now
      void captureCurrentFrameIntoAnswer()
      return true
    }

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

      if (handleFullscreenFrameCaptureShortcut(event)) return

      if (event.altKey || event.ctrlKey || event.metaKey) return
      if (isShortcutBlockedTarget(event.target)) return

      if (event.code === "Space") {
        event.preventDefault()
        togglePlayback()
        return
      }

      if ((event.key === "c" || event.key === "C") && !event.shiftKey && !isCapturePanelOpen) {
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

      if (allowCaptureDrafts && (event.key === "Enter" || event.code === "NumpadEnter") && !isCapturePanelOpen) {
        event.preventDefault()
        if (event.repeat || !instanceId) return
        void openCapturePanel(undefined, true)
        return
      }

      if ((event.key === "q" || event.key === "Q") && !isCapturePanelOpen) {
        event.preventDefault()
        if (event.repeat || !instanceId) return
        void openCapturePanel(undefined, true, "assistant")
        return
      }

      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return

      event.preventDefault()
      const deltaMs = event.key === "ArrowRight" ? FULLSCREEN_KEYBOARD_SEEK_STEP_MS : -FULLSCREEN_KEYBOARD_SEEK_STEP_MS
      seekByDelta(deltaMs)
    }

    function handleFullscreenKeyUp(event: KeyboardEvent) {
      if (event.defaultPrevented || event.isComposing) return
      handleFullscreenFrameCaptureShortcut(event)
    }

    document.addEventListener("keydown", handleFullscreenKeyDown, true)
    document.addEventListener("keyup", handleFullscreenKeyUp, true)
    return () => {
      document.removeEventListener("keydown", handleFullscreenKeyDown, true)
      document.removeEventListener("keyup", handleFullscreenKeyUp, true)
    }
  }, [
    allowCaptureDrafts,
    captureCurrentFrameIntoAnswer,
    capturePanelMode,
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
  const videoElementSrc = playbackKind === "HLS" ? undefined : (src ?? undefined)
  const videoCrossOrigin = src?.startsWith("http") ? "use-credentials" : undefined
  const isBaiduConnecting = Boolean(instance && effectiveSourceKind === "BAIDU_NETDISK" && !src && !playbackError)
  const latestAssistantTurn = useMemo(
    () => [...assistantTurns].reverse().find((turn) => turn.role === "assistant") ?? null,
    [assistantTurns],
  )
  const pomodoroSnapshot = useMemo(
    () => getPomodoroSnapshot({ enabled: pomodoroEnabled, weeklySchedule: pomodoroWeeklySchedule, quickPomodoro: pomodoroQuickPomodoro }, pomodoroNow),
    [pomodoroEnabled, pomodoroNow, pomodoroQuickPomodoro, pomodoroWeeklySchedule],
  )
  const pomodoroMicroBreakSegmentKey = useMemo(() => {
    if (!pomodoroSnapshot.segment || pomodoroSnapshot.startAtMs === null) return ""
    return [
      pomodoroSnapshot.startAtMs,
      pomodoroSnapshot.segment.planId,
      pomodoroSnapshot.segment.planIndex,
      pomodoroSnapshot.segment.pomodoroIndex,
      pomodoroSnapshot.segment.startOffsetMs,
      pomodoroSnapshot.segment.endOffsetMs,
    ].join(":")
  }, [pomodoroSnapshot.segment, pomodoroSnapshot.startAtMs])
  const pomodoroMicroBreakProjectAllowed =
    !pomodoroSnapshot.currentProjectRef ||
    (pomodoroSnapshot.currentProjectRef.subjectId === subjectId && pomodoroSnapshot.currentProjectRef.scopedProjectId === projectId)
  const pomodoroMicroBreakEligible =
    pomodoroMicroBreaks.enabled &&
    pomodoroSnapshot.status === "running" &&
    pomodoroSnapshot.phase === "focus" &&
    pomodoroMicroBreakProjectAllowed &&
    isShellFullscreen &&
    shouldRenderVideo &&
    pomodoroSnapshot.segmentRemainingMs > POMODORO_MICRO_BREAK_FORBIDDEN_WINDOW_MS

  const clearMicroBreakTimers = useCallback(() => {
    if (microBreakTimeoutRef.current !== null) {
      window.clearTimeout(microBreakTimeoutRef.current)
      microBreakTimeoutRef.current = null
    }
    if (microBreakIntervalRef.current !== null) {
      window.clearInterval(microBreakIntervalRef.current)
      microBreakIntervalRef.current = null
    }
  }, [])

  const cancelMicroBreak = useCallback((reason: MicroBreakCancelReason) => {
    clearMicroBreakTimers()
    // canceled-break no-resume: cancellation never calls video.play().
    setMicroBreakState((current) => (current.status === "idle" ? current : createIdleMicroBreakState(reason)))
    setMicroBreakNow(Date.now())
  }, [clearMicroBreakTimers])

  const createNextMicroBreakSchedule = useCallback(() => {
    if (!pomodoroMicroBreakSegmentKey) return null
    const delayMs = createRandomMicroBreakDelayMs(pomodoroMicroBreaks)
    const targetAtMs = pomodoroNow + delayMs
    const forbiddenAfterMs = pomodoroNow + pomodoroSnapshot.segmentRemainingMs - POMODORO_MICRO_BREAK_FORBIDDEN_WINDOW_MS
    if (forbiddenAfterMs <= pomodoroNow) return null
    if (targetAtMs >= forbiddenAfterMs) return null
    return {
      fullscreenEnteredAtMs: Date.now(),
      targetAtMs,
      forbiddenAfterMs,
      segmentKey: pomodoroMicroBreakSegmentKey,
    }
  }, [pomodoroMicroBreakSegmentKey, pomodoroMicroBreaks, pomodoroNow, pomodoroSnapshot.segmentRemainingMs])

  useEffect(() => {
    microBreakStateRef.current = microBreakState
  }, [microBreakState])

  useEffect(() => {
    return () => cancelMicroBreak("route_change")
  }, [cancelMicroBreak])

  useEffect(() => {
    cancelMicroBreak("route_change")
  }, [cancelMicroBreak, instanceId, projectId])

  useEffect(() => {
    if (!pomodoroMicroBreaks.enabled) {
      cancelMicroBreak("settings_disabled")
      return
    }
    if (!shouldRenderVideo) {
      cancelMicroBreak("video_unavailable")
      return
    }
    if (!isShellFullscreen) {
      cancelMicroBreak("fullscreen_exit")
      return
    }
    if (!pomodoroMicroBreakEligible) {
      cancelMicroBreak("pomodoro_ineligible")
      return
    }
    if (microBreakState.status !== "idle" && microBreakState.segmentKey === pomodoroMicroBreakSegmentKey) return
    const schedule = createNextMicroBreakSchedule()
    if (!schedule) {
      setMicroBreakState((current) => (current.status === "idle" ? current : createIdleMicroBreakState("pomodoro_ineligible")))
      return
    }
    clearMicroBreakTimers()
    setMicroBreakState({ status: "scheduled",
      fullscreenEnteredAtMs: schedule.fullscreenEnteredAtMs,
      targetAtMs: schedule.targetAtMs,
      forbiddenAfterMs: schedule.forbiddenAfterMs,
      segmentKey: schedule.segmentKey,
      wasPlayingBeforeBreak: false,
      countdownEndsAtMs: null,
      cancelReason: null,
    })
    setMicroBreakNow(Date.now())
  }, [
    cancelMicroBreak,
    clearMicroBreakTimers,
    createNextMicroBreakSchedule,
    isShellFullscreen,
    microBreakState.segmentKey,
    microBreakState.status,
    pomodoroMicroBreakEligible,
    pomodoroMicroBreakSegmentKey,
    pomodoroMicroBreaks.enabled,
    shouldRenderVideo,
  ])

  const handleMicroBreakTrigger = useCallback(() => {
    const scheduledState = microBreakStateRef.current
    if (scheduledState.status !== "scheduled") return
    const video = videoRef.current
    if (!video) {
      cancelMicroBreak("video_unavailable")
      return
    }
    if (!pomodoroMicroBreakEligible || !scheduledState.forbiddenAfterMs || Date.now() >= scheduledState.forbiddenAfterMs) {
      cancelMicroBreak("pomodoro_ineligible")
      return
    }

    const wasPlayingBeforeBreak = !video.paused && !video.ended
    void playPomodoroMicroBreakReminderSound()
    video.pause()
    const now = Date.now()
    setMicroBreakNow(now)
    setMicroBreakState({
      ...scheduledState,
      status: "resting",
      wasPlayingBeforeBreak,
      countdownEndsAtMs: now + pomodoroMicroBreaks.durationSeconds * 1000,
      cancelReason: null,
    })
  }, [cancelMicroBreak, pomodoroMicroBreakEligible, pomodoroMicroBreaks.durationSeconds])

  useEffect(() => {
    if (microBreakState.status !== "scheduled" || microBreakState.targetAtMs === null) return
    const delayMs = Math.max(0, microBreakState.targetAtMs - Date.now())
    const timer = window.setTimeout(handleMicroBreakTrigger, delayMs)
    microBreakTimeoutRef.current = timer
    return () => {
      window.clearTimeout(timer)
      if (microBreakTimeoutRef.current === timer) {
        microBreakTimeoutRef.current = null
      }
    }
  }, [handleMicroBreakTrigger, microBreakState.status, microBreakState.targetAtMs])

  const completeMicroBreak = useCallback((completedState: PomodoroMicroBreakTimerState) => {
    const video = videoRef.current
    if (completedState.wasPlayingBeforeBreak) {
      if (video) {
        void video.play().catch(() => {
          // Ignore autoplay refusal; the learner can resume playback manually.
        })
      }
    }
    const schedule = pomodoroMicroBreakEligible ? createNextMicroBreakSchedule() : null
    if (!schedule) {
      setMicroBreakState(createIdleMicroBreakState())
      return
    }
    setMicroBreakState({ status: "scheduled",
      fullscreenEnteredAtMs: completedState.fullscreenEnteredAtMs ?? schedule.fullscreenEnteredAtMs,
      targetAtMs: schedule.targetAtMs,
      forbiddenAfterMs: schedule.forbiddenAfterMs,
      segmentKey: schedule.segmentKey,
      wasPlayingBeforeBreak: false,
      countdownEndsAtMs: null,
      cancelReason: null,
    })
  }, [createNextMicroBreakSchedule, pomodoroMicroBreakEligible])

  useEffect(() => {
    if (microBreakState.status !== "resting") return
    const timer = window.setInterval(() => {
      const now = Date.now()
      setMicroBreakNow(now)
      const completedState = microBreakStateRef.current
      if (completedState.status !== "resting" || completedState.countdownEndsAtMs === null) return
      if (now < completedState.countdownEndsAtMs) return
      window.clearInterval(timer)
      if (microBreakIntervalRef.current === timer) {
        microBreakIntervalRef.current = null
      }
      completeMicroBreak(completedState)
    }, 1000)
    microBreakIntervalRef.current = timer
    return () => {
      window.clearInterval(timer)
      if (microBreakIntervalRef.current === timer) {
        microBreakIntervalRef.current = null
      }
    }
  }, [completeMicroBreak, microBreakState.status])

  const showMicroBreakOverlay = microBreakState.status === "resting" && isShellFullscreen
  const microBreakRemainingMs =
    microBreakState.status === "resting" && microBreakState.countdownEndsAtMs !== null
      ? Math.max(0, microBreakState.countdownEndsAtMs - microBreakNow)
      : 0
  const pomodoroUpcomingSegment = useMemo(
    () =>
      getPomodoroUpcomingSegmentPreview({ enabled: pomodoroEnabled, weeklySchedule: pomodoroWeeklySchedule, quickPomodoro: pomodoroQuickPomodoro }, pomodoroNow),
    [pomodoroEnabled, pomodoroNow, pomodoroQuickPomodoro, pomodoroWeeklySchedule],
  )
  const fullscreenUpcomingProjectTitle = ""
  const upcomingProjectRef = pomodoroUpcomingSegment?.projectRef ?? null
  const showFullscreenFocusPreview =
    !showMicroBreakOverlay &&
    isShellFullscreen &&
    pomodoroUpcomingSegment?.phase === "focus" &&
    Boolean(upcomingProjectRef) &&
    (upcomingProjectRef?.subjectId !== subjectId || upcomingProjectRef?.scopedProjectId !== projectId) &&
    pomodoroUpcomingSegment.startsInMs > 0 &&
    pomodoroUpcomingSegment.startsInMs <= POMODORO_TRANSITION_PREVIEW_WINDOW_MS
  const showFullscreenBreakPreview =
    !showMicroBreakOverlay &&
    isShellFullscreen &&
    pomodoroUpcomingSegment?.phase === "break" &&
    pomodoroUpcomingSegment.startsInMs > 0 &&
    pomodoroUpcomingSegment.startsInMs <= POMODORO_TRANSITION_PREVIEW_WINDOW_MS

  return (
    <Card
      className={cn(surface === "workbench" ? "theme-card-main overflow-hidden" : "overflow-hidden")}
      data-surface={surface}
      data-testid="video-pane-card"
    >
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
              src={videoElementSrc}
              crossOrigin={videoCrossOrigin}
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
                applyRememberedPlaybackRate(videoRef.current)
                syncVideoUiState(videoRef.current)
              }}
              onLoadedMetadata={handleLoadedMetadata}
              onCanPlay={handleCanPlay}
              onDurationChange={() => syncVideoUiState(videoRef.current)}
              onPlay={() => {
                lastPlaybackTrackedAtRef.current = Date.now()
                resetPlaybackCoverageAnchor(Math.floor((videoRef.current?.currentTime ?? 0) * 1000))
                setIsPlaying(true)
                wakeChrome()
              }}
              onPause={() => {
                flushPlaybackCoverage(Math.floor((videoRef.current?.currentTime ?? 0) * 1000))
                flushPlaybackDuration()
                lastPlaybackTrackedAtRef.current = null
                lastPlaybackTrackedPositionRef.current = null
                lastPlaybackTrackedPositionClockRef.current = null
                setIsPlaying(false)
              }}
              onVolumeChange={() => syncVideoUiState(videoRef.current)}
              onError={handleVideoError}
              onEnded={() => {
                flushPlaybackCoverage(Math.floor((videoRef.current?.currentTime ?? 0) * 1000))
                flushPlaybackDuration()
                lastPlaybackTrackedAtRef.current = null
                lastPlaybackTrackedPositionRef.current = null
                lastPlaybackTrackedPositionClockRef.current = null
                handleEnded()
              }}
              onTimeUpdate={handleTimeUpdate}
              onSeeked={() => {
                const nextMs = Math.floor((videoRef.current?.currentTime ?? 0) * 1000)
                resetPlaybackCoverageAnchor(nextMs)
                handleTimeUpdate()
              }}
            />

            {showMicroBreakOverlay ? (
              <div className="pomodoro-micro-break-overlay pointer-events-none absolute inset-0 z-[24] flex items-center justify-center px-4 text-white">
                <div className="pomodoro-micro-break-card w-full max-w-[min(88vw,28rem)] rounded-[1.2rem] border border-white/18 px-5 py-6 text-center">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-white/68">Micro Break</div>
                  <div className="mt-3 text-3xl font-semibold tracking-normal">闭眼休息</div>
                  <div className="mt-3 font-mono text-5xl font-semibold tabular-nums">
                    {formatPomodoroCountdown(microBreakRemainingMs)}
                  </div>
                  <div className="mt-3 text-sm leading-6 text-white/78">
                    放松眼睛，保持呼吸。倒计时结束后会按之前的播放状态继续。
                  </div>
                </div>
              </div>
            ) : null}

            {showFullscreenFocusPreview && pomodoroUpcomingSegment ? (
              <div className="pointer-events-none absolute inset-x-0 top-4 z-[22] flex justify-center px-4">
                <div className="w-full max-w-[min(92vw,34rem)] rounded-[1.2rem] border border-white/18 bg-[linear-gradient(140deg,rgba(7,12,24,0.84),rgba(18,31,60,0.76))] px-4 py-3 text-white shadow-[0_22px_56px_-34px_rgba(7,12,24,0.88)] backdrop-blur-xl">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-white/70">Upcoming Jump</div>
                  <div className="mt-1 text-base font-semibold">
                    {formatPomodoroCountdown(pomodoroUpcomingSegment.startsInMs)} 后切到
                    {fullscreenUpcomingProjectTitle ? `“${fullscreenUpcomingProjectTitle}”` : "绑定项目"}
                  </div>
                  <div className="mt-1 text-sm leading-6 text-white/80">
                    第 {pomodoroUpcomingSegment.pomodoroIndex}/{pomodoroUpcomingSegment.totalPomodoros} 个番茄即将开始，系统会自动离开当前项目并进入对应工作台。
                  </div>
                </div>
              </div>
            ) : null}

            {showFullscreenBreakPreview && pomodoroUpcomingSegment ? (
              <div className="pointer-events-none absolute inset-x-0 top-4 z-[22] flex justify-center px-4">
                <div className="w-full max-w-[min(92vw,34rem)] rounded-[1.2rem] border border-white/18 bg-[linear-gradient(140deg,rgba(34,20,6,0.82),rgba(79,45,10,0.74))] px-4 py-3 text-white shadow-[0_22px_56px_-34px_rgba(42,22,6,0.9)] backdrop-blur-xl">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-white/70">Upcoming Lock</div>
                  <div className="mt-1 text-base font-semibold">
                    {formatPomodoroCountdown(pomodoroUpcomingSegment.startsInMs)} 后进入休息时间
                  </div>
                  <div className="mt-1 text-sm leading-6 text-white/80">
                    当前工作台即将锁定，系统会把你拦回番茄钟页，建议先收尾当前操作。
                  </div>
                </div>
              </div>
            ) : null}

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
              subjectId={subjectId}
              projectId={projectId}
              hoveredBarrage={hoveredBarrage}
              isEnabled={isBarrageEnabled}
              isCapturePanelOpen={isCapturePanelOpen}
            />

            {subtitleState.text ? (
              <div
                className={cn(
                  "pointer-events-none absolute inset-x-0 z-[18] flex justify-center px-4",
                  isShellFullscreen ? "bottom-24 px-6" : "bottom-16",
                )}
              >
                <div
                  className={cn(
                    "w-auto max-w-[min(92vw,58rem)] text-center text-white",
                    isShellFullscreen && "max-w-[min(90vw,78rem)]",
                  )}
                >
                  {subtitleDisplayLines.map((line, index) => (
                    <div
                      key={`${index}:${line}`}
                      className={cn(
                        "whitespace-normal break-words font-semibold [text-shadow:0_2px_14px_rgba(0,0,0,0.92)]",
                        isShellFullscreen
                          ? "text-[clamp(1.3rem,1.9vw,2rem)] leading-[1.55]"
                          : "text-[15px] leading-7 sm:text-[17px]",
                        index > 0 && "mt-0.5",
                      )}
                    >
                      {line}
                    </div>
                  ))}
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
                        <div className="pointer-events-none absolute bottom-full left-1/2 pb-2 -translate-x-1/2 opacity-0 transition duration-150 group-hover/volume:pointer-events-auto group-hover/volume:opacity-100 group-focus-within/volume:pointer-events-auto group-focus-within/volume:opacity-100">
                          <div className="rounded-xl border border-white/12 bg-slate-950 p-1 shadow-[0_14px_32px_-20px_rgba(0,0,0,0.9)]">
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
                      <div className="pointer-events-none absolute bottom-full left-1/2 pb-2 -translate-x-1/2 opacity-0 transition duration-150 group-hover/rate:pointer-events-auto group-hover/rate:opacity-100 group-focus-within/rate:pointer-events-auto group-focus-within/rate:opacity-100">
                          <div className="min-w-[4.75rem] rounded-xl border border-white/12 bg-slate-950 p-1 shadow-[0_14px_32px_-20px_rgba(0,0,0,0.9)]">
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
                          subtitleMissing
                            ? "border border-white/8 bg-white/[0.04] text-white/34 hover:bg-white/[0.04] hover:text-white/34"
                            : isSubtitleEnabled
                            ? "border border-emerald-200/18 bg-emerald-300/18 text-emerald-50 hover:bg-emerald-300/24"
                            : "border border-white/10 text-white/72 hover:bg-white/10 hover:text-white",
                        )}
                        aria-pressed={isSubtitleEnabled}
                        onClick={toggleSubtitles}
                        disabled={subtitleButtonDisabled}
                        title={
                          subtitleMissing
                            ? (subtitleMissingText ?? "当前视频没有可用字幕文件")
                            : isSubtitleEnabled
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
                      {allowCaptureDrafts ? (
                        <Button
                          type="button"
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7 rounded-full text-white hover:bg-white/10"
                          onClick={() => void openCapturePanel(undefined, true, "capture")}
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
                        className={cn(
                          "h-7 w-7 rounded-full hover:bg-white/10",
                          capturePanelMode === "assistant" && isCapturePanelOpen
                            ? "text-cyan-100"
                            : "text-white",
                        )}
                        onClick={() => void openCapturePanel(undefined, true, "assistant")}
                        disabled={!instanceId || !llmConfigured}
                        title={llmConfigured ? "问视频助手 (Q)" : "当前还没有配置视频助手所需的 LLM"}
                      >
                        <MessageSquarePlus className="h-3.5 w-3.5" />
                        <span className="sr-only">问视频助手</span>
                      </Button>
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
                <div
                  className={cn(
                    "pointer-events-auto absolute bottom-12 right-3 flex max-h-[calc(100%-4.5rem)] flex-col overflow-hidden rounded-[1rem] border border-white/12 bg-[linear-gradient(180deg,rgba(15,23,42,0.84),rgba(2,6,23,0.94))] p-4 text-white shadow-[0_28px_64px_-34px_rgba(15,23,42,0.96)] backdrop-blur-xl",
                    capturePanelMode === "assistant"
                      ? "w-[min(42rem,calc(100%-1.5rem))]"
                      : "w-[min(24rem,calc(100%-1.5rem))]",
                  )}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-[11px] uppercase tracking-[0.18em] text-white/42">
                          {capturePanelMode === "assistant" ? "视频助手" : "记复述点"}
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <div className="inline-flex items-center rounded-full border border-cyan-200/18 bg-cyan-200/10 px-2.5 py-1 text-[11px] text-cyan-100">
                          锚点 {formatPlaybackClock(captureAnchorMs)}
                        </div>
                        {capturePanelMode === "assistant" && assistantFrame ? (
                          <div className="inline-flex items-center rounded-full border border-white/12 bg-white/[0.06] px-2.5 py-1 text-[11px] text-white/72">
                            已附带画面 {formatPlaybackClock(assistantFrame.timeMs)}
                          </div>
                        ) : null}
                      </div>
                    </div>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="h-8 w-8 rounded-full text-white/72 hover:bg-white/10 hover:text-white"
                      onClick={closeCapturePanel}
                      title={capturePanelMode === "assistant" ? "关闭视频助手" : "关闭记复述点"}
                    >
                      <X className="h-4 w-4" />
                      <span className="sr-only">{capturePanelMode === "assistant" ? "关闭视频助手" : "关闭记复述点"}</span>
                    </Button>
                  </div>

                  {capturePanelMode === "assistant" ? (
                    <div className="mt-3 flex min-h-0 flex-1 flex-col gap-3">
                      <div>
                        <label className="block">
                          <div className="mb-1 text-xs text-white/62">问题</div>
                          <textarea
                            ref={assistantInputRef}
                            value={assistantComposer}
                            onChange={(event) => {
                              touchQaActivity()
                              setAssistantComposer(event.target.value)
                              if (assistantError) setAssistantError(null)
                            }}
                            onFocus={touchQaActivity}
                            onClick={touchQaActivity}
                            onKeyDown={(event) => {
                              touchQaActivity()
                              if (event.key === "Escape") {
                                event.preventDefault()
                                closeCapturePanel()
                                return
                              }
                              if (event.nativeEvent.isComposing) return
                              if (event.key === "Enter" && !(event.ctrlKey || event.metaKey || event.shiftKey)) {
                                event.preventDefault()
                                void submitAssistantQuestion()
                              }
                            }}
                            placeholder={
                              canAskCourseAssistant
                                ? "例如：这页公式在讲什么？为什么这里要这样推？"
                                : "当前项目还没有满足视频助手的上下文条件"
                            }
                            disabled={!canAskCourseAssistant || isAssistantAsking}
                            className="min-h-[104px] w-full rounded-xl border border-white/10 bg-white/[0.05] px-3 py-2 text-sm text-white outline-none placeholder:text-white/28 focus:border-cyan-200/24 focus:bg-white/[0.08] disabled:cursor-not-allowed disabled:text-white/42"
                          />
                        </label>
                      </div>

                      <div
                        className="min-h-0 flex-1 overflow-y-auto rounded-[1rem] border border-white/10 bg-white/[0.04] p-3"
                        onScroll={touchQaActivity}
                      >
                        {playerAiMemberBlocked ? (
                          <MemberOnlyFeatureNotice
                            compact
                            title="视频助手是会员专属功能"
                            message="当前账号还没有有效会员。开通后就可以继续围绕当前画面和字幕提问。"
                            className="border-white/10 bg-white/[0.06] text-left shadow-none [&_h2]:text-white [&_p]:text-white/60"
                          />
                        ) : assistantTurns.length === 0 && !isAssistantAsking ? (
                          <div className="flex h-full min-h-[12rem] flex-col items-center justify-center px-4 text-center">
                            <div className="flex h-10 w-10 items-center justify-center rounded-full border border-cyan-200/18 bg-cyan-200/10 text-cyan-100">
                              <Sparkles className="h-4 w-4" />
                            </div>
                            <div className="mt-3 text-sm font-medium text-white">直接问这一刻正在讲什么</div>
                            <div className="mt-2 max-w-[28rem] text-xs leading-6 text-white/56">
                              视频助手会读取当前画面和附近字幕，再给你答案。
                            </div>
                          </div>
                        ) : (
                          <div className="space-y-3">
                            {assistantTurns.map((turn) =>
                              turn.role === "user" ? (
                                <div key={turn.id} className="flex justify-end">
                                  <div className="max-w-[85%] rounded-[1.2rem] border border-cyan-200/18 bg-cyan-300/12 px-4 py-3 text-sm leading-6 text-cyan-50">
                                    <div className="whitespace-pre-wrap break-words">{turn.content}</div>
                                  </div>
                                </div>
                              ) : (
                                <div
                                  key={turn.id}
                                  className="rounded-[1.2rem] border border-slate-200/70 bg-[rgba(252,254,255,0.98)] px-4 py-4 text-slate-900 shadow-[0_16px_32px_-28px_rgba(15,23,42,0.7)]"
                                >
                                  <MarkdownRichText text={turn.content} className="text-slate-900" />
                                  {turn.evidence && turn.evidence.length > 0 ? (
                                    <div className="mt-4 space-y-2">
                                      <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                                        依据片段
                                      </div>
                                      <div className="flex flex-wrap gap-2">
                                        {turn.evidence.map((evidence, index) => (
                                          <button
                                            key={`${turn.id}:${evidence.kind}:${evidence.startMs}:${evidence.endMs}:${index}`}
                                            type="button"
                                            className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-left text-[11px] leading-5 text-slate-600 transition hover:border-cyan-300/50 hover:bg-cyan-50 hover:text-cyan-800"
                                            onClick={() => {
                                              touchQaActivity()
                                              applySeekMs(evidence.startMs)
                                              setCaptureAnchorMs(evidence.startMs)
                                              setAssistantFrame(null)
                                            }}
                                            title="跳到这一段"
                                          >
                                            {evidence.title} · {formatEvidenceTimeRange(evidence.startMs, evidence.endMs)}
                                          </button>
                                        ))}
                                      </div>
                                    </div>
                                  ) : null}
                                </div>
                              ),
                            )}
                            {isAssistantAsking ? (
                              <div className="rounded-[1.2rem] border border-white/10 bg-white/[0.06] px-4 py-3 text-sm text-white/82">
                                <div className="inline-flex items-center gap-2">
                                  <LoaderCircle className="h-4 w-4 animate-spin" />
                                  {assistantStatus ?? "正在思考..."}
                                </div>
                              </div>
                            ) : null}
                          </div>
                        )}
                      </div>

                      <div className={cn("text-xs leading-5", assistantError ? "text-rose-200" : "text-white/52")}>
                        {assistantError ?? "Enter 提交问题，Shift+Enter 换行。视频助手会读取当前画面和附近字幕。"}
                      </div>

                      <div className="flex items-center justify-between gap-2">
                        <Button
                          type="button"
                          variant="ghost"
                          className="text-white/72 hover:bg-white/10 hover:text-white"
                          onClick={() => void copyLatestAssistantAnswer()}
                          disabled={!latestAssistantTurn?.content.trim()}
                        >
                          <Copy className="h-4 w-4" />
                          复制回答
                        </Button>
                        <div className="flex items-center gap-2">
                          <Button
                            type="button"
                            variant="ghost"
                            className="text-white/72 hover:bg-white/10 hover:text-white"
                            onClick={closeCapturePanel}
                          >
                            关闭
                          </Button>
                          <Button
                            type="button"
                            onClick={() => void submitAssistantQuestion()}
                            disabled={!canAskCourseAssistant || isAssistantAsking || !assistantComposer.trim()}
                          >
                            {isAssistantAsking ? (
                              <>
                                <LoaderCircle className="h-4 w-4 animate-spin" />
                                思考中
                              </>
                            ) : (
                              "发送问题"
                            )}
                          </Button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-3 min-h-0 overflow-y-auto pr-1">
                      <div className="space-y-3">
                        <label className="block">
                          <div className="mb-1 text-xs text-white/62">问题</div>
                          <RichContentEditor
                            subjectId={subjectId}
                            projectId={projectId}
                            field="question"
                            value={questionContent}
                            textareaRef={questionInputRef}
                            onUserActivity={touchComposeActivity}
                            placeholder="输入复述点问题，或直接 Ctrl+V 粘贴图片"
                            textareaClassName="min-h-[84px] rounded-xl border-white/10 bg-white/[0.05] px-3 py-2 text-sm text-white outline-none placeholder:text-white/28 focus:border-cyan-200/24 focus:bg-white/[0.08]"
                            imageClassName="h-24 w-24 rounded-xl border-white/10 bg-white/[0.06] object-cover"
                            onTextChange={(text) => {
                              touchComposeActivity()
                              setQuestionContent((prev) => setRichContentText(prev, text))
                              if (captureError) setCaptureError(null)
                            }}
                            onAppendImage={(assetId) => {
                              touchComposeActivity()
                              setQuestionContent((prev) => appendImageBlock(prev, assetId))
                              if (captureError) setCaptureError(null)
                            }}
                            onRemoveImage={(imageIndex) => {
                              touchComposeActivity()
                              setQuestionContent((prev) => removeImageBlockAt(prev, imageIndex))
                              if (captureError) setCaptureError(null)
                            }}
                            onTextKeyDown={(event) => {
                              touchComposeActivity()
                              if (event.key === "Escape") {
                                event.preventDefault()
                                closeCapturePanel()
                                return
                              }
                              if (event.nativeEvent.isComposing) return
                              if (event.key === "Tab" && !event.shiftKey) {
                                event.preventDefault()
                                openCaptureReferencePicker("question")
                                return
                              }
                              if (event.key === "Enter" && !(event.ctrlKey || event.metaKey || event.shiftKey)) {
                                event.preventDefault()
                                answerTextareaRef.current?.focus()
                              }
                            }}
                            referencePicker={
                              captureReferencePicker?.field === "question"
                                ? {
                                    isOpen: true,
                                    isLoading:
                                      captureReferenceSearchQ.isLoading ||
                                      (captureReferenceSearchQ.isFetching && !captureReferenceSearchQ.data),
                                    query: captureReferencePicker.query,
                                    highlightedIndex: captureReferencePicker.highlightedIndex,
                                    candidates: captureReferenceCandidates,
                                    onQueryChange: (query) =>
                                      setCaptureReferencePicker((current) => (current ? { ...current, query, highlightedIndex: 0 } : current)),
                                    onHighlightChange: (index) =>
                                      setCaptureReferencePicker((current) => (current ? { ...current, highlightedIndex: index } : current)),
                                    onConfirm: () => confirmCaptureReferencePickerSelection("question"),
                                    onSelect: (recallPointId) => {
                                      addCaptureReference(recallPointId)
                                      closeCaptureReferencePicker("question")
                                    },
                                    onClose: () => closeCaptureReferencePicker("question"),
                                  }
                                : undefined
                            }
                          />
                        </label>

                        <label className="block">
                          <div className="mb-1 text-xs text-white/62">答案</div>
                          <RichContentEditor
                            subjectId={subjectId}
                            projectId={projectId}
                            field="answer"
                            value={answerContent}
                            textareaRef={answerTextareaRef}
                            onUserActivity={touchComposeActivity}
                            placeholder="输入答案或你的复述内容，或直接 Ctrl+V 粘贴图片"
                            textareaClassName="min-h-[124px] rounded-xl border-white/10 bg-white/[0.05] px-3 py-2 text-sm text-white outline-none placeholder:text-white/28 focus:border-cyan-200/24 focus:bg-white/[0.08]"
                            imageClassName="h-24 w-24 rounded-xl border-white/10 bg-white/[0.06] object-cover"
                            onTextChange={(text) => {
                              touchComposeActivity()
                              setAnswerContent((prev) => setRichContentText(prev, text))
                              if (captureError) setCaptureError(null)
                            }}
                            onAppendImage={(assetId) => {
                              touchComposeActivity()
                              setAnswerContent((prev) => appendImageBlock(prev, assetId))
                              if (captureError) setCaptureError(null)
                            }}
                            onRemoveImage={(imageIndex) => {
                              touchComposeActivity()
                              setAnswerContent((prev) => removeImageBlockAt(prev, imageIndex))
                              if (captureError) setCaptureError(null)
                            }}
                            onTextKeyDown={(event) => {
                              touchComposeActivity()
                              if (event.key === "Escape") {
                                event.preventDefault()
                                closeCapturePanel()
                                return
                              }
                              if (event.nativeEvent.isComposing) return
                              if (event.key === "Tab" && !event.shiftKey) {
                                event.preventDefault()
                                openCaptureReferencePicker("answer")
                                return
                              }
                              if (event.key === "Enter" && !(event.ctrlKey || event.metaKey || event.shiftKey)) {
                                event.preventDefault()
                                void saveCaptureDraft()
                              }
                            }}
                            referencePicker={
                              captureReferencePicker?.field === "answer"
                                ? {
                                    isOpen: true,
                                    isLoading:
                                      captureReferenceSearchQ.isLoading ||
                                      (captureReferenceSearchQ.isFetching && !captureReferenceSearchQ.data),
                                    query: captureReferencePicker.query,
                                    highlightedIndex: captureReferencePicker.highlightedIndex,
                                    candidates: captureReferenceCandidates,
                                    onQueryChange: (query) =>
                                      setCaptureReferencePicker((current) => (current ? { ...current, query, highlightedIndex: 0 } : current)),
                                    onHighlightChange: (index) =>
                                      setCaptureReferencePicker((current) => (current ? { ...current, highlightedIndex: index } : current)),
                                    onConfirm: () => confirmCaptureReferencePickerSelection("answer"),
                                    onSelect: (recallPointId) => {
                                      addCaptureReference(recallPointId)
                                      closeCaptureReferencePicker("answer")
                                    },
                                    onClose: () => closeCaptureReferencePicker("answer"),
                                  }
                                : undefined
                            }
                          />
                        </label>
                      </div>

                      <div className="mt-3 rounded-xl border border-white/10 bg-white/[0.045] px-3 py-3">
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-[11px] uppercase tracking-[0.16em] text-white/44">引用关系</div>
                          <div className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-white/54">
                            已引用 {captureReferenceIds.length} 条
                          </div>
                        </div>
                        {captureReferenceIds.length > 0 ? (
                          <div className="mt-2 flex flex-wrap gap-2">
                            {captureReferenceIds.map((referenceId) => (
                              <button
                                key={`capture-reference-${referenceId}`}
                                type="button"
                                className="inline-flex max-w-full items-center gap-2 rounded-full border border-cyan-200/18 bg-cyan-200/10 px-2.5 py-1 text-left text-[11px] text-cyan-50"
                                onClick={() => {
                                  touchComposeActivity()
                                  setCaptureReferenceIds((current) => current.filter((id) => id !== referenceId))
                                }}
                                title={`移除 ${referenceId}`}
                              >
                                <span className="truncate">{formatRecallPointReference(referenceId)}</span>
                                <span className="text-white/44">移除</span>
                              </button>
                            ))}
                          </div>
                        ) : (
                          <div className="mt-2 text-xs text-white/42">还没有引用其他复述点。</div>
                        )}
                        {captureReferenceSearchQ.error ? (
                          <div className="mt-2 text-xs text-rose-200">候选复述点加载失败：{formatCourseAssistantError(captureReferenceSearchQ.error)}</div>
                        ) : null}
                      </div>

                      <div className={cn("mt-2 text-xs", captureError ? "text-rose-200" : "text-white/44")}>
                        {captureError ??
                          (isFrameCaptureUploading
                            ? "正在截取并插入当前视频帧..."
                            : "全屏时 Enter 可打开录入；录入框中 Enter 切换/保存，Shift+Enter 换行，Tab 引用复述点，Ctrl+Alt 截当前视频帧到答案。")}
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
                  )}
                </div>
              </div>
            ) : null}
          </div>
        ) : (
          <div
            className={cn(
              "rounded-[1.2rem] border p-6 text-sm text-muted-foreground",
              surface === "workbench" ? "theme-canvas border-border/60" : "border-[#dbe4ee] bg-[#fbfdff]",
            )}
          >
            <div className="flex items-start gap-3">
              <div className="theme-icon-surface mt-0.5 h-10 w-10 shrink-0">
                <VideoOff className="h-5 w-5" />
              </div>
              <div className="space-y-1.5">
                <div className="text-sm font-medium text-foreground">
                  {instance
                    ? playbackError ??
                      (isBaiduConnecting
                        ? "正在连接百度网盘视频流..."
                        : !serverMediaStreamEnabled && effectiveSourceKind === "BROWSER_LOCAL"
                          ? "正在准备播放资源..."
                          : "当前视频暂时不可用。")
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
})

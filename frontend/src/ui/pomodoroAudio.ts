import { useEffect, useRef } from "react"

import { requestPomodoroTtsPreviewAudio } from "@/ui/api/system"
import type { PomodoroPhase, PomodoroSnapshot } from "@/ui/store/pomodoroStore"

type AudioWindow = Window &
  typeof globalThis & {
    webkitAudioContext?: typeof AudioContext
  }

export type PomodoroTransitionSnapshot = Pick<PomodoroSnapshot, "status" | "phase" | "segmentIndex">
export type PomodoroPromptPreview = {
  key: string
  promptText: string
  startsInMs: number
}

let sharedAudioContext: AudioContext | null = null
let activePomodoroPromptAudio: HTMLAudioElement | null = null
const pomodoroPromptAudioCache = new Map<string, Promise<string>>()

function getAudioContext() {
  if (typeof window === "undefined") return null
  const view = window as AudioWindow
  const AudioContextCtor = view.AudioContext ?? view.webkitAudioContext
  if (!AudioContextCtor) return null
  if (!sharedAudioContext) {
    sharedAudioContext = new AudioContextCtor()
  }
  return sharedAudioContext
}

async function ensureAudioContextReady() {
  const context = getAudioContext()
  if (!context) return null
  if (context.state === "suspended") {
    try {
      await context.resume()
    } catch {
      return null
    }
  }
  return context
}

function scheduleNote(
  context: AudioContext,
  note: { startAt: number; frequency: number; duration: number; volume: number },
) {
  const { startAt, frequency, duration, volume } = note
  const oscillator = context.createOscillator()
  const gainNode = context.createGain()
  oscillator.type = "sine"
  oscillator.frequency.setValueAtTime(frequency, startAt)
  gainNode.gain.setValueAtTime(0.0001, startAt)
  gainNode.gain.exponentialRampToValueAtTime(volume, startAt + 0.02)
  gainNode.gain.exponentialRampToValueAtTime(0.0001, startAt + duration)
  oscillator.connect(gainNode)
  gainNode.connect(context.destination)
  oscillator.start(startAt)
  oscillator.stop(startAt + duration + 0.02)
}

export async function unlockPomodoroAudio() {
  await ensureAudioContextReady()
}

async function getPomodoroPromptAudioUrl(text: string) {
  const normalizedText = String(text || "").trim()
  if (!normalizedText) {
    return ""
  }
  const cached = pomodoroPromptAudioCache.get(normalizedText)
  if (cached) {
    return cached
  }
  const pending = requestPomodoroTtsPreviewAudio({ text: normalizedText }).then((blob) => {
    const objectUrl = URL.createObjectURL(blob)
    return objectUrl
  })
  pomodoroPromptAudioCache.set(normalizedText, pending)
  try {
    return await pending
  } catch (error) {
    pomodoroPromptAudioCache.delete(normalizedText)
    throw error
  }
}

export async function playPomodoroVoicePrompt(text: string) {
  const normalizedText = String(text || "").trim()
  if (!normalizedText || typeof window === "undefined") return false
  const audioUrl = await getPomodoroPromptAudioUrl(normalizedText)
  if (!audioUrl) return false
  if (activePomodoroPromptAudio) {
    activePomodoroPromptAudio.pause()
    activePomodoroPromptAudio.currentTime = 0
  }
  const audio = new Audio(audioUrl)
  audio.preload = "auto"
  activePomodoroPromptAudio = audio
  try {
    await audio.play()
    return true
  } catch {
    return false
  }
}

export async function playPomodoroTransitionSound(phase: PomodoroPhase) {
  const context = await ensureAudioContextReady()
  if (!context) return false

  const startAt = context.currentTime + 0.02
  const notes =
    phase === "focus"
      ? [
          { frequency: 659.25, offset: 0, duration: 0.18, volume: 0.06 },
          { frequency: 783.99, offset: 0.2, duration: 0.18, volume: 0.055 },
          { frequency: 987.77, offset: 0.4, duration: 0.22, volume: 0.05 },
        ]
      : [
          { frequency: 587.33, offset: 0, duration: 0.2, volume: 0.06 },
          { frequency: 493.88, offset: 0.22, duration: 0.2, volume: 0.055 },
          { frequency: 392, offset: 0.44, duration: 0.26, volume: 0.05 },
        ]

  for (const note of notes) {
    scheduleNote(context, {
      startAt: startAt + note.offset,
      frequency: note.frequency,
      duration: note.duration,
      volume: note.volume,
    })
  }

  return true
}

export async function playPomodoroMicroBreakReminderSound() {
  const context = await ensureAudioContextReady()
  if (!context) return false

  const startAt = context.currentTime + 0.02
  const microBreakReminderNotes = [
    { frequency: 880, offset: 0, duration: 0.12, volume: 0.055 },
    { frequency: 1174.66, offset: 0.16, duration: 0.14, volume: 0.05 },
    { frequency: 880, offset: 0.34, duration: 0.18, volume: 0.045 },
  ]

  for (const note of microBreakReminderNotes) {
    scheduleNote(context, {
      startAt: startAt + note.offset,
      frequency: note.frequency,
      duration: note.duration,
      volume: note.volume,
    })
  }

  return true
}

export function detectPomodoroPhaseTransition(
  previous: PomodoroTransitionSnapshot | null,
  snapshot: PomodoroTransitionSnapshot,
) {
  if (!previous) return null
  if (previous.status !== "running" || snapshot.status !== "running") return null
  if (!previous.phase || !snapshot.phase) return null
  if (previous.phase === snapshot.phase) return null
  if (previous.segmentIndex === snapshot.segmentIndex) return null
  const switchedBetweenFocusAndBreak =
    (previous.phase === "focus" && snapshot.phase === "break") ||
    (previous.phase === "break" && snapshot.phase === "focus")
  if (!switchedBetweenFocusAndBreak) return null
  return {
    fromPhase: previous.phase,
    toPhase: snapshot.phase,
  }
}

export function usePomodoroTransitionSound(snapshot: PomodoroTransitionSnapshot, enabled: boolean) {
  const previousSnapshotRef = useRef<PomodoroTransitionSnapshot | null>(null)

  useEffect(() => {
    function onUserGesture() {
      void unlockPomodoroAudio()
    }

    window.addEventListener("pointerdown", onUserGesture, { passive: true })
    window.addEventListener("keydown", onUserGesture)
    return () => {
      window.removeEventListener("pointerdown", onUserGesture)
      window.removeEventListener("keydown", onUserGesture)
    }
  }, [])

  useEffect(() => {
    const previous = previousSnapshotRef.current
    previousSnapshotRef.current = snapshot
    if (!enabled || !previous) return
    const transition = detectPomodoroPhaseTransition(previous, snapshot)
    if (!transition) return
    void playPomodoroTransitionSound(transition.toPhase)
  }, [enabled, snapshot])
}

export function usePomodoroPreTransitionSpeech(preview: PomodoroPromptPreview | null) {
  const spokenKeyRef = useRef("")

  useEffect(() => {
    if (!preview || !preview.promptText.trim()) return
    if (preview.startsInMs <= 0 || preview.startsInMs > 10_000) return
    if (spokenKeyRef.current === preview.key) return
    spokenKeyRef.current = preview.key
    void playPomodoroVoicePrompt(preview.promptText).catch(() => {
      // Ignore preview speech failures and keep the visual reminder as the fallback.
    })
  }, [preview])
}

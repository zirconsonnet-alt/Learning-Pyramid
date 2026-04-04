export const VIDEO_SUBTITLE_STORAGE_KEY = "plm-video-subtitles-enabled"
export const VIDEO_SUBTITLE_DELAY_STORAGE_KEY = "plm-video-subtitles-delay-ms"
export const VIDEO_SUBTITLE_DELAY_STEP_MS = 250
export const VIDEO_SUBTITLE_DELAY_LIMIT_MS = 2_000

export function loadVideoSubtitleEnabled() {
  if (typeof window === "undefined") return false
  try {
    const raw = window.localStorage.getItem(VIDEO_SUBTITLE_STORAGE_KEY)
    if (raw === null) return false
    return raw !== "0"
  } catch {
    return false
  }
}

function clampSubtitleDelayMs(value: number) {
  return Math.min(VIDEO_SUBTITLE_DELAY_LIMIT_MS, Math.max(-VIDEO_SUBTITLE_DELAY_LIMIT_MS, Math.round(value)))
}

export function loadVideoSubtitleDelayMs() {
  if (typeof window === "undefined") return 0
  try {
    const raw = window.localStorage.getItem(VIDEO_SUBTITLE_DELAY_STORAGE_KEY)
    if (raw === null) return 0
    const value = Number(raw)
    if (!Number.isFinite(value)) return 0
    return clampSubtitleDelayMs(value)
  } catch {
    return 0
  }
}

export function normalizeVideoSubtitleDelayMs(value: number) {
  return clampSubtitleDelayMs(value)
}

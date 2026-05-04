export const VIDEO_PLAYBACK_RATE_STORAGE_KEY = "plm-video-playback-rate"
export const DEFAULT_VIDEO_PLAYBACK_RATE = 1
export const VIDEO_PLAYBACK_RATE_OPTIONS = [0.75, 1, 1.25, 1.5, 2] as const

export function normalizeVideoPlaybackRate(value: unknown): number {
  if (value === null || value === undefined || value === "") return DEFAULT_VIDEO_PLAYBACK_RATE
  const parsed = typeof value === "number" ? value : Number(value)
  if (!Number.isFinite(parsed)) return DEFAULT_VIDEO_PLAYBACK_RATE
  return VIDEO_PLAYBACK_RATE_OPTIONS.reduce(
    (best, option) => (Math.abs(option - parsed) < Math.abs(best - parsed) ? option : best),
    DEFAULT_VIDEO_PLAYBACK_RATE,
  )
}

export function loadVideoPlaybackRate(): number {
  if (typeof window === "undefined") return DEFAULT_VIDEO_PLAYBACK_RATE
  try {
    return normalizeVideoPlaybackRate(window.localStorage.getItem(VIDEO_PLAYBACK_RATE_STORAGE_KEY))
  } catch {
    return DEFAULT_VIDEO_PLAYBACK_RATE
  }
}

export function saveVideoPlaybackRate(rate: number) {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(VIDEO_PLAYBACK_RATE_STORAGE_KEY, String(normalizeVideoPlaybackRate(rate)))
  } catch {
    // Ignore storage write failures and keep playback responsive.
  }
}

export const VIDEO_BARRAGE_STORAGE_KEY = "plm-video-barrage-enabled"

export function loadVideoBarrageEnabled() {
  if (typeof window === "undefined") return true
  try {
    const raw = window.localStorage.getItem(VIDEO_BARRAGE_STORAGE_KEY)
    if (raw === null) return true
    return raw !== "0"
  } catch {
    return true
  }
}

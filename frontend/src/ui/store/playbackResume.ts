const PLAYBACK_RESUME_STORAGE_PREFIX = "plm-playback-resume:"

export function playbackResumeStorageKey(projectId: string, instanceId: string) {
  return `${PLAYBACK_RESUME_STORAGE_PREFIX}${projectId}:${instanceId}`
}

export function loadPlaybackResumeMs(projectId: string, instanceId: string) {
  if (typeof window === "undefined") return null
  try {
    const raw = window.localStorage.getItem(playbackResumeStorageKey(projectId, instanceId))
    if (!raw) return null
    const parsed = Number(raw)
    return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : null
  } catch {
    return null
  }
}

export function savePlaybackResumeMs(projectId: string, instanceId: string, ms: number) {
  if (typeof window === "undefined") return
  try {
    if (!Number.isFinite(ms) || ms <= 0) {
      window.localStorage.removeItem(playbackResumeStorageKey(projectId, instanceId))
      return
    }
    window.localStorage.setItem(playbackResumeStorageKey(projectId, instanceId), String(Math.floor(ms)))
  } catch {
    // Ignore browser storage failures and keep playback working.
  }
}

export function clearPlaybackResumeMs(projectId: string, instanceId: string) {
  if (typeof window === "undefined") return
  try {
    window.localStorage.removeItem(playbackResumeStorageKey(projectId, instanceId))
  } catch {
    // Ignore browser storage failures and keep playback working.
  }
}

export function clearAllPlaybackResumeState() {
  if (typeof window === "undefined") return
  try {
    const keys: string[] = []
    for (let index = 0; index < window.localStorage.length; index += 1) {
      const key = window.localStorage.key(index)
      if (key?.startsWith(PLAYBACK_RESUME_STORAGE_PREFIX)) {
        keys.push(key)
      }
    }
    for (const key of keys) {
      window.localStorage.removeItem(key)
    }
  } catch {
    // Ignore browser storage failures and keep playback working.
  }
}

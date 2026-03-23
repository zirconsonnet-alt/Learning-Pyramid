const VIDEO_DURATION_STORAGE_PREFIX = "plm-video-duration:"

export function videoDurationStorageKey(projectId: string, instanceId: string) {
  return `${VIDEO_DURATION_STORAGE_PREFIX}${projectId}:${instanceId}`
}

export function loadVideoDurationMs(projectId: string, instanceId: string) {
  if (typeof window === "undefined") return null
  try {
    const raw = window.localStorage.getItem(videoDurationStorageKey(projectId, instanceId))
    if (!raw) return null
    const parsed = Number(raw)
    return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : null
  } catch {
    return null
  }
}

export function loadVideoDurationMap(projectId: string, instanceIds: string[]) {
  const out: Record<string, number> = {}
  for (const instanceId of instanceIds) {
    const durationMs = loadVideoDurationMs(projectId, instanceId)
    if (durationMs !== null) {
      out[instanceId] = durationMs
    }
  }
  return out
}

export function saveVideoDurationMs(projectId: string, instanceId: string, durationMs: number) {
  if (typeof window === "undefined") return
  try {
    if (!Number.isFinite(durationMs) || durationMs <= 0) {
      window.localStorage.removeItem(videoDurationStorageKey(projectId, instanceId))
      return
    }
    window.localStorage.setItem(videoDurationStorageKey(projectId, instanceId), String(Math.floor(durationMs)))
  } catch {
    // Ignore browser storage failures and keep playback working.
  }
}

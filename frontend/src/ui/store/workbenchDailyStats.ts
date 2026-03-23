type DailyWorkbenchStats = {
  playbackMs: number
}

const STORAGE_PREFIX = "plm-workbench-daily-stats:"

function storageKey(projectId: string, dateKey: string) {
  return `${STORAGE_PREFIX}${projectId}:${dateKey}`
}

export function getLocalDateKey(date = new Date()) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

export function loadDailyWorkbenchStats(projectId: string, dateKey = getLocalDateKey()): DailyWorkbenchStats {
  if (!projectId || typeof window === "undefined") return { playbackMs: 0 }
  try {
    const raw = window.localStorage.getItem(storageKey(projectId, dateKey))
    if (!raw) return { playbackMs: 0 }
    const parsed = JSON.parse(raw) as Partial<DailyWorkbenchStats>
    return {
      playbackMs: typeof parsed.playbackMs === "number" && Number.isFinite(parsed.playbackMs) ? parsed.playbackMs : 0,
    }
  } catch {
    return { playbackMs: 0 }
  }
}

export function saveDailyWorkbenchStats(projectId: string, stats: DailyWorkbenchStats, dateKey = getLocalDateKey()) {
  if (!projectId || typeof window === "undefined") return
  try {
    window.localStorage.setItem(storageKey(projectId, dateKey), JSON.stringify(stats))
  } catch {
    // Ignore storage failures and keep the workbench usable.
  }
}

export function addDailyPlaybackMs(projectId: string, deltaMs: number, dateKey = getLocalDateKey()) {
  if (!projectId || !Number.isFinite(deltaMs) || deltaMs <= 0) return
  const current = loadDailyWorkbenchStats(projectId, dateKey)
  saveDailyWorkbenchStats(
    projectId,
    {
      playbackMs: current.playbackMs + deltaMs,
    },
    dateKey,
  )
}

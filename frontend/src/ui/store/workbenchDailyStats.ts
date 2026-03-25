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

export function loadDailyPlaybackTotalsByDate(projectIds: string[]) {
  if (typeof window === "undefined" || projectIds.length === 0) return {} as Record<string, number>

  const projectIdSet = new Set(projectIds.filter(Boolean))
  const totalsByDate: Record<string, number> = {}

  for (let index = 0; index < window.localStorage.length; index += 1) {
    const key = window.localStorage.key(index)
    if (!key || !key.startsWith(STORAGE_PREFIX)) continue

    const remainder = key.slice(STORAGE_PREFIX.length)
    const separatorIndex = remainder.lastIndexOf(":")
    if (separatorIndex <= 0 || separatorIndex >= remainder.length - 1) continue

    const projectId = remainder.slice(0, separatorIndex)
    const dateKey = remainder.slice(separatorIndex + 1)
    if (!projectIdSet.has(projectId)) continue

    const playbackMs = loadDailyWorkbenchStats(projectId, dateKey).playbackMs
    if (playbackMs <= 0) continue
    totalsByDate[dateKey] = (totalsByDate[dateKey] ?? 0) + playbackMs
  }

  return totalsByDate
}

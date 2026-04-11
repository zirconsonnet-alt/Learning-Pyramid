export type DailyStudyPresenceStats = {
  presenceMs: number
}

const STORAGE_PREFIX = "plm-study-presence:"
const ACTIVE_WINDOW_MS = 20 * 60_000
const HEARTBEAT_MS = 5_000

const EMPTY_DAILY_STUDY_PRESENCE_STATS: DailyStudyPresenceStats = {
  presenceMs: 0,
}

function storageKey(projectId: string, dateKey: string) {
  return `${STORAGE_PREFIX}${projectId}:${dateKey}`
}

function getLocalDateKey(date = new Date()) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

function getLocalDayStartMs(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value)
}

function normalizeMs(value: unknown) {
  return isFiniteNumber(value) ? Math.max(0, Math.floor(value)) : 0
}

function loadDailyStudyPresenceStats(projectId: string, dateKey = getLocalDateKey()): DailyStudyPresenceStats {
  if (!projectId || typeof window === "undefined") return { ...EMPTY_DAILY_STUDY_PRESENCE_STATS }
  try {
    const raw = window.localStorage.getItem(storageKey(projectId, dateKey))
    const parsed = raw ? JSON.parse(raw) : null
    return {
      presenceMs: normalizeMs(parsed?.presenceMs),
    }
  } catch {
    return { ...EMPTY_DAILY_STUDY_PRESENCE_STATS }
  }
}

function saveDailyStudyPresenceStats(projectId: string, stats: DailyStudyPresenceStats, dateKey = getLocalDateKey()) {
  if (!projectId || typeof window === "undefined") return
  try {
    window.localStorage.setItem(
      storageKey(projectId, dateKey),
      JSON.stringify({
        presenceMs: normalizeMs(stats.presenceMs),
      }),
    )
  } catch {
    // Ignore storage failures; presence is an observability signal, not critical data.
  }
}

function addStudyPresenceMs(projectId: string, deltaMs: number, atMs = Date.now()) {
  if (!projectId || !Number.isFinite(deltaMs) || deltaMs <= 0) return
  const date = new Date(atMs)
  const dateKey = getLocalDateKey(date)
  const dayStartMs = getLocalDayStartMs(date)
  const offsetMs = atMs - dayStartMs
  const safeDeltaMs = Math.min(deltaMs, Math.max(0, offsetMs))
  if (safeDeltaMs <= 0) return
  const current = loadDailyStudyPresenceStats(projectId, dateKey)
  saveDailyStudyPresenceStats(
    projectId,
    {
      presenceMs: current.presenceMs + safeDeltaMs,
    },
    dateKey,
  )
}

export function loadDailyProjectStudyPresence(projectId: string, dateKey = getLocalDateKey()) {
  return loadDailyStudyPresenceStats(projectId, dateKey)
}

export function loadDailyStudyPresenceTotalsByDate(projectIds: string[]) {
  if (typeof window === "undefined" || projectIds.length === 0) return {} as Record<string, DailyStudyPresenceStats>

  const projectIdSet = new Set(projectIds.filter(Boolean))
  const totalsByDate: Record<string, DailyStudyPresenceStats> = {}

  for (let index = 0; index < window.localStorage.length; index += 1) {
    const key = window.localStorage.key(index)
    if (!key || !key.startsWith(STORAGE_PREFIX)) continue

    const remainder = key.slice(STORAGE_PREFIX.length)
    const separatorIndex = remainder.lastIndexOf(":")
    if (separatorIndex <= 0 || separatorIndex >= remainder.length - 1) continue

    const projectId = remainder.slice(0, separatorIndex)
    const dateKey = remainder.slice(separatorIndex + 1)
    if (!projectIdSet.has(projectId)) continue

    const stats = loadDailyStudyPresenceStats(projectId, dateKey)
    const current = totalsByDate[dateKey] ?? { ...EMPTY_DAILY_STUDY_PRESENCE_STATS }
    totalsByDate[dateKey] = {
      presenceMs: current.presenceMs + stats.presenceMs,
    }
  }

  return totalsByDate
}

export function createStudyPresenceTracker(projectId: string) {
  let lastInteractionAtMs = Date.now()
  let lastTickAtMs = Date.now()
  let timer: number | null = null

  function touch() {
    lastInteractionAtMs = Date.now()
  }

  function tick() {
    const now = Date.now()
    const deltaMs = Math.max(0, Math.min(now - lastTickAtMs, HEARTBEAT_MS))
    lastTickAtMs = now
    if (typeof document !== "undefined" && document.visibilityState !== "visible") return
    if (now - lastInteractionAtMs > ACTIVE_WINDOW_MS) return
    addStudyPresenceMs(projectId, deltaMs, now)
  }

  function start() {
    touch()
    lastTickAtMs = Date.now()
    timer = window.setInterval(tick, HEARTBEAT_MS)
  }

  function stop() {
    tick()
    if (timer !== null) {
      window.clearInterval(timer)
      timer = null
    }
  }

  return {
    start,
    stop,
    touch,
  }
}

export function clearAllStudyPresenceStats() {
  if (typeof window === "undefined") return
  const keys: string[] = []
  for (let index = 0; index < window.localStorage.length; index += 1) {
    const key = window.localStorage.key(index)
    if (key?.startsWith(STORAGE_PREFIX)) keys.push(key)
  }
  for (const key of keys) {
    window.localStorage.removeItem(key)
  }
}

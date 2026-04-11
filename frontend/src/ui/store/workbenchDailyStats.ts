export type StudyActivityKind = "watch" | "compose" | "review" | "qa"

export type DailyWorkbenchStats = {
  effectiveMs: number
  watchMs: number
  composeMs: number
  reviewMs: number
  qaMs: number
}

export type StudyMetricRange = {
  startMs: number
  endMs: number
}

export type DailyStudyMetricEntry = DailyWorkbenchStats & {
  projectId: string
  dateKey: string
  effectiveRanges: StudyMetricRange[]
  watchRanges: StudyMetricRange[]
  composeRanges: StudyMetricRange[]
  reviewRanges: StudyMetricRange[]
  qaRanges: StudyMetricRange[]
  updatedAt?: string
}

type DailyWorkbenchStatsStorage = DailyWorkbenchStats & {
  effectiveRanges: Array<[number, number]>
  watchRanges: Array<[number, number]>
  composeRanges: Array<[number, number]>
  reviewRanges: Array<[number, number]>
  qaRanges: Array<[number, number]>
}

const STORAGE_PREFIX = "plm-workbench-daily-stats:"

const EMPTY_DAILY_WORKBENCH_STATS: DailyWorkbenchStats = {
  effectiveMs: 0,
  watchMs: 0,
  composeMs: 0,
  reviewMs: 0,
  qaMs: 0,
}

function emptyStoredDailyWorkbenchStats(): DailyWorkbenchStatsStorage {
  return {
    ...EMPTY_DAILY_WORKBENCH_STATS,
    effectiveRanges: [],
    watchRanges: [],
    composeRanges: [],
    reviewRanges: [],
    qaRanges: [],
  }
}

function storageKey(projectId: string, dateKey: string) {
  return `${STORAGE_PREFIX}${projectId}:${dateKey}`
}

function toRangeEntries(ranges: Array<[number, number]>): StudyMetricRange[] {
  return ranges.map(([startMs, endMs]) => ({ startMs, endMs }))
}

function fromRangeEntries(ranges: StudyMetricRange[] | undefined): Array<[number, number]> {
  return Array.isArray(ranges)
    ? ranges
        .map((item) => {
          const startMs = Number(item?.startMs)
          const endMs = Number(item?.endMs)
          return Number.isFinite(startMs) && Number.isFinite(endMs) && endMs > startMs ? ([startMs, endMs] as [number, number]) : null
        })
        .filter((item): item is [number, number] => Boolean(item))
    : []
}

function isDateKeyWithinRange(dateKey: string, dateFrom?: string, dateTo?: string) {
  if (dateFrom && dateKey < dateFrom) return false
  if (dateTo && dateKey > dateTo) return false
  return true
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value)
}

function sumRanges(ranges: Array<[number, number]>) {
  return ranges.reduce((sum, [startMs, endMs]) => sum + Math.max(0, endMs - startMs), 0)
}

function normalizeRanges(ranges: Array<[number, number]>) {
  const sorted = ranges
    .filter(([startMs, endMs]) => isFiniteNumber(startMs) && isFiniteNumber(endMs) && endMs > startMs)
    .sort((left, right) => left[0] - right[0])

  if (sorted.length <= 1) return sorted

  const merged: Array<[number, number]> = [sorted[0]!]
  for (const [startMs, endMs] of sorted.slice(1)) {
    const last = merged[merged.length - 1]!
    if (startMs <= last[1]) {
      last[1] = Math.max(last[1], endMs)
      continue
    }
    merged.push([startMs, endMs])
  }
  return merged
}

function toStoredDailyWorkbenchStats(parsed: unknown): DailyWorkbenchStatsStorage {
  if (!parsed || typeof parsed !== "object") return emptyStoredDailyWorkbenchStats()

  const candidate = parsed as Partial<
    DailyWorkbenchStatsStorage & {
      playbackMs?: number
      effectiveRanges?: unknown
    }
  >

  const parseRanges = (value: unknown) =>
    normalizeRanges(
      Array.isArray(value)
        ? value
            .map((item) => {
              if (!Array.isArray(item) || item.length < 2) return null
              const startMs = Number(item[0])
              const endMs = Number(item[1])
              return Number.isFinite(startMs) && Number.isFinite(endMs) && endMs > startMs ? ([startMs, endMs] as [number, number]) : null
            })
            .filter((item): item is [number, number] => Boolean(item))
        : [],
    )

  const legacyPlaybackMs = isFiniteNumber(candidate.playbackMs) ? candidate.playbackMs : 0
  const watchMs = isFiniteNumber(candidate.watchMs) ? candidate.watchMs : legacyPlaybackMs
  const composeMs = isFiniteNumber(candidate.composeMs) ? candidate.composeMs : 0
  const reviewMs = isFiniteNumber(candidate.reviewMs) ? candidate.reviewMs : 0
  const qaMs = isFiniteNumber(candidate.qaMs) ? candidate.qaMs : 0
  const effectiveRanges = parseRanges(candidate.effectiveRanges)
  const watchRanges = parseRanges((candidate as { watchRanges?: unknown }).watchRanges)
  const composeRanges = parseRanges((candidate as { composeRanges?: unknown }).composeRanges)
  const reviewRanges = parseRanges((candidate as { reviewRanges?: unknown }).reviewRanges)
  const qaRanges = parseRanges((candidate as { qaRanges?: unknown }).qaRanges)
  const computedEffectiveMs =
    effectiveRanges.length > 0
      ? sumRanges(effectiveRanges)
      : isFiniteNumber(candidate.effectiveMs)
        ? candidate.effectiveMs
        : legacyPlaybackMs

  return {
    effectiveMs: computedEffectiveMs,
    watchMs,
    composeMs,
    reviewMs,
    qaMs,
    effectiveRanges,
    watchRanges,
    composeRanges,
    reviewRanges,
    qaRanges,
  }
}

function loadStoredDailyWorkbenchStats(projectId: string, dateKey = getLocalDateKey()): DailyWorkbenchStatsStorage {
  if (!projectId || typeof window === "undefined") return emptyStoredDailyWorkbenchStats()
  try {
    const raw = window.localStorage.getItem(storageKey(projectId, dateKey))
    if (!raw) return emptyStoredDailyWorkbenchStats()
    return toStoredDailyWorkbenchStats(JSON.parse(raw))
  } catch {
    return emptyStoredDailyWorkbenchStats()
  }
}

function saveStoredDailyWorkbenchStats(projectId: string, stats: DailyWorkbenchStatsStorage, dateKey = getLocalDateKey()) {
  if (!projectId || typeof window === "undefined") return
  try {
    window.localStorage.setItem(
      storageKey(projectId, dateKey),
      JSON.stringify({
        effectiveMs: Math.max(0, Math.floor(stats.effectiveMs)),
        watchMs: Math.max(0, Math.floor(stats.watchMs)),
        composeMs: Math.max(0, Math.floor(stats.composeMs)),
        reviewMs: Math.max(0, Math.floor(stats.reviewMs)),
        qaMs: Math.max(0, Math.floor(stats.qaMs)),
        effectiveRanges: normalizeRanges(stats.effectiveRanges),
        watchRanges: normalizeRanges(stats.watchRanges),
        composeRanges: normalizeRanges(stats.composeRanges),
        reviewRanges: normalizeRanges(stats.reviewRanges),
        qaRanges: normalizeRanges(stats.qaRanges),
      } satisfies DailyWorkbenchStatsStorage),
    )
  } catch {
    // Ignore storage failures and keep the workbench usable.
  }
}

function resolveActivityField(kind: StudyActivityKind): keyof DailyWorkbenchStats {
  if (kind === "compose") return "composeMs"
  if (kind === "review") return "reviewMs"
  if (kind === "qa") return "qaMs"
  return "watchMs"
}

function resolveActivityRangesField(kind: StudyActivityKind): keyof Pick<
  DailyWorkbenchStatsStorage,
  "watchRanges" | "composeRanges" | "reviewRanges" | "qaRanges"
> {
  if (kind === "compose") return "composeRanges"
  if (kind === "review") return "reviewRanges"
  if (kind === "qa") return "qaRanges"
  return "watchRanges"
}

function getLocalDayStartMs(date: Date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
}

function splitRangeByLocalDate(startAtMs: number, endAtMs: number) {
  const segments: Array<{ dateKey: string; startOffsetMs: number; endOffsetMs: number }> = []
  let cursor = startAtMs

  while (cursor < endAtMs) {
    const currentDate = new Date(cursor)
    const dateKey = getLocalDateKey(currentDate)
    const dayStartMs = getLocalDayStartMs(currentDate)
    const nextDayStartMs = new Date(currentDate.getFullYear(), currentDate.getMonth(), currentDate.getDate() + 1).getTime()
    const segmentEndMs = Math.min(endAtMs, nextDayStartMs)
    segments.push({
      dateKey,
      startOffsetMs: cursor - dayStartMs,
      endOffsetMs: segmentEndMs - dayStartMs,
    })
    cursor = segmentEndMs
  }

  return segments
}

export function getLocalDateKey(date = new Date()) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

export function loadDailyWorkbenchStats(projectId: string, dateKey = getLocalDateKey()): DailyWorkbenchStats {
  const stored = loadStoredDailyWorkbenchStats(projectId, dateKey)
  return {
    effectiveMs: stored.effectiveMs,
    watchMs: stored.watchMs,
    composeMs: stored.composeMs,
    reviewMs: stored.reviewMs,
    qaMs: stored.qaMs,
  }
}

export function saveDailyWorkbenchStats(projectId: string, stats: DailyWorkbenchStats, dateKey = getLocalDateKey()) {
  const current = loadStoredDailyWorkbenchStats(projectId, dateKey)
  saveStoredDailyWorkbenchStats(
    projectId,
    {
      ...current,
      effectiveMs: Math.max(0, Math.floor(stats.effectiveMs)),
      watchMs: Math.max(0, Math.floor(stats.watchMs)),
      composeMs: Math.max(0, Math.floor(stats.composeMs)),
      reviewMs: Math.max(0, Math.floor(stats.reviewMs)),
      qaMs: Math.max(0, Math.floor(stats.qaMs)),
    },
    dateKey,
  )
}

export function recordStudyActivity(projectId: string, kind: StudyActivityKind, startAtMs: number, endAtMs: number) {
  if (!projectId) return
  if (!Number.isFinite(startAtMs) || !Number.isFinite(endAtMs) || endAtMs <= startAtMs) return

  const activityField = resolveActivityField(kind)
  const activityRangesField = resolveActivityRangesField(kind)
  for (const segment of splitRangeByLocalDate(startAtMs, endAtMs)) {
    if (segment.endOffsetMs <= segment.startOffsetMs) continue

    const current = loadStoredDailyWorkbenchStats(projectId, segment.dateKey)
    const nextActivityRanges = normalizeRanges([...current[activityRangesField], [segment.startOffsetMs, segment.endOffsetMs]])
    const addedActivityMs = sumRanges(nextActivityRanges) - sumRanges(current[activityRangesField])
    const effectiveRanges = normalizeRanges([...current.effectiveRanges, [segment.startOffsetMs, segment.endOffsetMs]])
    const addedEffectiveMs = sumRanges(effectiveRanges) - sumRanges(current.effectiveRanges)
    saveStoredDailyWorkbenchStats(
      projectId,
      {
        ...current,
        [activityField]: current[activityField] + addedActivityMs,
        [activityRangesField]: nextActivityRanges,
        effectiveRanges,
        effectiveMs: current.effectiveMs + addedEffectiveMs,
      },
      segment.dateKey,
    )
  }
}

export function touchDailyStudyActivity(projectId: string, kind: StudyActivityKind, windowMs: number, atMs = Date.now()) {
  if (!projectId || !Number.isFinite(windowMs) || windowMs <= 0) return
  const startAtMs = Number.isFinite(atMs) ? atMs : Date.now()
  recordStudyActivity(projectId, kind, startAtMs, startAtMs + windowMs)
}

export function addDailyPlaybackMs(projectId: string, deltaMs: number) {
  if (!projectId || !Number.isFinite(deltaMs) || deltaMs <= 0) return
  const endAtMs = Date.now()
  recordStudyActivity(projectId, "watch", endAtMs - deltaMs, endAtMs)
}

export function loadDailyStudyTotalsByDate(projectIds: string[]) {
  if (typeof window === "undefined" || projectIds.length === 0) return {} as Record<string, DailyWorkbenchStats>

  const projectIdSet = new Set(projectIds.filter(Boolean))
  const totalsByDate: Record<string, DailyWorkbenchStats> = {}

  for (let index = 0; index < window.localStorage.length; index += 1) {
    const key = window.localStorage.key(index)
    if (!key || !key.startsWith(STORAGE_PREFIX)) continue

    const remainder = key.slice(STORAGE_PREFIX.length)
    const separatorIndex = remainder.lastIndexOf(":")
    if (separatorIndex <= 0 || separatorIndex >= remainder.length - 1) continue

    const projectId = remainder.slice(0, separatorIndex)
    const dateKey = remainder.slice(separatorIndex + 1)
    if (!projectIdSet.has(projectId)) continue

    const stats = loadDailyWorkbenchStats(projectId, dateKey)
    if (stats.effectiveMs <= 0 && stats.watchMs <= 0 && stats.composeMs <= 0 && stats.reviewMs <= 0 && stats.qaMs <= 0) continue
    const current = totalsByDate[dateKey] ?? { ...EMPTY_DAILY_WORKBENCH_STATS }
    totalsByDate[dateKey] = {
      effectiveMs: current.effectiveMs + stats.effectiveMs,
      watchMs: current.watchMs + stats.watchMs,
      composeMs: current.composeMs + stats.composeMs,
      reviewMs: current.reviewMs + stats.reviewMs,
      qaMs: current.qaMs + stats.qaMs,
    }
  }

  return totalsByDate
}

export function listDailyStudyMetricEntries(
  projectIds: string[],
  options?: {
    dateFrom?: string
    dateTo?: string
  },
) {
  if (typeof window === "undefined" || projectIds.length === 0) return [] as DailyStudyMetricEntry[]

  const projectIdSet = new Set(projectIds.filter(Boolean))
  const entries: DailyStudyMetricEntry[] = []

  for (let index = 0; index < window.localStorage.length; index += 1) {
    const key = window.localStorage.key(index)
    if (!key || !key.startsWith(STORAGE_PREFIX)) continue

    const remainder = key.slice(STORAGE_PREFIX.length)
    const separatorIndex = remainder.lastIndexOf(":")
    if (separatorIndex <= 0 || separatorIndex >= remainder.length - 1) continue

    const projectId = remainder.slice(0, separatorIndex)
    const dateKey = remainder.slice(separatorIndex + 1)
    if (!projectIdSet.has(projectId) || !isDateKeyWithinRange(dateKey, options?.dateFrom, options?.dateTo)) continue

    const stored = loadStoredDailyWorkbenchStats(projectId, dateKey)
    if (stored.effectiveMs <= 0 && stored.watchMs <= 0 && stored.composeMs <= 0 && stored.reviewMs <= 0 && stored.qaMs <= 0) continue

    entries.push({
      projectId,
      dateKey,
      effectiveMs: stored.effectiveMs,
      watchMs: stored.watchMs,
      composeMs: stored.composeMs,
      reviewMs: stored.reviewMs,
      qaMs: stored.qaMs,
      effectiveRanges: toRangeEntries(stored.effectiveRanges),
      watchRanges: toRangeEntries(stored.watchRanges),
      composeRanges: toRangeEntries(stored.composeRanges),
      reviewRanges: toRangeEntries(stored.reviewRanges),
      qaRanges: toRangeEntries(stored.qaRanges),
    })
  }

  return entries.sort((left, right) => {
    if (left.dateKey !== right.dateKey) return left.dateKey.localeCompare(right.dateKey)
    return left.projectId.localeCompare(right.projectId)
  })
}

export function mergeDailyStudyMetricEntries(entries: DailyStudyMetricEntry[]) {
  for (const entry of entries) {
    if (!entry.projectId || !entry.dateKey) continue
    saveStoredDailyWorkbenchStats(
      entry.projectId,
      toStoredDailyWorkbenchStats({
        effectiveMs: entry.effectiveMs,
        watchMs: entry.watchMs,
        composeMs: entry.composeMs,
        reviewMs: entry.reviewMs,
        qaMs: entry.qaMs,
        effectiveRanges: fromRangeEntries(entry.effectiveRanges),
        watchRanges: fromRangeEntries(entry.watchRanges),
        composeRanges: fromRangeEntries(entry.composeRanges),
        reviewRanges: fromRangeEntries(entry.reviewRanges),
        qaRanges: fromRangeEntries(entry.qaRanges),
      }),
      entry.dateKey,
    )
  }
}

export function clearAllDailyWorkbenchStats() {
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

export function loadDailyPlaybackTotalsByDate(projectIds: string[]) {
  const totalsByDate = loadDailyStudyTotalsByDate(projectIds)
  return Object.fromEntries(Object.entries(totalsByDate).map(([dateKey, stats]) => [dateKey, stats.watchMs])) as Record<string, number>
}

export type VideoWatchCoverageRange = {
  startMs: number
  endMs: number
}

type StoredVideoWatchCoverage = {
  watchedMs: number
  ranges: Array<[number, number]>
}

const VIDEO_WATCH_COVERAGE_STORAGE_PREFIX = "plm-video-watch-coverage:"

function storageKey(projectId: string, instanceId: string) {
  return `${VIDEO_WATCH_COVERAGE_STORAGE_PREFIX}${projectId}:${instanceId}`
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value)
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

function sumRanges(ranges: Array<[number, number]>) {
  return ranges.reduce((sum, [startMs, endMs]) => sum + Math.max(0, endMs - startMs), 0)
}

function clampRangeToDuration(range: [number, number], durationMs?: number | null): [number, number] | null {
  const [startMs, endMs] = range
  const maxMs = isFiniteNumber(durationMs) && durationMs > 0 ? Math.floor(durationMs) : null
  const normalizedStartMs = Math.max(0, Math.floor(startMs))
  const normalizedEndMs = Math.max(0, Math.floor(endMs))
  if (normalizedEndMs <= normalizedStartMs) return null
  if (maxMs === null) return [normalizedStartMs, normalizedEndMs]
  const clampedStartMs = Math.min(normalizedStartMs, maxMs)
  const clampedEndMs = Math.min(normalizedEndMs, maxMs)
  return clampedEndMs > clampedStartMs ? [clampedStartMs, clampedEndMs] : null
}

function emptyStoredVideoWatchCoverage(): StoredVideoWatchCoverage {
  return {
    watchedMs: 0,
    ranges: [],
  }
}

function parseStoredVideoWatchCoverage(parsed: unknown, durationMs?: number | null): StoredVideoWatchCoverage {
  if (!parsed || typeof parsed !== "object") return emptyStoredVideoWatchCoverage()

  const candidate = parsed as Partial<StoredVideoWatchCoverage>
  const ranges = normalizeRanges(
    Array.isArray(candidate.ranges)
      ? candidate.ranges
          .map((item) => {
            if (!Array.isArray(item) || item.length < 2) return null
            return clampRangeToDuration([Number(item[0]), Number(item[1])], durationMs)
          })
          .filter((item): item is [number, number] => Boolean(item))
      : [],
  )

  return {
    watchedMs: sumRanges(ranges),
    ranges,
  }
}

function loadStoredVideoWatchCoverage(projectId: string, instanceId: string, durationMs?: number | null) {
  if (!projectId || !instanceId || typeof window === "undefined") return emptyStoredVideoWatchCoverage()
  try {
    const raw = window.localStorage.getItem(storageKey(projectId, instanceId))
    if (!raw) return emptyStoredVideoWatchCoverage()
    return parseStoredVideoWatchCoverage(JSON.parse(raw), durationMs)
  } catch {
    return emptyStoredVideoWatchCoverage()
  }
}

function saveStoredVideoWatchCoverage(projectId: string, instanceId: string, coverage: StoredVideoWatchCoverage) {
  if (!projectId || !instanceId || typeof window === "undefined") return
  try {
    if (coverage.ranges.length === 0 || coverage.watchedMs <= 0) {
      window.localStorage.removeItem(storageKey(projectId, instanceId))
      return
    }
    window.localStorage.setItem(
      storageKey(projectId, instanceId),
      JSON.stringify({
        watchedMs: Math.max(0, Math.floor(coverage.watchedMs)),
        ranges: normalizeRanges(coverage.ranges),
      } satisfies StoredVideoWatchCoverage),
    )
  } catch {
    // Ignore browser storage failures and keep playback responsive.
  }
}

export function recordVideoWatchCoverageRange(
  projectId: string,
  instanceId: string,
  startMs: number,
  endMs: number,
  durationMs?: number | null,
) {
  const clampedRange = clampRangeToDuration([startMs, endMs], durationMs)
  if (!projectId || !instanceId || !clampedRange) return 0

  const current = loadStoredVideoWatchCoverage(projectId, instanceId, durationMs)
  const nextRanges = normalizeRanges([...current.ranges, clampedRange])
  const nextWatchedMs = sumRanges(nextRanges)
  saveStoredVideoWatchCoverage(projectId, instanceId, {
    watchedMs: nextWatchedMs,
    ranges: nextRanges,
  })
  return nextWatchedMs
}

export function loadVideoWatchCoverage(projectId: string, instanceId: string, durationMs?: number | null) {
  const stored = loadStoredVideoWatchCoverage(projectId, instanceId, durationMs)
  return {
    watchedMs: stored.watchedMs,
    ranges: stored.ranges.map(([startMs, endMs]) => ({ startMs, endMs })) as VideoWatchCoverageRange[],
  }
}

export function loadVideoWatchCoverageMap(
  projectId: string,
  instanceIds: string[],
  durationByInstanceId?: Record<string, number | null | undefined>,
) {
  const out: Record<string, number> = {}
  for (const instanceId of instanceIds) {
    const durationMs = durationByInstanceId?.[instanceId]
    const watchedMs = loadStoredVideoWatchCoverage(projectId, instanceId, durationMs).watchedMs
    if (watchedMs > 0) out[instanceId] = watchedMs
  }
  return out
}

export function clearAllVideoWatchCoverageState() {
  if (typeof window === "undefined") return
  try {
    const keys: string[] = []
    for (let index = 0; index < window.localStorage.length; index += 1) {
      const key = window.localStorage.key(index)
      if (key?.startsWith(VIDEO_WATCH_COVERAGE_STORAGE_PREFIX)) {
        keys.push(key)
      }
    }
    for (const key of keys) {
      window.localStorage.removeItem(key)
    }
  } catch {
    // Ignore browser storage failures and keep playback responsive.
  }
}

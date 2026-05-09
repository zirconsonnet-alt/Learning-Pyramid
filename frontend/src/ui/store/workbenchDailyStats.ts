export type StudyActivityKind = "video" | "recallEntry" | "review" | "aiQa"

export type StudyMetricRange = {
  startMs: number
  endMs: number
}

export type StudyProjectReference = {
  subjectId: string
  projectId: string
}

export type DailyWorkbenchStats = {
  schemaVersion: number
  webPresenceMs: number
  videoMs: number
  recallEntryMs: number
  reviewMs: number
  aiQaMs: number
  distractionMs: number
  isPartitionComplete: boolean
  effectiveMs: number
  watchMs: number
  composeMs: number
  qaMs: number
}

export type DailyStudyMetricEntry = DailyWorkbenchStats & {
  projectId: string
  projectRef?: StudyProjectReference | null
  dateKey: string
  presenceRanges: StudyMetricRange[]
  videoRanges: StudyMetricRange[]
  recallEntryRanges: StudyMetricRange[]
  reviewRanges: StudyMetricRange[]
  aiQaRanges: StudyMetricRange[]
  effectiveRanges: StudyMetricRange[]
  watchRanges: StudyMetricRange[]
  composeRanges: StudyMetricRange[]
  qaRanges: StudyMetricRange[]
  updatedAt?: string
}

export type PomodoroSegmentMetricSummary = DailyWorkbenchStats & {
  projectId: string | null
  projectRef: StudyProjectReference | null
  dateKey: string
  planId: string
  planIndex: number
  pomodoroIndex: number
  scheduledStartAtMs: number
  scheduledEndAtMs: number
  scheduledFocusMs: number
  absenceMs: number
  activeLearningMs: number
  attendanceRate: number
  effectiveLearningRate: number
  status: "not-started" | "in-progress" | "completed"
}

type StoredRangeKey = "presenceRanges" | "videoRanges" | "recallEntryRanges" | "reviewRanges" | "aiQaRanges"

type DailyWorkbenchStatsStorage = {
  schemaVersion: number
  presenceRanges: Array<[number, number]>
  videoRanges: Array<[number, number]>
  recallEntryRanges: Array<[number, number]>
  reviewRanges: Array<[number, number]>
  aiQaRanges: Array<[number, number]>
  effectiveMs: number
  watchMs: number
  composeMs: number
  reviewMs: number
  qaMs: number
  effectiveRanges: Array<[number, number]>
  watchRanges: Array<[number, number]>
  composeRanges: Array<[number, number]>
  qaRanges: Array<[number, number]>
}

const STORAGE_PREFIX = "plm-workbench-daily-stats:"
const CURRENT_SCHEMA_VERSION = 2

const EMPTY_DAILY_WORKBENCH_STATS: DailyWorkbenchStats = {
  schemaVersion: CURRENT_SCHEMA_VERSION,
  webPresenceMs: 0,
  videoMs: 0,
  recallEntryMs: 0,
  reviewMs: 0,
  aiQaMs: 0,
  distractionMs: 0,
  isPartitionComplete: true,
  effectiveMs: 0,
  watchMs: 0,
  composeMs: 0,
  qaMs: 0,
}

function emptyStoredDailyWorkbenchStats(): DailyWorkbenchStatsStorage {
  return {
    schemaVersion: CURRENT_SCHEMA_VERSION,
    presenceRanges: [],
    videoRanges: [],
    recallEntryRanges: [],
    reviewRanges: [],
    aiQaRanges: [],
    effectiveMs: 0,
    watchMs: 0,
    composeMs: 0,
    reviewMs: 0,
    qaMs: 0,
    effectiveRanges: [],
    watchRanges: [],
    composeRanges: [],
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

function offsetRangesByDay(ranges: Array<[number, number]>, dayStartMs: number) {
  return normalizeRanges(ranges.map(([startMs, endMs]) => [dayStartMs + startMs, dayStartMs + endMs]))
}

function isDateKeyWithinRange(dateKey: string, dateFrom?: string, dateTo?: string) {
  if (dateFrom && dateKey < dateFrom) return false
  if (dateTo && dateKey > dateTo) return false
  return true
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value)
}

function normalizeMs(value: unknown) {
  return isFiniteNumber(value) ? Math.max(0, Math.floor(value)) : 0
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

function subtractRanges(ranges: Array<[number, number]>, subtracting: Array<[number, number]>) {
  let remaining = normalizeRanges(ranges)
  for (const [removeStartMs, removeEndMs] of normalizeRanges(subtracting)) {
    const next: Array<[number, number]> = []
    for (const [startMs, endMs] of remaining) {
      if (removeEndMs <= startMs || removeStartMs >= endMs) {
        next.push([startMs, endMs])
        continue
      }
      if (removeStartMs > startMs) next.push([startMs, removeStartMs])
      if (removeEndMs < endMs) next.push([removeEndMs, endMs])
    }
    remaining = next
  }
  return remaining
}

function intersectRanges(leftRanges: Array<[number, number]>, rightRanges: Array<[number, number]>) {
  const left = normalizeRanges(leftRanges)
  const right = normalizeRanges(rightRanges)
  const result: Array<[number, number]> = []
  let leftIndex = 0
  let rightIndex = 0

  while (leftIndex < left.length && rightIndex < right.length) {
    const [leftStartMs, leftEndMs] = left[leftIndex]!
    const [rightStartMs, rightEndMs] = right[rightIndex]!
    const startMs = Math.max(leftStartMs, rightStartMs)
    const endMs = Math.min(leftEndMs, rightEndMs)
    if (endMs > startMs) result.push([startMs, endMs])
    if (leftEndMs < rightEndMs) {
      leftIndex += 1
    } else {
      rightIndex += 1
    }
  }

  return normalizeRanges(result)
}

function parseStoredRanges(value: unknown) {
  return normalizeRanges(
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
}

function toStoredDailyWorkbenchStats(parsed: unknown): DailyWorkbenchStatsStorage {
  if (!parsed || typeof parsed !== "object") return emptyStoredDailyWorkbenchStats()

  const candidate = parsed as Partial<
    DailyWorkbenchStatsStorage & {
      playbackMs?: number
      webPresenceMs?: number
      videoMs?: number
      recallEntryMs?: number
      aiQaMs?: number
    }
  >

  const legacyPlaybackMs = normalizeMs(candidate.playbackMs)
  const watchMs = normalizeMs(candidate.watchMs ?? candidate.videoMs ?? legacyPlaybackMs)
  const composeMs = normalizeMs(candidate.composeMs ?? candidate.recallEntryMs)
  const reviewMs = normalizeMs(candidate.reviewMs)
  const qaMs = normalizeMs(candidate.qaMs ?? candidate.aiQaMs)
  const presenceRanges = parseStoredRanges(candidate.presenceRanges)
  const videoRanges = parseStoredRanges(candidate.videoRanges ?? candidate.watchRanges)
  const recallEntryRanges = parseStoredRanges(candidate.recallEntryRanges ?? candidate.composeRanges)
  const reviewRanges = parseStoredRanges(candidate.reviewRanges)
  const aiQaRanges = parseStoredRanges(candidate.aiQaRanges ?? candidate.qaRanges)
  const effectiveRanges = parseStoredRanges(candidate.effectiveRanges)
  const watchRanges = parseStoredRanges(candidate.watchRanges ?? candidate.videoRanges)
  const composeRanges = parseStoredRanges(candidate.composeRanges ?? candidate.recallEntryRanges)
  const qaRanges = parseStoredRanges(candidate.qaRanges ?? candidate.aiQaRanges)
  const computedEffectiveMs =
    effectiveRanges.length > 0
      ? sumRanges(effectiveRanges)
      : normalizeMs(candidate.effectiveMs ?? legacyPlaybackMs)

  return {
    schemaVersion: normalizeMs(candidate.schemaVersion) || (presenceRanges.length > 0 ? CURRENT_SCHEMA_VERSION : 1),
    presenceRanges,
    videoRanges,
    recallEntryRanges,
    reviewRanges,
    aiQaRanges,
    effectiveMs: computedEffectiveMs,
    watchMs,
    composeMs,
    reviewMs,
    qaMs,
    effectiveRanges,
    watchRanges,
    composeRanges,
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
  const summary = summarizeWebMetricPartition(stats)
  try {
    window.localStorage.setItem(
      storageKey(projectId, dateKey),
      JSON.stringify({
        schemaVersion: CURRENT_SCHEMA_VERSION,
        webPresenceMs: summary.webPresenceMs,
        videoMs: summary.videoMs,
        recallEntryMs: summary.recallEntryMs,
        reviewMs: summary.reviewMs,
        aiQaMs: summary.aiQaMs,
        distractionMs: summary.distractionMs,
        isPartitionComplete: summary.isPartitionComplete,
        presenceRanges: normalizeRanges(stats.presenceRanges),
        videoRanges: normalizeRanges(stats.videoRanges),
        recallEntryRanges: normalizeRanges(stats.recallEntryRanges),
        reviewRanges: normalizeRanges(stats.reviewRanges),
        aiQaRanges: normalizeRanges(stats.aiQaRanges),
        effectiveMs: Math.max(0, Math.floor(summary.effectiveMs)),
        watchMs: Math.max(0, Math.floor(summary.watchMs)),
        composeMs: Math.max(0, Math.floor(summary.composeMs)),
        qaMs: Math.max(0, Math.floor(summary.qaMs)),
        effectiveRanges: normalizeRanges(stats.effectiveRanges),
        watchRanges: normalizeRanges(stats.watchRanges.length > 0 ? stats.watchRanges : stats.videoRanges),
        composeRanges: normalizeRanges(stats.composeRanges.length > 0 ? stats.composeRanges : stats.recallEntryRanges),
        qaRanges: normalizeRanges(stats.qaRanges.length > 0 ? stats.qaRanges : stats.aiQaRanges),
      }),
    )
  } catch {
    // Ignore storage failures and keep the workbench usable.
  }
}

function resolveActivityRangesField(kind: StudyActivityKind): StoredRangeKey {
  if (kind === "recallEntry") return "recallEntryRanges"
  if (kind === "review") return "reviewRanges"
  if (kind === "aiQa") return "aiQaRanges"
  return "videoRanges"
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

export function summarizeWebMetricPartition(stored: DailyWorkbenchStatsStorage): DailyWorkbenchStats {
  const presenceRanges = normalizeRanges(stored.presenceRanges)
  let unassignedPresenceRanges = presenceRanges
  const resolved = {
    aiQaRanges: [] as Array<[number, number]>,
    reviewRanges: [] as Array<[number, number]>,
    recallEntryRanges: [] as Array<[number, number]>,
    videoRanges: [] as Array<[number, number]>,
  }

  for (const key of ["aiQaRanges", "reviewRanges", "recallEntryRanges", "videoRanges"] as const) {
    resolved[key] = intersectRanges(stored[key], unassignedPresenceRanges)
    unassignedPresenceRanges = subtractRanges(unassignedPresenceRanges, resolved[key])
  }

  const summary = {
    videoMs: sumRanges(resolved.videoRanges),
    recallEntryMs: sumRanges(resolved.recallEntryRanges),
    reviewMs: sumRanges(resolved.reviewRanges),
    aiQaMs: sumRanges(resolved.aiQaRanges),
    distractionMs: sumRanges(unassignedPresenceRanges),
  }
  const activeLearningMs = summary.videoMs + summary.recallEntryMs + summary.reviewMs + summary.aiQaMs

  return {
    schemaVersion: CURRENT_SCHEMA_VERSION,
    webPresenceMs: summary.videoMs + summary.recallEntryMs + summary.reviewMs + summary.aiQaMs + summary.distractionMs,
    videoMs: summary.videoMs,
    recallEntryMs: summary.recallEntryMs,
    reviewMs: summary.reviewMs,
    aiQaMs: summary.aiQaMs,
    distractionMs: summary.distractionMs,
    isPartitionComplete: true,
    effectiveMs: activeLearningMs,
    watchMs: summary.videoMs,
    composeMs: summary.recallEntryMs,
    qaMs: summary.aiQaMs,
  }
}

export function loadDailyWebPresenceMetrics(projectId: string, dateKey = getLocalDateKey()): DailyWorkbenchStats {
  const stored = loadStoredDailyWorkbenchStats(projectId, dateKey)
  if (stored.presenceRanges.length === 0 && stored.schemaVersion < CURRENT_SCHEMA_VERSION) {
    return {
      ...EMPTY_DAILY_WORKBENCH_STATS,
      isPartitionComplete: false,
      effectiveMs: stored.effectiveMs,
      watchMs: stored.watchMs,
      composeMs: stored.composeMs,
      reviewMs: stored.reviewMs,
      qaMs: stored.qaMs,
    }
  }
  return summarizeWebMetricPartition(stored)
}

export function sliceDailyWebPresenceMetrics(projectId: string | null, startAtMs: number, endAtMs: number): DailyWorkbenchStats {
  if (!projectId || !Number.isFinite(startAtMs) || !Number.isFinite(endAtMs) || endAtMs <= startAtMs) {
    return { ...EMPTY_DAILY_WORKBENCH_STATS }
  }

  const sliced = emptyStoredDailyWorkbenchStats()
  for (const segment of splitRangeByLocalDate(startAtMs, endAtMs)) {
    const dayStartMs = new Date(`${segment.dateKey}T00:00:00`).getTime()
    const stored = loadStoredDailyWorkbenchStats(projectId, segment.dateKey)
    const sliceRange: Array<[number, number]> = [[dayStartMs + segment.startOffsetMs, dayStartMs + segment.endOffsetMs]]
    sliced.presenceRanges = normalizeRanges([
      ...sliced.presenceRanges,
      ...intersectRanges(offsetRangesByDay(stored.presenceRanges, dayStartMs), sliceRange).map(
        ([startMs, endMs]) => [startMs - startAtMs, endMs - startAtMs] as [number, number],
      ),
    ])
    sliced.videoRanges = normalizeRanges([
      ...sliced.videoRanges,
      ...intersectRanges(offsetRangesByDay(stored.videoRanges, dayStartMs), sliceRange).map(
        ([startMs, endMs]) => [startMs - startAtMs, endMs - startAtMs] as [number, number],
      ),
    ])
    sliced.recallEntryRanges = normalizeRanges([
      ...sliced.recallEntryRanges,
      ...intersectRanges(offsetRangesByDay(stored.recallEntryRanges, dayStartMs), sliceRange).map(
        ([startMs, endMs]) => [startMs - startAtMs, endMs - startAtMs] as [number, number],
      ),
    ])
    sliced.reviewRanges = normalizeRanges([
      ...sliced.reviewRanges,
      ...intersectRanges(offsetRangesByDay(stored.reviewRanges, dayStartMs), sliceRange).map(
        ([startMs, endMs]) => [startMs - startAtMs, endMs - startAtMs] as [number, number],
      ),
    ])
    sliced.aiQaRanges = normalizeRanges([
      ...sliced.aiQaRanges,
      ...intersectRanges(offsetRangesByDay(stored.aiQaRanges, dayStartMs), sliceRange).map(
        ([startMs, endMs]) => [startMs - startAtMs, endMs - startAtMs] as [number, number],
      ),
    ])
  }

  return summarizeWebMetricPartition(sliced)
}

export function loadPomodoroSegmentMetricSummary(params: {
  projectId: string | null
  projectRef?: StudyProjectReference | null
  dateKey: string
  planId: string
  planIndex: number
  pomodoroIndex: number
  scheduledStartAtMs: number
  scheduledEndAtMs: number
  now?: number
}): PomodoroSegmentMetricSummary {
  const scheduledFocusMs = Math.max(0, params.scheduledEndAtMs - params.scheduledStartAtMs)
  const now = Number.isFinite(params.now) ? Number(params.now) : Date.now()
  const effectiveEndAtMs = Math.min(params.scheduledEndAtMs, now)
  const status =
    now < params.scheduledStartAtMs ? "not-started" : now < params.scheduledEndAtMs ? "in-progress" : "completed"
  const metrics =
    effectiveEndAtMs > params.scheduledStartAtMs
      ? sliceDailyWebPresenceMetrics(params.projectId, params.scheduledStartAtMs, effectiveEndAtMs)
      : { ...EMPTY_DAILY_WORKBENCH_STATS }
  const absenceMs = Math.max(0, scheduledFocusMs - metrics.webPresenceMs)
  const activeLearningMs = metrics.videoMs + metrics.recallEntryMs + metrics.reviewMs + metrics.aiQaMs
  const attendanceRate = scheduledFocusMs > 0 ? metrics.webPresenceMs / scheduledFocusMs : 0
  const effectiveLearningRate = scheduledFocusMs > 0 ? activeLearningMs / scheduledFocusMs : 0

  return {
    ...metrics,
    projectId: params.projectId,
    projectRef: params.projectRef ?? null,
    dateKey: params.dateKey,
    planId: params.planId,
    planIndex: params.planIndex,
    pomodoroIndex: params.pomodoroIndex,
    scheduledStartAtMs: params.scheduledStartAtMs,
    scheduledEndAtMs: params.scheduledEndAtMs,
    scheduledFocusMs,
    absenceMs,
    activeLearningMs,
    attendanceRate,
    effectiveLearningRate,
    status,
  }
}

export function loadDailyWorkbenchStats(projectId: string, dateKey = getLocalDateKey()): DailyWorkbenchStats {
  return loadDailyWebPresenceMetrics(projectId, dateKey)
}

export function saveDailyWorkbenchStats(projectId: string, stats: DailyWorkbenchStats, dateKey = getLocalDateKey()) {
  const current = loadStoredDailyWorkbenchStats(projectId, dateKey)
  saveStoredDailyWorkbenchStats(
    projectId,
    {
      ...current,
      presenceRanges: current.presenceRanges,
      videoRanges: current.videoRanges,
      recallEntryRanges: current.recallEntryRanges,
      reviewRanges: current.reviewRanges,
      aiQaRanges: current.aiQaRanges,
      effectiveMs: Math.max(0, Math.floor(stats.effectiveMs)),
      watchMs: Math.max(0, Math.floor(stats.watchMs)),
      composeMs: Math.max(0, Math.floor(stats.composeMs)),
      reviewMs: Math.max(0, Math.floor(stats.reviewMs)),
      qaMs: Math.max(0, Math.floor(stats.qaMs)),
    },
    dateKey,
  )
}

export function recordWebPresenceActivity(projectId: string, startAtMs: number, endAtMs: number) {
  if (!projectId) return
  if (!Number.isFinite(startAtMs) || !Number.isFinite(endAtMs) || endAtMs <= startAtMs) return

  for (const segment of splitRangeByLocalDate(startAtMs, endAtMs)) {
    if (segment.endOffsetMs <= segment.startOffsetMs) continue

    const current = loadStoredDailyWorkbenchStats(projectId, segment.dateKey)
    saveStoredDailyWorkbenchStats(
      projectId,
      {
        ...current,
        presenceRanges: normalizeRanges([...current.presenceRanges, [segment.startOffsetMs, segment.endOffsetMs]]),
      },
      segment.dateKey,
    )
  }
}

export function recordStudyActivity(projectId: string, kind: StudyActivityKind, startAtMs: number, endAtMs: number) {
  if (!projectId) return
  if (!Number.isFinite(startAtMs) || !Number.isFinite(endAtMs) || endAtMs <= startAtMs) return

  const activityRangesField = resolveActivityRangesField(kind)
  for (const segment of splitRangeByLocalDate(startAtMs, endAtMs)) {
    if (segment.endOffsetMs <= segment.startOffsetMs) continue

    const current = loadStoredDailyWorkbenchStats(projectId, segment.dateKey)
    const nextActivityRanges = normalizeRanges([...current[activityRangesField], [segment.startOffsetMs, segment.endOffsetMs]])
    const effectiveRanges = normalizeRanges([...current.effectiveRanges, [segment.startOffsetMs, segment.endOffsetMs]])
    saveStoredDailyWorkbenchStats(
      projectId,
      {
        ...current,
        [activityRangesField]: nextActivityRanges,
        effectiveRanges,
        watchRanges: kind === "video" ? nextActivityRanges : current.watchRanges,
        composeRanges: kind === "recallEntry" ? nextActivityRanges : current.composeRanges,
        qaRanges: kind === "aiQa" ? nextActivityRanges : current.qaRanges,
      },
      segment.dateKey,
    )
  }
}

export function recordEffectiveStudyActivity(projectId: string, startAtMs: number, endAtMs: number) {
  if (!projectId) return
  if (!Number.isFinite(startAtMs) || !Number.isFinite(endAtMs) || endAtMs <= startAtMs) return

  for (const segment of splitRangeByLocalDate(startAtMs, endAtMs)) {
    if (segment.endOffsetMs <= segment.startOffsetMs) continue

    const current = loadStoredDailyWorkbenchStats(projectId, segment.dateKey)
    saveStoredDailyWorkbenchStats(
      projectId,
      {
        ...current,
        effectiveRanges: normalizeRanges([...current.effectiveRanges, [segment.startOffsetMs, segment.endOffsetMs]]),
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
  recordStudyActivity(projectId, "video", endAtMs - deltaMs, endAtMs)
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
    if (
      stats.webPresenceMs <= 0 &&
      stats.effectiveMs <= 0 &&
      stats.watchMs <= 0 &&
      stats.composeMs <= 0 &&
      stats.reviewMs <= 0 &&
      stats.qaMs <= 0
    ) {
      continue
    }
    const current = totalsByDate[dateKey] ?? { ...EMPTY_DAILY_WORKBENCH_STATS }
    totalsByDate[dateKey] = {
      schemaVersion: CURRENT_SCHEMA_VERSION,
      webPresenceMs: current.webPresenceMs + stats.webPresenceMs,
      videoMs: current.videoMs + stats.videoMs,
      recallEntryMs: current.recallEntryMs + stats.recallEntryMs,
      reviewMs: current.reviewMs + stats.reviewMs,
      aiQaMs: current.aiQaMs + stats.aiQaMs,
      distractionMs: current.distractionMs + stats.distractionMs,
      isPartitionComplete: current.isPartitionComplete && stats.isPartitionComplete,
      effectiveMs: current.effectiveMs + stats.effectiveMs,
      watchMs: current.watchMs + stats.watchMs,
      composeMs: current.composeMs + stats.composeMs,
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
    const summary = loadDailyWebPresenceMetrics(projectId, dateKey)
    if (
      summary.webPresenceMs <= 0 &&
      summary.effectiveMs <= 0 &&
      summary.watchMs <= 0 &&
      summary.composeMs <= 0 &&
      summary.reviewMs <= 0 &&
      summary.qaMs <= 0
    ) {
      continue
    }

    entries.push({
      projectId,
      dateKey,
      ...summary,
      presenceRanges: toRangeEntries(stored.presenceRanges),
      videoRanges: toRangeEntries(stored.videoRanges),
      recallEntryRanges: toRangeEntries(stored.recallEntryRanges),
      reviewRanges: toRangeEntries(stored.reviewRanges),
      aiQaRanges: toRangeEntries(stored.aiQaRanges),
      effectiveRanges: toRangeEntries(stored.effectiveRanges),
      watchRanges: toRangeEntries(stored.watchRanges.length > 0 ? stored.watchRanges : stored.videoRanges),
      composeRanges: toRangeEntries(stored.composeRanges.length > 0 ? stored.composeRanges : stored.recallEntryRanges),
      qaRanges: toRangeEntries(stored.qaRanges.length > 0 ? stored.qaRanges : stored.aiQaRanges),
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
        schemaVersion: entry.schemaVersion,
        webPresenceMs: entry.webPresenceMs,
        videoMs: entry.videoMs,
        recallEntryMs: entry.recallEntryMs,
        reviewMs: entry.reviewMs,
        aiQaMs: entry.aiQaMs,
        distractionMs: entry.distractionMs,
        isPartitionComplete: entry.isPartitionComplete,
        presenceRanges: fromRangeEntries(entry.presenceRanges),
        videoRanges: fromRangeEntries(entry.videoRanges),
        recallEntryRanges: fromRangeEntries(entry.recallEntryRanges),
        reviewRanges: fromRangeEntries(entry.reviewRanges),
        aiQaRanges: fromRangeEntries(entry.aiQaRanges),
        effectiveMs: entry.effectiveMs,
        watchMs: entry.watchMs,
        composeMs: entry.composeMs,
        qaMs: entry.qaMs,
        effectiveRanges: fromRangeEntries(entry.effectiveRanges),
        watchRanges: fromRangeEntries(entry.watchRanges),
        composeRanges: fromRangeEntries(entry.composeRanges),
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
  return Object.fromEntries(Object.entries(totalsByDate).map(([dateKey, stats]) => [dateKey, stats.videoMs])) as Record<string, number>
}

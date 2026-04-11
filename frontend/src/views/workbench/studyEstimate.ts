import type { DailyStudyMetricEntry, StudyMetricRange } from "@/ui/store/workbenchDailyStats"

export type ProjectStudyEstimate =
  | {
      status: "insufficient_data"
      sampleWatchMs: number
      sampleCoveredVideoMs: number
      sampleRecallPointCount: number
      sampleComposeMs: number
      sampleQaMs: number
      sampleCompletedMs: number
      sampleWatchCoverageRatio: number
    }
  | {
      status: "ready"
      remainingMs: number
      predictedTotalMs: number
      completedMs: number
      predictedRecallPointCount: number
      completionRatio: number
      confidence: "medium" | "high"
    }

const MIN_SAMPLE_WATCH_MS = 10 * 60_000
const MIN_SAMPLE_COVERED_VIDEO_MS = 8 * 60_000
const MIN_SAMPLE_RECALL_POINTS = 4
const MIN_SAMPLE_COMPLETED_MS = 8 * 60_000
const MIN_SAMPLE_WATCH_COVERAGE_RATIO = 0.35

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

function normalizeRanges(ranges: StudyMetricRange[]) {
  const sorted = ranges
    .filter((range) => Number.isFinite(range.startMs) && Number.isFinite(range.endMs) && range.endMs > range.startMs)
    .map((range) => ({ startMs: Math.floor(range.startMs), endMs: Math.floor(range.endMs) }))
    .sort((left, right) => left.startMs - right.startMs)

  if (sorted.length <= 1) return sorted

  const merged: StudyMetricRange[] = [sorted[0]!]
  for (const range of sorted.slice(1)) {
    const last = merged[merged.length - 1]!
    if (range.startMs <= last.endMs) {
      last.endMs = Math.max(last.endMs, range.endMs)
      continue
    }
    merged.push({ ...range })
  }
  return merged
}

function sumRanges(ranges: StudyMetricRange[]) {
  return normalizeRanges(ranges).reduce((sum, range) => sum + Math.max(0, range.endMs - range.startMs), 0)
}

function sumEntryEffectiveNoReviewMs(entry: DailyStudyMetricEntry) {
  return sumRanges([...entry.watchRanges, ...entry.composeRanges, ...entry.qaRanges])
}

export function estimateProjectStudyTime(params: {
  totalVideoMs: number
  coveredVideoMs: number
  recallPointCount: number
  entries: DailyStudyMetricEntry[]
}): ProjectStudyEstimate | null {
  const totalVideoMs = Math.max(0, Math.floor(params.totalVideoMs))
  const coveredVideoMs = Math.max(0, Math.floor(params.coveredVideoMs))
  const recallPointCount = Math.max(0, Math.floor(params.recallPointCount))
  const entries = params.entries

  if (totalVideoMs <= 0) return null

  const sampleWatchMs = entries.reduce((sum, entry) => sum + entry.watchMs, 0)
  const sampleComposeMs = entries.reduce((sum, entry) => sum + entry.composeMs, 0)
  const sampleQaMs = entries.reduce((sum, entry) => sum + entry.qaMs, 0)
  const sampleGrossMs = sampleWatchMs + sampleComposeMs + sampleQaMs
  const completedMs = entries.reduce((sum, entry) => sum + sumEntryEffectiveNoReviewMs(entry), 0)
  const sampleWatchCoverageRatio = sampleWatchMs / Math.max(coveredVideoMs, 1)

  if (
    sampleWatchMs < MIN_SAMPLE_WATCH_MS ||
    coveredVideoMs < MIN_SAMPLE_COVERED_VIDEO_MS ||
    recallPointCount < MIN_SAMPLE_RECALL_POINTS ||
    completedMs < MIN_SAMPLE_COMPLETED_MS ||
    sampleWatchCoverageRatio < MIN_SAMPLE_WATCH_COVERAGE_RATIO ||
    sampleGrossMs <= 0
  ) {
    return {
      status: "insufficient_data",
      sampleWatchMs,
      sampleCoveredVideoMs: coveredVideoMs,
      sampleRecallPointCount: recallPointCount,
      sampleComposeMs,
      sampleQaMs,
      sampleCompletedMs: completedMs,
      sampleWatchCoverageRatio,
    }
  }

  const watchFactor = clamp(sampleWatchMs / Math.max(coveredVideoMs, 1), 0.5, 3)
  const pointDensity = clamp(recallPointCount / Math.max(coveredVideoMs / 60_000, 1), 0.04, 8)
  const composePerPointMs = clamp(sampleComposeMs / Math.max(recallPointCount, 1), 20_000, 20 * 60_000)
  const qaRatio = clamp(sampleQaMs / Math.max(sampleWatchMs + sampleComposeMs, 1), 0, 1.5)
  const overlapFactor = clamp(completedMs / Math.max(sampleGrossMs, 1), 0.55, 1)

  const predictedRecallPointCount = Math.max(recallPointCount, Math.round((totalVideoMs / 60_000) * pointDensity))
  const predictedWatchMs = Math.round(totalVideoMs * watchFactor)
  const predictedComposeMs = Math.round(predictedRecallPointCount * composePerPointMs)
  const predictedQaMs = Math.round((predictedWatchMs + predictedComposeMs) * qaRatio)
  const predictedGrossMs = predictedWatchMs + predictedComposeMs + predictedQaMs
  const predictedTotalMs = Math.max(completedMs, predictedWatchMs, Math.round(predictedGrossMs * overlapFactor))
  const remainingMs = Math.max(0, predictedTotalMs - completedMs)
  const completionRatio = predictedTotalMs > 0 ? clamp(completedMs / predictedTotalMs, 0, 1) : 0

  const coveredVideoRatio = totalVideoMs > 0 ? coveredVideoMs / totalVideoMs : 0
  const confidence =
    sampleWatchMs >= 60 * 60_000 &&
    recallPointCount >= 12 &&
    coveredVideoRatio >= 0.35 &&
    completedMs >= 30 * 60_000 &&
    sampleWatchCoverageRatio >= 0.6
      ? "high"
      : "medium"

  return {
    status: "ready",
    remainingMs,
    predictedTotalMs,
    completedMs,
    predictedRecallPointCount,
    completionRatio,
    confidence,
  }
}

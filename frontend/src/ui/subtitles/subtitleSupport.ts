import type { Instance } from "@/ui/api/instances"
import type { MaterialSourceKind } from "@/ui/api/projects"
import type { ScopedProjectRef } from "@/ui/api/projectScope"
import { getInstanceSubtitleFile, type SubtitleSegment } from "@/ui/api/subtitles"
import { resolveProjectSameStemSiblingFile } from "@/ui/localMedia/projectDirectory"

export const SUPPORTED_SUBTITLE_EXTENSIONS = [".srt", ".vtt", ".ass", ".ssa"] as const
export const SUPPORTED_SUBTITLE_EXTENSIONS_LABEL = SUPPORTED_SUBTITLE_EXTENSIONS.join(" / ")

export type SubtitleDocument = {
  fileName: string
  format: "srt" | "vtt" | "ass" | "ssa"
  segments: SubtitleSegment[]
}

const subtitleDocumentCache = new Map<string, Promise<SubtitleDocument | null>>()

export async function loadSubtitleDocumentForInstance(params: {
  scope: ScopedProjectRef
  instance: Pick<Instance, "instanceId" | "materialId">
  sourceKind: MaterialSourceKind | null | undefined
}): Promise<SubtitleDocument | null> {
  const { scope, instance, sourceKind } = params
  const cacheKey = `${scope.subjectId}:${scope.scopedProjectId}:${instance.instanceId}:${instance.materialId}:${sourceKind ?? "unknown"}`
  const cached = subtitleDocumentCache.get(cacheKey)
  if (cached) return await cached

  const promise = (async () => {
    if (!sourceKind) return null

    if (sourceKind === "BROWSER_LOCAL") {
      const file = await resolveProjectSameStemSiblingFile(scope.scopedProjectId, instance.materialId, SUPPORTED_SUBTITLE_EXTENSIONS)
      if (!file) return null
      return await parseLocalSubtitleFile(file)
    }

    const remote = await getInstanceSubtitleFile(scope, instance.instanceId, { timeoutMs: 90_000 })
    if (!remote.found) return null
    return {
      fileName: remote.fileName,
      format: remote.format,
      segments: remote.segments,
    }
  })()

  subtitleDocumentCache.set(cacheKey, promise)
  try {
    return await promise
  } catch (error) {
    subtitleDocumentCache.delete(cacheKey)
    throw error
  }
}

export function clearSubtitleDocumentCache() {
  subtitleDocumentCache.clear()
}

export function findSubtitleTextAtMs(segments: SubtitleSegment[], playbackMs: number, graceMs = 120): string | null {
  if (segments.length === 0) return null
  const cursorMs = Math.max(0, Math.floor(playbackMs))
  const activeNow = findSubtitleSegmentsAtMs(segments, cursorMs)
  const activeText = joinSubtitleTexts(activeNow)
  if (activeText) return activeText

  if (graceMs <= 0) return null

  const previousCue = findMostRecentEndedSubtitleSegments(segments, cursorMs, Math.max(0, Math.floor(graceMs)))
  return joinSubtitleTexts(previousCue)
}

function findSubtitleSegmentsAtMs(segments: SubtitleSegment[], playbackMs: number): SubtitleSegment[] {
  const active: SubtitleSegment[] = []
  let low = 0
  let high = segments.length

  while (low < high) {
    const mid = Math.floor((low + high) / 2)
    if (segments[mid]!.endMs <= playbackMs) {
      low = mid + 1
    } else {
      high = mid
    }
  }

  for (let index = low; index < segments.length; index += 1) {
    const segment = segments[index]!
    if (segment.startMs > playbackMs) break
    if (segment.startMs <= playbackMs && playbackMs < segment.endMs) {
      active.push(segment)
    }
  }

  return active
}

function findMostRecentEndedSubtitleSegments(
  segments: SubtitleSegment[],
  playbackMs: number,
  graceMs: number,
): SubtitleSegment[] {
  let preferred: SubtitleSegment | null = null

  for (const segment of segments) {
    if (segment.endMs > playbackMs) break
    const gapMs = playbackMs - segment.endMs
    if (gapMs < 0 || gapMs > graceMs) continue
    if (
      preferred === null ||
      segment.endMs > preferred.endMs ||
      (segment.endMs === preferred.endMs && segment.startMs > preferred.startMs)
    ) {
      preferred = segment
    }
  }

  if (!preferred) return []
  return segments.filter(
    (segment) => segment.startMs === preferred.startMs && segment.endMs === preferred.endMs,
  )
}

function joinSubtitleTexts(segments: SubtitleSegment[]): string | null {
  const active = segments
    .map((segment) => segment.text.trim())
    .filter(Boolean)
  if (active.length === 0) return null
  return active.join(" ").replace(/\s+/g, " ").trim()
}

export function buildSubtitleContextText(params: {
  nodeLabel: string
  fileName: string
  segments: SubtitleSegment[]
  anchorMs?: number | null
  maxChars?: number
}): string | null {
  const { nodeLabel, fileName, segments, anchorMs = null, maxChars = 6000 } = params
  if (segments.length === 0) return null

  const selected = anchorMs === null
    ? segments
    : segments.filter((segment) => segment.endMs >= anchorMs - 90_000 && segment.startMs <= anchorMs + 90_000)
  const effective = selected.length > 0 ? selected : segments

  const lines: string[] = [
    `Supplemental subtitle context for “${nodeLabel}”.`,
    `Subtitle file: ${fileName}`,
  ]

  let currentLength = lines.join("\n").length
  for (const segment of effective) {
    const line = `[${formatSubtitleTimestamp(segment.startMs)}-${formatSubtitleTimestamp(segment.endMs)}] ${segment.text.trim()}`
    if (!segment.text.trim()) continue
    if (currentLength + line.length + 1 > maxChars) {
      lines.push("(subtitle context truncated)")
      break
    }
    lines.push(line)
    currentLength += line.length + 1
  }

  return lines.join("\n")
}

async function parseLocalSubtitleFile(file: File): Promise<SubtitleDocument> {
  const rawText = await file.text()
  const normalizedExt = file.name.includes(".") ? file.name.slice(file.name.lastIndexOf(".")).toLowerCase() : ""
  if (normalizedExt === ".srt") {
    return { fileName: file.name, format: "srt", segments: parseSrt(rawText) }
  }
  if (normalizedExt === ".vtt") {
    return { fileName: file.name, format: "vtt", segments: parseVtt(rawText) }
  }
  if (normalizedExt === ".ass") {
    return { fileName: file.name, format: "ass", segments: parseAssLike(rawText) }
  }
  if (normalizedExt === ".ssa") {
    return { fileName: file.name, format: "ssa", segments: parseAssLike(rawText) }
  }
  throw new Error(`暂不支持的字幕格式：${file.name}`)
}

function parseSrt(text: string): SubtitleSegment[] {
  const segments: SubtitleSegment[] = []
  const blocks = normalizeBlocks(text)
  for (const block of blocks) {
    let timelineIndex = 0
    if (!block[0]?.includes("-->") && block[1]?.includes("-->")) {
      timelineIndex = 1
    }
    const timeline = block[timelineIndex]
    if (!timeline || !timeline.includes("-->")) continue
    const [startMs, endMs] = parseArrowTimeline(timeline, false)
    const payload = block.slice(timelineIndex + 1).join("\n").trim()
    if (!payload) continue
    segments.push({ startMs, endMs, text: normalizeSubtitleText(payload) })
  }
  return normalizeSegments(segments)
}

function parseVtt(text: string): SubtitleSegment[] {
  const segments: SubtitleSegment[] = []
  const blocks = normalizeBlocks(text)
  for (const block of blocks) {
    const head = (block[0] ?? "").trim().toUpperCase()
    if (!block.length || head === "WEBVTT" || head.startsWith("NOTE") || head.startsWith("STYLE") || head.startsWith("REGION")) {
      continue
    }
    let timelineIndex = 0
    if (!block[0]?.includes("-->") && block[1]?.includes("-->")) {
      timelineIndex = 1
    }
    const timeline = block[timelineIndex]
    if (!timeline || !timeline.includes("-->")) continue
    const [startMs, endMs] = parseArrowTimeline(timeline, true)
    const payload = block.slice(timelineIndex + 1).join("\n").trim()
    if (!payload) continue
    segments.push({ startMs, endMs, text: normalizeSubtitleText(payload) })
  }
  return normalizeSegments(segments)
}

function parseAssLike(text: string): SubtitleSegment[] {
  const segments: SubtitleSegment[] = []
  const lines = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n")
  let inEvents = false
  let fields: string[] = []

  for (const rawLine of lines) {
    const line = rawLine.trim()
    if (!line) continue
    if (line.startsWith("[") && line.endsWith("]")) {
      inEvents = line.toLowerCase() === "[events]"
      continue
    }
    if (!inEvents) continue
    if (line.toLowerCase().startsWith("format:")) {
      fields = line
        .slice("format:".length)
        .split(",")
        .map((item) => item.trim().toLowerCase())
      continue
    }
    if (!line.toLowerCase().startsWith("dialogue:") || fields.length === 0) continue
    const payload = line.slice("dialogue:".length).trimStart()
    const parts = payload.split(",", fields.length - 1)
    if (parts.length < fields.length) continue
    const mapped = Object.fromEntries(fields.map((field, index) => [field, parts[index]?.trim() ?? ""])) as Record<string, string>
    if (!mapped.start || !mapped.end || !mapped.text) continue
    segments.push({
      startMs: parseAssTimestamp(mapped.start),
      endMs: parseAssTimestamp(mapped.end),
      text: normalizeSubtitleText(mapped.text),
    })
  }

  return normalizeSegments(segments)
}

function normalizeBlocks(text: string): string[][] {
  return text
    .replace(/\r\n/g, "\n")
    .replace(/\r/g, "\n")
    .trim()
    .split(/\n\s*\n/g)
    .map((block) => block.split("\n").map((line) => line.trim()).filter(Boolean))
    .filter((block) => block.length > 0)
}

function parseArrowTimeline(line: string, allowShortHours: boolean): [number, number] {
  const [rawStart, rawEnd] = line.split("-->")
  return [
    parseWebTimestamp((rawStart ?? "").trim().split(" ", 1)[0] ?? "", allowShortHours),
    parseWebTimestamp((rawEnd ?? "").trim().split(" ", 1)[0] ?? "", allowShortHours),
  ]
}

function parseWebTimestamp(value: string, allowShortHours: boolean): number {
  const parts = value.replace(",", ".").split(":")
  let hours = "0"
  let minutes = ""
  let secondsWithMillis = ""

  if (parts.length === 3) {
    ;[hours, minutes, secondsWithMillis] = parts
  } else if (parts.length === 2 && allowShortHours) {
    ;[minutes, secondsWithMillis] = parts
  } else {
    throw new Error(`无效字幕时间：${value}`)
  }

  const [secondsText, millisText = "0"] = secondsWithMillis.split(".", 2)
  return (
    ((Number(hours) * 60 + Number(minutes)) * 60 + Number(secondsText)) * 1000 +
    Number((millisText + "000").slice(0, 3))
  )
}

function parseAssTimestamp(value: string): number {
  const parts = value.split(":")
  if (parts.length !== 3) throw new Error(`无效 ASS 时间：${value}`)
  const [hoursText, minutesText, secondsWithCentis] = parts
  const [secondsText, centisText = "0"] = secondsWithCentis.split(".", 2)
  return (
    ((Number(hoursText) * 60 + Number(minutesText)) * 60 + Number(secondsText)) * 1000 +
    Number((centisText.slice(0, 2) || "0").padEnd(2, "0")) * 10
  )
}

function normalizeSubtitleText(text: string): string {
  return text
    .replace(/\ufeff/g, "")
    .replace(/\\N|\\n/g, "\n")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/\{[^}]*\}/g, "")
    .replace(/<\/?[^>]+>/g, "")
    .split("\n")
    .map((line) => line.replace(/\s+/g, " ").trim())
    .filter(Boolean)
    .join("\n")
    .trim()
}

function normalizeSegments(segments: SubtitleSegment[]): SubtitleSegment[] {
  return segments
    .map((segment) => ({
      startMs: Math.max(0, Math.floor(segment.startMs)),
      endMs: Math.max(0, Math.floor(segment.endMs)),
      text: segment.text.trim(),
    }))
    .filter((segment) => segment.endMs > segment.startMs && segment.text)
    .sort((left, right) => left.startMs - right.startMs || left.endMs - right.endMs || left.text.localeCompare(right.text))
}

function formatSubtitleTimestamp(ms: number) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000))
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`
}

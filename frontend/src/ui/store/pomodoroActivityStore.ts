import { getLocalDateKey } from "@/ui/store/workbenchDailyStats"

export type PomodoroActivityRecord = {
  recordId: string
  kind: "pomodoro"
  dateKey: string
  planId: string
  planIndex: number
  pomodoroIndex: number
  pomodoroLabel: string
  projectId: string | null
  startAtMs: number
  endAtMs: number
  durationMs: number
  recordedAtMs: number
}

type RecordPomodoroActivityInput = {
  planId: string
  planIndex: number
  pomodoroIndex: number
  projectId: string | null
  startAtMs: number
  endAtMs: number
}

const STORAGE_KEY = "plm-pomodoro-activity-records"

function normalizeRecord(raw: unknown): PomodoroActivityRecord | null {
  if (!raw || typeof raw !== "object") return null
  const input = raw as Partial<PomodoroActivityRecord>
  const startAtMs = Number(input.startAtMs)
  const endAtMs = Number(input.endAtMs)
  const pomodoroIndex = Number(input.pomodoroIndex)
  if (!Number.isFinite(startAtMs) || !Number.isFinite(endAtMs) || endAtMs <= startAtMs) return null
  if (!Number.isFinite(pomodoroIndex) || pomodoroIndex < 1) return null
  const dateKey = typeof input.dateKey === "string" && input.dateKey.trim() ? input.dateKey.trim() : getLocalDateKey(new Date(endAtMs))
  const planId = typeof input.planId === "string" && input.planId.trim() ? input.planId.trim() : "unknown-plan"
  const projectId = typeof input.projectId === "string" && input.projectId.trim() ? input.projectId.trim() : null
  return {
    recordId: typeof input.recordId === "string" && input.recordId.trim()
      ? input.recordId.trim()
      : `${dateKey}:${planId}:${Math.round(pomodoroIndex)}:${Math.floor(startAtMs)}`,
    kind: "pomodoro",
    dateKey,
    planId,
    planIndex: Number.isFinite(input.planIndex) ? Math.max(-1, Math.round(Number(input.planIndex))) : -1,
    pomodoroIndex: Math.max(1, Math.round(pomodoroIndex)),
    pomodoroLabel: typeof input.pomodoroLabel === "string" && input.pomodoroLabel.trim()
      ? input.pomodoroLabel.trim()
      : `番茄 ${Math.max(1, Math.round(pomodoroIndex))}`,
    projectId,
    startAtMs: Math.floor(startAtMs),
    endAtMs: Math.floor(endAtMs),
    durationMs: Math.max(0, Math.floor(endAtMs - startAtMs)),
    recordedAtMs: Number.isFinite(input.recordedAtMs) ? Math.floor(Number(input.recordedAtMs)) : Date.now(),
  }
}

function loadRawRecords() {
  if (typeof window === "undefined") return [] as PomodoroActivityRecord[]
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed)
      ? parsed.map(normalizeRecord).filter((item): item is PomodoroActivityRecord => Boolean(item))
      : []
  } catch {
    return []
  }
}

function saveRecords(records: PomodoroActivityRecord[]) {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(records))
  } catch {
    // Keep the timer usable even when local storage is unavailable.
  }
}

export function listPomodoroActivityRecords(options?: { dateKey?: string }) {
  return loadRawRecords()
    .filter((record) => !options?.dateKey || record.dateKey === options.dateKey)
    .sort((left, right) => right.endAtMs - left.endAtMs)
}

export function recordPomodoroActivity(input: RecordPomodoroActivityInput) {
  const normalized = normalizeRecord({
    ...input,
    kind: "pomodoro",
    dateKey: getLocalDateKey(new Date(input.endAtMs)),
    pomodoroLabel: `番茄 ${input.pomodoroIndex}`,
    durationMs: input.endAtMs - input.startAtMs,
    recordedAtMs: Date.now(),
  })
  if (!normalized) return null

  const records = loadRawRecords()
  if (records.some((record) => record.recordId === normalized.recordId)) return normalized
  const nextRecords = [normalized, ...records].sort((left, right) => right.endAtMs - left.endAtMs).slice(0, 500)
  saveRecords(nextRecords)
  return normalized
}

export function clearAllPomodoroActivityRecords() {
  if (typeof window === "undefined") return
  try {
    window.localStorage.removeItem(STORAGE_KEY)
  } catch {
    // Ignore storage failures.
  }
}

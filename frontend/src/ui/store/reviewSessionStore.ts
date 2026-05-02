export type ReviewSessionState = {
  answers: Record<string, 0 | 1>
  showAnswer: Record<string, boolean>
  insightDrafts: Record<string, string>
  showInsightEditor: Record<string, boolean>
  activeRecallPointId: string | null
}

export const EMPTY_REVIEW_SESSION: ReviewSessionState = {
  answers: {},
  showAnswer: {},
  insightDrafts: {},
  showInsightEditor: {},
  activeRecallPointId: null,
}

const REVIEW_SESSION_STORAGE_PREFIX = "plm-review-session:"
const REVIEW_SESSION_STORAGE_VERSION = 1

function storageKey(projectId: string) {
  return `${REVIEW_SESSION_STORAGE_PREFIX}${projectId}`
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value))
}

function normalizeAnswerMap(input: unknown): Record<string, 0 | 1> {
  if (!isRecord(input)) return {}
  return Object.fromEntries(
    Object.entries(input).filter((entry): entry is [string, 0 | 1] => {
      const [, value] = entry
      return value === 0 || value === 1
    }).map(([key, item]) => [key, item === 1 ? 1 : 0]),
  )
}

function normalizeBooleanMap(value: unknown): Record<string, boolean> {
  if (!isRecord(value)) return {}
  return Object.fromEntries(
    Object.entries(value)
      .filter((entry): entry is [string, boolean] => typeof entry[0] === "string" && typeof entry[1] === "boolean")
      .map(([key, item]) => [key, item]),
  )
}

function normalizeStringMap(value: unknown): Record<string, string> {
  if (!isRecord(value)) return {}
  return Object.fromEntries(
    Object.entries(value)
      .filter((entry): entry is [string, string] => typeof entry[0] === "string" && typeof entry[1] === "string")
      .map(([key, item]) => [key, item]),
  )
}

export function normalizeReviewSessionState(value: unknown): ReviewSessionState {
  const raw = isRecord(value) ? value : {}
  return {
    answers: normalizeAnswerMap(raw.answers),
    showAnswer: normalizeBooleanMap(raw.showAnswer),
    insightDrafts: normalizeStringMap(raw.insightDrafts),
    showInsightEditor: normalizeBooleanMap(raw.showInsightEditor),
    activeRecallPointId: typeof raw.activeRecallPointId === "string" ? raw.activeRecallPointId : null,
  }
}

function normalizeReviewSessionStateByHeadId(value: unknown): Record<string, ReviewSessionState> {
  const raw = isRecord(value) ? value : {}
  const sessions = isRecord(raw.sessions) ? raw.sessions : raw
  return Object.fromEntries(
    Object.entries(sessions)
      .filter(([headId]) => Boolean(headId.trim()))
      .map(([headId, session]) => [headId, normalizeReviewSessionState(session)]),
  )
}

export function loadReviewSessionStateByHeadId(projectId: string): Record<string, ReviewSessionState> {
  if (!projectId || typeof window === "undefined") return {}
  try {
    const raw = window.localStorage.getItem(storageKey(projectId))
    if (!raw) return {}
    return normalizeReviewSessionStateByHeadId(JSON.parse(raw))
  } catch {
    return {}
  }
}

export function saveReviewSessionStateByHeadId(projectId: string, state: Record<string, ReviewSessionState>) {
  if (!projectId || typeof window === "undefined") return
  try {
    const sessions = normalizeReviewSessionStateByHeadId(state)
    window.localStorage.setItem(
      storageKey(projectId),
      JSON.stringify({
        version: REVIEW_SESSION_STORAGE_VERSION,
        sessions,
      }),
    )
  } catch {
    // Ignore storage failures; in-memory state still protects the current interaction.
  }
}

export function clearPersistedReviewSession(projectId: string, headId: string) {
  if (!projectId || !headId) return
  const sessions = loadReviewSessionStateByHeadId(projectId)
  delete sessions[headId]
  saveReviewSessionStateByHeadId(projectId, sessions)
}

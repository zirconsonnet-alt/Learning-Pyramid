export const SESSION_COOKIE_NAME = "plm_session"

export function extractSessionCookie(setCookieHeader: string | null | undefined): string | null {
  const raw = String(setCookieHeader ?? "").trim()
  if (!raw) return null
  const firstPart = raw.split(";")[0]?.trim()
  if (!firstPart) return null
  if (!firstPart.startsWith(`${SESSION_COOKIE_NAME}=`)) return null
  const value = firstPart.slice(SESSION_COOKIE_NAME.length + 1)
  return value ? `${SESSION_COOKIE_NAME}=${value}` : null
}

export function buildCookieHeader(sessionCookie: string | null | undefined): string | undefined {
  const raw = String(sessionCookie ?? "").trim()
  return raw ? raw : undefined
}

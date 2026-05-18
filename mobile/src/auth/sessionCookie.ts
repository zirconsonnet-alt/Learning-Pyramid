export const SESSION_COOKIE_NAME = "plm_session"

export type SessionCookieUpdate =
  | { kind: "missing" }
  | { kind: "set"; cookie: string }
  | { kind: "clear" }

function splitSetCookieHeader(header: string): string[] {
  const parts: string[] = []
  let start = 0

  for (let index = 0; index < header.length; index += 1) {
    if (header[index] !== ",") continue

    const rest = header.slice(index + 1)
    if (/^\s*[!#$%&'*+\-.^_`|~0-9A-Za-z]+=/.test(rest)) {
      parts.push(header.slice(start, index).trim())
      start = index + 1
    }
  }

  parts.push(header.slice(start).trim())
  return parts.filter(Boolean)
}

export function extractSessionCookieUpdate(
  setCookieHeader: string | null | undefined,
): SessionCookieUpdate {
  const raw = String(setCookieHeader ?? "").trim()
  if (!raw) return { kind: "missing" }

  for (const cookie of splitSetCookieHeader(raw)) {
    const cookiePair = cookie.split(";")[0]?.trim()
    if (!cookiePair) continue

    const separatorIndex = cookiePair.indexOf("=")
    if (separatorIndex < 0) continue

    const name = cookiePair.slice(0, separatorIndex).trim()
    if (name !== SESSION_COOKIE_NAME) continue

    const value = cookiePair.slice(separatorIndex + 1).trim()
    if (!value || value === '""') return { kind: "clear" }

    return { kind: "set", cookie: `${SESSION_COOKIE_NAME}=${value}` }
  }

  return { kind: "missing" }
}

export function extractSessionCookie(setCookieHeader: string | null | undefined): string | null {
  const update = extractSessionCookieUpdate(setCookieHeader)
  return update.kind === "set" ? update.cookie : null
}

export function buildCookieHeader(sessionCookie: string | null | undefined): string | undefined {
  const raw = String(sessionCookie ?? "").trim()
  return new RegExp(`^${SESSION_COOKIE_NAME}=[^\\s;,]+$`).test(raw) ? raw : undefined
}

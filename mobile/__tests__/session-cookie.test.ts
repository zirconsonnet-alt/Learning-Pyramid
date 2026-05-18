import {
  buildCookieHeader,
  extractSessionCookie,
  extractSessionCookieUpdate,
} from "../src/auth/sessionCookie"

describe("session cookie helpers", () => {
  it("extracts plm_session from Set-Cookie", () => {
    const cookie = extractSessionCookie(
      "plm_session=abc123; Max-Age=2592000; Path=/; HttpOnly; SameSite=None; Secure",
    )

    expect(cookie).toBe("plm_session=abc123")
  })

  it("finds plm_session in combined Set-Cookie headers", () => {
    expect(
      extractSessionCookieUpdate(
        "other=1; Path=/, plm_session=abc123; Path=/; HttpOnly, another=2; Path=/",
      ),
    ).toEqual({ kind: "set", cookie: "plm_session=abc123" })
  })

  it("does not split Expires commas while finding plm_session", () => {
    expect(
      extractSessionCookieUpdate(
        "other=1; Expires=Wed, 21 Oct 2030 07:28:00 GMT; Path=/, plm_session=abc123; Path=/; HttpOnly",
      ),
    ).toEqual({ kind: "set", cookie: "plm_session=abc123" })
  })

  it("does not match similarly named cookies", () => {
    expect(extractSessionCookieUpdate("plm_session_backup=abc123; Path=/")).toEqual({
      kind: "missing",
    })
  })

  it("distinguishes missing, set, and clear updates", () => {
    expect(extractSessionCookieUpdate(null)).toEqual({ kind: "missing" })
    expect(extractSessionCookieUpdate("plm_session=abc123; Path=/")).toEqual({
      kind: "set",
      cookie: "plm_session=abc123",
    })
    expect(extractSessionCookieUpdate("plm_session=; Max-Age=0; Path=/")).toEqual({
      kind: "clear",
    })
    expect(extractSessionCookieUpdate('plm_session=""; Max-Age=0; Path=/')).toEqual({
      kind: "clear",
    })
    expect(extractSessionCookie("plm_session=; Max-Age=0; Path=/")).toBeNull()
  })

  it("builds Cookie header from a stored session cookie", () => {
    expect(buildCookieHeader("plm_session=abc123")).toBe("plm_session=abc123")
    expect(buildCookieHeader(null)).toBeUndefined()
  })

  it("only builds Cookie header for exact non-empty plm_session cookies", () => {
    expect(buildCookieHeader("plm_session=")).toBeUndefined()
    expect(buildCookieHeader("plm_session_backup=abc123")).toBeUndefined()
    expect(buildCookieHeader("other=1; plm_session=abc123")).toBeUndefined()
    expect(buildCookieHeader("plm_session=abc123; other=1")).toBeUndefined()
  })
})

import { buildCookieHeader, extractSessionCookie } from "../src/auth/sessionCookie"

describe("session cookie helpers", () => {
  it("extracts plm_session from Set-Cookie", () => {
    const cookie = extractSessionCookie(
      "plm_session=abc123; Max-Age=2592000; Path=/; HttpOnly; SameSite=None; Secure",
    )

    expect(cookie).toBe("plm_session=abc123")
  })

  it("builds Cookie header from a stored session cookie", () => {
    expect(buildCookieHeader("plm_session=abc123")).toBe("plm_session=abc123")
    expect(buildCookieHeader(null)).toBeUndefined()
  })
})

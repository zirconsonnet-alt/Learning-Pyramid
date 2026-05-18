export type SessionCookieStore = {
  getSessionCookie(): string | null
  setSessionCookie(cookie: string | null): void
  clearSessionCookie(): void
}

export function createSessionCookieStore(initialCookie: string | null = null): SessionCookieStore {
  let sessionCookie = initialCookie
  return {
    getSessionCookie: () => sessionCookie,
    setSessionCookie: (cookie) => {
      sessionCookie = cookie
    },
    clearSessionCookie: () => {
      sessionCookie = null
    },
  }
}

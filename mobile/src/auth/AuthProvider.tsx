import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react"

import type { AuthUser } from "../api/auth"
import type { createLearningPyramidApi } from "../api/types"
import type { SessionCookieStore } from "./sessionCookieStore"
import type { SessionStorage } from "./sessionStorage"

type AuthStatus = "loading" | "signedOut" | "signedIn"

type AuthContextValue = {
  status: AuthStatus
  user: AuthUser | null
  signIn(email: string, password: string): Promise<void>
  signOut(): Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({
  api,
  cookieStore,
  storage,
  children,
}: {
  api: ReturnType<typeof createLearningPyramidApi>
  cookieStore: SessionCookieStore
  storage: SessionStorage
  children: ReactNode
}) {
  const [status, setStatus] = useState<AuthStatus>("loading")
  const [user, setUser] = useState<AuthUser | null>(null)

  useEffect(() => {
    let active = true

    async function restore() {
      const sessionCookie = await storage.getSessionCookie()
      cookieStore.setSessionCookie(sessionCookie)
      if (!sessionCookie) {
        if (active) setStatus("signedOut")
        return
      }

      let currentUser: AuthUser | null
      try {
        currentUser = await api.auth.me()
      } catch {
        if (active) setStatus("signedOut")
        return
      }
      if (!active) return
      if (!currentUser) {
        cookieStore.clearSessionCookie()
        await storage.clearSessionCookie()
      }
      setUser(currentUser)
      setStatus(currentUser ? "signedIn" : "signedOut")
    }

    void restore()
    return () => {
      active = false
    }
  }, [api, cookieStore, storage])

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      signIn: async (email, password) => {
        const nextUser = await api.auth.login({ email, password })
        const nextCookie = cookieStore.getSessionCookie()
        if (!nextCookie) {
          throw new Error("登录响应没有返回会话 Cookie")
        }
        await storage.setSessionCookie(nextCookie)
        setUser(nextUser)
        setStatus("signedIn")
      },
      signOut: async () => {
        await api.auth.logout()
        cookieStore.clearSessionCookie()
        await storage.clearSessionCookie()
        setUser(null)
        setStatus("signedOut")
      },
    }),
    [api, cookieStore, status, storage, user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error("useAuth must be used within AuthProvider")
  return value
}

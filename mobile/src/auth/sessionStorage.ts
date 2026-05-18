import * as SecureStore from "expo-secure-store"

const SESSION_COOKIE_KEY = "learningpyramid.sessionCookie"

export type SessionStorage = {
  getSessionCookie(): Promise<string | null>
  setSessionCookie(cookie: string): Promise<void>
  clearSessionCookie(): Promise<void>
}

export const secureSessionStorage: SessionStorage = {
  getSessionCookie: () => SecureStore.getItemAsync(SESSION_COOKIE_KEY),
  setSessionCookie: (cookie) => SecureStore.setItemAsync(SESSION_COOKIE_KEY, cookie),
  clearSessionCookie: () => SecureStore.deleteItemAsync(SESSION_COOKIE_KEY),
}

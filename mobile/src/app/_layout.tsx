import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Slot } from "expo-router"
import { useState } from "react"

import { createApiClient } from "../api/http"
import { ApiProvider } from "../api/ApiProvider"
import { createLearningPyramidApi } from "../api/types"
import { AuthProvider } from "../auth/AuthProvider"
import { createSessionCookieStore } from "../auth/sessionCookieStore"
import { secureSessionStorage } from "../auth/sessionStorage"

const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? "https://plm.xuebao.chat/api"

export default function RootLayout() {
  const [queryClient] = useState(() => new QueryClient())
  const [cookieStore] = useState(() => createSessionCookieStore())
  const [api] = useState(() => {
    const client = createApiClient({
      baseUrl: API_BASE_URL,
      getSessionCookie: () => cookieStore.getSessionCookie(),
      setSessionCookie: (cookie) => cookieStore.setSessionCookie(cookie),
    })
    return createLearningPyramidApi(client)
  })

  return (
    <QueryClientProvider client={queryClient}>
      <ApiProvider api={api}>
        <AuthProvider api={api} cookieStore={cookieStore} storage={secureSessionStorage}>
          <Slot />
        </AuthProvider>
      </ApiProvider>
    </QueryClientProvider>
  )
}

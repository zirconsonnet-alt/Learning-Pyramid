import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Stack } from "expo-router"
import { useState } from "react"

import { ApiProvider } from "../api/ApiProvider"
import { API_BASE_URL } from "../api/config"
import { createApiClient } from "../api/http"
import { createLearningPyramidApi } from "../api/types"
import { AuthProvider } from "../auth/AuthProvider"
import { createSessionCookieStore } from "../auth/sessionCookieStore"
import { secureSessionStorage } from "../auth/sessionStorage"
import { ui } from "../constants/ui"

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
      <ApiProvider api={api} apiBaseUrl={API_BASE_URL} getSessionCookie={() => cookieStore.getSessionCookie()}>
        <AuthProvider api={api} cookieStore={cookieStore} storage={secureSessionStorage}>
          <Stack
            screenOptions={{
              gestureEnabled: true,
              headerBackTitle: "返回",
              headerTitleAlign: "center",
              headerShadowVisible: false,
              headerStyle: { backgroundColor: ui.colors.appBackground },
              headerTitleStyle: { color: ui.colors.text, fontSize: 20, fontWeight: "800" },
            }}
          >
            <Stack.Screen name="index" options={{ headerShown: false }} />
            <Stack.Screen name="mine" options={{ title: "我的" }} />
            <Stack.Screen name="settings/global" options={{ title: "全局设置" }} />
            <Stack.Screen name="subject/[subjectId]" options={{ title: "项目中心" }} />
            <Stack.Screen name="subject/[subjectId]/settings" options={{ title: "学科设置" }} />
            <Stack.Screen name="project/[subjectId]/[scopedProjectId]" options={{ headerShown: false }} />
            <Stack.Screen name="project-settings/[subjectId]/[scopedProjectId]" options={{ title: "项目设置" }} />
            <Stack.Screen name="offline-packages/[subjectId]/[scopedProjectId]" options={{ title: "离线课程包" }} />
          </Stack>
        </AuthProvider>
      </ApiProvider>
    </QueryClientProvider>
  )
}

import { createContext, useContext, type ReactNode } from "react"

import type { createLearningPyramidApi } from "./types"

type LearningPyramidApi = ReturnType<typeof createLearningPyramidApi>

type ApiContextValue = {
  api: LearningPyramidApi
  apiBaseUrl: string
  getSessionCookie(): string | null
}

const ApiContext = createContext<ApiContextValue | null>(null)

export function ApiProvider({
  api,
  apiBaseUrl,
  getSessionCookie = () => null,
  children,
}: {
  api: LearningPyramidApi
  apiBaseUrl: string
  getSessionCookie?: () => string | null
  children: ReactNode
}) {
  return <ApiContext.Provider value={{ api, apiBaseUrl, getSessionCookie }}>{children}</ApiContext.Provider>
}

export function useApiRuntime() {
  const value = useContext(ApiContext)
  if (!value) throw new Error("useApiRuntime must be used within ApiProvider")
  return value
}

export function useLearningPyramidApi() {
  return useApiRuntime().api
}

import { createContext, useContext, type ReactNode } from "react"

import type { createLearningPyramidApi } from "./types"

type LearningPyramidApi = ReturnType<typeof createLearningPyramidApi>

const ApiContext = createContext<LearningPyramidApi | null>(null)

export function ApiProvider({ api, children }: { api: LearningPyramidApi; children: ReactNode }) {
  return <ApiContext.Provider value={api}>{children}</ApiContext.Provider>
}

export function useLearningPyramidApi() {
  const api = useContext(ApiContext)
  if (!api) throw new Error("useLearningPyramidApi must be used within ApiProvider")
  return api
}

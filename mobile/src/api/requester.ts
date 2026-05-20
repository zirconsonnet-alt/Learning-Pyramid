import { z } from "zod"

export type ScopedProjectRef = {
  subjectId: string
  scopedProjectId: string
}

export type ApiRequestOptions<T> = {
  path: string
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"
  body?: unknown
  responseSchema: z.ZodType<T>
}

export type ApiRequester = {
  request: <T>(options: ApiRequestOptions<T>) => Promise<T>
}

export function projectApiPath(scope: ScopedProjectRef, suffix: string) {
  const cleanSuffix = suffix.startsWith("/") ? suffix : `/${suffix}`
  return `/subjects/${encodeURIComponent(scope.subjectId)}/projects/${encodeURIComponent(
    scope.scopedProjectId,
  )}${cleanSuffix}`
}

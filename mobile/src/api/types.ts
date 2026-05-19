import { z } from "zod"

import { createAuthApi } from "./auth"
import { createLearningObjectsApi } from "./learningObjects"
import { createLearningTasksApi } from "./learningTasks"
import { createMediaApi } from "./media"
import { createReviewApi } from "./review"
import { createSubjectsApi } from "./subjects"

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

export function createLearningPyramidApi(requester: ApiRequester) {
  return {
    auth: createAuthApi(requester),
    subjects: createSubjectsApi(requester),
    learningObjects: createLearningObjectsApi(requester),
    learningTasks: createLearningTasksApi(requester),
    media: createMediaApi(requester),
    review: createReviewApi(requester),
  }
}

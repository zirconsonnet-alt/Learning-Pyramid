import { z } from "zod"

import { apiRequest } from "@/ui/api/http"
import { projectApiPath, type ProjectScope } from "@/ui/api/projectScope"
import type { RichContent } from "@/ui/api/richContent"
import { normalizeRichContent, RichContentSchema } from "@/ui/api/richContent"

export const SubmitLearningTaskResultSchema = z.object({ entryNodeId: z.string() })
export const LearningTaskSchema = z.object({
  projectId: z.string(),
  learningTaskId: z.string(),
  title: z.string(),
  recallPointIds: z.array(z.string()),
  size: z.number().int(),
  entryNodeId: z.string().nullable(),
  entryNodeTitle: z.string().nullable(),
  reviewChainId: z.string().nullable(),
  targetLayerIndex: z.number().int().nullable(),
})
export type LearningTask = z.infer<typeof LearningTaskSchema>

export type SubmitLearningTaskItem = {
  question: RichContent
  answer: RichContent
  anchor: { instanceId: string; position: string } | null
  references: string[]
}

export function submitLearningTask(params: {
  scope: ProjectScope
  title: string
  items: SubmitLearningTaskItem[]
}) {
  return apiRequest({
    path: projectApiPath(params.scope, "/learning-tasks"),
    method: "POST",
    body: {
      title: params.title,
      items: params.items.map((it) => ({
        question: RichContentSchema.parse(normalizeRichContent(it.question)),
        answer: RichContentSchema.parse(normalizeRichContent(it.answer)),
        anchor: it.anchor,
        references: it.references,
      })),
    },
    responseSchema: SubmitLearningTaskResultSchema,
  })
}

export function getLearningTask(scope: ProjectScope, learningTaskId: string) {
  return apiRequest({
    path: projectApiPath(scope, `/learning-tasks/${learningTaskId}`),
    responseSchema: LearningTaskSchema,
  })
}

export function editLearningTask(scope: ProjectScope, learningTaskId: string, title: string) {
  return apiRequest({
    path: projectApiPath(scope, `/learning-tasks/${learningTaskId}`),
    method: "PATCH",
    body: { title },
    responseSchema: z.null(),
  })
}

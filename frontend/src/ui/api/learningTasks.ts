import { z } from "zod"

import { apiRequest } from "@/ui/api/http"
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
}

export function submitLearningTask(params: {
  projectId: string
  title: string
  items: SubmitLearningTaskItem[]
}) {
  return apiRequest({
    path: `/projects/${params.projectId}/learning-tasks`,
    method: "POST",
    body: {
      title: params.title,
      items: params.items.map((it) => ({
        question: RichContentSchema.parse(normalizeRichContent(it.question)),
        answer: RichContentSchema.parse(normalizeRichContent(it.answer)),
        anchor: it.anchor,
      })),
    },
    responseSchema: SubmitLearningTaskResultSchema,
  })
}

export function getLearningTask(projectId: string, learningTaskId: string) {
  return apiRequest({
    path: `/projects/${projectId}/learning-tasks/${learningTaskId}`,
    responseSchema: LearningTaskSchema,
  })
}

export function editLearningTask(projectId: string, learningTaskId: string, title: string) {
  return apiRequest({
    path: `/projects/${projectId}/learning-tasks/${learningTaskId}`,
    method: "PATCH",
    body: { title },
    responseSchema: z.null(),
  })
}

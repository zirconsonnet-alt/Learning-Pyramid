import { z } from "zod"

import { RichContentSchema, type RichContent } from "./richContent"
import { projectApiPath, type ApiRequester, type ScopedProjectRef } from "./requester"

const SubmitLearningTaskResultSchema = z.object({ entryNodeId: z.string() })

export type SubmitLearningTaskItem = {
  question: RichContent
  answer: RichContent
  anchor: { instanceId: string; position: string } | null
  references: string[]
}

export type SubmitLearningTaskInput = {
  title: string
  items: SubmitLearningTaskItem[]
}

export type SubmitLearningTaskResult = z.infer<typeof SubmitLearningTaskResultSchema>

export function createLearningTasksApi(api: ApiRequester) {
  return {
    submitLearningTask: (scope: ScopedProjectRef, input: SubmitLearningTaskInput) =>
      api.request({
        path: projectApiPath(scope, "/learning-tasks"),
        method: "POST",
        body: {
          title: input.title,
          items: input.items.map((item) => ({
            question: RichContentSchema.parse(item.question),
            answer: RichContentSchema.parse(item.answer),
            anchor: item.anchor,
            references: item.references,
          })),
        },
        responseSchema: SubmitLearningTaskResultSchema,
      }),
  }
}

import { z } from "zod"

import { apiRequest } from "@/ui/api/http"

export const QueueSchema = z.object({
  headId: z.string().nullable(),
  ids: z.array(z.string()),
})
export type Queue = z.infer<typeof QueueSchema>

export function getQueue(projectId: string) {
  return apiRequest({ path: `/projects/${projectId}/queue`, responseSchema: QueueSchema })
}


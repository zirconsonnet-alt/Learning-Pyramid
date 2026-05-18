import { z } from "zod"

import type { ApiRequester } from "./types"

export const SubjectSchema = z.object({
  subjectId: z.string(),
  title: z.string(),
  state: z.string(),
  createdAt: z.unknown(),
  deletedAt: z.unknown().nullable().optional(),
})

export const StudyMaterialSchema = z.object({
  subjectId: z.string(),
  materialId: z.string(),
  materialType: z.string(),
  title: z.string().nullable().optional(),
  createdAt: z.unknown(),
  scopedProjectId: z.string().nullable(),
})

export type Subject = z.infer<typeof SubjectSchema>
export type StudyMaterial = z.infer<typeof StudyMaterialSchema>

export function createSubjectsApi(requester: ApiRequester) {
  return {
    list: () =>
      requester.request({
        path: "/subjects",
        responseSchema: z.array(SubjectSchema),
      }),
    listMaterials: (subjectId: string) =>
      requester.request({
        path: `/subjects/${encodeURIComponent(subjectId)}/materials`,
        responseSchema: z.array(StudyMaterialSchema),
      }),
  }
}

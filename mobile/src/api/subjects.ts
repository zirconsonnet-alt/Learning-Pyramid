import { z } from "zod"

import type { ApiRequester } from "./types"

export const SubjectSchema = z.object({
  subjectId: z.string(),
  title: z.string(),
  state: z.string(),
  createdAt: z.string(),
  deletedAt: z.string().nullable(),
})

export const StudyMaterialTypeSchema = z.enum(["COURSE", "BOOK", "LOOSE_POINTS"])

export const StudyMaterialSchema = z.object({
  subjectId: z.string(),
  materialId: z.string(),
  materialType: StudyMaterialTypeSchema,
  title: z.string(),
  createdAt: z.string(),
  scopedProjectId: z.string().nullable(),
})

export type Subject = z.infer<typeof SubjectSchema>
export type StudyMaterialType = z.infer<typeof StudyMaterialTypeSchema>
export type StudyMaterial = z.infer<typeof StudyMaterialSchema>

export function createSubjectsApi(requester: ApiRequester) {
  return {
    listSubjects: () =>
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

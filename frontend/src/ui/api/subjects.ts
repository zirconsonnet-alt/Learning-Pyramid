import { z } from "zod"

import { apiRequest } from "@/ui/api/http"
import { projectApiPath, type ScopedProjectRef } from "@/ui/api/projectScope"

export const SubjectSchema = z.object({
  subjectId: z.string(),
  title: z.string(),
  state: z.string(),
  createdAt: z.string(),
  deletedAt: z.string().nullable(),
})
export type Subject = z.infer<typeof SubjectSchema>

export const StudyMaterialTypeSchema = z.enum(["COURSE", "BOOK", "LOOSE_POINTS"])
export type StudyMaterialType = z.infer<typeof StudyMaterialTypeSchema>

export const StudyMaterialSchema = z.object({
  subjectId: z.string(),
  materialId: z.string(),
  materialType: StudyMaterialTypeSchema,
  title: z.string(),
  createdAt: z.string(),
  scopedProjectId: z.string().nullable(),
})
export type StudyMaterial = z.infer<typeof StudyMaterialSchema>

export const SubjectContextSchema = z.object({
  subject: SubjectSchema,
  currentMaterial: StudyMaterialSchema,
  materials: z.array(StudyMaterialSchema),
  currentScopedProjectId: z.string(),
  currentInternalProjectId: z.string(),
})
export type SubjectContext = z.infer<typeof SubjectContextSchema>

const SubjectListSchema = z.array(SubjectSchema)
const CreateSubjectResultSchema = z.object({
  subjectId: z.string(),
})
const StudyMaterialListSchema = z.array(StudyMaterialSchema)

export function listSubjects() {
  return apiRequest({ path: "/subjects", responseSchema: SubjectListSchema })
}

export function createSubject(title: string) {
  return apiRequest({
    path: "/subjects",
    method: "POST",
    body: { title },
    responseSchema: CreateSubjectResultSchema,
  })
}

export function editSubject(subjectId: string, title: string) {
  return apiRequest({
    path: `/subjects/${subjectId}`,
    method: "PATCH",
    body: { title },
    responseSchema: z.null(),
  })
}

export function deleteSubject(subjectId: string) {
  return apiRequest({
    path: `/subjects/${subjectId}`,
    method: "DELETE",
    responseSchema: z.null(),
  })
}

export function listSubjectMaterials(subjectId: string) {
  return apiRequest({
    path: `/subjects/${subjectId}/materials`,
    responseSchema: StudyMaterialListSchema,
  })
}

export function createSubjectMaterial(subjectId: string, params: { materialType: StudyMaterialType; title?: string }) {
  return apiRequest({
    path: `/subjects/${subjectId}/materials`,
    method: "POST",
    body: params,
    responseSchema: StudyMaterialSchema,
  })
}

export function editSubjectMaterial(subjectId: string, materialId: string, title: string) {
  return apiRequest({
    path: `/subjects/${subjectId}/materials/${materialId}`,
    method: "PATCH",
    body: { title },
    responseSchema: StudyMaterialSchema,
  })
}

export function deleteSubjectMaterial(subjectId: string, materialId: string) {
  return apiRequest({
    path: `/subjects/${subjectId}/materials/${materialId}`,
    method: "DELETE",
    responseSchema: z.null(),
  })
}

export function getProjectSubjectContext(scope: ScopedProjectRef) {
  return apiRequest({
    path: projectApiPath(scope, "/subject-context"),
    responseSchema: SubjectContextSchema,
  })
}

import { useMemo } from "react"
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  createSubject,
  createSubjectMaterial,
  deleteSubject,
  deleteSubjectMaterial,
  editSubject,
  editSubjectMaterial,
  getProjectSubjectContext,
  listSubjectMaterials,
  listSubjects,
  type StudyMaterialType,
} from "@/ui/api/subjects"
import type { ScopedProjectRef } from "@/ui/api/projectScope"
import { isVirtualStudyReviewProjectId } from "@/ui/guideWalkthrough/guideVirtualProjectIds"
import {
  getVirtualStudyReviewSubjectContext,
} from "@/ui/guideWalkthrough/virtualStudyReviewProject"

export function useSubjects(enabled = true) {
  return useQuery({ queryKey: ["subjects"], queryFn: listSubjects, enabled })
}

export type SubjectProjectCatalogItem = {
  subjectId: string
  subjectTitle: string
  projectId: string
  title: string
  materialId: string
  materialType: StudyMaterialType
  createdAt: string
}

export function useSubjectProjectCatalog(enabled = true) {
  const subjectsQ = useSubjects(enabled)
  const materialQs = useQueries({
    queries: (subjectsQ.data ?? []).map((subject) => ({
      queryKey: ["subjectMaterials", subject.subjectId],
      queryFn: () => listSubjectMaterials(subject.subjectId),
      enabled: enabled && !subjectsQ.isLoading && !subjectsQ.error,
      staleTime: 60_000,
    })),
  })
  const projects = useMemo<SubjectProjectCatalogItem[]>(
    () =>
      (subjectsQ.data ?? []).flatMap((subject, index) =>
        (materialQs[index]?.data ?? [])
          .filter((material) => Boolean(material.scopedProjectId))
          .map((material) => ({
            subjectId: subject.subjectId,
            subjectTitle: subject.title,
            projectId: material.scopedProjectId as string,
            title: material.title,
            materialId: material.materialId,
            materialType: material.materialType,
            createdAt: material.createdAt,
          })),
      ),
    [materialQs, subjectsQ.data],
  )

  return {
    subjectsQ,
    materialQs,
    projects,
    isLoading: subjectsQ.isLoading || materialQs.some((query) => query.isLoading),
    error: subjectsQ.error ?? materialQs.find((query) => query.error)?.error ?? null,
  }
}

export function useCreateSubject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: { title: string }) => createSubject(p.title),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["subjects"] }),
        qc.invalidateQueries({ queryKey: ["projects"] }),
      ])
    },
  })
}

export function useEditSubject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: { subjectId: string; title: string }) => editSubject(params.subjectId, params.title),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["subjects"] }),
        qc.invalidateQueries({ queryKey: ["subjectContext"] }),
        qc.invalidateQueries({ queryKey: ["projects"] }),
      ])
    },
  })
}

export function useDeleteSubject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (subjectId: string) => deleteSubject(subjectId),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["subjects"] }),
        qc.invalidateQueries({ queryKey: ["subjectMaterials"] }),
        qc.invalidateQueries({ queryKey: ["projects"] }),
        qc.invalidateQueries({ queryKey: ["subjectContext"] }),
      ])
    },
  })
}

export function useSubjectMaterials(subjectId: string) {
  return useQuery({
    queryKey: ["subjectMaterials", subjectId],
    queryFn: () => listSubjectMaterials(subjectId),
    enabled: !!subjectId,
  })
}

export function useSubjectContext(scope: ScopedProjectRef | null, enabled = true) {
  const projectId = scope?.scopedProjectId ?? ""
  return useQuery({
    queryKey: ["subjectContext", scope?.subjectId ?? "", projectId],
    queryFn: () =>
      isVirtualStudyReviewProjectId(projectId)
        ? getVirtualStudyReviewSubjectContext()
        : getProjectSubjectContext(scope as ScopedProjectRef),
    enabled: enabled && !!scope?.subjectId && !!projectId,
    staleTime: 30_000,
  })
}

export function useScopedSubjectContext(subjectId: string, projectId: string, enabled = true) {
  const scope = subjectId && projectId ? { subjectId, scopedProjectId: projectId } : null
  return useQuery({
    queryKey: ["subjectContext", subjectId, projectId],
    queryFn: () =>
      isVirtualStudyReviewProjectId(projectId)
        ? getVirtualStudyReviewSubjectContext()
        : getProjectSubjectContext(scope as ScopedProjectRef),
    enabled: enabled && !!scope,
    staleTime: 30_000,
  })
}

export function useCreateSubjectMaterial() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: { subjectId: string; materialType: StudyMaterialType; title?: string }) =>
      createSubjectMaterial(params.subjectId, { materialType: params.materialType, title: params.title }),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["subjectMaterials"] }),
        qc.invalidateQueries({ queryKey: ["subjectContext"] }),
        qc.invalidateQueries({ queryKey: ["projects"] }),
        qc.invalidateQueries({ queryKey: ["subjects"] }),
      ])
    },
  })
}

export function useEditSubjectMaterial() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: { subjectId: string; materialId: string; title: string }) =>
      editSubjectMaterial(params.subjectId, params.materialId, params.title),
    onSuccess: async (_data, variables) => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["subjectMaterials", variables.subjectId] }),
        qc.invalidateQueries({ queryKey: ["subjectContext"] }),
        qc.invalidateQueries({ queryKey: ["projects"] }),
      ])
    },
  })
}

export function useDeleteSubjectMaterial() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: { subjectId: string; materialId: string }) =>
      deleteSubjectMaterial(params.subjectId, params.materialId),
    onSuccess: async (_data, variables) => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["subjectMaterials", variables.subjectId] }),
        qc.invalidateQueries({ queryKey: ["subjects"] }),
        qc.invalidateQueries({ queryKey: ["projects"] }),
        qc.invalidateQueries({ queryKey: ["subjectContext"] }),
      ])
    },
  })
}

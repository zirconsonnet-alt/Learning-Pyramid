import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

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

export function useSubjects(enabled = true) {
  return useQuery({ queryKey: ["subjects"], queryFn: listSubjects, enabled })
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

export function useSubjectContext(projectId: string, enabled = true) {
  return useQuery({
    queryKey: ["subjectContext", projectId],
    queryFn: () => getProjectSubjectContext(projectId),
    enabled: enabled && !!projectId,
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

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  createProject,
  deleteProject,
  editProject,
  getProjectMaterialSourceBinding,
  listProjects,
  type MaterialSourceKind,
  type ProjectType,
} from "@/ui/api/projects"
import { isVirtualStudyReviewProjectId } from "@/ui/guideWalkthrough/guideVirtualProjectIds"
import {
  getVirtualStudyReviewProject,
  getVirtualStudyReviewProjectMaterialSourceBinding,
} from "@/ui/guideWalkthrough/virtualStudyReviewProject"

const PROJECT_BINDING_QUERY_TIMEOUT_MS = 90_000

export function useProjects(enabled = true) {
  return useQuery({ queryKey: ["projects"], queryFn: listProjects, enabled })
}

export function useProject(projectId?: string, options?: { enabled?: boolean; subjectId?: string }) {
  const isVirtualProject = isVirtualStudyReviewProjectId(projectId)
  const query = useProjects((options?.enabled ?? true) && !isVirtualProject)
  const project =
    isVirtualProject
      ? getVirtualStudyReviewProject()
      : projectId
        ? query.data?.find((item) => {
            if (item.projectId !== projectId) return false
            if (options?.subjectId && item.subjectId && item.subjectId !== options.subjectId) return false
            if (options?.subjectId && !item.subjectId) return false
            return true
          }) ?? null
        : null

  return {
    ...query,
    project,
    projectTitle: project?.title ?? (projectId ? (query.isLoading ? "加载项目中..." : "未知项目") : "未选择项目"),
  }
}

export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: { title: string; initialProjectType?: ProjectType; initialSourceKind?: MaterialSourceKind }) =>
      createProject(p.title, {
        initialProjectType: p.initialProjectType,
        initialSourceKind: p.initialSourceKind,
      }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["projects"] })
    },
  })
}

export function useDeleteProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (projectId: string) => deleteProject(projectId),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["projects"] })
    },
  })
}

export function useEditProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (params: { projectId: string; title: string }) => editProject(params.projectId, params.title),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["projects"] })
    },
  })
}

export function useProjectMaterialSourceBinding(projectId: string) {
  return useQuery({
    queryKey: ["projectMaterialSourceBinding", projectId],
    queryFn: ({ signal }) =>
      isVirtualStudyReviewProjectId(projectId)
        ? getVirtualStudyReviewProjectMaterialSourceBinding()
        : getProjectMaterialSourceBinding(projectId, { signal, timeoutMs: PROJECT_BINDING_QUERY_TIMEOUT_MS }),
    enabled: !!projectId,
    refetchInterval: isVirtualStudyReviewProjectId(projectId) ? false : 5000,
  })
}

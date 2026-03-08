import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { createProject, deleteProject, listProjects } from "@/ui/api/projects"

export function useProjects() {
  return useQuery({ queryKey: ["projects"], queryFn: listProjects })
}

export function useProject(projectId?: string) {
  const query = useProjects()
  const project = projectId ? query.data?.find((item) => item.projectId === projectId) ?? null : null

  return {
    ...query,
    project,
    projectTitle: project?.title ?? (projectId ? (query.isLoading ? "加载项目中..." : "未知项目") : "未选择项目"),
  }
}

export function useCreateProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (p: { title: string }) => createProject(p.title),
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

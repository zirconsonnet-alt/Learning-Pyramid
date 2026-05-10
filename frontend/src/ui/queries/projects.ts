import { useQuery } from "@tanstack/react-query"

import {
  getProjectMaterialSourceBinding,
} from "@/ui/api/projects"
import type { ProjectScope } from "@/ui/api/projectScope"
import { isVirtualStudyReviewProjectId } from "@/ui/guideWalkthrough/guideVirtualProjectIds"
import {
  getVirtualStudyReviewProject,
  getVirtualStudyReviewProjectMaterialSourceBinding,
} from "@/ui/guideWalkthrough/virtualStudyReviewProject"
import { useSubjectContext } from "@/ui/queries/subjects"

const PROJECT_BINDING_QUERY_TIMEOUT_MS = 90_000

export function useProject(scope?: ProjectScope | null, options?: { enabled?: boolean }) {
  const projectId = scope?.projectId ?? ""
  const isVirtualProject = isVirtualStudyReviewProjectId(projectId)
  const query = useSubjectContext(scope ?? null, (options?.enabled ?? true) && Boolean(projectId) && !isVirtualProject)
  const currentMaterial = query.data?.currentMaterial ?? null
  let project = null
  if (isVirtualProject) {
    project = getVirtualStudyReviewProject()
  } else if (currentMaterial && currentMaterial.projectId === projectId) {
    project = {
      subjectId: currentMaterial.subjectId,
      projectId: currentMaterial.projectId,
      title: currentMaterial.title,
      state: "ACTIVE",
      createdAt: currentMaterial.createdAt,
      deletedAt: null,
    }
  }

  return {
    ...query,
    project,
    projectTitle: project?.title ?? (projectId ? (query.isLoading ? "加载项目中..." : "未知项目") : "未选择项目"),
  }
}

export function useProjectMaterialSourceBinding(scope: ProjectScope | null) {
  const projectId = scope?.projectId ?? ""
  return useQuery({
    queryKey: ["projectMaterialSourceBinding", scope?.subjectId ?? "", projectId],
    queryFn: ({ signal }) =>
      isVirtualStudyReviewProjectId(projectId)
        ? getVirtualStudyReviewProjectMaterialSourceBinding()
        : getProjectMaterialSourceBinding(scope as ProjectScope, { signal, timeoutMs: PROJECT_BINDING_QUERY_TIMEOUT_MS }),
    enabled: !!scope?.subjectId && !!projectId,
    refetchInterval: isVirtualStudyReviewProjectId(projectId) ? false : 5000,
  })
}

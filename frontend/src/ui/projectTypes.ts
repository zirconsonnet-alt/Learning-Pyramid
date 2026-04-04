import type { ProjectType } from "@/ui/api/projects"

export function formatProjectTypeLabel(projectType: ProjectType) {
  if (projectType === "COURSE") return "网课"
  if (projectType === "BOOK") return "书本"
  return "零散知识点"
}

export function projectTypeRequiresLearningObjectTree(projectType: ProjectType) {
  return projectType === "COURSE" || projectType === "BOOK"
}

export function projectTypeRequiresAnchor(projectType: ProjectType) {
  return projectType === "COURSE" || projectType === "BOOK"
}

export function projectTypeUsesResolvableCourseAnchor(projectType: ProjectType) {
  return projectType === "COURSE"
}

export type LearningContextStatus = "no-subject" | "subject-only" | "project" | "invalid"

export type MobileContextScope = "none" | "subject" | "project" | "account" | "system"

export type ProjectShellDestinationId = "learning" | "ai" | "review" | "structure" | "mine"

export type ContextMenuItemId =
  | "select-subject"
  | "switch-subject"
  | "subject-settings"
  | "select-project"
  | "switch-project"
  | "project-settings"
  | "subject-center"
  | "project-center"

export type LearningContextInput = {
  invalid?: boolean
  projectTitle?: string | null
  projectType?: string | null
  scopedProjectId?: string | null
  subjectId?: string | null
  subjectTitle?: string | null
}

export type MobileRouteTarget = {
  params?: Record<string, string>
  pathname: string
}

export type NavigationDestination = {
  id: ProjectShellDestinationId
  label: string
  requiredScope: MobileContextScope
}

export type ContextMenuItem = {
  id: ContextMenuItemId
  label: string
  requiredScope: MobileContextScope
  target?: MobileRouteTarget
}

export const PROJECT_SHELL_DESTINATIONS: NavigationDestination[] = [
  { id: "learning", label: "学习", requiredScope: "project" },
  { id: "ai", label: "AI", requiredScope: "project" },
  { id: "review", label: "复习", requiredScope: "project" },
  { id: "structure", label: "结构", requiredScope: "project" },
  { id: "mine", label: "我的", requiredScope: "account" },
]

export function getLearningContextStatus(context: LearningContextInput): LearningContextStatus {
  if (context.invalid) return "invalid"
  if (!context.subjectId) return "no-subject"
  if (!context.scopedProjectId) return "subject-only"
  return "project"
}

export function getVisibleScopedSettings(context: LearningContextInput) {
  const status = getLearningContextStatus(context)
  return {
    projectSettings: status === "project",
    subjectSettings: status === "subject-only" || status === "project",
  }
}

export function getRouteGuardTarget(requiredScope: MobileContextScope, context: LearningContextInput): MobileRouteTarget | null {
  if (requiredScope === "none" || requiredScope === "account" || requiredScope === "system") return null

  if (!context.subjectId || context.invalid) return { pathname: "/" }

  if (requiredScope === "subject") return null

  if (!context.scopedProjectId) {
    return { pathname: "/subject/[subjectId]", params: { subjectId: context.subjectId } }
  }

  return null
}

export function buildContextMenuItems(context: LearningContextInput): ContextMenuItem[] {
  const status = getLearningContextStatus(context)

  if (status === "no-subject" || status === "invalid") {
    return [{ id: "select-subject", label: "选择学科", requiredScope: "none", target: { pathname: "/" } }]
  }

  if (status === "subject-only") {
    return [
      { id: "switch-subject", label: "切换学科", requiredScope: "subject", target: { pathname: "/" } },
      {
        id: "subject-settings",
        label: "学科设置",
        requiredScope: "subject",
        target: { pathname: "/subject/[subjectId]/settings", params: { subjectId: context.subjectId ?? "" } },
      },
      {
        id: "select-project",
        label: "选择项目",
        requiredScope: "subject",
        target: { pathname: "/subject/[subjectId]", params: { subjectId: context.subjectId ?? "" } },
      },
      { id: "subject-center", label: "学科中心", requiredScope: "none", target: { pathname: "/" } },
    ]
  }

  return [
    { id: "switch-subject", label: "切换学科", requiredScope: "subject", target: { pathname: "/" } },
    {
      id: "subject-settings",
      label: "学科设置",
      requiredScope: "subject",
      target: { pathname: "/subject/[subjectId]/settings", params: { subjectId: context.subjectId ?? "" } },
    },
    {
      id: "switch-project",
      label: "切换项目",
      requiredScope: "project",
      target: { pathname: "/subject/[subjectId]", params: { subjectId: context.subjectId ?? "" } },
    },
    {
      id: "project-settings",
      label: "项目设置",
      requiredScope: "project",
      target: {
        pathname: "/project-settings/[subjectId]/[scopedProjectId]",
        params: { scopedProjectId: context.scopedProjectId ?? "", subjectId: context.subjectId ?? "" },
      },
    },
    { id: "subject-center", label: "学科中心", requiredScope: "none", target: { pathname: "/" } },
    {
      id: "project-center",
      label: "项目中心",
      requiredScope: "subject",
      target: { pathname: "/subject/[subjectId]", params: { subjectId: context.subjectId ?? "" } },
    },
  ]
}

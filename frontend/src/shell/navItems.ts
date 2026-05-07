import type { LucideIcon } from "lucide-react"
import { BookOpenText, Bot, Clock3, FolderKanban, LayoutDashboard, PanelsTopLeft, Settings2, Shield, Waypoints, Workflow } from "lucide-react"

import { buildGlobalSettingsPath } from "@/views/settings/globalSettingsRouting"

export type NavItem = {
  to: string
  label: string
  icon: LucideIcon
  guideTourAnchor?: string
}

const BASE_GLOBAL_NAV_ITEMS: NavItem[] = [
  { to: "/projects", label: "学科中心", icon: FolderKanban },
  { to: "/guide", label: "用户指南", icon: BookOpenText },
  { to: buildGlobalSettingsPath(), label: "全局设置", icon: Settings2 },
]

export function getGlobalNavItems(options?: { includeAdmin?: boolean; includeMembership?: boolean }) {
  const items = [...BASE_GLOBAL_NAV_ITEMS]
  if (options?.includeAdmin) {
    items.push({ to: "/admin", label: "后台管理", icon: Shield })
  }
  return items
}

export function getSubjectNavItems(subjectId: string, subjectProjectId: string) {
  if (!subjectId || !subjectProjectId) return []
  return [
    { to: `/subjects/${subjectId}`, label: "项目中心", icon: LayoutDashboard },
    { to: `/p/${subjectProjectId}/settings`, label: "学科设置", icon: Settings2 },
  ] satisfies NavItem[]
}

export function getProjectNavItems(pid: string, options?: { includeObjectTree?: boolean; settingsLabel?: string; settingsTo?: string }): NavItem[] {
  if (!pid) return []
  const items: NavItem[] = [
    { to: `/p/${pid}/workbench`, label: "工作台", icon: PanelsTopLeft, guideTourAnchor: "workbench-nav" },
    { to: `/p/${pid}/ai-chat`, label: "AI问答", icon: Bot },
    { to: `/p/${pid}/recommended-reviews`, label: "推荐复习", icon: Clock3 },
    { to: `/p/${pid}/task-tree`, label: "学习任务树", icon: Waypoints },
    { to: options?.settingsTo ?? `/p/${pid}/settings`, label: options?.settingsLabel ?? "项目设置", icon: Settings2, guideTourAnchor: "project-settings-nav" },
  ]
  if (options?.includeObjectTree ?? true) {
    items.splice(4, 0, { to: `/p/${pid}/object-tree`, label: "学习对象树", icon: Workflow })
  }
  return items
}

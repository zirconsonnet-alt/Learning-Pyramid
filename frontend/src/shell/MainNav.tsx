import type { LucideIcon } from "lucide-react"
import { BookOpenText, FolderKanban, PanelsTopLeft, Settings2, Waypoints, Workflow } from "lucide-react"
import { NavLink } from "react-router-dom"

import { cn } from "@/ui/utils"

export type NavItem = {
  to: string
  label: string
  icon: LucideIcon
}

export const GLOBAL_NAV_ITEMS: NavItem[] = [
  { to: "/projects", label: "项目中心", icon: FolderKanban },
  { to: "/guide", label: "用户指南", icon: BookOpenText },
]

export function getProjectNavItems(pid: string): NavItem[] {
  if (!pid) return []
  return [
    { to: `/p/${pid}/workbench`, label: "工作台", icon: PanelsTopLeft },
    { to: `/p/${pid}/task-tree`, label: "学习任务树", icon: Waypoints },
    { to: `/p/${pid}/object-tree`, label: "学习对象树", icon: Workflow },
    { to: `/p/${pid}/settings`, label: "项目设置", icon: Settings2 },
  ]
}

export function MainNav(props: { items: NavItem[]; onNavigate?: () => void; className?: string }) {
  const { items, onNavigate, className } = props

  return (
    <nav className={cn("flex w-full flex-col gap-1 text-sm", className)}>
      {items.map((item) => {
        const Icon = item.icon
        return (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                "group flex min-h-11 w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-sm transition-all duration-200",
                isActive
                  ? "bg-primary text-primary-foreground shadow-[0_18px_36px_-28px_rgba(30,58,95,0.4)]"
                  : "text-[#41546e] hover:bg-[#f4f7fb] hover:text-foreground",
              )
            }
          >
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-[#edf4ff] text-primary transition-colors group-hover:bg-white">
              <Icon className="h-4 w-4" />
            </span>
            <span className="min-w-0 truncate">{item.label}</span>
          </NavLink>
        )
      })}
    </nav>
  )
}

import type { LucideIcon } from "lucide-react"
import { BookOpenText, Clock3, FolderKanban, PanelsTopLeft, Settings2, Shield, UsersRound, Waypoints, Workflow } from "lucide-react"
import { NavLink } from "react-router-dom"

import { cn } from "@/ui/utils"

export type NavItem = {
  to: string
  label: string
  icon: LucideIcon
}

const BASE_GLOBAL_NAV_ITEMS: NavItem[] = [
  { to: "/projects", label: "项目中心", icon: FolderKanban },
  { to: "/friends", label: "好友", icon: UsersRound },
  { to: "/guide", label: "用户指南", icon: BookOpenText },
]

export function getGlobalNavItems(options?: { includeAdmin?: boolean; includeMembership?: boolean }): NavItem[] {
  const items = options?.includeMembership ? [...BASE_GLOBAL_NAV_ITEMS] : BASE_GLOBAL_NAV_ITEMS.filter((item) => item.to !== "/membership")
  if (options?.includeAdmin) {
    items.push({ to: "/admin", label: "后台管理", icon: Shield })
  }
  return items
}

export function getProjectNavItems(pid: string, options?: { includeObjectTree?: boolean }): NavItem[] {
  if (!pid) return []
  const items: NavItem[] = [
    { to: `/p/${pid}/workbench`, label: "工作台", icon: PanelsTopLeft },
    { to: `/p/${pid}/recommended-reviews`, label: "推荐复习", icon: Clock3 },
    { to: `/p/${pid}/task-tree`, label: "学习任务树", icon: Waypoints },
    { to: `/p/${pid}/settings`, label: "项目设置", icon: Settings2 },
  ]
  if (options?.includeObjectTree ?? true) {
    items.splice(3, 0, { to: `/p/${pid}/object-tree`, label: "学习对象树", icon: Workflow })
  }
  return items
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
            className="block"
          >
            {({ isActive }) => (
              <div
                className={cn(
                  "group flex min-h-11 w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-sm transition-all duration-200",
                  isActive
                    ? "bg-primary text-primary-foreground shadow-[0_18px_36px_-28px_hsl(var(--primary)/0.42)]"
                    : "text-[color:var(--theme-subtle-text)] hover:[background:var(--theme-soft-bg)] hover:text-foreground",
                )}
              >
                <span
                  className={cn(
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border transition-colors",
                    isActive
                      ? "border-white/15 bg-white/12 text-white"
                      : "[border-color:var(--theme-icon-border)] [background:var(--theme-icon-bg)] [color:var(--theme-icon-text)] group-hover:bg-white",
                  )}
                >
                  <Icon className="h-4 w-4" />
                </span>
                <span className="min-w-0 truncate">{item.label}</span>
              </div>
            )}
          </NavLink>
        )
      })}
    </nav>
  )
}

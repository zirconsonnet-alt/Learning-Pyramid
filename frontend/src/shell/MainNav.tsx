import type { LucideIcon } from "lucide-react"
import { BookOpenText, CircleUserRound, CreditCard, FolderKanban, PanelsTopLeft, Settings2, Shield, UsersRound, Waypoints, Workflow } from "lucide-react"
import { NavLink } from "react-router-dom"

import { cn } from "@/ui/utils"

export type NavItem = {
  to: string
  label: string
  icon: LucideIcon
}

const BASE_GLOBAL_NAV_ITEMS: NavItem[] = [
  { to: "/projects", label: "项目中心", icon: FolderKanban },
  { to: "/groups", label: "学习小组", icon: UsersRound },
  { to: "/membership", label: "会员中心", icon: CreditCard },
  { to: "/profile", label: "个人资料", icon: CircleUserRound },
  { to: "/guide", label: "用户指南", icon: BookOpenText },
]

export function getGlobalNavItems(options?: { includeAdmin?: boolean; includeMembership?: boolean }): NavItem[] {
  const items = options?.includeMembership ? [...BASE_GLOBAL_NAV_ITEMS] : BASE_GLOBAL_NAV_ITEMS.filter((item) => item.to !== "/membership")
  if (options?.includeAdmin) {
    items.push({ to: "/admin", label: "后台管理", icon: Shield })
  }
  return items
}

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
            className="block"
          >
            {({ isActive }) => (
              <div
                className={cn(
                  "group flex min-h-11 w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-sm transition-all duration-200",
                  isActive
                    ? "bg-primary text-primary-foreground shadow-[0_18px_36px_-28px_rgba(37,99,235,0.48)]"
                    : "text-[#42566f] hover:bg-[#f5f7fa] hover:text-foreground",
                )}
              >
                <span
                  className={cn(
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border transition-colors",
                    isActive
                      ? "border-white/15 bg-white/12 text-white"
                      : "border-[#e1e8f0] bg-[#f5f7fa] text-primary group-hover:bg-white",
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

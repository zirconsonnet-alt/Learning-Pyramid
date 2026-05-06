import { NavLink } from "react-router-dom"

import type { NavItem } from "@/shell/navItems"
import { cn } from "@/ui/utils"

export function MainNav(props: { items: NavItem[]; onNavigate?: () => void; className?: string }) {
  const { items, onNavigate, className } = props

  return (
    <nav className={cn("flex w-full flex-col text-sm", className)}>
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
                data-guide-tour={item.guideTourAnchor}
                className={cn(
                  "group flex min-h-11 w-full items-center gap-3 border-b border-border/55 px-1 py-3 text-sm transition-colors duration-200 last:border-b-0",
                  isActive
                    ? "text-primary"
                    : "text-[color:var(--theme-subtle-text)] hover:text-foreground",
                )}
              >
                <span
                  className={cn(
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border transition-colors",
                    isActive
                      ? "border-primary/20 bg-primary/10 text-primary"
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

import { NavLink } from "react-router-dom"
import { CreditCard, LayoutDashboard, UsersRound, type LucideIcon } from "lucide-react"

import { cn } from "@/ui/utils"

const items: Array<{ to: string; label: string; description: string; icon: LucideIcon }> = [
  { to: "/admin", label: "总览", description: "运营控制台", icon: LayoutDashboard },
  { to: "/admin/membership", label: "会员", description: "订单与提现", icon: CreditCard },
  { to: "/admin/users", label: "用户", description: "账号与权限", icon: UsersRound },
]

export function AdminNav() {
  return (
    <div className="grid gap-2 sm:grid-cols-3">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === "/admin"}
          aria-label={`进入${item.label}`}
          className={({ isActive }) =>
            cn(
              "group flex min-h-[4.25rem] items-center gap-3 rounded-2xl border px-4 py-3 text-sm transition-all duration-200",
              isActive
                ? "border-primary/20 bg-[hsl(var(--primary)/0.08)] text-foreground shadow-[0_18px_36px_-28px_hsl(var(--primary)/0.32)]"
                : "[border-color:var(--theme-soft-border)] [background:var(--theme-soft-bg)] text-[color:var(--theme-subtle-text)] hover:border-primary/20 hover:bg-white hover:text-foreground",
            )
          }
        >
          {({ isActive }) => {
            const Icon = item.icon
            return (
              <>
                <span
                  className={cn(
                    "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-colors",
                    isActive
                      ? "bg-primary text-primary-foreground shadow-[0_14px_28px_-18px_hsl(var(--primary)/0.72)]"
                      : "bg-[color:var(--theme-icon-bg)] text-[color:var(--theme-icon-text)] group-hover:bg-white group-hover:text-foreground",
                  )}
                >
                  <Icon className="h-4 w-4" />
                </span>
                <span className="min-w-0">
                  <span className="block font-semibold">{item.label}</span>
                  <span className="mt-0.5 block text-xs text-muted-foreground">{item.description}</span>
                </span>
              </>
            )
          }}
        </NavLink>
      ))}
    </div>
  )
}

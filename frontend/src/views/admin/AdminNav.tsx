import { NavLink } from "react-router-dom"

import { cn } from "@/ui/utils"

const items = [
  { to: "/admin", label: "总览" },
  { to: "/admin/membership", label: "会员" },
  { to: "/admin/users", label: "用户" },
  { to: "/admin/groups", label: "小组" },
]

export function AdminNav() {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === "/admin"}
          className={({ isActive }) =>
            cn(
              "inline-flex items-center rounded-xl border px-4 py-2 text-sm transition-all duration-200",
              isActive
                ? "border-primary/20 bg-[#eef5ff] font-medium text-[#1d4f8f]"
                : "border-[#dde5ee] bg-white text-[#5b6b82] hover:border-primary/20 hover:bg-[#f8fbff] hover:text-foreground",
            )
          }
        >
          {item.label}
        </NavLink>
      ))}
    </div>
  )
}

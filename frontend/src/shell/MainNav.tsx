import { NavLink, useParams } from "react-router-dom"

import { cn } from "@/ui/utils"

export function MainNav() {
  const { projectId } = useParams()
  const pid = projectId ?? ""

  const globalLinks = [
    { to: "/guide", label: "用户指南" },
  ]

  const projectLinks = pid
    ? [
        { to: `/p/${pid}/workbench`, label: "工作台" },
        { to: `/p/${pid}/task-tree`, label: "学习任务树" },
        { to: `/p/${pid}/object-tree`, label: "学习对象树" },
        { to: `/p/${pid}/timeline`, label: "时间线" },
      ]
    : []

  const itemClassName = ({ isActive }: { isActive: boolean }) =>
    cn(
      "relative inline-flex h-10 items-center rounded-xl px-3 text-sm transition-colors",
      isActive
        ? "bg-white text-foreground shadow-[0_8px_20px_-18px_rgba(30,58,95,0.42)] after:absolute after:bottom-0 after:left-3 after:right-3 after:h-0.5 after:rounded-full after:bg-primary"
        : "text-[#5b6b82] hover:bg-accent/70 hover:text-foreground",
    )

  return (
    <nav className="flex w-full flex-wrap items-center gap-1 text-sm lg:ml-auto lg:w-auto lg:flex-nowrap lg:justify-end">
      <div className="flex flex-wrap items-center gap-1 rounded-2xl border border-white/70 bg-white/62 p-1 shadow-[0_12px_30px_-26px_rgba(15,23,42,0.28)]">
        {globalLinks.map((item) => (
          <NavLink key={item.to} to={item.to} className={itemClassName}>
            {item.label}
          </NavLink>
        ))}
      </div>
      {pid ? (
        <>
          <div className="mx-1 hidden h-5 w-px bg-border/80 lg:block" />
          <div className="flex flex-wrap items-center gap-1 rounded-2xl border border-white/70 bg-white/62 p-1 shadow-[0_12px_30px_-26px_rgba(15,23,42,0.28)]">
            {projectLinks.map((item) => (
              <NavLink key={item.to} to={item.to} className={itemClassName}>
                {item.label}
              </NavLink>
            ))}
            <NavLink to={`/p/${pid}/settings`} className={({ isActive }) => cn(itemClassName({ isActive }), "shrink-0")}>
              项目设置
            </NavLink>
          </div>
        </>
      ) : null}
    </nav>
  )
}

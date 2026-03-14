import type { LucideIcon } from "lucide-react"
import { BookOpenText, FolderKanban, PanelsTopLeft, RadioTower, Settings2, TimerReset, Waypoints, Workflow } from "lucide-react"
import { NavLink, useParams } from "react-router-dom"

import { useSystemCapabilities } from "@/ui/queries/system"
import { cn } from "@/ui/utils"

type NavItem = {
  to: string
  label: string
  icon: LucideIcon
}

type MainNavVariant = "header" | "drawer"

function NavGroup(props: { title: string; items: NavItem[]; variant: MainNavVariant; onNavigate?: () => void }) {
  const { title, items, variant, onNavigate } = props
  const itemClassName = ({ isActive }: { isActive: boolean }) =>
    variant === "drawer"
      ? cn(
          "group flex h-12 w-full items-center gap-3 rounded-2xl px-4 text-sm transition-all duration-200",
          isActive
            ? "bg-primary text-primary-foreground shadow-[0_18px_36px_-28px_rgba(30,58,95,0.4)]"
            : "bg-white/88 text-[#41546e] hover:bg-white hover:text-foreground",
        )
      : cn(
          "group relative inline-flex h-10 shrink-0 items-center gap-2 rounded-xl px-3 text-[13px] transition-all duration-200 sm:h-11 sm:rounded-2xl sm:px-3.5 sm:text-sm",
          isActive
            ? "bg-white text-foreground shadow-[0_18px_36px_-28px_rgba(30,58,95,0.36)] after:absolute after:bottom-1.5 after:left-3 after:right-3 after:h-0.5 after:rounded-full after:bg-primary sm:after:left-4 sm:after:right-4"
            : "text-[#5b6b82] hover:bg-white/78 hover:text-foreground",
        )

  return (
    <div
      className={cn(
        variant === "drawer"
          ? "flex flex-col gap-3 rounded-[1.5rem] border border-white/80 bg-white/68 p-3 shadow-[0_18px_40px_-34px_rgba(15,23,42,0.28)]"
          : "flex items-center gap-2 rounded-[1.2rem] border border-white/70 bg-white/55 p-1.5 shadow-[0_14px_32px_-28px_rgba(15,23,42,0.22)] sm:flex-col sm:items-stretch sm:gap-2 sm:p-2",
      )}
    >
      <div
        className={cn(
          variant === "drawer"
            ? "px-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-[#73839a]"
            : "shrink-0 rounded-full bg-white/82 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[#73839a] sm:bg-transparent sm:px-2 sm:py-0 sm:text-[11px]",
        )}
      >
        {title}
      </div>
      <div
        className={cn(
          variant === "drawer"
            ? "flex flex-col gap-2"
            : "flex min-w-0 items-center gap-1 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden sm:flex-wrap sm:overflow-visible sm:pb-0",
        )}
      >
        {items.map((item) => {
          const Icon = item.icon
          return (
            <NavLink key={item.to} to={item.to} className={itemClassName} onClick={onNavigate}>
              <span
                className={cn(
                  variant === "drawer"
                    ? "flex h-8 w-8 items-center justify-center rounded-xl bg-[#edf4ff] text-primary transition-colors group-hover:bg-white group-hover:text-primary group-[.active]:bg-white/20"
                    : "flex h-7 w-7 items-center justify-center rounded-lg bg-[#eef4ff] text-primary transition-colors group-hover:bg-white group-hover:text-primary sm:rounded-xl",
                )}
              >
                <Icon className="h-4 w-4" />
              </span>
              <span>{item.label}</span>
            </NavLink>
          )
        })}
      </div>
    </div>
  )
}

export function MainNav(props: { variant?: MainNavVariant; onNavigate?: () => void }) {
  const { variant = "header", onNavigate } = props
  const { projectId } = useParams()
  const pid = projectId ?? ""
  const capabilitiesQ = useSystemCapabilities()
  const isHostedMode = capabilitiesQ.data?.appMode === "hosted"

  const globalLinks: NavItem[] = [
    { to: "/projects", label: "项目中心", icon: FolderKanban },
    { to: "/guide", label: "用户指南", icon: BookOpenText },
    ...(isHostedMode
      ? [
          { to: "/system/desktop-agent", label: "Desktop Agent", icon: Workflow },
          { to: "/system/relay-monitor", label: "Relay Monitor", icon: RadioTower },
        ]
      : []),
  ]

  const projectLinks: NavItem[] = pid
    ? [
        { to: `/p/${pid}/workbench`, label: "工作台", icon: PanelsTopLeft },
        { to: `/p/${pid}/task-tree`, label: "学习任务树", icon: Waypoints },
        { to: `/p/${pid}/object-tree`, label: "学习对象树", icon: Workflow },
        { to: `/p/${pid}/timeline`, label: "时间线", icon: TimerReset },
        { to: `/p/${pid}/settings`, label: "项目设置", icon: Settings2 },
      ]
    : []

  return (
    <nav className={cn("flex w-full flex-col text-sm", variant === "drawer" ? "gap-3" : "gap-2")}>
      <NavGroup title="全局" items={globalLinks} variant={variant} onNavigate={onNavigate} />
      {pid ? <NavGroup title="当前项目" items={projectLinks} variant={variant} onNavigate={onNavigate} /> : null}
    </nav>
  )
}

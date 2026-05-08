import type { ReactNode } from "react"

import xuebaoIdle from "@/assets/xuebao-idle.gif"
import xuebaoRotation from "@/assets/xuebao-rotation.gif"
import xuebaoStand from "@/assets/xuebao-stand.png"
import { cn } from "@/ui/utils"

export function DesktopPet(props: { page?: "home" | "workbench"; children?: ReactNode }) {
  const page = props.page ?? "home"
  const hasPopover = page === "workbench" && !!props.children

  return (
    <aside
      className={cn("plm-desktop-pet", page === "workbench" ? "is-workbench" : "is-home", hasPopover && "has-popover")}
      aria-label="雪豹桌面宠物"
    >
      <div className="plm-desktop-pet-button" tabIndex={hasPopover ? 0 : undefined}>
        <span className="plm-desktop-pet-stage" aria-hidden="true">
          <img className="plm-desktop-pet-image plm-desktop-pet-stand" src={xuebaoStand} alt="" />
          <img className="plm-desktop-pet-image plm-desktop-pet-idle" src={xuebaoIdle} alt="" />
          <img className="plm-desktop-pet-image plm-desktop-pet-rotation" src={xuebaoRotation} alt="" />
        </span>
        <span className="plm-desktop-pet-shadow" aria-hidden="true" />
      </div>
      {hasPopover ? (
        <div className="plm-desktop-pet-popover" role="dialog" aria-label="雪豹桌面宠物问答">
          {props.children}
        </div>
      ) : null}
    </aside>
  )
}

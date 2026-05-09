import { useEffect, useId, useRef, useState, type ReactNode } from "react"
import { X } from "lucide-react"

import xuebaoIdle from "@/assets/xuebao-idle.gif"
import xuebaoRotation from "@/assets/xuebao-rotation.gif"
import xuebaoStand from "@/assets/xuebao-stand.png"
import { cn } from "@/ui/utils"

export function DesktopPet(props: { page?: "home" | "workbench"; assistantState?: "idle" | "thinking"; children?: ReactNode }) {
  const page = props.page ?? "home"
  const assistantState = props.assistantState ?? "idle"
  const hasPopover = page === "workbench" && !!props.children
  const [pinRequested, setPinRequested] = useState(false)
  const isPinned = hasPopover && pinRequested
  const popoverId = useId()
  const rootRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    if (!hasPopover || !isPinned) return

    const onPointerDown = (event: PointerEvent) => {
      const target = event.target
      if (!(target instanceof Node)) return
      if (rootRef.current?.contains(target)) return
      setPinRequested(false)
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setPinRequested(false)
    }

    document.addEventListener("pointerdown", onPointerDown)
    document.addEventListener("keydown", onKeyDown)
    return () => {
      document.removeEventListener("pointerdown", onPointerDown)
      document.removeEventListener("keydown", onKeyDown)
    }
  }, [hasPopover, isPinned])

  return (
    <aside
      ref={rootRef}
      className={cn(
        "plm-desktop-pet",
        page === "workbench" ? "is-workbench" : "is-home",
        hasPopover && "has-popover",
        isPinned && "is-pinned",
        assistantState === "thinking" && "is-thinking",
      )}
      aria-label="雪豹桌面宠物"
    >
      <button
        type="button"
        className="plm-desktop-pet-button"
        aria-expanded={isPinned}
        aria-controls={hasPopover ? popoverId : undefined}
        aria-label={hasPopover ? (isPinned ? "收起雪豹问答" : "固定展开雪豹问答") : "雪豹桌面宠物"}
        onClick={() => {
          if (hasPopover) setPinRequested((current) => !current)
        }}
      >
        <span className="plm-desktop-pet-stage" aria-hidden="true">
          <img className="plm-desktop-pet-image plm-desktop-pet-stand" src={xuebaoStand} alt="" />
          <img className="plm-desktop-pet-image plm-desktop-pet-idle" src={xuebaoIdle} alt="" />
          <img className="plm-desktop-pet-image plm-desktop-pet-rotation" src={xuebaoRotation} alt="" />
        </span>
        <span className="plm-desktop-pet-shadow" aria-hidden="true" />
        {assistantState === "thinking" ? <span className="plm-desktop-pet-status-dot" aria-hidden="true" /> : null}
      </button>
      {hasPopover ? (
        <div id={popoverId} className="plm-desktop-pet-popover" role="dialog" aria-label="雪豹桌面宠物问答">
          <button
            type="button"
            className="plm-desktop-pet-popover-close"
            aria-label="关闭雪豹问答"
            title="关闭雪豹问答"
            onClick={() => setPinRequested(false)}
          >
            <X className="h-4 w-4" />
          </button>
          {props.children}
        </div>
      ) : null}
    </aside>
  )
}

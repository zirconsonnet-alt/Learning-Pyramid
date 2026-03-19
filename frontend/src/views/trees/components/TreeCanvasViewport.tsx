import { useEffect, useRef, useState, type MouseEvent as ReactMouseEvent, type ReactNode } from "react"

import { cn } from "@/ui/utils"

export function TreeCanvasViewport({
  canvasHeight,
  canvasWidth,
  children,
}: {
  canvasHeight: number
  canvasWidth: number
  children: ReactNode
}) {
  const viewportRef = useRef<HTMLDivElement | null>(null)
  const dragStateRef = useRef<{
    startClientX: number
    startClientY: number
    startScrollLeft: number
    startScrollTop: number
  } | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  useEffect(() => {
    if (!isDragging) return

    const previousUserSelect = document.body.style.userSelect
    document.body.style.userSelect = "none"

    const handleMouseMove = (event: MouseEvent) => {
      const viewport = viewportRef.current
      const dragState = dragStateRef.current
      if (!viewport || !dragState) return

      viewport.scrollLeft = dragState.startScrollLeft - (event.clientX - dragState.startClientX)
      viewport.scrollTop = dragState.startScrollTop - (event.clientY - dragState.startClientY)
    }

    const handleMouseUp = () => {
      dragStateRef.current = null
      setIsDragging(false)
    }

    window.addEventListener("mousemove", handleMouseMove)
    window.addEventListener("mouseup", handleMouseUp)

    return () => {
      document.body.style.userSelect = previousUserSelect
      window.removeEventListener("mousemove", handleMouseMove)
      window.removeEventListener("mouseup", handleMouseUp)
    }
  }, [isDragging])

  const handleMouseDown = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (event.button !== 0) return

    const target = event.target instanceof HTMLElement ? event.target : null
    if (target?.closest("[data-tree-node='true']")) return

    const viewport = viewportRef.current
    if (!viewport) return

    dragStateRef.current = {
      startClientX: event.clientX,
      startClientY: event.clientY,
      startScrollLeft: viewport.scrollLeft,
      startScrollTop: viewport.scrollTop,
    }
    setIsDragging(true)
    event.preventDefault()
  }

  return (
    <div
      ref={viewportRef}
      className={cn(
        "relative min-h-[32rem] overflow-auto rounded-[1.1rem]",
        isDragging ? "cursor-grabbing" : "cursor-grab",
      )}
      onMouseDown={handleMouseDown}
    >
      <div
        className="min-h-full min-w-full"
        style={{
          width: canvasWidth,
          height: canvasHeight,
        }}
      >
        <div style={{ width: canvasWidth, height: canvasHeight }}>{children}</div>
      </div>
    </div>
  )
}

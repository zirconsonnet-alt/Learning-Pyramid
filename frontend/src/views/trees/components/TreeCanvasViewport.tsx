import { ZoomIn, ZoomOut } from "lucide-react"
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
  const [zoomPercent, setZoomPercent] = useState(100)
  const zoom = zoomPercent / 100

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
    <div className="relative">
      <div className="absolute right-3 top-3 z-20 flex items-center gap-2 rounded-full border border-white/70 bg-white/90 px-3 py-2 shadow-[0_18px_40px_-28px_rgba(15,23,42,0.45)] backdrop-blur">
        <ZoomOut className="size-4 text-[#6f879f]" aria-hidden="true" />
        <input
          type="range"
          aria-label="缩放树图"
          min={60}
          max={140}
          step={5}
          value={zoomPercent}
          className="h-2 w-36 accent-[#2f66c5]"
          onChange={(event) => setZoomPercent(Number(event.target.value))}
          onMouseDown={(event) => event.stopPropagation()}
        />
        <ZoomIn className="size-4 text-[#6f879f]" aria-hidden="true" />
        <span className="min-w-10 text-right text-xs font-semibold text-[#5f7891]">{zoomPercent}%</span>
      </div>
      <div
        ref={viewportRef}
        className={cn(
          "relative min-h-[32rem] overflow-auto rounded-[1.1rem]",
          isDragging ? "cursor-grabbing" : "cursor-grab",
        )}
        onMouseDown={handleMouseDown}
        style={{
          height: Math.max(512, canvasHeight * zoom),
        }}
      >
        <div
          className="min-h-full min-w-full"
          style={{
            width: canvasWidth * zoom,
            height: canvasHeight * zoom,
          }}
        >
          <div
            style={{
              width: canvasWidth,
              height: canvasHeight,
              transform: `scale(${zoom})`,
              transformOrigin: "top left",
            }}
          >
            {children}
          </div>
        </div>
      </div>
    </div>
  )
}

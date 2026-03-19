import { useEffect, useRef, useState, type MouseEvent as ReactMouseEvent, type ReactNode, type WheelEvent as ReactWheelEvent } from "react"

import { cn } from "@/ui/utils"

const MIN_SCALE = 0.7
const MAX_SCALE = 1.8
const ZOOM_SENSITIVITY = 0.0015

function clampScale(value: number) {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, value))
}

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
  const scaleRef = useRef(1)
  const [isDragging, setIsDragging] = useState(false)
  const [scale, setScale] = useState(1)

  useEffect(() => {
    scaleRef.current = scale
  }, [scale])

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

  const handleWheel = (event: ReactWheelEvent<HTMLDivElement>) => {
    if (!event.ctrlKey) return

    const viewport = viewportRef.current
    if (!viewport) return

    event.preventDefault()

    const currentScale = scaleRef.current
    const nextScale = clampScale(currentScale * Math.exp(-event.deltaY * ZOOM_SENSITIVITY))
    if (Math.abs(nextScale - currentScale) < 0.001) return

    const bounds = viewport.getBoundingClientRect()
    const pointerOffsetX = event.clientX - bounds.left
    const pointerOffsetY = event.clientY - bounds.top
    const contentX = (viewport.scrollLeft + pointerOffsetX) / currentScale
    const contentY = (viewport.scrollTop + pointerOffsetY) / currentScale

    scaleRef.current = nextScale
    setScale(nextScale)

    requestAnimationFrame(() => {
      const activeViewport = viewportRef.current
      if (!activeViewport) return

      activeViewport.scrollLeft = contentX * nextScale - pointerOffsetX
      activeViewport.scrollTop = contentY * nextScale - pointerOffsetY
    })
  }

  return (
    <div
      ref={viewportRef}
      className={cn(
        "relative min-h-[32rem] overflow-auto rounded-[1.1rem]",
        isDragging ? "cursor-grabbing" : "cursor-grab",
      )}
      onMouseDown={handleMouseDown}
      onWheel={handleWheel}
    >
      <div
        className="min-h-full min-w-full"
        style={{
          width: canvasWidth * scale,
          height: canvasHeight * scale,
        }}
      >
        <div
          style={{
            width: canvasWidth,
            height: canvasHeight,
            transform: `scale(${scale})`,
            transformOrigin: "top left",
          }}
        >
          {children}
        </div>
      </div>
    </div>
  )
}

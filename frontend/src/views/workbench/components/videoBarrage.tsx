import type { RefObject } from "react"

import { RichContentRenderer } from "@/ui/components/RichContentRenderer"
import { cn } from "@/ui/utils"

import type { HoveredBarrage } from "./useVideoBarrage"

export function VideoBarrageLayer({
  layerRef,
  isEnabled,
  isCapturePanelOpen,
}: {
  layerRef: RefObject<HTMLDivElement>
  isEnabled: boolean
  isCapturePanelOpen: boolean
}) {
  return (
    <div
      ref={layerRef}
      className={cn(
        "pointer-events-none absolute inset-x-4 top-4 z-[11] h-[33%] overflow-hidden transition-opacity duration-150",
        (!isEnabled || isCapturePanelOpen) && "opacity-0",
      )}
      aria-hidden="true"
    />
  )
}

export function VideoBarrageDetailCard({
  projectId,
  hoveredBarrage,
  isEnabled,
  isCapturePanelOpen,
}: {
  projectId: string
  hoveredBarrage: HoveredBarrage | null
  isEnabled: boolean
  isCapturePanelOpen: boolean
}) {
  if (!hoveredBarrage || !isEnabled || isCapturePanelOpen) return null

  return (
    <div
      className="pointer-events-none absolute z-[15]"
      style={{
        left: `${hoveredBarrage.cardLeftPx}px`,
        top: `${hoveredBarrage.cardTopPx}px`,
        width: `${hoveredBarrage.cardWidthPx}px`,
        transform: "translateX(-50%)",
      }}
    >
      <div
        className={cn(
          "absolute h-3.5 w-3.5 rotate-45 border border-white/12 bg-[linear-gradient(180deg,rgba(15,23,42,0.88),rgba(2,6,23,0.94))]",
          hoveredBarrage.cardPlacement === "below" ? "-top-1.5" : "-bottom-1.5",
        )}
        style={{
          left: `${hoveredBarrage.arrowLeftPx}px`,
          transform: "translateX(-50%) rotate(45deg)",
        }}
      />
      <div className="rounded-[1rem] border border-white/12 bg-[linear-gradient(180deg,rgba(15,23,42,0.88),rgba(2,6,23,0.94))] px-4 py-3 text-white shadow-[0_24px_56px_-34px_rgba(15,23,42,0.96)] backdrop-blur-xl">
        <div className="text-[11px] uppercase tracking-[0.18em] text-cyan-100/68">复述点答案</div>
        <div className="mt-1 text-sm font-medium text-white/86">{hoveredBarrage.text}</div>
        <RichContentRenderer
          projectId={projectId}
          value={hoveredBarrage.answerContent}
          className="mt-2"
          textClassName="whitespace-pre-wrap text-sm leading-6 text-white/90"
          imageClassName="max-h-44 w-full rounded-xl border border-white/10 bg-white/[0.06] object-contain"
        />
      </div>
    </div>
  )
}

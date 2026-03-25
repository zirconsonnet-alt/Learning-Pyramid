import { useCallback, useEffect, useMemo, useRef, useState, type RefObject } from "react"
import Danmaku from "danmaku"
import { useNavigate } from "react-router-dom"

import type { RecallPoint } from "@/ui/api/review"
import {
  richContentHasMeaning,
  richContentToPlainText,
  richText,
  type RichContent,
} from "@/ui/api/richContent"

const BARRAGE_TEXT_MAX_LEN = 42
const BARRAGE_MIN_GAP_MS = 850
const BARRAGE_MAX_PER_WINDOW = 4
const BARRAGE_WINDOW_MS = 4_500
const BARRAGE_DETAIL_CARD_EDGE_PX = 16
const BARRAGE_DETAIL_CARD_GAP_PX = 10
const BARRAGE_DETAIL_CARD_MAX_WIDTH_PX = 384
const BARRAGE_DETAIL_CARD_ESTIMATED_HEIGHT_PX = 150

type BarrageCue = {
  recallPointId: string
  anchorMs: number
  text: string
  answerContent: RichContent
}

export type HoveredBarrage = {
  recallPointId: string
  text: string
  answerContent: RichContent
  cardLeftPx: number
  cardTopPx: number
  cardWidthPx: number
  cardPlacement: "above" | "below"
  arrowLeftPx: number
}

type DanmakuPrivate = Danmaku & {
  media?: HTMLMediaElement
  _: {
    visible?: boolean
    paused?: boolean
    listener?: {
      play?: () => void
      pause?: () => void
    }
  }
}

type UseVideoBarrageOptions = {
  projectId: string
  instanceId: string | null
  recallPoints: RecallPoint[]
  playerShellRef: RefObject<HTMLDivElement>
  videoRef: RefObject<HTMLVideoElement>
  barrageLayerRef: RefObject<HTMLDivElement>
  sourceKey: string
  isEnabled: boolean
  isCapturePanelOpen: boolean
}

function parseAnchorMs(position: string): number | null {
  const match = position.match(/^t=(\d+)$/)
  if (!match) return null
  const next = Number(match[1])
  return Number.isFinite(next) ? next : null
}

function normalizeBarrageText(text: string, maxLen = BARRAGE_TEXT_MAX_LEN) {
  const compact = text.replace(/\s+/g, " ").trim()
  if (!compact) return ""
  if (compact.length <= maxLen) return compact
  return `${compact.slice(0, maxLen - 1).trimEnd()}…`
}

function recallPointToBarrageText(recallPoint: RecallPoint) {
  const questionText = normalizeBarrageText(richContentToPlainText(recallPoint.question))
  if (questionText) return questionText
  return normalizeBarrageText(richContentToPlainText(recallPoint.answer))
}

function recallPointToBarrageAnswerContent(recallPoint: RecallPoint): RichContent {
  if (richContentHasMeaning(recallPoint.answer)) return recallPoint.answer
  if (richContentHasMeaning(recallPoint.question)) return recallPoint.question
  return richText("这条复述点还没有可展示的答案内容。")
}

function compareBarrageCuePriority(left: BarrageCue, right: BarrageCue) {
  const leftImageCount = left.answerContent.filter((block) => block.kind === "IMAGE").length
  const rightImageCount = right.answerContent.filter((block) => block.kind === "IMAGE").length
  if (leftImageCount !== rightImageCount) return rightImageCount - leftImageCount
  if (left.text.length !== right.text.length) return left.text.length - right.text.length
  if (left.answerContent.length !== right.answerContent.length) return right.answerContent.length - left.answerContent.length
  return left.anchorMs - right.anchorMs
}

function pickPreferredBarrageCue(cues: BarrageCue[]) {
  let best = cues[0]
  for (let index = 1; index < cues.length; index += 1) {
    if (compareBarrageCuePriority(cues[index], best) < 0) {
      best = cues[index]
    }
  }
  return best
}

function limitBarrageDensity(cues: BarrageCue[]) {
  if (cues.length <= 1) return cues

  const spaced: BarrageCue[] = []
  let group: BarrageCue[] = [cues[0]]

  for (let index = 1; index < cues.length; index += 1) {
    const cue = cues[index]
    const previous = cues[index - 1]
    if (cue.anchorMs - previous.anchorMs < BARRAGE_MIN_GAP_MS) {
      group.push(cue)
      continue
    }
    spaced.push(pickPreferredBarrageCue(group))
    group = [cue]
  }
  spaced.push(pickPreferredBarrageCue(group))

  const kept: BarrageCue[] = []
  for (const cue of spaced) {
    kept.push(cue)
    const windowIndexes: number[] = []
    for (let index = kept.length - 1; index >= 0; index -= 1) {
      if (cue.anchorMs - kept[index].anchorMs > BARRAGE_WINDOW_MS) break
      windowIndexes.unshift(index)
    }
    if (windowIndexes.length <= BARRAGE_MAX_PER_WINDOW) continue

    let removeIndex = windowIndexes[0]
    for (const index of windowIndexes.slice(1)) {
      if (compareBarrageCuePriority(kept[index], kept[removeIndex]) > 0) {
        removeIndex = index
      }
    }
    kept.splice(removeIndex, 1)
  }

  return kept
}

function buildVisibleBarrageCues(instanceId: string | null, recallPoints: RecallPoint[]) {
  const cues: BarrageCue[] = []
  for (const recallPoint of recallPoints) {
    if (recallPoint.state !== "ACTIVE") continue
    if (!instanceId || recallPoint.anchor.instanceId !== instanceId) continue
    const anchorMs = parseAnchorMs(recallPoint.anchor.position)
    if (anchorMs === null) continue
    const text = recallPointToBarrageText(recallPoint)
    if (!text) continue
    cues.push({
      recallPointId: recallPoint.recallPointId,
      anchorMs,
      text,
      answerContent: recallPointToBarrageAnswerContent(recallPoint),
    })
  }
  cues.sort((left, right) => left.anchorMs - right.anchorMs)
  return limitBarrageDensity(cues)
}

function pauseDanmakuPlayback(danmaku: Danmaku | null) {
  const controller = danmaku as DanmakuPrivate | null
  if (!controller?._.visible || controller._.paused) return
  controller._.listener?.pause?.()
}

function resumeDanmakuPlayback(danmaku: Danmaku | null) {
  const controller = danmaku as DanmakuPrivate | null
  if (!controller?._.visible || !controller.media || controller.media.paused) return
  controller._.listener?.play?.()
}

function createBarrageBubble(params: {
  text: string
  onPointerEnter: (element: HTMLDivElement) => void
  onPointerLeave: () => void
  onOpen: () => void
}) {
  const bubble = document.createElement("div")
  bubble.className = "plm-video-barrage-bubble"
  bubble.title = params.text
  bubble.tabIndex = 0
  bubble.setAttribute("role", "button")

  const label = document.createElement("span")
  label.textContent = params.text
  bubble.appendChild(label)

  bubble.addEventListener("mouseenter", () => params.onPointerEnter(bubble))
  bubble.addEventListener("mouseleave", params.onPointerLeave)
  bubble.addEventListener("focus", () => params.onPointerEnter(bubble))
  bubble.addEventListener("blur", params.onPointerLeave)
  bubble.addEventListener("click", (event) => {
    event.preventDefault()
    event.stopPropagation()
    params.onOpen()
  })
  bubble.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return
    event.preventDefault()
    params.onOpen()
  })

  return bubble
}

export function useVideoBarrage({
  projectId,
  instanceId,
  recallPoints,
  playerShellRef,
  videoRef,
  barrageLayerRef,
  sourceKey,
  isEnabled,
  isCapturePanelOpen,
}: UseVideoBarrageOptions) {
  const navigate = useNavigate()
  const danmakuRef = useRef<Danmaku | null>(null)
  const visibilityRef = useRef({
    isEnabled,
    isCapturePanelOpen,
  })
  const [hoveredBarrage, setHoveredBarrage] = useState<HoveredBarrage | null>(null)

  const barrageCueSnapshot = useMemo(
    () =>
      JSON.stringify(
        buildVisibleBarrageCues(instanceId, recallPoints).map((cue) => [
          cue.recallPointId,
          cue.anchorMs,
          cue.text,
          cue.answerContent,
        ] as const),
      ),
    [instanceId, recallPoints],
  )

  useEffect(() => {
    visibilityRef.current = { isEnabled, isCapturePanelOpen }
  }, [isCapturePanelOpen, isEnabled])

  const openBarrageRecallPoint = useCallback(
    (recallPointId: string) => {
      navigate(`/p/${projectId}/recall-points/${recallPointId}`)
    },
    [navigate, projectId],
  )

  const handleBarragePointerEnter = useCallback(
    (
      payload: Omit<HoveredBarrage, "cardLeftPx" | "cardTopPx" | "cardWidthPx" | "cardPlacement" | "arrowLeftPx">,
      element: HTMLDivElement,
    ) => {
      const shell = playerShellRef.current
      if (!shell) return

      const shellRect = shell.getBoundingClientRect()
      const bubbleRect = element.getBoundingClientRect()
      const availableWidth = Math.max(160, shellRect.width - BARRAGE_DETAIL_CARD_EDGE_PX * 2)
      const cardWidthPx = Math.min(BARRAGE_DETAIL_CARD_MAX_WIDTH_PX, availableWidth)
      const anchorCenterX = bubbleRect.left - shellRect.left + bubbleRect.width / 2
      const minCenterX = BARRAGE_DETAIL_CARD_EDGE_PX + cardWidthPx / 2
      const maxCenterX = shellRect.width - BARRAGE_DETAIL_CARD_EDGE_PX - cardWidthPx / 2
      const cardLeftPx = Math.min(Math.max(anchorCenterX, minCenterX), maxCenterX)
      const cardStartX = cardLeftPx - cardWidthPx / 2
      const arrowLeftPx = Math.min(Math.max(anchorCenterX - cardStartX, 22), cardWidthPx - 22)
      const belowTop = bubbleRect.bottom - shellRect.top + BARRAGE_DETAIL_CARD_GAP_PX
      const maxBelowTop = shellRect.height - BARRAGE_DETAIL_CARD_ESTIMATED_HEIGHT_PX - 72
      const shouldPlaceBelow = belowTop <= maxBelowTop
      const cardTopPx = shouldPlaceBelow
        ? belowTop
        : Math.max(
            BARRAGE_DETAIL_CARD_EDGE_PX,
            bubbleRect.top - shellRect.top - BARRAGE_DETAIL_CARD_ESTIMATED_HEIGHT_PX - BARRAGE_DETAIL_CARD_GAP_PX,
          )

      setHoveredBarrage({
        ...payload,
        cardLeftPx,
        cardTopPx,
        cardWidthPx,
        cardPlacement: shouldPlaceBelow ? "below" : "above",
        arrowLeftPx,
      })
      pauseDanmakuPlayback(danmakuRef.current)
    },
    [playerShellRef],
  )

  const handleBarragePointerLeave = useCallback(() => {
    setHoveredBarrage(null)
    if (!visibilityRef.current.isEnabled || visibilityRef.current.isCapturePanelOpen) return
    resumeDanmakuPlayback(danmakuRef.current)
  }, [])

  useEffect(() => {
    if (hoveredBarrage === null) return
    if (isEnabled && !isCapturePanelOpen && instanceId) return
    const animationFrameId = window.requestAnimationFrame(() => setHoveredBarrage(null))
    return () => {
      window.cancelAnimationFrame(animationFrameId)
    }
  }, [hoveredBarrage, instanceId, isCapturePanelOpen, isEnabled])

  useEffect(() => {
    const layer = barrageLayerRef.current
    const media = videoRef.current
    const cueRows = JSON.parse(barrageCueSnapshot) as Array<readonly [string, number, string, RichContent]>
    if (!layer || !media || !instanceId || cueRows.length === 0) {
      return
    }

    const danmaku = new Danmaku({
      container: layer,
      media,
      comments: cueRows.map(([recallPointId, anchorMs, text, answerContent]) => ({
        mode: "rtl" as const,
        time: anchorMs / 1000,
        render: () =>
          createBarrageBubble({
            text,
            onPointerEnter: (element) =>
              handleBarragePointerEnter({ recallPointId, text, answerContent }, element),
            onPointerLeave: handleBarragePointerLeave,
            onOpen: () => openBarrageRecallPoint(recallPointId),
          }),
      })),
      engine: "dom",
      speed: 144,
    })
    danmakuRef.current = danmaku

    const syncDanmakuSize = () => {
      danmaku.resize()
    }
    const resizeObserver =
      typeof ResizeObserver === "undefined" ? null : new ResizeObserver(() => syncDanmakuSize())

    resizeObserver?.observe(layer)
    window.addEventListener("resize", syncDanmakuSize)
    document.addEventListener("fullscreenchange", syncDanmakuSize)

    if (!visibilityRef.current.isEnabled || visibilityRef.current.isCapturePanelOpen) {
      danmaku.hide()
    }

    return () => {
      resizeObserver?.disconnect()
      window.removeEventListener("resize", syncDanmakuSize)
      document.removeEventListener("fullscreenchange", syncDanmakuSize)
      if (danmakuRef.current === danmaku) {
        danmakuRef.current = null
      }
      danmaku.destroy()
    }
  }, [
    barrageCueSnapshot,
    barrageLayerRef,
    handleBarragePointerEnter,
    handleBarragePointerLeave,
    instanceId,
    openBarrageRecallPoint,
    sourceKey,
    videoRef,
  ])

  useEffect(() => {
    const danmaku = danmakuRef.current
    if (!danmaku) return
    if (!isEnabled || isCapturePanelOpen) {
      danmaku.hide()
      return
    }
    danmaku.show()
    danmaku.resize()
  }, [isCapturePanelOpen, isEnabled])

  return { hoveredBarrage }
}

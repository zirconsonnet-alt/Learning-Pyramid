import { useCallback, useEffect, useMemo, useState } from "react"

import type { Instance } from "@/ui/api/instances"
import type { MaterialSourceKind } from "@/ui/api/projects"
import {
  clearSubtitleDocumentCache,
  findSubtitleTextAtMs,
  loadSubtitleDocumentForInstance,
  SUPPORTED_SUBTITLE_EXTENSIONS_LABEL,
  type SubtitleDocument,
} from "@/ui/subtitles/subtitleSupport"

type UseVideoSubtitlesParams = {
  projectId: string
  instance: Instance | null
  playbackMs: number
  enabled: boolean
  sourceKind: MaterialSourceKind | null | undefined
  subtitleDelayMs: number
}

export function useVideoSubtitles(params: UseVideoSubtitlesParams) {
  const { projectId, instance, playbackMs, enabled, sourceKind, subtitleDelayMs } = params
  const [document, setDocument] = useState<SubtitleDocument | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [errorText, setErrorText] = useState<string | null>(null)
  const [retryNonce, setRetryNonce] = useState(0)

  const effectivePlaybackMs = useMemo(
    () => Math.max(0, Math.floor(playbackMs - subtitleDelayMs)),
    [playbackMs, subtitleDelayMs],
  )

  useEffect(() => {
    if (!enabled || !instance || !sourceKind) {
      setDocument(null)
      setIsLoading(false)
      setErrorText(null)
      return
    }

    let cancelled = false
    setIsLoading(true)
    setErrorText(null)

    void loadSubtitleDocumentForInstance({ projectId, instance, sourceKind })
      .then((nextDocument) => {
        if (cancelled) return
        setDocument(nextDocument)
        if (!nextDocument) {
          setErrorText(`当前视频同目录下没有找到同名字幕文件（支持 ${SUPPORTED_SUBTITLE_EXTENSIONS_LABEL}）。`)
        }
      })
      .catch((error) => {
        if (cancelled) return
        setDocument(null)
        setErrorText(error instanceof Error ? error.message : "读取字幕文件失败")
      })
      .finally(() => {
        if (cancelled) return
        setIsLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [enabled, instance, projectId, retryNonce, sourceKind])

  const text = useMemo(() => {
    if (!enabled || !document) return null
    return findSubtitleTextAtMs(document.segments, effectivePlaybackMs)
  }, [document, effectivePlaybackMs, enabled])

  const retry = useCallback(() => {
    clearSubtitleDocumentCache()
    setRetryNonce((value) => value + 1)
  }, [])

  return {
    text,
    isLoading,
    isBootstrapping: false,
    errorText,
    retry,
  }
}

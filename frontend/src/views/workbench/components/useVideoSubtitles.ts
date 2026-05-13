import { useCallback, useEffect, useMemo, useState } from "react"

import type { Instance } from "@/ui/api/instances"
import type { ScopedProjectRef } from "@/ui/api/projectScope"
import type { MaterialSourceKind } from "@/ui/api/projects"
import {
  clearSubtitleDocumentCache,
  findSubtitleTextAtMs,
  loadSubtitleDocumentForInstance,
  SUPPORTED_SUBTITLE_EXTENSIONS_LABEL,
  type SubtitleDocument,
} from "@/ui/subtitles/subtitleSupport"

type UseVideoSubtitlesParams = {
  subjectId: string
  projectId: string
  instance: Instance | null
  playbackMs: number
  subtitlesEnabled: boolean
  detectionEnabled: boolean
  sourceKind: MaterialSourceKind | null | undefined
  subtitleDelayMs: number
}

type SubtitleLoadState = {
  document: SubtitleDocument | null
  isLoading: boolean
  missingText: string | null
  errorText: string | null
}

export function useVideoSubtitles(params: UseVideoSubtitlesParams) {
  const { subjectId, projectId, instance, playbackMs, subtitlesEnabled, detectionEnabled, sourceKind, subtitleDelayMs } = params
  const projectScope: ScopedProjectRef = useMemo(() => ({ subjectId, scopedProjectId: projectId }), [projectId, subjectId])
  const [loadState, setLoadState] = useState<SubtitleLoadState>({
    document: null,
    isLoading: false,
    missingText: null,
    errorText: null,
  })
  const [retryNonce, setRetryNonce] = useState(0)
  const sourceReady = detectionEnabled && instance && sourceKind
  const document = sourceReady ? loadState.document : null
  const isLoading = sourceReady ? loadState.isLoading : false
  const missingText = sourceReady ? loadState.missingText : null
  const errorText = sourceReady ? loadState.errorText : null

  const effectivePlaybackMs = useMemo(
    () => Math.max(0, Math.floor(playbackMs - subtitleDelayMs)),
    [playbackMs, subtitleDelayMs],
  )

  useEffect(() => {
    if (!detectionEnabled || !instance || !sourceKind) {
      return
    }

    let cancelled = false
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoadState((current) => ({
      document: current.document,
      isLoading: true,
      missingText: null,
      errorText: null,
    }))

    void loadSubtitleDocumentForInstance({ scope: projectScope, instance, sourceKind })
      .then((nextDocument) => {
        if (cancelled) return
        setLoadState({
          document: nextDocument,
          isLoading: false,
          missingText: nextDocument ? null : `当前视频同目录下没有找到同名字幕文件（支持 ${SUPPORTED_SUBTITLE_EXTENSIONS_LABEL}）。`,
          errorText: null,
        })
      })
      .catch((error) => {
        if (cancelled) return
        setLoadState({
          document: null,
          isLoading: false,
          missingText: null,
          errorText: error instanceof Error ? error.message : "读取字幕文件失败",
        })
      })

    return () => {
      cancelled = true
    }
  }, [detectionEnabled, instance, projectScope, retryNonce, sourceKind])

  const text = useMemo(() => {
    if (!subtitlesEnabled || !document) return null
    return findSubtitleTextAtMs(document.segments, effectivePlaybackMs)
  }, [document, effectivePlaybackMs, subtitlesEnabled])

  const retry = useCallback(() => {
    clearSubtitleDocumentCache()
    setRetryNonce((value) => value + 1)
  }, [])

  return {
    text,
    isLoading,
    missingText,
    errorText,
    hasSubtitleFile: document !== null,
    retry,
  }
}

export type CapturedVideoFrame = {
  timeMs: number
  imageDataUrl: string
}

export type CapturedVideoFrameFile = {
  timeMs: number
  file: File
}

function clampVideoTimeMs(video: HTMLVideoElement, ms: number) {
  const durationMs = Number.isFinite(video.duration) && video.duration > 0 ? Math.floor(video.duration * 1000) : null
  if (durationMs === null) return Math.max(0, Math.floor(ms))
  return Math.min(Math.max(0, Math.floor(ms)), durationMs)
}

function waitForVideoEvent(video: HTMLVideoElement, eventName: "loadedmetadata" | "seeked", signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException("Aborted", "AbortError"))
      return
    }

    const timeout = window.setTimeout(() => {
      cleanup()
      reject(new Error(eventName === "loadedmetadata" ? "读取视频信息超时" : "定位视频帧超时"))
    }, 15_000)

    const cleanup = () => {
      window.clearTimeout(timeout)
      video.removeEventListener(eventName, handleEvent)
      video.removeEventListener("error", handleError)
      signal?.removeEventListener("abort", handleAbort)
    }
    const handleEvent = () => {
      cleanup()
      resolve()
    }
    const handleError = () => {
      cleanup()
      reject(new Error(eventName === "loadedmetadata" ? "读取视频信息失败" : "定位视频帧失败"))
    }
    const handleAbort = () => {
      cleanup()
      reject(new DOMException("Aborted", "AbortError"))
    }

    video.addEventListener(eventName, handleEvent, { once: true })
    video.addEventListener("error", handleError, { once: true })
    signal?.addEventListener("abort", handleAbort, { once: true })
  })
}

export async function captureDisplayedVideoFrameBlob(video: HTMLVideoElement, timeMs: number): Promise<{ timeMs: number; blob: Blob }> {
  const width = video.videoWidth || 0
  const height = video.videoHeight || 0
  if (width <= 0 || height <= 0) {
    throw new Error("当前视频帧尚未就绪")
  }

  const scale = Math.min(1, 960 / Math.max(width, height))
  const canvas = document.createElement("canvas")
  canvas.width = Math.max(1, Math.round(width * scale))
  canvas.height = Math.max(1, Math.round(height * scale))
  const context = canvas.getContext("2d")
  if (!context) throw new Error("无法初始化画布")
  context.drawImage(video, 0, 0, canvas.width, canvas.height)

  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.78))
  if (!blob) throw new Error("当前画面编码失败")
  return {
    timeMs: Math.max(0, Math.floor(timeMs)),
    blob,
  }
}

export async function captureDisplayedVideoFrame(video: HTMLVideoElement, timeMs: number): Promise<CapturedVideoFrame> {
  const captured = await captureDisplayedVideoFrameBlob(video, timeMs)
  const imageDataUrl = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      if (typeof reader.result === "string") {
        resolve(reader.result)
        return
      }
      reject(new Error("当前画面读取失败"))
    }
    reader.onerror = () => reject(reader.error ?? new Error("当前画面读取失败"))
    reader.readAsDataURL(captured.blob)
  })

  return {
    timeMs: captured.timeMs,
    imageDataUrl,
  }
}

export async function captureDisplayedVideoFrameFile(video: HTMLVideoElement, timeMs: number): Promise<CapturedVideoFrameFile> {
  const captured = await captureDisplayedVideoFrameBlob(video, timeMs)
  return {
    timeMs: captured.timeMs,
    file: new File([captured.blob], `video-frame-${Math.floor(captured.timeMs / 1000)}s.jpg`, {
      type: captured.blob.type || "image/jpeg",
      lastModified: Date.now(),
    }),
  }
}

export async function captureVideoFrameAt(params: {
  src: string
  timeMs: number
  signal?: AbortSignal
}): Promise<CapturedVideoFrame> {
  const video = document.createElement("video")
  video.preload = "auto"
  video.muted = true
  video.playsInline = true
  video.crossOrigin = "anonymous"
  video.src = params.src

  try {
    if (video.readyState < HTMLMediaElement.HAVE_METADATA) {
      await waitForVideoEvent(video, "loadedmetadata", params.signal)
    }
    const targetMs = clampVideoTimeMs(video, params.timeMs)
    video.currentTime = targetMs / 1000
    if (Math.abs(video.currentTime * 1000 - targetMs) > 80 || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) {
      await waitForVideoEvent(video, "seeked", params.signal)
    }
    return await captureDisplayedVideoFrame(video, targetMs)
  } finally {
    video.pause()
    video.removeAttribute("src")
    video.load()
  }
}

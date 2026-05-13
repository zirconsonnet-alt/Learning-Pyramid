import { useCallback, useEffect, useRef, useState } from "react"

import {
  getPomodoroWallpaperScopeSignature,
  readPomodoroWallpaperBlob,
  type PomodoroWallpaperScope,
} from "@/ui/pomodoroWallpaper"

type PomodoroWallpaperState = {
  wallpaperUrl: string
  replacePomodoroWallpaperPreview: (blob: Blob | null) => void
}

export function usePomodoroWallpaper(scope: PomodoroWallpaperScope | null): PomodoroWallpaperState {
  const [wallpaperUrl, setWallpaperUrl] = useState("")
  const wallpaperObjectUrlRef = useRef("")
  const scopeSignature = getPomodoroWallpaperScopeSignature(scope)

  const replacePomodoroWallpaperPreview = useCallback((blob: Blob | null) => {
    if (wallpaperObjectUrlRef.current) {
      URL.revokeObjectURL(wallpaperObjectUrlRef.current)
      wallpaperObjectUrlRef.current = ""
    }
    if (!blob) {
      setWallpaperUrl("")
      return
    }
    const nextUrl = URL.createObjectURL(blob)
    wallpaperObjectUrlRef.current = nextUrl
    setWallpaperUrl(nextUrl)
  }, [])

  useEffect(() => {
    let cancelled = false
    replacePomodoroWallpaperPreview(null)
    if (!scope) {
      return () => {
        cancelled = true
      }
    }
    void readPomodoroWallpaperBlob(scope)
      .then((blob) => {
        if (cancelled) return
        replacePomodoroWallpaperPreview(blob)
      })
      .catch(() => {
        // Local wallpaper is cosmetic; page content remains usable if IndexedDB is unavailable.
      })
    return () => {
      cancelled = true
      if (wallpaperObjectUrlRef.current) {
        URL.revokeObjectURL(wallpaperObjectUrlRef.current)
        wallpaperObjectUrlRef.current = ""
      }
    }
  }, [replacePomodoroWallpaperPreview, scope, scopeSignature])

  return { wallpaperUrl, replacePomodoroWallpaperPreview }
}

export function PomodoroWallpaperBackdrop(props: { wallpaperUrl: string }) {
  if (!props.wallpaperUrl) return null
  return (
    <div
      data-pomodoro-wallpaper-backdrop
      className="pointer-events-none fixed inset-x-0 bottom-0 top-[3.75rem] z-0 bg-cover bg-center"
      style={{ backgroundImage: `url(${props.wallpaperUrl})` }}
    >
      <div
        className="absolute inset-0 backdrop-blur-[1px]"
        style={{
          background:
            "linear-gradient(180deg, hsl(var(--background) / 0.58) 0%, hsl(var(--background) / 0.72) 48%, hsl(var(--background) / 0.82) 100%)",
        }}
      />
    </div>
  )
}

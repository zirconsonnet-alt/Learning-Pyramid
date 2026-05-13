import type { ReactNode } from "react"

import { PomodoroWallpaperBackdrop } from "@/views/pomodoro/PomodoroWallpaperBackdrop"

type PomodoroSubpageFrameProps = {
  wallpaperUrl: string
  children: ReactNode
  maxWidthClassName?: string
}

export function PomodoroSubpageFrame(props: PomodoroSubpageFrameProps) {
  const { wallpaperUrl, children, maxWidthClassName = "max-w-5xl" } = props

  return (
    <>
      <PomodoroWallpaperBackdrop wallpaperUrl={wallpaperUrl} />
      <div
        data-pomodoro-wallpaper-scope="page"
        className={`relative z-10 mx-auto flex w-full ${maxWidthClassName} flex-col gap-8`}
      >
        {children}
      </div>
    </>
  )
}

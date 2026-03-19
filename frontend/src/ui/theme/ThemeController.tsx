import { useEffect } from "react"

import { DEFAULT_THEME_PRESET_ID } from "@/ui/theme/themePresets"
import { useThemeStore } from "@/ui/store/themeStore"

export function ThemeController() {
  const theme = useThemeStore((state) => state.theme)

  useEffect(() => {
    const root = document.documentElement
    root.dataset.theme = theme || DEFAULT_THEME_PRESET_ID
    root.style.colorScheme = "light"
  }, [theme])

  return null
}

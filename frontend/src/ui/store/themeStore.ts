import { create } from "zustand"
import { persist } from "zustand/middleware"

import { DEFAULT_THEME_PRESET_ID, isThemePresetId, type ThemePresetId } from "@/ui/theme/themePresets"

type ThemeState = {
  theme: ThemePresetId
  setTheme: (theme: ThemePresetId) => void
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      theme: DEFAULT_THEME_PRESET_ID,
      setTheme: (theme) => set({ theme }),
    }),
    {
      name: "plm-theme",
      merge: (persistedState, currentState) => {
        const persistedTheme =
          persistedState && typeof persistedState === "object" && "theme" in persistedState
            ? persistedState.theme
            : null
        return {
          ...currentState,
          theme: isThemePresetId(persistedTheme) ? persistedTheme : currentState.theme,
        }
      },
    },
  ),
)

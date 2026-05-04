import { useEffect, useRef } from "react"

import type { UserGlobalSettings } from "@/ui/api/profile"
import { useMyGlobalSettings } from "@/ui/queries/profile"
import { normalizeProjectReviewTemplate, useGlobalConfigStore } from "@/ui/store/globalConfigStore"
import { usePomodoroStore } from "@/ui/store/pomodoroStore"
import { useThemeStore } from "@/ui/store/themeStore"
import { DEFAULT_THEME_PRESET_ID, isThemePresetId } from "@/ui/theme/themePresets"

export function applyGlobalSettingsSnapshot(settings: UserGlobalSettings) {
  const theme = isThemePresetId(settings.theme) ? settings.theme : DEFAULT_THEME_PRESET_ID
  useThemeStore.getState().setTheme(theme)
  useGlobalConfigStore.getState().setDefaultProjectReviewTemplate(
    normalizeProjectReviewTemplate(settings.defaultProjectReviewTemplate),
  )
  usePomodoroStore.getState().setSettings({
    enabled: settings.pomodoro.enabled,
    weeklySchedule: settings.pomodoro.weeklySchedule,
    transitionSoundEnabled: settings.pomodoro.transitionSoundEnabled,
    defaultFocusPrompt: settings.pomodoro.defaultFocusPrompt,
    defaultBreakPrompt: settings.pomodoro.defaultBreakPrompt,
    microBreaks: settings.pomodoro.microBreaks,
  })
}

export function useBootstrapGlobalSettings(enabled: boolean, userId?: string | null) {
  const query = useMyGlobalSettings(enabled && Boolean(userId))
  const appliedKeyRef = useRef("")

  useEffect(() => {
    if (!enabled || !userId) {
      appliedKeyRef.current = ""
      return
    }
    if (!query.data) return
    const nextKey = `${userId}:${query.data.updatedAt ?? "default"}`
    if (appliedKeyRef.current === nextKey) return
    applyGlobalSettingsSnapshot(query.data)
    appliedKeyRef.current = nextKey
  }, [enabled, query.data, userId])

  return query
}

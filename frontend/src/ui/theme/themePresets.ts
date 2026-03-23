export const THEME_PRESETS = [
  {
    id: "mist",
    label: "雾蓝",
    description: "冷静、轻薄、空气感。",
    preview: ["#dfeaf5", "#fdfeff", "#1f8de0", "#224968"],
  },
  {
    id: "paper",
    label: "暖白",
    description: "柔和、纸感、低刺激。",
    preview: ["#f3e8dc", "#fffdf8", "#365cc0", "#6b5036"],
  },
  {
    id: "ink",
    label: "深描",
    description: "锐利、专注、高对比。",
    preview: ["#bcc8d8", "#f7fbff", "#1672ff", "#172334"],
  },
] as const

export type ThemePresetId = (typeof THEME_PRESETS)[number]["id"]

export const DEFAULT_THEME_PRESET_ID: ThemePresetId = "mist"

export function isThemePresetId(value: unknown): value is ThemePresetId {
  return typeof value === "string" && THEME_PRESETS.some((theme) => theme.id === value)
}

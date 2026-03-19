export const THEME_PRESETS = [
  {
    id: "mist",
    label: "雾蓝",
    description: "冷静的白灰蓝工作台，适合默认长时使用。",
    preview: ["#f5f7fa", "#ffffff", "#2563eb", "#334155"],
  },
  {
    id: "paper",
    label: "暖白",
    description: "更接近纸面的暖白底，降低冷灰疲劳感。",
    preview: ["#fffbf6", "#ffffff", "#3b82f6", "#4b5563"],
  },
  {
    id: "ink",
    label: "深描",
    description: "更高对比的浅色主题，信息边界更清楚。",
    preview: ["#eef2f7", "#ffffff", "#1d4ed8", "#0f172a"],
  },
] as const

export type ThemePresetId = (typeof THEME_PRESETS)[number]["id"]

export const DEFAULT_THEME_PRESET_ID: ThemePresetId = "mist"

export function isThemePresetId(value: unknown): value is ThemePresetId {
  return typeof value === "string" && THEME_PRESETS.some((theme) => theme.id === value)
}

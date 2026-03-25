export const THEME_PRESETS = [
  {
    id: "mist",
    label: "雾蓝",
    description: "冷静、轻薄、空气感。",
    preview: ["#dfeaf5", "#fdfeff", "#1f8de0", "#224968"],
    surface: {
      background:
        "radial-gradient(circle at 18% 18%, rgba(255, 255, 255, 0.82), transparent 42%), linear-gradient(180deg, rgba(247, 251, 255, 0.98) 0%, rgba(231, 240, 249, 0.98) 100%)",
      border: "#c8d9ea",
      shadow: "0 20px 38px -30px rgba(31, 73, 104, 0.24)",
      title: "#27445d",
      description: "#627d96",
      swatchBorder: "rgba(33, 73, 104, 0.08)",
    },
  },
  {
    id: "paper",
    label: "暖白",
    description: "柔和、纸感、低刺激。",
    preview: ["#f3e8dc", "#fffdf8", "#365cc0", "#6b5036"],
    surface: {
      background:
        "radial-gradient(circle at 18% 18%, rgba(255, 255, 255, 0.72), transparent 42%), linear-gradient(180deg, rgba(255, 250, 244, 0.99) 0%, rgba(245, 235, 222, 0.98) 100%)",
      border: "#dfcfba",
      shadow: "0 20px 38px -30px rgba(107, 80, 54, 0.18)",
      title: "#5f4731",
      description: "#8a6f56",
      swatchBorder: "rgba(84, 60, 35, 0.08)",
    },
  },
  {
    id: "ink",
    label: "深描",
    description: "锐利、专注、高对比。",
    preview: ["#8fa3ba", "#dfe8f1", "#2b78ff", "#152233"],
    surface: {
      background:
        "radial-gradient(circle at 20% 16%, rgba(121, 142, 171, 0.34), transparent 40%), linear-gradient(180deg, rgba(72, 84, 101, 0.98) 0%, rgba(45, 54, 67, 0.99) 100%)",
      border: "#5d7089",
      shadow: "0 24px 42px -28px rgba(16, 25, 38, 0.46)",
      title: "#f2f6fb",
      description: "#cad5e1",
      swatchBorder: "rgba(255, 255, 255, 0.12)",
    },
  },
] as const

export type ThemePresetId = (typeof THEME_PRESETS)[number]["id"]

export const DEFAULT_THEME_PRESET_ID: ThemePresetId = "mist"

export function isThemePresetId(value: unknown): value is ThemePresetId {
  return typeof value === "string" && THEME_PRESETS.some((theme) => theme.id === value)
}

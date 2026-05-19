export type AppRuntimeKind = "web" | "desktop"

type TauriWindow = Window & {
  __TAURI_INTERNALS__?: unknown
}

export function getAppRuntimeKind(): AppRuntimeKind {
  if (typeof window === "undefined") return "web"
  return "__TAURI_INTERNALS__" in (window as TauriWindow) ? "desktop" : "web"
}

export function isDesktopRuntime() {
  return getAppRuntimeKind() === "desktop"
}

export function installAppRuntimeMarker() {
  document.documentElement.dataset.appRuntime = getAppRuntimeKind()
}

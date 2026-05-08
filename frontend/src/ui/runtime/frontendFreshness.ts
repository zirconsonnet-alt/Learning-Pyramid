const FRONTEND_ENTRY_ASSET_RE = /\/assets\/(index-[A-Za-z0-9_-]+\.js)(?:[?#][^"']*)?/
const CHECK_THROTTLE_MS = 30_000
const RELOAD_MARKER = "lp:frontend-freshness-reload"

let freshnessMonitorInstalled = false
let lastCheckAtMs = 0
let pendingCheck: Promise<void> | null = null

export function extractFrontendEntryAsset(value: string) {
  return value.match(FRONTEND_ENTRY_ASSET_RE)?.[1] ?? null
}

function getCurrentFrontendEntryAsset() {
  if (typeof document === "undefined") return null
  for (const script of Array.from(document.scripts)) {
    const src = script.getAttribute("src")
    if (!src) continue
    const asset = extractFrontendEntryAsset(src)
    if (asset) return asset
  }
  return null
}

async function fetchLatestFrontendEntryAsset() {
  if (typeof window === "undefined") return null
  const url = new URL("/", window.location.origin)
  url.searchParams.set("__lp_freshness", `${Date.now()}`)
  const response = await fetch(url.toString(), {
    cache: "no-store",
    credentials: "same-origin",
  })
  if (!response.ok) return null
  return extractFrontendEntryAsset(await response.text())
}

export async function checkFrontendFreshness(options: { force?: boolean } = {}) {
  if (typeof window === "undefined" || typeof document === "undefined") return
  const currentAsset = getCurrentFrontendEntryAsset()
  if (!currentAsset) return

  const now = Date.now()
  if (!options.force && now - lastCheckAtMs < CHECK_THROTTLE_MS) return
  if (pendingCheck) return pendingCheck

  lastCheckAtMs = now
  pendingCheck = (async () => {
    try {
      const latestAsset = await fetchLatestFrontendEntryAsset()
      if (!latestAsset || latestAsset === currentAsset) return
      const reloadMarker = `${currentAsset}->${latestAsset}`
      if (sessionStorage.getItem(RELOAD_MARKER) === reloadMarker) return
      sessionStorage.setItem(RELOAD_MARKER, reloadMarker)
      window.location.reload()
    } catch {
      // Ignore freshness probes so routing and page interactions keep working.
    } finally {
      pendingCheck = null
    }
  })()

  return pendingCheck
}

function scheduleFrontendFreshnessCheck(force = false) {
  window.setTimeout(() => {
    void checkFrontendFreshness({ force })
  }, 0)
}

export function installFrontendFreshnessMonitor() {
  if (freshnessMonitorInstalled || typeof window === "undefined" || typeof document === "undefined") return
  freshnessMonitorInstalled = true

  const handleWindowFocus = () => {
    scheduleFrontendFreshnessCheck()
  }
  const handlePageShow = () => {
    scheduleFrontendFreshnessCheck(true)
  }
  const handleVisibilityChange = () => {
    if (document.visibilityState !== "visible") return
    scheduleFrontendFreshnessCheck()
  }
  const handleHistoryNavigation = () => {
    scheduleFrontendFreshnessCheck()
  }

  window.addEventListener("focus", handleWindowFocus)
  window.addEventListener("pageshow", handlePageShow)
  window.addEventListener("popstate", handleHistoryNavigation)
  document.addEventListener("visibilitychange", handleVisibilityChange)

  scheduleFrontendFreshnessCheck(true)
}

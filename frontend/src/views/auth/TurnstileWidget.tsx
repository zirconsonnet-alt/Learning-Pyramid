import { useEffect, useRef, useState } from "react"

import { cn } from "@/ui/utils"

type TurnstileRenderOptions = {
  sitekey: string
  action?: string
  callback?: (token: string) => void
  "expired-callback"?: () => void
  "error-callback"?: () => void
  theme?: "light" | "dark" | "auto"
}

type TurnstileApi = {
  ready?: (callback: () => void) => void
  render: (container: HTMLElement, options: TurnstileRenderOptions) => string
  reset: (widgetId: string) => void
  remove: (widgetId: string) => void
}

declare global {
  interface Window {
    turnstile?: TurnstileApi
    __plmTurnstileLoadPromise?: Promise<void>
  }
}

const TURNSTILE_SCRIPT_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit"
const TURNSTILE_SCRIPT_SELECTOR = 'script[data-plm-turnstile="true"]'
const TURNSTILE_LOADED_ATTRIBUTE = "data-plm-turnstile-loaded"
const TURNSTILE_SCRIPT_TIMEOUT_MS = 15_000

function waitForTurnstileReady(): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    let settled = false
    let pollId: number | null = null
    let timeoutId: number | null = null

    const cleanup = () => {
      if (pollId !== null) window.clearTimeout(pollId)
      if (timeoutId !== null) window.clearTimeout(timeoutId)
    }

    const complete = () => {
      if (settled) return
      settled = true
      cleanup()
      resolve()
    }

    const fail = () => {
      if (settled) return
      settled = true
      cleanup()
      reject(new Error("Turnstile API is not ready"))
    }

    const poll = () => {
      const turnstile = window.turnstile
      if (!turnstile) {
        pollId = window.setTimeout(poll, 50)
        return
      }

      try {
        if (turnstile.ready) {
          turnstile.ready(complete)
          return
        }
        complete()
      } catch {
        fail()
      }
    }

    timeoutId = window.setTimeout(fail, TURNSTILE_SCRIPT_TIMEOUT_MS)
    poll()
  })
}

function loadTurnstileScriptElement(): Promise<void> {
  const staleScript = document.querySelector<HTMLScriptElement>('script[data-plm-turnstile-error="true"]')
  staleScript?.remove()

  const existing = document.querySelector<HTMLScriptElement>(TURNSTILE_SCRIPT_SELECTOR)
  if (existing?.getAttribute(TURNSTILE_LOADED_ATTRIBUTE) === "true") {
    return Promise.resolve()
  }

  const script = existing ?? document.createElement("script")
  if (!existing) {
    script.src = TURNSTILE_SCRIPT_SRC
    script.async = true
    script.defer = true
    script.dataset.plmTurnstile = "true"
  }

  return new Promise<void>((resolve, reject) => {
    let settled = false
    let timeoutId: number | null = null

    const cleanup = () => {
      script.removeEventListener("load", handleLoad)
      script.removeEventListener("error", handleError)
      if (timeoutId !== null) window.clearTimeout(timeoutId)
    }

    const succeed = () => {
      if (settled) return
      settled = true
      script.setAttribute(TURNSTILE_LOADED_ATTRIBUTE, "true")
      cleanup()
      resolve()
    }

    const fail = () => {
      if (settled) return
      settled = true
      script.dataset.plmTurnstileError = "true"
      cleanup()
      script.remove()
      reject(new Error("Turnstile script failed to load"))
    }

    function handleLoad() {
      succeed()
    }

    function handleError() {
      fail()
    }

    timeoutId = window.setTimeout(fail, TURNSTILE_SCRIPT_TIMEOUT_MS)
    script.addEventListener("load", handleLoad, { once: true })
    script.addEventListener("error", handleError, { once: true })

    if (!existing) {
      document.head.appendChild(script)
    }
  })
}

async function loadTurnstileScript(): Promise<void> {
  if (typeof window === "undefined") return
  if (window.turnstile) {
    await waitForTurnstileReady()
    return
  }
  if (window.__plmTurnstileLoadPromise) {
    await window.__plmTurnstileLoadPromise
    return
  }
  window.__plmTurnstileLoadPromise = loadTurnstileScriptElement().then(waitForTurnstileReady)
  try {
    await window.__plmTurnstileLoadPromise
  } catch (error) {
    window.__plmTurnstileLoadPromise = undefined
    if (!window.turnstile) {
      document.querySelector<HTMLScriptElement>(TURNSTILE_SCRIPT_SELECTOR)?.remove()
    }
    throw error
  }
}

type TurnstileWidgetProps = {
  siteKey: string
  resetSignal: number
  onTokenChange: (token: string | null) => void
}

export function TurnstileWidget(props: TurnstileWidgetProps) {
  const { siteKey, resetSignal, onTokenChange } = props
  const containerRef = useRef<HTMLDivElement | null>(null)
  const widgetIdRef = useRef<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [loadAttempt, setLoadAttempt] = useState(0)

  const retryTurnstile = () => {
    onTokenChange(null)
    setLoadError(null)
    if (widgetIdRef.current && window.turnstile) {
      window.turnstile.remove(widgetIdRef.current)
      widgetIdRef.current = null
    }
    setLoadAttempt((attempt) => attempt + 1)
  }

  useEffect(() => {
    let cancelled = false
    onTokenChange(null)

    void loadTurnstileScript()
      .then(() => {
        if (cancelled || !containerRef.current || !window.turnstile) return
        setLoadError(null)
        if (widgetIdRef.current) {
          window.turnstile.remove(widgetIdRef.current)
          widgetIdRef.current = null
        }
        widgetIdRef.current = window.turnstile.render(containerRef.current, {
          sitekey: siteKey,
          action: "signup",
          theme: "light",
          callback: (token) => {
            if (!cancelled) onTokenChange(token || null)
          },
          "expired-callback": () => {
            if (!cancelled) onTokenChange(null)
          },
          "error-callback": () => {
            if (cancelled) return
            onTokenChange(null)
            setLoadError("人机校验加载失败，请点击重试校验。")
          },
        })
      })
      .catch(() => {
        if (cancelled) return
        onTokenChange(null)
        setLoadError("人机校验脚本加载失败，请点击重试校验。")
      })

    return () => {
      cancelled = true
      onTokenChange(null)
      if (widgetIdRef.current && window.turnstile) {
        window.turnstile.remove(widgetIdRef.current)
        widgetIdRef.current = null
      }
    }
  }, [loadAttempt, onTokenChange, siteKey])

  useEffect(() => {
    if (!resetSignal || !widgetIdRef.current || !window.turnstile) return
    window.turnstile.reset(widgetIdRef.current)
    onTokenChange(null)
  }, [onTokenChange, resetSignal])

  return (
    <div className="grid gap-2">
      <div ref={containerRef} className={cn("min-h-16")} />
      {loadError ? (
        <div className="flex flex-wrap items-center gap-2">
          <p className="text-xs leading-5 text-destructive">{loadError}</p>
          <button
            type="button"
            className="rounded-md border border-border px-2.5 py-1 text-xs font-medium text-foreground hover:bg-accent"
            onClick={retryTurnstile}
          >
            重试校验
          </button>
        </div>
      ) : (
        <p className="text-xs leading-5 text-muted-foreground">提交前请完成人机校验。</p>
      )}
    </div>
  )
}

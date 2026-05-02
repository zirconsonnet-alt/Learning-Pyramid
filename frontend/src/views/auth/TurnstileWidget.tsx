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

async function loadTurnstileScript(): Promise<void> {
  if (typeof window === "undefined") return
  if (window.turnstile) return
  if (window.__plmTurnstileLoadPromise) {
    await window.__plmTurnstileLoadPromise
    return
  }
  window.__plmTurnstileLoadPromise = new Promise<void>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>('script[data-plm-turnstile="true"]')
    if (existing) {
      existing.addEventListener("load", () => resolve(), { once: true })
      existing.addEventListener("error", () => reject(new Error("Turnstile script failed to load")), { once: true })
      return
    }
    const script = document.createElement("script")
    script.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit"
    script.async = true
    script.defer = true
    script.dataset.plmTurnstile = "true"
    script.onload = () => resolve()
    script.onerror = () => reject(new Error("Turnstile script failed to load"))
    document.head.appendChild(script)
  })
  try {
    await window.__plmTurnstileLoadPromise
  } catch (error) {
    window.__plmTurnstileLoadPromise = undefined
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

  useEffect(() => {
    let cancelled = false
    onTokenChange(null)
    setLoadError(null)

    void loadTurnstileScript()
      .then(() => {
        if (cancelled || !containerRef.current || !window.turnstile) return
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
            setLoadError("人机校验加载失败，请刷新页面后重试。")
          },
        })
      })
      .catch(() => {
        if (cancelled) return
        onTokenChange(null)
        setLoadError("人机校验脚本加载失败，请稍后重试。")
      })

    return () => {
      cancelled = true
      onTokenChange(null)
      if (widgetIdRef.current && window.turnstile) {
        window.turnstile.remove(widgetIdRef.current)
        widgetIdRef.current = null
      }
    }
  }, [onTokenChange, siteKey])

  useEffect(() => {
    if (!resetSignal || !widgetIdRef.current || !window.turnstile) return
    window.turnstile.reset(widgetIdRef.current)
    onTokenChange(null)
  }, [onTokenChange, resetSignal])

  return (
    <div className="grid gap-2">
      <div ref={containerRef} className={cn("min-h-16")} />
      <p className={cn("text-xs leading-5", loadError ? "text-destructive" : "text-muted-foreground")}>
        {loadError ?? "提交前请完成人机校验。"}
      </p>
    </div>
  )
}

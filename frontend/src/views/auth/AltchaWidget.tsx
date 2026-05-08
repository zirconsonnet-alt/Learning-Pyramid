import "altcha"

import type { CSSProperties } from "react"
import { useEffect, useRef, useState } from "react"

type AltchaElement = HTMLElement &
  {
    value?: string
    reset?: () => void
  }

const ALTCHA_STYLE: CSSProperties = {
  "--altcha-border-color": "hsl(var(--border))",
  "--altcha-border-radius": "14px",
  "--altcha-color-base": "rgba(255, 255, 255, 0.62)",
  "--altcha-color-primary": "hsl(var(--primary))",
  "--altcha-max-width": "100%",
} as CSSProperties

declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "altcha-widget": React.DetailedHTMLProps<React.HTMLAttributes<AltchaElement>, AltchaElement> & {
        challenge?: string
        name?: string
        auto?: string
        type?: string
        language?: string
      }
    }
  }
}

type AltchaWidgetProps = {
  challengeUrl: string
  resetSignal: number
  onTokenChange: (token: string | null) => void
}

function extractVerifiedPayload(event: Event, widget: AltchaElement | null): string | null {
  const detail = (event as CustomEvent<{ payload?: unknown }>).detail
  if (typeof detail?.payload === "string" && detail.payload.trim()) {
    return detail.payload.trim()
  }
  if (typeof widget?.value === "string" && widget.value.trim()) {
    return widget.value.trim()
  }
  const input = widget?.querySelector<HTMLInputElement>('input[name="altcha"]')
  const value = input?.value?.trim()
  return value || null
}

export function AltchaWidget(props: AltchaWidgetProps) {
  const { challengeUrl, resetSignal, onTokenChange } = props
  const widgetRef = useRef<AltchaElement | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const widget = widgetRef.current
    if (!widget) return

    const handleVerified = (event: Event) => {
      setError(null)
      onTokenChange(extractVerifiedPayload(event, widget))
    }
    const handleStateChange = (event: Event) => {
      const state = String((event as CustomEvent<{ state?: unknown }>).detail?.state ?? "")
      if (state === "error") {
        setError("人机校验失败，请重试。")
        onTokenChange(null)
      } else if (state === "expired") {
        setError("人机校验已过期，请重新校验。")
        onTokenChange(null)
      } else if (state !== "verified") {
        setError(null)
        onTokenChange(null)
      }
    }
    const handleExpired = () => {
      setError("人机校验已过期，请重新校验。")
      onTokenChange(null)
    }

    widget.addEventListener("verified", handleVerified)
    widget.addEventListener("statechange", handleStateChange)
    widget.addEventListener("expired", handleExpired)
    return () => {
      widget.removeEventListener("verified", handleVerified)
      widget.removeEventListener("statechange", handleStateChange)
      widget.removeEventListener("expired", handleExpired)
    }
  }, [onTokenChange])

  useEffect(() => {
    onTokenChange(null)
    setError(null)
    widgetRef.current?.reset?.()
  }, [challengeUrl, resetSignal, onTokenChange])

  return (
    <div className="grid gap-2">
      <altcha-widget
        ref={widgetRef}
        challenge={challengeUrl}
        name="altcha"
        auto="onload"
        type="checkbox"
        language="zh-cn"
        style={ALTCHA_STYLE}
      />
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
    </div>
  )
}

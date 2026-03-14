import { useEffect } from "react"
import { AlertCircle, CheckCircle2, Info, X } from "lucide-react"

import { Button } from "@/ui/components/ui/button"
import { type FeedbackItem, type FeedbackTone, useFeedbackStore } from "@/ui/store/feedbackStore"
import { cn } from "@/ui/utils"

function toneStyles(tone: FeedbackTone) {
  if (tone === "success") {
    return {
      shell: "border-emerald-200/80 bg-[linear-gradient(180deg,rgba(236,253,245,0.98),rgba(255,255,255,0.96))] text-emerald-950 shadow-[0_24px_50px_-34px_rgba(5,150,105,0.38)]",
      iconWrap: "bg-emerald-100 text-emerald-700",
      icon: CheckCircle2,
    }
  }
  if (tone === "error") {
    return {
      shell: "border-rose-200/80 bg-[linear-gradient(180deg,rgba(255,241,242,0.98),rgba(255,255,255,0.96))] text-rose-950 shadow-[0_24px_50px_-34px_rgba(225,29,72,0.34)]",
      iconWrap: "bg-rose-100 text-rose-700",
      icon: AlertCircle,
    }
  }
  return {
    shell: "border-sky-200/80 bg-[linear-gradient(180deg,rgba(239,246,255,0.98),rgba(255,255,255,0.96))] text-sky-950 shadow-[0_24px_50px_-34px_rgba(14,116,144,0.28)]",
    iconWrap: "bg-sky-100 text-sky-700",
    icon: Info,
  }
}

function FeedbackToast({ item }: { item: FeedbackItem }) {
  const dismiss = useFeedbackStore((state) => state.dismiss)
  const styles = toneStyles(item.tone)
  const Icon = styles.icon

  useEffect(() => {
    const timeoutId = window.setTimeout(() => dismiss(item.id), item.durationMs)
    return () => {
      window.clearTimeout(timeoutId)
    }
  }, [dismiss, item.durationMs, item.id])

  return (
    <div
      className={cn(
        "pointer-events-auto flex w-full items-start gap-3 rounded-[1.35rem] border px-4 py-4 backdrop-blur-xl animate-in slide-in-from-top-2 fade-in-50",
        styles.shell,
      )}
      role="status"
      aria-live="polite"
    >
      <div className={cn("mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl", styles.iconWrap)}>
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0 flex-1 space-y-1">
        <p className="text-sm font-semibold tracking-tight">{item.title}</p>
        {item.message ? <p className="text-sm leading-6 text-current/75">{item.message}</p> : null}
      </div>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-8 w-8 shrink-0 rounded-xl text-current/60 hover:bg-white/40 hover:text-current"
        onClick={() => dismiss(item.id)}
      >
        <X className="h-4 w-4" />
        <span className="sr-only">关闭提示</span>
      </Button>
    </div>
  )
}

export function FeedbackViewport() {
  const items = useFeedbackStore((state) => state.items)

  if (items.length === 0) return null

  return (
    <div className="pointer-events-none fixed inset-x-0 top-4 z-[70] flex justify-center px-4 sm:justify-end sm:px-6">
      <div className="flex w-full max-w-md flex-col gap-3">
        {items.map((item) => (
          <FeedbackToast key={item.id} item={item} />
        ))}
      </div>
    </div>
  )
}

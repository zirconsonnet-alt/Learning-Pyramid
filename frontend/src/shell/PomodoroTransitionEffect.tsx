import { useEffect, useRef, useState } from "react"
import { Coffee, Lock, Sparkles, TimerReset } from "lucide-react"

import { detectPomodoroPhaseTransition, type PomodoroTransitionSnapshot } from "@/ui/pomodoroAudio"
import { formatPomodoroCountdown, type PomodoroSnapshot } from "@/ui/store/pomodoroStore"

type TransitionCardState = {
  id: number
  phase: "focus" | "break"
  currentPomodoro: number
  totalPomodoros: number
  breakMinutes: number
  hasProjectBinding: boolean
  projectTitle: string | null
}

function buildTransitionCopy(transition: TransitionCardState) {
  if (transition.phase === "focus") {
    const projectText = transition.projectTitle ? `“${transition.projectTitle}”` : "对应项目"
    return {
      eyebrow: transition.currentPomodoro <= 1 ? "Focus Window" : "Back To Focus",
      title: transition.currentPomodoro <= 1 ? "学习时间到了" : "回到学习节奏",
      description: transition.hasProjectBinding
        ? `第 ${transition.currentPomodoro}/${transition.totalPomodoros} 个番茄已经开始，系统正在切入 ${projectText} 的工作台。`
        : `第 ${transition.currentPomodoro}/${transition.totalPomodoros} 个番茄已经开始，工作台重新解锁，但这个番茄还没有绑定项目。`,
      statusLabel: "工作台已解锁",
      phaseLabel: `番茄 ${transition.currentPomodoro}`,
      icon: Sparkles,
      overlayBackground:
        "radial-gradient(circle at 50% 40%, rgba(87, 160, 233, 0.28), transparent 26%), linear-gradient(180deg, rgba(237, 245, 255, 0.2), rgba(226, 239, 255, 0.12))",
      cardBackground:
        "linear-gradient(145deg, rgba(255,255,255,0.94), rgba(240,247,255,0.9))",
      borderColor: "rgba(142, 183, 230, 0.78)",
      shadowColor: "0 34px 80px -42px rgba(40, 109, 187, 0.46)",
      iconBackground: "linear-gradient(145deg, rgba(53, 129, 214, 0.18), rgba(79, 177, 164, 0.2))",
      iconColor: "#1f63b8",
      chipBackground: "rgba(38, 107, 189, 0.11)",
      chipText: "#235b94",
      shimmerBackground:
        "linear-gradient(90deg, transparent, rgba(255,255,255,0.72), transparent)",
      pulseColor: "rgba(75, 150, 223, 0.26)",
    }
  }
  return {
    eyebrow: "Reset Window",
    title: "休息一下",
    description: `第 ${transition.currentPomodoro} 个番茄刚结束，先休息 ${transition.breakMinutes} 分钟。工作台会在下一段学习时间自动重新放行。`,
    statusLabel: "工作台已锁定",
    phaseLabel: `休息 ${transition.currentPomodoro}`,
    icon: Coffee,
    overlayBackground:
      "radial-gradient(circle at 50% 40%, rgba(240, 178, 91, 0.26), transparent 26%), linear-gradient(180deg, rgba(255, 247, 236, 0.18), rgba(255, 241, 224, 0.1))",
    cardBackground:
      "linear-gradient(145deg, rgba(255,251,246,0.96), rgba(255,244,230,0.92))",
    borderColor: "rgba(238, 194, 126, 0.86)",
    shadowColor: "0 34px 80px -42px rgba(181, 118, 36, 0.4)",
    iconBackground: "linear-gradient(145deg, rgba(217, 147, 59, 0.18), rgba(252, 208, 132, 0.24))",
    iconColor: "#9a5e18",
    chipBackground: "rgba(185, 120, 30, 0.12)",
    chipText: "#8f5717",
    shimmerBackground:
      "linear-gradient(90deg, transparent, rgba(255,255,255,0.68), transparent)",
    pulseColor: "rgba(230, 172, 90, 0.28)",
  }
}

export function PomodoroTransitionEffect(props: {
  snapshot: PomodoroSnapshot
  enabled: boolean
  currentProjectTitle?: string | null
}) {
  const { snapshot, enabled, currentProjectTitle } = props
  const [activeTransition, setActiveTransition] = useState<TransitionCardState | null>(null)
  const previousSnapshotRef = useRef<PomodoroTransitionSnapshot | null>(null)
  const hideTimerRef = useRef<number | null>(null)

  useEffect(() => {
    return () => {
      if (hideTimerRef.current !== null) {
        window.clearTimeout(hideTimerRef.current)
      }
    }
  }, [])

  useEffect(() => {
    const previous = previousSnapshotRef.current
    const currentSnapshot: PomodoroTransitionSnapshot = {
      status: snapshot.status,
      phase: snapshot.phase,
      segmentIndex: snapshot.segmentIndex,
    }
    previousSnapshotRef.current = currentSnapshot
    if (!enabled) return
    const transition = detectPomodoroPhaseTransition(previous, currentSnapshot)
    if (!transition) return

    const nextCard: TransitionCardState = {
      id: Date.now(),
      phase: transition.toPhase,
      currentPomodoro: snapshot.currentPomodoro,
      totalPomodoros: snapshot.totalPomodoros,
      breakMinutes: snapshot.currentPlan?.breakMinutes ?? 5,
      hasProjectBinding: Boolean(currentProjectTitle),
      projectTitle: currentProjectTitle ?? null,
    }
    setActiveTransition(nextCard)

    if (hideTimerRef.current !== null) {
      window.clearTimeout(hideTimerRef.current)
    }
    hideTimerRef.current = window.setTimeout(() => {
      setActiveTransition((current) => (current?.id === nextCard.id ? null : current))
    }, 2200)
  }, [currentProjectTitle, enabled, snapshot])

  if (!activeTransition) return null

  const copy = buildTransitionCopy(activeTransition)
  const Icon = copy.icon

  return (
    <div className="pointer-events-none fixed inset-0 z-[60] overflow-hidden" aria-hidden="true">
      <div className="pomodoro-transition-overlay absolute inset-0" style={{ background: copy.overlayBackground }} />

      <div className="absolute left-1/2 top-1/2 h-[22rem] w-[22rem] -translate-x-1/2 -translate-y-1/2">
        <div className="pomodoro-transition-pulse absolute inset-0 rounded-full" style={{ background: copy.pulseColor }} />
        <div
          className="pomodoro-transition-pulse absolute inset-[14%] rounded-full"
          style={{ background: copy.pulseColor, animationDelay: "180ms" }}
        />
      </div>

      <div className="absolute inset-0 flex items-center justify-center px-4">
        <div
          className="pomodoro-transition-card relative w-full max-w-[32rem] overflow-hidden rounded-[2rem] border px-5 py-5 sm:px-6 sm:py-6"
          style={{
            background: copy.cardBackground,
            borderColor: copy.borderColor,
            boxShadow: copy.shadowColor,
          }}
        >
          <div
            className="pomodoro-transition-sweep absolute inset-y-0 left-[-30%] w-[46%] -skew-x-12 opacity-80"
            style={{ background: copy.shimmerBackground }}
          />

          <div className="relative flex items-start gap-4">
            <div
              className="relative flex h-14 w-14 shrink-0 items-center justify-center rounded-[1.3rem] border border-white/45"
              style={{ background: copy.iconBackground, color: copy.iconColor }}
            >
              <Icon className="h-6 w-6" />
            </div>

            <div className="min-w-0 flex-1">
              <div className="text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                {copy.eyebrow}
              </div>
              <div className="mt-2 text-[1.9rem] font-semibold tracking-[-0.05em] text-foreground">
                {copy.title}
              </div>
              <p className="mt-2 text-sm leading-7 text-[color:var(--theme-soft-text-strong)]">
                {copy.description}
              </p>
            </div>
          </div>

          <div className="relative mt-5 grid gap-3 sm:grid-cols-2">
            <div
              className="rounded-[1.1rem] border border-white/45 px-4 py-3"
              style={{ background: copy.chipBackground }}
            >
              <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">状态</div>
              <div className="mt-2 text-sm font-semibold" style={{ color: copy.chipText }}>
                {copy.statusLabel}
              </div>
            </div>

            <div
              className="rounded-[1.1rem] border border-white/45 px-4 py-3"
              style={{ background: copy.chipBackground }}
            >
              <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">当前阶段</div>
              <div className="mt-2 text-sm font-semibold" style={{ color: copy.chipText }}>
                {copy.phaseLabel}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export function PomodoroPreTransitionNotice(props: {
  phase: "focus" | "break"
  countdownMs: number
  currentPomodoro: number
  totalPomodoros: number
  projectTitle?: string | null
}) {
  const { phase, countdownMs, currentPomodoro, totalPomodoros, projectTitle } = props
  if (countdownMs <= 0 || countdownMs > 10_000) return null
  const Icon = phase === "focus" ? TimerReset : Lock
  const title = phase === "focus" ? "学习时间即将开始" : "休息时间即将开始"
  const description =
    phase === "focus"
      ? `${formatPomodoroCountdown(countdownMs)} 后会自动跳到${projectTitle ? `“${projectTitle}”` : "已绑定项目"}的工作台，开始第 ${currentPomodoro}/${totalPomodoros} 个番茄。`
      : `${formatPomodoroCountdown(countdownMs)} 后进入休息时间，当前工作台会被锁定。`
  return (
    <div className="pointer-events-none fixed inset-x-0 top-20 z-[58] flex justify-center px-4" aria-hidden="true">
      <div className="w-full max-w-[30rem] rounded-[1.35rem] border border-primary/15 bg-[linear-gradient(140deg,rgba(255,255,255,0.96),rgba(240,247,255,0.92))] px-4 py-4 shadow-[0_26px_60px_-34px_rgba(31,99,184,0.38)] backdrop-blur-xl">
        <div className="flex items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[1rem] border border-primary/10 bg-[hsl(var(--primary)/0.1)] text-primary">
            <Icon className="h-4.5 w-4.5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[11px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
              {phase === "focus" ? "Upcoming Jump" : "Upcoming Lock"}
            </div>
            <div className="mt-1 text-base font-semibold text-foreground">{title}</div>
            <p className="mt-1 text-sm leading-6 text-[color:var(--theme-soft-text-strong)]">{description}</p>
          </div>
        </div>
      </div>
    </div>
  )
}

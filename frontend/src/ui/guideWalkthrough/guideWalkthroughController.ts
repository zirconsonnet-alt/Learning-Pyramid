import { useEffect, useRef, type MutableRefObject } from "react"
import { driver, type AllowedButtons, type DriveStep, type Driver } from "driver.js"

import { resolveGuideWalkthroughCopy } from "./guideWalkthroughCopy"
import {
  GUIDE_WALKTHROUGH_STEPS,
  type GuideWalkthroughSessionStatus,
  type GuideWalkthroughStep,
} from "./guideWalkthroughSteps"
import { showInfoFeedback } from "@/ui/store/feedbackStore"
import { describePomodoroPhase, getPomodoroSnapshot, usePomodoroStore } from "@/ui/store/pomodoroStore"

const START_GUIDE_WALKTHROUGH_EVENT = "learningpyramid:start-guide-walkthrough"
const DESTROY_GUIDE_WALKTHROUGH_EVENT = "learningpyramid:destroy-guide-walkthrough"
const REFRESH_GUIDE_WALKTHROUGH_EVENT = "learningpyramid:refresh-guide-walkthrough"
const GUIDE_WALKTHROUGH_STEP_COMPLETED_EVENT = "learningpyramid:guide-walkthrough-step-completed"
const SUPPORTED_FALLBACK_MODES = ["centered-popover", "route-hint", "skip-with-explanation"] as const
const ACTION_STEP_BUTTONS: AllowedButtons[] = ["close"]
const TARGET_WAIT_INTERVAL_MS = 50
const TARGET_WAIT_MAX_ATTEMPTS = 20
const GUIDE_WALKTHROUGH_POMODORO_NON_FOCUS_TITLE = "当前不是学习时间"
const GUIDE_WALKTHROUGH_POMODORO_NON_FOCUS_MESSAGE = "当前处于{phaseLabel}，工作台会在下一段学习时间重新放行。本次引导先到这里。"

type GuideNavigate = (to: string, options?: { replace?: boolean }) => void

type BuildDriverStepsOptions = {
  getPathname: () => string
  navigate: GuideNavigate
}

function dispatchGuideWalkthroughEvent(name: string) {
  if (typeof window === "undefined") return
  window.dispatchEvent(new Event(name))
}

function dispatchGuideWalkthroughCustomEvent(name: string, detail: Record<string, string>) {
  if (typeof window === "undefined") return
  window.dispatchEvent(new CustomEvent(name, { detail }))
}

export function startGuideWalkthrough() {
  dispatchGuideWalkthroughEvent(START_GUIDE_WALKTHROUGH_EVENT)
  return true
}

export function destroyGuideWalkthrough() {
  dispatchGuideWalkthroughEvent(DESTROY_GUIDE_WALKTHROUGH_EVENT)
}

function isWorkbenchGuideStep(step: GuideWalkthroughStep | undefined) {
  return Boolean(step?.routeHint?.includes("/workbench"))
}

export function shouldEndGuideWalkthroughBeforeWorkbench(step: GuideWalkthroughStep | undefined, now = Date.now()) {
  if (!isWorkbenchGuideStep(step)) return false
  const state = usePomodoroStore.getState()
  const snapshot = getPomodoroSnapshot({ enabled: state.enabled, weeklySchedule: state.weeklySchedule, quickPomodoro: state.quickPomodoro }, now)
  return snapshot.shouldRestrictWorkbench && !snapshot.canUseWorkbench
}

function notifyGuideWalkthroughEndedBeforeWorkbench(now = Date.now()) {
  const state = usePomodoroStore.getState()
  const snapshot = getPomodoroSnapshot({ enabled: state.enabled, weeklySchedule: state.weeklySchedule, quickPomodoro: state.quickPomodoro }, now)
  const phaseLabel = describePomodoroPhase(
    snapshot.phase,
    snapshot.status,
    snapshot.idleReason,
    snapshot.enabled,
    snapshot.hasEnabledSchedule,
  )
  showInfoFeedback(
    GUIDE_WALKTHROUGH_POMODORO_NON_FOCUS_TITLE,
    GUIDE_WALKTHROUGH_POMODORO_NON_FOCUS_MESSAGE.replace("{phaseLabel}", phaseLabel),
  )
}

export function refreshGuideWalkthrough() {
  dispatchGuideWalkthroughEvent(REFRESH_GUIDE_WALKTHROUGH_EVENT)
}

export function completeGuideWalkthroughStep(stepId: GuideWalkthroughStep["id"]) {
  dispatchGuideWalkthroughCustomEvent(GUIDE_WALKTHROUGH_STEP_COMPLETED_EVENT, { stepId })
}

function escapeGuideTourAnchor(anchor: string) {
  return anchor.replaceAll("\\", "\\\\").replaceAll('"', '\\"')
}

function guideTourSelector(anchor: string) {
  return `[data-guide-tour="${escapeGuideTourAnchor(anchor)}"]`
}

export function resolveGuideTargetElement(step: GuideWalkthroughStep) {
  if (typeof document === "undefined" || !step.targetAnchor) return null
  return document.querySelector<HTMLElement>(guideTourSelector(step.targetAnchor))
}

export function handleRouteHint(step: GuideWalkthroughStep | undefined, navigate: GuideNavigate, pathname: string) {
  if (!step?.routeHint || step.routeHint.includes(":")) return false
  if (pathname === step.routeHint || pathname.startsWith(`${step.routeHint}/`)) return false
  navigate(step.routeHint)
  return true
}

function getCurrentPathname(fallback: string) {
  return typeof window === "undefined" ? fallback : window.location.pathname
}

function getActiveGuideWalkthroughStep(driverInstance: Driver, fallbackIndex: number) {
  const activeIndex = driverInstance.getActiveIndex() ?? fallbackIndex
  const step = GUIDE_WALKTHROUGH_STEPS[activeIndex]
  return step ? { activeIndex, step } : null
}

function waitForStepTarget(step: GuideWalkthroughStep, onReady: () => void, attempt = 0) {
  if (typeof window === "undefined" || !step.targetAnchor || resolveGuideTargetElement(step) || attempt >= TARGET_WAIT_MAX_ATTEMPTS) {
    onReady()
    return
  }

  window.setTimeout(() => waitForStepTarget(step, onReady, attempt + 1), TARGET_WAIT_INTERVAL_MS)
}

function advanceGuideWalkthroughFromIndex(driverInstance: Driver, stepIndex: number, options: BuildDriverStepsOptions) {
  const nextIndex = stepIndex + 1
  const nextStep = GUIDE_WALKTHROUGH_STEPS[nextIndex]
  if (!nextStep) {
    driverInstance.destroy()
    return
  }
  if (shouldEndGuideWalkthroughBeforeWorkbench(nextStep)) {
    notifyGuideWalkthroughEndedBeforeWorkbench()
    cleanupGuideWalkthrough({ current: driverInstance } as MutableRefObject<Driver | null>)
    return
  }

  const didNavigate = handleRouteHint(nextStep, options.navigate, options.getPathname())
  window.setTimeout(
    () => {
      waitForStepTarget(nextStep, () => {
        if (!driverInstance.isActive()) return
        replaceGuideWalkthroughSteps(driverInstance, options)
        driverInstance.moveTo(nextIndex)
      })
    },
    didNavigate ? 160 : 0,
  )
}

function completeActiveGuideWalkthroughStep(driverInstance: Driver, stepId: string, fallbackIndex: number, options: BuildDriverStepsOptions) {
  const active = getActiveGuideWalkthroughStep(driverInstance, fallbackIndex)
  if (!active || active.step.id !== stepId) return
  advanceGuideWalkthroughFromIndex(driverInstance, active.activeIndex, options)
}

function createPopover(step: GuideWalkthroughStep, stepIndex: number, options: BuildDriverStepsOptions, hasTarget: boolean): DriveStep["popover"] {
  const copy = resolveGuideWalkthroughCopy(step.sourceRef)
  const showButtons = hasTarget && step.advanceOn && step.advanceOn !== "manual" ? ACTION_STEP_BUTTONS : undefined
  return {
    title: step.popoverTitle ?? copy.title,
    description: copy.description,
    side: hasTarget ? step.popoverSide : "over",
    align: "center",
    showButtons,
    onNextClick: (_element, _driverStep, opts) => {
      advanceGuideWalkthroughFromIndex(opts.driver, opts.driver.getActiveIndex() ?? stepIndex, options)
    },
  }
}

export function buildFallbackDriverStep(step: GuideWalkthroughStep, stepIndex: number, options: BuildDriverStepsOptions): DriveStep {
  const popover = createPopover(step, stepIndex, options, false)
  const fallbackMode = SUPPORTED_FALLBACK_MODES.includes(step.fallbackMode) ? step.fallbackMode : "centered-popover"
  return {
    popover: {
      ...popover,
      popoverClass: `guide-walkthrough-fallback guide-walkthrough-fallback-${fallbackMode}`,
    },
  }
}

function buildDriverStep(step: GuideWalkthroughStep, stepIndex: number, options: BuildDriverStepsOptions): DriveStep {
  const target = resolveGuideTargetElement(step)
  if (!target) return buildFallbackDriverStep(step, stepIndex, options)

  return {
    element: target,
    onHighlighted: (element, _driverStep, opts) => {
      if (step.advanceOn !== "target-click" || !element) return
      element.addEventListener(
        "click",
        (event) => {
          if (!opts.driver.isActive()) return
          if (shouldEndGuideWalkthroughBeforeWorkbench(step)) {
            event.preventDefault()
            event.stopPropagation()
            notifyGuideWalkthroughEndedBeforeWorkbench()
            opts.driver.destroy()
            return
          }
          completeActiveGuideWalkthroughStep(opts.driver, step.id, stepIndex, options)
        },
        { once: true, capture: true },
      )
    },
    popover: createPopover(step, stepIndex, options, true),
  }
}

function buildDriverSteps(options: BuildDriverStepsOptions) {
  return GUIDE_WALKTHROUGH_STEPS.map((step, index) => buildDriverStep(step, index, options))
}

function replaceGuideWalkthroughSteps(driverInstance: Driver, options: BuildDriverStepsOptions) {
  driverInstance.setConfig({
    ...driverInstance.getConfig(),
    steps: buildDriverSteps(options),
  })
}

function waitForInitialTarget(step: GuideWalkthroughStep, onReady: () => void, attempt = 0) {
  waitForStepTarget(step, onReady, attempt)
}

export function cleanupGuideWalkthrough(
  driverRef?: MutableRefObject<Driver | null>,
  statusRef?: MutableRefObject<GuideWalkthroughSessionStatus>,
) {
  const currentDriver = driverRef?.current ?? null
  if (driverRef) driverRef.current = null
  if (statusRef) statusRef.current = "idle"
  if (currentDriver?.isActive()) currentDriver.destroy()
}

export function useGuideWalkthroughController({ navigate, pathname }: { navigate: GuideNavigate; pathname: string }) {
  const driverRef = useRef<Driver | null>(null)
  const statusRef = useRef<GuideWalkthroughSessionStatus>("idle")
  const latestPathnameRef = useRef(pathname)

  useEffect(() => {
    latestPathnameRef.current = pathname
    if (!driverRef.current?.isActive()) return
    replaceGuideWalkthroughSteps(driverRef.current, {
      getPathname: () => getCurrentPathname(latestPathnameRef.current),
      navigate,
    })
    driverRef.current.refresh()
  }, [navigate, pathname])

  useEffect(() => {
    const options: BuildDriverStepsOptions = {
      getPathname: () => getCurrentPathname(latestPathnameRef.current),
      navigate,
    }

    function runWalkthrough() {
      cleanupGuideWalkthrough(driverRef, statusRef)
      statusRef.current = "running"

      const firstStep = GUIDE_WALKTHROUGH_STEPS[0]
      const didNavigate = handleRouteHint(firstStep, navigate, options.getPathname())

      window.setTimeout(
        () => {
          waitForInitialTarget(firstStep, () => {
            const walkthroughDriver = driver({
              allowClose: true,
              animate: true,
              disableActiveInteraction: false,
              doneBtnText: "完成",
              nextBtnText: "下一步",
              overlayClickBehavior: "close",
              popoverClass: "guide-walkthrough-popover",
              prevBtnText: "上一步",
              progressText: "{{current}} / {{total}}",
              showProgress: true,
              stagePadding: 8,
              stageRadius: 12,
              steps: buildDriverSteps(options),
              onDestroyed: () => {
                driverRef.current = null
                statusRef.current = "closed"
                window.setTimeout(() => {
                  if (statusRef.current === "closed") statusRef.current = "idle"
                }, 0)
              },
            })

            driverRef.current = walkthroughDriver
            walkthroughDriver.drive()
          })
        },
        didNavigate ? 180 : 0,
      )
    }

    function destroyActiveWalkthrough() {
      cleanupGuideWalkthrough(driverRef, statusRef)
    }

    function refreshActiveWalkthrough() {
      if (!driverRef.current?.isActive()) return
      replaceGuideWalkthroughSteps(driverRef.current, options)
      driverRef.current.refresh()
    }

    function completeActiveWalkthroughStep(event: Event) {
      if (!driverRef.current?.isActive() || !(event instanceof CustomEvent)) return
      const stepId = typeof event.detail?.stepId === "string" ? event.detail.stepId : ""
      if (!stepId) return
      completeActiveGuideWalkthroughStep(driverRef.current, stepId, driverRef.current.getActiveIndex() ?? 0, options)
    }

    window.addEventListener(START_GUIDE_WALKTHROUGH_EVENT, runWalkthrough)
    window.addEventListener(DESTROY_GUIDE_WALKTHROUGH_EVENT, destroyActiveWalkthrough)
    window.addEventListener(REFRESH_GUIDE_WALKTHROUGH_EVENT, refreshActiveWalkthrough)
    window.addEventListener(GUIDE_WALKTHROUGH_STEP_COMPLETED_EVENT, completeActiveWalkthroughStep)

    return () => {
      window.removeEventListener(START_GUIDE_WALKTHROUGH_EVENT, runWalkthrough)
      window.removeEventListener(DESTROY_GUIDE_WALKTHROUGH_EVENT, destroyActiveWalkthrough)
      window.removeEventListener(REFRESH_GUIDE_WALKTHROUGH_EVENT, refreshActiveWalkthrough)
      window.removeEventListener(GUIDE_WALKTHROUGH_STEP_COMPLETED_EVENT, completeActiveWalkthroughStep)
      cleanupGuideWalkthrough(driverRef, statusRef)
    }
  }, [navigate])
}

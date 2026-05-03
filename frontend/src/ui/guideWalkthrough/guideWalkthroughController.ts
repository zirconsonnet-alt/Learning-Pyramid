import { useEffect, useRef, type MutableRefObject } from "react"
import { driver, type DriveStep, type Driver } from "driver.js"

import { resolveGuideWalkthroughCopy } from "./guideWalkthroughCopy"
import {
  GUIDE_WALKTHROUGH_STEPS,
  type GuideWalkthroughSessionStatus,
  type GuideWalkthroughStep,
} from "./guideWalkthroughSteps"

const START_GUIDE_WALKTHROUGH_EVENT = "learningpyramid:start-guide-walkthrough"
const DESTROY_GUIDE_WALKTHROUGH_EVENT = "learningpyramid:destroy-guide-walkthrough"
const REFRESH_GUIDE_WALKTHROUGH_EVENT = "learningpyramid:refresh-guide-walkthrough"
const SUPPORTED_FALLBACK_MODES = ["centered-popover", "route-hint", "skip-with-explanation"] as const
const TARGET_WAIT_INTERVAL_MS = 50
const TARGET_WAIT_MAX_ATTEMPTS = 20

type GuideNavigate = (to: string, options?: { replace?: boolean }) => void

type BuildDriverStepsOptions = {
  getPathname: () => string
  navigate: GuideNavigate
}

function dispatchGuideWalkthroughEvent(name: string) {
  if (typeof window === "undefined") return
  window.dispatchEvent(new Event(name))
}

export function startGuideWalkthrough() {
  dispatchGuideWalkthroughEvent(START_GUIDE_WALKTHROUGH_EVENT)
}

export function destroyGuideWalkthrough() {
  dispatchGuideWalkthroughEvent(DESTROY_GUIDE_WALKTHROUGH_EVENT)
}

export function refreshGuideWalkthrough() {
  dispatchGuideWalkthroughEvent(REFRESH_GUIDE_WALKTHROUGH_EVENT)
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

function createPopover(step: GuideWalkthroughStep, stepIndex: number, options: BuildDriverStepsOptions, hasTarget: boolean): DriveStep["popover"] {
  const copy = resolveGuideWalkthroughCopy(step.sourceRef)
  return {
    title: copy.title,
    description: copy.description,
    side: hasTarget ? step.popoverSide : "over",
    align: "center",
    onNextClick: (_element, _driverStep, opts) => {
      const nextIndex = (opts.driver.getActiveIndex() ?? stepIndex) + 1
      const nextStep = GUIDE_WALKTHROUGH_STEPS[nextIndex]
      if (!nextStep) {
        opts.driver.destroy()
        return
      }

      const didNavigate = handleRouteHint(nextStep, options.navigate, options.getPathname())
      if (didNavigate) {
        window.setTimeout(() => {
          opts.driver.setSteps(buildDriverSteps(options))
          opts.driver.moveNext()
        }, 160)
        return
      }

      opts.driver.moveNext()
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
    popover: createPopover(step, stepIndex, options, true),
  }
}

function buildDriverSteps(options: BuildDriverStepsOptions) {
  return GUIDE_WALKTHROUGH_STEPS.map((step, index) => buildDriverStep(step, index, options))
}

function waitForInitialTarget(step: GuideWalkthroughStep, onReady: () => void, attempt = 0) {
  if (!step.targetAnchor || resolveGuideTargetElement(step) || attempt >= TARGET_WAIT_MAX_ATTEMPTS) {
    onReady()
    return
  }

  window.setTimeout(() => waitForInitialTarget(step, onReady, attempt + 1), TARGET_WAIT_INTERVAL_MS)
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
    driverRef.current.setSteps(
      buildDriverSteps({
        getPathname: () => getCurrentPathname(latestPathnameRef.current),
        navigate,
      }),
    )
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
      driverRef.current.setSteps(buildDriverSteps(options))
      driverRef.current.refresh()
    }

    window.addEventListener(START_GUIDE_WALKTHROUGH_EVENT, runWalkthrough)
    window.addEventListener(DESTROY_GUIDE_WALKTHROUGH_EVENT, destroyActiveWalkthrough)
    window.addEventListener(REFRESH_GUIDE_WALKTHROUGH_EVENT, refreshActiveWalkthrough)

    return () => {
      window.removeEventListener(START_GUIDE_WALKTHROUGH_EVENT, runWalkthrough)
      window.removeEventListener(DESTROY_GUIDE_WALKTHROUGH_EVENT, destroyActiveWalkthrough)
      window.removeEventListener(REFRESH_GUIDE_WALKTHROUGH_EVENT, refreshActiveWalkthrough)
      cleanupGuideWalkthrough(driverRef, statusRef)
    }
  }, [navigate])
}

import { useEffect, useRef, type MutableRefObject } from "react"
import { driver, type AllowedButtons, type DriveStep, type Driver } from "driver.js"

import { resolveGuideWalkthroughCopy } from "./guideWalkthroughCopy"
import {
  DEFAULT_GUIDE_WALKTHROUGH_DOC_SLUG,
  GUIDE_WALKTHROUGH_STEPS,
  getGuideWalkthroughSteps,
  isGuideWalkthroughDocSlug,
  type GuideWalkthroughDocSlug,
  type GuideWalkthroughSessionStatus,
  type GuideWalkthroughStep,
} from "./guideWalkthroughSteps"
import { showInfoFeedback } from "@/ui/store/feedbackStore"
import { useAppStore } from "@/ui/store/appStore"
import {
  describePomodoroPhase,
  getActivePomodoroDayPlans,
  getPomodoroSnapshot,
  hasEnabledPomodoroSchedule,
  usePomodoroStore,
  type PomodoroSnapshot,
} from "@/ui/store/pomodoroStore"
import {
  VIRTUAL_STUDY_REVIEW_PROJECT_ID,
  isVirtualStudyReviewProjectId,
} from "@/ui/guideWalkthrough/guideVirtualProjectIds"
import {
  clearVirtualStudyReviewProjectSession,
  startVirtualStudyReviewProjectSession,
} from "@/ui/guideWalkthrough/virtualStudyReviewProject"

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

const WALKTHROUGH_QUERY_PARAM = "walkthrough"

type BuildDriverStepsOptions = {
  getPathname: () => string
  navigate: GuideNavigate
  getDocSlug: () => GuideWalkthroughDocSlug
  getSteps: () => GuideWalkthroughStep[]
}

function dispatchGuideWalkthroughEvent(name: string) {
  if (typeof window === "undefined") return
  window.dispatchEvent(new Event(name))
}

function dispatchGuideWalkthroughCustomEvent(name: string, detail: Record<string, string>) {
  if (typeof window === "undefined") return
  window.dispatchEvent(new CustomEvent(name, { detail }))
}

function cleanupVirtualStudyReviewProjectForDoc(docSlug: GuideWalkthroughDocSlug) {
  if (docSlug !== "study-review") return
  clearVirtualStudyReviewProjectSession()
}

function shouldLeaveVirtualStudyReviewRoute(pathname: string) {
  return pathname === `/p/${VIRTUAL_STUDY_REVIEW_PROJECT_ID}` || pathname.startsWith(`/p/${VIRTUAL_STUDY_REVIEW_PROJECT_ID}/`)
}

export function startGuideWalkthrough(docSlug: GuideWalkthroughDocSlug = DEFAULT_GUIDE_WALKTHROUGH_DOC_SLUG) {
  dispatchGuideWalkthroughCustomEvent(START_GUIDE_WALKTHROUGH_EVENT, { docSlug })
  return true
}

function consumeGuideWalkthroughQueryParam() {
  if (typeof window === "undefined") return null
  const url = new URL(window.location.href)
  const requestedDocSlug = url.searchParams.get(WALKTHROUGH_QUERY_PARAM)
  if (!isGuideWalkthroughDocSlug(requestedDocSlug)) return null
  url.searchParams.delete(WALKTHROUGH_QUERY_PARAM)
  window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}${url.hash}`)
  return requestedDocSlug
}

export function destroyGuideWalkthrough() {
  dispatchGuideWalkthroughEvent(DESTROY_GUIDE_WALKTHROUGH_EVENT)
}

function isWorkbenchGuideStep(step: GuideWalkthroughStep | undefined) {
  return Boolean(step?.routeHint?.includes("/workbench"))
}

function getProjectIdFromRouteHint(routeHint: string | undefined) {
  return routeHint?.match(/^\/p\/([^/]+)/)?.[1] ?? null
}

export function shouldEndGuideWalkthroughBeforeWorkbench(step: GuideWalkthroughStep | undefined, now = Date.now()) {
  if (!isWorkbenchGuideStep(step)) return false
  const stepProjectId = getProjectIdFromRouteHint(step?.routeHint)
  if (stepProjectId && isVirtualStudyReviewProjectId(stepProjectId)) return false
  const state = usePomodoroStore.getState()
  const snapshot = getPomodoroSnapshot({ enabled: state.enabled, weeklySchedule: state.weeklySchedule, quickPomodoro: state.quickPomodoro }, now)
  return snapshot.shouldRestrictWorkbench && !snapshot.canUseWorkbench
}

export function getPomodoroGuideStepIdsForSnapshot(snapshot: PomodoroSnapshot, hasSavedSchedule: boolean) {
  const stepIds: GuideWalkthroughStep["id"][] = ["pomodoro-open-settings"]

  if (snapshot.status === "running" && snapshot.phase === "focus") {
    stepIds.push("pomodoro-enter-web")
    return stepIds
  }

  if (!snapshot.enabled) {
    stepIds.push("pomodoro-enable-clock")
  }

  if (!hasSavedSchedule && !snapshot.hasEnabledSchedule) {
    stepIds.push("pomodoro-create-plan", "pomodoro-bind-project")
  }

  stepIds.push("pomodoro-enter-web")
  return stepIds
}

export function resolveGuideWalkthroughSessionSteps(docSlug: GuideWalkthroughDocSlug) {
  const steps = getGuideWalkthroughSteps(docSlug)
  if (docSlug !== "use-pomodoro") return steps

  const state = usePomodoroStore.getState()
  const snapshot = getPomodoroSnapshot({ enabled: state.enabled, weeklySchedule: state.weeklySchedule, quickPomodoro: state.quickPomodoro })
  const hasSavedSchedule = hasEnabledPomodoroSchedule(state.weeklySchedule)
  const stepIds = new Set(getPomodoroGuideStepIdsForSnapshot(snapshot, hasSavedSchedule))
  return steps.filter((step) => stepIds.has(step.id))
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

function getProjectIdFromPathname(pathname: string) {
  return pathname.match(/^\/p\/([^/]+)/)?.[1] ?? null
}

function getSubjectIdFromPathname(pathname: string) {
  return pathname.match(/^\/subjects\/([^/]+)/)?.[1] ?? null
}

function getPomodoroPlanIdFromPathname(pathname: string) {
  return pathname.match(/^\/pomodoro\/plans\/([^/]+)/)?.[1] ?? null
}

function resolveGuideProjectId(pathname: string) {
  const state = useAppStore.getState()
  return state.selectedWorkbenchProjectId ?? getProjectIdFromPathname(pathname) ?? state.recentWorkbenchProjectIds[0] ?? null
}

function resolveGuideSubjectId(pathname: string) {
  const state = useAppStore.getState()
  return state.selectedSubjectId ?? getSubjectIdFromPathname(pathname) ?? null
}

function resolveGuidePomodoroPlanId(pathname: string) {
  const activePlanId = getPomodoroPlanIdFromPathname(pathname)
  if (activePlanId) return activePlanId
  const weeklySchedule = usePomodoroStore.getState().weeklySchedule
  for (const daySchedule of Object.values(weeklySchedule)) {
    const firstPlan = getActivePomodoroDayPlans(daySchedule)[0] ?? daySchedule.plans[0]
    if (firstPlan?.id) return firstPlan.id
  }
  return null
}

export function resolveGuideRouteHint(step: GuideWalkthroughStep | undefined, pathname: string) {
  if (!step?.routeHint) return null
  let resolvedRouteHint = step.routeHint

  if (resolvedRouteHint.includes(":subjectId")) {
    const subjectId = resolveGuideSubjectId(pathname)
    if (!subjectId) return null
    resolvedRouteHint = resolvedRouteHint.replace(":subjectId", encodeURIComponent(subjectId))
  }

  if (resolvedRouteHint.includes(":projectId")) {
    const projectId = resolveGuideProjectId(pathname)
    if (!projectId) return null
    resolvedRouteHint = resolvedRouteHint.replace(":projectId", encodeURIComponent(projectId))
  }

  if (resolvedRouteHint.includes(":planId")) {
    const planId = resolveGuidePomodoroPlanId(pathname)
    if (!planId) return null
    resolvedRouteHint = resolvedRouteHint.replace(":planId", encodeURIComponent(planId))
  }

  return resolvedRouteHint.includes(":") ? null : resolvedRouteHint
}

export function handleRouteHint(step: GuideWalkthroughStep | undefined, navigate: GuideNavigate, pathname: string) {
  const routeHint = resolveGuideRouteHint(step, pathname)
  if (!routeHint) return false
  if (pathname === routeHint || pathname.startsWith(`${routeHint}/`)) return false
  navigate(routeHint)
  return true
}

function getCurrentPathname(fallback: string) {
  return typeof window === "undefined" ? fallback : window.location.pathname
}

function getActiveGuideWalkthroughStep(driverInstance: Driver, fallbackIndex: number, steps = GUIDE_WALKTHROUGH_STEPS) {
  const activeIndex = driverInstance.getActiveIndex() ?? fallbackIndex
  const step = steps[activeIndex]
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
  const nextStep = options.getSteps()[nextIndex]
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
  const active = getActiveGuideWalkthroughStep(driverInstance, fallbackIndex, options.getSteps())
  if (!active || active.step.id !== stepId) return
  advanceGuideWalkthroughFromIndex(driverInstance, active.activeIndex, options)
}

function createPopover(step: GuideWalkthroughStep, stepIndex: number, options: BuildDriverStepsOptions, hasTarget: boolean): DriveStep["popover"] {
  const copy = resolveGuideWalkthroughCopy(step.sourceRef, options.getDocSlug())
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
  return options.getSteps().map((step, index) => buildDriverStep(step, index, options))
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
  const activeDocSlugRef = useRef<GuideWalkthroughDocSlug>(DEFAULT_GUIDE_WALKTHROUGH_DOC_SLUG)
  const activeSessionStepsRef = useRef<GuideWalkthroughStep[]>(getGuideWalkthroughSteps(DEFAULT_GUIDE_WALKTHROUGH_DOC_SLUG))

  useEffect(() => {
    latestPathnameRef.current = pathname
    if (!driverRef.current?.isActive()) return
    replaceGuideWalkthroughSteps(driverRef.current, {
      getPathname: () => getCurrentPathname(latestPathnameRef.current),
      navigate,
      getDocSlug: () => activeDocSlugRef.current,
      getSteps: () => activeSessionStepsRef.current,
    })
    driverRef.current.refresh()
  }, [navigate, pathname])

  useEffect(() => {
    const options: BuildDriverStepsOptions = {
      getPathname: () => getCurrentPathname(latestPathnameRef.current),
      navigate,
      getDocSlug: () => activeDocSlugRef.current,
      getSteps: () => activeSessionStepsRef.current,
    }

    function runWalkthroughForDoc(requestedDocSlug: GuideWalkthroughDocSlug) {
      cleanupVirtualStudyReviewProjectForDoc(activeDocSlugRef.current)
      cleanupGuideWalkthrough(driverRef, statusRef)
      statusRef.current = "running"

      activeDocSlugRef.current = requestedDocSlug
      activeSessionStepsRef.current = resolveGuideWalkthroughSessionSteps(requestedDocSlug)
      if (requestedDocSlug === "study-review") {
        startVirtualStudyReviewProjectSession()
      }

      const firstStep = options.getSteps()[0]
      if (!firstStep) return
      if (shouldEndGuideWalkthroughBeforeWorkbench(firstStep)) {
        notifyGuideWalkthroughEndedBeforeWorkbench()
        cleanupGuideWalkthrough(driverRef, statusRef)
        return
      }
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
                cleanupVirtualStudyReviewProjectForDoc(activeDocSlugRef.current)
                if (isVirtualStudyReviewProjectId(getProjectIdFromPathname(getCurrentPathname(latestPathnameRef.current)))) {
                  navigate("/projects", { replace: true })
                }
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

    function runWalkthrough(event: Event) {
      const requestedDocSlug = event instanceof CustomEvent && isGuideWalkthroughDocSlug(event.detail?.docSlug) ? event.detail.docSlug : DEFAULT_GUIDE_WALKTHROUGH_DOC_SLUG
      runWalkthroughForDoc(requestedDocSlug)
    }

    function destroyActiveWalkthrough() {
      cleanupVirtualStudyReviewProjectForDoc(activeDocSlugRef.current)
      if (shouldLeaveVirtualStudyReviewRoute(getCurrentPathname(latestPathnameRef.current))) {
        navigate("/projects", { replace: true })
      }
      cleanupGuideWalkthrough(driverRef, statusRef)
    }

    function refreshActiveWalkthrough() {
      if (!driverRef.current?.isActive()) return
      activeSessionStepsRef.current = resolveGuideWalkthroughSessionSteps(activeDocSlugRef.current)
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

    const requestedDocSlug = consumeGuideWalkthroughQueryParam()
    if (requestedDocSlug) {
      window.setTimeout(() => runWalkthroughForDoc(requestedDocSlug), 0)
    }

    return () => {
      window.removeEventListener(START_GUIDE_WALKTHROUGH_EVENT, runWalkthrough)
      window.removeEventListener(DESTROY_GUIDE_WALKTHROUGH_EVENT, destroyActiveWalkthrough)
      window.removeEventListener(REFRESH_GUIDE_WALKTHROUGH_EVENT, refreshActiveWalkthrough)
      window.removeEventListener(GUIDE_WALKTHROUGH_STEP_COMPLETED_EVENT, completeActiveWalkthroughStep)
      cleanupVirtualStudyReviewProjectForDoc(activeDocSlugRef.current)
      cleanupGuideWalkthrough(driverRef, statusRef)
    }
  }, [navigate])
}

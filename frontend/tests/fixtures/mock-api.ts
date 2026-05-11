import type { Page, Route } from "@playwright/test"

import {
  instance,
  learningObjectNode,
  material,
  membershipSummary,
  nowIso,
  project,
  recallPoint,
  reviewTask,
  subject,
  testUser,
} from "./test-data"

function ok(data: unknown) {
  return { ok: true, data }
}

function stream(content: string) {
  return `event: delta\ndata: ${JSON.stringify({ content })}\n\n`
}

async function fulfill(route: Route, data: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json; charset=utf-8",
    body: JSON.stringify(ok(data)),
  })
}

async function fulfillNull(route: Route) {
  await fulfill(route, null)
}

function buildOrder(status = "pending") {
  return {
    orderId: "order_e2e",
    userId: testUser.userId,
    planId: "monthly",
    planName: "月会员",
    orderType: "renewal",
    pricingVersion: "e2e",
    periodDays: 30,
    listAmountCent: 2000,
    firstOrderDiscountCent: 0,
    couponDiscountCent: 0,
    payableAmountCent: 2000,
    couponId: null,
    provider: "manual_test",
    providerTradeNo: null,
    status,
    clientIp: "127.0.0.1",
    clientVersion: "e2e",
    createdAt: nowIso,
    paidAt: status === "paid" ? nowIso : null,
    closedAt: null,
    refundedAt: null,
    expiredAt: null,
    entitlementId: "ent_e2e",
    remark: "",
  }
}

type MockMembershipOrder = ReturnType<typeof buildOrder>

type MockAuthState = "signed-in" | "signed-out"
type MockContentState = "ready" | "empty"
type MockSystemCapabilities = {
  appMode: "hosted"
  asrEnabled: boolean
  serverMediaStreamEnabled: boolean
  browserLocalMediaEnabled: boolean
  baiduNetdiskEnabled: boolean
  authEnabled: boolean
  allowSignup: boolean
  signupInviteRequired: boolean
  passwordResetEnabled: boolean
  emailVerificationEnabled: boolean
  signupHumanCheckEnabled: boolean
  signupHumanCheckProvider: "altcha" | null
  signupHumanCheckChallengeUrl: string | null
  llmConfigured: boolean
  storyGenerationConfigured: boolean
  llmSource: string
}
type MockPomodoroWeekday = "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun"
type MockPomodoroPlan = {
  id: string
  enabled: boolean
  startTime: string
  focusMinutes: number
  breakMinutes: number
  pomodoroCount: number
  projectRefs: Array<{ subjectId: string; projectId: string } | null>
  breakPrompt: string
  focusPrompts: string[]
}
type MockGlobalSettings = {
  theme: string
  pomodoro: {
    enabled: boolean
    transitionSoundEnabled: boolean
    defaultFocusPrompt: string
    defaultBreakPrompt: string
    microBreaks: {
      enabled: boolean
      minIntervalSeconds: number
      maxIntervalSeconds: number
      durationSeconds: number
    }
    weeklySchedule: Record<MockPomodoroWeekday, { plans: MockPomodoroPlan[] }>
  }
  defaultProjectReviewTemplate: Array<{ kind: "CONVERGENCE" | "REVIEW_TASK"; count?: number }>
  learningPlans: { plans: unknown[]; progressSnapshots: unknown[] }
  updatedAt: string | null
}

function createEmptyPomodoroSchedule(): MockGlobalSettings["pomodoro"]["weeklySchedule"] {
  return {
    mon: { plans: [] },
    tue: { plans: [] },
    wed: { plans: [] },
    thu: { plans: [] },
    fri: { plans: [] },
    sat: { plans: [] },
    sun: { plans: [] },
  }
}

export function createMockGlobalSettings(overrides: Partial<MockGlobalSettings> = {}): MockGlobalSettings {
  return {
    theme: "warm-paper",
    pomodoro: {
      enabled: false,
      transitionSoundEnabled: false,
      defaultFocusPrompt: "",
      defaultBreakPrompt: "",
      microBreaks: {
        enabled: false,
        minIntervalSeconds: 180,
        maxIntervalSeconds: 300,
        durationSeconds: 10,
      },
      weeklySchedule: createEmptyPomodoroSchedule(),
      ...overrides.pomodoro,
    },
    defaultProjectReviewTemplate: [{ kind: "CONVERGENCE" }],
    learningPlans: { plans: [], progressSnapshots: [] },
    updatedAt: nowIso,
    ...overrides,
  }
}

export async function installMockApi(
  page: Page,
  options: {
    authState?: MockAuthState
    contentState?: MockContentState
    globalSettings?: MockGlobalSettings
    systemCapabilities?: Partial<MockSystemCapabilities>
  } = {},
) {
  const authState = options.authState ?? "signed-in"
  const contentState = options.contentState ?? "ready"
  let globalSettings = options.globalSettings ?? createMockGlobalSettings()
  let membershipOrders: MockMembershipOrder[] = []

  await page.route("**/*", async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (!url.pathname.startsWith("/api/")) {
      await route.continue()
      return
    }
    const path = url.pathname.replace(/^\/api/, "") || "/"
    const method = request.method()
    const scopedProjectPath = `/subjects/${subject.subjectId}/projects/${project.projectId}`

    if (path === "/system/capabilities") {
      const systemCapabilities: MockSystemCapabilities = {
        appMode: "hosted",
        asrEnabled: false,
        serverMediaStreamEnabled: false,
        browserLocalMediaEnabled: true,
        baiduNetdiskEnabled: false,
        authEnabled: true,
        allowSignup: true,
        signupInviteRequired: false,
        passwordResetEnabled: true,
        emailVerificationEnabled: false,
        signupHumanCheckEnabled: false,
        signupHumanCheckProvider: null,
        signupHumanCheckChallengeUrl: null,
        llmConfigured: true,
        storyGenerationConfigured: true,
        llmSource: "env",
        ...options.systemCapabilities,
      }
      await fulfill(route, systemCapabilities)
      return
    }

    if (path === "/system/data-safety") {
      await fulfill(route, {
        state: "ok",
        checkedAt: nowIso,
        environment: "e2e",
        releaseBlocked: false,
        protectedClasses: [],
        latestVerifiedBackup: null,
        findings: [],
      })
      return
    }

    if (path === "/auth/me") {
      await fulfill(route, authState === "signed-in" ? testUser : null)
      return
    }

    if (path === "/auth/login" || path === "/auth/register") {
      await fulfill(route, path.endsWith("register") ? { ...testUser, emailVerificationRequired: false, verificationEmailSent: false, verificationWaitToken: null } : testUser)
      return
    }

    if (path === "/profile/me") {
      await fulfill(route, testUser)
      return
    }

    if (path === "/profile/me/global-settings") {
      if (method === "PUT") {
        const payload = JSON.parse(request.postData() || "{}") as Partial<MockGlobalSettings>
        globalSettings = {
          ...globalSettings,
          ...payload,
          pomodoro: {
            ...globalSettings.pomodoro,
            ...payload.pomodoro,
          },
          updatedAt: new Date().toISOString(),
        }
      }
      await fulfill(route, globalSettings)
      return
    }

    if (path === "/subjects") {
      await fulfill(route, method === "POST" ? { subjectId: subject.subjectId } : [subject])
      return
    }

    if (path === `/subjects/${subject.subjectId}/materials`) {
      await fulfill(route, [material])
      return
    }

    if (path === `${scopedProjectPath}/subject-context`) {
      await fulfill(route, {
        subject,
        currentMaterial: material,
        materials: [material],
        currentProjectId: project.projectId,
      })
      return
    }

    if (path === `${scopedProjectPath}/material-source-binding`) {
      await fulfill(route, { projectId: project.projectId, sourceKind: "MANUAL", sourceRootLabel: null, updatedAt: nowIso })
      return
    }

    if (path === `${scopedProjectPath}/project-config`) {
      await fulfill(route, {
        projectId: project.projectId,
        projectType: "COURSE",
        rollUpStrategy: "THRESHOLD_AUTO",
        layerConfigs: {},
        reviewRecommendationConfig: {
          minRecallPointsToEnable: 1,
          maxHistoryLen: 20,
          recommendedBatchSize: 10,
          forgettingCurveDecayPerDay: 0.18,
        },
      })
      return
    }

    if (path === `${scopedProjectPath}/instances`) {
      await fulfill(route, contentState === "empty" ? [] : [instance])
      return
    }

    if (path === `${scopedProjectPath}/missing-instances`) {
      await fulfill(route, { instanceIds: [] })
      return
    }

    if (path === `${scopedProjectPath}/instances/${instance.instanceId}/recall-points`) {
      await fulfill(route, { recallPointIds: [recallPoint.recallPointId] })
      return
    }

    if (path === `${scopedProjectPath}/video-watch-progress`) {
      await fulfill(route, {})
      return
    }

    if (path === `${scopedProjectPath}/queue`) {
      await fulfill(route, { headId: null, ids: [] })
      return
    }

    if (path === `${scopedProjectPath}/layers`) {
      await fulfill(route, [])
      return
    }

    if (path === `${scopedProjectPath}/learning-task-nodes`) {
      await fulfill(route, [])
      return
    }

    if (path === `${scopedProjectPath}/learning-object-roots`) {
      await fulfill(route, { rootLearningObjectNodeIds: contentState === "empty" ? [] : [learningObjectNode.nodeId] })
      return
    }

    if (path === `${scopedProjectPath}/learning-object-nodes`) {
      await fulfill(route, contentState === "empty" ? [] : [learningObjectNode])
      return
    }

    if (path === `${scopedProjectPath}/learning-objects/${learningObjectNode.nodeId}/recall-points`) {
      await fulfill(route, [recallPoint])
      return
    }

    if (path === `${scopedProjectPath}/audit-log-events`) {
      await fulfill(route, [])
      return
    }

    if (path === `${scopedProjectPath}/review-recommendations`) {
      await fulfill(route, {
        items: [{
          recallPoint,
          reviewRecommendationIndex: 1,
          estimatedMemoryStrength: 0.5,
          weightedSuccessRatio: 0.5,
          lastReviewedAt: null,
          lastReviewResult: null,
          reviewCount: 0,
        }],
        totalCount: 1,
        offset: 0,
        limit: 500,
        nextOffset: null,
      })
      return
    }

    if (path === `${scopedProjectPath}/review-tasks/${reviewTask.reviewTaskId}`) {
      await fulfill(route, reviewTask)
      return
    }

    if (path === `${scopedProjectPath}/ranges/range_e2e`) {
      await fulfill(route, { projectId: project.projectId, rangeId: "range_e2e", recallPointIds: [recallPoint.recallPointId] })
      return
    }

    if (path === `${scopedProjectPath}/recall-points/${recallPoint.recallPointId}`) {
      await fulfill(route, recallPoint)
      return
    }

    if (path === `${scopedProjectPath}/llm/ask/stream`) {
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream; charset=utf-8",
        body: stream("这是自动化测试的确定性 AI 回复。"),
      })
      return
    }

    if (path === "/membership/me") {
      await fulfill(route, membershipSummary)
      return
    }

    if (path === "/membership/orders") {
      if (method === "POST") {
        const order = membershipOrders.find((item) => item.status === "pending") ?? buildOrder()
        membershipOrders = [order]
        await fulfill(route, {
          order,
          paymentPayload: {
            mode: "manual",
            provider: "manual_test",
            providerLabel: "手动测试",
            instruction: "自动化测试订单",
            providerTradeNoHint: "manual_e2e",
            expiresAt: null,
            codeUrl: null,
            qrImageDataUrl: null,
            openUrl: null,
            pollIntervalSeconds: null,
            statusCheckSupported: true,
          },
          reusedExistingOrder: false,
        })
        return
      }
      await fulfill(route, membershipOrders)
      return
    }

    if (path === "/membership/orders/preview") {
      await fulfill(route, {
        userId: testUser.userId,
        planId: "monthly",
        planName: "月会员",
        orderType: "renewal",
        periodDays: 30,
        listAmountCent: 2000,
        firstOrderDiscountCent: 0,
        couponDiscountCent: 0,
        payableAmountCent: 2000,
        couponId: null,
      })
      return
    }

    if (path === "/invites/me") {
      await fulfill(route, {
        userId: testUser.userId,
        inviteCode: "LP-E2E",
        boundInviterUserId: null,
        boundInviteCode: null,
        bindingStatus: null,
        boundAt: null,
        totalInvitedUsers: 1,
        rewardedInviteCount: 0,
        availableCouponCount: 0,
        pendingCommissionCent: 0,
        withdrawableCommissionCent: 0,
        recentInvites: [],
      })
      return
    }

    if (path === "/coupons/me") {
      await fulfill(route, [])
      return
    }

    if (path === "/commissions/me") {
      await fulfill(route, {
        account: {
          userId: testUser.userId,
          pendingCent: 0,
          withdrawableCent: 0,
          reservedCent: 0,
          paidOutCent: 0,
          canceledCent: 0,
          updatedAt: nowIso,
        },
        payoutReadiness: { provider: "wechat", status: "unbound", identityId: null, maskedLabel: null, verifiedAt: null },
        recentCommissions: [],
      })
      return
    }

    if (path === "/commissions/withdrawals") {
      await fulfill(route, [])
      return
    }

    if (path === "/admin/overview") {
      await fulfill(route, {
        users: 3,
        activeUsers: 2,
        studyUsers: 2,
        studyUsers7d: 1,
        effectiveStudyMs: 3_600_000,
        watchMs: 1_200_000,
        composeMs: 600_000,
        reviewMs: 900_000,
        qaMs: 300_000,
      })
      return
    }

    if (path === "/admin/audit-logs") {
      await fulfill(route, [])
      return
    }

    if (path === "/admin/membership/overview") {
      await fulfill(route, {
        paidOrders: 2,
        activeMemberships: 1,
        totalPaidAmountCent: 4000,
        firstPurchasePaidOrders: 1,
        renewalPaidOrders: 1,
        pendingOrders: 0,
        inviteBindings: 1,
        rewardedInvites: 0,
        coupons: 0,
        availableCoupons: 0,
        usedCoupons: 0,
        pendingCommissionCent: 0,
        withdrawableCommissionCent: 0,
        reservedWithdrawalCent: 0,
        paidOutCent: 0,
        commissionRecords: 0,
        withdrawals: 0,
      })
      return
    }

    if (method !== "GET") {
      await fulfillNull(route)
      return
    }

    await fulfill(route, [])
  })
}

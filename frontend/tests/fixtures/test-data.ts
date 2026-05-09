export const nowIso = "2026-05-09T00:00:00Z"

export const testUser = {
  userId: "user_e2e",
  email: "learner@example.com",
  createdAt: nowIso,
  publicUid: "LP-E2E",
  nickname: "自动化学习者",
  bio: "",
  avatarUrl: null,
  status: "active",
  updatedAt: nowIso,
  roles: ["super_admin"],
}

export const subject = {
  subjectId: "subj_e2e",
  title: "自动化测试学科",
  state: "ACTIVE",
  createdAt: nowIso,
  deletedAt: null,
}

export const project = {
  projectId: "proj_e2e",
  title: "自动化测试项目",
  state: "ACTIVE",
  createdAt: nowIso,
  deletedAt: null,
}

export const material = {
  subjectId: subject.subjectId,
  materialId: "mat_e2e",
  materialType: "COURSE",
  title: project.title,
  createdAt: nowIso,
  projectId: project.projectId,
}

export const instance = {
  instanceId: "inst_e2e",
  materialId: "lesson-1.mp4",
  materialDisplayName: "第一讲 自动化导论",
  presence: "PRESENT",
  lastSeenAt: nowIso,
  mediaSourceKind: "MANUAL",
  playbackKind: "FILE",
  durationMs: 600_000,
}

export const learningObjectNode = {
  kind: "leaf",
  projectId: project.projectId,
  nodeId: "node_e2e",
  relativePath: "第一讲 自动化导论.mp4",
  source: "browser",
  parentId: null,
  instanceId: instance.instanceId,
  title: "第一讲 自动化导论",
}

export const recallPoint = {
  projectId: project.projectId,
  recallPointId: "rp_e2e",
  createdAt: nowIso,
  state: "ACTIVE",
  deletedAt: null,
  question: [{ kind: "TEXT", text: "什么是自动化测试？" }],
  answer: [{ kind: "TEXT", text: "用程序验证用户关键流程。" }],
  anchor: { instanceId: instance.instanceId, position: "t=0" },
  references: [],
  insights: [],
}

export const reviewTask = {
  projectId: project.projectId,
  reviewTaskId: "review_e2e",
  inputRangeId: "range_e2e",
  createdAt: nowIso,
  state: "PENDING",
  executedAt: null,
  resultRangeId: null,
}

export const membershipSummary = {
  userId: testUser.userId,
  currentStatus: "active",
  currentStartsAt: nowIso,
  currentEndsAt: "2099-12-31T23:59:59Z",
  isActive: true,
  isFirstOrderEligible: false,
  baseMonthlyPriceCent: 2000,
  firstOrderPriceCent: 100,
  renewalPriceCent: 2000,
  currentPriceCent: 2000,
  supportedPaymentProviders: ["manual_test"],
}

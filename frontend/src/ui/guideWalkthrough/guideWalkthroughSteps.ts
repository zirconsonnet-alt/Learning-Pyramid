export type GuideWalkthroughExtractMode = "heading" | "item" | "paragraph" | "summary-from-items"
export type GuideWalkthroughFallbackMode = "centered-popover" | "route-hint" | "skip-with-explanation"
export type GuideWalkthroughPopoverSide = "top" | "right" | "bottom" | "left"
export type GuideWalkthroughSessionStatus = "idle" | "running" | "closed"
export type GuideWalkthroughAdvanceMode = "manual" | "target-click" | "completion-event"
export type GuideWalkthroughDocSlug = "create-subject-project" | "study-review" | "use-ai-chat" | "use-pomodoro"

export type GuideWalkthroughSourceRef = {
  heading: string
  itemIndex?: number
  itemIndexes?: number[]
  extractMode: GuideWalkthroughExtractMode
}

export type GuideWalkthroughStep = {
  id: string
  popoverTitle?: string
  popoverDescription?: string
  sourceRef: GuideWalkthroughSourceRef
  routeHint?: string
  targetAnchor?: string
  fallbackMode: GuideWalkthroughFallbackMode
  advanceOn?: GuideWalkthroughAdvanceMode
  popoverSide?: GuideWalkthroughPopoverSide
}

export const DEFAULT_GUIDE_WALKTHROUGH_DOC_SLUG: GuideWalkthroughDocSlug = "create-subject-project"

export const GUIDE_WALKTHROUGH_DOC_SLUGS: GuideWalkthroughDocSlug[] = ["create-subject-project", "study-review", "use-ai-chat", "use-pomodoro"]

export const CREATE_SUBJECT_PROJECT_GUIDE_STEPS: GuideWalkthroughStep[] = [
  {
    id: "create-subject",
    sourceRef: {
      heading: "第 1 步：创建学科和项目",
      itemIndex: 2,
      extractMode: "item",
    },
    routeHint: "/subjects",
    targetAnchor: "new-subject-button",
    fallbackMode: "centered-popover",
    advanceOn: "target-click",
    popoverSide: "bottom",
  },
  {
    id: "create-subject-submit",
    popoverTitle: "第 2 步：填写标题并创建学科",
    sourceRef: {
      heading: "第 1 步：创建学科和项目",
      itemIndex: 4,
      extractMode: "item",
    },
    routeHint: "/subjects",
    targetAnchor: "create-subject-submit",
    fallbackMode: "centered-popover",
    advanceOn: "completion-event",
    popoverSide: "top",
  },
  {
    id: "choose-project",
    popoverTitle: "第 3 步：打开项目设置",
    sourceRef: {
      heading: "第 1 步：创建学科和项目",
      itemIndex: 6,
      extractMode: "item",
    },
    routeHint: "/subjects/:subjectId",
    targetAnchor: "subject-project-settings-entry",
    fallbackMode: "route-hint",
    advanceOn: "target-click",
    popoverSide: "right",
  },
  {
    id: "authorize-directory",
    sourceRef: {
      heading: "第 2 步：到“项目设置”绑定目录",
      itemIndex: 3,
      extractMode: "item",
    },
    routeHint: "/subjects/:subjectId/projects/:scopedProjectId/settings",
    targetAnchor: "authorize-directory-button",
    fallbackMode: "centered-popover",
    advanceOn: "completion-event",
    popoverSide: "left",
  },
  {
    id: "import-directory",
    sourceRef: {
      heading: "第 3 步：同步目录内容",
      itemIndex: 2,
      extractMode: "item",
    },
    routeHint: "/subjects/:subjectId/projects/:scopedProjectId/settings",
    targetAnchor: "import-directory-button",
    fallbackMode: "centered-popover",
    advanceOn: "completion-event",
    popoverSide: "left",
  },
  {
    id: "view-imported-workbench",
    popoverTitle: "第 6 步：查看导入结果",
    popoverDescription: "左侧是刚导入的内容目录。",
    sourceRef: {
      heading: "第 3 步：同步目录内容",
      itemIndex: 4,
      extractMode: "item",
    },
    routeHint: "/subjects/:subjectId/projects/:scopedProjectId/workbench",
    targetAnchor: "learning-object-tree",
    fallbackMode: "centered-popover",
    advanceOn: "manual",
    popoverSide: "right",
  },
]

export const STUDY_REVIEW_GUIDE_STEPS: GuideWalkthroughStep[] = [
  {
    id: "select-learning-object",
    sourceRef: {
      heading: "第 5 步：在工作台录入复述点",
      itemIndex: 1,
      extractMode: "item",
    },
    routeHint: "/subjects/guide-virtual-study-review/projects/guide-virtual-study-review/workbench",
    targetAnchor: "learning-object-tree-item",
    fallbackMode: "centered-popover",
    advanceOn: "completion-event",
    popoverSide: "right",
  },
  {
    id: "add-recall-point",
    sourceRef: {
      heading: "第 5 步：在工作台录入复述点",
      itemIndex: 4,
      extractMode: "item",
    },
    routeHint: "/subjects/guide-virtual-study-review/projects/guide-virtual-study-review/workbench",
    targetAnchor: "add-recall-point-button",
    fallbackMode: "centered-popover",
    advanceOn: "completion-event",
    popoverSide: "left",
  },
  {
    id: "fill-recall-question",
    popoverTitle: "第 4 步：填写问题",
    sourceRef: {
      heading: "第 5 步：在工作台录入复述点",
      itemIndex: 6,
      extractMode: "item",
    },
    routeHint: "/subjects/guide-virtual-study-review/projects/guide-virtual-study-review/workbench",
    targetAnchor: "recall-question-editor",
    fallbackMode: "centered-popover",
    advanceOn: "completion-event",
    popoverSide: "top",
  },
  {
    id: "fill-recall-answer",
    popoverTitle: "第 5 步：填写答案",
    sourceRef: {
      heading: "第 5 步：在工作台录入复述点",
      itemIndex: 7,
      extractMode: "item",
    },
    routeHint: "/subjects/guide-virtual-study-review/projects/guide-virtual-study-review/workbench",
    targetAnchor: "recall-answer-editor",
    fallbackMode: "centered-popover",
    advanceOn: "completion-event",
    popoverSide: "top",
  },
  {
    id: "submit-learning",
    sourceRef: {
      heading: "第 5 步：在工作台录入复述点",
      itemIndex: 11,
      extractMode: "item",
    },
    routeHint: "/subjects/guide-virtual-study-review/projects/guide-virtual-study-review/workbench",
    targetAnchor: "submit-learning-button",
    fallbackMode: "centered-popover",
    advanceOn: "completion-event",
    popoverSide: "top",
  },
  {
    id: "submit-review-answer",
    sourceRef: {
      heading: "第 6 步：做复习",
      itemIndex: 3,
      extractMode: "item",
    },
    routeHint: "/subjects/guide-virtual-study-review/projects/guide-virtual-study-review/workbench",
    targetAnchor: "submit-review-answer-button",
    fallbackMode: "centered-popover",
    advanceOn: "completion-event",
    popoverSide: "left",
  },
  {
    id: "mark-review-result",
    sourceRef: {
      heading: "第 6 步：做复习",
      itemIndex: 5,
      extractMode: "item",
    },
    routeHint: "/subjects/guide-virtual-study-review/projects/guide-virtual-study-review/workbench",
    targetAnchor: "review-memory-choice-buttons",
    fallbackMode: "centered-popover",
    advanceOn: "completion-event",
    popoverSide: "left",
  },
  {
    id: "submit-review",
    sourceRef: {
      heading: "第 6 步：做复习",
      itemIndex: 6,
      extractMode: "item",
    },
    routeHint: "/subjects/guide-virtual-study-review/projects/guide-virtual-study-review/workbench",
    targetAnchor: "submit-review-button",
    fallbackMode: "centered-popover",
    advanceOn: "completion-event",
    popoverSide: "left",
  },
]

export const USE_AI_CHAT_GUIDE_STEPS: GuideWalkthroughStep[] = [
  {
    id: "ai-confirm-context",
    sourceRef: {
      heading: "使用前先确认 3 个条件",
      itemIndexes: [1, 2],
      extractMode: "summary-from-items",
    },
    routeHint: "/subjects/:subjectId/projects/:scopedProjectId/ai-chat",
    targetAnchor: "ai-context-check",
    fallbackMode: "centered-popover",
    advanceOn: "completion-event",
    popoverSide: "bottom",
  },
  {
    id: "ai-confirm-llm",
    sourceRef: {
      heading: "使用前先确认 3 个条件",
      itemIndex: 3,
      extractMode: "item",
    },
    routeHint: "/settings/global",
    targetAnchor: "ai-llm-check",
    fallbackMode: "centered-popover",
    advanceOn: "completion-event",
    popoverSide: "bottom",
  },
  {
    id: "ai-open-chat",
    sourceRef: {
      heading: "第 3 步：进入项目 AI 问答界面",
      itemIndex: 2,
      extractMode: "item",
    },
    routeHint: "/subjects/:subjectId/projects/:scopedProjectId/ai-chat",
    targetAnchor: "ai-chat-entry",
    fallbackMode: "centered-popover",
    advanceOn: "completion-event",
    popoverSide: "right",
  },
  {
    id: "ai-select-node",
    sourceRef: {
      heading: "第 3 步：进入项目 AI 问答界面",
      itemIndex: 4,
      extractMode: "item",
    },
    routeHint: "/subjects/:subjectId/projects/:scopedProjectId/ai-chat",
    targetAnchor: "ai-learning-object-node",
    fallbackMode: "centered-popover",
    advanceOn: "completion-event",
    popoverSide: "right",
  },
  {
    id: "ai-send-message",
    sourceRef: {
      heading: "第 3 步：进入项目 AI 问答界面",
      itemIndex: 5,
      extractMode: "item",
    },
    routeHint: "/subjects/:subjectId/projects/:scopedProjectId/ai-chat",
    targetAnchor: "ai-message-composer",
    fallbackMode: "centered-popover",
    advanceOn: "completion-event",
    popoverSide: "top",
  },
]

export const USE_POMODORO_GUIDE_STEPS: GuideWalkthroughStep[] = [
  {
    id: "pomodoro-open-settings",
    sourceRef: {
      heading: "第 1 步：先开启番茄钟",
      itemIndex: 2,
      extractMode: "item",
    },
    routeHint: "/pomodoro",
    targetAnchor: "pomodoro-settings-entry",
    fallbackMode: "centered-popover",
    advanceOn: "target-click",
    popoverSide: "bottom",
  },
  {
    id: "pomodoro-enable-clock",
    sourceRef: {
      heading: "第 1 步：先开启番茄钟",
      itemIndex: 3,
      extractMode: "item",
    },
    routeHint: "/pomodoro",
    targetAnchor: "pomodoro-session-status",
    fallbackMode: "centered-popover",
    advanceOn: "completion-event",
    popoverSide: "bottom",
  },
  {
    id: "pomodoro-create-plan",
    sourceRef: {
      heading: "第 2 步：设定番茄计划",
      itemIndexes: [1, 2, 3, 4],
      extractMode: "summary-from-items",
    },
    routeHint: "/pomodoro",
    targetAnchor: "pomodoro-create-plan-button",
    fallbackMode: "centered-popover",
    advanceOn: "completion-event",
    popoverSide: "left",
  },
  {
    id: "pomodoro-bind-project",
    sourceRef: {
      heading: "第 2 步：设定番茄计划",
      itemIndex: 5,
      extractMode: "item",
    },
    routeHint: "/pomodoro/plans/:planId",
    targetAnchor: "pomodoro-project-binding",
    fallbackMode: "centered-popover",
    advanceOn: "completion-event",
    popoverSide: "top",
  },
  {
    id: "pomodoro-enter-web",
    sourceRef: {
      heading: "第 3 步：番茄开始后登录网页",
      itemIndexes: [1, 2, 3, 4, 5],
      extractMode: "summary-from-items",
    },
    routeHint: "/pomodoro",
    targetAnchor: "pomodoro-web-entry-reminder",
    fallbackMode: "centered-popover",
    advanceOn: "completion-event",
    popoverSide: "top",
  },
]

export const GUIDE_WALKTHROUGH_STEPS_BY_DOC: Record<GuideWalkthroughDocSlug, GuideWalkthroughStep[]> = {
  "create-subject-project": CREATE_SUBJECT_PROJECT_GUIDE_STEPS,
  "study-review": STUDY_REVIEW_GUIDE_STEPS,
  "use-ai-chat": USE_AI_CHAT_GUIDE_STEPS,
  "use-pomodoro": USE_POMODORO_GUIDE_STEPS,
}

export const GUIDE_WALKTHROUGH_STEPS = GUIDE_WALKTHROUGH_STEPS_BY_DOC[DEFAULT_GUIDE_WALKTHROUGH_DOC_SLUG]

export function isGuideWalkthroughDocSlug(value: unknown): value is GuideWalkthroughDocSlug {
  return typeof value === "string" && GUIDE_WALKTHROUGH_DOC_SLUGS.includes(value as GuideWalkthroughDocSlug)
}

export function getGuideWalkthroughSteps(docSlug: GuideWalkthroughDocSlug = DEFAULT_GUIDE_WALKTHROUGH_DOC_SLUG) {
  return GUIDE_WALKTHROUGH_STEPS_BY_DOC[docSlug] ?? GUIDE_WALKTHROUGH_STEPS
}

export const guideWalkthroughSourceReferences = Object.entries(GUIDE_WALKTHROUGH_STEPS_BY_DOC).flatMap(([docSlug, steps]) =>
  steps.map((step) => ({
    id: step.id,
    docSlug,
    sourceRef: step.sourceRef,
    targetAnchor: step.targetAnchor,
    fallbackMode: step.fallbackMode,
  })),
)

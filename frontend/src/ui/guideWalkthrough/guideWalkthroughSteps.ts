export type GuideWalkthroughExtractMode = "heading" | "item" | "paragraph" | "summary-from-items"
export type GuideWalkthroughFallbackMode = "centered-popover" | "route-hint" | "skip-with-explanation"
export type GuideWalkthroughPopoverSide = "top" | "right" | "bottom" | "left"
export type GuideWalkthroughSessionStatus = "idle" | "running" | "closed"

export type GuideWalkthroughSourceRef = {
  heading: string
  itemIndex?: number
  itemIndexes?: number[]
  extractMode: GuideWalkthroughExtractMode
}

export type GuideWalkthroughStep = {
  id: string
  sourceRef: GuideWalkthroughSourceRef
  routeHint?: string
  targetAnchor?: string
  fallbackMode: GuideWalkthroughFallbackMode
  popoverSide?: GuideWalkthroughPopoverSide
}

export const GUIDE_WALKTHROUGH_STEPS: GuideWalkthroughStep[] = [
  {
    id: "create-subject",
    sourceRef: {
      heading: "第 1 步：创建学科和项目",
      itemIndex: 2,
      extractMode: "item",
    },
    routeHint: "/projects",
    targetAnchor: "new-subject-button",
    fallbackMode: "centered-popover",
    popoverSide: "bottom",
  },
  {
    id: "create-subject-submit",
    sourceRef: {
      heading: "第 1 步：创建学科和项目",
      itemIndex: 4,
      extractMode: "item",
    },
    routeHint: "/projects",
    targetAnchor: "create-subject-submit",
    fallbackMode: "centered-popover",
    popoverSide: "top",
  },
  {
    id: "choose-project",
    sourceRef: {
      heading: "第 1 步：创建学科和项目",
      itemIndex: 6,
      extractMode: "item",
    },
    routeHint: "/subjects/:subjectId",
    targetAnchor: "subject-project-entry",
    fallbackMode: "route-hint",
    popoverSide: "right",
  },
  {
    id: "open-project-settings",
    sourceRef: {
      heading: "第 2 步：到“项目设置”绑定目录",
      itemIndex: 1,
      extractMode: "item",
    },
    routeHint: "/p/:projectId/settings",
    targetAnchor: "project-settings-nav",
    fallbackMode: "route-hint",
    popoverSide: "bottom",
  },
  {
    id: "authorize-directory",
    sourceRef: {
      heading: "第 2 步：到“项目设置”绑定目录",
      itemIndex: 3,
      extractMode: "item",
    },
    routeHint: "/p/:projectId/settings",
    targetAnchor: "authorize-directory-button",
    fallbackMode: "centered-popover",
    popoverSide: "left",
  },
  {
    id: "import-directory",
    sourceRef: {
      heading: "第 3 步：导入内容目录",
      itemIndex: 2,
      extractMode: "item",
    },
    routeHint: "/p/:projectId/settings",
    targetAnchor: "import-directory-button",
    fallbackMode: "centered-popover",
    popoverSide: "left",
  },
  {
    id: "open-workbench",
    sourceRef: {
      heading: "第 4 步：确认视频能正常打开",
      itemIndex: 1,
      extractMode: "item",
    },
    routeHint: "/p/:projectId/workbench",
    targetAnchor: "workbench-nav",
    fallbackMode: "route-hint",
    popoverSide: "bottom",
  },
  {
    id: "select-learning-object",
    sourceRef: {
      heading: "第 5 步：在工作台录入复述点",
      itemIndex: 1,
      extractMode: "item",
    },
    routeHint: "/p/:projectId/workbench",
    targetAnchor: "learning-object-tree",
    fallbackMode: "centered-popover",
    popoverSide: "right",
  },
  {
    id: "add-recall-point",
    sourceRef: {
      heading: "第 5 步：在工作台录入复述点",
      itemIndex: 4,
      extractMode: "item",
    },
    routeHint: "/p/:projectId/workbench",
    targetAnchor: "add-recall-point-button",
    fallbackMode: "centered-popover",
    popoverSide: "left",
  },
  {
    id: "submit-learning",
    sourceRef: {
      heading: "第 5 步：在工作台录入复述点",
      itemIndex: 10,
      extractMode: "item",
    },
    routeHint: "/p/:projectId/workbench",
    targetAnchor: "submit-learning-button",
    fallbackMode: "centered-popover",
    popoverSide: "top",
  },
  {
    id: "do-review",
    sourceRef: {
      heading: "第 6 步：做复习",
      itemIndexes: [1, 2, 3, 4],
      extractMode: "summary-from-items",
    },
    routeHint: "/p/:projectId/workbench",
    targetAnchor: "review-pane",
    fallbackMode: "centered-popover",
    popoverSide: "left",
  },
]

export const guideWalkthroughSourceReferences = GUIDE_WALKTHROUGH_STEPS.map((step) => ({
  id: step.id,
  sourceRef: step.sourceRef,
  targetAnchor: step.targetAnchor,
  fallbackMode: step.fallbackMode,
}))

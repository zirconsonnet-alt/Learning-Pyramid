# Contract: Walkthrough Step Map

## Purpose

Define the contract between system usage instructions, walkthrough steps, frontend target anchors, and fallback behavior.

## Step Schema

```ts
type GuideWalkthroughStep = {
  id: string
  sourceRef: {
    heading: string
    itemIndex?: number
    extractMode: "heading" | "item" | "paragraph" | "summary-from-items"
  }
  routeHint?: string
  targetAnchor?: string
  fallbackMode: "centered-popover" | "route-hint" | "skip-with-explanation"
  popoverSide?: "top" | "right" | "bottom" | "left"
}
```

## First-Release Step Coverage

| Step ID | Manual Source | Preferred Target Anchor | Fallback |
|--------|---------------|-------------------------|----------|
| `create-subject` | `第 1 步：创建学科和项目`, item 2 | `new-subject-button` | Centered guidance if the user is not on the subject center |
| `create-subject-submit` | `第 1 步：创建学科和项目`, item 4 | `create-subject-submit` | Explain that a subject title is required before creating |
| `choose-project` | `第 1 步：创建学科和项目`, item 6 | `subject-project-entry` | Route hint to the subject dashboard or centered guidance if no subject exists |
| `open-project-settings` | `第 2 步：到“项目设置”绑定目录`, item 1 | `project-settings-nav` | Route hint to create/select a project first |
| `authorize-directory` | `第 2 步：到“项目设置”绑定目录`, item 3 | `authorize-directory-button` | Explain that unsupported browsers may not show directory authorization |
| `import-directory` | `第 3 步：导入内容目录`, item 2 | `import-directory-button` | Explain that authorization must happen before import |
| `open-workbench` | `第 4 步：确认视频能正常打开`, item 1 | `workbench-nav` | Route hint to select a project first |
| `select-learning-object` | `第 5 步：在工作台录入复述点`, item 1 | `learning-object-tree` | Explain that content must be imported before objects appear |
| `add-recall-point` | `第 5 步：在工作台录入复述点`, item 4 | `add-recall-point-button` | Explain that a learning object or compatible project mode is needed |
| `submit-learning` | `第 5 步：在工作台录入复述点`, item 10 | `submit-learning-button` | Explain that title, question, answer, and review queue gates affect submission |
| `do-review` | `第 6 步：做复习`, items 1-4 | `review-pane` | Explain that review appears after the system schedules review tasks |

## Validation Rules

- Every step ID must be unique.
- Every `sourceRef.heading` must exist in `docs/learningpyramid-user-manual.md`.
- Every `itemIndex` must resolve inside that heading's ordered list.
- Every non-empty `targetAnchor` must appear in source files as `data-guide-tour="<anchor>"`.
- Every step must declare a fallback mode.
- No step may include separately authored popover body text.

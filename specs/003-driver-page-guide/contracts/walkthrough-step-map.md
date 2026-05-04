# Contract: Walkthrough Step Map

## Purpose

Define the contract between system usage instructions, walkthrough steps, frontend target anchors, and fallback behavior.

## Step Schema

```ts
type GuideWalkthroughStep = {
  id: string
  popoverTitle?: string
  sourceRef: {
    heading: string
    itemIndex?: number
    extractMode: "heading" | "item" | "paragraph" | "summary-from-items"
  }
  routeHint?: string
  targetAnchor?: string
  fallbackMode: "centered-popover" | "route-hint" | "skip-with-explanation"
  advanceOn?: "manual" | "target-click" | "completion-event"
  popoverSide?: "top" | "right" | "bottom" | "left"
}
```

`advanceOn` defines how the learner leaves an actionable step:

- `target-click`: advance after the learner clicks the highlighted target.
- `completion-event`: advance only after the underlying business action reports success.
- `manual` or omitted: show normal walkthrough controls for fallback, review, or non-action guidance.

## First-Release Step Coverage

| Step ID | Manual Source | Preferred Target Anchor | Fallback |
|--------|---------------|-------------------------|----------|
| `create-subject` | `第 1 步：创建学科和项目`, item 2 | `new-subject-button` | Centered guidance if the user is not on the subject center |
| `create-subject-submit` | `第 1 步：创建学科和项目`, item 4 | `create-subject-submit` | Explain that a subject title is required before creating |
| `choose-project` | `第 1 步：创建学科和项目`, item 6 | `subject-project-settings-entry` | Route hint to the subject dashboard or centered guidance if no subject exists |
| `authorize-directory` | `第 2 步：到“项目设置”绑定目录`, item 3 | `authorize-directory-button` | Route to `/p/:projectId/project-settings`; explain that unsupported browsers may not show directory authorization |
| `import-directory` | `第 3 步：同步目录内容`, item 2 | `import-directory-button` | Route to `/p/:projectId/project-settings`; explain that authorization must happen before sync |
| `select-learning-object` | `第 5 步：在工作台录入复述点`, item 1 | `learning-object-tree-item` | Explain that content must be synced before objects appear |
| `add-recall-point` | `第 5 步：在工作台录入复述点`, item 4 | `add-recall-point-button` | Explain that a learning object or compatible project mode is needed |
| `fill-recall-question` | `第 5 步：在工作台录入复述点`, item 6 | `recall-question-editor` | Advance only after the learner types the question/prompt |
| `fill-recall-answer` | `第 5 步：在工作台录入复述点`, item 7 | `recall-answer-editor` | Advance only after the learner types the answer/recall content |
| `submit-learning` | `第 5 步：在工作台录入复述点`, item 11 | `submit-learning-button` | Explain that title, question, answer, and review queue gates affect submission |
| `submit-review-answer` | `第 6 步：做复习`, item 3 | `submit-review-answer-button` | Explain that a written answer or skip is needed before judging memory |
| `mark-review-result` | `第 6 步：做复习`, item 5 | `review-memory-choice-buttons` | Explain that the learner should choose the true remembered/forgotten result |
| `submit-review` | `第 6 步：做复习`, item 6 | `submit-review-button` | Explain that every review item must be judged before submission |

## Validation Rules

- Every step ID must be unique.
- Every `sourceRef.heading` must exist in one of the task guide documents.
- Every `itemIndex` must resolve inside that heading's ordered list.
- Every non-empty `targetAnchor` must appear in source files as `data-guide-tour="<anchor>"`.
- Every step must declare a fallback mode.
- Actionable steps must prefer `target-click` or `completion-event` over requiring the learner to press the walkthrough next button.
- No step may include separately authored popover body text.
- `popoverTitle` may be used for guide-specific micro-step titles, while body copy must still come from the manual source.

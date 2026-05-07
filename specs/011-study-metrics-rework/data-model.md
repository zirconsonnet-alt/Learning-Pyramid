# Data Model: Study Metrics Rework

## Web Presence Interval

Represents a measured period when a learner is objectively present in the web page for one project.

### Fields

- `projectId`: project scope being measured.
- `dateKey`: local date for the stored segment.
- `startMs`: local-day offset when the interval starts.
- `endMs`: local-day offset when the interval ends.

### Validation Rules

- `projectId` is required.
- `dateKey` is a local date key.
- `endMs` must be greater than `startMs`.
- Intervals are normalized and merged per project/date.
- Intervals may cross midnight only after being split into date-local intervals.

## Metric Category

The mutually exclusive displayed category assigned to a web-present moment.

### Values

- `video`: actual wall-clock video playback time.
- `recallEntry`: recall point recording/editing window.
- `review`: review interface operation window.
- `aiQa`: full-screen AI Q&A window.
- `distraction`: web-present time not assigned to another category.

## Category Activity Interval

Represents a measured active category candidate before final partition resolution.

### Fields

- `projectId`: project scope being measured.
- `dateKey`: local date for the stored segment.
- `category`: one of `video`, `recallEntry`, `review`, or `aiQa`.
- `startMs`: local-day offset when the interval starts.
- `endMs`: local-day offset when the interval ends.
- `source`: optional recorder origin such as workbench player, compose pane, review pane, or AI page.

### Validation Rules

- `distraction` is not recorded directly; it is derived as the web presence remainder.
- Active intervals are clipped to web presence during summary generation.
- Overlapping category intervals are resolved into one category per elapsed moment using the foreground learning state rule.

## Workbench Metric Summary

Displayed daily or scoped summary for the workbench card.

### Fields

- `projectId`
- `dateKey`
- `webPresenceMs`
- `videoMs`
- `recallEntryMs`
- `reviewMs`
- `aiQaMs`
- `distractionMs`
- `isPartitionComplete`

### Validation Rules

- `webPresenceMs = videoMs + recallEntryMs + reviewMs + aiQaMs + distractionMs`.
- All durations are non-negative integers.
- `isPartitionComplete` is false for legacy-only data that cannot prove the partition.

## Pomodoro Segment Metric Summary

Statistics for one numbered Pomodoro focus segment.

### Fields

- `planId`
- `planIndex`
- `pomodoroIndex`
- `projectId`
- `scheduledStartAtMs`
- `scheduledEndAtMs`
- `scheduledFocusMs`
- `webPresenceMs`
- `videoMs`
- `recallEntryMs`
- `reviewMs`
- `aiQaMs`
- `distractionMs`
- `absenceMs`
- `activeLearningMs`
- `attendanceRate`
- `effectiveLearningRate`
- `status`: `not-started`, `in-progress`, or `completed`

### Validation Rules

- `absenceMs = max(0, scheduledFocusMs - webPresenceMs)`.
- `activeLearningMs = videoMs + recallEntryMs + reviewMs + aiQaMs`.
- `attendanceRate = webPresenceMs / scheduledFocusMs` when scheduled focus is greater than zero.
- `effectiveLearningRate = activeLearningMs / scheduledFocusMs` when scheduled focus is greater than zero.
- Category durations plus distraction equal web presence for the segment.
- In-progress summaries must be labeled as incomplete.

## Pomodoro Plan Metric Summary

Aggregate statistics for one Pomodoro plan.

### Fields

- `planId`
- `planIndex`
- `dateKey`
- `segments`: list of Pomodoro Segment Metric Summary.
- `scheduledFocusMs`
- `webPresenceMs`
- `videoMs`
- `recallEntryMs`
- `reviewMs`
- `aiQaMs`
- `distractionMs`
- `absenceMs`
- `activeLearningMs`
- `attendanceRate`
- `effectiveLearningRate`
- `status`

### Validation Rules

- Aggregate values are sums of the plan's numbered focus segment values.
- Break segments are excluded from scheduled focus and absence.
- Status is completed only when every included focus segment has ended.

## Legacy Study Metric Record

Existing synced record that may contain `effective`, `watch`, `compose`, `review`, and `qa` durations/ranges without web presence partition proof.

### Handling Rules

- Legacy active ranges may be used for backwards-compatible profile totals where the old surfaces still require them.
- Legacy records must not be displayed as complete web-presence partitions.
- Legacy records must not create synthetic web presence or distraction values.
- New records should include enough web presence and category range detail to produce complete summaries.

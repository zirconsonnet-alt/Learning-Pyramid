# Feature Specification: Study Metrics Rework

**Feature Branch**: `011-study-metrics-rework`  
**Created**: 2026-05-07  
**Status**: Draft  
**Input**: User description: "网页驻留：客观指标，用户在网页前的时间。视频观看：客观指标，用户播放视频消耗的实际时长。复述点录入：客观指标，用户记录复述点花的时间窗口。复习用时：客观指标，复习界面操作的时间窗口。AI问答：客观指标，用户全屏内问AI所用的时间窗口。走神时间：不处于以上窗口也不在观看视频，但是属于网页驻留的时间。视频观看加复述点录入加复习用时加AI问答用时加走神时间必然等于网页驻留时间，前几者构成网页驻留时间的划分。工作状态卡片就只展示这几个指标。番茄钟是否开启不影响这些指标如何计算。只要番茄钟开启，系统必须能够知道已经过去的某个番茄计划或者番茄1,2,3内以上信息的具体数字，用来记录这个番茄的实际学习情况。番茄钟统计界面以番茄为单位，并且用番茄规定的学习时间减去网页驻留时间算得缺席时间，也就是用户本来应该在学习然而却没有学习的时间，并把这些信息做成直观的饼状图，计算其他派生属性，比如有效学习率等等指标。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read Objective Workbench Study Time (Priority: P1)

As a learner reviewing today's workbench status, I want the work status card to show only objective web-based time categories so that I can trust what each number means.

**Why this priority**: This fixes the misleading current behavior where non-web study can make web presence and focus rate appear perfect. The workbench card must first become truthful and internally consistent.

**Independent Test**: Can be fully tested by spending time on the workbench in different learning states and verifying the card shows web presence plus its exact category breakdown without any Pomodoro-only or synthetic effective-study rows.

**Acceptance Scenarios**:

1. **Given** a learner spends 10 minutes in the web page with 4 minutes watching video, 2 minutes entering recall points, 1 minute reviewing, 1 minute asking AI, and 2 minutes in none of those states, **When** they expand the work status card, **Then** the card shows 10 minutes of web presence, 4 minutes of video watching, 2 minutes of recall point entry, 1 minute of review time, 1 minute of AI Q&A, and 2 minutes of distraction time.
2. **Given** a learner has Pomodoro study time recorded but has not been present in the web page during that period, **When** they view the work status card, **Then** web presence remains based on real web presence only and is not raised to match Pomodoro or effective-study time.
3. **Given** the same moment could be associated with more than one learning signal, **When** the work status card totals are calculated, **Then** that moment contributes to exactly one visible category so the category total always equals web presence.

---

### User Story 2 - Distinguish Distraction From Active Learning States (Priority: P2)

As a learner, I want distraction time to mean web-present time that is not video watching, recall point entry, review, or AI Q&A so that the metric identifies idle or off-task time without inventing extra study categories.

**Why this priority**: Distraction time is only meaningful if it is the remainder of a complete partition of web presence, not a separate overlapping metric.

**Independent Test**: Can be tested by remaining on the page without playing video or using the learning tools, then confirming the added time increases distraction and not any active learning category.

**Acceptance Scenarios**:

1. **Given** a learner is present on the web page and none of the active learning categories apply, **When** time passes, **Then** the elapsed web-present time is counted as distraction time.
2. **Given** a learner starts watching video, entering recall points, reviewing, or asking AI, **When** that active state begins, **Then** the elapsed time stops increasing distraction and increases the active category instead.
3. **Given** a learner leaves the web page, hides it, or is no longer considered present, **When** time passes, **Then** neither distraction nor any web-presence category increases.

---

### User Story 3 - Inspect Pomodoro Learning By Plan And Pomodoro (Priority: P3)

As a learner using Pomodoro, I want each completed or elapsed Pomodoro plan and individual Pomodoro to show the same objective time categories, absence time, and derived learning rates so that I can judge whether I actually studied during scheduled learning time.

**Why this priority**: Pomodoro should not change basic metric definitions, but it needs scheduled-time slices to explain planned versus actual learning behavior.

**Independent Test**: Can be fully tested by running a Pomodoro plan, using the workbench for only part of a scheduled learning segment, and checking the Pomodoro statistics view for that plan and individual Pomodoro.

**Acceptance Scenarios**:

1. **Given** a Pomodoro learning segment was scheduled for 25 minutes and the learner had 18 minutes of web presence during that segment, **When** the Pomodoro statistics are viewed, **Then** the segment shows 7 minutes of absence time.
2. **Given** a Pomodoro plan contains multiple numbered Pomodoros, **When** the learner views statistics for the plan, **Then** each Pomodoro shows its own web presence, video watching, recall point entry, review time, AI Q&A, distraction time, absence time, and derived rates.
3. **Given** the learner views an already elapsed Pomodoro plan from earlier in the day, **When** the statistics load, **Then** the system can still report the objective category values for the plan and for each numbered Pomodoro.
4. **Given** Pomodoro is enabled or disabled, **When** workbench metrics are calculated, **Then** the definitions of web presence, video watching, recall point entry, review time, AI Q&A, and distraction time remain identical.

### Edge Cases

- If no web presence has been recorded for the current day, all work status card time categories show zero and no focus-style percentage is shown in that card.
- If active category windows overlap, the displayed categories remain mutually exclusive by assigning each elapsed moment to one current foreground learning state.
- If a video is open but not playing, elapsed web-present time does not count as video watching unless another active category applies.
- If AI Q&A is used outside the intended full-screen AI interaction surface, the elapsed time does not count as AI Q&A for this metric unless the product explicitly treats that surface as the full-screen AI Q&A context.
- If a Pomodoro learning segment has not started yet, it has no elapsed metric values and no absence time.
- If a Pomodoro learning segment is currently in progress, statistics may show elapsed values so far and must clearly avoid presenting incomplete values as final.
- If web presence in a Pomodoro segment exceeds the scheduled learning duration because of timing boundaries or clock drift, absence time is never negative.
- If historical data lacks the new category partition, the product must not fabricate precise category values for those historical periods.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define web presence as the objective time a learner is present in the web page and eligible to be counted as in-page study presence.
- **FR-002**: The system MUST define video watching as objective elapsed time consumed by actual video playback while the learner is web-present.
- **FR-003**: The system MUST define recall point entry as the objective time window during which the learner records or edits recall points while web-present.
- **FR-004**: The system MUST define review time as the objective time window during which the learner operates the review interface while web-present.
- **FR-005**: The system MUST define AI Q&A as the objective time window during which the learner uses the full-screen AI Q&A experience while web-present.
- **FR-006**: The system MUST define distraction time as web-present time that is not assigned to video watching, recall point entry, review time, or AI Q&A.
- **FR-007**: The system MUST make video watching, recall point entry, review time, AI Q&A, and distraction time a complete, mutually exclusive partition of web presence for displayed workbench metrics.
- **FR-008**: The system MUST ensure the displayed sum of video watching, recall point entry, review time, AI Q&A, and distraction time equals displayed web presence for the same scope.
- **FR-009**: The work status card MUST show only web presence, video watching, recall point entry, review time, AI Q&A, and distraction time from this metric set.
- **FR-010**: The work status card MUST NOT show effective learning time, learning stay time, objective focus rate, content contact, recall point construction, or other legacy rows that duplicate or distort the new metric definitions.
- **FR-011**: Pomodoro enabled state MUST NOT change the definitions or base calculation rules for web presence, video watching, recall point entry, review time, AI Q&A, or distraction time.
- **FR-012**: When Pomodoro is active, the system MUST be able to report the base metric values for each elapsed Pomodoro plan.
- **FR-013**: When Pomodoro is active, the system MUST be able to report the base metric values for each elapsed numbered Pomodoro within a plan.
- **FR-014**: Pomodoro statistics MUST calculate absence time for a learning segment as scheduled learning time minus web presence, clamped so it cannot be negative.
- **FR-015**: Pomodoro statistics MUST present per-Pomodoro values in a visual breakdown that includes web presence categories and absence time.
- **FR-016**: Pomodoro statistics MUST provide derived metrics, including at minimum effective learning rate, based on the objective per-Pomodoro values.
- **FR-017**: The system MUST identify whether Pomodoro statistics are final for completed segments or still in-progress for currently running segments.
- **FR-018**: The system MUST avoid presenting unavailable historical category detail as measured fact when older records do not contain enough information.
- **FR-019**: Documentation or in-product metric descriptions affected by this change MUST use the new metric names and definitions consistently.

### Key Entities *(include if feature involves data)*

- **Web Presence Interval**: A measured period when the learner is present in the web page and eligible for in-page study metrics.
- **Metric Category Interval**: A measured period assigned to exactly one displayed category: video watching, recall point entry, review time, AI Q&A, or distraction.
- **Workbench Metric Summary**: The daily or scoped summary shown in the work status card, containing web presence and the complete category partition.
- **Pomodoro Plan Metric Summary**: The objective metric summary for an elapsed Pomodoro plan, including scheduled learning time, web presence categories, absence time, and derived rates.
- **Pomodoro Segment Metric Summary**: The objective metric summary for one numbered Pomodoro learning segment inside a plan.
- **Absence Time**: Scheduled Pomodoro learning time during which the learner was not web-present.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of tested workbench metric summaries, video watching plus recall point entry plus review time plus AI Q&A plus distraction time equals web presence for the same scope.
- **SC-002**: In 100% of tested cases where only Pomodoro time exists and no web presence exists, the work status card shows zero web presence rather than matching Pomodoro or effective-study time.
- **SC-003**: Users can identify from the work status card how much of their web-present time was spent in each active learning category and distraction without interpreting legacy metric names.
- **SC-004**: For every completed Pomodoro learning segment in test data, absence time equals scheduled learning time minus web presence and is never negative.
- **SC-005**: For every completed Pomodoro plan in test data, the statistics view can show per-plan and per-numbered-Pomodoro values for web presence, all five category values, absence time, and effective learning rate.
- **SC-006**: In user-facing metric labels and help text covered by review, 100% of affected references use the new metric names and definitions.

## Assumptions

- "User in front of the web page" is treated as the product's existing objective web-presence eligibility signal, including page visibility and recent interaction rules, unless later planning defines a stricter measurable presence signal.
- "Actual video playback" means elapsed wall-clock time while playback is active, not video timeline coverage or content duration.
- Recall point entry, review time, and AI Q&A remain time-window metrics because user activity in those tools is event-driven rather than continuously measurable like video playback.
- When category windows overlap, the current foreground learning state determines the single displayed category for that time.
- Effective learning rate in Pomodoro statistics means active learning category time divided by scheduled learning time unless later planning explicitly adopts a narrower formula.
- This feature changes metric definitions, display, and Pomodoro statistics; it does not require changing the learning method itself.

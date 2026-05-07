# Research: Study Metrics Rework

## Decision: Use Web Presence As The Single Metric Total

**Decision**: The workbench metric model will treat web presence as the only total for the work status card. Video watching, recall point entry, review time, AI Q&A, and distraction are derived as a complete partition of web presence.

**Rationale**: The current model stores action windows and page presence separately, then displays a synthetic maximum. That allowed Pomodoro scheduled time to masquerade as web presence. A single total plus a partition makes every displayed value explainable and testable.

**Alternatives considered**:

- Keep effective learning as the card headline: rejected because it mixes web and non-web concepts.
- Keep learning stay as `max(presence, effective)`: rejected because it fabricates presence.
- Show both raw presence and effective learning in the card: rejected because the user explicitly asked the card to show only the new objective set.

## Decision: Resolve Overlaps At Summary Time With One Foreground Category

**Decision**: Store or compute intervals for web presence and active category windows, then resolve the displayed summary by assigning each elapsed moment inside web presence to exactly one category. When active windows overlap, the current foreground learning state wins.

**Rationale**: Existing video playback, compose, review, and QA signals may overlap. Adding their raw durations can exceed web presence. Resolving overlaps when summarizing preserves the invariant without requiring every recorder to know about every other recorder.

**Alternatives considered**:

- Prevent all overlap at recording time: rejected because signals come from separate components and routes.
- Divide overlapping time proportionally: rejected because users expect clear categories and the spec requires a partition.
- Prioritize video above all tools: rejected because a learner can pause attention from video to enter/ask/review while playback state may still emit signals; foreground state better matches user intent.

## Decision: Keep Video Watching As Wall-Clock Playback Time

**Decision**: Video watching is elapsed wall-clock time while playback is active and web presence is eligible, not video timeline coverage and not media duration.

**Rationale**: The user asked for actual time consumed by playing video. Timeline coverage answers a different question: how much content was covered. Existing watch coverage can remain separate from this feature.

**Alternatives considered**:

- Use video timeline delta: rejected because seeking and playback speed distort real time spent.
- Use coverage map watched duration: rejected because it measures content coverage, not wall-clock attention.

## Decision: Pomodoro Statistics Slice The Same Intervals

**Decision**: Pomodoro plan and numbered Pomodoro statistics will intersect scheduled focus segments with the same web presence and category intervals used by the workbench card.

**Rationale**: Pomodoro must not change metric definitions. Slicing by scheduled segment gives plan-level and per-Pomodoro values without introducing a second recording system.

**Alternatives considered**:

- Record a separate Pomodoro-specific metric stream: rejected because it risks divergent definitions.
- Continue recording completed Pomodoro duration as effective learning: rejected because it caused the misleading card behavior.

## Decision: Absence And Effective Learning Rate Are Pomodoro-Derived Only

**Decision**: Absence time is `scheduled focus duration - web presence`, clamped to zero. Effective learning rate for Pomodoro statistics is active category time divided by scheduled focus duration, where active category time is video watching plus recall point entry plus review time plus AI Q&A.

**Rationale**: Absence is meaningful only against scheduled Pomodoro learning time. Distraction is web-present but inactive, so it should not count as effective learning in a Pomodoro rate.

**Alternatives considered**:

- Active category time divided by web presence: rejected because it is a focus-within-presence rate, not effectiveness against planned time.
- Web presence divided by scheduled focus duration: useful as an attendance rate, but it does not distinguish active learning from distraction.

## Decision: Hosted Sync Needs A New Contract With Legacy Read Fallback

**Decision**: Extend study metric sync to carry `presenceRanges`, category ranges, and a schema/version marker while continuing to read old `effective/watch/compose/review/qa` records as legacy data. Old records must not be used to fabricate precise distraction or web presence partitions.

**Rationale**: Hosted users already sync daily metric ranges. The new invariant requires web presence ranges and partitionable categories. However, historical records cannot be retroactively made precise.

**Alternatives considered**:

- Local-only metric rework: rejected because existing profile/friend/admin surfaces depend on synced study metrics.
- Hard migration of old records into new ranges: rejected because legacy data lacks true web presence and overlap resolution.

## Decision: Workbench Card Removes Legacy Rows Instead Of Renaming Them

**Decision**: The card will display only: web presence, video watching, recall point entry, review time, AI Q&A, and distraction time.

**Rationale**: Renaming legacy rows such as content contact or recall point construction would preserve old overlap semantics. Removing them makes the product promise unambiguous.

**Alternatives considered**:

- Keep count rows for recall points in the same card: rejected for this feature because the user asked this card to show only these metrics; counts can remain elsewhere.
- Keep objective focus rate: rejected because the new Pomodoro statistics own derived rates and the card should stay objective.

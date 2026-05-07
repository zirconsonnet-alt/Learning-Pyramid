# Contract: Study Metrics Sync

## Purpose

Synchronize objective study metric ranges between the browser and hosted account storage without reintroducing synthetic effective-learning totals.

## Sync Entry

Each entry represents one project and one local date.

### Required Fields For New Entries

- `projectId`: project identifier.
- `dateKey`: local date key.
- `schemaVersion`: metric schema version for the entry.
- `webPresenceMs`: total web presence duration.
- `videoMs`: video playback duration.
- `recallEntryMs`: recall point entry duration.
- `reviewMs`: review duration.
- `aiQaMs`: AI Q&A duration.
- `distractionMs`: derived distraction duration.
- `presenceRanges`: normalized web presence ranges.
- `videoRanges`: normalized video playback ranges.
- `recallEntryRanges`: normalized recall point entry ranges.
- `reviewRanges`: normalized review ranges.
- `aiQaRanges`: normalized AI Q&A ranges.

### Legacy-Compatible Fields

Older clients and stored records may still contain:

- `effectiveMs`
- `watchMs`
- `composeMs`
- `qaMs`
- `effectiveRanges`
- `watchRanges`
- `composeRanges`
- `qaRanges`

The system may continue to read these fields for historical aggregate compatibility, but it must not use them to fabricate a complete web presence partition.

## Merge Rules

- Ranges for the same project/date/category are merged by union.
- Duration fields for new entries are recomputed from normalized ranges when ranges are present.
- Response entries include the normalized merged ranges and durations.
- If an entry contains both new and legacy fields, new fields are authoritative for the workbench partition.
- The response must identify whether a returned entry can support complete partition display.

## Validation

- All ranges use local-day offsets and must satisfy `endMs > startMs >= 0`.
- All durations are non-negative integers.
- For complete new entries, `videoMs + recallEntryMs + reviewMs + aiQaMs + distractionMs` must equal `webPresenceMs`.
- Invalid project ownership continues to be rejected by the existing authenticated project-ownership rule.

## Backward Readability

- Existing legacy records remain readable after the feature ships.
- Legacy-only records can contribute to old aggregate totals where still required.
- Legacy-only records must be labeled or treated as incomplete for the new workbench/Pomodoro partition.

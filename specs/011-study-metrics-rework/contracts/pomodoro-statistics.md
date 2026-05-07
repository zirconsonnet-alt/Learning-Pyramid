# Contract: Pomodoro Statistics

## Scope

Pomodoro statistics show objective study behavior for scheduled focus time. They do not define or alter workbench metric collection.

## Per-Pomodoro Segment

For each elapsed numbered Pomodoro focus segment, show:

- Pomodoro label and scheduled time window.
- Bound project.
- Web presence.
- Video watching.
- Recall point entry.
- Review time.
- AI Q&A.
- Distraction time.
- Absence time.
- Attendance rate.
- Effective learning rate.
- Status: completed or in-progress.

## Per-Plan Summary

For each Pomodoro plan, show an aggregate of its numbered focus segments:

- Total scheduled focus time.
- Total web presence.
- Category totals.
- Absence time.
- Attendance rate.
- Effective learning rate.
- Segment list.

## Visual Breakdown

The statistics view includes a pie-style or donut-style visual breakdown for scheduled focus time:

- Active learning categories: video watching, recall point entry, review time, AI Q&A.
- Distraction.
- Absence.

The visual must make absence visually distinct from web-present categories.

## Formulas

```text
activeLearningMs = videoMs + recallEntryMs + reviewMs + aiQaMs
absenceMs = max(0, scheduledFocusMs - webPresenceMs)
attendanceRate = webPresenceMs / scheduledFocusMs
effectiveLearningRate = activeLearningMs / scheduledFocusMs
```

Rates are shown only when scheduled focus time is greater than zero.

## In-Progress Segments

If a focus segment is currently running:

- Values may be shown for elapsed time so far.
- The UI must indicate that the values are in progress.
- The segment must not be counted as a completed final record.

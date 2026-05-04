# Data Model: Pomodoro Random Micro Breaks

## RandomMicroBreakSettings

Durable learner preference stored as part of Pomodoro settings.

| Field | Type | Default | Validation |
|-------|------|---------|------------|
| `enabled` | boolean | `false` | Boolean only |
| `minIntervalSeconds` | integer | `180` | 30-3600 seconds |
| `maxIntervalSeconds` | integer | `300` | 30-3600 seconds and `>= minIntervalSeconds` |
| `durationSeconds` | integer | `10` | 5-300 seconds |

Relationships:

- Belongs to the Pomodoro settings object.
- Applies to both scheduled Pomodoro focus segments and quick Pomodoro focus sessions.
- Does not belong to individual projects, videos, or plans.

## PomodoroSettings

Existing durable settings object extended with random micro break settings.

| Existing Field | Relationship To Micro Breaks |
|----------------|------------------------------|
| `enabled` | Scheduled Pomodoro must be enabled, unless a quick Pomodoro session is active |
| `weeklySchedule` | Defines focus segment end times and forbidden windows |
| `quickPomodoro` | Local active quick session can make Pomodoro focus eligible |
| `transitionSoundEnabled` | Independent setting; micro break sound uses its own enabled feature state |
| `defaultFocusPrompt` / `defaultBreakPrompt` | Independent settings; micro break does not change transition prompt text |
| `microBreaks` | New RandomMicroBreakSettings object |

## RandomMicroBreakTimer

Ephemeral fullscreen-session state owned by the video player flow.

| Field | Type | Purpose |
|-------|------|---------|
| `status` | `idle` \| `scheduled` \| `resting` | Current micro break controller state |
| `fullscreenEnteredAtMs` | integer or null | Start point for the current fullscreen timer |
| `targetAtMs` | integer or null | Randomized reminder trigger time |
| `forbiddenAfterMs` | integer or null | Focus segment end minus 3 minutes |
| `segmentKey` | string | Identifies the active Pomodoro focus segment |
| `wasPlayingBeforeBreak` | boolean | Determines whether playback should resume |
| `countdownEndsAtMs` | integer or null | End time for visible rest countdown |

State transitions:

```text
idle
  -> scheduled   when eligible Pomodoro focus fullscreen starts and a randomized target fits before the forbidden window
  -> idle        when fullscreen exits, Pomodoro becomes ineligible, no video is playable, or target would fall in forbidden window

scheduled
  -> resting     when targetAtMs arrives while still eligible
  -> idle        when canceled by fullscreen exit, Pomodoro phase change, route change, or settings disabled

resting
  -> scheduled   when countdown completes, the learner remains eligible/fullscreen, and another randomized target fits
  -> idle        when countdown completes but no next target fits, or when canceled
```

## MicroBreakSession

Single triggered rest event. This state does not need durable persistence.

| Field | Type | Purpose |
|-------|------|---------|
| `startedAtMs` | integer | Trigger time |
| `durationSeconds` | integer | Countdown length copied from settings at trigger time |
| `endsAtMs` | integer | Countdown completion time |
| `wasPlayingBeforeBreak` | boolean | Playback restoration rule |
| `cancelReason` | `fullscreen_exit` \| `pomodoro_ineligible` \| `route_change` \| `settings_disabled` \| null | Explains cancellation for tests/debugging |

Validation rules:

- Only one session may be active at a time.
- A canceled session never resumes video.
- A completed session resumes video only when `wasPlayingBeforeBreak` is true.

## Persistence & Migration

- Existing local Pomodoro store version should be incremented.
- Missing `microBreaks` in old local state or remote payload normalizes to default disabled settings.
- Backend profile/global-settings responses include default `microBreaks` values when older stored settings do not contain them.

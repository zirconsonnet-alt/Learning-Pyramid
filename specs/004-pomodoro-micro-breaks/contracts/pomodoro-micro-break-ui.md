# Contract: Pomodoro Micro Break UI Behavior

## Pomodoro Settings Page

### Controls

- Toggle: random micro breaks enabled/disabled.
- Minimum interval input: positive interval value shown in minutes or seconds with clear labeling.
- Maximum interval input: same unit as minimum interval.
- Micro break duration input: positive duration shown in seconds.
- Save action persists alongside existing Pomodoro settings.
- Reset/default action returns to disabled, 3-5 minute interval, and 10-second duration.

### Validation Feedback

- Minimum interval must be positive.
- Maximum interval must not be less than minimum interval.
- Micro break duration must be positive.
- Invalid settings prevent save and show a user-facing error.

## Workbench Fullscreen Player

### Eligibility

The micro break timer can start only when all conditions are true:

- Random micro breaks are enabled.
- A Pomodoro focus segment is running.
- The current workbench project is allowed by the active Pomodoro focus segment.
- The video player shell is fullscreen.
- A playable video element is present.
- More than 3 minutes remain in the current focus segment after accounting for the randomized interval.

### Trigger Behavior

When the randomized target time arrives and eligibility still holds:

1. Play a short reminder sound if browser audio allows it.
2. Record whether the video was playing.
3. Pause the video.
4. Show an overlay instructing the learner to close their eyes.
5. Show a countdown for the configured duration.

### Completion Behavior

- If the countdown completes and the video had been playing, resume playback.
- If the countdown completes and the video had been paused, leave it paused.
- If the learner stays fullscreen and the Pomodoro focus segment remains eligible, schedule the next randomized interval.
- If no next interval can fit before the final 3-minute forbidden window, return to idle for the rest of the segment.

### Cancellation Behavior

Cancel pending or active micro breaks when any condition occurs:

- Fullscreen exits.
- Pomodoro leaves focus phase.
- Pomodoro stops or completes.
- User navigates away from the workbench.
- Random micro breaks are disabled.
- Current video becomes unavailable.

Canceled micro breaks must not auto-resume video.

## Conflict Rules

- No micro break may trigger during the final 3 minutes of a focus segment.
- No micro break may overlap with the existing 10-second learning-end prompt.
- If a randomized trigger would land inside the forbidden window, skip it rather than moving it earlier.

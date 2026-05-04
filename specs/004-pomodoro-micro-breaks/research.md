# Research: Pomodoro Random Micro Breaks

## Decision: Store settings in existing Pomodoro global settings

Random micro break preferences will be part of the existing Pomodoro settings payload. The frontend Zustand store keeps local settings for anonymous/offline use, and authenticated users sync the same values through `/api/profile/me/global-settings`.

**Rationale**: The user explicitly placed this feature under Pomodoro settings. The project already syncs Pomodoro enabled state, schedules, transition sound, and default prompts through the global settings contract, so extending that shape keeps one source of truth.

**Alternatives considered**:

- Local-only browser storage: rejected because current Pomodoro settings already support authenticated cross-login persistence.
- Per-project or per-video settings: rejected because the feature is tied to active Pomodoro study, not a specific course item.

## Decision: Use defaults of disabled, 3-5 minute interval, and 10-second break

Default settings are disabled, minimum interval 180 seconds, maximum interval 300 seconds, and rest duration 10 seconds.

**Rationale**: Disabled preserves existing behavior. The interval and duration come directly from the requested example and primary scenario.

**Alternatives considered**:

- Enabled by default: rejected because random interruptions are intrusive unless the learner opts in.
- A single fixed interval: rejected because the requested behavior is random within a range.

## Decision: Represent persisted interval and duration values in seconds

Settings use integer seconds for minimum interval, maximum interval, and rest duration. The settings UI can display interval values as minutes and rest duration as seconds, but the persisted model uses seconds.

**Rationale**: Seconds avoid fractional minute ambiguity, support the 10-second rest duration naturally, and simplify countdown/timer validation.

**Alternatives considered**:

- Milliseconds: rejected for persisted settings because it is less readable in synced JSON and more error-prone for manual inspection.
- Minutes for all fields: rejected because micro break duration is naturally expressed in seconds.

## Decision: Validate with bounded positive ranges

Use bounded normalization: interval values are positive and clamped to an implementation-defined safe range, maximum interval is never less than minimum interval, and rest duration is positive. Planned UI/API bounds: interval 30-3600 seconds, rest duration 5-300 seconds.

**Rationale**: The spec requires positive values and max >= min. Bounded values prevent accidental zero-delay loops or excessively long/invalid settings while leaving practical flexibility.

**Alternatives considered**:

- Only check `> 0`: rejected because very small intervals could create constant interruptions and timers.
- Hard-code only 3-5 minutes: rejected because user asked for custom intervals.

## Decision: Timer is owned by the fullscreen video player flow

The active timer/controller belongs near `VideoPane` because that component owns the video element, playback state, fullscreen state, existing transition previews, and fullscreen overlays.

**Rationale**: The feature starts when the learner enters video fullscreen, pauses/resumes the current video, cancels when fullscreen exits, and displays an overlay inside the fullscreen player. Keeping the controller close to those signals avoids cross-module coupling.

**Alternatives considered**:

- Global Pomodoro store timer: rejected because the store should hold durable settings, not DOM/video element state.
- App shell timer: rejected because the shell does not own video playback or fullscreen element state.

## Decision: Eligibility is based on active Pomodoro focus snapshot plus fullscreen state

A random micro break can be scheduled only when the Pomodoro snapshot is running, phase is focus, the workbench is using the active Pomodoro project, a playable video is rendered, and the player shell is fullscreen.

**Rationale**: This matches the requirement that the feature is usable only after Pomodoro starts and the learner enters the fullscreen course player.

**Alternatives considered**:

- Any workbench fullscreen video: rejected because the feature is Pomodoro-specific.
- Any Pomodoro state, including break phase: rejected because micro breaks are for study time.

## Decision: Skip reminders that would land inside the final 3-minute forbidden window

When scheduling, compute the focus segment forbidden boundary as `segment end time - 3 minutes`. If `now + randomizedDelay` is at or after that boundary, do not schedule that reminder. Do not move the reminder earlier.

**Rationale**: The spec says reminders cannot trigger in the final 3 minutes. Moving them earlier would create a surprise interruption that does not correspond to the randomized interval.

**Alternatives considered**:

- Clamp reminder to just before the 3-minute boundary: rejected because it violates the randomized interval contract.
- Allow trigger until the final 10-second prompt: rejected because the user specified a stronger 3-minute exclusion.

## Decision: Reuse Pomodoro audio infrastructure with a distinct short reminder

Add or reuse a short Web Audio reminder through `pomodoroAudio.ts`, with visual countdown as fallback when sound playback is blocked.

**Rationale**: The project already handles audio unlock and transition sounds for Pomodoro. Reusing that path avoids another audio permission model and keeps graceful failure behavior.

**Alternatives considered**:

- TTS for the micro break prompt: rejected for v1 because the requirement only asks for a ring and visible guidance.
- External audio file dependency: rejected because no new asset is needed.

## Decision: Restore playback only when the video was playing before the break

Record pre-break playback state at trigger time. The controller pauses the video, then resumes only if it was playing before the pause. Cancellation never resumes playback.

**Rationale**: This exactly matches the user's "如果之前在播放" requirement and avoids surprising playback after manual pauses or canceled breaks.

**Alternatives considered**:

- Always resume after countdown: rejected because it would override intentional pauses.
- Never resume: rejected because it breaks the low-friction study flow requested by the user.

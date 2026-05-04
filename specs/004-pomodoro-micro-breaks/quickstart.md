# Quickstart: Validate Pomodoro Random Micro Breaks

## Prerequisites

- Use a project with at least one playable course video.
- Ensure the Pomodoro entry and Pomodoro settings page are available.
- For faster manual validation, temporarily use a short micro break interval during local development if the implementation exposes development-friendly values.

## Setup

1. Open Pomodoro settings.
2. Enable random micro breaks.
3. Set a valid interval range, for example 3-5 minutes.
4. Set micro break duration to 10 seconds.
5. Save settings.
6. Start a Pomodoro focus segment, either through a scheduled Pomodoro or quick Pomodoro.
7. Enter the active Pomodoro project workbench and open a playable video.
8. Enter video player fullscreen.

## Expected Manual Flow

1. While fullscreen remains active and the focus segment has more than 3 minutes remaining, a reminder triggers within the configured interval.
2. The reminder plays a short sound when browser audio allows it.
3. The video pauses.
4. A visible closed-eye rest countdown appears for the configured duration.
5. If the video was playing before the reminder, playback resumes when the countdown ends.
6. If the video was paused before the reminder, playback remains paused when the countdown ends.
7. Exiting fullscreen before a reminder triggers cancels and resets the timer.
8. Re-entering fullscreen starts a fresh timer.

## End-Of-Study Conflict Checks

1. Enter fullscreen when the focus segment has 3 minutes or less remaining.
2. Confirm no random micro break triggers.
3. Confirm the existing 10-second Pomodoro transition prompt still appears normally.
4. Confirm no random micro break overlay overlaps that prompt.

## Suggested Automated Checks

```powershell
python -m pytest tests/test_frontend_pomodoro_multi_plan.py tests/test_frontend_fullscreen_capture.py tests/test_profile_api.py
pnpm --dir frontend exec eslint src/views/pomodoro/PomodoroSettingsPage.tsx src/views/workbench/components/VideoPane.tsx src/ui/store/pomodoroStore.ts src/ui/pomodoroAudio.ts src/ui/api/profile.ts src/ui/globalSettingsSync.ts
pnpm --dir frontend build
```

## Task Sequence Validation Notes

- Run the targeted `pytest` command after adding source assertions and backend profile API tests so the missing `microBreaks` contract fails before implementation.
- Re-run the same `pytest` command after each completed story phase that touches settings, fullscreen playback, or cancellation behavior.
- Run targeted ESLint before the final frontend build because the feature touches React hooks in both settings and fullscreen video code.

## Notes

- Full browser automation is useful for the fullscreen overlay, but source assertions and build checks should remain the minimum regression suite.
- Existing unrelated lint failures outside the touched files should be reported separately rather than hidden.

## Validation Log

- 2026-05-04: `python -m pytest tests/test_frontend_pomodoro_multi_plan.py tests/test_frontend_fullscreen_capture.py tests/test_profile_api.py` passed with 43 tests.
- 2026-05-04: Targeted ESLint passed for Pomodoro settings, workbench video, Pomodoro store/audio, profile API sync, Pomodoro page, and global settings page.
- 2026-05-04: `pnpm --dir frontend build` passed after rerunning with elevated permissions because the first sandboxed attempt could not spawn the Vite/esbuild subprocess.
- 2026-05-04: Interactive fullscreen validation with a real playable video remains the main residual manual check after deployment: enable random micro breaks, enter an active Pomodoro focus fullscreen video, observe reminder/pause/countdown/conditional resume, and confirm no trigger in the final 3 minutes.

# Quickstart: Study Metrics Rework

## Manual Validation Flow

1. Open a project workbench with no Pomodoro active.
2. Stay present on the page without playing video or using study tools.
3. Confirm the work status card increases web presence and distraction by the same amount.
4. Play a video for a short interval.
5. Confirm web presence increases and video watching receives that interval instead of distraction.
6. Enter or edit recall points.
7. Confirm recall point entry increases and the displayed categories still sum to web presence.
8. Use review and AI Q&A surfaces.
9. Confirm review time and AI Q&A increase only while those surfaces are active and web-present.
10. Start a Pomodoro focus segment, then leave the web page for part of the scheduled focus time.
11. Confirm Pomodoro statistics show absence as scheduled focus time minus web presence.
12. Confirm the workbench card does not convert Pomodoro scheduled time into web presence.

## Source-Level Checks

```powershell
pytest tests/test_frontend_workbench_metrics.py
pytest tests/test_frontend_pomodoro_multi_plan.py
pytest tests/test_profile_api.py
```

## Build Check

```powershell
pnpm --dir frontend build
```

## Documentation Check

Review `docs/learningpyramid-user-manual.md` and verify the metric descriptions use:

- 网页驻留
- 视频观看
- 复述点录入
- 复习用时
- AI 问答
- 走神时间

Legacy workbench card labels should not be documented as current behavior.

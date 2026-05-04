# Contract: Pomodoro Micro Breaks In Global Settings

## Scope

This contract extends the existing authenticated user global settings payload. It does not introduce a new endpoint.

## GET `/api/profile/me/global-settings`

### Response Shape

```json
{
  "theme": "string",
  "pomodoro": {
    "enabled": true,
    "transitionSoundEnabled": false,
    "defaultFocusPrompt": "string",
    "defaultBreakPrompt": "string",
    "microBreaks": {
      "enabled": false,
      "minIntervalSeconds": 180,
      "maxIntervalSeconds": 300,
      "durationSeconds": 10
    },
    "weeklySchedule": {
      "mon": { "plans": [] },
      "tue": { "plans": [] },
      "wed": { "plans": [] },
      "thu": { "plans": [] },
      "fri": { "plans": [] },
      "sat": { "plans": [] },
      "sun": { "plans": [] }
    }
  },
  "defaultProjectReviewTemplate": [{ "kind": "CONVERGENCE", "count": 1 }],
  "learningPlans": { "plans": [], "progressSnapshots": [] },
  "updatedAt": "2026-05-04T00:00:00Z"
}
```

### Compatibility

- If stored settings do not contain `pomodoro.microBreaks`, the response must include default disabled settings.
- Existing clients that do not send `microBreaks` should continue to receive default values after normalization.

## PUT `/api/profile/me/global-settings`

### Request Shape

```json
{
  "theme": "string",
  "pomodoro": {
    "enabled": true,
    "transitionSoundEnabled": false,
    "defaultFocusPrompt": "string",
    "defaultBreakPrompt": "string",
    "microBreaks": {
      "enabled": true,
      "minIntervalSeconds": 180,
      "maxIntervalSeconds": 300,
      "durationSeconds": 10
    },
    "weeklySchedule": {
      "mon": { "plans": [] },
      "tue": { "plans": [] },
      "wed": { "plans": [] },
      "thu": { "plans": [] },
      "fri": { "plans": [] },
      "sat": { "plans": [] },
      "sun": { "plans": [] }
    }
  },
  "defaultProjectReviewTemplate": [{ "kind": "CONVERGENCE", "count": 1 }]
}
```

### Validation

- `pomodoro.microBreaks.enabled` must be boolean.
- `minIntervalSeconds` must be an integer from 30 to 3600.
- `maxIntervalSeconds` must be an integer from 30 to 3600.
- `maxIntervalSeconds` must be greater than or equal to `minIntervalSeconds`.
- `durationSeconds` must be an integer from 5 to 300.

### Expected Outcomes

- Valid requests persist and echo normalized `microBreaks` settings in the response.
- Invalid interval ordering returns a validation error and does not update stored settings.
- Invalid duration or interval bounds return a validation error and do not update stored settings.

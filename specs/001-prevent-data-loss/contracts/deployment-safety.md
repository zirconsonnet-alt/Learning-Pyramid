# Contract: Deployment Safety

This contract defines how deployment and synchronization workflows interact with protected data.

## Preflight Check

Preflight runs before deploy, sync, rebuild, restart with volume changes, or maintenance that can affect persistent paths.

Input:

```json
{
  "operation": "sync-selfhost",
  "environment": "self-host",
  "requireFreshBackup": true,
  "maxBackupAgeMinutes": 1440,
  "candidateDeleteRules": ["frontend/dist/assets/**"],
  "override": null
}
```

Output:

```json
{
  "allowed": false,
  "state": "blocked",
  "blockers": [
    {
      "code": "PROTECTED_PATH_NOT_MOUNTED",
      "message": "/app/data is not backed by the expected persistent host path",
      "protectedClassId": "media-assets"
    }
  ],
  "warnings": [],
  "latestVerifiedBackup": null
}
```

Rules:

- Any blocker sets `allowed=false`.
- A missing, empty-unexpected, unreadable, or unwritable protected path is a blocker.
- Delete/sync rules may not target protected data paths.
- Operations that can destroy or replace data require a fresh verified backup unless an audited emergency override is supplied.

## Emergency Override

Input:

```json
{
  "overrideId": "override_20260502_120000",
  "actor": "operator@example.com",
  "reason": "emergency recovery after disk incident",
  "expiresAt": "2026-05-02T13:00:00Z",
  "acknowledgedRisks": [
    "protected storage could be incomplete",
    "restore from latest verified backup may be required"
  ],
  "linkedBackupId": "backup_20260502_110000"
}
```

Rules:

- Override must be explicit, time-limited, and audited.
- Override cannot be implicit through command flags such as `--force` unless the same metadata is supplied.

## Postflight Check

Postflight runs after deploy or restore.

Output:

```json
{
  "state": "ok",
  "checkedAt": "2026-05-02T12:05:00Z",
  "validated": {
    "users": 3,
    "projects": 12,
    "recallPoints": 120,
    "mediaReferences": 42
  },
  "findings": []
}
```

Rules:

- HTTP health alone is insufficient.
- Postflight must verify representative user/project/media access.
- Any unresolved blocking finding marks the deployment failed.

## Sync Script Behavior

Required behavior for `tools/sync_selfhost_server.ps1` and shell equivalents:

- Run or call preflight before changing containers or remote files.
- Preserve protected data paths regardless of rsync delete settings.
- Keep deploy assets and runtime data concerns separate.
- Run postflight after container restart.
- Surface blockers in command output and exit non-zero.

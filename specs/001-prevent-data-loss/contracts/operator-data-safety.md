# Contract: Operator Data Safety

This contract defines the operator-visible safety workflows for backup, restore, integrity checks, and status reporting.

## Data Safety Status API

`GET /api/system/data-safety`

Response `200`:

```json
{
  "state": "ok",
  "checkedAt": "2026-05-02T12:00:00Z",
  "releaseBlocked": false,
  "protectedClasses": [
    {
      "id": "media-assets",
      "storageKind": "filesystem",
      "state": "ok",
      "locations": ["/app/data"]
    }
  ],
  "latestVerifiedBackup": {
    "bundleId": "backup_20260502_120000",
    "createdAt": "2026-05-02T12:00:00Z",
    "fileCount": 42,
    "totalBytes": 123456
  },
  "findings": []
}
```

Rules:

- `state=blocked` means deploy/restart/rebuild/sync operations must stop unless an audited override is supplied.
- Missing or unreadable protected storage is never reported as an empty dataset.

## Integrity Check API

`POST /api/system/data-safety/check`

Request:

```json
{
  "scope": "all",
  "includeMediaReferences": true
}
```

Response `200`:

```json
{
  "state": "blocked",
  "checkedAt": "2026-05-02T12:01:00Z",
  "findings": [
    {
      "severity": "blocking",
      "code": "MEDIA_FILE_MISSING",
      "protectedClassId": "media-assets",
      "affectedEntityIds": ["proj_000011", "asset_00000001"],
      "expectedLocation": "/app/data/.../media/asset_00000001.png",
      "recommendedAction": "restore the file from a verified backup or remove the broken reference intentionally"
    }
  ]
}
```

## Backup CLI

Command:

```powershell
python tools/backup_runtime_bundle.py .\backups\runtime.zip --include-media --verify
```

Required behavior:

- Captures project/application snapshots, auth snapshots, media payload files, and a manifest.
- Writes checksums for each included media file.
- Exits non-zero if any blocking protected data class cannot be read.
- Prints a verification summary.

## Backup Verification CLI

Command:

```powershell
python tools/backup_runtime_bundle.py .\backups\runtime.zip --verify-only
```

Required behavior:

- Validates manifest schema, counts, file presence, and checksums.
- Exits non-zero when the bundle cannot be used for restore.

## Restore CLI

Dry run:

```powershell
python tools/restore_runtime_bundle.py .\backups\runtime.zip --dry-run
```

Apply:

```powershell
python tools/restore_runtime_bundle.py .\backups\runtime.zip --confirm-replace
```

Required behavior:

- Refuses unverified bundles.
- Shows what will be replaced before applying.
- Uses staging paths before replacing active data.
- Runs post-restore integrity checks.
- Writes an audit event with operation id and result.

## Audit Events

All backup, restore, integrity check, deploy block, and override operations write durable events with actor, timestamp, operation id, inputs summary, result, and affected protected data classes.

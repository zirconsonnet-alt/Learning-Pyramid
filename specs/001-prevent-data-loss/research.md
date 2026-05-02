# Research: Prevent Server Data Loss

## Decision: Protected Data Inventory Is Explicit

Protected production data includes user auth records, sessions, profiles, memberships, project metadata, recall points, review progress, uploaded media assets, media reference indexes, operational audit records, and backup/restore manifests.

Rationale: The recent image-loss incident showed that database snapshots alone are not enough. Filesystem media under project roots is user data and must be treated like the database.

Alternatives considered:

- Database-only inventory: rejected because media files can be lost while database references remain.
- Relying on Docker volume naming conventions: rejected because a valid-looking container can still shadow or omit the real bind mount.

## Decision: Backup Bundles Include Media Payloads And Manifests

Runtime backup bundles will include store snapshots, auth snapshots, media manifests, media files, checksums, counts, sizes, source paths, app/build metadata, and verification results.

Rationale: A restore must prove both references and bytes are present. Manifests allow fast integrity checks and explain exactly what was captured.

Alternatives considered:

- Store only file paths in backup metadata: rejected because paths do not recover deleted files.
- Copy media without checksums: rejected because partial or corrupt copies would look successful.

## Decision: Restore Uses Dry-Run, Confirmation, Staging, And Verification

Restore must support dry-run validation, explicit replace confirmation, staging into temporary paths, final application, and post-restore integrity reporting.

Rationale: Recovery is a destructive operation if it replaces current data. Operators need a precise preview and a verified result.

Alternatives considered:

- One-step overwrite restore: rejected because it can destroy newer data or leave partial state.
- Manual file/database restoration: rejected because it is hard to audit and easy to get wrong during an incident.

## Decision: Deployment Gates Block Data Risk

Preflight checks block deploy/sync/rebuild when protected paths are missing, empty unexpectedly, unreadable, unwritable, mounted to ephemeral container storage, or targeted by delete rules. Risky operations require a fresh verified backup unless explicitly overridden with audited emergency metadata.

Rationale: The system must fail closed before data can be lost. A warning is not enough for operations that can remove user data.

Alternatives considered:

- Post-deploy checks only: rejected because they detect loss after damage.
- Warnings without blocking: rejected because the spec requires preventing silent data loss.

## Decision: Postflight Checks Confirm Representative Data

After deployment, checks verify application health plus representative protected data: users, projects, recall points, media reference resolution, and configured storage paths.

Rationale: A deploy can succeed technically while serving an empty or partial dataset. Postflight checks catch that distinction immediately.

Alternatives considered:

- HTTP health endpoint only: rejected because it cannot prove user data is accessible.

## Decision: Broken Media References Are First-Class Findings

Integrity checks compare media reference records against expected files and report missing files, orphaned files, inaccessible paths, and affected project/recall-point identifiers.

Rationale: The current broken image symptom is exactly a stale reference to missing file bytes. Future incidents need direct diagnosis.

Alternatives considered:

- Let frontend image load failures reveal the problem: rejected because users see broken UI before operators see the cause.

## Decision: UI And API Distinguish Empty Data From Inaccessible Data

When protected data cannot be loaded or integrity checks fail, the API returns a data-safety state and the frontend shows unavailable/degraded state instead of silently rendering an empty project.

Rationale: Silent empty states make data loss look normal and delay response.

Alternatives considered:

- Reuse generic fetch errors only: rejected because they do not explain whether data is absent, inaccessible, or degraded.

## Decision: Safety Events Are Audited

Backup, restore, preflight, postflight, integrity check, deploy block, and emergency override events are recorded with actor, timestamp, operation id, inputs, result, and affected protected classes.

Rationale: Data-loss prevention needs accountability and incident reconstruction.

Alternatives considered:

- Console logs only: rejected because container logs are not durable enough for audit history.

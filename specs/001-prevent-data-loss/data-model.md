# Data Model: Prevent Server Data Loss

## ProtectedDataClass

Represents a category of production user data that must survive operations.

Fields:

- `id`: stable identifier, for example `auth-users`, `project-store`, `media-assets`
- `label`: operator-facing name
- `storage_kind`: `database`, `filesystem`, or `derived-index`
- `locations`: configured database names, tables, directories, or index files
- `criticality`: `blocking` or `warning`
- `owner_component`: backend, tools, deployment, or frontend

Validation:

- Every blocking class has at least one configured location.
- Filesystem classes must declare expected persistent mount roots.

## DataSafetyStatus

Current system-level safety state.

Fields:

- `state`: `ok`, `warning`, `blocked`, or `unknown`
- `checked_at`: timestamp
- `environment`: local, self-host, hosted, or unknown
- `protected_classes`: list of `ProtectedDataClass` statuses
- `findings`: list of `IntegrityFinding`
- `latest_verified_backup`: optional `BackupManifest` summary
- `release_blocked`: boolean

Validation:

- Any blocking finding sets `state=blocked` and `release_blocked=true`.
- `unknown` is used when required storage cannot be inspected.

## BackupBundle

Durable archive or directory containing recoverable protected data.

Fields:

- `bundle_id`: unique id
- `created_at`: timestamp
- `created_by`: operator or automation id
- `source_environment`: environment identifier
- `app_version`: build or commit metadata when available
- `manifest`: `BackupManifest`
- `store_snapshot`: project/application data snapshot
- `auth_snapshot`: authentication data snapshot
- `media_payload`: uploaded media files included with relative paths
- `verification`: latest `BackupVerification`

Validation:

- A bundle is usable only when `verification.state=verified`.
- Media references in snapshots must resolve either to included media files or explicit skipped entries with reason.

## BackupManifest

Machine-readable description of bundle contents.

Fields:

- `schema_version`
- `protected_classes`
- `file_count`
- `total_bytes`
- `checksums`
- `media_assets`
- `snapshot_counts`
- `warnings`

Validation:

- Checksum entries are required for all included media payload files.
- Snapshot counts must be non-negative and internally consistent.

## BackupVerification

Result of validating a backup bundle.

Fields:

- `state`: `verified`, `failed`, or `partial`
- `verified_at`
- `checks`
- `errors`
- `warnings`

Validation:

- Any missing payload file referenced by the manifest fails verification.
- Any corrupt checksum fails verification.

## RestorePlan

Dry-run result before applying a restore.

Fields:

- `bundle_id`
- `target_environment`
- `mode`: `replace`, `merge-safe`, or `inspect-only`
- `would_replace`
- `would_create`
- `would_skip`
- `risks`
- `requires_confirmation`

Validation:

- `replace` mode always requires explicit confirmation.
- A restore cannot proceed from an unverified bundle.

## RestoreReport

Result after applying a restore.

Fields:

- `operation_id`
- `started_at`
- `finished_at`
- `bundle_id`
- `applied_counts`
- `post_restore_status`
- `errors`
- `rollback_available`

Validation:

- Successful restore requires post-restore `DataSafetyStatus.state` to be `ok` or documented `warning`.

## IntegrityFinding

A specific data-safety issue.

Fields:

- `id`
- `severity`: `blocking`, `warning`, or `info`
- `code`
- `message`
- `protected_class_id`
- `affected_entity_ids`
- `expected_location`
- `observed_state`
- `recommended_action`

Validation:

- Blocking findings must include affected class and recommended action.

## MediaReferenceCheckResult

Specialized result for media references.

Fields:

- `project_id`
- `asset_id`
- `referenced_by`
- `expected_path`
- `exists`
- `readable`
- `checksum`
- `finding_id`

Validation:

- `exists=false` for an actively referenced media asset creates a blocking `IntegrityFinding`.

## DataSafetyAuditEvent

Durable audit event for safety-sensitive operations.

Fields:

- `event_id`
- `occurred_at`
- `actor`
- `operation_type`
- `operation_id`
- `inputs_summary`
- `result`
- `protected_classes`
- `override_id`

Validation:

- Emergency overrides require an audit event.
- Failed backup, restore, preflight, and postflight operations are retained.

## DestructiveOperationOverride

Explicit emergency authorization for bypassing a safety blocker.

Fields:

- `override_id`
- `actor`
- `reason`
- `expires_at`
- `acknowledged_risks`
- `linked_backup_id`

Validation:

- Override must expire.
- Override must include reason and risk acknowledgement.
- Override cannot bypass backup verification unless the incident record explicitly states backup is unavailable and why.

## State Transitions

Backup: `requested -> created -> verified -> retained` or `requested -> created -> failed`.

Restore: `dry-run -> confirmed -> staged -> applied -> verified` or `dry-run -> confirmed -> failed`.

Deployment gate: `pending -> checked -> allowed` or `pending -> checked -> blocked`; emergency path is `blocked -> overridden -> audited -> allowed`.

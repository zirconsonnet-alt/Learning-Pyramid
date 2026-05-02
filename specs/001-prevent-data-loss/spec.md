# Feature Specification: Prevent Server Data Loss

**Feature Branch**: `001-prevent-data-loss`  
**Created**: 2026-05-02  
**Status**: Draft  
**Input**: User description: "服务器无故丢失用户数据，这简直就是犯罪，永远杜绝这种现象"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Protect User Data During Operations (Priority: P1)

As a learner using the hosted service, I need my account, projects, recall points, review progress, uploaded images, membership state, settings, and study history to remain intact after deployments, restarts, container rebuilds, synchronization runs, and routine maintenance, so that I can trust the service with long-term learning records.

**Why this priority**: Silent or unexplained user data loss destroys trust and can erase irreplaceable study work. This is the minimum viable protection for any hosted deployment.

**Independent Test**: Seed a hosted-like environment with representative user data and media, perform each routine operational action, and verify that every seeded record and file is still accessible afterward.

**Acceptance Scenarios**:

1. **Given** a hosted environment with active users, projects, recall points, review queues, uploaded recall-point images, and membership records, **When** a normal deployment completes, **Then** all data remains present, readable, and associated with the same users and projects.
2. **Given** a hosted environment with active users and uploaded media, **When** the app container is rebuilt or restarted, **Then** user records and uploaded media remain available without requiring manual restoration.
3. **Given** a synchronization or deployment command is about to run, **When** it detects that a target path may contain persistent user data, **Then** the command refuses destructive changes unless a verified backup and explicit operator confirmation are present.

---

### User Story 2 - Recover Quickly From Data Incidents (Priority: P2)

As the service operator, I need recent, complete, and restorable backups for hosted user data, so that any confirmed data incident can be reversed with minimal loss and a clear recovery path.

**Why this priority**: Prevention is mandatory, but backup and recovery are the final line of defense when storage, deployment, or human mistakes happen.

**Independent Test**: Create representative data, capture a backup, intentionally restore into a clean environment, and verify that users, projects, media, subscriptions, and learning progress match the source state.

**Acceptance Scenarios**:

1. **Given** a production-like environment with representative user data, **When** an operator requests a backup, **Then** the resulting backup includes account data, project data, uploaded media, configuration required to interpret the data, and a human-readable summary.
2. **Given** a backup created by the system, **When** it is restored into a clean environment, **Then** all included users can sign in and all included learning data and media are accessible.
3. **Given** a deployment or migration is requested, **When** a recent verified backup is missing or stale, **Then** the operation is blocked or clearly requires an explicit emergency override with an audit record.

---

### User Story 3 - Detect and Explain Data Risk (Priority: P3)

As the service operator, I need clear warnings, audit trails, and health checks for storage and data integrity risks, so that data loss is detected before users report missing work and every incident has a traceable explanation.

**Why this priority**: Silent failure is the most damaging mode. Operators need early warning and evidence to prevent recurrence.

**Independent Test**: Introduce controlled risk conditions, such as missing persistent media paths, unreadable backup targets, or mismatched data references, and verify that the system reports actionable warnings and records the relevant operational events.

**Acceptance Scenarios**:

1. **Given** user records reference uploaded media, **When** the referenced media file is missing, **Then** the system reports the broken reference with affected project, asset, and user impact information instead of silently rendering a broken state.
2. **Given** a deployment or maintenance action changes storage paths or data-bearing directories, **When** the action completes, **Then** an audit record identifies what was checked, what was changed, and whether persistent data validation passed.
3. **Given** recurring integrity checks are enabled, **When** data or media references become inconsistent, **Then** operators receive a clear alert before the issue becomes a broad user-facing data loss incident.

### Edge Cases

- A deployment is interrupted midway through upload, extraction, synchronization, or container refresh.
- A persistent directory is accidentally omitted, remapped, mounted read-only, or replaced by an empty directory.
- A database record references a media file that no longer exists, or a media file exists without a matching record.
- A backup completes but is incomplete, corrupted, encrypted with an unavailable key, or produced from the wrong environment.
- Multiple users are active while a deployment, backup, migration, or restore is in progress.
- An operator runs a destructive command from the wrong working directory or against the wrong server.
- Storage space is exhausted during upload, backup, restore, or media write.
- A rollback restores application files but not matching user data, or restores user data without matching media.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST classify hosted user data as protected production data, including accounts, sessions needed for continuity, profiles, projects, learning objects, recall points, review tasks, review queues, uploaded media, membership records, payment state, settings, audit records, and study metrics.
- **FR-002**: The system MUST preserve protected production data across routine deployments, restarts, rebuilds, synchronization runs, and maintenance tasks.
- **FR-003**: Deployment and synchronization operations MUST avoid deleting, replacing, or shadowing persistent user-data directories by default.
- **FR-004**: Any operation that can remove, overwrite, relocate, or make inaccessible protected production data MUST require a verified backup and an explicit operator confirmation that names the affected environment and data scope.
- **FR-005**: The system MUST block routine deployment or migration when persistent storage paths are missing, empty when data is expected, not writable when writes are required, or not readable when reads are required.
- **FR-006**: The system MUST verify after deployment that representative protected data categories remain reachable, including user records, project records, recall points, and uploaded media references.
- **FR-007**: The system MUST provide a backup capability that captures all protected production data needed for full service recovery, including uploaded media and the configuration needed to interpret restored data.
- **FR-008**: The system MUST verify backup integrity before considering a backup valid for deployment, migration, or emergency recovery.
- **FR-009**: The system MUST provide a restore capability that can recreate a usable environment from a valid backup and report exactly what was restored.
- **FR-010**: The system MUST keep an audit trail for backup, restore, deployment, synchronization, migration, destructive override, and data-integrity check events.
- **FR-011**: The system MUST detect broken references between persisted records and uploaded media and report affected project, record, and asset identifiers to operators.
- **FR-012**: The system MUST show users a clear recoverable-state message when their data cannot be loaded, rather than silently presenting empty projects, missing media, or reset account state as if it were normal.
- **FR-013**: The system MUST distinguish “no data exists” from “data exists but cannot be reached” in user-facing and operator-facing states.
- **FR-014**: The system MUST retain enough recent backup history to recover from accidental deletion discovered after at least one normal deployment cycle.
- **FR-015**: Emergency overrides that bypass backup, integrity, or storage checks MUST be recorded with operator identity, reason, timestamp, affected environment, and expected impact.
- **FR-016**: The system MUST provide an operator-facing data safety status that summarizes latest backup age, latest restore verification, storage path health, known broken references, and latest deployment data validation result.
- **FR-017**: The system MUST treat unresolved protected-data integrity failures as release blockers for hosted production deployments.
- **FR-018**: The system MUST include automated checks that fail when deployment configuration would place protected user data only in non-persistent runtime storage.

### Key Entities

- **Protected Production Data**: User-owned or user-affecting data that must never disappear silently, including learning content, account state, uploaded media, payment/membership state, configuration, and audit history.
- **Data Safety Check**: A pre-operation or post-operation validation that confirms protected data locations, references, and representative records remain accessible.
- **Backup Snapshot**: A restorable capture of protected production data, uploaded media, and interpretation metadata at a known point in time.
- **Restore Verification**: Evidence that a backup can recreate a usable environment and that restored records and media match the source snapshot.
- **Operational Audit Event**: A durable record of deployments, backups, restores, overrides, integrity failures, and maintenance actions that may affect data safety.
- **Broken Data Reference**: A persisted relationship, such as a media asset reference, whose target is missing or inaccessible.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of routine hosted deployments preserve seeded representative user accounts, projects, recall points, review state, uploaded media, and membership records in validation runs.
- **SC-002**: 0 routine deployments proceed when configured persistent storage for protected production data is missing, inaccessible, or mapped only to non-persistent runtime storage.
- **SC-003**: A valid full backup can be produced and restored into a clean environment with all sampled user data and uploaded media accessible within 30 minutes for a standard hosted deployment.
- **SC-004**: 100% of destructive overrides produce an audit record containing operator, reason, timestamp, environment, and data scope.
- **SC-005**: Broken references between records and uploaded media are detected and reported with affected identifiers in the next integrity check.
- **SC-006**: Users never see an empty or reset state as normal when the system has evidence that their data exists but cannot be reached.
- **SC-007**: Operators can view current data safety status, including backup age and integrity result, in under 1 minute.
- **SC-008**: Support tickets or user reports caused by unexplained hosted data disappearance fall to zero after adoption.

## Assumptions

- Hosted production data includes both database-like records and filesystem-like uploaded media.
- The feature covers prevention, detection, backup, restore, and auditability; it does not require recovering files that were already permanently lost before backups existed.
- Routine operations include deployments, container restarts, container rebuilds, release synchronization, migrations, and server maintenance commands.
- Emergency override remains possible for true disaster response, but it must be explicit, auditable, and exceptional.
- Existing authentication and authorization concepts remain in place; this feature adds data safety guarantees around them.

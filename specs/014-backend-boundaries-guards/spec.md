# Feature Specification: Backend Boundaries and Guards

**Feature Branch**: `014-backend-boundaries-guards`  
**Created**: 2026-05-10  
**Status**: Draft  
**Input**: User description: "先做后端架构边界设计和护栏，明确后端模块边界、防止 scoped project identity、auth ownership、跨 project 原子写入、router 越界调用等语义再次分叉。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Understand Backend Boundaries (Priority: P1)

As the project maintainer, I want a clear backend boundary design so future backend work has one obvious place for identity resolution, authorization ownership, cross-project mutation, and transport adaptation decisions.

**Why this priority**: Without a shared boundary design, new fixes can solve local symptoms while creating parallel semantics in another layer.

**Independent Test**: Can be tested by reviewing a backend change proposal and identifying which boundary owns each responsibility without reading unrelated modules.

**Acceptance Scenarios**:

1. **Given** a proposed route change, **When** the maintainer checks the boundary design, **Then** it is clear whether the route may perform the behavior directly or must delegate to a backend service boundary.
2. **Given** a proposed subject/material lifecycle change, **When** the maintainer checks the boundary design, **Then** it is clear that cross-project mutations require one atomic behavior owner.
3. **Given** a proposed scoped project identity change, **When** the maintainer checks the boundary design, **Then** it is clear where public project ids are resolved to storage identities and where they must not appear.

---

### User Story 2 - Detect Boundary Drift Early (Priority: P2)

As the project maintainer, I want guard checks that report boundary violations so accidental forks in identity, authorization, or mutation semantics are caught before they become accepted patterns.

**Why this priority**: A written design alone does not prevent drift; lightweight guards make violations visible during review and verification.

**Independent Test**: Can be tested by introducing representative boundary violations in a disposable working copy and confirming the guard report identifies them.

**Acceptance Scenarios**:

1. **Given** transport-layer code attempts to access backend storage internals directly, **When** guard checks run, **Then** the violation is reported with the affected location and rule.
2. **Given** authorization ownership is added for a storage-only project identity, **When** guard checks run, **Then** the violation is reported as an authorization boundary error.
3. **Given** a cross-project lifecycle mutation bypasses the atomic behavior owner, **When** guard checks run, **Then** the violation is reported as a mutation consistency risk.

---

### User Story 3 - Guide Incremental Refactoring (Priority: P3)

As the project maintainer, I want the boundary design to identify safe extraction seams so the backend can become clearer incrementally without changing user-visible behavior.

**Why this priority**: The current backend has large modules, but clarity must improve through bounded steps rather than broad rewrites.

**Independent Test**: Can be tested by choosing the first extraction candidate and confirming it has a defined responsibility, allowed dependencies, forbidden dependencies, and unchanged externally visible behavior.

**Acceptance Scenarios**:

1. **Given** a large backend module contains multiple responsibilities, **When** the design is reviewed, **Then** it identifies which responsibility should be extracted first and why.
2. **Given** a proposed extraction would change public behavior, **When** the design is applied, **Then** the change is rejected unless a separate behavior-changing feature explicitly approves it.

### Edge Cases

- A guard reports an existing violation that cannot be fixed within the current feature scope; the system must report it without silently allowing new violations of the same type.
- A module legitimately needs privileged access to storage internals; the design must require an explicit named boundary owner rather than ad hoc access from transport or unrelated services.
- Existing compatibility or migration paths are discovered; they must be documented as current risk, not expanded into new fallback or shim behavior.
- A guard cannot determine intent from static structure alone; it must produce a reviewable finding rather than silently classifying the pattern as safe.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a backend boundary design that names each major backend responsibility and identifies its owning layer.
- **FR-002**: The boundary design MUST define what transport-layer code is allowed to do and what it must delegate to backend behavior owners.
- **FR-003**: The boundary design MUST define one ownership rule for public scoped project identities and storage-only project identities.
- **FR-004**: The boundary design MUST define one ownership rule for user authorization over subject-level resources and must exclude storage-only identities from user ownership semantics.
- **FR-005**: The boundary design MUST define that cross-project lifecycle mutations are owned by an atomic behavior boundary and must not be split across independent writes.
- **FR-006**: The boundary design MUST define how existing migration or compatibility paths are treated so they do not become new fallback, shim, or legacy expansion points.
- **FR-007**: Guard checks MUST report transport-layer access to backend storage internals when that access bypasses the approved backend boundary.
- **FR-008**: Guard checks MUST report attempts to assign user ownership to storage-only project identities.
- **FR-009**: Guard checks MUST report scoped project routes or backend behaviors that bypass the approved scoped identity resolution boundary.
- **FR-010**: Guard checks MUST report cross-project lifecycle mutation paths that do not go through the approved atomic behavior owner.
- **FR-011**: Guard reports MUST include enough information for review: rule id, affected location, severity, and a short explanation of the risk.
- **FR-012**: The feature MUST preserve existing user-visible behavior unless a separate approved feature changes that behavior.
- **FR-013**: The feature MUST not introduce fallback, shim, legacy compatibility expansion, hidden global state, or duplicate behavior paths as part of clarifying the architecture.

### Key Entities

- **Boundary Rule**: A named architectural constraint with an owner, rationale, allowed behavior, forbidden behavior, and review severity.
- **Guard Finding**: A report item identifying a possible rule violation, its affected location, severity, and explanation.
- **Transport Boundary**: The layer responsible for request adaptation, response shaping, and dependency wiring, without owning storage or domain mutation semantics.
- **Identity Boundary**: The owner of public scoped project identity resolution into storage-only identities.
- **Authorization Boundary**: The owner of user access and ownership semantics.
- **Atomic Mutation Boundary**: The owner of cross-project lifecycle changes that must publish all related state together or none of it.
- **Migration Risk**: An existing compatibility or migration path that must be contained and not expanded into new behavior.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer can classify at least 90% of backend change proposals in the affected areas into an owning boundary within 5 minutes.
- **SC-002**: Guard checks identify representative violations for transport-layer internals access, storage-only authorization ownership, scoped identity bypass, and non-atomic cross-project mutation.
- **SC-003**: New backend changes in the affected areas can be reviewed against a named rule id rather than relying on reviewer memory or informal convention.
- **SC-004**: No user-visible behavior changes are required to complete this feature.
- **SC-005**: The first implementation plan derived from this spec can be split into independently verifiable tasks for boundary documentation, guard checks, and any minimal cleanup required by the guards.

## Assumptions

- The first scope is architecture clarification and guard creation, not a broad backend rewrite.
- Existing behavior remains the baseline unless a specific behavior change is separately approved.
- Existing scoped project decisions remain binding: public scoped ids are public interface identity; storage-only project keys are implementation details; authorization ownership is subject-based.
- Guard checks are allowed to report existing risk without automatically fixing every reported location.
- The first refactoring candidate, if any is included later, should be the smallest change needed to make the boundary enforceable.

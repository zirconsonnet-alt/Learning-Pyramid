# Research: Unified Roll-Up Commit

## Decision: Make learning-object-isomorphic roll-up queue-backed

**Decision**: Learning-object-isomorphic roll-up will evaluate learning-object containers as before, but it may only select a container for roll-up when the source layer's current aggregation queue contains candidates covered by that learning object. If no covered current candidates exist, the object is skipped and no parent is created or registered for that object.

**Rationale**: The feature requirement is that all roll-ups consume aggregation queue candidates. If manual or threshold roll-up has already consumed the child candidates for a chapter, the queue is the durable signal that there is nothing left to roll up for that chapter.

**Alternatives considered**:

- Use active recall point coverage alone to decide eligibility. Rejected because it can recreate parents after queue candidates were already consumed.
- Create object-mirror nodes first and then prune the queue. Rejected because parent creation can happen before proving that queue-backed candidates exist.

## Decision: Preserve trigger-specific selection, unify landing outcome

**Decision**: Manual and threshold roll-up keep current-layer queue selection. Learning-object-isomorphic roll-up adds a selection step that filters source queue candidates by learning-object coverage. After selection, all triggers must produce the same outcome: consume selected source candidates, attach them under one parent, register the parent to the next applicable layer once, and record the reason.

**Rationale**: The trigger mode should answer "why and which candidates?" but not create a separate hierarchy semantics for "what happens after candidates are chosen."

**Alternatives considered**:

- Fully replace all paths with one large new orchestration workflow. Rejected as too broad and risky for this fix.
- Leave isomorphic roll-up as a mirror-maintenance path. Rejected because it allows duplicate hierarchy state.

## Decision: Keep Phase A/Phase B transaction boundaries intact

**Decision**: The implementation plan must respect existing roll-up scheduling boundaries: candidate freezing and parent creation happen separately from upper-layer registration where required, and no orchestrator Tick runs in the same transaction as forbidden phases.

**Rationale**: Existing tests and comments encode important scheduling invariants. This feature should remove state divergence, not loosen transaction boundaries.

**Alternatives considered**:

- Register isomorphic parents immediately in the same helper regardless of existing boundaries. Rejected because it can bypass existing scheduling constraints.

## Decision: Focus tests on observable hierarchy and queue effects

**Decision**: Tests will assert queue consumption, duplicate prevention, parent registration, and existing behavior preservation rather than private helper names.

**Rationale**: The feature is a domain behavior change. Tests should remain robust if helper extraction details change during implementation.

**Alternatives considered**:

- Source-level tests for exact helper calls. Rejected because they over-constrain implementation structure.

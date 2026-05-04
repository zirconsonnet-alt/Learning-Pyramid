# Feature Specification: Unified Roll-Up Commit

**Feature Branch**: `005-unify-roll-up-commit`  
**Created**: 2026-05-04  
**Status**: Draft  
**Input**: User description: "选出来之后的核心落地动作必须统一：不管是手动 roll up、同构上推还是阈值聚合上推，本质上都是把聚合队列的某些节点挂到一个新的上层节点；选中节点之后必须走统一的落地协议，避免重复建立、漏上推和状态分叉。补充：同构上推必须先从源层聚合队列中选到可消耗候选；如果候选已经被手动或阈值上推消耗，源聚合队列没有这些任务，就不能再次建立同名或同内容的上层节点。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Same Result After Candidate Selection (Priority: P1)

As a learner or reviewer of the learning structure, I want manual roll-up, threshold roll-up, and learning-object-isomorphic roll-up to produce the same committed structure once their candidates are chosen, so that changing the trigger mode never creates duplicate parent nodes or skips the next layer.

**Why this priority**: This is the core correctness guarantee. The trigger may differ, but the committed learning hierarchy must remain coherent and predictable.

**Independent Test**: Can be tested by preparing the same lower-layer aggregation candidates, invoking each roll-up trigger mode, and comparing the resulting parent node, child attachment, consumed candidates, upper-layer registration, and event/audit visibility.

**Acceptance Scenarios**:

1. **Given** a layer has eligible aggregation candidates, **When** manual roll-up selects those candidates, **Then** the system commits them through the shared roll-up landing behavior.
2. **Given** a layer has eligible aggregation candidates that satisfy the configured threshold, **When** threshold roll-up selects those candidates, **Then** the system commits them through the same shared roll-up landing behavior used by manual roll-up.
3. **Given** learning-object-isomorphic roll-up determines that a learning object container may be represented, **When** the source aggregation queue contains lower-layer candidates covered by that learning object, **Then** the system selects those queue candidates and commits them through the same shared roll-up landing behavior used by manual and threshold roll-up.

---

### User Story 2 - Prevent Duplicate Parents For Existing Roll-Ups (Priority: P2)

As a learner switching between roll-up strategies, I want the system to recognize an already committed upper-layer parent for the same selected lower-layer content, so that switching to learning-object-isomorphic roll-up does not create a second "Chapter 1" or equivalent duplicate node.

**Why this priority**: Strategy switching is a normal control-plane action. It must not damage the learning hierarchy or force the learner to manually clean duplicate structures.

**Independent Test**: Can be tested by manually rolling up a chapter-like candidate set, confirming the source aggregation queue no longer contains that chapter's child candidates, switching to learning-object-isomorphic roll-up, and verifying that the same content is not committed into a second parent node.

**Acceptance Scenarios**:

1. **Given** a set of lower-layer candidates has already been committed into an upper-layer parent, **When** another roll-up strategy later selects the same effective candidate set, **Then** the system reuses or recognizes the existing committed parent instead of creating a duplicate.
2. **Given** an existing upper-layer parent is recognized for selected candidates, **When** the roll-up completes, **Then** the lower-layer candidates are not reattached into a second competing parent.
3. **Given** the recognized parent is already registered in the correct upper layer, **When** the same effective roll-up is selected again, **Then** the operation is idempotent and does not add a duplicate upper-layer registration.
4. **Given** manual roll-up has already consumed the child candidates for "Chapter 1" from the source aggregation queue, **When** learning-object-isomorphic roll-up later evaluates the "Chapter 1" learning object, **Then** it performs no hierarchy-changing write and does not create another "Chapter 1" parent.

---

### User Story 3 - Preserve Trigger-Specific Selection While Sharing Landing (Priority: P3)

As a system maintainer, I want each trigger mode to keep its own candidate-selection rule while sharing the final landing behavior, so that manual control, threshold automation, and learning-object tree alignment remain distinct only where they should be distinct.

**Why this priority**: The feature should fix state divergence without removing valid differences in how each strategy chooses candidates.

**Independent Test**: Can be tested by verifying that each trigger mode chooses candidates according to its own rule, then hands the selected candidates to the same roll-up commit outcome.

**Acceptance Scenarios**:

1. **Given** the learner invokes manual roll-up, **When** candidates are selected, **Then** selection is based on the target layer's current aggregation queue.
2. **Given** threshold automation runs, **When** candidates are selected, **Then** selection is based on the target layer's current aggregation queue and threshold eligibility.
3. **Given** learning-object-isomorphic roll-up runs, **When** candidates are selected, **Then** selection is based on learning-object structure and currently consumable source aggregation queue candidates, and the selected candidates still land through the shared roll-up behavior.

### Edge Cases

- If a trigger selects no candidates, the system makes no hierarchy-changing write and reports a no-op outcome.
- If selected candidates include an ancestor and descendant from the same learning-task hierarchy, the roll-up is rejected rather than committing an ambiguous structure.
- If the global review task queue is not empty, roll-up triggers remain blocked by the existing review-priority gate.
- If actionable missing instances exist, roll-up triggers remain blocked by the existing missing-instance gate.
- If the selected candidates are already consumed by an existing committed parent, the outcome is idempotent and does not create a duplicate parent.
- If a learning object is structurally eligible but the source aggregation queue contains no covered candidates for it, learning-object-isomorphic roll-up makes no hierarchy-changing write.
- If manual or threshold roll-up already consumed the candidates for a learning object, later learning-object-isomorphic roll-up cannot recreate that learning object as a new parent from recall points alone.
- If the intended upper layer does not exist yet, the shared landing behavior creates or initializes it before registering the parent.
- If a learning-object-isomorphic selection maps to an already committed manually created parent, the system treats that parent as the effective roll-up result rather than requiring a separate object-mirror duplicate.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST define one shared roll-up landing behavior that is used after candidate selection by manual roll-up, threshold roll-up, and learning-object-isomorphic roll-up.
- **FR-002**: The shared landing behavior MUST attach the selected lower-layer candidate nodes under one upper-layer parent node.
- **FR-003**: The shared landing behavior MUST consume the selected candidates from their source layer's current aggregation queue in the same committed outcome.
- **FR-004**: The shared landing behavior MUST register the resulting upper-layer parent into the next applicable layer exactly once.
- **FR-005**: The shared landing behavior MUST create or initialize the required upper layer when it does not already exist.
- **FR-006**: The shared landing behavior MUST be idempotent for the same effective selected candidate set, so a repeated selection does not create a duplicate parent or duplicate upper-layer registration.
- **FR-007**: System MUST recognize an existing committed parent that already represents the same effective selected candidate set, even if that parent was created by a different roll-up trigger mode.
- **FR-008**: Manual roll-up MUST differ from other trigger modes only in how it selects candidates and records its user-initiated reason.
- **FR-009**: Threshold roll-up MUST differ from other trigger modes only in how it decides eligibility and records its threshold-triggered reason.
- **FR-010**: Learning-object-isomorphic roll-up MUST differ from other trigger modes only in how it selects and labels/binds the intended parent according to the learning-object structure.
- **FR-011**: System MUST NOT allow learning-object-isomorphic roll-up to bypass the shared landing behavior by creating an upper-layer hierarchy that is disconnected from selected aggregation candidates.
- **FR-012**: System MUST NOT create a second upper-layer parent for a learning-object container when the same effective lower-layer content has already been manually or automatically rolled up.
- **FR-013**: Learning-object-isomorphic roll-up MUST select lower-layer candidates from the source layer's current aggregation queue before it can create or update an upper-layer parent.
- **FR-014**: Learning-object-isomorphic roll-up MUST perform a no-op when the source aggregation queue contains no candidates covered by the evaluated learning object.
- **FR-015**: Learning-object-isomorphic roll-up MUST NOT create an upper-layer parent from learning-object structure or recall point coverage alone when no source aggregation queue candidates are available to consume.
- **FR-016**: System MUST preserve the existing review-priority and missing-instance gates for all roll-up trigger modes.
- **FR-017**: System MUST record enough roll-up outcome information for users and maintainers to distinguish the trigger reason while confirming that the same shared landing behavior was used.
- **FR-018**: System MUST keep roll-up selection rules separate from roll-up landing rules so future trigger modes can reuse the same landing behavior after selecting candidates.

### Key Entities

- **Roll-Up Trigger**: The reason or mode that initiates candidate selection, such as manual, threshold, or learning-object-isomorphic.
- **Selected Candidate Set**: The ordered lower-layer learning-task nodes chosen for one roll-up attempt.
- **Roll-Up Parent**: The upper-layer learning-task node that represents the selected candidates after the shared landing behavior completes.
- **Source Aggregation Queue**: The layer-owned candidate queue from which selected candidates are consumed.
- **Upper-Layer Registration**: The fact that the resulting parent is registered into the next applicable layer for future review and aggregation.
- **Roll-Up Outcome Record**: User-visible or audit-visible information describing the selected candidates, resulting parent, and trigger reason.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For the same effective selected candidate set, manual, threshold, and learning-object-isomorphic roll-up produce one equivalent committed parent structure.
- **SC-002**: Repeating a roll-up selection for already committed content creates zero duplicate parent nodes and zero duplicate upper-layer registrations.
- **SC-003**: Switching roll-up strategies after a successful roll-up preserves the existing hierarchy without creating a same-content duplicate in 100% of tested cases.
- **SC-004**: Every successful roll-up consumes the selected candidates from the source aggregation queue and registers the resulting parent to the upper layer in one committed outcome.
- **SC-005**: Users and maintainers can identify the trigger reason for every successful roll-up outcome without the trigger reason changing the core hierarchy result.
- **SC-006**: After manual or threshold roll-up consumes a learning object's child candidates, learning-object-isomorphic roll-up creates zero additional parent nodes for that same learning object.

## Assumptions

- "Core landing behavior" means the hierarchy-changing result after candidates are selected: parent creation or recognition, child attachment, source candidate consumption, upper-layer registration, and outcome recording.
- Trigger modes may keep different candidate-selection rules and different trigger-reason metadata.
- A learning object becoming structurally eligible is not sufficient by itself to roll up; there must also be currently consumable source aggregation queue candidates.
- The feature is about roll-up correctness and control-plane consistency, not about changing review task execution semantics.
- Existing gates such as non-empty review queue blocking and actionable missing-instance blocking remain in force.

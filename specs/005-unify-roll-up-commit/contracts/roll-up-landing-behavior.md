# Contract: Unified Roll-Up Landing Behavior

## Scope

This contract defines the expected behavior after any roll-up trigger has selected candidates. It applies to manual roll-up, threshold roll-up, and learning-object-isomorphic roll-up.

## Preconditions

- The global review task queue is empty.
- No actionable missing instances block progression.
- A source layer can be resolved.
- A hierarchy-changing roll-up has a non-empty selected candidate set from the source layer's current aggregation queue.
- Selected candidates do not contain an ancestor/descendant mix.

## Trigger-Specific Selection

Manual roll-up:

- Selects candidates from the target layer's current aggregation queue.
- Uses the user-provided or default parent title.
- Records a manual trigger reason.

Threshold roll-up:

- Selects candidates from the target layer's current aggregation queue only after threshold eligibility is met.
- Uses the automatic aggregation title.
- Records a threshold trigger reason.

Learning-object-isomorphic roll-up:

- Evaluates learning-object containers in deterministic order.
- Computes the source layer from the learning object's intended target layer.
- Selects only current source aggregation queue candidates covered by the evaluated learning object.
- Performs no hierarchy-changing write when no covered source queue candidates exist.
- Must not create a parent from learning-object structure or recall point coverage alone.

## Shared Landing Outcome

For any successful trigger:

1. The selected source queue candidates are frozen for the roll-up attempt.
2. The selected candidates are consumed from the source aggregation queue.
3. Exactly one upper-layer parent is created or an existing equivalent parent is recognized.
4. The selected candidates are attached under that parent.
5. The parent is registered to the next applicable layer exactly once.
6. The outcome records the trigger reason without changing the hierarchy semantics.

## No-Op Outcomes

The system performs no hierarchy-changing write when:

- The trigger selects no candidates.
- Learning-object-isomorphic roll-up finds a structurally eligible learning object but no covered source queue candidates.
- The effective content has already been consumed and no additional registration is needed.
- Required gates are blocked.

## Required Regression Coverage

- Manual roll-up consumes a chapter's child candidates; switching to learning-object-isomorphic roll-up does not create a duplicate chapter parent.
- Learning-object-isomorphic roll-up with covered current source queue candidates consumes those candidates and registers the resulting parent to the upper layer.
- Learning-object-isomorphic roll-up with active recall points but an empty source queue does not create an object-mirror parent.
- Existing disabled-threshold manual roll-up behavior remains valid.
- Existing threshold roll-up behavior continues to consume the queue and record threshold reason.

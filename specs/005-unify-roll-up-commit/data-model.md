# Data Model: Unified Roll-Up Commit

## Roll-Up Trigger

Represents the reason a roll-up attempt started.

Fields:

- `reason`: Manual, threshold, or learning-object-isomorphic.
- `target_layer_index`: Layer whose current candidates are being considered or consumed.
- `intended_parent_label`: Optional user title or learning-object-derived label.
- `learning_object_reference`: Optional learning-object container reference for isomorphic selection.

Validation rules:

- Review-priority gate must be clear before any trigger mutates roll-up state.
- Actionable missing instances must block every trigger mode.
- Trigger reason may affect event/audit metadata but must not change the shared landing outcome for the same candidate set.

## Selected Candidate Set

The ordered lower-layer learning-task nodes selected for one roll-up attempt.

Fields:

- `source_layer_index`: Layer whose aggregation queue contains the candidates.
- `candidate_node_ids`: Ordered current queue candidates selected for consumption.
- `covered_instance_ids`: Instances covered by selected candidates, used to match learning-object-isomorphic intent.
- `covered_recall_point_ids`: Recall points covered by selected candidates, used for threshold and validation checks.

Validation rules:

- Candidate set must be non-empty for a hierarchy-changing roll-up.
- Candidates must come from the source layer's current aggregation queue.
- Candidate set must not mix ancestor and descendant nodes.
- If the same effective candidates have already been consumed, a repeat selection must be no-op or reuse the existing committed parent without duplicate registration.

## Roll-Up Parent

The upper-layer learning-task node representing the selected candidate set.

Fields:

- `node_id`: Stable learning-task node identifier.
- `title`: Manual, default, or learning-object-derived title.
- `child_node_ids`: Selected candidates attached under this parent.
- `origin_metadata`: Existing origin/binding information when applicable.

Validation rules:

- A successful roll-up creates or recognizes exactly one parent for the selected candidate set.
- The parent must not duplicate another committed parent for the same effective selected content.
- When an existing parent is recognized, the operation must not reattach children into a competing parent.

## Source Aggregation Queue

Layer-owned queue containing candidates not yet consumed by a roll-up.

Fields:

- `layer_index`: Source layer index.
- `current_node_ids`: Current unconsumed candidates.
- `historical_node_ids`: Previously consumed entries retained according to existing queue semantics.

Validation rules:

- Successful roll-up consumes selected candidates from the current queue in the same committed outcome.
- Learning-object-isomorphic roll-up must no-op when this queue contains no candidates covered by the evaluated learning object.

## Upper-Layer Registration

Registration that makes the roll-up parent available to the next applicable layer.

Fields:

- `parent_node_id`: Resulting roll-up parent.
- `upper_layer_index`: Next applicable layer.
- `registration_state`: Existing registration fact and aggregation queue membership.

Validation rules:

- A resulting parent is registered exactly once to the upper layer.
- If the upper layer does not exist, it is created or initialized before registration.
- Repeated roll-up selection must not add duplicate registration.

## Roll-Up Outcome Record

User-visible or audit-visible record of the completed or no-op roll-up attempt.

Fields:

- `trigger_reason`: Manual, threshold, or learning-object-isomorphic.
- `selected_candidate_count`: Number of consumed candidates.
- `parent_node_id`: Resulting parent when hierarchy changed or was recognized.
- `no_op_reason`: Empty source queue, no covered candidates, existing consumed content, or gate blocked.

Validation rules:

- Successful outcomes must preserve enough reason metadata for maintainers to distinguish the trigger.
- Reason metadata must not imply a separate landing behavior.

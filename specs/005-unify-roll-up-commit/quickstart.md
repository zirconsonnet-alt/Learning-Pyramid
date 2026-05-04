# Quickstart: Unified Roll-Up Commit Validation

## Targeted Tests

Run the focused roll-up behavior tests:

```powershell
pytest tests/test_spec_alignment.py -k "roll_up or isomorphic"
```

Run the specific regression once it exists:

```powershell
pytest tests/test_spec_alignment.py -k "isomorphic_does_not_duplicate_after_manual_roll_up"
```

Run the full spec-alignment suite after implementation:

```powershell
pytest tests/test_spec_alignment.py
```

## Manual Scenario

1. Create a manual-source project with a learning-object tree containing a root course and "Chapter 1" with two leaf lessons.
2. Submit learning tasks that cover both Chapter 1 lessons so layer 0 has current aggregation candidates.
3. Manually roll up layer 0 into "Chapter 1".
4. Confirm layer 0 current aggregation queue no longer contains the consumed child candidates.
5. Switch the project to learning-object-isomorphic roll-up.
6. Confirm no second "Chapter 1" parent appears.
7. Confirm no duplicate upper-layer registration appears for the same content.

## Expected Implementation Checks

- Learning-object-isomorphic roll-up must inspect source aggregation queue candidates before parent creation.
- If no covered source candidates exist, the scan returns no hierarchy-changing result.
- If covered candidates exist, the result must consume those candidates and register one parent to the upper layer.
- Existing review queue and actionable missing instance gates must still block all trigger modes.

## Validation Notes

- 2026-05-04: `pytest tests/test_spec_alignment.py -k "does_not_duplicate_after_manual_roll_up or noops_with_empty_source_queue"` passed with the new queue-backed isomorphic behavior.
- 2026-05-04: `pytest tests/test_spec_alignment.py -k "test_learning_object_isomorphic_roll_up_creates_object_mirror_layers or test_learning_object_isomorphic_roll_up_consumes_covered_lower_layer_candidates or test_learning_object_isomorphic_roll_up_prunes_stale_lower_layer_candidates or test_disabled_threshold_roll_up_keeps_candidates_until_manual_roll_up or does_not_duplicate_after_manual_roll_up or noops_with_empty_source_queue"` passed.
- 2026-05-04: Full `pytest tests/test_spec_alignment.py` passed (`102 passed, 51 skipped`).

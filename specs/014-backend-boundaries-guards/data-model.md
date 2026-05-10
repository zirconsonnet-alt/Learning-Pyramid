# Data Model: Backend Boundaries and Guards

## Boundary Rule

Represents one architectural constraint.

Fields:
- `rule_id`: Stable identifier, such as `BBG001`.
- `name`: Short rule name.
- `owner`: Boundary responsible for the behavior.
- `severity`: `low`, `medium`, or `high`.
- `rationale`: Why the rule exists.
- `allowed_patterns`: Behaviors allowed by the rule.
- `forbidden_patterns`: Behaviors that should produce findings.
- `approved_owner_paths`: Optional repository-relative paths that may own otherwise privileged behavior for this rule.

Validation:
- `rule_id`, `name`, `owner`, and `severity` are required.
- `severity` must be one of the defined levels.
- Each rule must have at least one forbidden pattern.
- Approved owner paths must be explicit repository-relative paths, not broad directory globs.

## Guard Finding

Represents one possible boundary violation.

Fields:
- `rule_id`: Boundary Rule that produced the finding.
- `path`: Repository-relative affected path.
- `line`: Optional line number when available.
- `severity`: Severity copied from the rule or raised by context.
- `message`: Short explanation of the risk.
- `evidence`: The matched behavior or review clue.

Validation:
- `rule_id`, `path`, `severity`, and `message` are required.
- Findings must be deterministic for the same repository state.
- Findings must be reviewable without requiring unrelated source inspection.

## Boundary Owner

Represents an approved owner for a category of behavior.

Fields:
- `name`: Boundary name.
- `responsibilities`: Behaviors owned by this boundary.
- `allowed_dependencies`: Other boundaries this owner may call.
- `forbidden_dependencies`: Dependencies that would create layering violations.
- `approved_paths`: Repository-relative files that implement the boundary owner.

Validation:
- Each responsibility must have exactly one owner.
- A dependency listed as forbidden cannot also be listed as allowed.
- Approved paths do not create general compatibility exceptions; they only identify the owning boundary for review.

## Migration Risk

Represents existing compatibility or migration behavior that should be contained.

Fields:
- `path`: Location of the existing behavior.
- `risk`: Why the behavior can cause drift.
- `containment_rule`: Boundary Rule that prevents expansion.
- `status`: `documented`, `contained`, or `requires-decision`.

Validation:
- Migration risks cannot be treated as approved patterns for new code.
- Risks marked `requires-decision` must not be automatically fixed by this feature.

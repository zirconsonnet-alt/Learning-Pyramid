from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True, slots=True)
class SubjectMaterialRecoveryItem:
    subject_id: str
    material_id: str
    material_type: str
    title: str
    created_at_ms: int
    scoped_project_id: str
    internal_project_id: str

    def to_json(self) -> dict[str, object]:
        return {
            "subjectId": self.subject_id,
            "materialId": self.material_id,
            "materialType": self.material_type,
            "title": self.title,
            "createdAtMs": int(self.created_at_ms),
            "scopedProjectId": self.scoped_project_id,
            "internalProjectId": self.internal_project_id,
        }


@dataclass(frozen=True, slots=True)
class SubjectMaterialIntegrityIssue:
    kind: str
    subject_id: str | None
    scoped_project_id: str | None
    internal_project_id: str | None
    material_id: str | None

    def to_json(self) -> dict[str, object | None]:
        return {
            "kind": self.kind,
            "subjectId": self.subject_id,
            "scopedProjectId": self.scoped_project_id,
            "internalProjectId": self.internal_project_id,
            "materialId": self.material_id,
        }


def build_subject_material_recovery_plan(
    *,
    project_rows: Sequence[dict[str, Any]],
    relationship_rows: Sequence[dict[str, Any]],
) -> list[SubjectMaterialRecoveryItem]:
    projects = {_text(row.get("project_id")): row for row in project_rows if _text(row.get("project_id"))}
    existing_internal_ids = {_text(row.get("internal_project_id")) for row in relationship_rows}
    existing_scoped_refs = {
        (_text(row.get("subject_id")), _text(row.get("scoped_project_id")))
        for row in relationship_rows
        if _text(row.get("subject_id")) and _text(row.get("scoped_project_id"))
    }

    items: list[SubjectMaterialRecoveryItem] = []
    for row in sorted(project_rows, key=lambda item: (_text(item.get("subject_id")), _text(item.get("scoped_project_id")), _text(item.get("project_id")))):
        internal_project_id = _text(row.get("project_id"))
        subject_id = _text(row.get("subject_id"))
        scoped_project_id = _text(row.get("scoped_project_id"))
        if not internal_project_id or not subject_id or not scoped_project_id:
            continue
        if _state(row) != "ACTIVE":
            continue
        if internal_project_id in existing_internal_ids or (subject_id, scoped_project_id) in existing_scoped_refs:
            continue
        subject = projects.get(subject_id)
        if subject is None or _state(subject) != "ACTIVE":
            continue
        project_type = _text(row.get("project_type")).upper()
        if project_type not in {"COURSE", "BOOK", "LOOSE_POINTS"}:
            continue
        items.append(
            SubjectMaterialRecoveryItem(
                subject_id=subject_id,
                material_id=f"mat_recovered_{internal_project_id}",
                material_type=project_type,
                title=_text(row.get("project_title")) or internal_project_id,
                created_at_ms=_int(row.get("created_at_ms")),
                scoped_project_id=scoped_project_id,
                internal_project_id=internal_project_id,
            )
        )
    return items


def validate_subject_material_relationship_integrity(
    *,
    project_rows: Sequence[dict[str, Any]],
    relationship_rows: Sequence[dict[str, Any]],
) -> list[SubjectMaterialIntegrityIssue]:
    projects = {_text(row.get("project_id")): row for row in project_rows if _text(row.get("project_id"))}
    issues: list[SubjectMaterialIntegrityIssue] = []
    existing_internal_ids = {_text(row.get("internal_project_id")) for row in relationship_rows}
    existing_scoped_refs = {
        (_text(row.get("subject_id")), _text(row.get("scoped_project_id")))
        for row in relationship_rows
        if _text(row.get("subject_id")) and _text(row.get("scoped_project_id"))
    }
    for row in relationship_rows:
        subject_id = _text(row.get("subject_id")) or None
        scoped_project_id = _text(row.get("scoped_project_id")) or None
        internal_project_id = _text(row.get("internal_project_id")) or None
        material_id = _text(row.get("material_id")) or None

        subject = projects.get(subject_id or "")
        if subject is None:
            issues.append(
                SubjectMaterialIntegrityIssue(
                    kind="missing_subject",
                    subject_id=subject_id,
                    scoped_project_id=scoped_project_id,
                    internal_project_id=internal_project_id,
                    material_id=material_id,
                )
            )
        elif _state(subject) == "DELETED":
            issues.append(
                SubjectMaterialIntegrityIssue(
                    kind="deleted_subject",
                    subject_id=subject_id,
                    scoped_project_id=scoped_project_id,
                    internal_project_id=internal_project_id,
                    material_id=material_id,
                )
            )

        internal_project = projects.get(internal_project_id or "")
        if internal_project is None:
            issues.append(
                SubjectMaterialIntegrityIssue(
                    kind="missing_internal_project",
                    subject_id=subject_id,
                    scoped_project_id=scoped_project_id,
                    internal_project_id=internal_project_id,
                    material_id=material_id,
                )
            )
        elif _state(internal_project) == "DELETED":
            issues.append(
                SubjectMaterialIntegrityIssue(
                    kind="deleted_internal_project",
                    subject_id=subject_id,
                    scoped_project_id=scoped_project_id,
                    internal_project_id=internal_project_id,
                    material_id=material_id,
                )
            )
    for row in project_rows:
        internal_project_id = _text(row.get("project_id")) or None
        subject_id = _text(row.get("subject_id")) or None
        scoped_project_id = _text(row.get("scoped_project_id")) or None
        if subject_id is None and scoped_project_id is None:
            continue
        if _state(row) != "ACTIVE":
            continue
        if internal_project_id in existing_internal_ids or (subject_id or "", scoped_project_id or "") in existing_scoped_refs:
            continue
        subject = projects.get(subject_id or "")
        if subject is None or _state(subject) == "DELETED":
            issues.append(
                SubjectMaterialIntegrityIssue(
                    kind="missing_subject" if subject is None else "deleted_subject",
                    subject_id=subject_id,
                    scoped_project_id=scoped_project_id,
                    internal_project_id=internal_project_id,
                    material_id=None,
                )
            )
        project_type = _text(row.get("project_type")).upper()
        if project_type not in {"COURSE", "BOOK", "LOOSE_POINTS"}:
            issues.append(
                SubjectMaterialIntegrityIssue(
                    kind="unsupported_material_project_type",
                    subject_id=subject_id,
                    scoped_project_id=scoped_project_id,
                    internal_project_id=internal_project_id,
                    material_id=None,
                )
            )
    return issues


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _state(row: dict[str, Any]) -> str:
    return _text(row.get("project_state")).upper()


def _int(value: Any) -> int:
    if value is None or value == "":
        return 0
    return int(value)

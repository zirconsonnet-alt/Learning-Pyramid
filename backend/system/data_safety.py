from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Sequence


DataSafetySeverity = Literal["blocking", "warning", "info"]
StorageKind = Literal["database", "filesystem", "derived-index"]


class DataSafetyState:
    OK = "ok"
    WARNING = "warning"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ProtectedDataClass:
    id: str
    label: str
    storage_kind: StorageKind
    locations: tuple[str, ...]
    criticality: Literal["blocking", "warning"] = "blocking"
    owner_component: str = "backend"

    def to_api_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "label": self.label,
            "storageKind": self.storage_kind,
            "locations": list(self.locations),
            "criticality": self.criticality,
            "ownerComponent": self.owner_component,
        }


@dataclass(frozen=True, slots=True)
class DataSafetyFinding:
    severity: DataSafetySeverity
    code: str
    message: str
    protected_class_id: str
    affected_entity_ids: tuple[str, ...] = tuple()
    expected_location: str | None = None
    observed_state: str | None = None
    recommended_action: str | None = None

    def to_api_dict(self) -> dict[str, object]:
        return {
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "protectedClassId": self.protected_class_id,
            "affectedEntityIds": list(self.affected_entity_ids),
            "expectedLocation": self.expected_location,
            "observedState": self.observed_state,
            "recommendedAction": self.recommended_action,
        }


@dataclass(frozen=True, slots=True)
class DataSafetyStatus:
    state: str
    checked_at: datetime
    protected_classes: tuple[ProtectedDataClass, ...]
    findings: tuple[DataSafetyFinding, ...] = tuple()
    release_blocked: bool = False
    environment: str = "unknown"
    latest_verified_backup: dict[str, object] | None = None

    def to_api_dict(self) -> dict[str, object]:
        return {
            "state": self.state,
            "checkedAt": self.checked_at.replace(microsecond=0).isoformat(),
            "environment": self.environment,
            "releaseBlocked": self.release_blocked,
            "protectedClasses": [item.to_api_dict() for item in self.protected_classes],
            "latestVerifiedBackup": self.latest_verified_backup,
            "findings": [item.to_api_dict() for item in self.findings],
        }


def build_default_protected_data_classes(*, data_roots: Sequence[str] | None = None) -> tuple[ProtectedDataClass, ...]:
    roots = tuple(str(item) for item in (data_roots or ("/data", "/app/data")))
    return (
        ProtectedDataClass(
            id="auth-users",
            label="Accounts, sessions, profiles, and memberships",
            storage_kind="database",
            locations=("auth-store",),
            owner_component="backend",
        ),
        ProtectedDataClass(
            id="project-store",
            label="Projects, recall points, review progress, and settings",
            storage_kind="database",
            locations=("project-store",),
            owner_component="backend",
        ),
        ProtectedDataClass(
            id="media-assets",
            label="Uploaded media assets",
            storage_kind="filesystem",
            locations=roots,
            owner_component="backend",
        ),
        ProtectedDataClass(
            id="audit-events",
            label="Operational audit events",
            storage_kind="derived-index",
            locations=("data-safety-audit",),
            owner_component="backend",
        ),
    )


def _unknown_storage_finding() -> DataSafetyFinding:
    return DataSafetyFinding(
        severity="blocking",
        code="DATA_SAFETY_UNKNOWN",
        message="Protected data storage could not be inspected.",
        protected_class_id="protected-data",
        observed_state="unknown",
        recommended_action="Run data-safety checks from an environment that can inspect protected storage paths.",
    )


def collect_data_safety_status(
    *,
    findings: Sequence[DataSafetyFinding] | None = None,
    storage_check_available: bool = True,
    protected_classes: Sequence[ProtectedDataClass] | None = None,
    environment: str = "unknown",
) -> DataSafetyStatus:
    resolved_findings = list(findings or ())
    if not storage_check_available:
        resolved_findings.append(_unknown_storage_finding())

    has_blocker = any(item.severity == "blocking" for item in resolved_findings)
    has_warning = any(item.severity == "warning" for item in resolved_findings)
    if has_blocker:
        state = DataSafetyState.BLOCKED if storage_check_available else DataSafetyState.UNKNOWN
    elif has_warning:
        state = DataSafetyState.WARNING
    else:
        state = DataSafetyState.OK

    return DataSafetyStatus(
        state=state,
        checked_at=datetime.now(timezone.utc),
        protected_classes=tuple(protected_classes or build_default_protected_data_classes()),
        findings=tuple(resolved_findings),
        release_blocked=bool(has_blocker),
        environment=environment,
    )


def collect_post_deploy_data_safety_status(
    *,
    validated: dict[str, int] | None = None,
    findings: Sequence[DataSafetyFinding] | None = None,
    environment: str = "unknown",
) -> dict[str, object]:
    status = collect_data_safety_status(findings=findings, environment=environment)
    payload = status.to_api_dict()
    payload["validated"] = dict(validated or {})
    return payload


def validate_protected_filesystem_roots(roots: Sequence[str | Path]) -> tuple[DataSafetyFinding, ...]:
    findings: list[DataSafetyFinding] = []
    for root in roots:
        path = Path(root)
        if not path.exists():
            findings.append(
                DataSafetyFinding(
                    severity="blocking",
                    code="PROTECTED_PATH_MISSING",
                    message=f"Protected data path does not exist: {path}",
                    protected_class_id="media-assets",
                    affected_entity_ids=("media-assets",),
                    expected_location=str(path),
                    observed_state="missing",
                    recommended_action="Restore the persistent data mount before continuing.",
                )
            )
            continue
        if not path.is_dir():
            findings.append(
                DataSafetyFinding(
                    severity="blocking",
                    code="PROTECTED_PATH_NOT_DIRECTORY",
                    message=f"Protected data path is not a directory: {path}",
                    protected_class_id="media-assets",
                    affected_entity_ids=("media-assets",),
                    expected_location=str(path),
                    observed_state="not-directory",
                    recommended_action="Point protected data storage at a persistent directory.",
                )
            )
            continue
        try:
            any(path.iterdir())
        except OSError:
            findings.append(
                DataSafetyFinding(
                    severity="blocking",
                    code="PROTECTED_PATH_UNREADABLE",
                    message=f"Protected data path cannot be read: {path}",
                    protected_class_id="media-assets",
                    affected_entity_ids=("media-assets",),
                    expected_location=str(path),
                    observed_state="unreadable",
                    recommended_action="Fix permissions or remount protected storage before continuing.",
                )
            )
    return tuple(findings)


def scan_media_references(
    references: Sequence[dict[str, object]],
    *,
    media_roots: Sequence[str | Path] = tuple(),
) -> tuple[DataSafetyFinding, ...]:
    findings: list[DataSafetyFinding] = []
    referenced_paths: set[Path] = set()
    for ref in references:
        project_id = str(ref.get("projectId") or "")
        asset_id = str(ref.get("assetId") or "")
        referenced_by = str(ref.get("referencedBy") or "")
        expected_path = Path(str(ref.get("expectedPath") or ""))
        if expected_path:
            referenced_paths.add(expected_path.resolve())
        if not expected_path.exists():
            affected = tuple(item for item in (project_id, asset_id, referenced_by) if item)
            findings.append(
                DataSafetyFinding(
                    severity="blocking",
                    code="MEDIA_FILE_MISSING",
                    message=f"Referenced media file is missing: {expected_path}",
                    protected_class_id="media-assets",
                    affected_entity_ids=affected,
                    expected_location=str(expected_path),
                    observed_state="missing",
                    recommended_action="Restore the media file from a verified backup or remove the broken reference intentionally.",
                )
            )

    for root in media_roots:
        root_path = Path(root)
        if not root_path.exists() or not root_path.is_dir():
            continue
        for path in sorted(item for item in root_path.rglob("*") if item.is_file()):
            if path.resolve() in referenced_paths:
                continue
            if path.parent.name != "media":
                continue
            findings.append(
                DataSafetyFinding(
                    severity="warning",
                    code="MEDIA_FILE_ORPHANED",
                    message=f"Media file has no known reference: {path}",
                    protected_class_id="media-assets",
                    affected_entity_ids=(path.stem,),
                    expected_location=str(path),
                    observed_state="orphaned",
                    recommended_action="Confirm whether this media file should be linked or archived.",
                )
            )
    return tuple(findings)

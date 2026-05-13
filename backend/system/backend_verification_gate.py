import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Iterable, Mapping

from backend.system.api import SystemAPI
from backend.system.inmemory_system import InMemorySystem
from backend.system.persistence_store import SQLiteSnapshotStore
from backend.system.postgres_store import PostgresStore


class GateOutcome(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True, slots=True)
class GateStatus:
    outcome: GateOutcome
    message: str
    details: Mapping[str, object] = field(default_factory=dict)

    @staticmethod
    def passed(message: str = "ok", *, details: Mapping[str, object] | None = None) -> "GateStatus":
        return GateStatus(GateOutcome.PASSED, message, dict(details or {}))

    @staticmethod
    def failed(message: str, *, details: Mapping[str, object] | None = None) -> "GateStatus":
        return GateStatus(GateOutcome.FAILED, message, dict(details or {}))

    @staticmethod
    def skipped(message: str, *, details: Mapping[str, object] | None = None) -> "GateStatus":
        return GateStatus(GateOutcome.SKIPPED, message, dict(details or {}))


@dataclass(frozen=True, slots=True)
class GateCheck:
    check_id: str
    label: str
    required: bool
    run: Callable[[], GateStatus]


@dataclass(frozen=True, slots=True)
class GateCheckResult:
    check_id: str
    label: str
    required: bool
    status: GateStatus

    @property
    def blocks_release(self) -> bool:
        return self.required and self.status.outcome is not GateOutcome.PASSED

    def to_dict(self) -> dict[str, object]:
        return {
            "checkId": self.check_id,
            "label": self.label,
            "required": self.required,
            "outcome": self.status.outcome.value,
            "message": self.status.message,
            "details": dict(self.status.details),
            "releaseBlocked": self.blocks_release,
        }


@dataclass(frozen=True, slots=True)
class GateReport:
    gate_name: str
    results: tuple[GateCheckResult, ...]

    @property
    def exit_code(self) -> int:
        return 1 if any(result.blocks_release for result in self.results) else 0

    @property
    def release_blocked(self) -> bool:
        return self.exit_code != 0

    def to_dict(self) -> dict[str, object]:
        executed = [result.to_dict() for result in self.results if result.status.outcome is not GateOutcome.SKIPPED]
        skipped = [result.to_dict() for result in self.results if result.status.outcome is GateOutcome.SKIPPED]
        failed = [result.to_dict() for result in self.results if result.status.outcome is GateOutcome.FAILED]
        return {
            "gateName": self.gate_name,
            "releaseBlocked": self.release_blocked,
            "executedChecks": executed,
            "skippedChecks": skipped,
            "failedChecks": failed,
            "unresolvedRisks": skipped if self.release_blocked else [],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)

    def to_text(self) -> str:
        lines = [f"gate={self.gate_name}", f"releaseBlocked={str(self.release_blocked).lower()}"]
        for result in self.results:
            details = " ".join(f"{key}={value}" for key, value in sorted(result.status.details.items()))
            suffix = f" {details}" if details else ""
            lines.append(
                f"{result.status.outcome.value} {result.check_id} required={str(result.required).lower()} "
                f"message={result.status.message}{suffix}"
            )
        return "\n".join(lines)


def run_gate(checks: Iterable[GateCheck], *, gate_name: str = "backend-release-gate") -> GateReport:
    results = tuple(
        GateCheckResult(
            check_id=check.check_id,
            label=check.label,
            required=check.required,
            status=check.run(),
        )
        for check in checks
    )
    return GateReport(gate_name=gate_name, results=results)


def pure_checks() -> tuple[GateCheck, ...]:
    return (
        GateCheck(
            check_id="scope_classification",
            label="Pure change scope classification",
            required=True,
            run=lambda: GateStatus.passed("pure scope does not require storage smoke"),
        ),
    )


def _sqlite_api(store_path: Path) -> SystemAPI:
    return SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(store_path)))


def run_sqlite_restart_recovery_smoke(
    store_path: Path,
    *,
    reload_api: Callable[[Path], SystemAPI] | None = None,
) -> GateStatus:
    try:
        first_api = _sqlite_api(store_path)
        subject_id = first_api.create_subject("Backend Gate Restart Subject")
        materials = first_api.list_subject_materials(subject_id)
        if not materials:
            return GateStatus.failed(
                "subject material relationship missing before restart",
                details={"boundary": "create", "subjectId": str(subject_id)},
            )
        material = materials[0]
        if material.scoped_project_id is None or material.internal_project_id is None:
            return GateStatus.failed(
                "subject material relationship is incomplete before restart",
                details={"boundary": "create", "subjectId": str(subject_id)},
            )

        reloaded_api = reload_api(store_path) if reload_api is not None else _sqlite_api(store_path)
        resolved_internal_project_id = reloaded_api.resolve_scoped_project_internal_key(subject_id, material.scoped_project_id)
        if str(resolved_internal_project_id) != str(material.internal_project_id):
            return GateStatus.failed(
                "restart relationship resolved to a different internal project",
                details={
                    "boundary": "restart",
                    "subjectId": str(subject_id),
                    "scopedProjectId": str(material.scoped_project_id),
                    "expectedInternalProjectId": str(material.internal_project_id),
                    "internalProjectId": str(resolved_internal_project_id),
                },
            )

        context = reloaded_api.get_scoped_subject_context_for_project(
            resolved_internal_project_id,
            public_project_id=material.scoped_project_id,
        )
        if str(context.get("current_internal_project_id")) != str(material.internal_project_id):
            return GateStatus.failed(
                "restart relationship did not reopen the same scoped workspace",
                details={
                    "boundary": "restart",
                    "subjectId": str(subject_id),
                    "scopedProjectId": str(material.scoped_project_id),
                    "internalProjectId": str(material.internal_project_id),
                },
            )

        return GateStatus.passed(
            "restart relationship recovered and workspace reopened",
            details={
                "boundary": "restart",
                "subjectId": str(subject_id),
                "scopedProjectId": str(material.scoped_project_id),
                "internalProjectId": str(material.internal_project_id),
            },
        )
    except Exception as exc:
        return GateStatus.failed(
            f"restart relationship check failed: {exc}",
            details={"boundary": "restart", "errorType": type(exc).__name__},
        )


def sqlite_restart_recovery_check(store_path: Path) -> GateCheck:
    return GateCheck(
        check_id="restart_recovery",
        label="SQLite restart recovery smoke",
        required=True,
        run=lambda: run_sqlite_restart_recovery_smoke(store_path),
    )


def _default_postgres_dsn() -> str | None:
    for env_name in ("LEARNINGPYRAMID_TEST_POSTGRES_DSN", "LEARNINGPYRAMID_STORE_POSTGRES_DSN", "LEARNINGPYRAMID_POSTGRES_DSN"):
        value = os.getenv(env_name, "").strip()
        if value:
            return value
    return None


def run_postgres_workspace_restart_smoke(dsn: str) -> dict[str, object]:
    first_api = SystemAPI(InMemorySystem(persist_store=PostgresStore(dsn)))
    subject_id = first_api.create_subject("Backend Gate PostgreSQL Subject")
    material = first_api.list_subject_materials(subject_id)[0]
    if material.scoped_project_id is None or material.internal_project_id is None:
        raise RuntimeError("created subject material relationship is incomplete")

    reloaded_api = SystemAPI(InMemorySystem(persist_store=PostgresStore(dsn)))
    resolved_internal_project_id = reloaded_api.resolve_scoped_project_internal_key(subject_id, material.scoped_project_id)
    if str(resolved_internal_project_id) != str(material.internal_project_id):
        raise RuntimeError("PostgreSQL restart resolved a different internal project")
    context = reloaded_api.get_scoped_subject_context_for_project(
        resolved_internal_project_id,
        public_project_id=material.scoped_project_id,
    )
    if str(context.get("current_internal_project_id")) != str(material.internal_project_id):
        raise RuntimeError("PostgreSQL restart did not reopen the same scoped workspace")

    return {
        "subjectId": str(subject_id),
        "scopedProjectId": str(material.scoped_project_id),
        "internalProjectId": str(material.internal_project_id),
    }


def run_postgres_storage_smoke(
    dsn: str,
    *,
    smoke_runner: Callable[[str], Mapping[str, object]] | None = None,
) -> GateStatus:
    try:
        payload = dict((smoke_runner or run_postgres_workspace_restart_smoke)(dsn))
        return GateStatus.passed(
            "PostgreSQL storage smoke passed",
            details={"boundary": "storage", **payload},
        )
    except Exception as exc:
        return GateStatus.failed(
            f"PostgreSQL storage smoke failed: {exc}",
            details={"boundary": "storage", "errorType": type(exc).__name__},
        )


def postgres_storage_check(
    dsn: str | None = None,
    *,
    smoke_runner: Callable[[str], Mapping[str, object]] | None = None,
) -> GateCheck:
    resolved_dsn = str(dsn or _default_postgres_dsn() or "").strip()

    def _run() -> GateStatus:
        if not resolved_dsn:
            return GateStatus.skipped(
                "PostgreSQL DSN is required for storage scope",
                details={"boundary": "storage", "env": "LEARNINGPYRAMID_TEST_POSTGRES_DSN"},
            )
        return run_postgres_storage_smoke(resolved_dsn, smoke_runner=smoke_runner)

    return GateCheck(
        check_id="postgres_storage_smoke",
        label="PostgreSQL storage and migration smoke",
        required=True,
        run=_run,
    )


def run_identity_boundary_smoke(
    *,
    route_checker: Callable[[], list[str]],
    backend_boundary_checker: Callable[[], list[str]],
    scoped_id_checker: Callable[[], Mapping[str, object]],
) -> GateStatus:
    try:
        route_issues = list(route_checker())
        backend_boundary_issues = list(backend_boundary_checker())
        scoped_report = dict(scoped_id_checker())
        duplicate_scoped_ids = list(scoped_report.get("duplicateScopedProjectIds") or [])
        blocking_issues = list(scoped_report.get("blockingIssues") or [])
        projects_verified = int(scoped_report.get("projectsVerified", 0) or 0)
        if projects_verified <= 0:
            blocking_issues.append("no scoped project identity sample was verified")
        details = {
            "boundary": "identity",
            "diagnosticFields": "subjectId,scopedProjectId,internalProjectId",
            "routeIssues": route_issues,
            "backendBoundaryIssues": backend_boundary_issues,
            "duplicateScopedProjectIds": duplicate_scoped_ids,
            "blockingIssues": blocking_issues,
            "projectsVerified": projects_verified,
        }
        if route_issues or backend_boundary_issues or duplicate_scoped_ids or blocking_issues:
            return GateStatus.failed("identity boundary check failed", details=details)
        return GateStatus.passed("identity boundary diagnostics verified", details=details)
    except Exception as exc:
        return GateStatus.failed(
            f"identity boundary check failed: {exc}",
            details={"boundary": "identity", "errorType": type(exc).__name__},
        )


def identity_boundary_check(
    *,
    route_checker: Callable[[], list[str]],
    backend_boundary_checker: Callable[[], list[str]],
    scoped_id_checker: Callable[[], Mapping[str, object]],
) -> GateCheck:
    return GateCheck(
        check_id="identity_boundary",
        label="Scoped identity boundary and diagnostics",
        required=True,
        run=lambda: run_identity_boundary_smoke(
            route_checker=route_checker,
            backend_boundary_checker=backend_boundary_checker,
            scoped_id_checker=scoped_id_checker,
        ),
    )

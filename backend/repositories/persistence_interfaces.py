from dataclasses import dataclass
from typing import Any, Optional, Protocol, Sequence

from backend.models.aggregation_queue import AggregationQueue
from backend.models.audit_log_event import AuditLogEvent
from backend.models.layer import Layer
from backend.models.project import Project
from backend.models.project_config import ProjectConfig
from backend.models.project_material_source_binding import ProjectMaterialSourceBinding
from backend.models.project_storage_config import ProjectStorageConfig
from backend.models.review_task_queue import ReviewTaskQueue


@dataclass(frozen=True, slots=True)
class SystemStateRecord:
    schema_version: int
    idgen_counters: dict[str, Any]
    updated_at: str


@dataclass(frozen=True, slots=True)
class ProjectSnapshotRecord:
    project_id: str
    project_title: str
    project_state: str
    created_at_ms: int
    deleted_at_ms: int | None
    subject_id: str | None
    scoped_project_id: str | None
    project_sequence: int
    updated_at: str


@dataclass(frozen=True, slots=True)
class SubjectMaterialCollectionRecord:
    subject_id: str
    initialized: bool
    updated_at: str


@dataclass(frozen=True, slots=True)
class SubjectMaterialRelationshipRecord:
    subject_id: str
    material_id: str
    material_type: str
    title: str
    created_at_ms: int
    scoped_project_id: str
    internal_project_id: str
    updated_at: str


class SqlMutationSession(Protocol):
    project_id: str | None
    raw_connection: Any

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class SqlSystemStateRepository(Protocol):
    def get(self, session: SqlMutationSession) -> Optional[SystemStateRecord]: ...

    def upsert(self, session: SqlMutationSession, state: SystemStateRecord) -> None: ...


class SqlProjectSnapshotRepository(Protocol):
    def get(self, session: SqlMutationSession, project_id: str) -> Optional[ProjectSnapshotRecord]: ...

    def all(self, session: SqlMutationSession) -> Sequence[ProjectSnapshotRecord]: ...

    def upsert(self, session: SqlMutationSession, record: ProjectSnapshotRecord) -> None: ...

    def delete_absent(self, session: SqlMutationSession, keep_project_ids: Sequence[str]) -> None: ...


class SqlSubjectMaterialRelationshipRepository(Protocol):
    def delete_for_subject(self, session: SqlMutationSession, subject_id: str) -> None: ...

    def upsert_collection(self, session: SqlMutationSession, record: SubjectMaterialCollectionRecord) -> None: ...

    def insert_relationships(
        self,
        session: SqlMutationSession,
        records: Sequence[SubjectMaterialRelationshipRecord],
    ) -> None: ...

    def get_collection(self, session: SqlMutationSession, subject_id: str) -> Optional[SubjectMaterialCollectionRecord]: ...

    def list_for_subject(self, session: SqlMutationSession, subject_id: str) -> Sequence[SubjectMaterialRelationshipRecord]: ...

    def get_by_internal_project(
        self,
        session: SqlMutationSession,
        internal_project_id: str,
    ) -> Optional[SubjectMaterialRelationshipRecord]: ...


class SqlLifecycleRepository(Protocol):
    def create_bootstrap(
        self,
        session: SqlMutationSession,
        *,
        project: Project,
        project_snapshot: dict[str, Any],
        project_storage_config: ProjectStorageConfig,
        project_material_source_binding: ProjectMaterialSourceBinding,
        project_config: ProjectConfig,
        review_task_queue: ReviewTaskQueue,
        layers: Sequence[Layer],
        aggregation_queues: Sequence[AggregationQueue],
        audit_events: Sequence[AuditLogEvent],
        updated_at: str,
    ) -> None: ...

    def replace_with_deleted_tombstone(
        self,
        session: SqlMutationSession,
        *,
        project: Project,
        project_snapshot: dict[str, Any],
        audit_events: Sequence[AuditLogEvent],
        updated_at: str,
    ) -> None: ...


class SqlUnitOfWork(Protocol):
    session: SqlMutationSession
    system_state: SqlSystemStateRepository
    project_snapshots: SqlProjectSnapshotRepository
    subject_material_relationships: SqlSubjectMaterialRelationshipRepository
    project_lifecycle: SqlLifecycleRepository

    def __enter__(self) -> "SqlUnitOfWork": ...

    def __exit__(self, exc_type, exc, tb) -> bool | None: ...


PersistenceMutationSession = SqlMutationSession
SystemStateRepository = SqlSystemStateRepository
ProjectSnapshotRepository = SqlProjectSnapshotRepository
SubjectMaterialRelationshipRepository = SqlSubjectMaterialRelationshipRepository
ProjectLifecycleRepository = SqlLifecycleRepository
PersistenceUnitOfWork = SqlUnitOfWork

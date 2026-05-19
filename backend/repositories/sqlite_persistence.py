import json
import sqlite3
import threading
from dataclasses import dataclass
from typing import Callable, Sequence

from backend.models.aggregation_queue import AggregationQueue
from backend.models.audit_log_event import AuditLogEvent
from backend.models.errors import NotFound, PreconditionFailure
from backend.models.layer import Layer
from backend.models.project import Project
from backend.models.project_config import ProjectConfig
from backend.models.project_material_source_binding import ProjectMaterialSourceBinding
from backend.models.project_storage_config import ProjectStorageConfig
from backend.models.review_task_queue import ReviewTaskQueue
from backend.repositories.persistence_interfaces import (
    ProjectSnapshotRecord,
    SubjectMaterialCollectionRecord,
    SubjectMaterialRelationshipRecord,
    SqlLifecycleRepository,
    SqlProjectSnapshotRepository,
    SqlSubjectMaterialRelationshipRepository,
    SqlSystemStateRepository,
    SqlUnitOfWork,
    SystemStateRecord,
)
from backend.system.persistence_json import (
    encode_project_config_payload,
    encode_project_material_source_binding_payload,
    encode_project_storage_config_payload,
    encode_timestamp_ms,
)


@dataclass
class SQLitePersistenceSession:
    raw_connection: sqlite3.Connection
    project_id: str | None = None
    _closed: bool = False

    def commit(self) -> None:
        if self._closed:
            return
        self.raw_connection.commit()
        self._closed = True

    def rollback(self) -> None:
        if self._closed:
            return
        self.raw_connection.rollback()
        self._closed = True

    @property
    def is_open(self) -> bool:
        return not self._closed


class SQLiteSystemStateRepository(SqlSystemStateRepository):
    def get(self, session: SQLitePersistenceSession) -> SystemStateRecord | None:
        row = session.raw_connection.execute(
            "SELECT schema_version, idgen_counters_json, updated_at FROM system_state WHERE slot = 1"
        ).fetchone()
        if row is None:
            return None
        raw_counters = json.loads(str(row["idgen_counters_json"]))
        counters = dict(raw_counters) if isinstance(raw_counters, dict) else {}
        return SystemStateRecord(
            schema_version=int(row["schema_version"]),
            idgen_counters=counters,
            updated_at=str(row["updated_at"]),
        )

    def upsert(self, session: SQLitePersistenceSession, state: SystemStateRecord) -> None:
        session.raw_connection.execute(
            """
            INSERT INTO system_state (slot, schema_version, idgen_counters_json, updated_at)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(slot) DO UPDATE SET
                schema_version = excluded.schema_version,
                idgen_counters_json = excluded.idgen_counters_json,
                updated_at = excluded.updated_at
            """,
            (
                int(state.schema_version),
                json.dumps(state.idgen_counters, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                str(state.updated_at),
            ),
        )


class SQLiteProjectSnapshotRepository(SqlProjectSnapshotRepository):
    def get(self, session: SQLitePersistenceSession, project_id: str) -> ProjectSnapshotRecord | None:
        row = session.raw_connection.execute(
            """
            SELECT project_id, project_title, project_state, created_at_ms, deleted_at_ms,
                   subject_id, scoped_project_id, project_sequence, updated_at
            FROM project_snapshots
            WHERE project_id = ?
            """,
            (str(project_id),),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def all(self, session: SQLitePersistenceSession) -> tuple[ProjectSnapshotRecord, ...]:
        rows = session.raw_connection.execute(
            """
            SELECT project_id, project_title, project_state, created_at_ms, deleted_at_ms,
                   subject_id, scoped_project_id, project_sequence, updated_at
            FROM project_snapshots
            ORDER BY project_id ASC
            """
        ).fetchall()
        return tuple(self._row_to_record(row) for row in rows)

    def upsert(self, session: SQLitePersistenceSession, record: ProjectSnapshotRecord) -> None:
        session.raw_connection.execute(
            """
            INSERT INTO project_snapshots (
                project_id,
                project_title,
                project_state,
                created_at_ms,
                deleted_at_ms,
                subject_id,
                scoped_project_id,
                project_sequence,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(project_id) DO UPDATE SET
                project_title = excluded.project_title,
                project_state = excluded.project_state,
                created_at_ms = excluded.created_at_ms,
                deleted_at_ms = excluded.deleted_at_ms,
                subject_id = excluded.subject_id,
                scoped_project_id = excluded.scoped_project_id,
                project_sequence = excluded.project_sequence,
                updated_at = excluded.updated_at
            """,
            (
                str(record.project_id),
                str(record.project_title),
                str(record.project_state),
                int(record.created_at_ms),
                None if record.deleted_at_ms is None else int(record.deleted_at_ms),
                None if record.subject_id is None else str(record.subject_id),
                None if record.scoped_project_id is None else str(record.scoped_project_id),
                int(record.project_sequence),
                str(record.updated_at),
            ),
        )

    def delete_absent(self, session: SQLitePersistenceSession, keep_project_ids: Sequence[str]) -> None:
        keep_ids = tuple(sorted(str(project_id) for project_id in keep_project_ids))
        if keep_ids:
            placeholders = ",".join("?" for _ in keep_ids)
            session.raw_connection.execute(
                f"DELETE FROM project_snapshots WHERE project_id NOT IN ({placeholders})",
                keep_ids,
            )
            return
        session.raw_connection.execute("DELETE FROM project_snapshots")

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ProjectSnapshotRecord:
        return ProjectSnapshotRecord(
            project_id=str(row["project_id"]),
            project_title=str(row["project_title"]),
            project_state=str(row["project_state"]),
            created_at_ms=int(row["created_at_ms"]),
            deleted_at_ms=None if row["deleted_at_ms"] is None else int(row["deleted_at_ms"]),
            subject_id=None if row["subject_id"] is None else str(row["subject_id"]),
            scoped_project_id=None if row["scoped_project_id"] is None else str(row["scoped_project_id"]),
            project_sequence=int(row["project_sequence"] or 0),
            updated_at=str(row["updated_at"]),
        )


class SQLiteSubjectMaterialRelationshipRepository(SqlSubjectMaterialRelationshipRepository):
    def delete_for_subject(self, session: SQLitePersistenceSession, subject_id: str) -> None:
        session.raw_connection.execute("DELETE FROM subject_material_relationship_index WHERE subject_id = ?", (str(subject_id),))
        session.raw_connection.execute("DELETE FROM subject_material_collection_index WHERE subject_id = ?", (str(subject_id),))

    def upsert_collection(self, session: SQLitePersistenceSession, record: SubjectMaterialCollectionRecord) -> None:
        session.raw_connection.execute(
            """
            INSERT INTO subject_material_collection_index (
                subject_id,
                initialized,
                updated_at
            )
            VALUES (?, ?, ?)
            ON CONFLICT(subject_id) DO UPDATE SET
                initialized = excluded.initialized,
                updated_at = excluded.updated_at
            """,
            (
                str(record.subject_id),
                1 if record.initialized else 0,
                str(record.updated_at),
            ),
        )

    def insert_relationships(
        self,
        session: SQLitePersistenceSession,
        records: Sequence[SubjectMaterialRelationshipRecord],
    ) -> None:
        for record in records:
            session.raw_connection.execute(
                """
                INSERT INTO subject_material_relationship_index (
                    subject_id,
                    material_id,
                    material_type,
                    title,
                    created_at_ms,
                    scoped_project_id,
                    internal_project_id,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record.subject_id),
                    str(record.material_id),
                    str(record.material_type),
                    str(record.title),
                    int(record.created_at_ms),
                    str(record.scoped_project_id),
                    str(record.internal_project_id),
                    str(record.updated_at),
                ),
            )

    def get_collection(self, session: SQLitePersistenceSession, subject_id: str) -> SubjectMaterialCollectionRecord | None:
        row = session.raw_connection.execute(
            """
            SELECT subject_id, initialized, updated_at
            FROM subject_material_collection_index
            WHERE subject_id = ?
            """,
            (str(subject_id),),
        ).fetchone()
        return None if row is None else self._collection_row_to_record(row)

    def list_for_subject(self, session: SQLitePersistenceSession, subject_id: str) -> tuple[SubjectMaterialRelationshipRecord, ...]:
        rows = session.raw_connection.execute(
            """
            SELECT subject_id, material_id, material_type, title, created_at_ms, scoped_project_id, internal_project_id, updated_at
            FROM subject_material_relationship_index
            WHERE subject_id = ?
            ORDER BY created_at_ms ASC, material_id ASC
            """,
            (str(subject_id),),
        ).fetchall()
        return tuple(self._relationship_row_to_record(row) for row in rows)

    def get_by_internal_project(
        self,
        session: SQLitePersistenceSession,
        internal_project_id: str,
    ) -> SubjectMaterialRelationshipRecord | None:
        row = session.raw_connection.execute(
            """
            SELECT subject_id, material_id, material_type, title, created_at_ms, scoped_project_id, internal_project_id, updated_at
            FROM subject_material_relationship_index
            WHERE internal_project_id = ?
            """,
            (str(internal_project_id),),
        ).fetchone()
        return None if row is None else self._relationship_row_to_record(row)

    @staticmethod
    def _collection_row_to_record(row: sqlite3.Row) -> SubjectMaterialCollectionRecord:
        return SubjectMaterialCollectionRecord(
            subject_id=str(row["subject_id"]),
            initialized=bool(int(row["initialized"])),
            updated_at=str(row["updated_at"]),
        )

    @staticmethod
    def _relationship_row_to_record(row: sqlite3.Row) -> SubjectMaterialRelationshipRecord:
        return SubjectMaterialRelationshipRecord(
            subject_id=str(row["subject_id"]),
            material_id=str(row["material_id"]),
            material_type=str(row["material_type"]),
            title=str(row["title"]),
            created_at_ms=int(row["created_at_ms"]),
            scoped_project_id=str(row["scoped_project_id"]),
            internal_project_id=str(row["internal_project_id"]),
            updated_at=str(row["updated_at"]),
        )


class SQLiteProjectLifecycleRepository(SqlLifecycleRepository):
    _PROJECT_SCOPED_TABLES: tuple[str, ...] = (
        "project_storage_config_index",
        "project_material_source_binding_index",
        "project_config_index",
        "instance_index",
        "instance_media_binding_index",
        "video_watch_progress_index",
        "learning_object_node_index",
        "recall_point_index",
        "learning_task_index",
        "learning_task_node_index",
        "entry_registration_index",
        "range_snapshot_index",
        "review_task_index",
        "convergence_index",
        "review_chain_index",
        "review_task_queue_index",
        "layer_state_index",
        "audit_log_event_index",
        "asr_artifact_index",
        "aggregation_queue_index",
        "aggregation_event_index",
        "material_allowlist_index",
        "media_asset_index",
        "recall_point_review_record_index",
    )

    def create_bootstrap(
        self,
        session: SQLitePersistenceSession,
        *,
        project: Project,
        project_snapshot: dict[str, object],
        project_storage_config: ProjectStorageConfig,
        project_material_source_binding: ProjectMaterialSourceBinding,
        project_config: ProjectConfig,
        review_task_queue: ReviewTaskQueue,
        layers: Sequence[Layer],
        aggregation_queues: Sequence[AggregationQueue],
        audit_events: Sequence[AuditLogEvent],
        updated_at: str,
    ) -> None:
        existing = session.raw_connection.execute(
            "SELECT 1 FROM project_snapshots WHERE project_id = ?",
            (str(project.project_id),),
        ).fetchone()
        if existing is not None:
            raise PreconditionFailure("project_id already exists")

        self._upsert_project_snapshot(
            session,
            project=project,
            project_snapshot=project_snapshot,
            updated_at=updated_at,
        )
        self._replace_project_config(
            session,
            project_storage_config=project_storage_config,
            project_material_source_binding=project_material_source_binding,
            project_config=project_config,
        )
        self._replace_review_task_queue(session, review_task_queue)
        self._replace_layers(session, layers=layers)
        self._replace_aggregation_queues(session, aggregation_queues=aggregation_queues)
        self._replace_audit_events(session, project_id=str(project.project_id), audit_events=audit_events)

    def replace_with_deleted_tombstone(
        self,
        session: SQLitePersistenceSession,
        *,
        project: Project,
        project_snapshot: dict[str, object],
        audit_events: Sequence[AuditLogEvent],
        updated_at: str,
    ) -> None:
        row = session.raw_connection.execute(
            "SELECT project_state FROM project_snapshots WHERE project_id = ?",
            (str(project.project_id),),
        ).fetchone()
        if row is None:
            raise NotFound(project.project_id)
        if str(row["project_state"]) != "ACTIVE":
            raise PreconditionFailure("Project must be ACTIVE to delete")

        self._upsert_project_snapshot(
            session,
            project=project,
            project_snapshot=project_snapshot,
            updated_at=updated_at,
        )
        self._clear_project_scope(session, str(project.project_id))
        self._replace_audit_events(session, project_id=str(project.project_id), audit_events=audit_events)

    def _clear_project_scope(self, session: SQLitePersistenceSession, project_id: str) -> None:
        for table_name in self._PROJECT_SCOPED_TABLES:
            session.raw_connection.execute(f"DELETE FROM {table_name} WHERE project_id = ?", (str(project_id),))

    def _upsert_project_snapshot(
        self,
        session: SQLitePersistenceSession,
        *,
        project: Project,
        project_snapshot: dict[str, object],
        updated_at: str,
    ) -> None:
        snapshot_record = ProjectSnapshotRecord(
            project_id=str(project.project_id),
            project_title=str(project.title),
            project_state=str(project.state.value),
            created_at_ms=encode_timestamp_ms(project.created_at),
            deleted_at_ms=None if project.deleted_at is None else encode_timestamp_ms(project.deleted_at),
            subject_id=None if project.subject_id is None else str(project.subject_id),
            scoped_project_id=None if project.scoped_project_id is None else str(project.scoped_project_id),
            project_sequence=int(project.project_sequence),
            updated_at=str(updated_at),
        )
        SQLiteProjectSnapshotRepository().upsert(session, snapshot_record)

    def _replace_project_config(
        self,
        session: SQLitePersistenceSession,
        *,
        project_storage_config: ProjectStorageConfig,
        project_material_source_binding: ProjectMaterialSourceBinding,
        project_config: ProjectConfig,
    ) -> None:
        project_id = str(project_storage_config.project_id)
        session.raw_connection.execute("DELETE FROM project_storage_config_index WHERE project_id = ?", (project_id,))
        session.raw_connection.execute("DELETE FROM project_material_source_binding_index WHERE project_id = ?", (project_id,))
        session.raw_connection.execute("DELETE FROM project_config_index WHERE project_id = ?", (project_id,))

        storage_payload = encode_project_storage_config_payload(project_storage_config)
        session.raw_connection.execute(
            """
            INSERT INTO project_storage_config_index (
                project_id,
                project_root,
                learning_object_root,
                fs_sync_policy,
                updated_at_ms
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                project_id,
                str(storage_payload["projectRoot"]),
                str(storage_payload["learningObjectRoot"]),
                str(storage_payload["fsSyncPolicy"]),
                int(storage_payload["updatedAtMs"]),
            ),
        )

        binding_payload = encode_project_material_source_binding_payload(project_material_source_binding)
        session.raw_connection.execute(
            """
            INSERT INTO project_material_source_binding_index (
                project_id,
                source_kind,
                source_root_label,
                updated_at_ms
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                project_id,
                str(binding_payload["sourceKind"]),
                None if binding_payload["sourceRootLabel"] is None else str(binding_payload["sourceRootLabel"]),
                int(binding_payload["updatedAtMs"]),
            ),
        )

        config_payload = encode_project_config_payload(project_config)
        session.raw_connection.execute(
            """
            INSERT INTO project_config_index (
                project_id,
                updated_at_ms,
                config_json
            )
            VALUES (?, ?, ?)
            """,
            (
                project_id,
                int(config_payload["updatedAtMs"]),
                json.dumps(config_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
            ),
        )

    def _replace_review_task_queue(
        self,
        session: SQLitePersistenceSession,
        review_task_queue: ReviewTaskQueue,
    ) -> None:
        project_id = str(review_task_queue.project_id)
        session.raw_connection.execute("DELETE FROM review_task_queue_index WHERE project_id = ?", (project_id,))
        session.raw_connection.execute(
            """
            INSERT INTO review_task_queue_index (
                project_id,
                queue_id,
                review_task_ids_json,
                head_index
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                project_id,
                str(review_task_queue.queue_id),
                json.dumps(
                    [str(review_task_id) for review_task_id in review_task_queue.review_task_ids],
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ),
                int(review_task_queue.head_index),
            ),
        )

    def _replace_layers(self, session: SQLitePersistenceSession, *, layers: Sequence[Layer]) -> None:
        if not layers:
            return
        project_id = str(layers[0].project_id)
        session.raw_connection.execute("DELETE FROM layer_state_index WHERE project_id = ?", (project_id,))
        for layer in layers:
            session.raw_connection.execute(
                """
                INSERT INTO layer_state_index (
                    project_id,
                    layer_id,
                    layer_index,
                    layer_mode,
                    orchestrator_managed_review_chain_ids_json,
                    aggregation_k_node,
                    aggregation_k_point,
                    aggregation_cycle_state,
                    pending_roll_up_parent_node_id,
                    normal_tick_quota_remaining
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(layer.project_id),
                    str(layer.layer_id),
                    int(layer.layer_index),
                    str(layer.layer_mode.value),
                    json.dumps(
                        [str(chain_id) for chain_id in layer.orchestrator_managed_review_chain_ids],
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    int(layer.aggregation_k_node),
                    int(layer.aggregation_k_point),
                    str(layer.aggregation_cycle_state.value),
                    None if layer.pending_roll_up_parent_node_id is None else str(layer.pending_roll_up_parent_node_id),
                    int(layer.normal_tick_quota_remaining),
                ),
            )

    def _replace_aggregation_queues(
        self,
        session: SQLitePersistenceSession,
        *,
        aggregation_queues: Sequence[AggregationQueue],
    ) -> None:
        if not aggregation_queues:
            return
        project_id = str(aggregation_queues[0].project_id)
        session.raw_connection.execute("DELETE FROM aggregation_queue_index WHERE project_id = ?", (project_id,))
        for aggregation_queue in aggregation_queues:
            session.raw_connection.execute(
                """
                INSERT INTO aggregation_queue_index (
                    project_id,
                    layer_index,
                    node_ids_json,
                    head_index
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    str(aggregation_queue.project_id),
                    int(aggregation_queue.layer_index),
                    json.dumps(
                        [str(node_id) for node_id in aggregation_queue.node_ids],
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    int(aggregation_queue.head_index),
                ),
            )

    def _replace_audit_events(
        self,
        session: SQLitePersistenceSession,
        *,
        project_id: str,
        audit_events: Sequence[AuditLogEvent],
    ) -> None:
        session.raw_connection.execute("DELETE FROM audit_log_event_index WHERE project_id = ?", (str(project_id),))
        for audit_event in audit_events:
            session.raw_connection.execute(
                """
                INSERT INTO audit_log_event_index (
                    project_id,
                    event_id,
                    occurred_at_ms,
                    kind,
                    api_name,
                    result,
                    payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(audit_event.project_id),
                    str(audit_event.event_id),
                    encode_timestamp_ms(audit_event.occurred_at),
                    str(audit_event.kind.value),
                    str(audit_event.api_name),
                    str(audit_event.result.value),
                    str(audit_event.payload),
                ),
            )


class SQLitePersistenceUnitOfWork(SqlUnitOfWork):
    def __init__(
        self,
        *,
        connect: Callable[[], sqlite3.Connection],
        lock: threading.RLock,
        project_id: str | None = None,
    ) -> None:
        self._connect = connect
        self._lock = lock
        self._project_id = project_id
        self._connection: sqlite3.Connection | None = None
        self.session: SQLitePersistenceSession
        self.system_state = SQLiteSystemStateRepository()
        self.project_snapshots = SQLiteProjectSnapshotRepository()
        self.subject_material_relationships = SQLiteSubjectMaterialRelationshipRepository()
        self.project_lifecycle = SQLiteProjectLifecycleRepository()

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("SQLitePersistenceUnitOfWork is not open")
        return self._connection

    def __enter__(self) -> "SQLitePersistenceUnitOfWork":
        self._lock.acquire()
        try:
            self._connection = self._connect()
            self._connection.execute("BEGIN IMMEDIATE")
            self.session = SQLitePersistenceSession(raw_connection=self._connection, project_id=self._project_id)
            return self
        except Exception:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
            self._lock.release()
            raise

    def __exit__(self, exc_type, exc, tb) -> bool | None:
        try:
            if self._connection is None:
                return None
            if exc_type is None:
                self.session.commit()
            else:
                self.session.rollback()
        finally:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
            self._lock.release()
        return None

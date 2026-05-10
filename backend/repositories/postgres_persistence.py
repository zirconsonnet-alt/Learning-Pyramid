import re
from dataclasses import dataclass
from typing import Any, Callable

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
    SqlLifecycleRepository,
    SqlProjectSnapshotRepository,
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
from backend.system.postgres_runtime import get_postgres_pool


def _translate_placeholders(sql: str) -> str:
    out: list[str] = []
    index = 0
    in_single_quote = False
    while index < len(sql):
        ch = sql[index]
        if ch == "'":
            out.append(ch)
            if in_single_quote and index + 1 < len(sql) and sql[index + 1] == "'":
                out.append("'")
                index += 2
                continue
            in_single_quote = not in_single_quote
            index += 1
            continue
        if ch == "?" and not in_single_quote:
            out.append("%s")
            index += 1
            continue
        out.append(ch)
        index += 1
    return "".join(out)


def translate_sql_for_postgres(sql: str) -> str | None:
    text = str(sql)
    if text.strip().upper().startswith("PRAGMA "):
        return None

    translated = _translate_placeholders(text)
    translated = re.sub(r"\bBEGIN\s+IMMEDIATE\b", "BEGIN", translated, flags=re.IGNORECASE)

    if re.match(r"^\s*(CREATE\s+TABLE|ALTER\s+TABLE)\b", translated, flags=re.IGNORECASE):
        translated = re.sub(r"\bINTEGER\b", "BIGINT", translated, flags=re.IGNORECASE)

    return translated


class _EmptyCursor:
    def fetchone(self) -> None:
        return None

    def fetchall(self) -> list[Any]:
        return []


class PostgresSqlCursor:
    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor

    def fetchone(self) -> Any:
        return self._cursor.fetchone()

    def fetchall(self) -> list[Any]:
        return list(self._cursor.fetchall())


class PostgresSqlConnection:
    def __init__(self, connection: Any, *, close_callback: Callable[[Any], None] | None = None) -> None:
        self._connection = connection
        self._close_callback = close_callback
        self._closed = False

    def execute(self, sql: str, params: tuple[Any, ...] | list[Any] | None = None) -> PostgresSqlCursor | _EmptyCursor:
        translated = translate_sql_for_postgres(sql)
        if translated is None:
            return _EmptyCursor()
        values = tuple(params or ())
        cursor = self._connection.execute(translated, values)
        return PostgresSqlCursor(cursor)

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._close_callback is not None:
            self._close_callback(self._connection)
            return
        self._connection.close()


@dataclass
class PostgresPersistenceSession:
    raw_connection: PostgresSqlConnection
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


class PostgresSystemStateRepository(SqlSystemStateRepository):
    def get(self, session: PostgresPersistenceSession) -> SystemStateRecord | None:
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

    def upsert(self, session: PostgresPersistenceSession, state: SystemStateRecord) -> None:
        session.raw_connection.execute(
            """
            INSERT INTO system_state (slot, schema_version, idgen_counters_json, updated_at)
            VALUES (1, %s, %s, %s)
            ON CONFLICT(slot) DO UPDATE SET
                schema_version = EXCLUDED.schema_version,
                idgen_counters_json = EXCLUDED.idgen_counters_json,
                updated_at = EXCLUDED.updated_at
            """,
            (
                int(state.schema_version),
                _json_dump(state.idgen_counters),
                str(state.updated_at),
            ),
        )


class PostgresProjectSnapshotRepository(SqlProjectSnapshotRepository):
    def get(self, session: PostgresPersistenceSession, project_id: str) -> ProjectSnapshotRecord | None:
        row = session.raw_connection.execute(
            """
            SELECT project_id, project_title, project_state, created_at_ms, deleted_at_ms,
                   subject_id, scoped_project_id, project_sequence, updated_at
            FROM project_snapshots
            WHERE project_id = %s
            """,
            (str(project_id),),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def all(self, session: PostgresPersistenceSession) -> tuple[ProjectSnapshotRecord, ...]:
        rows = session.raw_connection.execute(
            """
            SELECT project_id, project_title, project_state, created_at_ms, deleted_at_ms,
                   subject_id, scoped_project_id, project_sequence, updated_at
            FROM project_snapshots
            ORDER BY project_id ASC
            """
        ).fetchall()
        return tuple(self._row_to_record(row) for row in rows)

    def upsert(self, session: PostgresPersistenceSession, record: ProjectSnapshotRecord) -> None:
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
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(project_id) DO UPDATE SET
                project_title = EXCLUDED.project_title,
                project_state = EXCLUDED.project_state,
                created_at_ms = EXCLUDED.created_at_ms,
                deleted_at_ms = EXCLUDED.deleted_at_ms,
                subject_id = EXCLUDED.subject_id,
                scoped_project_id = EXCLUDED.scoped_project_id,
                project_sequence = EXCLUDED.project_sequence,
                updated_at = EXCLUDED.updated_at
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

    def delete_absent(self, session: PostgresPersistenceSession, keep_project_ids: tuple[str, ...] | list[str]) -> None:
        keep_ids = tuple(sorted(str(project_id) for project_id in keep_project_ids))
        if not keep_ids:
            session.raw_connection.execute("DELETE FROM project_snapshots")
            return
        placeholders = ", ".join("%s" for _ in keep_ids)
        session.raw_connection.execute(
            f"DELETE FROM project_snapshots WHERE project_id NOT IN ({placeholders})",
            keep_ids,
        )

    @staticmethod
    def _row_to_record(row: Any) -> ProjectSnapshotRecord:
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


class PostgresLifecycleRepository(SqlLifecycleRepository):
    _PROJECT_SCOPED_TABLES: tuple[str, ...] = (
        "project_storage_config_index",
        "project_material_source_binding_index",
        "project_config_index",
        "instance_index",
        "instance_media_binding_index",
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
        session: PostgresPersistenceSession,
        *,
        project: Project,
        project_snapshot: dict[str, Any],
        project_storage_config: ProjectStorageConfig,
        project_material_source_binding: ProjectMaterialSourceBinding,
        project_config: ProjectConfig,
        review_task_queue: ReviewTaskQueue,
        layers: tuple[Layer, ...] | list[Layer],
        aggregation_queues: tuple[AggregationQueue, ...] | list[AggregationQueue],
        audit_events: tuple[AuditLogEvent, ...] | list[AuditLogEvent],
        updated_at: str,
    ) -> None:
        existing = session.raw_connection.execute(
            "SELECT 1 FROM project_snapshots WHERE project_id = %s",
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
        session: PostgresPersistenceSession,
        *,
        project: Project,
        project_snapshot: dict[str, Any],
        audit_events: tuple[AuditLogEvent, ...] | list[AuditLogEvent],
        updated_at: str,
    ) -> None:
        row = session.raw_connection.execute(
            "SELECT project_state FROM project_snapshots WHERE project_id = %s",
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

    def _clear_project_scope(self, session: PostgresPersistenceSession, project_id: str) -> None:
        for table_name in self._PROJECT_SCOPED_TABLES:
            session.raw_connection.execute(f"DELETE FROM {table_name} WHERE project_id = %s", (str(project_id),))

    def _upsert_project_snapshot(
        self,
        session: PostgresPersistenceSession,
        *,
        project: Project,
        project_snapshot: dict[str, Any],
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
        PostgresProjectSnapshotRepository().upsert(session, snapshot_record)

    def _replace_project_config(
        self,
        session: PostgresPersistenceSession,
        *,
        project_storage_config: ProjectStorageConfig,
        project_material_source_binding: ProjectMaterialSourceBinding,
        project_config: ProjectConfig,
    ) -> None:
        project_id = str(project_storage_config.project_id)
        session.raw_connection.execute("DELETE FROM project_storage_config_index WHERE project_id = %s", (project_id,))
        session.raw_connection.execute("DELETE FROM project_material_source_binding_index WHERE project_id = %s", (project_id,))
        session.raw_connection.execute("DELETE FROM project_config_index WHERE project_id = %s", (project_id,))

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
            VALUES (%s, %s, %s, %s, %s)
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
            VALUES (%s, %s, %s, %s)
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
            VALUES (%s, %s, %s)
            """,
            (
                project_id,
                int(config_payload["updatedAtMs"]),
                _json_dump(config_payload),
            ),
        )

    def _replace_review_task_queue(self, session: PostgresPersistenceSession, review_task_queue: ReviewTaskQueue) -> None:
        project_id = str(review_task_queue.project_id)
        session.raw_connection.execute("DELETE FROM review_task_queue_index WHERE project_id = %s", (project_id,))
        session.raw_connection.execute(
            """
            INSERT INTO review_task_queue_index (
                project_id,
                queue_id,
                review_task_ids_json,
                head_index
            )
            VALUES (%s, %s, %s, %s)
            """,
            (
                project_id,
                str(review_task_queue.queue_id),
                _json_dump([str(review_task_id) for review_task_id in review_task_queue.review_task_ids]),
                int(review_task_queue.head_index),
            ),
        )

    def _replace_layers(self, session: PostgresPersistenceSession, *, layers: tuple[Layer, ...] | list[Layer]) -> None:
        if not layers:
            return
        project_id = str(layers[0].project_id)
        session.raw_connection.execute("DELETE FROM layer_state_index WHERE project_id = %s", (project_id,))
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
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    str(layer.project_id),
                    str(layer.layer_id),
                    int(layer.layer_index),
                    str(layer.layer_mode.value),
                    _json_dump([str(chain_id) for chain_id in layer.orchestrator_managed_review_chain_ids]),
                    int(layer.aggregation_k_node),
                    int(layer.aggregation_k_point),
                    str(layer.aggregation_cycle_state.value),
                    None if layer.pending_roll_up_parent_node_id is None else str(layer.pending_roll_up_parent_node_id),
                    int(layer.normal_tick_quota_remaining),
                ),
            )

    def _replace_aggregation_queues(
        self,
        session: PostgresPersistenceSession,
        *,
        aggregation_queues: tuple[AggregationQueue, ...] | list[AggregationQueue],
    ) -> None:
        if not aggregation_queues:
            return
        project_id = str(aggregation_queues[0].project_id)
        session.raw_connection.execute("DELETE FROM aggregation_queue_index WHERE project_id = %s", (project_id,))
        for aggregation_queue in aggregation_queues:
            session.raw_connection.execute(
                """
                INSERT INTO aggregation_queue_index (
                    project_id,
                    layer_index,
                    node_ids_json,
                    head_index
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    str(aggregation_queue.project_id),
                    int(aggregation_queue.layer_index),
                    _json_dump([str(node_id) for node_id in aggregation_queue.node_ids]),
                    int(aggregation_queue.head_index),
                ),
            )

    def _replace_audit_events(
        self,
        session: PostgresPersistenceSession,
        *,
        project_id: str,
        audit_events: tuple[AuditLogEvent, ...] | list[AuditLogEvent],
    ) -> None:
        session.raw_connection.execute("DELETE FROM audit_log_event_index WHERE project_id = %s", (str(project_id),))
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
                VALUES (%s, %s, %s, %s, %s, %s, %s)
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


class PostgresPersistenceUnitOfWork(SqlUnitOfWork):
    def __init__(self, *, connect: Callable[[], PostgresSqlConnection], project_id: str | None = None) -> None:
        self._connect = connect
        self._project_id = project_id
        self._connection: PostgresSqlConnection | None = None
        self.session: PostgresPersistenceSession
        self.system_state = PostgresSystemStateRepository()
        self.project_snapshots = PostgresProjectSnapshotRepository()
        self.project_lifecycle = PostgresLifecycleRepository()

    @property
    def connection(self) -> PostgresSqlConnection:
        if self._connection is None:
            raise RuntimeError("PostgresPersistenceUnitOfWork is not open")
        return self._connection

    def __enter__(self) -> "PostgresPersistenceUnitOfWork":
        self._connection = self._connect()
        try:
            self._connection.execute("BEGIN")
            self.session = PostgresPersistenceSession(raw_connection=self._connection, project_id=self._project_id)
            return self
        except Exception:
            self._connection.close()
            self._connection = None
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
        return None


PostgresUoW = PostgresPersistenceUnitOfWork


def connect_postgres(dsn: str) -> PostgresSqlConnection:
    pool = get_postgres_pool(str(dsn))
    connection = pool.acquire()
    return PostgresSqlConnection(connection, close_callback=pool.release)

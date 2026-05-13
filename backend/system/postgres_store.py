import json
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

from backend.models.aggregation_event import AggregationEvent
from backend.models.asr_artifact import AsrArtifact
from backend.models.audit_log_event import AuditLogEvent
from backend.models.entry_registration import EntryRegistration
from backend.models.enums import (
    InstancePresence,
    LearningTaskNodeOrigin,
    MaterialSourceKind,
    ProjectState,
    RecallPointState,
)
from backend.models.instance import Instance
from backend.models.instance_media_binding import InstanceMediaBinding
from backend.models.learning_object_node import LearningObjectContainer, LearningObjectLeaf, LearningObjectNode
from backend.models.learning_task import LearningTask
from backend.models.learning_task_node import LearningTaskNode
from backend.models.layer import Layer
from backend.models.project import Project
from backend.models.project_config import ProjectConfig
from backend.models.project_storage_config import ProjectStorageConfig
from backend.models.range_snapshot import RangeSnapshot
from backend.models.review_chain import ReviewChain
from backend.models.review_task import ReviewTask
from backend.models.convergence import Convergence
from backend.models.recall_point import RecallPoint
from backend.models.types import (
    AsrArtifactId,
    ConvergenceId,
    InstanceId,
    LearningObjectNodeId,
    LearningTaskId,
    LearningTaskNodeId,
    ProjectId,
    RangeId,
    RecallPointId,
    ReviewChainId,
    ReviewTaskId,
    id_canonical_text,
)
from backend.repositories.persistence_interfaces import SqlSubjectMaterialRelationshipRepository, SqlUnitOfWork, SystemStateRecord
from backend.repositories.postgres_persistence import (
    PostgresPersistenceSession,
    PostgresPersistenceUnitOfWork,
    PostgresSubjectMaterialRelationshipRepository,
    connect_postgres,
)
from backend.system.persistence_json import decode_project_config_payload, decode_project_storage_config_payload
from backend.system.postgres_runtime import get_postgres_pool, redact_postgres_dsn
from backend.system.postgres_schema import (
    apply_postgres_migrations,
    expected_postgres_migration_status,
    postgres_migration_status,
    validate_postgres_migration_plan,
)
from backend.system.persistence_store import SQLiteSnapshotStore


class PostgresStore(SQLiteSnapshotStore):
    def __init__(self, dsn: str) -> None:
        self._dsn = str(dsn).strip()
        if not self._dsn:
            raise ValueError("PostgreSQL DSN must be non-empty")
        self._path = Path("__postgres_store__")
        self._lock = threading.RLock()
        self._init_db()

    @property
    def location(self) -> Path | None:
        return None

    def _connect(self):
        return connect_postgres(self._dsn)

    @contextmanager
    def _pool_connection(self) -> Iterator[Any]:
        pool = get_postgres_pool(self._dsn)
        with pool.connection() as conn:
            yield conn

    def _fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[Any]:
        with self._pool_connection() as conn:
            return list(conn.execute(sql, params).fetchall())

    def _fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> Any | None:
        with self._pool_connection() as conn:
            return conn.execute(sql, params).fetchone()

    @staticmethod
    def _in_clause(values: tuple[str, ...]) -> str:
        return ", ".join("%s" for _ in values)

    def _load_global_llm_settings_payload(self, conn) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT payload_json
            FROM global_settings_index
            WHERE settings_key = %s
            """,
            ("global_llm",),
        ).fetchone()
        if row is None:
            return None
        payload = json.loads(str(row["payload_json"]))
        if not isinstance(payload, dict):
            raise ValueError("Global LLM settings payload must be a JSON object")
        return payload

    def _replace_global_llm_settings_payload(self, conn, payload: dict[str, Any] | None, *, updated_at: str) -> None:
        conn.execute("DELETE FROM global_settings_index WHERE settings_key = %s", ("global_llm",))
        if payload is None:
            return
        conn.execute(
            """
            INSERT INTO global_settings_index (settings_key, payload_json, updated_at)
            VALUES (%s, %s, %s)
            """,
            (
                "global_llm",
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                str(updated_at),
            ),
        )

    @staticmethod
    def _table_exists(conn, table_name: str) -> bool:
        row = conn.execute(
            """
            SELECT 1
            FROM pg_tables
            WHERE schemaname = current_schema() AND tablename = %s
            LIMIT 1
            """,
            (str(table_name),),
        ).fetchone()
        return row is not None

    def _init_db(self) -> None:
        with self._lock:
            validate_postgres_migration_plan()
            pool = get_postgres_pool(self._dsn)
            conn = pool.acquire()
            try:
                apply_postgres_migrations(conn, target="store")
            finally:
                pool.release(conn)

    @staticmethod
    def _migration_health_error(status: dict[str, object]) -> str | None:
        conflicts = list(status.get("conflicts", []))
        if conflicts:
            item = conflicts[0]
            if isinstance(item, dict):
                return (
                    "Conflicting PostgreSQL store migrations detected for "
                    f"{item.get('scope')}:{item.get('version')}"
                )
            return "Conflicting PostgreSQL store migrations detected"
        pending = list(status.get("pending", []))
        if pending:
            item = pending[0]
            if isinstance(item, dict):
                return f"Pending PostgreSQL store migration {item.get('scope')}:{item.get('version')}"
            return "Pending PostgreSQL store migrations detected"
        return None

    def healthcheck(self) -> dict[str, object]:
        health = get_postgres_pool(self._dsn).healthcheck()
        health["backend"] = "postgres"
        health["dsn"] = redact_postgres_dsn(self._dsn)
        health["expectedMigrations"] = expected_postgres_migration_status(target="store")
        if bool(health.get("ok", False)):
            pool = get_postgres_pool(self._dsn)
            conn = pool.acquire()
            try:
                status = postgres_migration_status(conn, target="store")
                health["migrations"] = status
                migration_error = self._migration_health_error(status)
                if migration_error:
                    health["ok"] = False
                    health["error"] = migration_error
                else:
                    conn.execute("SELECT 1 FROM project_snapshots LIMIT 1").fetchone()
                    health["probe"] = {"ok": True, "target": "project_snapshots"}
            except Exception as exc:
                health["ok"] = False
                health["error"] = str(exc)
                health["probe"] = {"ok": False, "error": str(exc)}
            finally:
                pool.release(conn)
        return health

    def begin_unit_of_work(self, *, project_id: str | None = None) -> SqlUnitOfWork:
        return PostgresPersistenceUnitOfWork(connect=self._connect, project_id=project_id)

    def _subject_material_relationship_repository(self) -> SqlSubjectMaterialRelationshipRepository:
        return PostgresSubjectMaterialRelationshipRepository()

    def _subject_material_relationship_session(self, conn):
        return PostgresPersistenceSession(raw_connection=conn)

    def load_snapshot(self) -> dict[str, Any] | None:
        with self._lock:
            with self._pool_connection() as conn:
                sharded = self._load_from_sharded_tables_native(conn)

            if sharded is not None:
                return sharded

            return None

    def save_snapshot(self, snapshot: dict[str, Any]) -> None:
        normalized = self._normalize_snapshot(snapshot)
        updated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        with self.begin_unit_of_work() as uow:
            uow.system_state.upsert(
                uow.session,
                SystemStateRecord(
                    schema_version=int(normalized["schemaVersion"]),
                    idgen_counters=dict(normalized["idgenCounters"]),
                    updated_at=updated_at,
                ),
            )
            self._replace_global_llm_settings_payload(
                uow.connection,
                normalized.get("globalLlmSettings"),
                updated_at=updated_at,
            )
            projects = dict(normalized["projects"])
            uow.project_snapshots.delete_absent(uow.session, tuple(projects.keys()))
            for project_id, project_payload in projects.items():
                if not isinstance(project_payload, dict):
                    raise ValueError("Project snapshot must be a JSON object")
                uow.project_snapshots.upsert(
                    uow.session,
                    self._project_snapshot_record(
                        project_id=str(project_id),
                        project_payload=project_payload,
                        updated_at=updated_at,
                    ),
                )
            for project_id, project_payload in projects.items():
                self._refresh_project_entity_indexes(
                    uow.connection,
                    project_id=str(project_id),
                    project_payload=project_payload,
                )

    def _load_from_sharded_tables_native(self, conn) -> dict[str, Any] | None:
        system_row = conn.execute(
            "SELECT schema_version, idgen_counters_json FROM system_state WHERE slot = 1"
        ).fetchone()
        global_llm_settings = self._load_global_llm_settings_payload(conn)
        project_rows = conn.execute(
            """
            SELECT project_id, project_title, project_state, created_at_ms, deleted_at_ms,
                   subject_id, scoped_project_id, project_sequence
            FROM project_snapshots
            ORDER BY project_id ASC
            """
        ).fetchall()
        if system_row is None and global_llm_settings is None and not project_rows:
            return None

        if system_row is None:
            schema_version = 1
            idgen_counters: dict[str, Any] = {}
        else:
            schema_version = int(system_row["schema_version"])
            raw_counters = str(system_row["idgen_counters_json"])
            loaded_counters = json.loads(raw_counters)
            idgen_counters = dict(loaded_counters) if isinstance(loaded_counters, dict) else {}

        projects: dict[str, Any] = {}
        for row in project_rows:
            projects[str(row["project_id"])] = self._hydrate_project_payload_from_row_native(conn, row=row)

        return {
            "schemaVersion": schema_version,
            "idgenCounters": idgen_counters,
            "globalLlmSettings": global_llm_settings,
            "projects": projects,
        }

    def _hydrate_project_payload_from_row_native(self, conn, *, row: Any) -> dict[str, Any]:
        project_payload = self._project_payload_from_snapshot_row(row)
        if str(row["project_state"]) == ProjectState.DELETED.value:
            return project_payload
        return self._hydrate_project_payload_native(conn, project_id=str(row["project_id"]), project_payload=project_payload)

    def _hydrate_project_payload_native(self, conn, *, project_id: str, project_payload: dict[str, Any]) -> dict[str, Any]:
        hydrated = dict(project_payload)

        storage_row = conn.execute(
            """
            SELECT project_root, learning_object_root, fs_sync_policy, updated_at_ms
            FROM project_storage_config_index
            WHERE project_id = %s
            """,
            (str(project_id),),
        ).fetchone()
        if storage_row is None:
            raise RuntimeError(f"project_storage_config_index row is required for active project {project_id}")
        hydrated["projectStorageConfig"] = {
            "projectId": str(project_id),
            "projectRoot": str(storage_row["project_root"]),
            "learningObjectRoot": str(storage_row["learning_object_root"]),
            "fsSyncPolicy": str(storage_row["fs_sync_policy"]),
            "updatedAtMs": int(storage_row["updated_at_ms"]),
        }

        material_source_binding_row = conn.execute(
            """
            SELECT source_kind, source_root_label, updated_at_ms
            FROM project_material_source_binding_index
            WHERE project_id = %s
            """,
            (str(project_id),),
        ).fetchone()
        if material_source_binding_row is None:
            raise RuntimeError(f"project_material_source_binding_index row is required for active project {project_id}")
        hydrated["projectMaterialSourceBinding"] = {
            "projectId": str(project_id),
            "sourceKind": str(material_source_binding_row["source_kind"]),
            "sourceRootLabel": None
            if material_source_binding_row["source_root_label"] is None
            else str(material_source_binding_row["source_root_label"]),
            "updatedAtMs": int(material_source_binding_row["updated_at_ms"]),
        }

        config_row = conn.execute(
            """
            SELECT config_json
            FROM project_config_index
            WHERE project_id = %s
            """,
            (str(project_id),),
        ).fetchone()
        if config_row is None:
            raise RuntimeError(f"project_config_index row is required for active project {project_id}")
        config_payload = json.loads(str(config_row["config_json"]))
        if not isinstance(config_payload, dict):
            raise ValueError("ProjectConfig payload must be a JSON object")
        hydrated["projectConfig"] = config_payload

        self._hydrate_subject_material_relationships(conn, project_id=project_id, hydrated=hydrated)

        instance_rows = conn.execute(
            """
            SELECT instance_id, material_id, presence, last_seen_at_ms
            FROM instance_index
            WHERE project_id = %s
            ORDER BY instance_id ASC
            """,
            (str(project_id),),
        ).fetchall()
        hydrated["instances"] = {
            str(row["instance_id"]): {
                "projectId": str(project_id),
                "instanceId": str(row["instance_id"]),
                "materialId": str(row["material_id"]),
                "presence": str(row["presence"] or InstancePresence.PRESENT.value),
                "lastSeenAtMs": None if row["last_seen_at_ms"] is None else int(row["last_seen_at_ms"]),
            }
            for row in instance_rows
        }

        instance_media_binding_rows = conn.execute(
            """
            SELECT instance_id, source_kind, playback_kind, account_id, remote_file_id, remote_path,
                   mime_type, size_bytes, duration_ms, source_payload_json, updated_at_ms
            FROM instance_media_binding_index
            WHERE project_id = %s
            ORDER BY instance_id ASC
            """,
            (str(project_id),),
        ).fetchall()
        hydrated["instanceMediaBindings"] = {
            str(row["instance_id"]): {
                "projectId": str(project_id),
                "instanceId": str(row["instance_id"]),
                "sourceKind": str(row["source_kind"]),
                "playbackKind": str(row["playback_kind"] or "FILE"),
                "accountId": None if row["account_id"] is None else str(row["account_id"]),
                "remoteFileId": None if row["remote_file_id"] is None else str(row["remote_file_id"]),
                "remotePath": None if row["remote_path"] is None else str(row["remote_path"]),
                "mimeType": None if row["mime_type"] is None else str(row["mime_type"]),
                "sizeBytes": None if row["size_bytes"] is None else int(row["size_bytes"]),
                "durationMs": None if row["duration_ms"] is None else int(row["duration_ms"]),
                "sourcePayload": json.loads(str(row["source_payload_json"]) if row["source_payload_json"] is not None else "{}"),
                "updatedAtMs": int(row["updated_at_ms"]),
            }
            for row in instance_media_binding_rows
        }

        node_rows = conn.execute(
            """
            SELECT node_id, node_kind, source, relative_path, parent_id, instance_id, title, children_json
            FROM learning_object_node_index
            WHERE project_id = %s
            ORDER BY node_id ASC
            """,
            (str(project_id),),
        ).fetchall()
        nodes: dict[str, dict[str, Any]] = {}
        for row in node_rows:
            payload: dict[str, Any] = {
                "kind": str(row["node_kind"]),
                "source": str(row["source"]),
                "projectId": str(project_id),
                "nodeId": str(row["node_id"]),
                "relativePath": str(row["relative_path"]),
                "parentId": None if row["parent_id"] is None else str(row["parent_id"]),
                "title": str(row["title"]),
            }
            if str(row["node_kind"]) == "LEAF":
                payload["instanceId"] = str(row["instance_id"])
            else:
                children_raw = str(row["children_json"]) if row["children_json"] is not None else "[]"
                payload["children"] = list(json.loads(children_raw))
            nodes[str(row["node_id"])] = payload
        hydrated["learningObjectNodes"] = nodes

        recall_point_rows = conn.execute(
            """
            SELECT recall_point_id, created_at_ms, anchor_instance_id, anchor_position, question_plain_text,
                   answer_plain_text, insights_count, payload_json
            FROM recall_point_index
            WHERE project_id = %s
            ORDER BY recall_point_id ASC
            """,
            (str(project_id),),
        ).fetchall()
        hydrated["recallPoints"] = {
            str(row["recall_point_id"]): self._recall_point_payload_from_index_row(
                project_id=str(project_id),
                row=row,
            )
            for row in recall_point_rows
        }

        learning_task_rows = conn.execute(
            """
            SELECT learning_task_id, title, recall_point_ids_json
            FROM learning_task_index
            WHERE project_id = %s
            ORDER BY learning_task_id ASC
            """,
            (str(project_id),),
        ).fetchall()
        hydrated["learningTasks"] = {
            str(row["learning_task_id"]): self._learning_task_payload_from_index_row(project_id=str(project_id), row=row)
            for row in learning_task_rows
        }

        learning_task_node_rows = conn.execute(
            """
            SELECT node_id, node_kind, parent_id, bound_learning_task_id, node_origin, bound_learning_object_node_id, object_mirror_status, title, children_json
            FROM learning_task_node_index
            WHERE project_id = %s
            ORDER BY node_id ASC
            """,
            (str(project_id),),
        ).fetchall()
        hydrated["learningTaskNodes"] = {
            str(row["node_id"]): self._learning_task_node_payload_from_index_row(project_id=str(project_id), row=row)
            for row in learning_task_node_rows
        }

        entry_reg_rows = conn.execute(
            """
            SELECT entry_node, target_layer_index, review_chain_id, registration_seq
            FROM entry_registration_index
            WHERE project_id = %s
            ORDER BY entry_node ASC
            """,
            (str(project_id),),
        ).fetchall()
        hydrated["entryRegs"] = {
            str(row["entry_node"]): self._entry_registration_payload_from_index_row(project_id=str(project_id), row=row)
            for row in entry_reg_rows
        }

        range_snapshot_rows = conn.execute(
            """
            SELECT range_id, recall_point_ids_json
            FROM range_snapshot_index
            WHERE project_id = %s
            ORDER BY range_id ASC
            """,
            (str(project_id),),
        ).fetchall()
        hydrated["rangeSnapshots"] = {
            str(row["range_id"]): self._range_snapshot_payload_from_index_row(project_id=str(project_id), row=row)
            for row in range_snapshot_rows
        }

        review_task_rows = conn.execute(
            """
            SELECT review_task_id, input_range_id, created_at_ms, state, executed_at_ms, result_range_id
            FROM review_task_index
            WHERE project_id = %s
            ORDER BY review_task_id ASC
            """,
            (str(project_id),),
        ).fetchall()
        hydrated["reviewTasks"] = {
            str(row["review_task_id"]): self._review_task_payload_from_index_row(project_id=str(project_id), row=row)
            for row in review_task_rows
        }

        convergence_rows = conn.execute(
            """
            SELECT convergence_id, seed_range_id, rule_id, review_task_ids_json, state
            FROM convergence_index
            WHERE project_id = %s
            ORDER BY convergence_id ASC
            """,
            (str(project_id),),
        ).fetchall()
        hydrated["convergences"] = {
            str(row["convergence_id"]): self._convergence_payload_from_index_row(project_id=str(project_id), row=row)
            for row in convergence_rows
        }

        review_chain_rows = conn.execute(
            """
            SELECT review_chain_id, queue_json, head_index, state
            FROM review_chain_index
            WHERE project_id = %s
            ORDER BY review_chain_id ASC
            """,
            (str(project_id),),
        ).fetchall()
        hydrated["reviewChains"] = {
            str(row["review_chain_id"]): self._review_chain_payload_from_index_row(project_id=str(project_id), row=row)
            for row in review_chain_rows
        }

        queue_row = conn.execute(
            """
            SELECT queue_id, review_task_ids_json, head_index
            FROM review_task_queue_index
            WHERE project_id = %s
            """,
            (str(project_id),),
        ).fetchone()
        if queue_row is not None:
            hydrated["reviewTaskQueue"] = self._review_task_queue_payload_from_index_row(project_id=str(project_id), row=queue_row)
        elif project_payload.get("reviewTaskQueue") is not None:
            hydrated["reviewTaskQueue"] = dict(project_payload["reviewTaskQueue"])
        else:
            hydrated["reviewTaskQueue"] = None

        layer_rows = conn.execute(
            """
            SELECT layer_id, layer_index, layer_mode, orchestrator_managed_review_chain_ids_json,
                   aggregation_k_node, aggregation_k_point, aggregation_cycle_state,
                   pending_roll_up_parent_node_id, normal_tick_quota_remaining
            FROM layer_state_index
            WHERE project_id = %s
            ORDER BY layer_index ASC, layer_id ASC
            """,
            (str(project_id),),
        ).fetchall()
        hydrated["layers"] = {
            str(row["layer_id"]): self._layer_payload_from_index_row(project_id=str(project_id), row=row)
            for row in layer_rows
        }
        hydrated["layersByIndex"] = {
            str(int(row["layer_index"])): str(row["layer_id"])
            for row in layer_rows
        }
        hydrated["aggregationKNode"] = {str(int(row["layer_index"])): int(row["aggregation_k_node"]) for row in layer_rows}
        hydrated["aggregationKPoint"] = {str(int(row["layer_index"])): int(row["aggregation_k_point"]) for row in layer_rows}
        hydrated["aggregationCycleState"] = {
            str(int(row["layer_index"])): str(row["aggregation_cycle_state"])
            for row in layer_rows
        }
        hydrated["pendingRollUpParentNodeId"] = {
            str(int(row["layer_index"])): None
            if row["pending_roll_up_parent_node_id"] is None
            else str(row["pending_roll_up_parent_node_id"])
            for row in layer_rows
        }
        hydrated["normalTickQuotaRemaining"] = {
            str(int(row["layer_index"])): int(row["normal_tick_quota_remaining"])
            for row in layer_rows
        }

        audit_log_event_rows = conn.execute(
            """
            SELECT event_id, occurred_at_ms, kind, api_name, result, payload
            FROM audit_log_event_index
            WHERE project_id = %s
            ORDER BY occurred_at_ms ASC, event_id ASC
            """,
            (str(project_id),),
        ).fetchall()
        hydrated["auditLogEvents"] = {
            str(row["event_id"]): self._audit_log_event_payload_from_index_row(project_id=str(project_id), row=row)
            for row in audit_log_event_rows
        }

        asr_artifact_rows = conn.execute(
            """
            SELECT asr_artifact_id, created_at_ms, provider, recall_point_id, source_instance_id, center_ms, pre_ms,
                   post_ms, segments_json
            FROM asr_artifact_index
            WHERE project_id = %s
            ORDER BY asr_artifact_id ASC
            """,
            (str(project_id),),
        ).fetchall()
        hydrated["asrArtifacts"] = {
            str(row["asr_artifact_id"]): self._asr_artifact_payload_from_index_row(project_id=str(project_id), row=row)
            for row in asr_artifact_rows
        }

        aggregation_queue_rows = conn.execute(
            """
            SELECT layer_index, node_ids_json, head_index
            FROM aggregation_queue_index
            WHERE project_id = %s
            ORDER BY layer_index ASC
            """,
            (str(project_id),),
        ).fetchall()
        hydrated["aggregationQueues"] = {
            str(int(row["layer_index"])): self._aggregation_queue_payload_from_index_row(project_id=str(project_id), row=row)
            for row in aggregation_queue_rows
        }

        aggregation_event_rows = conn.execute(
            """
            SELECT event_id, created_at_ms, layer_index, parent_node_id, child_node_ids_json, reason, title
            FROM aggregation_event_index
            WHERE project_id = %s
            ORDER BY event_id ASC
            """,
            (str(project_id),),
        ).fetchall()
        hydrated["aggregationEvents"] = {
            str(row["event_id"]): self._aggregation_event_payload_from_index_row(project_id=str(project_id), row=row)
            for row in aggregation_event_rows
        }

        material_allowlist_row = conn.execute(
            """
            SELECT allowlist_id, material_ids_json
            FROM material_allowlist_index
            WHERE project_id = %s
            """,
            (str(project_id),),
        ).fetchone()
        if material_allowlist_row is not None:
            hydrated["materialAllowlist"] = self._material_allowlist_payload_from_index_row(
                project_id=str(project_id),
                row=material_allowlist_row,
            )
        else:
            hydrated["materialAllowlist"] = None if project_payload.get("materialAllowlist") is None else dict(project_payload["materialAllowlist"])

        media_asset_rows = conn.execute(
            """
            SELECT asset_id, kind, relative_path, created_at_ms, mime_type
            FROM media_asset_index
            WHERE project_id = %s
            ORDER BY asset_id ASC
            """,
            (str(project_id),),
        ).fetchall()
        hydrated["mediaAssets"] = {
            str(row["asset_id"]): self._media_asset_payload_from_index_row(project_id=str(project_id), row=row)
            for row in media_asset_rows
        }

        review_record_rows = conn.execute(
            """
            SELECT record_id, recall_point_id, review_task_id, occurred_at_ms, result
            FROM recall_point_review_record_index
            WHERE project_id = %s
            ORDER BY occurred_at_ms ASC, record_id ASC
            """,
            (str(project_id),),
        ).fetchall()
        hydrated["recallPointReviewRecords"] = {
            str(row["record_id"]): self._recall_point_review_record_payload_from_index_row(project_id=str(project_id), row=row)
            for row in review_record_rows
        }
        return hydrated

    def list_projects_metadata(self, *, active_only: bool = True) -> tuple[Project, ...]:
        query = """
            SELECT project_id, project_title, project_state, created_at_ms, deleted_at_ms,
                   subject_id, scoped_project_id, project_sequence
            FROM project_snapshots
        """
        params: tuple[Any, ...] = tuple()
        if active_only:
            query += " WHERE project_state = %s"
            params = (ProjectState.ACTIVE.value,)
        query += " ORDER BY project_id ASC"
        rows = self._fetchall(query, params)
        projects: list[Project] = []
        for row in rows:
            projects.append(Project(
                project_id=ProjectId(str(row["project_id"])),
                title=str(row["project_title"]),
                state=ProjectState(str(row["project_state"])),
                created_at=self._ms_to_ts(int(row["created_at_ms"])),
                deleted_at=self._ms_to_ts(None if row["deleted_at_ms"] is None else int(row["deleted_at_ms"])),
                subject_id=None if row["subject_id"] is None else ProjectId(str(row["subject_id"])),
                scoped_project_id=None if row["scoped_project_id"] is None else ProjectId(str(row["scoped_project_id"])),
                project_sequence=int(row["project_sequence"] or 0),
            ))
        return tuple(projects)

    def get_project_config(self, project_id: str) -> ProjectConfig | None:
        row = self._fetchone(
            """
            SELECT config_json
            FROM project_config_index
            WHERE project_id = %s
            """,
            (str(project_id),),
        )
        if row is None:
            return None
        payload = json.loads(str(row["config_json"]))
        if not isinstance(payload, dict):
            raise ValueError("ProjectConfig payload must be a JSON object")
        return decode_project_config_payload(payload)

    def get_project_storage_config(self, project_id: str) -> ProjectStorageConfig | None:
        row = self._fetchone(
            """
            SELECT project_root, learning_object_root, fs_sync_policy, updated_at_ms
            FROM project_storage_config_index
            WHERE project_id = %s
            """,
            (str(project_id),),
        )
        if row is None:
            return None
        return decode_project_storage_config_payload(
            {
                "projectId": str(project_id),
                "projectRoot": str(row["project_root"]),
                "learningObjectRoot": str(row["learning_object_root"]),
                "fsSyncPolicy": str(row["fs_sync_policy"]),
                "updatedAtMs": int(row["updated_at_ms"]),
            }
        )

    def list_audit_log_events(self, project_id: str) -> tuple[AuditLogEvent, ...]:
        rows = self._fetchall(
            """
            SELECT event_id, occurred_at_ms, kind, api_name, result, payload
            FROM audit_log_event_index
            WHERE project_id = %s
            ORDER BY occurred_at_ms ASC, event_id ASC
            """,
            (str(project_id),),
        )
        return tuple(self._decode_audit_log_event_index_row(project_id=str(project_id), row=row) for row in rows)

    def list_instances(self, project_id: str) -> tuple[Instance, ...]:
        rows = self._fetchall(
            """
            SELECT instance_id, material_id, presence, last_seen_at_ms
            FROM instance_index
            WHERE project_id = %s
            ORDER BY instance_id ASC
            """,
            (str(project_id),),
        )
        return tuple(
            Instance(
                project_id=ProjectId(str(project_id)),
                instance_id=InstanceId(str(row["instance_id"])),
                material_id=PurePosixPath(str(row["material_id"])),
                presence=InstancePresence(str(row["presence"] or InstancePresence.PRESENT.value)),
                last_seen_at=self._ms_to_ts(None if row["last_seen_at_ms"] is None else int(row["last_seen_at_ms"])),
            )
            for row in rows
        )

    def get_instance(self, project_id: str, instance_id: str) -> Instance | None:
        row = self._fetchone(
            """
            SELECT material_id, presence, last_seen_at_ms
            FROM instance_index
            WHERE project_id = %s AND instance_id = %s
            """,
            (str(project_id), str(instance_id)),
        )
        if row is None:
            return None
        return Instance(
            project_id=ProjectId(str(project_id)),
            instance_id=InstanceId(str(instance_id)),
            material_id=PurePosixPath(str(row["material_id"])),
            presence=InstancePresence(str(row["presence"] or InstancePresence.PRESENT.value)),
            last_seen_at=self._ms_to_ts(None if row["last_seen_at_ms"] is None else int(row["last_seen_at_ms"])),
        )

    def list_instance_media_bindings(self, project_id: str) -> tuple[InstanceMediaBinding, ...]:
        rows = self._fetchall(
            """
            SELECT instance_id, source_kind, playback_kind, account_id, remote_file_id, remote_path,
                   mime_type, size_bytes, duration_ms, source_payload_json, updated_at_ms
            FROM instance_media_binding_index
            WHERE project_id = %s
            ORDER BY instance_id ASC
            """,
            (str(project_id),),
        )
        return tuple(self._decode_instance_media_binding(project_id=str(project_id), row=row) for row in rows)

    def get_instance_media_binding(self, project_id: str, instance_id: str) -> InstanceMediaBinding | None:
        row = self._fetchone(
            """
            SELECT instance_id, source_kind, playback_kind, account_id, remote_file_id, remote_path,
                   mime_type, size_bytes, duration_ms, source_payload_json, updated_at_ms
            FROM instance_media_binding_index
            WHERE project_id = %s AND instance_id = %s
            """,
            (str(project_id), str(instance_id)),
        )
        if row is None:
            return None
        return self._decode_instance_media_binding(project_id=str(project_id), row=row)

    def list_missing_instance_ids(self, project_id: str) -> tuple[InstanceId, ...]:
        rows = self._fetchall(
            """
            SELECT instance_id
            FROM instance_index
            WHERE project_id = %s AND presence = %s
            ORDER BY instance_id ASC
            """,
            (str(project_id), InstancePresence.MISSING.value),
        )
        return tuple(InstanceId(str(row["instance_id"])) for row in rows)

    def list_recall_point_ids_by_instance(self, project_id: str, instance_id: str) -> tuple[RecallPointId, ...]:
        rows = self._fetchall(
            """
            SELECT recall_point_id, created_at_ms, anchor_instance_id, anchor_position, question_plain_text,
                   answer_plain_text, insights_count, payload_json
            FROM recall_point_index
            WHERE project_id = %s AND anchor_instance_id = %s
            ORDER BY recall_point_id ASC
            """,
            (str(project_id), str(instance_id)),
        )
        out: list[RecallPointId] = []
        for row in rows:
            raw = self._recall_point_payload_from_index_row(project_id=str(project_id), row=row)
            rp = self._decode_recall_point(project_id=str(project_id), raw=raw)
            if rp.state == RecallPointState.ACTIVE:
                out.append(rp.recall_point_id)
        return tuple(out)

    def get_recall_point(self, project_id: str, recall_point_id: str) -> RecallPoint | None:
        row = self._fetchone(
            """
            SELECT recall_point_id, created_at_ms, anchor_instance_id, anchor_position, question_plain_text,
                   answer_plain_text, insights_count, payload_json
            FROM recall_point_index
            WHERE project_id = %s AND recall_point_id = %s
            """,
            (str(project_id), str(recall_point_id)),
        )
        if row is None:
            return None
        raw = self._recall_point_payload_from_index_row(project_id=str(project_id), row=row)
        return self._decode_recall_point(project_id=str(project_id), raw=raw)

    def list_recall_points(self, project_id: str) -> tuple[RecallPoint, ...]:
        rows = self._fetchall(
            """
            SELECT recall_point_id, created_at_ms, anchor_instance_id, anchor_position, question_plain_text,
                   answer_plain_text, insights_count, payload_json
            FROM recall_point_index
            WHERE project_id = %s
            ORDER BY created_at_ms ASC, recall_point_id ASC
            """,
            (str(project_id),),
        )
        return tuple(
            self._decode_recall_point(
                project_id=str(project_id),
                raw=self._recall_point_payload_from_index_row(project_id=str(project_id), row=row),
            )
            for row in rows
        )

    def search_recall_points(self, project_id: str, query: str | None = None, limit: int = 20) -> tuple[RecallPoint, ...]:
        normalized_query = str(query or "").strip().lower()
        resolved_limit = max(1, min(int(limit), 50))
        fetch_limit = min(max(resolved_limit * 5, resolved_limit + 20), 200)
        where_clause = "WHERE project_id = %s"
        params: list[Any] = [str(project_id)]
        if normalized_query:
            like = f"%{normalized_query}%"
            where_clause += (
                " AND (LOWER(recall_point_id) LIKE %s OR LOWER(question_plain_text) LIKE %s OR LOWER(answer_plain_text) LIKE %s)"
            )
            params.extend([like, like, like])
        rows = self._fetchall(
            f"""
            SELECT recall_point_id, created_at_ms, anchor_instance_id, anchor_position, question_plain_text,
                   answer_plain_text, insights_count, payload_json
            FROM recall_point_index
            {where_clause}
            ORDER BY created_at_ms DESC, recall_point_id DESC
            LIMIT %s
            """,
            (*params, fetch_limit),
        )
        items: list[RecallPoint] = []
        for row in rows:
            item = self._decode_recall_point(
                project_id=str(project_id),
                raw=self._recall_point_payload_from_index_row(project_id=str(project_id), row=row),
            )
            if item.state != RecallPointState.ACTIVE:
                continue
            items.append(item)
            if len(items) >= resolved_limit:
                break
        return tuple(items)

    def list_recall_points_by_learning_object_node(self, project_id: str, node_id: str) -> tuple[RecallPoint, ...]:
        rows = self._fetchall(
            """
            SELECT node_id, node_kind, instance_id, children_json
            FROM learning_object_node_index
            WHERE project_id = %s
            """,
            (str(project_id),),
        )
        node_map = {
            str(row["node_id"]): {
                "kind": str(row["node_kind"]),
                "instance_id": None if row["instance_id"] is None else str(row["instance_id"]),
                "children": tuple(json.loads(str(row["children_json"]))) if row["children_json"] is not None else tuple(),
            }
            for row in rows
        }
        if str(node_id) not in node_map:
            return tuple()

        covered_instance_ids: set[str] = set()
        stack = [str(node_id)]
        seen: set[str] = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            entry = node_map.get(current)
            if entry is None:
                continue
            if entry["kind"] == "LEAF":
                instance_id = entry["instance_id"]
                if instance_id:
                    covered_instance_ids.add(instance_id)
                continue
            stack.extend(str(child) for child in entry["children"])

        if not covered_instance_ids:
            return tuple()

        instance_ids = tuple(sorted(covered_instance_ids))
        rows = self._fetchall(
            f"""
            SELECT recall_point_id, created_at_ms, anchor_instance_id, anchor_position, question_plain_text,
                   answer_plain_text, insights_count, payload_json
            FROM recall_point_index
            WHERE project_id = %s AND anchor_instance_id IN ({self._in_clause(instance_ids)})
            ORDER BY recall_point_id ASC
            """,
            (str(project_id), *instance_ids),
        )
        items: list[RecallPoint] = []
        for row in rows:
            raw = self._recall_point_payload_from_index_row(project_id=str(project_id), row=row)
            rp = self._decode_recall_point(project_id=str(project_id), raw=raw)
            if rp.state == RecallPointState.ACTIVE:
                items.append(rp)
        return tuple(items)

    def get_review_chain_entry_registration(self, project_id: str, review_chain_id: str) -> EntryRegistration | None:
        row = self._fetchone(
            """
            SELECT entry_node, target_layer_index, review_chain_id, registration_seq
            FROM entry_registration_index
            WHERE project_id = %s AND review_chain_id = %s
            ORDER BY entry_node ASC
            LIMIT 1
            """,
            (str(project_id), str(review_chain_id)),
        )
        if row is None:
            return None
        return self._decode_entry_registration_index_row(project_id=str(project_id), row=row)

    def list_learning_object_nodes(self, project_id: str) -> tuple[LearningObjectNode, ...]:
        rows = self._fetchall(
            """
            SELECT node_id, node_kind, source, relative_path, parent_id, instance_id, title, children_json
            FROM learning_object_node_index
            WHERE project_id = %s
            ORDER BY node_id ASC
            """,
            (str(project_id),),
        )
        nodes: list[LearningObjectNode] = []
        for row in rows:
            node_kind = str(row["node_kind"])
            if node_kind == "LEAF":
                nodes.append(
                    LearningObjectLeaf(
                        source=str(row["source"]),
                        project_id=ProjectId(str(project_id)),
                        node_id=LearningObjectNodeId(str(row["node_id"])),
                        relative_path=PurePosixPath(str(row["relative_path"])),
                        parent_id=None if row["parent_id"] is None else LearningObjectNodeId(str(row["parent_id"])),
                        instance_id=InstanceId(str(row["instance_id"])),
                        title=str(row["title"]),
                    )
                )
                continue
            children_raw = str(row["children_json"]) if row["children_json"] is not None else "[]"
            children = json.loads(children_raw)
            nodes.append(
                LearningObjectContainer(
                    source=str(row["source"]),
                    project_id=ProjectId(str(project_id)),
                    node_id=LearningObjectNodeId(str(row["node_id"])),
                    relative_path=PurePosixPath(str(row["relative_path"])),
                    parent_id=None if row["parent_id"] is None else LearningObjectNodeId(str(row["parent_id"])),
                    children=tuple(LearningObjectNodeId(str(item)) for item in children),
                    title=str(row["title"]),
                )
            )
        return tuple(nodes)

    def get_learning_object_node(self, project_id: str, node_id: str) -> LearningObjectNode | None:
        row = self._fetchone(
            """
            SELECT node_kind, source, relative_path, parent_id, instance_id, title, children_json
            FROM learning_object_node_index
            WHERE project_id = %s AND node_id = %s
            """,
            (str(project_id), str(node_id)),
        )
        if row is None:
            return None
        if str(row["node_kind"]) == "LEAF":
            return LearningObjectLeaf(
                source=str(row["source"]),
                project_id=ProjectId(str(project_id)),
                node_id=LearningObjectNodeId(str(node_id)),
                relative_path=PurePosixPath(str(row["relative_path"])),
                parent_id=None if row["parent_id"] is None else LearningObjectNodeId(str(row["parent_id"])),
                instance_id=InstanceId(str(row["instance_id"])),
                title=str(row["title"]),
            )
        children_raw = str(row["children_json"]) if row["children_json"] is not None else "[]"
        children = json.loads(children_raw)
        return LearningObjectContainer(
            source=str(row["source"]),
            project_id=ProjectId(str(project_id)),
            node_id=LearningObjectNodeId(str(node_id)),
            relative_path=PurePosixPath(str(row["relative_path"])),
            parent_id=None if row["parent_id"] is None else LearningObjectNodeId(str(row["parent_id"])),
            children=tuple(LearningObjectNodeId(str(item)) for item in children),
            title=str(row["title"]),
        )

    def list_learning_object_root_ids(self, project_id: str) -> tuple[LearningObjectNodeId, ...]:
        rows = self._fetchall(
            """
            SELECT node_id
            FROM learning_object_node_index
            WHERE project_id = %s AND parent_id IS NULL
            ORDER BY node_id ASC
            """,
            (str(project_id),),
        )
        return tuple(LearningObjectNodeId(str(row["node_id"])) for row in rows)

    def list_learning_task_nodes(self, project_id: str) -> tuple[LearningTaskNode, ...]:
        rows = self._fetchall(
            """
            SELECT node_id, node_kind, parent_id, bound_learning_task_id, node_origin, bound_learning_object_node_id, object_mirror_status, title, children_json
            FROM learning_task_node_index
            WHERE project_id = %s
            ORDER BY node_id ASC
            """,
            (str(project_id),),
        )
        return tuple(self._decode_learning_task_node_index_row(project_id=str(project_id), row=row) for row in rows)

    def get_learning_task_node(self, project_id: str, node_id: str) -> LearningTaskNode | None:
        row = self._fetchone(
            """
            SELECT node_id, node_kind, parent_id, bound_learning_task_id, node_origin, bound_learning_object_node_id, object_mirror_status, title, children_json
            FROM learning_task_node_index
            WHERE project_id = %s AND node_id = %s
            """,
            (str(project_id), str(node_id)),
        )
        if row is None:
            return None
        return self._decode_learning_task_node_index_row(project_id=str(project_id), row=row)

    def get_learning_task(self, project_id: str, learning_task_id: str) -> LearningTask | None:
        row = self._fetchone(
            """
            SELECT learning_task_id, title, recall_point_ids_json
            FROM learning_task_index
            WHERE project_id = %s AND learning_task_id = %s
            """,
            (str(project_id), str(learning_task_id)),
        )
        if row is None:
            return None
        return self._decode_learning_task_index_row(project_id=str(project_id), row=row)

    def get_learning_task_entry_registration(self, project_id: str, learning_task_id: str) -> EntryRegistration | None:
        row = self._fetchone(
            """
            SELECT eri.entry_node, eri.target_layer_index, eri.review_chain_id, eri.registration_seq
            FROM learning_task_node_index ltn
            JOIN entry_registration_index eri
              ON eri.project_id = ltn.project_id AND eri.entry_node = ltn.node_id
            WHERE ltn.project_id = %s AND ltn.node_kind = 'LEAF' AND ltn.bound_learning_task_id = %s
            ORDER BY ltn.node_id ASC
            LIMIT 1
            """,
            (str(project_id), str(learning_task_id)),
        )
        if row is None:
            return None
        return self._decode_entry_registration_index_row(project_id=str(project_id), row=row)

    def get_learning_task_node_entry_registration(self, project_id: str, node_id: str) -> EntryRegistration | None:
        row = self._fetchone(
            """
            SELECT entry_node, target_layer_index, review_chain_id, registration_seq
            FROM entry_registration_index
            WHERE project_id = %s AND entry_node = %s
            """,
            (str(project_id), str(node_id)),
        )
        if row is None:
            return None
        return self._decode_entry_registration_index_row(project_id=str(project_id), row=row)

    def list_recall_points_by_learning_task_node(self, project_id: str, node_id: str) -> tuple[RecallPoint, ...]:
        with self._pool_connection() as conn:
            node_rows = list(
                conn.execute(
                    """
                    SELECT node_id, node_kind, bound_learning_task_id, children_json
                    FROM learning_task_node_index
                    WHERE project_id = %s
                    """,
                    (str(project_id),),
                ).fetchall()
            )
            task_rows = list(
                conn.execute(
                    """
                    SELECT learning_task_id, recall_point_ids_json
                    FROM learning_task_index
                    WHERE project_id = %s
                    """,
                    (str(project_id),),
                ).fetchall()
            )

        node_map = {
            str(row["node_id"]): {
                "kind": str(row["node_kind"]),
                "bound_learning_task_id": None if row["bound_learning_task_id"] is None else str(row["bound_learning_task_id"]),
                "children": tuple(json.loads(str(row["children_json"]))) if row["children_json"] is not None else tuple(),
            }
            for row in node_rows
        }
        if str(node_id) not in node_map:
            return tuple()

        task_map = {
            str(row["learning_task_id"]): tuple(RecallPointId(str(item)) for item in json.loads(str(row["recall_point_ids_json"])))
            for row in task_rows
        }

        ordered_recall_point_ids: list[RecallPointId] = []
        stack: list[str] = [str(node_id)]
        while stack:
            current = stack.pop()
            current_entry = node_map.get(current)
            if current_entry is None:
                continue
            if current_entry["kind"] == "LEAF":
                bound_task_id = current_entry["bound_learning_task_id"]
                if bound_task_id is not None:
                    ordered_recall_point_ids.extend(task_map.get(bound_task_id, tuple()))
                continue
            children = tuple(str(item) for item in current_entry["children"])
            stack.extend(reversed(children))

        if not ordered_recall_point_ids:
            return tuple()

        unique_recall_point_ids = tuple(dict.fromkeys(str(item) for item in ordered_recall_point_ids))
        recall_point_rows = self._fetchall(
            f"""
            SELECT recall_point_id, created_at_ms, anchor_instance_id, anchor_position, question_plain_text,
                   answer_plain_text, insights_count, payload_json
            FROM recall_point_index
            WHERE project_id = %s AND recall_point_id IN ({self._in_clause(unique_recall_point_ids)})
            """,
            (str(project_id), *unique_recall_point_ids),
        )
        recall_point_map = {
            str(row["recall_point_id"]): self._decode_recall_point(
                project_id=str(project_id),
                raw=self._recall_point_payload_from_index_row(project_id=str(project_id), row=row),
            )
            for row in recall_point_rows
        }
        return tuple(
            recall_point_map[str(recall_point_id)]
            for recall_point_id in ordered_recall_point_ids
            if str(recall_point_id) in recall_point_map
            and recall_point_map[str(recall_point_id)].state == RecallPointState.ACTIVE
        )

    def get_review_task_queue(self, project_id: str) -> tuple[ReviewTaskId | None, tuple[ReviewTaskId, ...]] | None:
        row = self._fetchone(
            """
            SELECT queue_id, review_task_ids_json, head_index
            FROM review_task_queue_index
            WHERE project_id = %s
            """,
            (str(project_id),),
        )
        if row is None:
            return None
        return self._decode_review_task_queue_index_row(project_id=str(project_id), row=row)

    def list_layers(self, project_id: str) -> tuple[Layer, ...]:
        rows = self._fetchall(
            """
            SELECT layer_id, layer_index, layer_mode, orchestrator_managed_review_chain_ids_json,
                   aggregation_k_node, aggregation_k_point, aggregation_cycle_state,
                   pending_roll_up_parent_node_id, normal_tick_quota_remaining
            FROM layer_state_index
            WHERE project_id = %s
            ORDER BY layer_index ASC, layer_id ASC
            """,
            (str(project_id),),
        )
        return tuple(self._decode_layer_index_row(project_id=str(project_id), row=row) for row in rows)

    def get_aggregation_queue_current(self, project_id: str, layer_index: int) -> tuple[LearningTaskNodeId, ...] | None:
        row = self._fetchone(
            """
            SELECT layer_index, node_ids_json, head_index
            FROM aggregation_queue_index
            WHERE project_id = %s AND layer_index = %s
            """,
            (str(project_id), int(layer_index)),
        )
        if row is None:
            return None
        payload = self._aggregation_queue_payload_from_index_row(project_id=str(project_id), row=row)
        node_ids = tuple(LearningTaskNodeId(str(item)) for item in list(payload["nodeIds"]))
        return tuple(node_ids[int(payload["headIndex"]) :])

    def list_aggregation_events(self, project_id: str) -> tuple[AggregationEvent, ...]:
        rows = self._fetchall(
            """
            SELECT event_id, created_at_ms, layer_index, parent_node_id, child_node_ids_json, reason, title
            FROM aggregation_event_index
            WHERE project_id = %s
            ORDER BY event_id ASC
            """,
            (str(project_id),),
        )
        return tuple(self._decode_aggregation_event_index_row(project_id=str(project_id), row=row) for row in rows)

    def get_review_task(self, project_id: str, review_task_id: str) -> ReviewTask | None:
        row = self._fetchone(
            """
            SELECT review_task_id, input_range_id, created_at_ms, state, executed_at_ms, result_range_id
            FROM review_task_index
            WHERE project_id = %s AND review_task_id = %s
            """,
            (str(project_id), str(review_task_id)),
        )
        if row is None:
            return None
        return self._decode_review_task_index_row(project_id=str(project_id), row=row)

    def get_asr_artifact(self, project_id: str, asr_artifact_id: str) -> AsrArtifact | None:
        row = self._fetchone(
            """
            SELECT asr_artifact_id, created_at_ms, provider, recall_point_id, source_instance_id, center_ms, pre_ms,
                   post_ms, segments_json
            FROM asr_artifact_index
            WHERE project_id = %s AND asr_artifact_id = %s
            """,
            (str(project_id), str(asr_artifact_id)),
        )
        if row is None:
            return None
        return self._decode_asr_artifact_index_row(project_id=str(project_id), row=row)

    def _list_asr_artifacts(self, project_id: str) -> tuple[AsrArtifact, ...]:
        rows = self._fetchall(
            """
            SELECT asr_artifact_id, created_at_ms, provider, recall_point_id, source_instance_id, center_ms, pre_ms,
                   post_ms, segments_json
            FROM asr_artifact_index
            WHERE project_id = %s
            ORDER BY asr_artifact_id ASC
            """,
            (str(project_id),),
        )
        return tuple(self._decode_asr_artifact_index_row(project_id=str(project_id), row=row) for row in rows)

    def export_asr_by_learning_object_node(self, project_id: str, node_id: str) -> tuple[AsrArtifact, ...]:
        recall_point_order = {
            id_canonical_text(item.recall_point_id): index
            for index, item in enumerate(self.list_recall_points_by_learning_object_node(project_id, node_id))
        }
        if not recall_point_order:
            return tuple()

        items = [
            artifact
            for artifact in self._list_asr_artifacts(project_id)
            if id_canonical_text(artifact.recall_point_id) in recall_point_order
        ]
        items.sort(
            key=lambda art: (
                int(recall_point_order[id_canonical_text(art.recall_point_id)]),
                str(art.provider.value),
                int(art.center_ms),
                int(art.pre_ms),
                int(art.post_ms),
                id_canonical_text(art.asr_artifact_id),
            )
        )
        return tuple(items)

    def export_asr_by_learning_task_node(self, project_id: str, node_id: str) -> tuple[AsrArtifact, ...]:
        recall_point_order = {
            id_canonical_text(item.recall_point_id): index
            for index, item in enumerate(self.list_recall_points_by_learning_task_node(project_id, node_id))
        }
        if not recall_point_order:
            return tuple()

        items = [
            artifact
            for artifact in self._list_asr_artifacts(project_id)
            if id_canonical_text(artifact.recall_point_id) in recall_point_order
        ]
        items.sort(
            key=lambda art: (
                int(recall_point_order[id_canonical_text(art.recall_point_id)]),
                str(art.provider.value),
                int(art.center_ms),
                int(art.pre_ms),
                int(art.post_ms),
                id_canonical_text(art.asr_artifact_id),
            )
        )
        return tuple(items)

    def get_convergence(self, project_id: str, convergence_id: str) -> Convergence | None:
        row = self._fetchone(
            """
            SELECT convergence_id, seed_range_id, rule_id, review_task_ids_json, state
            FROM convergence_index
            WHERE project_id = %s AND convergence_id = %s
            """,
            (str(project_id), str(convergence_id)),
        )
        if row is None:
            return None
        return self._decode_convergence_index_row(project_id=str(project_id), row=row)

    def get_review_chain(self, project_id: str, review_chain_id: str) -> ReviewChain | None:
        row = self._fetchone(
            """
            SELECT review_chain_id, queue_json, head_index, state
            FROM review_chain_index
            WHERE project_id = %s AND review_chain_id = %s
            """,
            (str(project_id), str(review_chain_id)),
        )
        if row is None:
            return None
        return self._decode_review_chain_index_row(project_id=str(project_id), row=row)

    def get_range_snapshot(self, project_id: str, range_id: str) -> RangeSnapshot | None:
        row = self._fetchone(
            """
            SELECT range_id, recall_point_ids_json
            FROM range_snapshot_index
            WHERE project_id = %s AND range_id = %s
            """,
            (str(project_id), str(range_id)),
        )
        if row is None:
            return None
        return self._decode_range_snapshot_index_row(project_id=str(project_id), row=row)

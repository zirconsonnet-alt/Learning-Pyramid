from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Protocol, runtime_checkable

from backend.models.aggregation_event import AggregationEvent
from backend.models.asr_artifact import AsrArtifact, AsrSegment
from backend.models.audit_log_event import AuditLogEvent
from backend.models.entry_registration import EntryRegistration
from backend.models.enums import (
    AggregationCycleState,
    AggregationEventReason,
    AsrProvider,
    AuditEventKind,
    AuditResultCode,
    ClientRuntimeKind,
    ContentBlockKind,
    ConvergenceState,
    InstancePresence,
    LayerMode,
    MaterialSourceKind,
    MediaAssetKind,
    ProjectState,
    RecallPointState,
    RecallPointReviewResult,
    ReviewChainState,
    ReviewTaskState,
)
from backend.models.instance import Instance
from backend.models.instance_media_binding import InstanceMediaBinding
from backend.models.learning_object_node import LearningObjectContainer, LearningObjectLeaf, LearningObjectNode
from backend.models.learning_task import LearningTask
from backend.models.learning_task_node import LearningTaskContainer, LearningTaskLeaf, LearningTaskNode
from backend.models.layer import Layer
from backend.models.material_allowlist import MaterialAllowlist
from backend.models.media_asset import MediaAsset
from backend.models.project import Project
from backend.models.project_config import ProjectConfig
from backend.models.project_storage_config import ProjectStorageConfig
from backend.models.range_snapshot import RangeSnapshot
from backend.models.recall_point_review_record import RecallPointReviewRecord
from backend.models.review_chain import ReviewChain, ReviewChainItem, ReviewChainItemKind
from backend.models.review_task import ReviewTask
from backend.models.convergence import Convergence
from backend.models.recall_point import Anchor, RecallPoint
from backend.models.rich_content import ContentBlock
from backend.repositories.persistence_interfaces import ProjectSnapshotRecord, SqlUnitOfWork, SystemStateRecord
from backend.repositories.sqlite_persistence import SQLitePersistenceUnitOfWork
from backend.models.types import (
    InstanceId,
    AggregationEventId,
    AsrArtifactId,
    ConvergenceId,
    ConvergenceRuleId,
    LayerId,
    MediaAssetId,
    LearningObjectNodeId,
    LearningTaskId,
    LearningTaskNodeId,
    ProjectId,
    RangeId,
    RecallPointId,
    ReviewChainId,
    ReviewTaskId,
    ReviewTaskQueueId,
    id_canonical_text,
)
from backend.system.persistence_json import (
    SCHEMA_VERSION,
    decode_project_config_payload,
    decode_project_storage_config_payload,
)


@runtime_checkable
class SnapshotStore(Protocol):
    @property
    def location(self) -> Path | None: ...

    def load_snapshot(self) -> dict[str, Any] | None: ...

    def save_snapshot(self, snapshot: dict[str, Any]) -> None: ...

    def save_project_snapshot(
        self,
        *,
        project_id: str,
        project_snapshot: dict[str, Any],
        idgen_counters: dict[str, Any],
        schema_version: int = 1,
    ) -> None: ...

    def healthcheck(self) -> dict[str, object]: ...


@runtime_checkable
class SqlStore(SnapshotStore, Protocol):
    def begin_unit_of_work(self, *, project_id: str | None = None) -> SqlUnitOfWork: ...

    def list_projects_metadata(self, *, active_only: bool = True) -> tuple[Project, ...]: ...

    def get_project_config(self, project_id: str) -> ProjectConfig | None: ...

    def get_project_storage_config(self, project_id: str) -> ProjectStorageConfig | None: ...

    def list_audit_log_events(self, project_id: str) -> tuple[AuditLogEvent, ...]: ...

    def list_instances(self, project_id: str) -> tuple[Instance, ...]: ...

    def get_instance(self, project_id: str, instance_id: str) -> Instance | None: ...

    def list_instance_media_bindings(self, project_id: str) -> tuple[InstanceMediaBinding, ...]: ...

    def get_instance_media_binding(self, project_id: str, instance_id: str) -> InstanceMediaBinding | None: ...

    def list_missing_instance_ids(self, project_id: str) -> tuple[InstanceId, ...]: ...

    def list_recall_point_ids_by_instance(self, project_id: str, instance_id: str) -> tuple[RecallPointId, ...]: ...

    def get_learning_object_node(self, project_id: str, node_id: str) -> LearningObjectNode | None: ...

    def list_learning_object_nodes(self, project_id: str) -> tuple[LearningObjectNode, ...]: ...

    def list_learning_object_root_ids(self, project_id: str) -> tuple[LearningObjectNodeId, ...]: ...

    def get_learning_task_node(self, project_id: str, node_id: str) -> LearningTaskNode | None: ...

    def get_learning_task(self, project_id: str, learning_task_id: str) -> LearningTask | None: ...

    def get_learning_task_entry_registration(self, project_id: str, learning_task_id: str) -> EntryRegistration | None: ...

    def get_learning_task_node_entry_registration(self, project_id: str, node_id: str) -> EntryRegistration | None: ...

    def get_review_chain_entry_registration(self, project_id: str, review_chain_id: str) -> EntryRegistration | None: ...

    def list_learning_task_nodes(self, project_id: str) -> tuple[LearningTaskNode, ...]: ...

    def list_recall_points_by_learning_task_node(self, project_id: str, node_id: str) -> tuple[RecallPoint, ...]: ...

    def list_recall_points_by_learning_object_node(self, project_id: str, node_id: str) -> tuple[RecallPoint, ...]: ...

    def get_review_task_queue(self, project_id: str) -> tuple[ReviewTaskId | None, tuple[ReviewTaskId, ...]] | None: ...

    def get_review_task(self, project_id: str, review_task_id: str) -> ReviewTask | None: ...

    def get_convergence(self, project_id: str, convergence_id: str) -> Convergence | None: ...

    def get_review_chain(self, project_id: str, review_chain_id: str) -> ReviewChain | None: ...

    def get_range_snapshot(self, project_id: str, range_id: str) -> RangeSnapshot | None: ...

    def get_recall_point(self, project_id: str, recall_point_id: str) -> RecallPoint | None: ...

    def list_layers(self, project_id: str) -> tuple[Layer, ...]: ...

    def get_aggregation_queue_current(self, project_id: str, layer_index: int) -> tuple[LearningTaskNodeId, ...] | None: ...

    def list_aggregation_events(self, project_id: str) -> tuple[AggregationEvent, ...]: ...

    def get_asr_artifact(self, project_id: str, asr_artifact_id: str) -> AsrArtifact | None: ...

    def export_asr_by_learning_object_node(self, project_id: str, node_id: str) -> tuple[AsrArtifact, ...]: ...

    def export_asr_by_learning_task_node(self, project_id: str, node_id: str) -> tuple[AsrArtifact, ...]: ...


class JsonSnapshotStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser().resolve()

    @property
    def location(self) -> Path:
        return self._path

    def load_snapshot(self) -> dict[str, Any] | None:
        if not self._path.exists():
            return None
        raw = self._path.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Snapshot must be a JSON object")
        return data

    def save_snapshot(self, snapshot: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

        fd, tmp_name = tempfile.mkstemp(prefix=self._path.name + ".", suffix=".tmp", dir=str(self._path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_name, self._path)
        finally:
            try:
                if os.path.exists(tmp_name):
                    os.remove(tmp_name)
            except Exception:
                pass

    def save_project_snapshot(
        self,
        *,
        project_id: str,
        project_snapshot: dict[str, Any],
        idgen_counters: dict[str, Any],
        schema_version: int = 1,
    ) -> None:
        current = self.load_snapshot()
        projects = {}
        global_llm_settings = None
        if current is not None:
            normalized_current = self._normalize_snapshot(current)
            projects = dict(normalized_current.get("projects", {}))
            global_llm_settings = normalized_current.get("globalLlmSettings")
        projects[str(project_id)] = dict(project_snapshot)
        self.save_snapshot(
            {
                "schemaVersion": int(schema_version),
                "idgenCounters": dict(idgen_counters),
                "globalLlmSettings": global_llm_settings,
                "projects": projects,
            }
        )

    def healthcheck(self) -> dict[str, object]:
        return {"ok": True, "backend": "json", "location": None if self._path is None else self._path.as_posix()}

    @staticmethod
    def _normalize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
        schema_version = int(snapshot.get("schemaVersion", 1))
        idgen_counters = dict(snapshot.get("idgenCounters", {}))
        raw_global_llm_settings = snapshot.get("globalLlmSettings")
        global_llm_settings = dict(raw_global_llm_settings) if isinstance(raw_global_llm_settings, dict) else None
        projects = dict(snapshot.get("projects", {}))
        return {
            "schemaVersion": schema_version,
            "idgenCounters": idgen_counters,
            "globalLlmSettings": global_llm_settings,
            "projects": projects,
        }


class SQLiteSnapshotStore:
    def __init__(self, path: str | Path, *, legacy_json_path: str | Path | None = None) -> None:
        self._path = Path(path).expanduser().resolve()
        self._legacy_json_path = None if legacy_json_path is None else Path(legacy_json_path).expanduser().resolve()
        self._lock = threading.RLock()
        self._init_db()

    @property
    def location(self) -> Path:
        return self._path

    def _connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def healthcheck(self) -> dict[str, object]:
        try:
            conn = self._connect()
            try:
                row = conn.execute("SELECT 1 AS ok").fetchone()
            finally:
                conn.close()
            return {
                "ok": bool(row is not None and int(row["ok"]) == 1),
                "backend": "sqlite",
                "location": self._path.as_posix(),
            }
        except Exception as exc:
            return {
                "ok": False,
                "backend": "sqlite",
                "location": self._path.as_posix(),
                "error": str(exc),
            }

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS system_state (
                        slot INTEGER PRIMARY KEY CHECK (slot = 1),
                        schema_version INTEGER NOT NULL,
                        idgen_counters_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS global_settings_index (
                        settings_key TEXT PRIMARY KEY,
                        payload_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS project_snapshots (
                        project_id TEXT PRIMARY KEY,
                        project_title TEXT NOT NULL,
                        project_state TEXT NOT NULL,
                        created_at_ms INTEGER NOT NULL,
                        deleted_at_ms INTEGER NULL,
                        snapshot_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_project_snapshots_state
                    ON project_snapshots (project_state)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS project_storage_config_index (
                        project_id TEXT PRIMARY KEY,
                        project_root TEXT NOT NULL,
                        learning_object_root TEXT NOT NULL,
                        fs_sync_policy TEXT NOT NULL,
                        updated_at_ms INTEGER NOT NULL,
                        FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS project_config_index (
                        project_id TEXT PRIMARY KEY,
                        updated_at_ms INTEGER NOT NULL,
                        config_json TEXT NOT NULL,
                        FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS instance_index (
                        project_id TEXT NOT NULL,
                        instance_id TEXT NOT NULL,
                        material_id TEXT NOT NULL,
                        material_display_name TEXT NOT NULL,
                        presence TEXT NULL,
                        last_seen_at_ms INTEGER NULL,
                        PRIMARY KEY (project_id, instance_id),
                        FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_instance_index_project
                    ON instance_index (project_id)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS instance_media_binding_index (
                        project_id TEXT NOT NULL,
                        instance_id TEXT NOT NULL,
                        source_kind TEXT NOT NULL,
                        playback_kind TEXT NOT NULL DEFAULT 'FILE',
                        account_id TEXT,
                        remote_file_id TEXT,
                        remote_path TEXT,
                        mime_type TEXT,
                        size_bytes INTEGER,
                        duration_ms INTEGER,
                        source_payload_json TEXT NOT NULL DEFAULT '{}',
                        updated_at_ms INTEGER NOT NULL,
                        PRIMARY KEY (project_id, instance_id),
                        FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE,
                        FOREIGN KEY(project_id, instance_id) REFERENCES instance_index(project_id, instance_id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_instance_media_binding_index_project
                    ON instance_media_binding_index (project_id, source_kind, updated_at_ms DESC)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS learning_object_node_index (
                        project_id TEXT NOT NULL,
                        node_id TEXT NOT NULL,
                        node_kind TEXT NOT NULL,
                        source TEXT NOT NULL,
                        relative_path TEXT NOT NULL,
                        parent_id TEXT NULL,
                        instance_id TEXT NULL,
                        title TEXT NOT NULL,
                        child_count INTEGER NOT NULL,
                        children_json TEXT NULL,
                        PRIMARY KEY (project_id, node_id),
                        FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_learning_object_node_index_project
                    ON learning_object_node_index (project_id)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS recall_point_index (
                        project_id TEXT NOT NULL,
                        recall_point_id TEXT NOT NULL,
                        created_at_ms INTEGER NOT NULL,
                        anchor_instance_id TEXT NOT NULL,
                        anchor_position TEXT NOT NULL,
                        question_plain_text TEXT NOT NULL,
                        answer_plain_text TEXT NOT NULL,
                        insights_count INTEGER NOT NULL,
                        payload_json TEXT NULL,
                        PRIMARY KEY (project_id, recall_point_id),
                        FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_recall_point_index_project
                    ON recall_point_index (project_id)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS learning_task_index (
                        project_id TEXT NOT NULL,
                        learning_task_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        recall_point_ids_json TEXT NOT NULL,
                        recall_point_count INTEGER NOT NULL,
                        PRIMARY KEY (project_id, learning_task_id),
                        FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_learning_task_index_project
                    ON learning_task_index (project_id)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS learning_task_node_index (
                        project_id TEXT NOT NULL,
                        node_id TEXT NOT NULL,
                        node_kind TEXT NOT NULL,
                        parent_id TEXT NULL,
                        bound_learning_task_id TEXT NULL,
                        title TEXT NOT NULL,
                        child_count INTEGER NOT NULL,
                        children_json TEXT NULL,
                        PRIMARY KEY (project_id, node_id),
                        FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_learning_task_node_index_project
                    ON learning_task_node_index (project_id)
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_learning_task_node_index_bound_task
                    ON learning_task_node_index (project_id, bound_learning_task_id)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS entry_registration_index (
                        project_id TEXT NOT NULL,
                        entry_node TEXT NOT NULL,
                        target_layer_index INTEGER NOT NULL,
                        review_chain_id TEXT NOT NULL,
                        registration_seq INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY (project_id, entry_node),
                        FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_entry_registration_index_project
                    ON entry_registration_index (project_id)
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_entry_registration_index_review_chain
                    ON entry_registration_index (project_id, review_chain_id)
                    """
                )
                self._ensure_column(
                    conn,
                    "entry_registration_index",
                    "registration_seq",
                    "INTEGER NOT NULL DEFAULT 0",
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS range_snapshot_index (
                        project_id TEXT NOT NULL,
                        range_id TEXT NOT NULL,
                        recall_point_ids_json TEXT NOT NULL,
                        recall_point_count INTEGER NOT NULL,
                        PRIMARY KEY (project_id, range_id),
                        FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_range_snapshot_index_project
                    ON range_snapshot_index (project_id)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS review_task_index (
                        project_id TEXT NOT NULL,
                        review_task_id TEXT NOT NULL,
                        input_range_id TEXT NOT NULL,
                        created_at_ms INTEGER NOT NULL,
                        state TEXT NOT NULL,
                        executed_at_ms INTEGER NULL,
                        result_range_id TEXT NULL,
                        PRIMARY KEY (project_id, review_task_id),
                        FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_review_task_index_project
                    ON review_task_index (project_id)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS convergence_index (
                        project_id TEXT NOT NULL,
                        convergence_id TEXT NOT NULL,
                        seed_range_id TEXT NOT NULL,
                        rule_id TEXT NOT NULL,
                        review_task_ids_json TEXT NOT NULL,
                        round_count INTEGER NOT NULL,
                        state TEXT NOT NULL,
                        PRIMARY KEY (project_id, convergence_id),
                        FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_convergence_index_project
                    ON convergence_index (project_id)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS review_chain_index (
                        project_id TEXT NOT NULL,
                        review_chain_id TEXT NOT NULL,
                        queue_json TEXT NOT NULL,
                        queue_length INTEGER NOT NULL,
                        head_index INTEGER NOT NULL,
                        state TEXT NOT NULL,
                        PRIMARY KEY (project_id, review_chain_id),
                        FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_review_chain_index_project
                    ON review_chain_index (project_id)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS review_task_queue_index (
                        project_id TEXT PRIMARY KEY,
                        queue_id TEXT NOT NULL,
                        review_task_ids_json TEXT NOT NULL,
                        head_index INTEGER NOT NULL,
                        FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS layer_state_index (
                        project_id TEXT NOT NULL,
                        layer_id TEXT NOT NULL,
                        layer_index INTEGER NOT NULL,
                        layer_mode TEXT NOT NULL,
                        orchestrator_managed_review_chain_ids_json TEXT NOT NULL,
                        aggregation_k_node INTEGER NOT NULL DEFAULT 8,
                        aggregation_k_point INTEGER NOT NULL DEFAULT 64,
                        aggregation_cycle_state TEXT NOT NULL DEFAULT 'DONE',
                        pending_roll_up_parent_node_id TEXT NULL,
                        normal_tick_quota_remaining INTEGER NOT NULL DEFAULT 1,
                        PRIMARY KEY (project_id, layer_id),
                        FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_layer_state_index_project_layer_index
                    ON layer_state_index (project_id, layer_index)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audit_log_event_index (
                        project_id TEXT NOT NULL,
                        event_id TEXT NOT NULL,
                        occurred_at_ms INTEGER NOT NULL,
                        kind TEXT NOT NULL,
                        api_name TEXT NOT NULL,
                        result TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        PRIMARY KEY (project_id, event_id),
                        FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_audit_log_event_index_project
                    ON audit_log_event_index (project_id, occurred_at_ms, event_id)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS asr_artifact_index (
                        project_id TEXT NOT NULL,
                        asr_artifact_id TEXT NOT NULL,
                        created_at_ms INTEGER NOT NULL,
                        provider TEXT NOT NULL,
                        recall_point_id TEXT NOT NULL,
                        source_instance_id TEXT NOT NULL,
                        center_ms INTEGER NOT NULL,
                        pre_ms INTEGER NOT NULL,
                        post_ms INTEGER NOT NULL,
                        segments_json TEXT NOT NULL,
                        PRIMARY KEY (project_id, asr_artifact_id),
                        FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_asr_artifact_index_project
                    ON asr_artifact_index (project_id, recall_point_id)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS aggregation_queue_index (
                        project_id TEXT NOT NULL,
                        layer_index INTEGER NOT NULL,
                        node_ids_json TEXT NOT NULL,
                        head_index INTEGER NOT NULL,
                        PRIMARY KEY (project_id, layer_index),
                        FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS aggregation_event_index (
                        project_id TEXT NOT NULL,
                        event_id TEXT NOT NULL,
                        created_at_ms INTEGER NOT NULL,
                        layer_index INTEGER NOT NULL,
                        parent_node_id TEXT NOT NULL,
                        child_node_ids_json TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        title TEXT NULL,
                        PRIMARY KEY (project_id, event_id),
                        FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_aggregation_event_index_project
                    ON aggregation_event_index (project_id, event_id)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS material_allowlist_index (
                        project_id TEXT PRIMARY KEY,
                        allowlist_id TEXT NOT NULL,
                        material_ids_json TEXT NOT NULL,
                        material_count INTEGER NOT NULL,
                        FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS media_asset_index (
                        project_id TEXT NOT NULL,
                        asset_id TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        relative_path TEXT NOT NULL,
                        created_at_ms INTEGER NOT NULL,
                        mime_type TEXT NULL,
                        PRIMARY KEY (project_id, asset_id),
                        FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_media_asset_index_project
                    ON media_asset_index (project_id)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS recall_point_review_record_index (
                        project_id TEXT NOT NULL,
                        record_id TEXT NOT NULL,
                        recall_point_id TEXT NOT NULL,
                        review_task_id TEXT NOT NULL,
                        occurred_at_ms INTEGER NOT NULL,
                        result TEXT NOT NULL,
                        PRIMARY KEY (project_id, record_id),
                        FOREIGN KEY(project_id) REFERENCES project_snapshots(project_id) ON DELETE CASCADE
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_recall_point_review_record_index_project
                    ON recall_point_review_record_index (project_id, occurred_at_ms, record_id)
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS snapshot_state (
                        slot INTEGER PRIMARY KEY CHECK (slot = 1),
                        snapshot_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                self._ensure_column(conn, "recall_point_index", "payload_json", "TEXT NULL")
                self._ensure_column(conn, "layer_state_index", "aggregation_k_node", "INTEGER NOT NULL DEFAULT 8")
                self._ensure_column(conn, "layer_state_index", "aggregation_k_point", "INTEGER NOT NULL DEFAULT 64")
                self._ensure_column(
                    conn,
                    "layer_state_index",
                    "aggregation_cycle_state",
                    "TEXT NOT NULL DEFAULT 'DONE'",
                )
                self._ensure_column(conn, "layer_state_index", "pending_roll_up_parent_node_id", "TEXT NULL")
                self._ensure_column(
                    conn,
                    "layer_state_index",
                    "normal_tick_quota_remaining",
                    "INTEGER NOT NULL DEFAULT 1",
                )
                conn.commit()
            finally:
                conn.close()

    @staticmethod
    def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_sql: str) -> None:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing = {str(row["name"]) for row in rows}
        if column_name in existing:
            return
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")

    @staticmethod
    def _material_display_name(material_id: str) -> str:
        path = PurePosixPath(str(material_id or "").strip())
        return path.name or path.as_posix()

    @staticmethod
    def _decode_audit_event_kind(raw: object) -> AuditEventKind:
        value = str(raw)
        legacy_map = {
            "CREATE_LLM_SESSION": AuditEventKind.EDIT_PROJECT_CONFIG,
            "LLM_CHAT_TURN": AuditEventKind.EDIT_PROJECT_CONFIG,
            "CLOSE_LLM_SESSION": AuditEventKind.EDIT_PROJECT_CONFIG,
        }
        if value in legacy_map:
            return legacy_map[value]
        return AuditEventKind(value)

    @staticmethod
    def _rich_content_to_plain_text(raw: object) -> str:
        items = list(raw) if isinstance(raw, (list, tuple)) else []
        parts: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("kind", "")).strip().upper()
            if kind == "TEXT":
                text = str(item.get("text", "")).strip().replace("\n", " ")
                if text:
                    parts.append(text)
            elif kind == "IMAGE":
                parts.append("[IMAGE]")
        return " ".join(parts).strip()

    @staticmethod
    def _decode_content_block(raw: dict[str, Any]) -> ContentBlock:
        kind = ContentBlockKind(str(raw.get("kind", "")))
        if kind == ContentBlockKind.TEXT:
            return ContentBlock(kind=kind, text=str(raw.get("text", "")))
        return ContentBlock(kind=kind, asset_id=None if raw.get("assetId") is None else str(raw.get("assetId")))

    @classmethod
    def _decode_rich_content(cls, raw: object) -> tuple[ContentBlock, ...]:
        items = list(raw) if isinstance(raw, (list, tuple)) else []
        return tuple(cls._decode_content_block(dict(item)) for item in items if isinstance(item, dict))

    @classmethod
    def _decode_recall_point(cls, *, project_id: str, raw: dict[str, Any]) -> RecallPoint:
        raw_anchor = raw.get("anchor")
        anchor_payload = None if raw_anchor is None else dict(raw_anchor)
        return RecallPoint(
            project_id=ProjectId(str(project_id)),
            recall_point_id=RecallPointId(str(raw.get("recallPointId"))),
            created_at=cls._ms_to_ts(int(raw.get("createdAtMs", 0))),
            question=cls._decode_rich_content(raw.get("question")),
            answer=cls._decode_rich_content(raw.get("answer")),
            anchor=None
            if anchor_payload is None
            else Anchor(
                instance_id=InstanceId(str(anchor_payload.get("instanceId", ""))),
                position=str(anchor_payload.get("position", "")),
            ),
            insights=tuple(cls._decode_rich_content(item) for item in list(raw.get("insights", []))),
            state=RecallPointState(str(raw.get("state", RecallPointState.ACTIVE.value))),
            deleted_at=cls._ms_to_ts(None if raw.get("deletedAtMs") is None else int(raw.get("deletedAtMs"))),
        )

    @classmethod
    def _decode_instance_media_binding(cls, *, project_id: str, row: sqlite3.Row) -> InstanceMediaBinding:
        payload_json = str(row["source_payload_json"]) if row["source_payload_json"] is not None else "{}"
        payload = json.loads(payload_json)
        if not isinstance(payload, dict):
            raise ValueError("InstanceMediaBinding.source_payload_json must decode to a JSON object")
        return InstanceMediaBinding.create(
            ProjectId(str(project_id)),
            InstanceId(str(row["instance_id"])),
            source_kind=MaterialSourceKind(str(row["source_kind"])),
            playback_kind=str(row["playback_kind"] or "FILE"),
            account_id=None if row["account_id"] is None else str(row["account_id"]),
            remote_file_id=None if row["remote_file_id"] is None else str(row["remote_file_id"]),
            remote_path=None if row["remote_path"] is None else str(row["remote_path"]),
            mime_type=None if row["mime_type"] is None else str(row["mime_type"]),
            size_bytes=None if row["size_bytes"] is None else int(row["size_bytes"]),
            duration_ms=None if row["duration_ms"] is None else int(row["duration_ms"]),
            source_payload=payload,
            updated_at=cls._ms_to_ts(int(row["updated_at_ms"])),
        )

    def _refresh_project_entity_indexes(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        project_payload: dict[str, Any],
    ) -> None:
        conn.execute("DELETE FROM project_storage_config_index WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM project_config_index WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM instance_index WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM instance_media_binding_index WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM learning_object_node_index WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM recall_point_index WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM learning_task_index WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM learning_task_node_index WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM entry_registration_index WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM range_snapshot_index WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM review_task_index WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM convergence_index WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM review_chain_index WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM review_task_queue_index WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM layer_state_index WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM audit_log_event_index WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM asr_artifact_index WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM aggregation_queue_index WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM aggregation_event_index WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM material_allowlist_index WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM media_asset_index WHERE project_id = ?", (project_id,))
        conn.execute("DELETE FROM recall_point_review_record_index WHERE project_id = ?", (project_id,))

        storage_config = project_payload.get("projectStorageConfig")
        if isinstance(storage_config, dict):
            conn.execute(
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
                    str(storage_config.get("projectRoot", "")),
                    str(storage_config.get("learningObjectRoot", "learning_objects")),
                    str(storage_config.get("fsSyncPolicy", "")),
                    int(storage_config.get("updatedAtMs", 0)),
                ),
            )

        project_config = project_payload.get("projectConfig")
        if isinstance(project_config, dict):
            conn.execute(
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
                    int(project_config.get("updatedAtMs", 0)),
                    json.dumps(project_config, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                ),
            )

        for instance_id, raw_instance in dict(project_payload.get("instances", {})).items():
            instance_payload = dict(raw_instance)
            material_id = str(instance_payload.get("materialId", ""))
            conn.execute(
                """
                INSERT INTO instance_index (
                    project_id,
                    instance_id,
                    material_id,
                    material_display_name,
                    presence,
                    last_seen_at_ms
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    str(instance_id),
                    material_id,
                    self._material_display_name(material_id),
                    None if instance_payload.get("presence") is None else str(instance_payload.get("presence")),
                    None if instance_payload.get("lastSeenAtMs") is None else int(instance_payload.get("lastSeenAtMs")),
                ),
            )

        for instance_id, raw_binding in dict(project_payload.get("instanceMediaBindings", {})).items():
            binding_payload = dict(raw_binding)
            source_payload = dict(binding_payload.get("sourcePayload", {}))
            conn.execute(
                """
                INSERT INTO instance_media_binding_index (
                    project_id,
                    instance_id,
                    source_kind,
                    playback_kind,
                    account_id,
                    remote_file_id,
                    remote_path,
                    mime_type,
                    size_bytes,
                    duration_ms,
                    source_payload_json,
                    updated_at_ms
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    str(instance_id),
                    str(binding_payload.get("sourceKind", MaterialSourceKind.SERVER_FS.value)),
                    str(binding_payload.get("playbackKind", "FILE")),
                    None if binding_payload.get("accountId") is None else str(binding_payload.get("accountId")),
                    None if binding_payload.get("remoteFileId") is None else str(binding_payload.get("remoteFileId")),
                    None if binding_payload.get("remotePath") is None else str(binding_payload.get("remotePath")),
                    None if binding_payload.get("mimeType") is None else str(binding_payload.get("mimeType")),
                    None if binding_payload.get("sizeBytes") is None else int(binding_payload.get("sizeBytes")),
                    None if binding_payload.get("durationMs") is None else int(binding_payload.get("durationMs")),
                    json.dumps(source_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                    int(binding_payload.get("updatedAtMs", 0)),
                ),
            )

        for node_id, raw_node in dict(project_payload.get("learningObjectNodes", {})).items():
            node_payload = dict(raw_node)
            children = list(node_payload.get("children", []))
            conn.execute(
                """
                INSERT INTO learning_object_node_index (
                    project_id,
                    node_id,
                    node_kind,
                    source,
                    relative_path,
                    parent_id,
                    instance_id,
                    title,
                    child_count,
                    children_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    str(node_id),
                    str(node_payload.get("kind", "")),
                    str(node_payload.get("source", "")),
                    str(node_payload.get("relativePath", "")),
                    None if node_payload.get("parentId") is None else str(node_payload.get("parentId")),
                    None if node_payload.get("instanceId") is None else str(node_payload.get("instanceId")),
                    str(node_payload.get("title", "")),
                    len(children),
                    None if not children else json.dumps(children, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                ),
            )

        for recall_point_id, raw_recall_point in dict(project_payload.get("recallPoints", {})).items():
            recall_point_payload = dict(raw_recall_point)
            raw_anchor_payload = recall_point_payload.get("anchor")
            anchor_payload = None if raw_anchor_payload is None else dict(raw_anchor_payload)
            conn.execute(
                """
                INSERT INTO recall_point_index (
                    project_id,
                    recall_point_id,
                    created_at_ms,
                    anchor_instance_id,
                    anchor_position,
                    question_plain_text,
                    answer_plain_text,
                    insights_count,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    str(recall_point_id),
                    int(recall_point_payload.get("createdAtMs", 0)),
                    "" if anchor_payload is None else str(anchor_payload.get("instanceId", "")),
                    "" if anchor_payload is None else str(anchor_payload.get("position", "")),
                    self._rich_content_to_plain_text(recall_point_payload.get("question")),
                    self._rich_content_to_plain_text(recall_point_payload.get("answer")),
                    len(list(recall_point_payload.get("insights", []))),
                    json.dumps(recall_point_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                ),
            )

        for learning_task_id, raw_learning_task in dict(project_payload.get("learningTasks", {})).items():
            learning_task_payload = dict(raw_learning_task)
            recall_point_ids = list(learning_task_payload.get("recallPointIds", []))
            conn.execute(
                """
                INSERT INTO learning_task_index (
                    project_id,
                    learning_task_id,
                    title,
                    recall_point_ids_json,
                    recall_point_count
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    str(learning_task_id),
                    str(learning_task_payload.get("title", "")),
                    json.dumps(recall_point_ids, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                    len(recall_point_ids),
                ),
            )

        for node_id, raw_node in dict(project_payload.get("learningTaskNodes", {})).items():
            node_payload = dict(raw_node)
            children = list(node_payload.get("children", []))
            conn.execute(
                """
                INSERT INTO learning_task_node_index (
                    project_id,
                    node_id,
                    node_kind,
                    parent_id,
                    bound_learning_task_id,
                    title,
                    child_count,
                    children_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    str(node_id),
                    str(node_payload.get("kind", "")),
                    None if node_payload.get("parentId") is None else str(node_payload.get("parentId")),
                    None
                    if node_payload.get("boundLearningTaskId") is None
                    else str(node_payload.get("boundLearningTaskId")),
                    str(node_payload.get("title", "")),
                    len(children),
                    None if not children else json.dumps(children, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                ),
            )

        for entry_node, raw_entry_reg in dict(project_payload.get("entryRegs", {})).items():
            entry_reg_payload = dict(raw_entry_reg)
            conn.execute(
                """
                INSERT INTO entry_registration_index (
                    project_id,
                    entry_node,
                    target_layer_index,
                    review_chain_id,
                    registration_seq
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    str(entry_node),
                    int(entry_reg_payload.get("targetLayerIndex", 0)),
                    str(entry_reg_payload.get("reviewChainId", "")),
                    int(entry_reg_payload.get("registrationSeq", 0)),
                ),
            )

        for range_id, raw_range_snapshot in dict(project_payload.get("rangeSnapshots", {})).items():
            range_snapshot_payload = dict(raw_range_snapshot)
            recall_point_ids = list(range_snapshot_payload.get("recallPointIds", []))
            conn.execute(
                """
                INSERT INTO range_snapshot_index (
                    project_id,
                    range_id,
                    recall_point_ids_json,
                    recall_point_count
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    project_id,
                    str(range_id),
                    json.dumps(recall_point_ids, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                    len(recall_point_ids),
                ),
            )

        for review_task_id, raw_review_task in dict(project_payload.get("reviewTasks", {})).items():
            review_task_payload = dict(raw_review_task)
            conn.execute(
                """
                INSERT INTO review_task_index (
                    project_id,
                    review_task_id,
                    input_range_id,
                    created_at_ms,
                    state,
                    executed_at_ms,
                    result_range_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    str(review_task_id),
                    str(review_task_payload.get("inputRangeId", "")),
                    int(review_task_payload.get("createdAtMs", 0)),
                    str(review_task_payload.get("state", "")),
                    None if review_task_payload.get("executedAtMs") is None else int(review_task_payload.get("executedAtMs")),
                    None if review_task_payload.get("resultRangeId") is None else str(review_task_payload.get("resultRangeId")),
                ),
            )

        for convergence_id, raw_convergence in dict(project_payload.get("convergences", {})).items():
            convergence_payload = dict(raw_convergence)
            review_task_ids = list(convergence_payload.get("reviewTaskIds", []))
            conn.execute(
                """
                INSERT INTO convergence_index (
                    project_id,
                    convergence_id,
                    seed_range_id,
                    rule_id,
                    review_task_ids_json,
                    round_count,
                    state
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    str(convergence_id),
                    str(convergence_payload.get("seedRangeId", "")),
                    str(convergence_payload.get("ruleId", "")),
                    json.dumps(review_task_ids, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                    len(review_task_ids),
                    str(convergence_payload.get("state", "")),
                ),
            )

        for review_chain_id, raw_review_chain in dict(project_payload.get("reviewChains", {})).items():
            review_chain_payload = dict(raw_review_chain)
            queue_payload = list(review_chain_payload.get("queue", []))
            conn.execute(
                """
                INSERT INTO review_chain_index (
                    project_id,
                    review_chain_id,
                    queue_json,
                    queue_length,
                    head_index,
                    state
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    str(review_chain_id),
                    json.dumps(queue_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                    len(queue_payload),
                    int(review_chain_payload.get("headIndex", 0)),
                    str(review_chain_payload.get("state", "")),
                ),
            )

        review_task_queue = project_payload.get("reviewTaskQueue")
        if isinstance(review_task_queue, dict):
            review_task_ids = list(review_task_queue.get("reviewTaskIds", []))
            conn.execute(
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
                    str(review_task_queue.get("queueId", "")),
                    json.dumps(review_task_ids, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                    int(review_task_queue.get("headIndex", 0)),
                ),
            )

        for layer_id, raw_layer in dict(project_payload.get("layers", {})).items():
            layer_payload = dict(raw_layer)
            managed_review_chain_ids = list(layer_payload.get("orchestratorManagedReviewChainIds", []))
            layer_index = int(layer_payload.get("layerIndex", 0))
            aggregation_k_node = int(dict(project_payload.get("aggregationKNode", {})).get(str(layer_index), 8))
            aggregation_k_point = int(dict(project_payload.get("aggregationKPoint", {})).get(str(layer_index), 64))
            aggregation_cycle_state = str(
                dict(project_payload.get("aggregationCycleState", {})).get(str(layer_index), "DONE")
            )
            pending_roll_up_parent_node_id = dict(project_payload.get("pendingRollUpParentNodeId", {})).get(str(layer_index))
            normal_tick_quota_remaining = int(
                dict(project_payload.get("normalTickQuotaRemaining", {})).get(str(layer_index), 1)
            )
            conn.execute(
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
                    project_id,
                    str(layer_id),
                    layer_index,
                    str(layer_payload.get("layerMode", "")),
                    json.dumps(managed_review_chain_ids, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                    aggregation_k_node,
                    aggregation_k_point,
                    aggregation_cycle_state,
                    None if pending_roll_up_parent_node_id is None else str(pending_roll_up_parent_node_id),
                    normal_tick_quota_remaining,
                ),
            )

        for event_id, raw_event in dict(project_payload.get("auditLogEvents", {})).items():
            audit_event_payload = dict(raw_event)
            conn.execute(
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
                    project_id,
                    str(event_id),
                    int(audit_event_payload.get("occurredAtMs", 0)),
                    str(audit_event_payload.get("kind", "")),
                    str(audit_event_payload.get("apiName", "")),
                    str(audit_event_payload.get("result", "")),
                    str(audit_event_payload.get("payload", "")),
                ),
            )

        for asr_artifact_id, raw_asr_artifact in dict(project_payload.get("asrArtifacts", {})).items():
            asr_artifact_payload = dict(raw_asr_artifact)
            conn.execute(
                """
                INSERT INTO asr_artifact_index (
                    project_id,
                    asr_artifact_id,
                    created_at_ms,
                    provider,
                    recall_point_id,
                    source_instance_id,
                    center_ms,
                    pre_ms,
                    post_ms,
                    segments_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    str(asr_artifact_id),
                    int(asr_artifact_payload.get("createdAtMs", 0)),
                    str(asr_artifact_payload.get("provider", "")),
                    str(asr_artifact_payload.get("recallPointId", "")),
                    str(asr_artifact_payload.get("sourceInstanceId", "")),
                    int(asr_artifact_payload.get("centerMs", 0)),
                    int(asr_artifact_payload.get("preMs", 0)),
                    int(asr_artifact_payload.get("postMs", 0)),
                    json.dumps(
                        list(asr_artifact_payload.get("segments", [])),
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                ),
            )

        for layer_index, raw_aggregation_queue in dict(project_payload.get("aggregationQueues", {})).items():
            aggregation_queue_payload = dict(raw_aggregation_queue)
            node_ids = list(aggregation_queue_payload.get("nodeIds", []))
            conn.execute(
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
                    project_id,
                    int(layer_index),
                    json.dumps(node_ids, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                    int(aggregation_queue_payload.get("headIndex", 0)),
                ),
            )

        for event_id, raw_aggregation_event in dict(project_payload.get("aggregationEvents", {})).items():
            aggregation_event_payload = dict(raw_aggregation_event)
            child_node_ids = list(aggregation_event_payload.get("childNodeIds", []))
            conn.execute(
                """
                INSERT INTO aggregation_event_index (
                    project_id,
                    event_id,
                    created_at_ms,
                    layer_index,
                    parent_node_id,
                    child_node_ids_json,
                    reason,
                    title
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    str(event_id),
                    int(aggregation_event_payload.get("createdAtMs", 0)),
                    int(aggregation_event_payload.get("layerIndex", 0)),
                    str(aggregation_event_payload.get("parentNodeId", "")),
                    json.dumps(child_node_ids, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                    str(aggregation_event_payload.get("reason", "")),
                    None if aggregation_event_payload.get("title") is None else str(aggregation_event_payload.get("title")),
                ),
            )

        material_allowlist = project_payload.get("materialAllowlist")
        if isinstance(material_allowlist, dict):
            material_ids = list(material_allowlist.get("materialIds", []))
            conn.execute(
                """
                INSERT INTO material_allowlist_index (
                    project_id,
                    allowlist_id,
                    material_ids_json,
                    material_count
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    project_id,
                    str(material_allowlist.get("allowlistId", "")),
                    json.dumps(material_ids, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                    len(material_ids),
                ),
            )

        for asset_id, raw_media_asset in dict(project_payload.get("mediaAssets", {})).items():
            media_asset_payload = dict(raw_media_asset)
            conn.execute(
                """
                INSERT INTO media_asset_index (
                    project_id,
                    asset_id,
                    kind,
                    relative_path,
                    created_at_ms,
                    mime_type
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    str(asset_id),
                    str(media_asset_payload.get("kind", "")),
                    str(media_asset_payload.get("relativePath", "")),
                    int(media_asset_payload.get("createdAtMs", 0)),
                    None if media_asset_payload.get("mimeType") is None else str(media_asset_payload.get("mimeType")),
                ),
            )

        for record_id, raw_review_record in dict(project_payload.get("recallPointReviewRecords", {})).items():
            review_record_payload = dict(raw_review_record)
            conn.execute(
                """
                INSERT INTO recall_point_review_record_index (
                    project_id,
                    record_id,
                    recall_point_id,
                    review_task_id,
                    occurred_at_ms,
                    result
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project_id,
                    str(record_id),
                    str(review_record_payload.get("recallPointId", "")),
                    str(review_record_payload.get("reviewTaskId", "")),
                    int(review_record_payload.get("occurredAtMs", 0)),
                    str(review_record_payload.get("result", "")),
                ),
            )

    @staticmethod
    def _strip_externalized_project_payload(project_payload: dict[str, Any]) -> dict[str, Any]:
        # `project_snapshots.snapshot_json` is kept only as a compatibility/export shell.
        # The authoritative project facts now live in normalized index tables.
        raw = dict(project_payload)
        raw.pop("instances", None)
        raw.pop("instanceMediaBindings", None)
        raw.pop("learningObjectNodes", None)
        raw.pop("recallPoints", None)
        raw.pop("learningTasks", None)
        raw.pop("learningTaskNodes", None)
        raw.pop("entryRegs", None)
        raw.pop("rangeSnapshots", None)
        raw.pop("reviewTasks", None)
        raw.pop("convergences", None)
        raw.pop("reviewChains", None)
        raw.pop("reviewTaskQueue", None)
        raw.pop("layers", None)
        raw.pop("layersByIndex", None)
        raw.pop("auditLogEvents", None)
        raw.pop("asrArtifacts", None)
        raw.pop("aggregationQueues", None)
        raw.pop("aggregationEvents", None)
        raw.pop("materialAllowlist", None)
        raw.pop("mediaAssets", None)
        raw.pop("recallPointReviewRecords", None)
        raw.pop("aggregationKNode", None)
        raw.pop("aggregationKPoint", None)
        raw.pop("aggregationCycleState", None)
        raw.pop("pendingRollUpParentNodeId", None)
        raw.pop("normalTickQuotaRemaining", None)
        return raw

    @staticmethod
    def _project_payload_uses_externalized_fields(project_payload: dict[str, Any]) -> bool:
        if dict(project_payload.get("instances", {})):
            return True
        if dict(project_payload.get("learningObjectNodes", {})):
            return True
        if dict(project_payload.get("recallPoints", {})):
            return True
        if dict(project_payload.get("learningTasks", {})):
            return True
        if dict(project_payload.get("learningTaskNodes", {})):
            return True
        if dict(project_payload.get("entryRegs", {})):
            return True
        if dict(project_payload.get("rangeSnapshots", {})):
            return True
        if dict(project_payload.get("reviewTasks", {})):
            return True
        if dict(project_payload.get("convergences", {})):
            return True
        if dict(project_payload.get("reviewChains", {})):
            return True
        if project_payload.get("reviewTaskQueue") is not None:
            return True
        if dict(project_payload.get("layers", {})):
            return True
        if dict(project_payload.get("layersByIndex", {})):
            return True
        if dict(project_payload.get("auditLogEvents", {})):
            return True
        if dict(project_payload.get("asrArtifacts", {})):
            return True
        if dict(project_payload.get("aggregationQueues", {})):
            return True
        if dict(project_payload.get("aggregationEvents", {})):
            return True
        if project_payload.get("materialAllowlist") is not None:
            return True
        if dict(project_payload.get("mediaAssets", {})):
            return True
        if dict(project_payload.get("recallPointReviewRecords", {})):
            return True
        if dict(project_payload.get("aggregationKNode", {})):
            return True
        if dict(project_payload.get("aggregationKPoint", {})):
            return True
        if dict(project_payload.get("aggregationCycleState", {})):
            return True
        if dict(project_payload.get("pendingRollUpParentNodeId", {})):
            return True
        if dict(project_payload.get("normalTickQuotaRemaining", {})):
            return True
        return False

    def _recall_point_payload_from_index_row(
        self,
        *,
        project_id: str,
        row: sqlite3.Row,
        legacy_payloads: dict[str, Any],
    ) -> dict[str, Any]:
        raw_payload = row["payload_json"] if "payload_json" in row.keys() else None
        if raw_payload is not None:
            payload = json.loads(str(raw_payload))
            if isinstance(payload, dict):
                return payload

        legacy_payload = legacy_payloads.get(str(row["recall_point_id"]))
        if isinstance(legacy_payload, dict):
            return dict(legacy_payload)

        return {
            "projectId": str(project_id),
            "recallPointId": str(row["recall_point_id"]),
            "createdAtMs": int(row["created_at_ms"]),
            "state": RecallPointState.ACTIVE.value,
            "deletedAtMs": None,
            "question": [{"kind": "TEXT", "text": str(row["question_plain_text"])}],
            "answer": [{"kind": "TEXT", "text": str(row["answer_plain_text"])}],
            "anchor": None
            if not str(row["anchor_instance_id"] or "").strip() and not str(row["anchor_position"] or "").strip()
            else {
                "instanceId": str(row["anchor_instance_id"]),
                "position": str(row["anchor_position"]),
            },
            "insights": [],
        }

    @staticmethod
    def _learning_task_payload_from_index_row(*, project_id: str, row: sqlite3.Row) -> dict[str, Any]:
        raw_recall_point_ids = str(row["recall_point_ids_json"]) if row["recall_point_ids_json"] is not None else "[]"
        return {
            "projectId": str(project_id),
            "learningTaskId": str(row["learning_task_id"]),
            "recallPointIds": list(json.loads(raw_recall_point_ids)),
            "title": str(row["title"]),
        }

    @staticmethod
    def _learning_task_node_payload_from_index_row(*, project_id: str, row: sqlite3.Row) -> dict[str, Any]:
        kind = str(row["node_kind"])
        payload: dict[str, Any] = {
            "kind": kind,
            "projectId": str(project_id),
            "nodeId": str(row["node_id"]),
            "parentId": None if row["parent_id"] is None else str(row["parent_id"]),
            "title": str(row["title"]),
        }
        if kind == "LEAF":
            payload["boundLearningTaskId"] = str(row["bound_learning_task_id"])
        else:
            children_raw = str(row["children_json"]) if row["children_json"] is not None else "[]"
            payload["children"] = list(json.loads(children_raw))
        return payload

    @staticmethod
    def _entry_registration_payload_from_index_row(*, project_id: str, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "projectId": str(project_id),
            "entryNode": str(row["entry_node"]),
            "targetLayerIndex": int(row["target_layer_index"]),
            "reviewChainId": str(row["review_chain_id"]),
            "registrationSeq": int(row["registration_seq"]),
        }

    @staticmethod
    def _range_snapshot_payload_from_index_row(*, project_id: str, row: sqlite3.Row) -> dict[str, Any]:
        raw_recall_point_ids = str(row["recall_point_ids_json"]) if row["recall_point_ids_json"] is not None else "[]"
        return {
            "projectId": str(project_id),
            "rangeId": str(row["range_id"]),
            "recallPointIds": list(json.loads(raw_recall_point_ids)),
        }

    @staticmethod
    def _review_task_payload_from_index_row(*, project_id: str, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "projectId": str(project_id),
            "reviewTaskId": str(row["review_task_id"]),
            "inputRangeId": str(row["input_range_id"]),
            "createdAtMs": int(row["created_at_ms"]),
            "state": str(row["state"]),
            "executedAtMs": None if row["executed_at_ms"] is None else int(row["executed_at_ms"]),
            "resultRangeId": None if row["result_range_id"] is None else str(row["result_range_id"]),
        }

    @staticmethod
    def _convergence_payload_from_index_row(*, project_id: str, row: sqlite3.Row) -> dict[str, Any]:
        raw_review_task_ids = str(row["review_task_ids_json"]) if row["review_task_ids_json"] is not None else "[]"
        return {
            "projectId": str(project_id),
            "convergenceId": str(row["convergence_id"]),
            "seedRangeId": str(row["seed_range_id"]),
            "ruleId": str(row["rule_id"]),
            "reviewTaskIds": list(json.loads(raw_review_task_ids)),
            "state": str(row["state"]),
        }

    @staticmethod
    def _review_chain_payload_from_index_row(*, project_id: str, row: sqlite3.Row) -> dict[str, Any]:
        raw_queue = str(row["queue_json"]) if row["queue_json"] is not None else "[]"
        return {
            "projectId": str(project_id),
            "reviewChainId": str(row["review_chain_id"]),
            "queue": list(json.loads(raw_queue)),
            "headIndex": int(row["head_index"]),
            "state": str(row["state"]),
        }

    @staticmethod
    def _review_task_queue_payload_from_index_row(*, project_id: str, row: sqlite3.Row) -> dict[str, Any]:
        raw_review_task_ids = str(row["review_task_ids_json"]) if row["review_task_ids_json"] is not None else "[]"
        return {
            "projectId": str(project_id),
            "queueId": str(row["queue_id"]),
            "reviewTaskIds": list(json.loads(raw_review_task_ids)),
            "headIndex": int(row["head_index"]),
        }

    @staticmethod
    def _layer_payload_from_index_row(*, project_id: str, row: sqlite3.Row) -> dict[str, Any]:
        raw_review_chain_ids = (
            str(row["orchestrator_managed_review_chain_ids_json"])
            if row["orchestrator_managed_review_chain_ids_json"] is not None
            else "[]"
        )
        return {
            "projectId": str(project_id),
            "layerId": str(row["layer_id"]),
            "layerIndex": int(row["layer_index"]),
            "layerMode": str(row["layer_mode"]),
            "orchestratorManagedReviewChainIds": list(json.loads(raw_review_chain_ids)),
            "aggregationKNode": int(row["aggregation_k_node"]),
            "aggregationKPoint": int(row["aggregation_k_point"]),
            "aggregationCycleState": str(row["aggregation_cycle_state"]),
            "pendingRollUpParentNodeId": None
            if row["pending_roll_up_parent_node_id"] is None
            else str(row["pending_roll_up_parent_node_id"]),
            "normalTickQuotaRemaining": int(row["normal_tick_quota_remaining"]),
        }

    @staticmethod
    def _audit_log_event_payload_from_index_row(*, project_id: str, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "projectId": str(project_id),
            "eventId": str(row["event_id"]),
            "occurredAtMs": int(row["occurred_at_ms"]),
            "kind": str(row["kind"]),
            "apiName": str(row["api_name"]),
            "result": str(row["result"]),
            "payload": str(row["payload"]),
        }

    @staticmethod
    def _asr_artifact_payload_from_index_row(*, project_id: str, row: sqlite3.Row) -> dict[str, Any]:
        raw_segments = str(row["segments_json"]) if row["segments_json"] is not None else "[]"
        return {
            "projectId": str(project_id),
            "asrArtifactId": str(row["asr_artifact_id"]),
            "createdAtMs": int(row["created_at_ms"]),
            "provider": str(row["provider"]),
            "producerRuntimeKind": ClientRuntimeKind.DESKTOP_NATIVE.value,
            "recallPointId": str(row["recall_point_id"]),
            "sourceInstanceId": str(row["source_instance_id"]),
            "centerMs": int(row["center_ms"]),
            "preMs": int(row["pre_ms"]),
            "postMs": int(row["post_ms"]),
            "segments": list(json.loads(raw_segments)),
        }

    @staticmethod
    def _aggregation_queue_payload_from_index_row(*, project_id: str, row: sqlite3.Row) -> dict[str, Any]:
        raw_node_ids = str(row["node_ids_json"]) if row["node_ids_json"] is not None else "[]"
        return {
            "projectId": str(project_id),
            "layerIndex": int(row["layer_index"]),
            "nodeIds": list(json.loads(raw_node_ids)),
            "headIndex": int(row["head_index"]),
        }

    @staticmethod
    def _aggregation_event_payload_from_index_row(*, project_id: str, row: sqlite3.Row) -> dict[str, Any]:
        raw_child_node_ids = str(row["child_node_ids_json"]) if row["child_node_ids_json"] is not None else "[]"
        return {
            "projectId": str(project_id),
            "eventId": str(row["event_id"]),
            "createdAtMs": int(row["created_at_ms"]),
            "layerIndex": int(row["layer_index"]),
            "parentNodeId": str(row["parent_node_id"]),
            "childNodeIds": list(json.loads(raw_child_node_ids)),
            "reason": str(row["reason"]),
            "title": None if row["title"] is None else str(row["title"]),
        }

    @staticmethod
    def _material_allowlist_payload_from_index_row(*, project_id: str, row: sqlite3.Row) -> dict[str, Any]:
        raw_material_ids = str(row["material_ids_json"]) if row["material_ids_json"] is not None else "[]"
        return {
            "projectId": str(project_id),
            "allowlistId": str(row["allowlist_id"]),
            "materialIds": list(json.loads(raw_material_ids)),
        }

    @staticmethod
    def _media_asset_payload_from_index_row(*, project_id: str, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "projectId": str(project_id),
            "assetId": str(row["asset_id"]),
            "kind": str(row["kind"]),
            "relativePath": str(row["relative_path"]),
            "createdAtMs": int(row["created_at_ms"]),
            "mimeType": None if row["mime_type"] is None else str(row["mime_type"]),
        }

    @staticmethod
    def _recall_point_review_record_payload_from_index_row(*, project_id: str, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "projectId": str(project_id),
            "recordId": str(row["record_id"]),
            "recallPointId": str(row["recall_point_id"]),
            "reviewTaskId": str(row["review_task_id"]),
            "occurredAtMs": int(row["occurred_at_ms"]),
            "result": str(row["result"]),
        }

    @classmethod
    def _decode_learning_task_index_row(cls, *, project_id: str, row: sqlite3.Row) -> LearningTask:
        payload = cls._learning_task_payload_from_index_row(project_id=project_id, row=row)
        return LearningTask(
            project_id=ProjectId(str(project_id)),
            learning_task_id=LearningTaskId(str(payload["learningTaskId"])),
            recall_point_ids=tuple(RecallPointId(str(item)) for item in list(payload["recallPointIds"])),
            title=str(payload["title"]),
        )

    @classmethod
    def _decode_learning_task_node_index_row(cls, *, project_id: str, row: sqlite3.Row) -> LearningTaskNode:
        payload = cls._learning_task_node_payload_from_index_row(project_id=project_id, row=row)
        if str(payload["kind"]) == "LEAF":
            return LearningTaskLeaf(
                project_id=ProjectId(str(project_id)),
                node_id=LearningTaskNodeId(str(payload["nodeId"])),
                parent_id=None if payload.get("parentId") is None else LearningTaskNodeId(str(payload["parentId"])),
                bound_learning_task_id=LearningTaskId(str(payload["boundLearningTaskId"])),
                title=str(payload["title"]),
            )
        return LearningTaskContainer(
            project_id=ProjectId(str(project_id)),
            node_id=LearningTaskNodeId(str(payload["nodeId"])),
            parent_id=None if payload.get("parentId") is None else LearningTaskNodeId(str(payload["parentId"])),
            children=tuple(LearningTaskNodeId(str(item)) for item in list(payload.get("children", []))),
            title=str(payload["title"]),
        )

    @classmethod
    def _decode_entry_registration_index_row(cls, *, project_id: str, row: sqlite3.Row) -> EntryRegistration:
        payload = cls._entry_registration_payload_from_index_row(project_id=project_id, row=row)
        return EntryRegistration(
            project_id=ProjectId(str(project_id)),
            entry_node=LearningTaskNodeId(str(payload["entryNode"])),
            target_layer_index=int(payload["targetLayerIndex"]),
            review_chain_id=ReviewChainId(str(payload["reviewChainId"])),
            registration_seq=int(payload["registrationSeq"]),
        )

    @classmethod
    def _decode_range_snapshot_index_row(cls, *, project_id: str, row: sqlite3.Row) -> RangeSnapshot:
        payload = cls._range_snapshot_payload_from_index_row(project_id=project_id, row=row)
        return RangeSnapshot(
            project_id=ProjectId(str(project_id)),
            range_id=RangeId(str(payload["rangeId"])),
            recall_point_ids=tuple(RecallPointId(str(item)) for item in list(payload["recallPointIds"])),
        )

    @classmethod
    def _decode_review_task_index_row(cls, *, project_id: str, row: sqlite3.Row) -> ReviewTask:
        payload = cls._review_task_payload_from_index_row(project_id=project_id, row=row)
        return ReviewTask(
            project_id=ProjectId(str(project_id)),
            review_task_id=ReviewTaskId(str(payload["reviewTaskId"])),
            input_range_id=RangeId(str(payload["inputRangeId"])),
            created_at=cls._ms_to_ts(int(payload["createdAtMs"])),
            state=ReviewTaskState(str(payload["state"])),
            executed_at=None if payload.get("executedAtMs") is None else cls._ms_to_ts(int(payload["executedAtMs"])),
            result_range_id=None if payload.get("resultRangeId") is None else RangeId(str(payload["resultRangeId"])),
        )

    @classmethod
    def _decode_convergence_index_row(cls, *, project_id: str, row: sqlite3.Row) -> Convergence:
        payload = cls._convergence_payload_from_index_row(project_id=project_id, row=row)
        return Convergence(
            project_id=ProjectId(str(project_id)),
            convergence_id=ConvergenceId(str(payload["convergenceId"])),
            seed_range_id=RangeId(str(payload["seedRangeId"])),
            rule_id=ConvergenceRuleId(str(payload["ruleId"])),
            review_task_ids=tuple(ReviewTaskId(str(item)) for item in list(payload["reviewTaskIds"])),
            state=ConvergenceState(str(payload["state"])),
        )

    @classmethod
    def _decode_review_chain_index_row(cls, *, project_id: str, row: sqlite3.Row) -> ReviewChain:
        payload = cls._review_chain_payload_from_index_row(project_id=project_id, row=row)
        items: list[ReviewChainItem] = []
        for raw_item in list(payload["queue"]):
            item_payload = dict(raw_item)
            kind = ReviewChainItemKind(str(item_payload["kind"]))
            if kind == ReviewChainItemKind.CONVERGENCE:
                item_id = ConvergenceId(str(item_payload["id"]))
            else:
                item_id = ReviewTaskId(str(item_payload["id"]))
            items.append(ReviewChainItem(kind=kind, id=item_id))
        return ReviewChain(
            project_id=ProjectId(str(project_id)),
            review_chain_id=ReviewChainId(str(payload["reviewChainId"])),
            queue=tuple(items),
            head_index=int(payload["headIndex"]),
            state=ReviewChainState(str(payload["state"])),
        )

    @classmethod
    def _decode_review_task_queue_index_row(cls, *, project_id: str, row: sqlite3.Row) -> tuple[ReviewTaskId | None, tuple[ReviewTaskId, ...]]:
        payload = cls._review_task_queue_payload_from_index_row(project_id=project_id, row=row)
        review_task_ids = tuple(ReviewTaskId(str(item)) for item in list(payload["reviewTaskIds"]))
        head_index = int(payload["headIndex"])
        current_ids = review_task_ids[head_index:]
        return (current_ids[0] if current_ids else None, current_ids)

    @classmethod
    def _decode_layer_index_row(cls, *, project_id: str, row: sqlite3.Row) -> Layer:
        payload = cls._layer_payload_from_index_row(project_id=project_id, row=row)
        return Layer(
            project_id=ProjectId(str(project_id)),
            layer_id=LayerId(str(payload["layerId"])),
            layer_index=int(payload["layerIndex"]),
            layer_mode=LayerMode(str(payload["layerMode"])),
            orchestrator_managed_review_chain_ids=tuple(
                ReviewChainId(str(item)) for item in list(payload["orchestratorManagedReviewChainIds"])
            ),
            aggregation_k_node=int(payload["aggregationKNode"]),
            aggregation_k_point=int(payload["aggregationKPoint"]),
            aggregation_cycle_state=AggregationCycleState(str(payload["aggregationCycleState"])),
            pending_roll_up_parent_node_id=None
            if payload.get("pendingRollUpParentNodeId") is None
            else LearningTaskNodeId(str(payload["pendingRollUpParentNodeId"])),
            normal_tick_quota_remaining=int(payload["normalTickQuotaRemaining"]),
        )

    @classmethod
    def _decode_audit_log_event_index_row(cls, *, project_id: str, row: sqlite3.Row) -> AuditLogEvent:
        payload = cls._audit_log_event_payload_from_index_row(project_id=project_id, row=row)
        return AuditLogEvent(
            project_id=ProjectId(str(project_id)),
            event_id=str(payload["eventId"]),
            occurred_at=cls._ms_to_ts(int(payload["occurredAtMs"])),
            kind=cls._decode_audit_event_kind(payload["kind"]),
            api_name=str(payload["apiName"]),
            result=AuditResultCode(str(payload["result"])),
            payload=str(payload["payload"]),
        )

    @classmethod
    def _decode_asr_artifact_index_row(cls, *, project_id: str, row: sqlite3.Row) -> AsrArtifact:
        payload = cls._asr_artifact_payload_from_index_row(project_id=project_id, row=row)
        return AsrArtifact(
            project_id=ProjectId(str(project_id)),
            asr_artifact_id=AsrArtifactId(str(payload["asrArtifactId"])),
            created_at=cls._ms_to_ts(int(payload["createdAtMs"])),
            provider=AsrProvider(str(payload["provider"])),
            producer_runtime_kind=ClientRuntimeKind(str(payload.get("producerRuntimeKind", ClientRuntimeKind.DESKTOP_NATIVE.value))),
            recall_point_id=RecallPointId(str(payload["recallPointId"])),
            source_instance_id=InstanceId(str(payload["sourceInstanceId"])),
            center_ms=int(payload["centerMs"]),
            pre_ms=int(payload["preMs"]),
            post_ms=int(payload["postMs"]),
            segments=tuple(
                AsrSegment(
                    start_ms=int(dict(item).get("startMs", 0)),
                    end_ms=int(dict(item).get("endMs", 0)),
                    text=str(dict(item).get("text", "")),
                    confidence=None if dict(item).get("confidence") is None else float(dict(item)["confidence"]),
                )
                for item in list(payload["segments"])
            ),
        )

    @classmethod
    def _decode_aggregation_event_index_row(cls, *, project_id: str, row: sqlite3.Row) -> AggregationEvent:
        payload = cls._aggregation_event_payload_from_index_row(project_id=project_id, row=row)
        return AggregationEvent(
            project_id=ProjectId(str(project_id)),
            event_id=AggregationEventId(str(payload["eventId"])),
            created_at=cls._ms_to_ts(int(payload["createdAtMs"])),
            layer_index=int(payload["layerIndex"]),
            parent_node_id=LearningTaskNodeId(str(payload["parentNodeId"])),
            child_node_ids=tuple(LearningTaskNodeId(str(item)) for item in list(payload["childNodeIds"])),
            reason=AggregationEventReason(str(payload["reason"])),
            title=None if payload.get("title") is None else str(payload["title"]),
        )

    @classmethod
    def _decode_material_allowlist_index_row(cls, *, project_id: str, row: sqlite3.Row) -> MaterialAllowlist:
        payload = cls._material_allowlist_payload_from_index_row(project_id=project_id, row=row)
        return MaterialAllowlist(
            project_id=ProjectId(str(project_id)),
            allowlist_id=str(payload["allowlistId"]),
            material_ids=tuple(PurePosixPath(str(item)) for item in list(payload["materialIds"])),
        )

    @classmethod
    def _decode_media_asset_index_row(cls, *, project_id: str, row: sqlite3.Row) -> MediaAsset:
        payload = cls._media_asset_payload_from_index_row(project_id=project_id, row=row)
        return MediaAsset(
            project_id=ProjectId(str(project_id)),
            asset_id=MediaAssetId(str(payload["assetId"])),
            kind=MediaAssetKind(str(payload["kind"])),
            relative_path=PurePosixPath(str(payload["relativePath"])),
            created_at=cls._ms_to_ts(int(payload["createdAtMs"])),
            mime_type=None if payload.get("mimeType") is None else str(payload["mimeType"]),
        )

    @classmethod
    def _decode_recall_point_review_record_index_row(
        cls,
        *,
        project_id: str,
        row: sqlite3.Row,
    ) -> RecallPointReviewRecord:
        payload = cls._recall_point_review_record_payload_from_index_row(project_id=project_id, row=row)
        return RecallPointReviewRecord(
            project_id=ProjectId(str(project_id)),
            record_id=str(payload["recordId"]),
            recall_point_id=RecallPointId(str(payload["recallPointId"])),
            review_task_id=ReviewTaskId(str(payload["reviewTaskId"])),
            occurred_at=cls._ms_to_ts(int(payload["occurredAtMs"])),
            result=RecallPointReviewResult(str(payload["result"])),
        )

    def _hydrate_project_payload(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        project_payload: dict[str, Any],
    ) -> dict[str, Any]:
        hydrated = dict(project_payload)

        storage_row = conn.execute(
            """
            SELECT project_root, learning_object_root, fs_sync_policy, updated_at_ms
            FROM project_storage_config_index
            WHERE project_id = ?
            """,
            (str(project_id),),
        ).fetchone()
        if storage_row is not None:
            hydrated["projectStorageConfig"] = {
                "projectId": str(project_id),
                "projectRoot": str(storage_row["project_root"]),
                "learningObjectRoot": str(storage_row["learning_object_root"]),
                "fsSyncPolicy": str(storage_row["fs_sync_policy"]),
                "updatedAtMs": int(storage_row["updated_at_ms"]),
            }

        config_row = conn.execute(
            """
            SELECT config_json
            FROM project_config_index
            WHERE project_id = ?
            """,
            (str(project_id),),
        ).fetchone()
        if config_row is not None:
            config_payload = json.loads(str(config_row["config_json"]))
            if not isinstance(config_payload, dict):
                raise ValueError("ProjectConfig payload must be a JSON object")
            hydrated["projectConfig"] = config_payload

        instance_rows = conn.execute(
            """
            SELECT instance_id, material_id, presence, last_seen_at_ms
            FROM instance_index
            WHERE project_id = ?
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
            WHERE project_id = ?
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
            WHERE project_id = ?
            ORDER BY node_id ASC
            """,
            (str(project_id),),
        ).fetchall()
        nodes: dict[str, dict[str, Any]] = {}
        for row in node_rows:
            kind = str(row["node_kind"])
            payload: dict[str, Any] = {
                "kind": kind,
                "source": str(row["source"]),
                "projectId": str(project_id),
                "nodeId": str(row["node_id"]),
                "relativePath": str(row["relative_path"]),
                "parentId": None if row["parent_id"] is None else str(row["parent_id"]),
                "title": str(row["title"]),
            }
            if kind == "LEAF":
                payload["instanceId"] = str(row["instance_id"])
            else:
                children_raw = str(row["children_json"]) if row["children_json"] is not None else "[]"
                payload["children"] = list(json.loads(children_raw))
            nodes[str(row["node_id"])] = payload
        hydrated["learningObjectNodes"] = nodes

        # Normalized index tables are authoritative. Do not merge shell-only externalized rows
        # back into the hydrated payload, otherwise stale compatibility-shell data could be
        # resurrected during compaction.
        legacy_recall_points = dict(project_payload.get("recallPoints", {}))
        recall_point_rows = conn.execute(
            """
            SELECT recall_point_id, created_at_ms, anchor_instance_id, anchor_position, question_plain_text,
                   answer_plain_text, insights_count, payload_json
            FROM recall_point_index
            WHERE project_id = ?
            ORDER BY recall_point_id ASC
            """,
            (str(project_id),),
        ).fetchall()
        hydrated["recallPoints"] = {
            str(row["recall_point_id"]): self._recall_point_payload_from_index_row(
                project_id=str(project_id),
                row=row,
                legacy_payloads=legacy_recall_points,
            )
            for row in recall_point_rows
        }

        learning_task_rows = conn.execute(
            """
            SELECT learning_task_id, title, recall_point_ids_json
            FROM learning_task_index
            WHERE project_id = ?
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
            SELECT node_id, node_kind, parent_id, bound_learning_task_id, title, children_json
            FROM learning_task_node_index
            WHERE project_id = ?
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
            WHERE project_id = ?
            ORDER BY target_layer_index ASC, registration_seq ASC, entry_node ASC
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
            WHERE project_id = ?
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
            WHERE project_id = ?
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
            WHERE project_id = ?
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
            WHERE project_id = ?
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
            WHERE project_id = ?
            """,
            (str(project_id),),
        ).fetchone()
        if queue_row is not None:
            hydrated["reviewTaskQueue"] = self._review_task_queue_payload_from_index_row(
                project_id=str(project_id),
                row=queue_row,
            )
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
            WHERE project_id = ?
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
        hydrated["aggregationKNode"] = {
            str(int(row["layer_index"])): int(row["aggregation_k_node"])
            for row in layer_rows
        }
        hydrated["aggregationKPoint"] = {
            str(int(row["layer_index"])): int(row["aggregation_k_point"])
            for row in layer_rows
        }
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
            WHERE project_id = ?
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
            WHERE project_id = ?
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
            WHERE project_id = ?
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
            WHERE project_id = ?
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
            WHERE project_id = ?
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
            WHERE project_id = ?
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
            WHERE project_id = ?
            ORDER BY occurred_at_ms ASC, record_id ASC
            """,
            (str(project_id),),
        ).fetchall()
        hydrated["recallPointReviewRecords"] = {
            str(row["record_id"]): self._recall_point_review_record_payload_from_index_row(
                project_id=str(project_id),
                row=row,
            )
            for row in review_record_rows
        }
        return hydrated

    @staticmethod
    def _decode_compat_snapshot_payload(raw_snapshot: object) -> dict[str, Any]:
        if raw_snapshot is None:
            return {}
        text = str(raw_snapshot).strip()
        if not text:
            return {}
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("Project snapshot must be a JSON object")
        return payload

    @staticmethod
    def _project_payload_from_snapshot_row(row: sqlite3.Row) -> dict[str, Any]:
        deleted_at_ms_raw = row["deleted_at_ms"]
        return {
            "project": {
                "projectId": str(row["project_id"]),
                "title": str(row["project_title"]),
                "state": str(row["project_state"]),
                "createdAtMs": int(row["created_at_ms"]),
                "deletedAtMs": None if deleted_at_ms_raw is None else int(deleted_at_ms_raw),
            }
        }

    def _load_global_llm_settings_payload(self, conn: sqlite3.Connection) -> dict[str, Any] | None:
        row = conn.execute(
            """
            SELECT payload_json
            FROM global_settings_index
            WHERE settings_key = ?
            """,
            ("global_llm",),
        ).fetchone()
        if row is None:
            return None
        payload = json.loads(str(row["payload_json"]))
        if not isinstance(payload, dict):
            raise ValueError("Global LLM settings payload must be a JSON object")
        return payload

    def _replace_global_llm_settings_payload(self, conn: sqlite3.Connection, payload: dict[str, Any] | None, *, updated_at: str) -> None:
        conn.execute("DELETE FROM global_settings_index WHERE settings_key = ?", ("global_llm",))
        if payload is None:
            return
        conn.execute(
            """
            INSERT INTO global_settings_index (settings_key, payload_json, updated_at)
            VALUES (?, ?, ?)
            """,
            (
                "global_llm",
                json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                str(updated_at),
            ),
        )

    def _hydrate_project_payload_from_row(self, conn: sqlite3.Connection, *, row: sqlite3.Row) -> tuple[dict[str, Any], bool]:
        compat_payload = self._decode_compat_snapshot_payload(row["snapshot_json"])
        project_payload = dict(compat_payload)
        project_payload["project"] = self._project_payload_from_snapshot_row(row)["project"]
        return (
            self._hydrate_project_payload(
                conn,
                project_id=str(row["project_id"]),
                project_payload=project_payload,
            ),
            self._project_payload_uses_externalized_fields(compat_payload),
        )

    @staticmethod
    def _normalize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
        schema_version = int(snapshot.get("schemaVersion", 1))
        idgen_counters = dict(snapshot.get("idgenCounters", {}))
        raw_global_llm_settings = snapshot.get("globalLlmSettings")
        global_llm_settings = dict(raw_global_llm_settings) if isinstance(raw_global_llm_settings, dict) else None
        projects = dict(snapshot.get("projects", {}))
        return {
            "schemaVersion": schema_version,
            "idgenCounters": idgen_counters,
            "globalLlmSettings": global_llm_settings,
            "projects": projects,
        }

    def begin_unit_of_work(self, *, project_id: str | None = None) -> SqlUnitOfWork:
        return SQLitePersistenceUnitOfWork(connect=self._connect, lock=self._lock, project_id=project_id)

    def _load_from_sharded_tables(self, conn: sqlite3.Connection) -> tuple[dict[str, Any] | None, bool]:
        system_row = conn.execute(
            "SELECT schema_version, idgen_counters_json FROM system_state WHERE slot = 1"
        ).fetchone()
        global_llm_settings = self._load_global_llm_settings_payload(conn)
        project_rows = conn.execute(
            """
            SELECT project_id, project_title, project_state, created_at_ms, deleted_at_ms, snapshot_json
            FROM project_snapshots
            ORDER BY project_id ASC
            """
        ).fetchall()

        if system_row is None and global_llm_settings is None and not project_rows:
            return None, False

        if system_row is None:
            schema_version = 1
            idgen_counters: dict[str, Any] = {}
        else:
            schema_version = int(system_row["schema_version"])
            raw_counters = str(system_row["idgen_counters_json"])
            loaded_counters = json.loads(raw_counters)
            idgen_counters = dict(loaded_counters) if isinstance(loaded_counters, dict) else {}

        projects: dict[str, Any] = {}
        needs_compaction = False
        for row in project_rows:
            hydrated_payload, row_needs_compaction = self._hydrate_project_payload_from_row(conn, row=row)
            if row_needs_compaction:
                needs_compaction = True
            projects[str(row["project_id"])] = hydrated_payload

        return (
            {
                "schemaVersion": schema_version,
                "idgenCounters": idgen_counters,
                "globalLlmSettings": global_llm_settings,
                "projects": projects,
            },
            needs_compaction,
        )

    def _needs_project_config_index_backfill(self, conn: sqlite3.Connection) -> bool:
        try:
            row = conn.execute(
                """
                SELECT 1
                FROM project_snapshots ps
                LEFT JOIN project_storage_config_index sci ON sci.project_id = ps.project_id
                LEFT JOIN project_config_index pci ON pci.project_id = ps.project_id
                WHERE sci.project_id IS NULL OR pci.project_id IS NULL
                LIMIT 1
                """
            ).fetchone()
        except sqlite3.OperationalError:
            return True
        return row is not None

    def _needs_recall_point_payload_backfill(self, conn: sqlite3.Connection) -> bool:
        try:
            row = conn.execute(
                """
                SELECT 1
                FROM recall_point_index
                WHERE payload_json IS NULL OR payload_json = ''
                LIMIT 1
                """
            ).fetchone()
        except sqlite3.OperationalError:
            return True
        return row is not None

    def _read_legacy_sqlite_snapshot(self, conn: sqlite3.Connection) -> dict[str, Any] | None:
        try:
            row = conn.execute("SELECT snapshot_json FROM snapshot_state WHERE slot = 1").fetchone()
        except sqlite3.OperationalError:
            return None
        if row is None:
            return None
        data = json.loads(str(row["snapshot_json"]))
        if not isinstance(data, dict):
            raise ValueError("Legacy SQLite snapshot must be a JSON object")
        return self._normalize_snapshot(data)

    @staticmethod
    def _project_snapshot_record(
        *,
        project_id: str,
        project_payload: dict[str, Any],
        updated_at: str,
    ) -> ProjectSnapshotRecord:
        project_meta = dict(project_payload.get("project", {}))
        deleted_at_ms_raw = project_meta.get("deletedAtMs")
        return ProjectSnapshotRecord(
            project_id=str(project_id),
            project_title=str(project_meta.get("title", "")),
            project_state=str(project_meta.get("state", "")),
            created_at_ms=int(project_meta.get("createdAtMs", 0)),
            deleted_at_ms=None if deleted_at_ms_raw is None else int(deleted_at_ms_raw),
            snapshot=SQLiteSnapshotStore._strip_externalized_project_payload(project_payload),
            updated_at=updated_at,
        )

    def save_project_snapshot(
        self,
        *,
        project_id: str,
        project_snapshot: dict[str, Any],
        idgen_counters: dict[str, Any],
        schema_version: int = 1,
    ) -> None:
        updated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        payload = dict(project_snapshot)
        with self.begin_unit_of_work(project_id=str(project_id)) as uow:
            uow.system_state.upsert(
                uow.session,
                SystemStateRecord(
                    schema_version=int(schema_version),
                    idgen_counters=dict(idgen_counters),
                    updated_at=updated_at,
                ),
            )
            uow.project_snapshots.upsert(
                uow.session,
                self._project_snapshot_record(
                    project_id=str(project_id),
                    project_payload=payload,
                    updated_at=updated_at,
                ),
            )
            self._refresh_project_entity_indexes(uow.connection, project_id=str(project_id), project_payload=payload)
            uow.connection.execute("DELETE FROM snapshot_state WHERE slot = 1")

    def _read_legacy_snapshot(self) -> dict[str, Any] | None:
        legacy = self._legacy_json_path
        if legacy is None or legacy == self._path or not legacy.exists():
            return None
        raw = legacy.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Legacy snapshot must be a JSON object")
        return data

    def _archive_legacy_snapshot(self) -> None:
        legacy = self._legacy_json_path
        if legacy is None or legacy == self._path or not legacy.exists():
            return
        target = legacy.with_name(f"{legacy.name}.imported.bak")
        if target.exists():
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            target = legacy.with_name(f"{legacy.name}.imported-{stamp}.bak")
        try:
            os.replace(legacy, target)
        except OSError:
            return

    @staticmethod
    def _ms_to_ts(ms: int | None) -> datetime | None:
        if ms is None:
            return None
        return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=int(ms))

    def load_snapshot(self) -> dict[str, Any] | None:
        with self._lock:
            conn = self._connect()
            try:
                sharded, needs_compaction = self._load_from_sharded_tables(conn)
                if sharded is not None:
                    needs_backfill = self._needs_project_config_index_backfill(conn)
                    needs_recall_point_backfill = self._needs_recall_point_payload_backfill(conn)
                else:
                    needs_backfill = False
                    needs_recall_point_backfill = False
                legacy_sqlite = self._read_legacy_sqlite_snapshot(conn)
            finally:
                conn.close()

            if sharded is not None:
                if needs_backfill or needs_compaction or needs_recall_point_backfill:
                    self.save_snapshot(sharded)
                self._archive_legacy_snapshot()
                return sharded

            if legacy_sqlite is not None:
                self.save_snapshot(legacy_sqlite)
                return self._normalize_snapshot(legacy_sqlite)

            legacy_data = self._read_legacy_snapshot()
            if legacy_data is None:
                return None
            self.save_snapshot(legacy_data)
            self._archive_legacy_snapshot()
            return self._normalize_snapshot(legacy_data)

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
                self._refresh_project_entity_indexes(
                    uow.connection,
                    project_id=str(project_id),
                    project_payload=project_payload,
                )
            uow.connection.execute("DELETE FROM snapshot_state WHERE slot = 1")

    def list_projects_metadata(self, *, active_only: bool = True) -> tuple[Project, ...]:
        query = """
            SELECT project_id, project_title, project_state, created_at_ms, deleted_at_ms
            FROM project_snapshots
        """
        params: tuple[object, ...] = tuple()
        if active_only:
            query += " WHERE project_state = ?"
            params = (ProjectState.ACTIVE.value,)
        query += " ORDER BY project_id ASC"

        conn = self._connect()
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()

        return tuple(
            Project(
                project_id=ProjectId(str(row["project_id"])),
                title=str(row["project_title"]),
                state=ProjectState(str(row["project_state"])),
                created_at=self._ms_to_ts(int(row["created_at_ms"])),
                deleted_at=self._ms_to_ts(None if row["deleted_at_ms"] is None else int(row["deleted_at_ms"])),
            )
            for row in rows
        )

    def get_project_config(self, project_id: str) -> ProjectConfig | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT config_json
                FROM project_config_index
                WHERE project_id = ?
                """,
                (str(project_id),),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        payload = json.loads(str(row["config_json"]))
        if not isinstance(payload, dict):
            raise ValueError("ProjectConfig payload must be a JSON object")
        return decode_project_config_payload(payload)

    def get_project_storage_config(self, project_id: str) -> ProjectStorageConfig | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT project_root, learning_object_root, fs_sync_policy, updated_at_ms
                FROM project_storage_config_index
                WHERE project_id = ?
                """,
                (str(project_id),),
            ).fetchone()
        finally:
            conn.close()
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
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT event_id, occurred_at_ms, kind, api_name, result, payload
                FROM audit_log_event_index
                WHERE project_id = ?
                ORDER BY occurred_at_ms ASC, event_id ASC
                """,
                (str(project_id),),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._decode_audit_log_event_index_row(project_id=str(project_id), row=row) for row in rows)

    def list_instances(self, project_id: str) -> tuple[Instance, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT instance_id, material_id, presence, last_seen_at_ms
                FROM instance_index
                WHERE project_id = ?
                ORDER BY instance_id ASC
                """,
                (str(project_id),),
            ).fetchall()
        finally:
            conn.close()

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
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT material_id, presence, last_seen_at_ms
                FROM instance_index
                WHERE project_id = ? AND instance_id = ?
                """,
                (str(project_id), str(instance_id)),
            ).fetchone()
        finally:
            conn.close()

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
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT instance_id, source_kind, playback_kind, account_id, remote_file_id, remote_path,
                       mime_type, size_bytes, duration_ms, source_payload_json, updated_at_ms
                FROM instance_media_binding_index
                WHERE project_id = ?
                ORDER BY instance_id ASC
                """,
                (str(project_id),),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._decode_instance_media_binding(project_id=str(project_id), row=row) for row in rows)

    def get_instance_media_binding(self, project_id: str, instance_id: str) -> InstanceMediaBinding | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT instance_id, source_kind, playback_kind, account_id, remote_file_id, remote_path,
                       mime_type, size_bytes, duration_ms, source_payload_json, updated_at_ms
                FROM instance_media_binding_index
                WHERE project_id = ? AND instance_id = ?
                """,
                (str(project_id), str(instance_id)),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._decode_instance_media_binding(project_id=str(project_id), row=row)

    def list_missing_instance_ids(self, project_id: str) -> tuple[InstanceId, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT instance_id
                FROM instance_index
                WHERE project_id = ? AND presence = ?
                ORDER BY instance_id ASC
                """,
                (str(project_id), InstancePresence.MISSING.value),
            ).fetchall()
        finally:
            conn.close()
        return tuple(InstanceId(str(row["instance_id"])) for row in rows)

    def list_recall_point_ids_by_instance(self, project_id: str, instance_id: str) -> tuple[RecallPointId, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT recall_point_id, created_at_ms, anchor_instance_id, anchor_position, question_plain_text,
                       answer_plain_text, insights_count, payload_json
                FROM recall_point_index
                WHERE project_id = ? AND anchor_instance_id = ?
                ORDER BY recall_point_id ASC
                """,
                (str(project_id), str(instance_id)),
            ).fetchall()
        finally:
            conn.close()
        out: list[RecallPointId] = []
        for row in rows:
            raw = self._recall_point_payload_from_index_row(project_id=str(project_id), row=row, legacy_payloads={})
            rp = self._decode_recall_point(project_id=str(project_id), raw=raw)
            if rp.state == RecallPointState.ACTIVE:
                out.append(rp.recall_point_id)
        return tuple(out)

    def get_recall_point(self, project_id: str, recall_point_id: str) -> RecallPoint | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT recall_point_id, created_at_ms, anchor_instance_id, anchor_position, question_plain_text,
                       answer_plain_text, insights_count, payload_json
                FROM recall_point_index
                WHERE project_id = ? AND recall_point_id = ?
                """,
                (str(project_id), str(recall_point_id)),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        raw = self._recall_point_payload_from_index_row(project_id=str(project_id), row=row, legacy_payloads={})
        return self._decode_recall_point(project_id=str(project_id), raw=raw)

    def list_recall_points_by_learning_object_node(self, project_id: str, node_id: str) -> tuple[RecallPoint, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT node_id, node_kind, instance_id, children_json
                FROM learning_object_node_index
                WHERE project_id = ?
                """,
                (str(project_id),),
            ).fetchall()
        finally:
            conn.close()

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

        recall_point_ids: set[RecallPointId] = set()
        for instance_id in sorted(covered_instance_ids):
            recall_point_ids.update(self.list_recall_point_ids_by_instance(str(project_id), instance_id))

        placeholders = ",".join("?" for _ in sorted(covered_instance_ids))
        conn = self._connect()
        try:
            rows = conn.execute(
                f"""
                SELECT recall_point_id, created_at_ms, anchor_instance_id, anchor_position, question_plain_text,
                       answer_plain_text, insights_count, payload_json
                FROM recall_point_index
                WHERE project_id = ? AND anchor_instance_id IN ({placeholders})
                ORDER BY recall_point_id ASC
                """,
                (str(project_id), *tuple(sorted(covered_instance_ids))),
            ).fetchall()
        finally:
            conn.close()

        items: list[RecallPoint] = []
        for row in rows:
            raw = self._recall_point_payload_from_index_row(project_id=str(project_id), row=row, legacy_payloads={})
            rp = self._decode_recall_point(project_id=str(project_id), raw=raw)
            if rp.state == RecallPointState.ACTIVE:
                items.append(rp)
        return tuple(items)

    def get_review_chain_entry_registration(self, project_id: str, review_chain_id: str) -> EntryRegistration | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT entry_node, target_layer_index, review_chain_id, registration_seq
                FROM entry_registration_index
                WHERE project_id = ? AND review_chain_id = ?
                ORDER BY target_layer_index ASC, registration_seq ASC, entry_node ASC
                LIMIT 1
                """,
                (str(project_id), str(review_chain_id)),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._decode_entry_registration_index_row(project_id=str(project_id), row=row)

    def list_learning_object_nodes(self, project_id: str) -> tuple[LearningObjectLeaf | LearningObjectContainer, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT node_id, node_kind, source, relative_path, parent_id, instance_id, title, children_json
                FROM learning_object_node_index
                WHERE project_id = ?
                ORDER BY node_id ASC
                """,
                (str(project_id),),
            ).fetchall()
        finally:
            conn.close()

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

    def get_learning_object_node(self, project_id: str, node_id: str) -> LearningObjectLeaf | LearningObjectContainer | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT node_kind, source, relative_path, parent_id, instance_id, title, children_json
                FROM learning_object_node_index
                WHERE project_id = ? AND node_id = ?
                """,
                (str(project_id), str(node_id)),
            ).fetchone()
        finally:
            conn.close()

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
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT node_id
                FROM learning_object_node_index
                WHERE project_id = ? AND parent_id IS NULL
                ORDER BY node_id ASC
                """,
                (str(project_id),),
            ).fetchall()
        finally:
            conn.close()
        return tuple(LearningObjectNodeId(str(row["node_id"])) for row in rows)

    def list_learning_task_nodes(self, project_id: str) -> tuple[LearningTaskNode, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT node_id, node_kind, parent_id, bound_learning_task_id, title, children_json
                FROM learning_task_node_index
                WHERE project_id = ?
                ORDER BY node_id ASC
                """,
                (str(project_id),),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._decode_learning_task_node_index_row(project_id=str(project_id), row=row) for row in rows)

    def get_learning_task_node(self, project_id: str, node_id: str) -> LearningTaskNode | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT node_id, node_kind, parent_id, bound_learning_task_id, title, children_json
                FROM learning_task_node_index
                WHERE project_id = ? AND node_id = ?
                """,
                (str(project_id), str(node_id)),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._decode_learning_task_node_index_row(project_id=str(project_id), row=row)

    def get_learning_task(self, project_id: str, learning_task_id: str) -> LearningTask | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT learning_task_id, title, recall_point_ids_json
                FROM learning_task_index
                WHERE project_id = ? AND learning_task_id = ?
                """,
                (str(project_id), str(learning_task_id)),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._decode_learning_task_index_row(project_id=str(project_id), row=row)

    def get_learning_task_entry_registration(self, project_id: str, learning_task_id: str) -> EntryRegistration | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT eri.entry_node, eri.target_layer_index, eri.review_chain_id, eri.registration_seq
                FROM learning_task_node_index ltn
                JOIN entry_registration_index eri
                  ON eri.project_id = ltn.project_id AND eri.entry_node = ltn.node_id
                WHERE ltn.project_id = ? AND ltn.node_kind = 'LEAF' AND ltn.bound_learning_task_id = ?
                ORDER BY eri.target_layer_index ASC, eri.registration_seq ASC, ltn.node_id ASC
                LIMIT 1
                """,
                (str(project_id), str(learning_task_id)),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._decode_entry_registration_index_row(project_id=str(project_id), row=row)

    def get_learning_task_node_entry_registration(self, project_id: str, node_id: str) -> EntryRegistration | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT entry_node, target_layer_index, review_chain_id, registration_seq
                FROM entry_registration_index
                WHERE project_id = ? AND entry_node = ?
                """,
                (str(project_id), str(node_id)),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._decode_entry_registration_index_row(project_id=str(project_id), row=row)

    def list_recall_points_by_learning_task_node(self, project_id: str, node_id: str) -> tuple[RecallPoint, ...]:
        conn = self._connect()
        try:
            node_rows = conn.execute(
                """
                SELECT node_id, node_kind, bound_learning_task_id, children_json
                FROM learning_task_node_index
                WHERE project_id = ?
                """,
                (str(project_id),),
            ).fetchall()
            task_rows = conn.execute(
                """
                SELECT learning_task_id, recall_point_ids_json
                FROM learning_task_index
                WHERE project_id = ?
                """,
                (str(project_id),),
            ).fetchall()
        finally:
            conn.close()

        node_map = {
            str(row["node_id"]): {
                "kind": str(row["node_kind"]),
                "bound_learning_task_id": None
                if row["bound_learning_task_id"] is None
                else str(row["bound_learning_task_id"]),
                "children": tuple(json.loads(str(row["children_json"]))) if row["children_json"] is not None else tuple(),
            }
            for row in node_rows
        }
        if str(node_id) not in node_map:
            return tuple()

        task_map = {
            str(row["learning_task_id"]): tuple(
                RecallPointId(str(item))
                for item in json.loads(str(row["recall_point_ids_json"]))
            )
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
        placeholders = ",".join("?" for _ in unique_recall_point_ids)
        conn = self._connect()
        try:
            recall_point_rows = conn.execute(
                f"""
                SELECT recall_point_id, created_at_ms, anchor_instance_id, anchor_position, question_plain_text,
                       answer_plain_text, insights_count, payload_json
                FROM recall_point_index
                WHERE project_id = ? AND recall_point_id IN ({placeholders})
                """,
                (str(project_id), *unique_recall_point_ids),
            ).fetchall()
        finally:
            conn.close()

        recall_point_map = {
            str(row["recall_point_id"]): self._decode_recall_point(
                project_id=str(project_id),
                raw=self._recall_point_payload_from_index_row(project_id=str(project_id), row=row, legacy_payloads={}),
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
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT queue_id, review_task_ids_json, head_index
                FROM review_task_queue_index
                WHERE project_id = ?
                """,
                (str(project_id),),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._decode_review_task_queue_index_row(project_id=str(project_id), row=row)

    def list_layers(self, project_id: str) -> tuple[Layer, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT layer_id, layer_index, layer_mode, orchestrator_managed_review_chain_ids_json,
                       aggregation_k_node, aggregation_k_point, aggregation_cycle_state,
                       pending_roll_up_parent_node_id, normal_tick_quota_remaining
                FROM layer_state_index
                WHERE project_id = ?
                ORDER BY layer_index ASC, layer_id ASC
                """,
                (str(project_id),),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._decode_layer_index_row(project_id=str(project_id), row=row) for row in rows)

    def get_aggregation_queue_current(self, project_id: str, layer_index: int) -> tuple[LearningTaskNodeId, ...] | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT layer_index, node_ids_json, head_index
                FROM aggregation_queue_index
                WHERE project_id = ? AND layer_index = ?
                """,
                (str(project_id), int(layer_index)),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        payload = self._aggregation_queue_payload_from_index_row(project_id=str(project_id), row=row)
        node_ids = tuple(LearningTaskNodeId(str(item)) for item in list(payload["nodeIds"]))
        return tuple(node_ids[int(payload["headIndex"]) :])

    def list_aggregation_events(self, project_id: str) -> tuple[AggregationEvent, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT event_id, created_at_ms, layer_index, parent_node_id, child_node_ids_json, reason, title
                FROM aggregation_event_index
                WHERE project_id = ?
                ORDER BY event_id ASC
                """,
                (str(project_id),),
            ).fetchall()
        finally:
            conn.close()
        return tuple(self._decode_aggregation_event_index_row(project_id=str(project_id), row=row) for row in rows)

    def get_review_task(self, project_id: str, review_task_id: str) -> ReviewTask | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT review_task_id, input_range_id, created_at_ms, state, executed_at_ms, result_range_id
                FROM review_task_index
                WHERE project_id = ? AND review_task_id = ?
                """,
                (str(project_id), str(review_task_id)),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._decode_review_task_index_row(project_id=str(project_id), row=row)

    def get_asr_artifact(self, project_id: str, asr_artifact_id: str) -> AsrArtifact | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT asr_artifact_id, created_at_ms, provider, recall_point_id, source_instance_id, center_ms, pre_ms,
                       post_ms, segments_json
                FROM asr_artifact_index
                WHERE project_id = ? AND asr_artifact_id = ?
                """,
                (str(project_id), str(asr_artifact_id)),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._decode_asr_artifact_index_row(project_id=str(project_id), row=row)

    def _list_asr_artifacts(self, project_id: str) -> tuple[AsrArtifact, ...]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT asr_artifact_id, created_at_ms, provider, recall_point_id, source_instance_id, center_ms, pre_ms,
                       post_ms, segments_json
                FROM asr_artifact_index
                WHERE project_id = ?
                ORDER BY asr_artifact_id ASC
                """,
                (str(project_id),),
            ).fetchall()
        finally:
            conn.close()
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
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT convergence_id, seed_range_id, rule_id, review_task_ids_json, state
                FROM convergence_index
                WHERE project_id = ? AND convergence_id = ?
                """,
                (str(project_id), str(convergence_id)),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._decode_convergence_index_row(project_id=str(project_id), row=row)

    def get_review_chain(self, project_id: str, review_chain_id: str) -> ReviewChain | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT review_chain_id, queue_json, head_index, state
                FROM review_chain_index
                WHERE project_id = ? AND review_chain_id = ?
                """,
                (str(project_id), str(review_chain_id)),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._decode_review_chain_index_row(project_id=str(project_id), row=row)

    def get_range_snapshot(self, project_id: str, range_id: str) -> RangeSnapshot | None:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT range_id, recall_point_ids_json
                FROM range_snapshot_index
                WHERE project_id = ? AND range_id = ?
                """,
                (str(project_id), str(range_id)),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._decode_range_snapshot_index_row(project_id=str(project_id), row=row)


SQLiteStore = SQLiteSnapshotStore

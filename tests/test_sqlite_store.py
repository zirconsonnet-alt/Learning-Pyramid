from __future__ import annotations

import json
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

import pytest

from backend.models.aggregation_event import AggregationEvent
from backend.models.aggregation_queue import AggregationQueue
from backend.models.asr_artifact import AsrArtifact, AsrSegment
from backend.models.audit_log_event import AuditLogEvent
from backend.models.convergence import Convergence
from backend.models.entry_registration import EntryRegistration
from backend.models.enums import (
    AggregationCycleState,
    AggregationEventReason,
    AuditEventKind,
    AuditResultCode,
    AsrProvider,
    ClientRuntimeKind,
    ConvergenceState,
    InstancePresence,
    LayerMode,
    MediaAssetKind,
    ProjectState,
    RecallPointReviewResult,
    ReviewChainState,
    ReviewTaskState,
    SessionMode,
)
from backend.models.instance import Instance
from backend.models.layer import Layer
from backend.models.learning_object_node import LearningObjectLeaf
from backend.models.learning_task import LearningTask
from backend.models.learning_task_node import LearningTaskLeaf
from backend.models.media_asset import MediaAsset
from backend.models.project import Project
from backend.models.project_config import default_layer_config, default_project_config
from backend.models.project_storage_config import ProjectStorageConfig
from backend.models.range_snapshot import RangeSnapshot
from backend.models.recall_point import Anchor, RecallPoint
from backend.models.recall_point_review_record import RecallPointReviewRecord
from backend.models.rich_content import rich_text
from backend.models.review_chain import ReviewChain
from backend.models.review_task import ReviewTask
from backend.models.review_task_queue import ReviewTaskQueue
from backend.models.types import ConvergenceRuleId, MediaAssetId, id_canonical_text, now_utc_ms
from backend.repositories.persistence_interfaces import ProjectSnapshotRecord, SystemStateRecord
from backend.system.api import SystemAPI
from backend.system.inmemory_system import InMemorySystem
from backend.system.membership_commission_store import (
    WITHDRAWAL_STATUS_AWAITING_CONFIRMATION,
    WITHDRAWAL_STATUS_FAILED,
    WITHDRAWAL_STATUS_PROCESSING,
    WITHDRAWAL_STATUS_SUCCEEDED,
    MembershipCommissionStore,
)
from backend.models.errors import PreconditionFailure
from backend.system.persistence_json import SCHEMA_VERSION, decode_project_payload, encode_project_payload, encode_project_shell_payload
from backend.system.persistence_store import JsonSnapshotStore, SQLiteSnapshotStore


def test_sqlite_store_persists_projects_across_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    project_root = tmp_path / "project-alpha"

    api = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(db_path)))
    project_id = api.create_project("Alpha", project_root=str(project_root))

    reloaded = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(db_path)))
    projects = reloaded.list_projects()
    cfg = reloaded.get_project_storage_config(project_id)

    assert any(str(project.project_id) == str(project_id) for project in projects)
    assert cfg.project_root.as_posix() == project_root.as_posix()


def test_sqlite_store_persists_global_llm_settings_across_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"

    api = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(db_path)))
    status_before = api.get_global_llm_status()
    assert status_before["llmConfigured"] is False

    updated = api.update_global_llm_settings(
        base_url="https://api.openai.com/v1",
        model_name="gpt-4o-mini",
        api_key="sk-test-12345678",
        prompt_assembly_mode="user_concat",
    )
    assert updated["llmConfigured"] is True
    assert updated["llmSource"] == "global"
    assert updated["promptAssemblyMode"] == "user_concat"
    assert updated["savedApiKeyConfigured"] is True

    reloaded = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(db_path)))
    status_after = reloaded.get_global_llm_status()
    assert status_after["baseUrl"] == "https://api.openai.com/v1"
    assert status_after["modelName"] == "gpt-4o-mini"
    assert status_after["llmConfigured"] is True
    assert status_after["llmSource"] == "global"
    assert status_after["promptAssemblyMode"] == "user_concat"
    assert status_after["savedApiKeyConfigured"] is True
    assert status_after["savedApiKeyPreview"] == "sk-t...5678"


def test_sqlite_store_imports_legacy_json_snapshot(tmp_path: Path) -> None:
    legacy_json_path = tmp_path / "legacy-store.json"
    db_path = tmp_path / "plm_store.sqlite3"
    project_root = tmp_path / "project-beta"

    legacy_api = SystemAPI(InMemorySystem(persist_path=legacy_json_path))
    project_id = legacy_api.create_project("Beta", project_root=str(project_root))

    migrated = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(db_path, legacy_json_path=legacy_json_path)))
    projects = migrated.list_projects()
    assert any(str(project.project_id) == str(project_id) for project in projects)
    archived_candidates = sorted(tmp_path.glob("legacy-store.json.imported*.bak"))
    assert len(archived_candidates) == 1
    assert not legacy_json_path.exists()

    reloaded = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(db_path, legacy_json_path=legacy_json_path)))
    projects_after_reload = reloaded.list_projects()
    cfg = reloaded.get_project_storage_config(project_id)

    assert any(str(project.project_id) == str(project_id) for project in projects_after_reload)
    assert cfg.project_root.as_posix() == project_root.as_posix()


def test_sqlite_store_backfills_project_config_tables_on_reload(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    project_root = tmp_path / "project-backfill"

    api = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(db_path)))
    project_id = api.create_project("Backfill", project_root=str(project_root))

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("DELETE FROM project_config_index")
        conn.execute("DELETE FROM project_storage_config_index")
        conn.commit()
    finally:
        conn.close()

    reloaded = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(db_path)))
    project_config = reloaded.get_project_config(project_id)
    storage_config = reloaded.get_project_storage_config(project_id)

    assert str(project_config.project_id) == str(project_id)
    assert storage_config.project_root.as_posix() == project_root.as_posix()


def test_sqlite_store_rebuilds_projects_when_snapshot_json_is_empty_object(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    project_root = tmp_path / "project-empty-shell"

    api = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(db_path)))
    project_id = api.create_project("Empty Shell", project_root=str(project_root))

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("UPDATE project_snapshots SET snapshot_json = '{}' WHERE project_id = ?", (str(project_id),))
        conn.commit()
    finally:
        conn.close()

    reloaded = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(db_path)))

    projects = reloaded.list_projects()
    storage_config = reloaded.get_project_storage_config(project_id)
    project_config = reloaded.get_project_config(project_id)
    layers = reloaded.list_layers(project_id)
    queue_head, queue_ids = reloaded.get_queue(project_id)

    assert any(str(project.project_id) == str(project_id) for project in projects)
    assert storage_config.project_root.as_posix() == project_root.as_posix()
    assert str(project_config.project_id) == str(project_id)
    assert [layer.layer_index for layer in layers] == [0]
    assert queue_head is None
    assert queue_ids == tuple()


def test_sqlite_store_archives_legacy_json_even_after_sqlite_exists(tmp_path: Path) -> None:
    legacy_json_path = tmp_path / "legacy-store.json"
    db_path = tmp_path / "plm_store.sqlite3"

    legacy_api = SystemAPI(InMemorySystem(persist_path=legacy_json_path))
    project_id = legacy_api.create_project("Archive Legacy")

    migrated = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(db_path, legacy_json_path=legacy_json_path)))
    assert any(str(project.project_id) == str(project_id) for project in migrated.list_projects())

    archived_candidates = sorted(tmp_path.glob("legacy-store.json.imported*.bak"))
    assert len(archived_candidates) == 1
    legacy_json_path.write_text('{"stale":true}', encoding="utf-8")

    reloaded = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(db_path, legacy_json_path=legacy_json_path)))
    assert any(str(project.project_id) == str(project_id) for project in reloaded.list_projects())
    assert not legacy_json_path.exists()
    assert len(list(tmp_path.glob("legacy-store.json.imported*.bak"))) == 2


def test_sqlite_store_uses_sharded_project_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"

    api = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(db_path)))
    alpha_id = api.create_project("Alpha")
    beta_id = api.create_project("Beta")
    api.delete_project(alpha_id)

    conn = sqlite3.connect(str(db_path))
    try:
        system_row = conn.execute("SELECT schema_version, idgen_counters_json FROM system_state WHERE slot = 1").fetchone()
        project_rows = conn.execute(
            "SELECT project_id, project_title, project_state, snapshot_json FROM project_snapshots ORDER BY project_id ASC"
        ).fetchall()
    finally:
        conn.close()

    assert system_row is not None
    assert int(system_row[0]) == 1
    counters = json.loads(str(system_row[1]))
    assert isinstance(counters, dict)

    assert len(project_rows) == 2
    assert project_rows[0][0] == str(alpha_id)
    assert project_rows[0][1] == "Alpha"
    assert project_rows[0][2] == "DELETED"
    assert isinstance(json.loads(str(project_rows[0][3])), dict)
    assert project_rows[1][0] == str(beta_id)
    assert project_rows[1][1] == "Beta"
    assert project_rows[1][2] == "ACTIVE"


def test_sqlite_store_migrates_legacy_single_row_sqlite_table(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    legacy_json_path = tmp_path / "legacy-store.json"

    legacy_api = SystemAPI(InMemorySystem(persist_path=legacy_json_path))
    project_id = legacy_api.create_project("Gamma")
    payload = json.loads(legacy_json_path.read_text(encoding="utf-8"))

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE snapshot_state (
                slot INTEGER PRIMARY KEY CHECK (slot = 1),
                snapshot_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO snapshot_state (slot, snapshot_json, updated_at) VALUES (1, ?, '2026-03-08T00:00:00+00:00')",
            (json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),),
        )
        conn.commit()
    finally:
        conn.close()

    reloaded = SystemAPI(InMemorySystem(persist_store=SQLiteSnapshotStore(db_path)))
    projects = reloaded.list_projects()

    assert any(str(project.project_id) == str(project_id) for project in projects)

    conn = sqlite3.connect(str(db_path))
    try:
        migrated_rows = conn.execute("SELECT project_id FROM project_snapshots").fetchall()
        legacy_row = conn.execute("SELECT COUNT(*) FROM snapshot_state").fetchone()
    finally:
        conn.close()

    assert migrated_rows == [(str(project_id),)]
    assert legacy_row == (0,)


def test_sqlite_store_updates_only_changed_project_row_on_commit(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    system = InMemorySystem(persist_store=SQLiteSnapshotStore(db_path))
    api = SystemAPI(system)
    alpha_id = api.create_project("Alpha")
    beta_id = api.create_project("Beta")

    conn = sqlite3.connect(str(db_path))
    try:
        before_rows = dict(
            conn.execute("SELECT project_id, updated_at FROM project_snapshots ORDER BY project_id ASC").fetchall()
        )
    finally:
        conn.close()

    time.sleep(1.1)

    session = system.begin_session(alpha_id, SessionMode.READ_WRITE)
    try:
        instance = Instance.create(
            project_id=alpha_id,
            instance_id=system.g.idgen.new_instance_id(alpha_id),
            material_id="alpha/lesson-1.mp4",
            presence=InstancePresence.PRESENT,
        )
        system.instance_repo.add(session, instance)
        system.commit(session)
    finally:
        if session.state == "OPEN":
            system.rollback(session)

    conn = sqlite3.connect(str(db_path))
    try:
        after_rows = dict(
            conn.execute("SELECT project_id, updated_at FROM project_snapshots ORDER BY project_id ASC").fetchall()
        )
    finally:
        conn.close()

    assert before_rows[str(alpha_id)] != after_rows[str(alpha_id)]
    assert before_rows[str(beta_id)] == after_rows[str(beta_id)]


def test_project_payload_helpers_round_trip_bootstrapped_project(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    project_root = tmp_path / "project-roundtrip"
    system = InMemorySystem(persist_store=SQLiteSnapshotStore(db_path))
    api = SystemAPI(system)
    project_id = api.create_project("RoundTrip", project_root=str(project_root))

    project_store = system.g.projects[str(project_id)]
    payload = encode_project_payload(project_store)
    decoded = decode_project_payload(str(project_id), payload)

    assert decoded["project"].title == "RoundTrip"
    assert decoded["project_storage_config"].project_root.as_posix() == project_root.as_posix()
    assert decoded["project_config"].project_id == project_id
    assert decoded["review_task_queue"].queue_id == "GLOBAL_QUEUE"
    assert list(decoded["layers_by_index"].keys()) == [0]


def test_decode_project_payload_uses_current_layer_config_defaults_for_missing_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    system = InMemorySystem(persist_store=SQLiteSnapshotStore(db_path))
    api = SystemAPI(system)
    project_id = api.create_project("LayerConfig Defaults")

    payload = encode_project_payload(system.g.projects[str(project_id)])
    payload["projectConfig"] = {
        "projectId": str(project_id),
        "layerConfigs": {"0": {}},
        "pushConfig": {},
        "updatedAtMs": payload["projectConfig"]["updatedAtMs"],
    }

    decoded = decode_project_payload(str(project_id), payload)
    cfg0 = decoded["project_config"].layer_configs[0]
    expected = default_layer_config()

    assert cfg0.review_chain_template == expected.review_chain_template
    assert cfg0.aggregation_k_node == expected.aggregation_k_node
    assert cfg0.aggregation_k_point == expected.aggregation_k_point
    assert cfg0.threshold_roll_up_enabled is expected.threshold_roll_up_enabled


def test_json_store_save_project_snapshot_preserves_other_projects(tmp_path: Path) -> None:
    json_path = tmp_path / "plm_store.json"
    system = InMemorySystem(persist_path=json_path)
    api = SystemAPI(system)
    alpha_id = api.create_project("Alpha")
    beta_id = api.create_project("Beta")

    store = JsonSnapshotStore(json_path)
    alpha_payload = encode_project_payload(system.g.projects[str(alpha_id)])
    alpha_payload["project"]["title"] = "Alpha Renamed"

    store.save_project_snapshot(
        project_id=str(alpha_id),
        project_snapshot=alpha_payload,
        idgen_counters=system.g.idgen._counters,
        schema_version=SCHEMA_VERSION,
    )

    snapshot = store.load_snapshot()

    assert snapshot is not None
    assert snapshot["projects"][str(alpha_id)]["project"]["title"] == "Alpha Renamed"
    assert snapshot["projects"][str(beta_id)]["project"]["title"] == "Beta"


def test_sqlite_unit_of_work_commits_project_snapshot_row(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    store = SQLiteSnapshotStore(db_path)
    project_id = "project_manual"
    updated_at = "2026-03-09T00:00:00+00:00"
    payload = {
        "project": {
            "projectId": project_id,
            "title": "Manual Project",
            "state": "ACTIVE",
            "createdAtMs": 12345,
            "deletedAtMs": None,
        }
    }

    with store.begin_unit_of_work(project_id=project_id) as uow:
        uow.system_state.upsert(
            uow.session,
            SystemStateRecord(
                schema_version=SCHEMA_VERSION,
                idgen_counters={"project": 1},
                updated_at=updated_at,
            ),
        )
        uow.project_snapshots.upsert(
            uow.session,
            ProjectSnapshotRecord(
                project_id=project_id,
                project_title="Manual Project",
                project_state="ACTIVE",
                created_at_ms=12345,
                deleted_at_ms=None,
                snapshot=payload,
                updated_at=updated_at,
            ),
        )

    snapshot = store.load_snapshot()

    assert snapshot is not None
    assert snapshot["projects"][project_id]["project"]["title"] == "Manual Project"
    assert snapshot["idgenCounters"] == {"project": 1}


def test_sqlite_unit_of_work_rolls_back_project_snapshot_row(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    store = SQLiteSnapshotStore(db_path)
    project_id = "project_rollback"
    payload = {
        "project": {
            "projectId": project_id,
            "title": "Should Roll Back",
            "state": "ACTIVE",
            "createdAtMs": 54321,
            "deletedAtMs": None,
        }
    }

    try:
        with store.begin_unit_of_work(project_id=project_id) as uow:
            uow.system_state.upsert(
                uow.session,
                SystemStateRecord(
                    schema_version=SCHEMA_VERSION,
                    idgen_counters={"project": 99},
                    updated_at="2026-03-09T00:00:01+00:00",
                ),
            )
            uow.project_snapshots.upsert(
                uow.session,
                ProjectSnapshotRecord(
                    project_id=project_id,
                    project_title="Should Roll Back",
                    project_state="ACTIVE",
                    created_at_ms=54321,
                    deleted_at_ms=None,
                    snapshot=payload,
                    updated_at="2026-03-09T00:00:01+00:00",
                ),
            )
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    assert store.load_snapshot() is None


def test_sqlite_project_lifecycle_bootstrap_rolls_back_multi_table_state(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    store = SQLiteSnapshotStore(db_path)
    project_id = "proj_txn"
    now = now_utc_ms()
    project = Project(
        project_id=project_id,
        title="Txn Project",
        state=ProjectState.ACTIVE,
        created_at=now,
        deleted_at=None,
    )
    storage_config = ProjectStorageConfig.create(project_id, str(tmp_path / "txn-project"), updated_at=now)
    project_config = default_project_config(project_id=project_id, updated_at=now)
    review_task_queue = ReviewTaskQueue(project_id=project_id, queue_id="GLOBAL_QUEUE", review_task_ids=tuple(), head_index=0)
    layer = Layer(
        project_id=project_id,
        layer_id="layer_00000001",
        layer_index=0,
        layer_mode=LayerMode.AUTO_TICK_ON_ENTRY,
        orchestrator_managed_review_chain_ids=tuple(),
        aggregation_k_node=10,
        aggregation_k_point=200,
        aggregation_cycle_state=AggregationCycleState.DONE,
    )
    aggregation_queue = AggregationQueue(project_id=project_id, layer_index=0, node_ids=tuple(), head_index=0)
    audit_event = AuditLogEvent(
        project_id=project_id,
        event_id="audit_00000001",
        occurred_at=now,
        kind=AuditEventKind.PROJECT_CREATED,
        api_name="create_project",
        result=AuditResultCode.OK,
        payload='{"projectId":"proj_txn"}',
    )

    try:
        with store.begin_unit_of_work(project_id=project_id) as uow:
            uow.system_state.upsert(
                uow.session,
                SystemStateRecord(
                    schema_version=SCHEMA_VERSION,
                    idgen_counters={"__system__:proj": 1},
                    updated_at="2026-03-09T00:00:00+00:00",
                ),
            )
            uow.project_lifecycle.create_bootstrap(
                uow.session,
                project=project,
                project_snapshot=encode_project_shell_payload(
                    project=project,
                    project_storage_config=storage_config,
                    project_config=project_config,
                ),
                project_storage_config=storage_config,
                project_config=project_config,
                review_task_queue=review_task_queue,
                layers=(layer,),
                aggregation_queues=(aggregation_queue,),
                audit_events=(audit_event,),
                updated_at="2026-03-09T00:00:00+00:00",
            )
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    conn = sqlite3.connect(str(db_path))
    try:
        counts = {
            "project_snapshots": conn.execute("SELECT COUNT(*) FROM project_snapshots").fetchone()[0],
            "project_config_index": conn.execute("SELECT COUNT(*) FROM project_config_index").fetchone()[0],
            "project_storage_config_index": conn.execute("SELECT COUNT(*) FROM project_storage_config_index").fetchone()[0],
            "review_task_queue_index": conn.execute("SELECT COUNT(*) FROM review_task_queue_index").fetchone()[0],
            "layer_state_index": conn.execute("SELECT COUNT(*) FROM layer_state_index").fetchone()[0],
            "aggregation_queue_index": conn.execute("SELECT COUNT(*) FROM aggregation_queue_index").fetchone()[0],
            "audit_log_event_index": conn.execute("SELECT COUNT(*) FROM audit_log_event_index").fetchone()[0],
        }
    finally:
        conn.close()

    assert counts == {
        "project_snapshots": 0,
        "project_config_index": 0,
        "project_storage_config_index": 0,
        "review_task_queue_index": 0,
        "layer_state_index": 0,
        "aggregation_queue_index": 0,
        "audit_log_event_index": 0,
    }


def test_sqlite_unit_of_work_serializes_concurrent_writers(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    store = SQLiteSnapshotStore(db_path)
    writer_started = threading.Event()
    writer_entered = threading.Event()
    writer_finished = threading.Event()

    def _second_writer() -> None:
        writer_started.set()
        with store.begin_unit_of_work(project_id="proj_writer_2") as uow:
            writer_entered.set()
            uow.system_state.upsert(
                uow.session,
                SystemStateRecord(
                    schema_version=SCHEMA_VERSION,
                    idgen_counters={"writer": 2},
                    updated_at="2026-03-09T00:00:02+00:00",
                ),
            )
        writer_finished.set()

    with store.begin_unit_of_work(project_id="proj_writer_1") as uow:
        uow.system_state.upsert(
            uow.session,
            SystemStateRecord(
                schema_version=SCHEMA_VERSION,
                idgen_counters={"writer": 1},
                updated_at="2026-03-09T00:00:01+00:00",
            ),
        )
        thread = threading.Thread(target=_second_writer, daemon=True)
        thread.start()
        assert writer_started.wait(1.0)
        assert not writer_entered.wait(0.2)

    assert writer_entered.wait(1.0)
    assert writer_finished.wait(1.0)
    thread.join(timeout=1.0)

    snapshot = store.load_snapshot()
    assert snapshot is not None
    assert snapshot["idgenCounters"] == {"writer": 2}


def test_system_api_create_project_bypasses_project_payload_commit_path(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    project_root = tmp_path / "project-direct-create"
    system = InMemorySystem(persist_store=SQLiteSnapshotStore(db_path))
    api = SystemAPI(system)

    def _explode(*args, **kwargs):
        raise AssertionError("encode_project_payload should not be called for SQLite create_project")

    monkeypatch.setattr("backend.system.inmemory_system.encode_project_payload", _explode)

    project_id = api.create_project("Direct Create", project_root=str(project_root))

    conn = sqlite3.connect(str(db_path))
    try:
        snapshot_row = conn.execute(
            "SELECT project_state, snapshot_json FROM project_snapshots WHERE project_id = ?",
            (str(project_id),),
        ).fetchone()
        queue_row = conn.execute(
            """
            SELECT queue_id, review_task_ids_json, head_index
            FROM review_task_queue_index
            WHERE project_id = ?
            """,
            (str(project_id),),
        ).fetchone()
        layer_row = conn.execute(
            """
            SELECT layer_index, aggregation_cycle_state
            FROM layer_state_index
            WHERE project_id = ?
            """,
            (str(project_id),),
        ).fetchone()
        aggq_row = conn.execute(
            """
            SELECT layer_index, node_ids_json, head_index
            FROM aggregation_queue_index
            WHERE project_id = ?
            """,
            (str(project_id),),
        ).fetchone()
        audit_row = conn.execute(
            """
            SELECT kind, api_name, result
            FROM audit_log_event_index
            WHERE project_id = ?
            ORDER BY occurred_at_ms ASC, event_id ASC
            """,
            (str(project_id),),
        ).fetchone()
    finally:
        conn.close()

    assert snapshot_row is not None
    assert snapshot_row[0] == "ACTIVE"
    snapshot_payload = json.loads(str(snapshot_row[1]))
    assert set(snapshot_payload.keys()) == {
        "project",
        "projectConfig",
        "projectStorageConfig",
        "projectMaterialSourceBinding",
    }
    assert snapshot_payload["projectMaterialSourceBinding"]["sourceKind"] == "SERVER_FS"
    assert queue_row == ("GLOBAL_QUEUE", "[]", 0)
    assert layer_row == (0, "DONE")
    assert aggq_row == (0, "[]", 0)
    assert audit_row == ("PROJECT_CREATED", "create_project", "OK")
    assert system.g.projects[str(project_id)].project is not None
    assert system.g.projects[str(project_id)].project.title == "Direct Create"


def test_system_api_delete_project_bypasses_project_payload_commit_path(monkeypatch, tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    system = InMemorySystem(persist_store=SQLiteSnapshotStore(db_path))
    api = SystemAPI(system)

    def _explode(*args, **kwargs):
        raise AssertionError("encode_project_payload should not be called for SQLite delete_project")

    monkeypatch.setattr("backend.system.inmemory_system.encode_project_payload", _explode)

    project_id = api.create_project("Direct Delete")
    api.delete_project(project_id)

    conn = sqlite3.connect(str(db_path))
    try:
        snapshot_row = conn.execute(
            "SELECT project_state, snapshot_json FROM project_snapshots WHERE project_id = ?",
            (str(project_id),),
        ).fetchone()
        config_count = conn.execute(
            "SELECT COUNT(*) FROM project_config_index WHERE project_id = ?",
            (str(project_id),),
        ).fetchone()
        storage_count = conn.execute(
            "SELECT COUNT(*) FROM project_storage_config_index WHERE project_id = ?",
            (str(project_id),),
        ).fetchone()
        queue_count = conn.execute(
            "SELECT COUNT(*) FROM review_task_queue_index WHERE project_id = ?",
            (str(project_id),),
        ).fetchone()
        layer_count = conn.execute(
            "SELECT COUNT(*) FROM layer_state_index WHERE project_id = ?",
            (str(project_id),),
        ).fetchone()
        audit_rows = conn.execute(
            """
            SELECT kind, api_name, result
            FROM audit_log_event_index
            WHERE project_id = ?
            ORDER BY occurred_at_ms ASC, event_id ASC
            """,
            (str(project_id),),
        ).fetchall()
    finally:
        conn.close()

    assert snapshot_row is not None
    assert snapshot_row[0] == "DELETED"
    assert set(json.loads(str(snapshot_row[1])).keys()) == {"project"}
    assert config_count == (0,)
    assert storage_count == (0,)
    assert queue_count == (0,)
    assert layer_count == (0,)
    assert audit_rows == [("PROJECT_DELETED", "delete_project", "OK")]
    assert system.g.projects[str(project_id)].project is not None
    assert system.g.projects[str(project_id)].project.state.value == "DELETED"


def test_sqlite_store_refreshes_entity_index_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    project_root = tmp_path / "project-delta"
    system = InMemorySystem(persist_store=SQLiteSnapshotStore(db_path))
    api = SystemAPI(system)
    project_id = api.create_project("Delta", project_root=str(project_root))

    session = system.begin_session(project_id, SessionMode.READ_WRITE)
    try:
        instance = Instance.create(
            project_id=project_id,
            instance_id=system.g.idgen.new_instance_id(project_id),
            material_id="course/lesson-1.mp4",
            presence=InstancePresence.PRESENT,
        )
        system.instance_repo.add(session, instance)

        leaf = LearningObjectLeaf(
            source="MANUAL",
            project_id=project_id,
            node_id=system.g.idgen.new_learning_object_node_id(project_id),
            relative_path=instance.material_id,
            parent_id=None,
            instance_id=instance.instance_id,
            title="Lesson 1",
        )
        system.learning_object_repo.add(session, leaf)

        recall_point = RecallPoint(
            project_id=project_id,
            recall_point_id=system.g.idgen.new_recall_point_id(project_id),
            created_at=now_utc_ms(),
            question=rich_text("What happened?"),
            answer=rich_text("Lesson one happened."),
            anchor=Anchor(instance_id=instance.instance_id, position="t=1000"),
        )
        system.recall_point_repo.add(session, recall_point)
        system.commit(session)
    finally:
        if session.state == "OPEN":
            system.rollback(session)

    conn = sqlite3.connect(str(db_path))
    try:
        instance_row = conn.execute(
            """
            SELECT material_id, material_display_name, presence
            FROM instance_index
            WHERE project_id = ? AND instance_id = ?
            """,
            (str(project_id), str(instance.instance_id)),
        ).fetchone()
        node_row = conn.execute(
            """
            SELECT node_kind, source, relative_path, instance_id, title, child_count
            FROM learning_object_node_index
            WHERE project_id = ? AND node_id = ?
            """,
            (str(project_id), str(leaf.node_id)),
        ).fetchone()
        recall_point_row = conn.execute(
            """
            SELECT anchor_instance_id, anchor_position, question_plain_text, answer_plain_text, insights_count
            FROM recall_point_index
            WHERE project_id = ? AND recall_point_id = ?
            """,
            (str(project_id), str(recall_point.recall_point_id)),
        ).fetchone()
    finally:
        conn.close()

    assert instance_row == ("course/lesson-1.mp4", "lesson-1.mp4", "PRESENT")
    assert node_row == ("LEAF", "MANUAL", "course/lesson-1.mp4", str(instance.instance_id), "Lesson 1", 0)
    assert recall_point_row == (
        str(instance.instance_id),
        "t=1000",
        "What happened?",
        "Lesson one happened.",
        0,
    )


def test_sqlite_store_externalizes_core_entities_from_snapshot_row(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    system = InMemorySystem(persist_store=SQLiteSnapshotStore(db_path))
    api = SystemAPI(system)
    project_id = api.create_project("Externalized")

    session = system.begin_session(project_id, SessionMode.READ_WRITE)
    try:
        instance = Instance.create(
            project_id=project_id,
            instance_id=system.g.idgen.new_instance_id(project_id),
            material_id="course/lesson-2.mp4",
            presence=InstancePresence.PRESENT,
        )
        system.instance_repo.add(session, instance)
        leaf = LearningObjectLeaf(
            source="MANUAL",
            project_id=project_id,
            node_id=system.g.idgen.new_learning_object_node_id(project_id),
            relative_path=instance.material_id,
            parent_id=None,
            instance_id=instance.instance_id,
            title="Lesson 2",
        )
        system.learning_object_repo.add(session, leaf)
        recall_point = RecallPoint(
            project_id=project_id,
            recall_point_id=system.g.idgen.new_recall_point_id(project_id),
            created_at=now_utc_ms(),
            question=rich_text("What changed in lesson 2?"),
            answer=rich_text("Lesson 2 introduced a new concept."),
            anchor=Anchor(instance_id=instance.instance_id, position="t=2500"),
        )
        system.recall_point_repo.add(session, recall_point)
        range_snapshot = RangeSnapshot(
            project_id=project_id,
            range_id=system.g.idgen.new_range_id(project_id),
            recall_point_ids=(recall_point.recall_point_id,),
        )
        system.range_repo.add(session, range_snapshot)
        learning_task = LearningTask(
            project_id=project_id,
            learning_task_id=system.g.idgen.new_learning_task_id(project_id),
            recall_point_ids=(recall_point.recall_point_id,),
            title="Lesson 2 task",
        )
        system.learning_task_repo.add(session, learning_task)
        task_node = LearningTaskLeaf(
            project_id=project_id,
            node_id=system.g.idgen.new_learning_task_node_id(project_id),
            parent_id=None,
            bound_learning_task_id=learning_task.learning_task_id,
            title="Lesson 2 node",
        )
        system.learning_task_node_repo.add(session, task_node)
        review_chain = ReviewChain(
            project_id=project_id,
            review_chain_id=system.g.idgen.new_review_chain_id(project_id),
            queue=tuple(),
            head_index=0,
            state=ReviewChainState.IN_PROGRESS,
        )
        system.review_chain_repo.add(session, review_chain)
        review_task = ReviewTask(
            project_id=project_id,
            review_task_id=system.g.idgen.new_review_task_id(project_id),
            input_range_id=range_snapshot.range_id,
            created_at=now_utc_ms(),
            state=ReviewTaskState.PENDING,
        )
        system.review_task_repo.add(session, review_task)
        convergence = Convergence(
            project_id=project_id,
            convergence_id=system.g.idgen.new_convergence_id(project_id),
            seed_range_id=range_snapshot.range_id,
            rule_id=ConvergenceRuleId("conv_rule_externalized"),
            review_task_ids=(review_task.review_task_id,),
            state=ConvergenceState.IN_PROGRESS,
        )
        system.convergence_repo.add(session, convergence)
        system.entry_repo.add(
            session,
            EntryRegistration(
                project_id=project_id,
                entry_node=task_node.node_id,
                target_layer_index=0,
                review_chain_id=review_chain.review_chain_id,
                registration_seq=1,
            ),
        )
        asr_artifact = AsrArtifact(
            project_id=project_id,
            asr_artifact_id=system.g.idgen.new_asr_artifact_id(project_id),
            created_at=now_utc_ms(),
            provider=AsrProvider.WHISPER,
            producer_runtime_kind=ClientRuntimeKind.DESKTOP_NATIVE,
            recall_point_id=recall_point.recall_point_id,
            source_instance_id=instance.instance_id,
            center_ms=2500,
            pre_ms=1000,
            post_ms=1500,
            segments=(AsrSegment(start_ms=2000, end_ms=2600, text="Lesson 2 introduced a concept."),),
        )
        system.asr_artifact_repo.add(session, asr_artifact)
        aggregation_event = AggregationEvent(
            project_id=project_id,
            event_id=system.g.idgen.new_aggregation_event_id(project_id),
            created_at=now_utc_ms(),
            layer_index=0,
            parent_node_id=task_node.node_id,
            child_node_ids=(task_node.node_id,),
            reason=AggregationEventReason.MANUAL_DRAIN,
            title="Lesson 2 aggregation",
        )
        system.event_repo.append(session, aggregation_event)
        system.material_allowlist_repo.replace(session, (instance.material_id,))
        media_asset = MediaAsset(
            project_id=project_id,
            asset_id=MediaAssetId("asset_000001"),
            kind=MediaAssetKind.IMAGE,
            relative_path=PurePosixPath("media/lesson-2.png"),
            created_at=now_utc_ms(),
            mime_type="image/png",
        )
        system.media_asset_repo.add(session, media_asset)
        review_record = RecallPointReviewRecord(
            project_id=project_id,
            record_id=system.g.idgen.new_recall_point_review_record_id(project_id),
            recall_point_id=recall_point.recall_point_id,
            review_task_id=review_task.review_task_id,
            occurred_at=now_utc_ms(),
            result=RecallPointReviewResult.CAN_RECALL,
        )
        system.recall_point_review_record_repo.append(session, review_record)
        system.commit(session)
    finally:
        if session.state == "OPEN":
            system.rollback(session)

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT snapshot_json FROM project_snapshots WHERE project_id = ?", (str(project_id),)).fetchone()
        learning_task_row = conn.execute(
            """
            SELECT title, recall_point_count
            FROM learning_task_index
            WHERE project_id = ? AND learning_task_id = ?
            """,
            (str(project_id), str(learning_task.learning_task_id)),
        ).fetchone()
        learning_task_node_row = conn.execute(
            """
            SELECT node_kind, bound_learning_task_id, title
            FROM learning_task_node_index
            WHERE project_id = ? AND node_id = ?
            """,
            (str(project_id), str(task_node.node_id)),
        ).fetchone()
        entry_reg_row = conn.execute(
            """
            SELECT target_layer_index, review_chain_id, registration_seq
            FROM entry_registration_index
            WHERE project_id = ? AND entry_node = ?
            """,
            (str(project_id), str(task_node.node_id)),
        ).fetchone()
        range_snapshot_row = conn.execute(
            """
            SELECT recall_point_count
            FROM range_snapshot_index
            WHERE project_id = ? AND range_id = ?
            """,
            (str(project_id), str(range_snapshot.range_id)),
        ).fetchone()
        review_task_row = conn.execute(
            """
            SELECT input_range_id, state
            FROM review_task_index
            WHERE project_id = ? AND review_task_id = ?
            """,
            (str(project_id), str(review_task.review_task_id)),
        ).fetchone()
        convergence_row = conn.execute(
            """
            SELECT seed_range_id, rule_id, round_count, state
            FROM convergence_index
            WHERE project_id = ? AND convergence_id = ?
            """,
            (str(project_id), str(convergence.convergence_id)),
        ).fetchone()
        review_chain_row = conn.execute(
            """
            SELECT queue_length, head_index, state
            FROM review_chain_index
            WHERE project_id = ? AND review_chain_id = ?
            """,
            (str(project_id), str(review_chain.review_chain_id)),
        ).fetchone()
        queue_row = conn.execute(
            """
            SELECT queue_id, head_index
            FROM review_task_queue_index
            WHERE project_id = ?
            """,
            (str(project_id),),
        ).fetchone()
        layer_row = conn.execute(
            """
            SELECT layer_index, aggregation_k_node, aggregation_k_point, aggregation_cycle_state, normal_tick_quota_remaining
            FROM layer_state_index
            WHERE project_id = ?
            ORDER BY layer_index ASC
            LIMIT 1
            """,
            (str(project_id),),
        ).fetchone()
        audit_event_count_row = conn.execute(
            "SELECT COUNT(*) FROM audit_log_event_index WHERE project_id = ?",
            (str(project_id),),
        ).fetchone()
        asr_artifact_row = conn.execute(
            """
            SELECT provider, recall_point_id, source_instance_id, center_ms
            FROM asr_artifact_index
            WHERE project_id = ? AND asr_artifact_id = ?
            """,
            (str(project_id), str(asr_artifact.asr_artifact_id)),
        ).fetchone()
        aggregation_queue_row = conn.execute(
            """
            SELECT layer_index, head_index
            FROM aggregation_queue_index
            WHERE project_id = ? AND layer_index = 0
            """,
            (str(project_id),),
        ).fetchone()
        aggregation_event_row = conn.execute(
            """
            SELECT layer_index, parent_node_id, reason, title
            FROM aggregation_event_index
            WHERE project_id = ? AND event_id = ?
            """,
            (str(project_id), str(aggregation_event.event_id)),
        ).fetchone()
        material_allowlist_row = conn.execute(
            """
            SELECT allowlist_id, material_count
            FROM material_allowlist_index
            WHERE project_id = ?
            """,
            (str(project_id),),
        ).fetchone()
        media_asset_row = conn.execute(
            """
            SELECT kind, relative_path, mime_type
            FROM media_asset_index
            WHERE project_id = ? AND asset_id = ?
            """,
            (str(project_id), str(media_asset.asset_id)),
        ).fetchone()
        review_record_row = conn.execute(
            """
            SELECT recall_point_id, review_task_id, result
            FROM recall_point_review_record_index
            WHERE project_id = ? AND record_id = ?
            """,
            (str(project_id), str(review_record.record_id)),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert learning_task_row == ("Lesson 2 task", 1)
    assert learning_task_node_row == ("LEAF", str(learning_task.learning_task_id), "Lesson 2 node")
    assert entry_reg_row == (0, str(review_chain.review_chain_id), 1)
    assert range_snapshot_row == (1,)
    assert review_task_row == (str(range_snapshot.range_id), "PENDING")
    assert convergence_row == (str(range_snapshot.range_id), "conv_rule_externalized", 1, "IN_PROGRESS")
    assert review_chain_row == (0, 0, "IN_PROGRESS")
    assert queue_row == ("GLOBAL_QUEUE", 0)
    assert layer_row is not None
    assert layer_row[0] == 0
    assert audit_event_count_row is not None and int(audit_event_count_row[0]) >= 1
    assert asr_artifact_row == ("WHISPER", str(recall_point.recall_point_id), str(instance.instance_id), 2500)
    assert aggregation_queue_row == (0, 0)
    assert aggregation_event_row == (0, str(task_node.node_id), "MANUAL_DRAIN", "Lesson 2 aggregation")
    assert material_allowlist_row == ("MATERIAL_ALLOWLIST_V1", 1)
    assert media_asset_row == ("IMAGE", "media/lesson-2.png", "image/png")
    assert review_record_row == (str(recall_point.recall_point_id), str(review_task.review_task_id), "CAN_RECALL")
    snapshot_payload = json.loads(str(row[0]))
    assert "projectStorageConfig" in snapshot_payload
    assert "projectConfig" in snapshot_payload
    assert "instances" not in snapshot_payload
    assert "learningObjectNodes" not in snapshot_payload
    assert "recallPoints" not in snapshot_payload
    assert "learningTasks" not in snapshot_payload
    assert "learningTaskNodes" not in snapshot_payload
    assert "entryRegs" not in snapshot_payload
    assert "rangeSnapshots" not in snapshot_payload
    assert "reviewTasks" not in snapshot_payload
    assert "convergences" not in snapshot_payload
    assert "reviewChains" not in snapshot_payload
    assert "reviewTaskQueue" not in snapshot_payload
    assert "layers" not in snapshot_payload
    assert "layersByIndex" not in snapshot_payload
    assert "auditLogEvents" not in snapshot_payload
    assert "asrArtifacts" not in snapshot_payload
    assert "aggregationQueues" not in snapshot_payload
    assert "aggregationEvents" not in snapshot_payload
    assert "materialAllowlist" not in snapshot_payload
    assert "mediaAssets" not in snapshot_payload
    assert "recallPointReviewRecords" not in snapshot_payload
    assert "aggregationKNode" not in snapshot_payload
    assert "aggregationKPoint" not in snapshot_payload
    assert "aggregationCycleState" not in snapshot_payload
    assert "pendingRollUpParentNodeId" not in snapshot_payload
    assert "normalTickQuotaRemaining" not in snapshot_payload

    snapshot = SQLiteSnapshotStore(db_path).load_snapshot()

    assert snapshot is not None
    restored_project = snapshot["projects"][str(project_id)]
    assert restored_project["projectStorageConfig"]["projectId"] == str(project_id)
    assert restored_project["projectConfig"]["projectId"] == str(project_id)
    assert list(restored_project["instances"].keys()) == [str(instance.instance_id)]
    assert list(restored_project["learningObjectNodes"].keys()) == [str(leaf.node_id)]
    assert list(restored_project["recallPoints"].keys()) == [str(recall_point.recall_point_id)]
    assert list(restored_project["learningTasks"].keys()) == [str(learning_task.learning_task_id)]
    assert list(restored_project["learningTaskNodes"].keys()) == [str(task_node.node_id)]
    assert list(restored_project["entryRegs"].keys()) == [str(task_node.node_id)]
    assert restored_project["entryRegs"][str(task_node.node_id)]["registrationSeq"] == 1
    assert list(restored_project["rangeSnapshots"].keys()) == [str(range_snapshot.range_id)]
    assert list(restored_project["reviewTasks"].keys()) == [str(review_task.review_task_id)]
    assert list(restored_project["convergences"].keys()) == [str(convergence.convergence_id)]
    assert list(restored_project["reviewChains"].keys()) == [str(review_chain.review_chain_id)]
    assert restored_project["reviewTaskQueue"]["queueId"] == "GLOBAL_QUEUE"
    assert list(restored_project["layersByIndex"].keys()) == ["0"]
    assert restored_project["auditLogEvents"]
    assert list(restored_project["asrArtifacts"].keys()) == [str(asr_artifact.asr_artifact_id)]
    assert list(restored_project["aggregationQueues"].keys()) == ["0"]
    assert list(restored_project["aggregationEvents"].keys()) == [str(aggregation_event.event_id)]
    assert restored_project["materialAllowlist"]["allowlistId"] == "MATERIAL_ALLOWLIST_V1"
    assert list(restored_project["mediaAssets"].keys()) == [str(media_asset.asset_id)]
    assert list(restored_project["recallPointReviewRecords"].keys()) == [str(review_record.record_id)]
    assert restored_project["aggregationKNode"]
    assert restored_project["aggregationKPoint"]
    assert restored_project["aggregationCycleState"]
    assert "0" in restored_project["normalTickQuotaRemaining"]


def test_sqlite_store_compacts_legacy_snapshot_rows_on_reload(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    system = InMemorySystem(persist_store=SQLiteSnapshotStore(db_path))
    api = SystemAPI(system)
    project_id = api.create_project("Compaction")

    session = system.begin_session(project_id, SessionMode.READ_WRITE)
    try:
        instance = Instance.create(
            project_id=project_id,
            instance_id=system.g.idgen.new_instance_id(project_id),
            material_id="course/legacy.mp4",
            presence=InstancePresence.PRESENT,
        )
        system.instance_repo.add(session, instance)
        leaf = LearningObjectLeaf(
            source="MANUAL",
            project_id=project_id,
            node_id=system.g.idgen.new_learning_object_node_id(project_id),
            relative_path=instance.material_id,
            parent_id=None,
            instance_id=instance.instance_id,
            title="Legacy Lesson",
        )
        system.learning_object_repo.add(session, leaf)
        recall_point = RecallPoint(
            project_id=project_id,
            recall_point_id=system.g.idgen.new_recall_point_id(project_id),
            created_at=now_utc_ms(),
            question=rich_text("Legacy question"),
            answer=rich_text("Legacy answer"),
            anchor=Anchor(instance_id=instance.instance_id, position="t=5000"),
        )
        system.recall_point_repo.add(session, recall_point)
        range_snapshot = RangeSnapshot(
            project_id=project_id,
            range_id=system.g.idgen.new_range_id(project_id),
            recall_point_ids=(recall_point.recall_point_id,),
        )
        system.range_repo.add(session, range_snapshot)
        learning_task = LearningTask(
            project_id=project_id,
            learning_task_id=system.g.idgen.new_learning_task_id(project_id),
            recall_point_ids=(recall_point.recall_point_id,),
            title="Legacy task",
        )
        system.learning_task_repo.add(session, learning_task)
        task_node = LearningTaskLeaf(
            project_id=project_id,
            node_id=system.g.idgen.new_learning_task_node_id(project_id),
            parent_id=None,
            bound_learning_task_id=learning_task.learning_task_id,
            title="Legacy task node",
        )
        system.learning_task_node_repo.add(session, task_node)
        review_chain = ReviewChain(
            project_id=project_id,
            review_chain_id=system.g.idgen.new_review_chain_id(project_id),
            queue=tuple(),
            head_index=0,
            state=ReviewChainState.IN_PROGRESS,
        )
        system.review_chain_repo.add(session, review_chain)
        review_task = ReviewTask(
            project_id=project_id,
            review_task_id=system.g.idgen.new_review_task_id(project_id),
            input_range_id=range_snapshot.range_id,
            created_at=now_utc_ms(),
            state=ReviewTaskState.PENDING,
        )
        system.review_task_repo.add(session, review_task)
        convergence = Convergence(
            project_id=project_id,
            convergence_id=system.g.idgen.new_convergence_id(project_id),
            seed_range_id=range_snapshot.range_id,
            rule_id=ConvergenceRuleId("conv_rule_legacy"),
            review_task_ids=(review_task.review_task_id,),
            state=ConvergenceState.IN_PROGRESS,
        )
        system.convergence_repo.add(session, convergence)
        system.entry_repo.add(
            session,
            EntryRegistration(
                project_id=project_id,
                entry_node=task_node.node_id,
                target_layer_index=0,
                review_chain_id=review_chain.review_chain_id,
                registration_seq=1,
            ),
        )
        asr_artifact = AsrArtifact(
            project_id=project_id,
            asr_artifact_id=system.g.idgen.new_asr_artifact_id(project_id),
            created_at=now_utc_ms(),
            provider=AsrProvider.WHISPER,
            producer_runtime_kind=ClientRuntimeKind.DESKTOP_NATIVE,
            recall_point_id=recall_point.recall_point_id,
            source_instance_id=instance.instance_id,
            center_ms=5000,
            pre_ms=1200,
            post_ms=1400,
            segments=(AsrSegment(start_ms=4500, end_ms=5200, text="Legacy concept."),),
        )
        system.asr_artifact_repo.add(session, asr_artifact)
        aggregation_event = AggregationEvent(
            project_id=project_id,
            event_id=system.g.idgen.new_aggregation_event_id(project_id),
            created_at=now_utc_ms(),
            layer_index=0,
            parent_node_id=task_node.node_id,
            child_node_ids=(task_node.node_id,),
            reason=AggregationEventReason.MANUAL_DRAIN,
            title="Legacy aggregation",
        )
        system.event_repo.append(session, aggregation_event)
        system.material_allowlist_repo.replace(session, (instance.material_id,))
        media_asset = MediaAsset(
            project_id=project_id,
            asset_id=MediaAssetId("asset_legacy_000001"),
            kind=MediaAssetKind.IMAGE,
            relative_path=PurePosixPath("media/legacy.png"),
            created_at=now_utc_ms(),
            mime_type="image/png",
        )
        system.media_asset_repo.add(session, media_asset)
        review_record = RecallPointReviewRecord(
            project_id=project_id,
            record_id=system.g.idgen.new_recall_point_review_record_id(project_id),
            recall_point_id=recall_point.recall_point_id,
            review_task_id=review_task.review_task_id,
            occurred_at=now_utc_ms(),
            result=RecallPointReviewResult.CANNOT_RECALL,
        )
        system.recall_point_review_record_repo.append(session, review_record)
        system.commit(session)
    finally:
        if session.state == "OPEN":
            system.rollback(session)

    store = SQLiteSnapshotStore(db_path)
    hydrated_snapshot = store.load_snapshot()
    assert hydrated_snapshot is not None
    full_payload = dict(hydrated_snapshot["projects"][str(project_id)])
    full_payload["instances"] = {
        **dict(full_payload.get("instances", {})),
        "inst_shell_only": {
            "projectId": str(project_id),
            "instanceId": "inst_shell_only",
            "materialId": "course/shell-only.mp4",
            "presence": "PRESENT",
            "lastSeenAtMs": None,
        },
    }

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "UPDATE project_snapshots SET snapshot_json = ? WHERE project_id = ?",
            (json.dumps(full_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True), str(project_id)),
        )
        conn.execute(
            "UPDATE recall_point_index SET payload_json = NULL WHERE project_id = ?",
            (str(project_id),),
        )
        conn.commit()
    finally:
        conn.close()

    reloaded = SQLiteSnapshotStore(db_path)
    loaded_again = reloaded.load_snapshot()
    assert loaded_again is not None
    restored_project = dict(loaded_again["projects"][str(project_id)])
    assert "inst_shell_only" not in dict(restored_project.get("instances", {}))

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT snapshot_json FROM project_snapshots WHERE project_id = ?", (str(project_id),)).fetchone()
    finally:
        conn.close()

    assert row is not None
    compacted_payload = json.loads(str(row[0]))
    assert "instances" not in compacted_payload
    assert "learningObjectNodes" not in compacted_payload
    assert "recallPoints" not in compacted_payload
    assert "learningTasks" not in compacted_payload
    assert "learningTaskNodes" not in compacted_payload
    assert "entryRegs" not in compacted_payload
    assert "rangeSnapshots" not in compacted_payload
    assert "reviewTasks" not in compacted_payload
    assert "convergences" not in compacted_payload
    assert "reviewChains" not in compacted_payload
    assert "reviewTaskQueue" not in compacted_payload
    assert "layers" not in compacted_payload
    assert "layersByIndex" not in compacted_payload
    assert "auditLogEvents" not in compacted_payload
    assert "asrArtifacts" not in compacted_payload
    assert "aggregationQueues" not in compacted_payload
    assert "aggregationEvents" not in compacted_payload
    assert "materialAllowlist" not in compacted_payload
    assert "mediaAssets" not in compacted_payload
    assert "recallPointReviewRecords" not in compacted_payload
    assert "aggregationKNode" not in compacted_payload
    assert "aggregationKPoint" not in compacted_payload
    assert "aggregationCycleState" not in compacted_payload
    assert "pendingRollUpParentNodeId" not in compacted_payload
    assert "normalTickQuotaRemaining" not in compacted_payload

    conn = sqlite3.connect(str(db_path))
    try:
        payload_row = conn.execute(
            "SELECT payload_json FROM recall_point_index WHERE project_id = ? AND recall_point_id = ?",
            (str(project_id), str(recall_point.recall_point_id)),
        ).fetchone()
        learning_task_row = conn.execute(
            """
            SELECT title, recall_point_count
            FROM learning_task_index
            WHERE project_id = ? AND learning_task_id = ?
            """,
            (str(project_id), str(learning_task.learning_task_id)),
        ).fetchone()
        task_node_row = conn.execute(
            """
            SELECT node_kind, bound_learning_task_id, title
            FROM learning_task_node_index
            WHERE project_id = ? AND node_id = ?
            """,
            (str(project_id), str(task_node.node_id)),
        ).fetchone()
        entry_reg_row = conn.execute(
            """
            SELECT target_layer_index, review_chain_id, registration_seq
            FROM entry_registration_index
            WHERE project_id = ? AND entry_node = ?
            """,
            (str(project_id), str(task_node.node_id)),
        ).fetchone()
        range_snapshot_row = conn.execute(
            """
            SELECT recall_point_count
            FROM range_snapshot_index
            WHERE project_id = ? AND range_id = ?
            """,
            (str(project_id), str(range_snapshot.range_id)),
        ).fetchone()
        review_task_row = conn.execute(
            """
            SELECT input_range_id, state
            FROM review_task_index
            WHERE project_id = ? AND review_task_id = ?
            """,
            (str(project_id), str(review_task.review_task_id)),
        ).fetchone()
        convergence_row = conn.execute(
            """
            SELECT seed_range_id, rule_id, round_count, state
            FROM convergence_index
            WHERE project_id = ? AND convergence_id = ?
            """,
            (str(project_id), str(convergence.convergence_id)),
        ).fetchone()
        review_chain_row = conn.execute(
            """
            SELECT queue_length, head_index, state
            FROM review_chain_index
            WHERE project_id = ? AND review_chain_id = ?
            """,
            (str(project_id), str(review_chain.review_chain_id)),
        ).fetchone()
        queue_row = conn.execute(
            """
            SELECT queue_id, head_index
            FROM review_task_queue_index
            WHERE project_id = ?
            """,
            (str(project_id),),
        ).fetchone()
        layer_row = conn.execute(
            """
            SELECT layer_index, aggregation_k_node, aggregation_k_point, aggregation_cycle_state, normal_tick_quota_remaining
            FROM layer_state_index
            WHERE project_id = ?
            ORDER BY layer_index ASC
            LIMIT 1
            """,
            (str(project_id),),
        ).fetchone()
        audit_event_count_row = conn.execute(
            "SELECT COUNT(*) FROM audit_log_event_index WHERE project_id = ?",
            (str(project_id),),
        ).fetchone()
        asr_artifact_row = conn.execute(
            """
            SELECT provider, recall_point_id, source_instance_id, center_ms
            FROM asr_artifact_index
            WHERE project_id = ? AND asr_artifact_id = ?
            """,
            (str(project_id), str(asr_artifact.asr_artifact_id)),
        ).fetchone()
        aggregation_queue_row = conn.execute(
            """
            SELECT layer_index, head_index
            FROM aggregation_queue_index
            WHERE project_id = ? AND layer_index = 0
            """,
            (str(project_id),),
        ).fetchone()
        aggregation_event_row = conn.execute(
            """
            SELECT layer_index, parent_node_id, reason, title
            FROM aggregation_event_index
            WHERE project_id = ? AND event_id = ?
            """,
            (str(project_id), str(aggregation_event.event_id)),
        ).fetchone()
        material_allowlist_row = conn.execute(
            """
            SELECT allowlist_id, material_count
            FROM material_allowlist_index
            WHERE project_id = ?
            """,
            (str(project_id),),
        ).fetchone()
        media_asset_row = conn.execute(
            """
            SELECT kind, relative_path, mime_type
            FROM media_asset_index
            WHERE project_id = ? AND asset_id = ?
            """,
            (str(project_id), str(media_asset.asset_id)),
        ).fetchone()
        review_record_row = conn.execute(
            """
            SELECT recall_point_id, review_task_id, result
            FROM recall_point_review_record_index
            WHERE project_id = ? AND record_id = ?
            """,
            (str(project_id), str(review_record.record_id)),
        ).fetchone()
    finally:
        conn.close()

    assert payload_row is not None
    assert payload_row[0] is not None
    assert learning_task_row == ("Legacy task", 1)
    assert task_node_row == ("LEAF", str(learning_task.learning_task_id), "Legacy task node")
    assert entry_reg_row == (0, str(review_chain.review_chain_id), 1)
    assert range_snapshot_row == (1,)
    assert review_task_row == (str(range_snapshot.range_id), "PENDING")
    assert convergence_row == (str(range_snapshot.range_id), "conv_rule_legacy", 1, "IN_PROGRESS")
    assert review_chain_row == (0, 0, "IN_PROGRESS")
    assert queue_row == ("GLOBAL_QUEUE", 0)
    assert layer_row is not None
    assert layer_row[0] == 0
    assert audit_event_count_row is not None and int(audit_event_count_row[0]) >= 1
    assert asr_artifact_row == ("WHISPER", str(recall_point.recall_point_id), str(instance.instance_id), 5000)
    assert aggregation_queue_row == (0, 0)
    assert aggregation_event_row == (0, str(task_node.node_id), "MANUAL_DRAIN", "Legacy aggregation")
    assert material_allowlist_row == ("MATERIAL_ALLOWLIST_V1", 1)
    assert media_asset_row == ("IMAGE", "media/legacy.png", "image/png")
    assert review_record_row == (str(recall_point.recall_point_id), str(review_task.review_task_id), "CANNOT_RECALL")


def test_system_api_reads_common_views_from_sqlite_indexes(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    project_root = tmp_path / "project-epsilon"
    system = InMemorySystem(persist_store=SQLiteSnapshotStore(db_path))
    api = SystemAPI(system)
    project_id = api.create_project("Epsilon", project_root=str(project_root))

    session = system.begin_session(project_id, SessionMode.READ_WRITE)
    try:
        instance = Instance.create(
            project_id=project_id,
            instance_id=system.g.idgen.new_instance_id(project_id),
            material_id="series/episode-1.mp4",
            presence=InstancePresence.PRESENT,
        )
        system.instance_repo.add(session, instance)
        leaf = LearningObjectLeaf(
            source="MANUAL",
            project_id=project_id,
            node_id=system.g.idgen.new_learning_object_node_id(project_id),
            relative_path=instance.material_id,
            parent_id=None,
            instance_id=instance.instance_id,
            title="Episode 1",
        )
        system.learning_object_repo.add(session, leaf)
        system.commit(session)
    finally:
        if session.state == "OPEN":
            system.rollback(session)

    system.g.projects[str(project_id)].instances.clear()
    system.g.projects[str(project_id)].learning_object_nodes.clear()
    api._startup_fs_sync_done.add(id_canonical_text(project_id))

    projects = api.list_projects()
    instances = api.list_instances(project_id)
    nodes = api.list_learning_object_nodes(project_id)
    fetched = api.get_learning_object_node(project_id, leaf.node_id)

    assert any(str(project.project_id) == str(project_id) for project in projects)
    assert [str(item.instance_id) for item in instances] == [str(instance.instance_id)]
    assert [str(item.node_id) for item in nodes] == [str(leaf.node_id)]
    assert str(fetched.node_id) == str(leaf.node_id)


def test_system_api_reads_recall_points_from_sqlite_indexes(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    system = InMemorySystem(persist_store=SQLiteSnapshotStore(db_path))
    api = SystemAPI(system)
    project_id = api.create_project("Zeta")

    session = system.begin_session(project_id, SessionMode.READ_WRITE)
    try:
        instance = Instance.create(
            project_id=project_id,
            instance_id=system.g.idgen.new_instance_id(project_id),
            material_id="series/episode-2.mp4",
            presence=InstancePresence.PRESENT,
        )
        system.instance_repo.add(session, instance)
        leaf = LearningObjectLeaf(
            source="MANUAL",
            project_id=project_id,
            node_id=system.g.idgen.new_learning_object_node_id(project_id),
            relative_path=instance.material_id,
            parent_id=None,
            instance_id=instance.instance_id,
            title="Episode 2",
        )
        system.learning_object_repo.add(session, leaf)
        recall_point = RecallPoint(
            project_id=project_id,
            recall_point_id=system.g.idgen.new_recall_point_id(project_id),
            created_at=now_utc_ms(),
            question=rich_text("Who arrived?"),
            answer=rich_text("Episode two protagonist arrived."),
            anchor=Anchor(instance_id=instance.instance_id, position="t=2000"),
        )
        system.recall_point_repo.add(session, recall_point)
        system.commit(session)
    finally:
        if session.state == "OPEN":
            system.rollback(session)

    system.g.projects[str(project_id)].instances.clear()
    system.g.projects[str(project_id)].learning_object_nodes.clear()
    system.g.projects[str(project_id)].recall_points.clear()
    api._startup_fs_sync_done.add(id_canonical_text(project_id))

    recall_point_ids = api.list_recall_points_by_instance(project_id, instance.instance_id)
    fetched = api.get_recall_point(project_id, recall_point.recall_point_id)
    listed = api.list_recall_points_by_learning_object_node(project_id, leaf.node_id)

    assert recall_point_ids == (recall_point.recall_point_id,)
    assert str(fetched.recall_point_id) == str(recall_point.recall_point_id)
    assert fetched.question[0].text == "Who arrived?"
    assert fetched.answer[0].text == "Episode two protagonist arrived."
    assert fetched.anchor.position == "t=2000"
    assert [str(item.recall_point_id) for item in listed] == [str(recall_point.recall_point_id)]


def test_system_api_reads_project_views_from_sqlite_project_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "plm_store.sqlite3"
    project_root = tmp_path / "project-theta"
    system = InMemorySystem(persist_store=SQLiteSnapshotStore(db_path))
    api = SystemAPI(system)
    project_id = api.create_project("Theta", project_root=str(project_root))

    session = system.begin_session(project_id, SessionMode.READ_WRITE)
    try:
        instance = Instance.create(
            project_id=project_id,
            instance_id=system.g.idgen.new_instance_id(project_id),
            material_id="series/episode-3.mp4",
            presence=InstancePresence.PRESENT,
        )
        system.instance_repo.add(session, instance)
        leaf = LearningObjectLeaf(
            source="MANUAL",
            project_id=project_id,
            node_id=system.g.idgen.new_learning_object_node_id(project_id),
            relative_path=instance.material_id,
            parent_id=None,
            instance_id=instance.instance_id,
            title="Episode 3 video",
        )
        system.learning_object_repo.add(session, leaf)
        recall_point = RecallPoint(
            project_id=project_id,
            recall_point_id=system.g.idgen.new_recall_point_id(project_id),
            created_at=now_utc_ms(),
            question=rich_text("What changed?"),
            answer=rich_text("Episode three changed the stakes."),
            anchor=Anchor(instance_id=instance.instance_id, position="t=3000"),
        )
        system.recall_point_repo.add(session, recall_point)
        range_snapshot = RangeSnapshot(
            project_id=project_id,
            range_id=system.g.idgen.new_range_id(project_id),
            recall_point_ids=(recall_point.recall_point_id,),
        )
        system.range_repo.add(session, range_snapshot)
        learning_task = LearningTask(
            project_id=project_id,
            learning_task_id=system.g.idgen.new_learning_task_id(project_id),
            recall_point_ids=(recall_point.recall_point_id,),
            title="Episode 3 task",
        )
        system.learning_task_repo.add(session, learning_task)
        task_node = LearningTaskLeaf(
            project_id=project_id,
            node_id=system.g.idgen.new_learning_task_node_id(project_id),
            parent_id=None,
            bound_learning_task_id=learning_task.learning_task_id,
            title="Episode 3 node",
        )
        system.learning_task_node_repo.add(session, task_node)
        review_chain = ReviewChain(
            project_id=project_id,
            review_chain_id=system.g.idgen.new_review_chain_id(project_id),
            queue=tuple(),
            head_index=0,
            state=ReviewChainState.IN_PROGRESS,
        )
        system.review_chain_repo.add(session, review_chain)
        review_task = ReviewTask(
            project_id=project_id,
            review_task_id=system.g.idgen.new_review_task_id(project_id),
            input_range_id=range_snapshot.range_id,
            created_at=now_utc_ms(),
            state=ReviewTaskState.PENDING,
        )
        system.review_task_repo.add(session, review_task)
        convergence = Convergence(
            project_id=project_id,
            convergence_id=system.g.idgen.new_convergence_id(project_id),
            seed_range_id=range_snapshot.range_id,
            rule_id=ConvergenceRuleId("conv_rule_demo"),
            review_task_ids=(review_task.review_task_id,),
            state=ConvergenceState.IN_PROGRESS,
        )
        system.convergence_repo.add(session, convergence)
        asr_artifact = AsrArtifact(
            project_id=project_id,
            asr_artifact_id=system.g.idgen.new_asr_artifact_id(project_id),
            created_at=now_utc_ms(),
            provider=AsrProvider.WHISPER,
            producer_runtime_kind=ClientRuntimeKind.DESKTOP_NATIVE,
            recall_point_id=recall_point.recall_point_id,
            source_instance_id=instance.instance_id,
            center_ms=3000,
            pre_ms=1500,
            post_ms=2000,
            segments=(AsrSegment(start_ms=2500, end_ms=3200, text="Episode three changed the stakes."),),
        )
        system.asr_artifact_repo.add(session, asr_artifact)
        system.entry_repo.add(
            session,
            EntryRegistration(
                project_id=project_id,
                entry_node=task_node.node_id,
                target_layer_index=0,
                review_chain_id=review_chain.review_chain_id,
                registration_seq=1,
            ),
        )
        aggregation_event = AggregationEvent(
            project_id=project_id,
            event_id=system.g.idgen.new_aggregation_event_id(project_id),
            created_at=now_utc_ms(),
            layer_index=0,
            parent_node_id=task_node.node_id,
            child_node_ids=(task_node.node_id,),
            reason=AggregationEventReason.MANUAL_DRAIN,
            title="Episode 3 aggregation",
        )
        system.event_repo.append(session, aggregation_event)
        system.commit(session)
    finally:
        if session.state == "OPEN":
            system.rollback(session)

    project_store = system.g.projects[str(project_id)]
    project_store.project_config = None
    project_store.project_storage_config = None
    project_store.audit_log_events.clear()
    project_store.learning_object_nodes.clear()
    project_store.recall_points.clear()
    project_store.asr_artifacts.clear()
    project_store.learning_tasks.clear()
    project_store.learning_task_nodes.clear()
    project_store.range_snapshots.clear()
    project_store.review_tasks.clear()
    project_store.convergences.clear()
    project_store.review_chains.clear()
    project_store.review_task_queue = None
    project_store.layers.clear()
    project_store.layers_by_index.clear()
    project_store.entry_regs.clear()
    project_store.aggregation_queues.clear()
    project_store.aggregation_events.clear()
    api._startup_fs_sync_done.add(id_canonical_text(project_id))

    project_config = api.get_project_config(project_id)
    storage_config = api.get_project_storage_config(project_id)
    audit_events = api.list_audit_log_events(project_id)
    fetched_task_node = api.get_learning_task_node(project_id, task_node.node_id)
    fetched_task = api.get_learning_task(project_id, learning_task.learning_task_id)
    task_entry_reg = api.get_learning_task_entry_registration(project_id, learning_task.learning_task_id)
    task_node_entry_reg = api.get_learning_task_node_entry_registration(project_id, task_node.node_id)
    task_nodes = api.list_learning_task_nodes(project_id)
    task_recall_points = api.list_recall_points_by_learning_task_node(project_id, task_node.node_id)
    queue_head, queue_ids = api.get_queue(project_id)
    fetched_asr = api.get_asr_artifact(project_id, asr_artifact.asr_artifact_id)
    object_asr = api.export_asr_by_learning_object_node(project_id, leaf.node_id)
    task_asr = api.export_asr_by_learning_task_node(project_id, task_node.node_id)
    fetched_review_task = api.get_review_task(project_id, review_task.review_task_id)
    fetched_convergence = api.get_convergence(project_id, convergence.convergence_id)
    fetched_review_chain = api.get_review_chain(project_id, review_chain.review_chain_id)
    fetched_range_snapshot = api.get_range_snapshot(project_id, range_snapshot.range_id)
    validation = api.validate_recall_point_ids_resolvable(project_id, range_snapshot.range_id)
    layers = api.list_layers(project_id)
    entry_reg = api.get_review_chain_entry_registration(project_id, review_chain.review_chain_id)
    agg_queue_ids = api.get_aggregation_queue_current(project_id, 0)
    agg_events = api.list_aggregation_events(project_id)

    assert str(project_config.project_id) == str(project_id)
    assert storage_config.project_root.as_posix() == project_root.as_posix()
    assert [event.kind.value for event in audit_events] == ["PROJECT_CREATED"]
    assert str(fetched_task_node.node_id) == str(task_node.node_id)
    assert str(fetched_task.learning_task_id) == str(learning_task.learning_task_id)
    assert str(task_entry_reg.entry_node) == str(task_node.node_id)
    assert str(task_node_entry_reg.entry_node) == str(task_node.node_id)
    assert [str(node.node_id) for node in task_nodes] == [str(task_node.node_id)]
    assert [str(item.recall_point_id) for item in task_recall_points] == [str(recall_point.recall_point_id)]
    assert queue_head is None
    assert queue_ids == tuple()
    assert str(fetched_asr.asr_artifact_id) == str(asr_artifact.asr_artifact_id)
    assert [str(item.asr_artifact_id) for item in object_asr] == [str(asr_artifact.asr_artifact_id)]
    assert [str(item.asr_artifact_id) for item in task_asr] == [str(asr_artifact.asr_artifact_id)]
    assert str(fetched_review_task.review_task_id) == str(review_task.review_task_id)
    assert str(fetched_convergence.convergence_id) == str(convergence.convergence_id)
    assert str(fetched_review_chain.review_chain_id) == str(review_chain.review_chain_id)
    assert str(fetched_range_snapshot.range_id) == str(range_snapshot.range_id)
    assert validation.code.value == "OK"
    assert [layer.layer_index for layer in layers] == [0]
    assert str(entry_reg.entry_node) == str(task_node.node_id)
    assert agg_queue_ids == tuple()
    assert [str(event.event_id) for event in agg_events] == [str(aggregation_event.event_id)]


def test_membership_payout_binding_attempt_replaces_active_identity(tmp_path: Path) -> None:
    store = MembershipCommissionStore(tmp_path / "membership.sqlite3")

    first = store.create_payout_binding_attempt(
        "user_inviter",
        channel="manual_test",
        state="state-1",
        expires_at="2026-05-05T00:10:00+00:00",
    )
    identity = store.complete_payout_binding_attempt(
        "user_inviter",
        binding_attempt_id=first.binding_attempt_id,
        authorization_code="manual_openid_001",
        state="state-1",
        openid="openid_inviter_001",
        appid="wx-test-app",
        completed_at="2026-05-05T00:01:00+00:00",
    )

    assert identity.masked_openid == "openid_***"
    assert store.get_active_payout_identity("user_inviter").identity_id == identity.identity_id

    second = store.create_payout_binding_attempt(
        "user_inviter",
        channel="manual_test",
        state="state-2",
        expires_at="2026-05-05T00:20:00+00:00",
    )
    replacement = store.complete_payout_binding_attempt(
        "user_inviter",
        binding_attempt_id=second.binding_attempt_id,
        authorization_code="manual_openid_002",
        state="state-2",
        openid="openid_inviter_002",
        appid="wx-test-app",
        completed_at="2026-05-05T00:11:00+00:00",
    )

    identities = store.list_admin_payout_identities(status="all")
    assert [item.status for item in identities] == ["active", "replaced"]
    assert store.get_active_payout_identity("user_inviter").identity_id == replacement.identity_id


def test_membership_desktop_qr_payout_binding_requires_mobile_confirmation(tmp_path: Path) -> None:
    store = MembershipCommissionStore(tmp_path / "membership.sqlite3")

    attempt = store.create_payout_binding_attempt(
        "user_inviter",
        channel="desktop_qr_official_account_h5",
        state="state-qr",
        expires_at="2026-05-05T00:10:00+00:00",
        desktop_return_url="https://learningpyramid.test/membership",
        mobile_binding_url="https://learningpyramid.test/membership/wechat-payout-bind?attempt=wpbind&state=state-qr",
    )

    assert attempt.status == "created"
    assert attempt.desktop_return_url == "https://learningpyramid.test/membership"
    assert "wechat-payout-bind" in attempt.mobile_binding_url
    assert attempt.scanned_at is None
    assert attempt.confirmed_at is None

    scanned = store.mark_payout_binding_attempt_scanned(
        attempt.binding_attempt_id,
        state="state-qr",
        scanned_at="2026-05-05T00:01:00+00:00",
    )
    assert scanned.status == "scanned"
    assert scanned.scanned_at == "2026-05-05T00:01:00+00:00"
    assert store.get_active_payout_identity("user_inviter") is None

    with pytest.raises(PreconditionFailure, match="confirmed account does not match"):
        store.complete_payout_binding_attempt(
            "user_inviter",
            binding_attempt_id=attempt.binding_attempt_id,
            authorization_code="manual_openid_001",
            state="state-qr",
            openid="openid_inviter_001",
            appid="wx-test-app",
            confirmed_learning_pyramid_user_id="other_user",
            completed_at="2026-05-05T00:02:00+00:00",
        )

    identity = store.complete_payout_binding_attempt(
        "user_inviter",
        binding_attempt_id=attempt.binding_attempt_id,
        authorization_code="manual_openid_001",
        state="state-qr",
        openid="openid_inviter_001",
        appid="wx-test-app",
        confirmed_learning_pyramid_user_id="user_inviter",
        completed_at="2026-05-05T00:02:00+00:00",
    )

    assert identity.identity_id.startswith("wpid_")
    completed = store.get_payout_binding_attempt(attempt.binding_attempt_id)
    assert completed is not None
    assert completed.status == "bound"
    assert completed.confirmed_at == "2026-05-05T00:02:00+00:00"

    with pytest.raises(PreconditionFailure, match="already been consumed"):
        store.mark_payout_binding_attempt_scanned(
            attempt.binding_attempt_id,
            state="state-qr",
            scanned_at="2026-05-05T00:03:00+00:00",
        )


def test_membership_desktop_qr_payout_binding_expires_without_identity(tmp_path: Path) -> None:
    store = MembershipCommissionStore(tmp_path / "membership.sqlite3")
    attempt = store.create_payout_binding_attempt(
        "user_inviter",
        channel="desktop_qr_official_account_h5",
        state="state-expired",
        expires_at="2026-05-05T00:10:00+00:00",
        desktop_return_url="https://learningpyramid.test/membership",
        mobile_binding_url="https://learningpyramid.test/membership/wechat-payout-bind?attempt=wpbind&state=state-expired",
    )

    with pytest.raises(PreconditionFailure, match="expired"):
        store.mark_payout_binding_attempt_scanned(
            attempt.binding_attempt_id,
            state="state-expired",
            scanned_at="2026-05-05T00:11:00+00:00",
        )

    expired = store.get_payout_binding_attempt(attempt.binding_attempt_id)
    assert expired is not None
    assert expired.status == "expired"
    assert store.get_active_payout_identity("user_inviter") is None


def test_membership_automatic_settlement_records_run_metadata(tmp_path: Path) -> None:
    store = MembershipCommissionStore(tmp_path / "membership.sqlite3")
    paid_at = datetime(2026, 5, 4, 0, 0, tzinfo=timezone.utc)
    commission = store.create_pending_commission(
        inviter_user_id="user_inviter",
        invitee_user_id="user_invitee",
        source_order_id="order_settle_001",
        source_payment_amount_cent=2000,
        paid_at=paid_at.isoformat(),
    )
    assert commission is not None

    result = store.settle_due_commissions(now=paid_at + timedelta(hours=24, seconds=1), limit=10)

    assert result.settled_count == 1
    assert result.canceled_count == 0
    assert result.skipped_count == 0
    assert result.error_count == 0
    assert result.run_id.startswith("run_")

    updated = store.get_commission_for_order("order_settle_001")
    assert updated is not None
    assert updated.status == "settled"
    assert updated.settlement_mode == "automatic"
    assert updated.settlement_run_id == result.run_id

    again = store.settle_due_commissions(now=paid_at + timedelta(hours=24, seconds=2), limit=10)
    assert again.settled_count == 0
    assert again.skipped_count == 0


def test_membership_commission_refund_window_can_be_shortened_for_testing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("PLM_MEMBERSHIP_COMMISSION_REFUND_WINDOW_MINUTES", "1")
    store = MembershipCommissionStore(tmp_path / "membership.sqlite3")
    paid_at = datetime(2026, 5, 4, 0, 0, tzinfo=timezone.utc)

    commission = store.create_pending_commission(
        inviter_user_id="user_inviter",
        invitee_user_id="user_invitee",
        source_order_id="order_short_refund_window_001",
        source_payment_amount_cent=2000,
        paid_at=paid_at.isoformat(),
    )

    assert commission is not None
    assert commission.refund_window_ends_at == (paid_at + timedelta(minutes=1)).isoformat()
    early = store.settle_due_commissions(now=paid_at + timedelta(seconds=59), limit=10)
    assert early.settled_count == 0
    due = store.settle_due_commissions(now=paid_at + timedelta(minutes=1, seconds=1), limit=10)
    assert due.settled_count == 1


def test_membership_withdrawal_reserves_balance_and_applies_provider_result_once(tmp_path: Path) -> None:
    store = MembershipCommissionStore(tmp_path / "membership.sqlite3")
    paid_at = datetime(2026, 5, 4, 0, 0, tzinfo=timezone.utc)
    store.create_pending_commission(
        inviter_user_id="user_inviter",
        invitee_user_id="user_invitee",
        source_order_id="order_withdraw_001",
        source_payment_amount_cent=2000,
        paid_at=paid_at.isoformat(),
    )
    store.settle_due_commissions(now=paid_at + timedelta(hours=24, seconds=1), limit=10)
    attempt = store.create_payout_binding_attempt(
        "user_inviter",
        channel="manual_test",
        state="state-withdraw",
        expires_at="2026-05-05T00:10:00+00:00",
    )
    identity = store.complete_payout_binding_attempt(
        "user_inviter",
        binding_attempt_id=attempt.binding_attempt_id,
        authorization_code="manual_openid_001",
        state="state-withdraw",
        openid="openid_inviter_001",
        appid="wx-test-app",
        completed_at="2026-05-05T00:01:00+00:00",
    )

    withdrawal = store.create_withdrawal_request("user_inviter", amount_cent=500, identity_id=identity.identity_id)

    assert withdrawal.status == "created"
    assert withdrawal.out_bill_no.startswith("LPWD")
    assert store.get_user_account("user_inviter").reserved_cent == 500
    assert store.get_user_account("user_inviter").withdrawable_cent == 0

    awaiting = store.mark_withdrawal_awaiting_confirmation(
        withdrawal.withdrawal_id,
        transfer_bill_no="transfer_bill_001",
        provider_state="WAIT_USER_CONFIRM",
        package_info="package-info",
        raw_payload_json='{"state":"WAIT_USER_CONFIRM"}',
    )
    assert awaiting.status == WITHDRAWAL_STATUS_AWAITING_CONFIRMATION

    succeeded = store.apply_withdrawal_provider_result(
        out_bill_no=withdrawal.out_bill_no,
        provider_state="SUCCESS",
        mapped_status=WITHDRAWAL_STATUS_SUCCEEDED,
        transfer_bill_no="transfer_bill_001",
        amount_cent=500,
        appid="wx-test-app",
        raw_payload_json='{"state":"SUCCESS"}',
        provider_event_id="notify_001",
        event_type="notify",
    )
    repeated = store.apply_withdrawal_provider_result(
        out_bill_no=withdrawal.out_bill_no,
        provider_state="SUCCESS",
        mapped_status=WITHDRAWAL_STATUS_SUCCEEDED,
        transfer_bill_no="transfer_bill_001",
        amount_cent=500,
        appid="wx-test-app",
        raw_payload_json='{"state":"SUCCESS"}',
        provider_event_id="notify_001",
        event_type="notify",
    )

    assert succeeded.status == WITHDRAWAL_STATUS_SUCCEEDED
    assert repeated.status == WITHDRAWAL_STATUS_SUCCEEDED
    assert store.get_user_account("user_inviter").reserved_cent == 0
    assert store.get_user_account("user_inviter").paid_out_cent == 500

    events = store.list_payout_provider_events(withdrawal_id=withdrawal.withdrawal_id)
    assert len(events) == 2
    notify_events = [event for event in events if event.event_type == "notify"]
    assert len(notify_events) == 1
    assert notify_events[0].provider_event_id == "notify_001"


def test_membership_withdrawal_failure_returns_reserved_balance(tmp_path: Path) -> None:
    store = MembershipCommissionStore(tmp_path / "membership.sqlite3")
    paid_at = datetime(2026, 5, 4, 0, 0, tzinfo=timezone.utc)
    store.create_pending_commission(
        inviter_user_id="user_inviter",
        invitee_user_id="user_invitee",
        source_order_id="order_withdraw_failed_001",
        source_payment_amount_cent=2000,
        paid_at=paid_at.isoformat(),
    )
    store.settle_due_commissions(now=paid_at + timedelta(hours=24, seconds=1), limit=10)
    attempt = store.create_payout_binding_attempt(
        "user_inviter",
        channel="manual_test",
        state="state-failed",
        expires_at="2026-05-05T00:10:00+00:00",
    )
    identity = store.complete_payout_binding_attempt(
        "user_inviter",
        binding_attempt_id=attempt.binding_attempt_id,
        authorization_code="manual_openid_001",
        state="state-failed",
        openid="openid_inviter_001",
        appid="wx-test-app",
        completed_at="2026-05-05T00:01:00+00:00",
    )
    withdrawal = store.create_withdrawal_request("user_inviter", amount_cent=500, identity_id=identity.identity_id)
    store.mark_withdrawal_processing(
        withdrawal.withdrawal_id,
        provider_transfer_no="transfer_bill_002",
        provider_state="PROCESSING",
        raw_payload_json='{"state":"PROCESSING"}',
    )

    failed = store.apply_withdrawal_provider_result(
        out_bill_no=withdrawal.out_bill_no,
        provider_state="FAIL",
        mapped_status=WITHDRAWAL_STATUS_FAILED,
        transfer_bill_no="transfer_bill_002",
        amount_cent=500,
        appid="wx-test-app",
        raw_payload_json='{"state":"FAIL"}',
        provider_event_id="notify_002",
        event_type="notify",
        failure_reason="provider rejected",
    )

    assert failed.status == WITHDRAWAL_STATUS_FAILED
    assert failed.failure_reason == "provider rejected"
    assert store.get_user_account("user_inviter").reserved_cent == 0
    assert store.get_user_account("user_inviter").withdrawable_cent == 500

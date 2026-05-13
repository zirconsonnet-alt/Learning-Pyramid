import json
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from backend.models.errors import PreconditionFailure
from backend.system import local_whisper
from backend.system.app_paths import default_auth_db_path, default_membership_db_path, default_store_db_path
from backend.system.auth_store import (
    DEFAULT_POMODORO_BREAK_MINUTES,
    DEFAULT_POMODORO_COUNT,
    DEFAULT_POMODORO_FOCUS_MINUTES,
    SQLiteAuthStore,
    _AuthStoreImpl,
    _hash_session_token,
    _pomodoro_weekly_schedule_to_json,
    _session_token_lookup_candidates,
    decrypt_secret_value,
)
from backend.system.inmemory_system import InMemorySystem
from backend.system.membership_commission_store import MembershipCommissionStore
from backend.system.membership_marketing_store import MembershipMarketingStore
from backend.system.membership_store import MembershipOrder, MembershipStore
from backend.system.membership_payment_service import (
    MembershipPaymentService,
    _safe_path,
    _local_order_id_from_wechat_out_trade_no,
    current_wechat_native_payment_config,
)
from backend.system.persistence_json import decode_project_payload, decode_snapshot
from backend.system.persistence_store import JsonSnapshotStore, SQLiteSnapshotStore
from backend.system import version as app_version
from tools import launch_plm, stop_plm
from backend.system import hosted_deployment_checks
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64
import hashlib
import os


def _insert_project_snapshot_row(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    snapshot_json: str | None = None,
) -> None:
    columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(project_snapshots)").fetchall()}
    if "snapshot_json" in columns:
        conn.execute(
            """
            INSERT INTO project_snapshots (
                project_id, project_title, project_state, created_at_ms, deleted_at_ms, snapshot_json, updated_at
            ) VALUES (?, 'Project', 'ACTIVE', 0, NULL, ?, '2026-01-01T00:00:00+00:00')
            """,
            (project_id, snapshot_json or "{}"),
        )
        return
    conn.execute(
        """
        INSERT INTO project_snapshots (
            project_id, project_title, project_state, created_at_ms, deleted_at_ms,
            subject_id, scoped_project_id, project_sequence, updated_at
        ) VALUES (
            ?, 'Project', 'ACTIVE', 0, NULL,
            NULL, NULL, 0, '2026-01-01T00:00:00+00:00'
        )
        """,
        (project_id,),
    )


class BackendLegacyCleanupTest(unittest.TestCase):
    def test_current_app_version_has_no_legacy_app_ids(self) -> None:
        self.assertFalse(hasattr(app_version, "LEGACY_APP_IDS"))

    def test_runtime_process_detection_rejects_removed_app_markers(self) -> None:
        for module in (launch_plm, stop_plm):
            with patch.object(module, "_read_process_command_line", return_value="PLM3-server --runtime-token token"):
                self.assertFalse(module._is_expected_runtime_process(1, "token"))
            with patch.object(module, "_read_process_command_line", return_value="plm-server --runtime-token token"):
                self.assertFalse(module._is_expected_runtime_process(1, "token"))

    def test_local_whisper_uses_current_env_name_only(self) -> None:
        requested_keys: list[str] = []

        def getenv(key: str, default: str | None = None) -> str:
            requested_keys.append(key)
            return ""

        local_whisper.find_local_whisper_python.cache_clear()
        try:
            with (
                patch.object(local_whisper.os, "getenv", side_effect=getenv),
                patch.object(local_whisper.importlib.util, "find_spec", return_value=None),
                patch.object(local_whisper, "_python_supports_whisper", return_value=False),
            ):
                self.assertIsNone(local_whisper.find_local_whisper_python())
        finally:
            local_whisper.find_local_whisper_python.cache_clear()

        self.assertIn("WHISPER_PYTHON", requested_keys)
        self.assertNotIn("PLM3_WHISPER_PYTHON", requested_keys)

    def test_runtime_sources_do_not_use_removed_product_markers(self) -> None:
        root = Path(__file__).resolve().parent.parent
        production_paths = (
            root / "backend" / "system" / "api.py",
            root / "backend" / "system" / "local_whisper.py",
            root / "backend" / "system" / "version.py",
            root / "tools" / "build_release_bundle.py",
            root / "tools" / "build_windows_installer.py",
            root / "tools" / "launch_plm.py",
            root / "tools" / "local_whisper_service.py",
            root / "tools" / "stop_plm.py",
        )
        removed_markers = (
            "PLM3",
            "PLM3_WHISPER_PYTHON",
            "plm-server",
            "plm3-whisper-",
            "plm-asr-",
            "plm-asr-upload-",
            "plm-instance-asr-",
            "plm-instance-asr-upload-",
        )
        for path in production_paths:
            text = path.read_text(encoding="utf-8")
            for marker in removed_markers:
                self.assertNotIn(marker, text, str(path))

    def test_runtime_sources_do_not_use_removed_plm_env_namespace(self) -> None:
        root = Path(__file__).resolve().parent.parent
        production_roots = (
            root / "adapter",
            root / "backend",
            root / "tools",
        )
        production_paths = [
            path
            for production_root in production_roots
            for path in production_root.rglob("*.py")
            if "__pycache__" not in path.parts
        ]
        allowed_fragments = (
            "test_backend_legacy_cleanup.py",
        )
        for path in production_paths:
            if any(fragment in str(path) for fragment in allowed_fragments):
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("PLM_", text, str(path))

    def test_runtime_config_files_do_not_use_removed_plm_env_namespace(self) -> None:
        root = Path(__file__).resolve().parent.parent
        config_paths = (
            root / "Caddyfile.selfhost",
            root / "Dockerfile",
            root / "Dockerfile.selfhost",
            root / "docker-compose.postgres.yml",
            root / "docker-compose.selfhost.yml",
            root / "docker-compose.selfhost.postgres.yml",
            root / "docker-compose.selfhost.proxy.yml",
            root / "README.md",
        )
        for path in config_paths:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("PLM_", text, str(path))

    def test_wechat_config_does_not_read_lowercase_appid_env_aliases(self) -> None:
        requested_keys: list[str] = []

        def getenv(key: str, default: str | None = None) -> str:
            requested_keys.append(key)
            return ""

        with patch("backend.system.membership_payment_service.os.getenv", side_effect=getenv):
            current_wechat_native_payment_config()
        with patch("backend.system.hosted_deployment_checks.os.getenv", side_effect=getenv):
            hosted_deployment_checks._wechat_app_id()

        self.assertIn("LEARNINGPYRAMID_WECHAT_PAY_APP_ID", requested_keys)
        self.assertNotIn("appid", requested_keys)
        self.assertNotIn("APPID", requested_keys)

    def test_default_sqlite_database_names_use_current_product_name(self) -> None:
        self.assertEqual(default_store_db_path().name, "learningpyramid_store.sqlite3")
        self.assertEqual(default_auth_db_path().name, "learningpyramid_auth.sqlite3")
        self.assertEqual(default_membership_db_path().name, "learningpyramid_membership.sqlite3")

    def test_secret_decryption_rejects_removed_plm_aad(self) -> None:
        key = b"test-key"
        nonce = b"1" * 12
        aes_key = hashlib.sha256(key).digest()
        old_ciphertext = AESGCM(aes_key).encrypt(nonce, b"secret", b"plm:secret:v1")
        encoded = "aesgcm:v1:" + base64.urlsafe_b64encode(nonce + old_ciphertext).decode("ascii")

        old_value = os.environ.get("LEARNINGPYRAMID_TOKEN_ENCRYPTION_KEY")
        os.environ["LEARNINGPYRAMID_TOKEN_ENCRYPTION_KEY"] = key.decode("ascii")
        try:
            with self.assertRaises(PreconditionFailure):
                decrypt_secret_value(encoded)
        finally:
            if old_value is None:
                os.environ.pop("LEARNINGPYRAMID_TOKEN_ENCRYPTION_KEY", None)
            else:
                os.environ["LEARNINGPYRAMID_TOKEN_ENCRYPTION_KEY"] = old_value

    def test_inmemory_system_requires_persisted_system_id_counters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "store.json"
            snapshot_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "idgenCounters": {},
                        "globalLlmSettings": None,
                        "projects": {
                            "proj_000001": {
                                "project": {
                                    "projectId": "proj_000001",
                                    "title": "Project",
                                    "state": "DELETED",
                                    "createdAtMs": 0,
                                    "deletedAtMs": 1,
                                    "subjectId": None,
                                    "scopedProjectId": None,
                                    "projectSequence": 0,
                                },
                                "auditLogEvents": {},
                                "instances": {},
                                "learningObjectNodes": {},
                                "learningTasks": {},
                                "learningTaskNodes": {},
                                "rangeSnapshots": {},
                                "reviewTasks": {},
                                "convergences": {},
                                "reviewChains": {},
                                "reviewTaskQueue": None,
                                "layers": {},
                                "layersByIndex": {},
                                "entryRegs": {},
                                "aggregationQueues": {},
                                "aggregationEvents": {},
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PreconditionFailure):
                InMemorySystem(persist_store=JsonSnapshotStore(snapshot_path))

    def test_inmemory_system_requires_persisted_project_audit_counters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "store.json"
            snapshot_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "idgenCounters": {"__system__:proj": 1, "__system__:subj": 0},
                        "globalLlmSettings": None,
                        "projects": {
                            "proj_000001": {
                                "project": {
                                    "projectId": "proj_000001",
                                    "title": "Project",
                                    "state": "DELETED",
                                    "createdAtMs": 0,
                                    "deletedAtMs": 1,
                                    "subjectId": None,
                                    "scopedProjectId": None,
                                    "projectSequence": 0,
                                },
                                "auditLogEvents": {
                                    "audit_00000001": {
                                        "projectId": "proj_000001",
                                        "eventId": "audit_00000001",
                                        "occurredAtMs": 0,
                                        "kind": "PROJECT_DELETED",
                                        "apiName": "delete_project",
                                        "result": "OK",
                                        "payload": "{}",
                                    }
                                },
                                "instances": {},
                                "learningObjectNodes": {},
                                "learningTasks": {},
                                "learningTaskNodes": {},
                                "rangeSnapshots": {},
                                "reviewTasks": {},
                                "convergences": {},
                                "reviewChains": {},
                                "reviewTaskQueue": None,
                                "layers": {},
                                "layersByIndex": {},
                                "entryRegs": {},
                                "aggregationQueues": {},
                                "aggregationEvents": {},
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaises(PreconditionFailure):
                InMemorySystem(persist_store=JsonSnapshotStore(snapshot_path))

    def test_sqlite_store_does_not_import_legacy_json_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store_path = root / "store.sqlite3"
            legacy_path = root / ".plm_store.json"
            legacy_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "idgenCounters": {},
                        "projects": {},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            store = SQLiteSnapshotStore(store_path)

            self.assertIsNone(store.load_snapshot())

    def test_project_payload_requires_current_project_storage_config(self) -> None:
        payload = {
            "project": {
                "projectId": "proj_000001",
                "title": "Project",
                "state": "ACTIVE",
                "createdAtMs": 0,
                "deletedAtMs": None,
                "subjectId": None,
                "scopedProjectId": None,
                "projectSequence": 0,
            },
            "projectMaterialSourceBinding": {
                "projectId": "proj_000001",
                "sourceKind": "SERVER_FS",
                "sourceRootLabel": None,
                "updatedAtMs": 0,
            },
            "projectConfig": None,
            "instances": {},
            "learningObjectNodes": {},
            "learningTasks": {},
            "learningTaskNodes": {},
            "rangeSnapshots": {},
            "reviewTasks": {},
            "convergences": {},
            "reviewChains": {},
            "reviewTaskQueue": None,
            "layers": {},
            "layersByIndex": {},
            "entryRegs": {},
            "aggregationQueues": {},
        }

        with self.assertRaises(ValueError):
            decode_project_payload("proj_000001", payload)

    def test_project_payload_rejects_project_scan_config(self) -> None:
        payload = {
            "project": {
                "projectId": "proj_000001",
                "title": "Project",
                "state": "ACTIVE",
                "createdAtMs": 0,
                "deletedAtMs": None,
                "subjectId": None,
                "scopedProjectId": None,
                "projectSequence": 0,
            },
            "projectScanConfig": {
                "projectId": "proj_000001",
                "scanRoot": "/tmp/materials",
                "updatedAtMs": 0,
            },
            "projectMaterialSourceBinding": {
                "projectId": "proj_000001",
                "sourceKind": "SERVER_FS",
                "sourceRootLabel": None,
                "updatedAtMs": 0,
            },
            "projectConfig": None,
            "instances": {},
            "learningObjectNodes": {},
            "learningTasks": {},
            "learningTaskNodes": {},
            "rangeSnapshots": {},
            "reviewTasks": {},
            "convergences": {},
            "reviewChains": {},
            "reviewTaskQueue": None,
            "layers": {},
            "layersByIndex": {},
            "entryRegs": {},
            "aggregationQueues": {},
        }

        with self.assertRaises(ValueError):
            decode_project_payload("proj_000001", payload)

    def test_deleted_project_tombstone_does_not_require_active_project_config(self) -> None:
        payload = {
            "project": {
                "projectId": "proj_000001",
                "title": "Project",
                "state": "DELETED",
                "createdAtMs": 0,
                "deletedAtMs": 1,
                "subjectId": None,
                "scopedProjectId": None,
                "projectSequence": 0,
            },
            "instances": {},
            "learningObjectNodes": {},
            "learningTasks": {},
            "learningTaskNodes": {},
            "rangeSnapshots": {},
            "reviewTasks": {},
            "convergences": {},
            "reviewChains": {},
            "reviewTaskQueue": None,
            "layers": {},
            "layersByIndex": {},
            "entryRegs": {},
            "aggregationQueues": {},
        }

        decoded = decode_project_payload("proj_000001", payload)

        self.assertIsNone(decoded["project_storage_config"])
        self.assertIsNone(decoded["project_material_source_binding"])
        self.assertIsNone(decoded["project_config"])

    def test_sqlite_store_does_not_import_snapshot_state_slot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "store.sqlite3"
            store = SQLiteSnapshotStore(store_path)
            conn = sqlite3.connect(store_path)
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
                    "INSERT INTO snapshot_state (slot, snapshot_json, updated_at) VALUES (1, ?, '2026-01-01T00:00:00+00:00')",
                    (
                        json.dumps(
                            {
                                "schemaVersion": 1,
                                "idgenCounters": {},
                                "projects": {},
                            },
                            ensure_ascii=False,
                        ),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            self.assertIsNone(store.load_snapshot())

    def test_auth_session_lookup_does_not_include_plaintext_session_token(self) -> None:
        token = "plain-session-token"

        self.assertEqual((_hash_session_token(token),), _session_token_lookup_candidates(token))

    def test_pomodoro_weekly_schedule_does_not_inherit_legacy_root_fields(self) -> None:
        settings = _AuthStoreImpl._row_to_user_global_settings(
            {
                "user_id": "user_1",
                "payload_json": json.dumps(
                    {
                        "pomodoro": {
                            "enabled": True,
                            "focusMinutes": 45,
                            "breakMinutes": 15,
                            "pomodoroCount": 2,
                            "weeklySchedule": {"mon": {"enabled": True}},
                        }
                    },
                    ensure_ascii=False,
                ),
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        )

        self.assertEqual(1, len(settings.pomodoro_weekly_schedule))
        plan = settings.pomodoro_weekly_schedule[0]
        self.assertEqual(DEFAULT_POMODORO_FOCUS_MINUTES, plan.focus_minutes)
        self.assertEqual(DEFAULT_POMODORO_BREAK_MINUTES, plan.break_minutes)
        self.assertEqual(DEFAULT_POMODORO_COUNT, plan.pomodoro_count)

    def test_pomodoro_project_refs_use_scoped_project_id(self) -> None:
        settings = _AuthStoreImpl._row_to_user_global_settings(
            {
                "user_id": "user_1",
                "payload_json": json.dumps(
                    {
                        "pomodoro": {
                            "enabled": True,
                            "weeklySchedule": {
                                "mon": {
                                    "plans": [
                                        {
                                            "enabled": True,
                                            "startTime": "09:00",
                                            "focusMinutes": 25,
                                            "breakMinutes": 5,
                                            "pomodoroCount": 1,
                                            "projectRefs": [
                                                {"subjectId": "subj_000001", "scopedProjectId": "proj_000001"}
                                            ],
                                        }
                                    ]
                                }
                            },
                        }
                    },
                    ensure_ascii=False,
                ),
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        )

        self.assertEqual(
            ({"subjectId": "subj_000001", "scopedProjectId": "proj_000001"},),
            settings.pomodoro_weekly_schedule[0].project_refs,
        )
        self.assertEqual(
            [{"subjectId": "subj_000001", "scopedProjectId": "proj_000001"}],
            _pomodoro_weekly_schedule_to_json(settings.pomodoro_weekly_schedule)["mon"]["plans"][0]["projectRefs"],
        )

    def test_pomodoro_project_refs_reject_ambiguous_project_id(self) -> None:
        settings = _AuthStoreImpl._row_to_user_global_settings(
            {
                "user_id": "user_1",
                "payload_json": json.dumps(
                    {
                        "pomodoro": {
                            "enabled": True,
                            "weeklySchedule": {
                                "mon": {
                                    "plans": [
                                        {
                                            "enabled": True,
                                            "startTime": "09:00",
                                            "focusMinutes": 25,
                                            "breakMinutes": 5,
                                            "pomodoroCount": 1,
                                            "projectRefs": [
                                                {"subjectId": "subj_000001", "projectId": "proj_000001"}
                                            ],
                                        }
                                    ]
                                }
                            },
                        }
                    },
                    ensure_ascii=False,
                ),
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        )

        self.assertEqual((None,), settings.pomodoro_weekly_schedule[0].project_refs)

    def test_wechat_order_id_requires_out_trade_no(self) -> None:
        with self.assertRaises(PreconditionFailure):
            _local_order_id_from_wechat_out_trade_no("")

    def test_wechat_transfer_status_requires_out_bill_no_from_payload(self) -> None:
        with self.assertRaises(PreconditionFailure):
            MembershipPaymentService._wechat_transfer_status_from_payload(
                withdrawal_id="wd_1",
                payload={"state": "SUCCESS"},
            )

    def test_commission_store_rejects_legacy_withdrawal_status_check_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "membership.sqlite3"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    """
                    CREATE TABLE commission_withdrawal_requests (
                        withdrawal_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        amount_cent INTEGER NOT NULL,
                        target_type TEXT NOT NULL,
                        wechat_open_id TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL CHECK(status IN ('pending', 'processing', 'succeeded', 'failed', 'canceled')),
                        provider_transfer_no TEXT,
                        failure_reason TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        submitted_at TEXT,
                        completed_at TEXT
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO commission_withdrawal_requests (
                        withdrawal_id, user_id, amount_cent, target_type, wechat_open_id,
                        status, provider_transfer_no, failure_reason, created_at, submitted_at, completed_at
                    ) VALUES (
                        'wd_1', 'user_1', 1500, 'wechat', '', 'pending', NULL, '', '2026-01-01T00:00:00+00:00', NULL, NULL
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

            with self.assertRaises(RuntimeError):
                MembershipCommissionStore(db_path)

    def test_commission_store_rejects_withdrawal_table_missing_current_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "membership.sqlite3"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    """
                    CREATE TABLE commission_withdrawal_requests (
                        withdrawal_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        amount_cent INTEGER NOT NULL,
                        target_type TEXT NOT NULL,
                        wechat_open_id TEXT NOT NULL DEFAULT '',
                        status TEXT NOT NULL,
                        provider_transfer_no TEXT,
                        failure_reason TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        submitted_at TEXT,
                        completed_at TEXT
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

            with self.assertRaises(RuntimeError):
                MembershipCommissionStore(db_path)

    def test_audit_log_event_rejects_removed_legacy_kind(self) -> None:
        payload = {
            "schemaVersion": 1,
            "idgenCounters": {},
            "projects": {
                "proj_000001": {
                    "project": {
                        "projectId": "proj_000001",
                        "title": "Project",
                        "state": "DELETED",
                        "createdAtMs": 0,
                        "deletedAtMs": 1,
                        "subjectId": None,
                        "scopedProjectId": None,
                        "projectSequence": 0,
                    },
                    "auditLogEvents": {
                        "evt_1": {
                            "projectId": "proj_000001",
                            "eventId": "evt_1",
                            "occurredAtMs": 0,
                            "kind": "CREATE_LLM_SESSION",
                            "apiName": "old_api",
                            "result": "OK",
                            "payload": {},
                        }
                    },
                }
            },
        }

        with self.assertRaises(ValueError):
            decode_snapshot(payload)

    def test_sqlite_store_requires_project_config_index_instead_of_snapshot_shell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "store.sqlite3"
            store = SQLiteSnapshotStore(store_path)
            conn = sqlite3.connect(store_path)
            try:
                conn.execute(
                    """
                    INSERT INTO system_state (slot, schema_version, idgen_counters_json, updated_at)
                    VALUES (1, 1, '{}', '2026-01-01T00:00:00+00:00')
                    """
                )
                _insert_project_snapshot_row(
                    conn,
                    project_id="proj_000001",
                    snapshot_json=json.dumps(
                        {
                            "project": {
                                "projectId": "proj_000001",
                                "title": "Project",
                                "state": "ACTIVE",
                                "createdAtMs": 0,
                                "deletedAtMs": None,
                                "subjectId": None,
                                "scopedProjectId": None,
                                "projectSequence": 0,
                            },
                            "projectStorageConfig": {
                                "projectId": "proj_000001",
                                "projectRoot": "/tmp/project",
                                "learningObjectRoot": "learning_objects",
                                "fsSyncPolicy": "STARTUP_SYNC",
                                "updatedAtMs": 0,
                            },
                            "projectConfig": {
                                "projectId": "proj_000001",
                                "projectType": "COURSE",
                                "layerConfigs": {
                                    "0": {
                                        "reviewChainTemplate": [{"kind": "CONVERGENCE"}],
                                        "aggregationKNode": 8,
                                        "aggregationKPoint": 64,
                                    }
                                },
                                "pushConfig": {"strategy": "none", "params": {}},
                                "updatedAtMs": 0,
                            },
                        },
                        ensure_ascii=False,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO project_storage_config_index (
                        project_id, project_root, learning_object_root, fs_sync_policy, updated_at_ms
                    ) VALUES ('proj_000001', '/tmp/project', 'learning_objects', 'STARTUP_SYNC', 0)
                    """
                )
                conn.execute(
                    """
                    INSERT INTO project_material_source_binding_index (
                        project_id, source_kind, source_root_label, updated_at_ms
                    ) VALUES ('proj_000001', 'SERVER_FS', NULL, 0)
                    """
                )
                conn.commit()
            finally:
                conn.close()

            with self.assertRaises(RuntimeError):
                store.load_snapshot()

    def test_sqlite_store_does_not_restore_entities_from_project_snapshot_shell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store_path = Path(tmp) / "store.sqlite3"
            store = SQLiteSnapshotStore(store_path)
            conn = sqlite3.connect(store_path)
            try:
                conn.execute(
                    """
                    INSERT INTO system_state (slot, schema_version, idgen_counters_json, updated_at)
                    VALUES (1, 1, '{}', '2026-01-01T00:00:00+00:00')
                    """
                )
                _insert_project_snapshot_row(conn, project_id="proj_000001")
                conn.execute(
                    """
                    INSERT INTO project_storage_config_index (
                        project_id, project_root, learning_object_root, fs_sync_policy, updated_at_ms
                    ) VALUES ('proj_000001', '/tmp/project', 'learning_objects', 'STARTUP_SYNC', 0)
                    """
                )
                conn.execute(
                    """
                    INSERT INTO project_config_index (project_id, updated_at_ms, config_json)
                    VALUES (
                        'proj_000001',
                        0,
                        '{"projectId":"proj_000001","projectType":"COURSE","layerConfigs":{"0":{"reviewChainTemplate":[{"kind":"CONVERGENCE"}],"aggregationKNode":8,"aggregationKPoint":64}},"pushConfig":{"strategy":"none","params":{}},"updatedAtMs":0}'
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO project_material_source_binding_index (
                        project_id, source_kind, source_root_label, updated_at_ms
                    ) VALUES ('proj_000001', 'SERVER_FS', NULL, 0)
                    """
                )
                columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(project_snapshots)").fetchall()}
                if "snapshot_json" in columns:
                    conn.execute(
                        """
                        UPDATE project_snapshots
                        SET snapshot_json = '{"instances":{"inst_shell":{"projectId":"proj_000001","instanceId":"inst_shell","materialId":"shell.mp4"}}}'
                        WHERE project_id = 'proj_000001'
                        """
                    )
                conn.commit()
            finally:
                conn.close()

            snapshot = store.load_snapshot()

            self.assertEqual({}, snapshot["projects"]["proj_000001"]["instances"])

    def test_auth_store_rejects_missing_current_auth_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "auth.sqlite3"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    """
                    CREATE TABLE users (
                        user_id TEXT PRIMARY KEY,
                        email TEXT NOT NULL UNIQUE,
                        password_hash TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

            with self.assertRaises(RuntimeError):
                SQLiteAuthStore(db_path)

    def test_auth_store_does_not_drop_deprecated_study_group_tables_on_startup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "auth.sqlite3"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute("CREATE TABLE study_groups (group_id TEXT PRIMARY KEY)")
                conn.commit()
            finally:
                conn.close()

            SQLiteAuthStore(db_path)
            conn = sqlite3.connect(db_path)
            try:
                row = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'study_groups'"
                ).fetchone()
            finally:
                conn.close()

            self.assertIsNotNone(row)

    def test_membership_store_rejects_missing_current_order_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "membership.sqlite3"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    """
                    CREATE TABLE membership_orders (
                        order_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        order_type TEXT NOT NULL,
                        pricing_version TEXT NOT NULL,
                        period_days INTEGER NOT NULL,
                        list_amount_cent INTEGER NOT NULL,
                        payable_amount_cent INTEGER NOT NULL,
                        provider TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

            with self.assertRaises(RuntimeError):
                MembershipStore(db_path)

    def test_membership_store_rejects_non_current_entitlement_source_order_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "membership.sqlite3"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    """
                    CREATE TABLE membership_entitlements (
                        entitlement_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        source_order_id TEXT NOT NULL,
                        source_kind TEXT NOT NULL DEFAULT 'order',
                        start_at TEXT NOT NULL,
                        end_at TEXT NOT NULL,
                        granted_days INTEGER NOT NULL,
                        status TEXT NOT NULL,
                        granted_at TEXT NOT NULL,
                        revoked_at TEXT,
                        revoke_reason TEXT NOT NULL DEFAULT ''
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

            with self.assertRaises(RuntimeError):
                MembershipStore(db_path)

    def test_membership_refund_window_uses_current_env_minutes(self) -> None:
        paid_at = "2026-05-11T00:00:00+00:00"
        order = MembershipOrder(
            order_id="order_1",
            user_id="user_1",
            plan_id="monthly",
            plan_name="月会员",
            order_type="first_purchase",
            pricing_version="membership_plans_v2",
            period_days=30,
            list_amount_cent=2000,
            first_order_discount_cent=0,
            coupon_discount_cent=0,
            payable_amount_cent=2000,
            coupon_id=None,
            provider="manual_test",
            provider_trade_no="trade_1",
            status="paid",
            client_ip="",
            client_version="",
            created_at=paid_at,
            paid_at=paid_at,
            closed_at=None,
            refunded_at=None,
            expired_at=None,
            entitlement_id="entitlement_1",
            remark="",
        )

        with tempfile.TemporaryDirectory() as tmp:
            store = MembershipStore(Path(tmp) / "membership.sqlite3")
            with patch.dict(os.environ, {"LEARNINGPYRAMID_MEMBERSHIP_REFUND_WINDOW_MINUTES": "1"}):
                with self.assertRaises(PreconditionFailure):
                    store.ensure_refund_can_start(
                        order,
                        now=datetime.fromisoformat("2026-05-11T00:02:00+00:00"),
                    )

    def test_membership_marketing_store_rejects_missing_current_coupon_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "membership.sqlite3"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    """
                    CREATE TABLE coupons (
                        coupon_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        amount_cent INTEGER NOT NULL,
                        min_spend_cent INTEGER NOT NULL,
                        source TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

            with self.assertRaises(RuntimeError):
                MembershipMarketingStore(db_path)

    def test_membership_marketing_store_rejects_non_current_invite_constraints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "membership.sqlite3"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    """
                    CREATE TABLE invite_bindings (
                        invitee_user_id TEXT PRIMARY KEY,
                        inviter_user_id TEXT NOT NULL,
                        invite_code_snapshot TEXT NOT NULL,
                        status TEXT NOT NULL CHECK (status IN ('bound', 'rewarded')),
                        bound_at TEXT NOT NULL,
                        rewarded_at TEXT,
                        reward_trigger_order_id TEXT,
                        reward_coupon_id TEXT,
                        discount_coupon_id TEXT
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

            with self.assertRaises(RuntimeError):
                MembershipMarketingStore(db_path)

    def test_commission_store_rejects_commission_records_missing_current_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "membership.sqlite3"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    """
                    CREATE TABLE commission_records (
                        commission_id TEXT PRIMARY KEY,
                        inviter_user_id TEXT NOT NULL,
                        invitee_user_id TEXT NOT NULL,
                        source_order_id TEXT NOT NULL UNIQUE,
                        source_payment_amount_cent INTEGER NOT NULL,
                        threshold_amount_cent INTEGER NOT NULL,
                        commission_amount_cent INTEGER NOT NULL,
                        refund_window_ends_at TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        settled_at TEXT,
                        canceled_at TEXT,
                        cancel_reason TEXT NOT NULL DEFAULT ''
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

            with self.assertRaises(RuntimeError):
                MembershipCommissionStore(db_path)

    def test_commission_store_rejects_binding_attempts_missing_current_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "membership.sqlite3"
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    """
                    CREATE TABLE payout_binding_attempts (
                        binding_attempt_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        provider TEXT NOT NULL,
                        channel TEXT NOT NULL,
                        state TEXT NOT NULL,
                        status TEXT NOT NULL,
                        authorization_code_hash TEXT NOT NULL DEFAULT '',
                        resolved_openid TEXT NOT NULL DEFAULT '',
                        identity_id TEXT,
                        failure_reason TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        authorized_at TEXT,
                        completed_at TEXT,
                        expires_at TEXT NOT NULL
                    )
                    """
                )
                conn.commit()
            finally:
                conn.close()

            with self.assertRaises(RuntimeError):
                MembershipCommissionStore(db_path)

    def test_wechat_cert_path_does_not_use_implicit_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "apiclient_key.pem").write_text("pem", encoding="utf-8")

            self.assertIsNone(_safe_path(""))

import json
import hashlib
import os
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from dataclasses import replace
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Optional, Sequence, Tuple
from urllib.parse import urlparse, urlunparse

from backend.models.aggregation_event import AggregationEvent
from backend.models.aggregation_queue import AggregationQueue
from backend.models.asr_artifact import AsrArtifact, AsrSegment
from backend.models.audit_log_event import AuditLogEvent
from backend.models.convergence import Convergence
from backend.models.enums import (
    AggregationCycleState,
    AggregationEventReason,
    AuditEventKind,
    AuditResultCode,
    AsrProvider,
    ClientRuntimeKind,
    ConvergenceState,
    FsSyncPolicy,
    InstancePresence,
    LayerMode,
    MediaAssetKind,
    MaterialSourceKind,
    ProjectState,
    RecallPointState,
    RecallPointReviewResult,
    ReviewChainTemplateItemKind,
    ReviewChainState,
    ReviewTaskState,
    RuntimeCapability,
    SessionMode,
)
from backend.models.errors import DirectoryStructureCorruptedError, ExternalServiceError, NotFound, PreconditionFailure
from backend.models.instance import Instance
from backend.models.layer import Layer
from backend.models.learning_object_node import LearningObjectContainer, LearningObjectLeaf
from backend.models.learning_task import LearningTask
from backend.models.learning_task_node import LearningTaskContainer, LearningTaskLeaf, LearningTaskNode
from backend.models.media_asset import MediaAsset
from backend.models.project import Project
from backend.models.project_config import (
    LayerConfig,
    LocalServiceConfig,
    ProjectConfig,
    ReviewChainTemplate,
    default_project_config,
    default_layer_config,
)
from backend.models.project_material_source_binding import ProjectMaterialSourceBinding
from backend.models.project_storage_config import ProjectStorageConfig
from backend.models.recall_point import Anchor, RecallPoint
from backend.models.recall_point_review_record import RecallPointReviewRecord
from backend.models.rich_content import RichContent, validate_rich_content_write_time
from backend.models.review_chain import ReviewChain, ReviewChainItem, ReviewChainItemKind
from backend.models.review_task import ReviewTask
from backend.models.review_task_queue import ReviewTaskQueue
from backend.models.types import (
    AsrArtifactId,
    ConvergenceId,
    ConvergenceRuleId,
    InstanceId,
    LearningObjectNodeId,
    LearningTaskId,
    LearningTaskNodeId,
    MediaAssetId,
    ProjectId,
    RangeId,
    RecallPointId,
    ReviewChainId,
    ReviewTaskId,
    id_canonical_text,
    id_from_rel_path,
    normalize_material_id_to_purepath,
    node_id_from_rel_path,
    now_utc_ms,
)
from backend.models.validation import ValidationResult
from backend.models.entry_registration import EntryRegistration
from backend.protocols.interfaces import LearningItem
from backend.protocols.learning_task_submit import learning_task_submit
from backend.protocols.review_submit_binary import review_submit_binary
from backend.repositories.persistence_interfaces import SystemStateRecord
from backend.system.local_whisper import ensure_local_whisper_runtime, is_builtin_whisper_base_url
from backend.system.material_paths import resolve_material_file_path
from backend.system.persistence_json import SCHEMA_VERSION, encode_project_payload_record, encode_project_shell_payload
from backend.system.persistence_store import SqlStore
from backend.system.project_paths import allocate_project_root
from backend.system.runtime_features import current_native_runtime_config, current_runtime_features
from backend.system.inmemory_system import (
    DEFAULT_AGGREGATION_K_NODE,
    DEFAULT_AGGREGATION_K_POINT,
    InMemorySystem,
    MutationSession,
    SessionState,
)


class TickAttemptResult(str, Enum):
    PRODUCED = "PRODUCED"
    EMPTY = "EMPTY"
    GATE_BLOCKED = "GATE_BLOCKED"

MAX_ASR_WINDOW_MS: int = 5 * 60 * 1000

class SystemAPI:
    """
    4.5 对外入口白名单（最小可运行内存实现）
    """

    def __init__(self, sys: InMemorySystem) -> None:
        self.sys = sys
        self.idgen = sys.g.idgen
        self._startup_fs_sync_done: set[str] = set()

    def _sql_store(self) -> SqlStore | None:
        store = getattr(self.sys, "_persist_store", None)
        return store if isinstance(store, SqlStore) else None

    def _reload_sql_state(self) -> None:
        self.sys.g.projects.clear()
        self.sys._load_persisted()
        self.sys._ensure_system_project_id_seq()

    @staticmethod
    def _sql_updated_at_text() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    @staticmethod
    def _image_extension_for_upload(mime_type: str, filename: str | None) -> str:
        mime = str(mime_type or "").strip().lower()
        mapping = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/webp": ".webp",
            "image/gif": ".gif",
            "image/bmp": ".bmp",
        }
        if mime in mapping:
            return mapping[mime]
        if filename:
            ext = Path(str(filename)).suffix.lower().strip()
            if ext in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
                return ".jpg" if ext == ".jpeg" else ext
        raise PreconditionFailure(f"Unsupported image mime type: {mime_type}")

    def _create_project_sql_direct(
        self,
        sql_store: SqlStore,
        title: str,
        project_root: str | None,
        *,
        initial_source_kind: MaterialSourceKind,
    ) -> ProjectId:
        if not isinstance(initial_source_kind, MaterialSourceKind):
            raise PreconditionFailure("create_project.initial_source_kind must be MaterialSourceKind")
        pid = self.idgen.new_project_id()
        resolved_project_root = project_root
        if resolved_project_root is None:
            auto_project_root, _ = allocate_project_root(title)
            resolved_project_root = auto_project_root.as_posix()

        project = Project(
            project_id=pid,
            title=title,
            state=ProjectState.ACTIVE,
            created_at=now_utc_ms(),
            deleted_at=None,
        )
        project.validate_write_time()

        review_task_queue = ReviewTaskQueue(
            project_id=pid,
            queue_id="GLOBAL_QUEUE",
            review_task_ids=tuple(),
            head_index=0,
        )
        review_task_queue.validate_local_invariants()

        storage_config = ProjectStorageConfig.create(
            pid,
            resolved_project_root,
            learning_object_root="learning_objects",
            fs_sync_policy=FsSyncPolicy.STARTUP_SYNC,
            updated_at=now_utc_ms(),
        )
        material_source_binding = ProjectMaterialSourceBinding.create(
            pid,
            source_kind=initial_source_kind,
            updated_at=now_utc_ms(),
        )
        project_config = default_project_config(project_id=pid, updated_at=now_utc_ms())

        layer0 = Layer(
            project_id=pid,
            layer_id=self.idgen.new_layer_id(pid),
            layer_index=0,
            layer_mode=LayerMode.AUTO_TICK_ON_ENTRY,
            orchestrator_managed_review_chain_ids=tuple(),
            aggregation_k_node=DEFAULT_AGGREGATION_K_NODE,
            aggregation_k_point=DEFAULT_AGGREGATION_K_POINT,
            aggregation_cycle_state=AggregationCycleState.DONE,
        )
        layer0.validate_local_invariants()
        aggregation_queue = AggregationQueue(
            project_id=pid,
            layer_index=0,
            node_ids=tuple(),
            head_index=0,
        )
        aggregation_queue.validate_local_invariants()

        audit_event = AuditLogEvent(
            project_id=pid,
            event_id=self.idgen.new_audit_event_id(pid),
            occurred_at=now_utc_ms(),
            kind=AuditEventKind.PROJECT_CREATED,
            api_name="create_project",
            result=AuditResultCode.OK,
            payload=json.dumps({"projectId": str(pid)}, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        )
        audit_event.validate_write_time()

        updated_at = self._sql_updated_at_text()
        with sql_store.begin_unit_of_work(project_id=str(pid)) as uow:
            uow.system_state.upsert(
                uow.session,
                SystemStateRecord(
                    schema_version=SCHEMA_VERSION,
                    idgen_counters=dict(self.idgen._counters),
                    updated_at=updated_at,
                ),
            )
            uow.project_lifecycle.create_bootstrap(
                uow.session,
                project=project,
                project_snapshot=encode_project_shell_payload(
                    project=project,
                    project_storage_config=storage_config,
                    project_material_source_binding=material_source_binding,
                    project_config=project_config,
                ),
                project_storage_config=storage_config,
                project_config=project_config,
                review_task_queue=review_task_queue,
                layers=(layer0,),
                aggregation_queues=(aggregation_queue,),
                audit_events=(audit_event,),
                updated_at=updated_at,
            )

        self._reload_sql_state()
        return pid

    def _delete_project_sql_direct(self, sql_store: SqlStore, project_id: ProjectId) -> None:
        project_store = self.sys.g.projects.get(str(project_id))
        if project_store is None or project_store.project is None:
            raise NotFound(project_id)
        if project_store.project.state != ProjectState.ACTIVE:
            raise PreconditionFailure("Project must be ACTIVE to delete")

        deleted_at = now_utc_ms()
        deleted_project = Project(
            project_id=project_store.project.project_id,
            title=project_store.project.title,
            state=ProjectState.DELETED,
            created_at=project_store.project.created_at,
            deleted_at=deleted_at,
        )
        deleted_project.validate_write_time()

        audit_event = AuditLogEvent(
            project_id=project_id,
            event_id=self.idgen.new_audit_event_id(project_id),
            occurred_at=deleted_at,
            kind=AuditEventKind.PROJECT_DELETED,
            api_name="delete_project",
            result=AuditResultCode.OK,
            payload=json.dumps({"projectId": str(project_id)}, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        )
        audit_event.validate_write_time()

        updated_at = self._sql_updated_at_text()
        with sql_store.begin_unit_of_work(project_id=str(project_id)) as uow:
            uow.system_state.upsert(
                uow.session,
                SystemStateRecord(
                    schema_version=SCHEMA_VERSION,
                    idgen_counters=dict(self.idgen._counters),
                    updated_at=updated_at,
                ),
            )
            uow.project_lifecycle.replace_with_deleted_tombstone(
                uow.session,
                project=deleted_project,
                project_snapshot={"project": encode_project_payload_record(deleted_project)},
                audit_events=(audit_event,),
                updated_at=updated_at,
            )

        self._startup_fs_sync_done.discard(id_canonical_text(project_id))
        self._reload_sql_state()

    def _append_audit_event(
        self,
        s: MutationSession,
        *,
        kind: AuditEventKind,
        api_name: str,
        payload: dict[str, object],
    ) -> None:
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        ev = AuditLogEvent(
            project_id=s.project_id,
            event_id=self.idgen.new_audit_event_id(s.project_id),
            occurred_at=now_utc_ms(),
            kind=kind,
            api_name=api_name,
            result=AuditResultCode.OK,
            payload=text,
        )
        ev.validate_write_time()
        self.sys.audit_log_repo.append(s, ev)

    @staticmethod
    def _require_runtime_capability(
        s: MutationSession,
        *,
        capability: RuntimeCapability,
        api_name: str,
    ) -> None:
        if s.runtime_kind != ClientRuntimeKind.DESKTOP_NATIVE:
            raise PreconditionFailure(f"{api_name} is only available for DESKTOP_NATIVE runtime")
        if capability not in s.runtime_capabilities:
            raise PreconditionFailure(f"{api_name} requires runtime capability {capability.value}")

    @staticmethod
    def _resolve_local_service_url(cfg: LocalServiceConfig, *, default_path: str) -> str:
        base = str(cfg.base_url).strip()
        u = urlparse(base)
        if not u.scheme or not u.netloc:
            raise PreconditionFailure("LocalServiceConfig.base_url must be an absolute http(s) URL")
        if u.path and u.path not in ("", "/"):
            return base
        if not default_path.startswith("/"):
            raise ValueError("default_path must start with '/'")
        return urlunparse((u.scheme, u.netloc, default_path, "", "", ""))

    @staticmethod
    def _stable_json_dumps(payload: object) -> bytes:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")

    @classmethod
    def _http_post_json(
        cls,
        *,
        url: str,
        payload: dict[str, object],
        api_key: Optional[str],
        timeout_sec: float,
    ) -> dict[str, Any]:
        body = cls._stable_json_dumps(payload)
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        if api_key is not None and str(api_key).strip():
            req.add_header("Authorization", f"Bearer {api_key}")

        try:
            with urllib.request.urlopen(req, timeout=float(timeout_sec)) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                body = e.read().decode("utf-8", errors="replace").strip()
                if body:
                    detail = f" body={body[:400]}"
            except Exception:
                detail = ""
            raise ExternalServiceError(f"External service unavailable: HTTP {e.code} {e.reason}{detail}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise ExternalServiceError(f"External service unavailable: {e}") from e
        try:
            decoded: Any = json.loads(raw.decode("utf-8"))
        except Exception as e:
            raise ExternalServiceError(f"External service returned invalid JSON: {e}") from e
        if not isinstance(decoded, dict):
            raise ExternalServiceError("External service returned non-object JSON")
        return decoded

    def _ensure_startup_fs_sync_done(self, project_id: ProjectId) -> None:
        """
        0b.1.5b: When fs_sync_policy == STARTUP_SYNC, perform one filesystem sync before exposing
        any READ_WRITE write entrypoint for this project.
        """
        pid_k = id_canonical_text(project_id)
        if pid_k in self._startup_fs_sync_done:
            return
        if not current_runtime_features().server_media_stream_enabled:
            self._startup_fs_sync_done.add(pid_k)
            return

        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            cfg = self.sys.project_storage_config_repo.get(s)
            binding = self.sys.project_material_source_binding_repo.get(s)
        finally:
            self.sys.rollback(s)

        if binding.source_kind in {MaterialSourceKind.BROWSER_LOCAL, MaterialSourceKind.MANUAL}:
            self._startup_fs_sync_done.add(pid_k)
            return

        if cfg.fs_sync_policy != FsSyncPolicy.STARTUP_SYNC:
            self._startup_fs_sync_done.add(pid_k)
            return

        self._run_sync_learning_objects_from_fs(project_id)
        self._startup_fs_sync_done.add(pid_k)

    def _run_sync_learning_objects_from_fs(self, project_id: ProjectId) -> dict[str, object]:
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            cfg = self.sys.project_storage_config_repo.get(s)
            binding = self.sys.project_material_source_binding_repo.get(s)
            if binding.source_kind not in {MaterialSourceKind.SERVER_FS, MaterialSourceKind.NATIVE_LOCAL}:
                raise PreconditionFailure("sync_learning_objects_from_fs: source_kind must be SERVER_FS or NATIVE_LOCAL")
            if cfg.fs_sync_policy == FsSyncPolicy.DISABLED:
                raise PreconditionFailure("sync_learning_objects_from_fs: fs_sync_policy is DISABLED")

            abs_project_root = Path(cfg.project_root.as_posix()).resolve()
            abs_root = (abs_project_root / Path(cfg.learning_object_root.as_posix())).resolve()
            try:
                abs_root.relative_to(abs_project_root)
            except Exception:
                raise PreconditionFailure("sync_learning_objects_from_fs: learning_object_root must be under project_root")

            try:
                if not abs_root.exists():
                    raise PreconditionFailure(f"sync_learning_objects_from_fs: abs_root not found: {abs_root}")
                if not abs_root.is_dir():
                    raise PreconditionFailure(f"sync_learning_objects_from_fs: abs_root is not a directory: {abs_root}")
                if abs_root.is_symlink():
                    raise DirectoryStructureCorruptedError(
                        f"UnsupportedFilesystemEntry: symlink not supported: {abs_root}"
                    )
            except PreconditionFailure:
                raise
            except Exception as e:
                raise PreconditionFailure(f"sync_learning_objects_from_fs: abs_root scan failed: {e}")

            # ---------- Phase 1: Scan & validate (no repo writes) ----------
            file_rel_raw: list[PurePosixPath] = []
            dir_rel_set: set[PurePosixPath] = {PurePosixPath(".")}

            def _scan_dir(d_os: Path) -> None:
                """
                Spec 0b.1.5b strong constraints:
                - Ignore entries whose name starts with '.'.
                - Reject symlinks/shortcuts and non-file/non-dir entries.
                - Enforce directory homogeneity (direct children all dirs or all files).
                """
                stack: list[Path] = [d_os]
                while stack:
                    cur = stack.pop()
                    has_dir = False
                    has_file = False
                    dir_names: list[str] = []
                    file_names: list[str] = []
                    try:
                        with os.scandir(cur) as it:
                            for ent in it:
                                name = ent.name
                                if name.startswith("."):
                                    continue
                                # Windows "shortcut" files are regular files; treat as unsupported entry.
                                if name.lower().endswith(".lnk"):
                                    raise DirectoryStructureCorruptedError(
                                        f"UnsupportedFilesystemEntry: shortcut not supported: {Path(ent.path)}"
                                    )
                                if ent.is_symlink():
                                    raise DirectoryStructureCorruptedError(
                                        f"UnsupportedFilesystemEntry: symlink not supported: {Path(ent.path)}"
                                    )
                                if ent.is_dir(follow_symlinks=False):
                                    has_dir = True
                                    dir_names.append(name)
                                    child = Path(ent.path)
                                    rel = PurePosixPath(child.relative_to(abs_root).as_posix())
                                    dir_rel_set.add(rel)
                                    stack.append(child)
                                elif ent.is_file(follow_symlinks=False):
                                    has_file = True
                                    file_names.append(name)
                                    child = Path(ent.path)
                                    rel = PurePosixPath(child.relative_to(abs_root).as_posix())
                                    file_rel_raw.append(rel)
                                else:
                                    raise DirectoryStructureCorruptedError(
                                        f"UnsupportedFilesystemEntry: not a file/dir: {Path(ent.path)}"
                                    )
                    except DirectoryStructureCorruptedError:
                        raise
                    except Exception as e:
                        raise PreconditionFailure(f"sync_learning_objects_from_fs: scan failed: {e}")

                    if has_dir and has_file:
                        dir_names.sort()
                        file_names.sort()
                        raise DirectoryStructureCorruptedError(
                            "DirectoryStructureCorrupted: mixed files/dirs under "
                            f"{cur}; dirs={dir_names[:10]} files={file_names[:10]}"
                        )

            _scan_dir(abs_root)

            file_rel = sorted(set(file_rel_raw), key=lambda p: p.as_posix())
            dir_rel = sorted(dir_rel_set, key=lambda p: p.as_posix())

            cur_instances = self.sys.instance_repo.all(s)
            cur_instances_by_key = {id_canonical_text(i.instance_id): i for i in cur_instances}

            existing_instance_id_by_material: dict[str, InstanceId] = {}
            for inst in sorted(cur_instances, key=lambda x: id_canonical_text(x.instance_id)):
                existing_instance_id_by_material.setdefault(inst.material_id.as_posix(), inst.instance_id)

            used_instance_keys: set[str] = set()
            instance_id_by_file: dict[PurePosixPath, InstanceId] = {}
            for rel in file_rel:
                abs_rel = (abs_root / Path(rel.as_posix())).resolve().as_posix()
                existing_iid = existing_instance_id_by_material.get(rel.as_posix()) or existing_instance_id_by_material.get(abs_rel)
                if existing_iid is not None and id_canonical_text(existing_iid) not in used_instance_keys:
                    iid = existing_iid
                else:
                    iid = id_from_rel_path(rel)
                instance_id_by_file[rel] = iid
                used_instance_keys.add(id_canonical_text(iid))

            leaf_id_by_file: dict[PurePosixPath, LearningObjectNodeId] = {rel: node_id_from_rel_path(rel, "LEAF") for rel in file_rel}
            dir_id_by_dir: dict[PurePosixPath, LearningObjectNodeId] = {rel: node_id_from_rel_path(rel, "DIR") for rel in dir_rel}

            # ---------- Phase 2: Stage writes ----------
            now = now_utc_ms()

            scanned_instance_keys = {id_canonical_text(x) for x in instance_id_by_file.values()}
            instances_to_add: list[Instance] = []
            instances_to_update: list[Instance] = []
            created_instances = 0
            updated_instances = 0
            for rel in file_rel:
                iid = instance_id_by_file[rel]
                inst_key = id_canonical_text(iid)
                existing = cur_instances_by_key.get(inst_key)
                last_seen_at = (
                    existing.last_seen_at
                    if existing is not None
                    and existing.material_id == rel
                    and existing.presence == InstancePresence.PRESENT
                    else now
                )
                desired = Instance.create(
                    project_id,
                    iid,
                    rel,
                    presence=InstancePresence.PRESENT,
                    last_seen_at=last_seen_at,
                )
                if existing is None:
                    instances_to_add.append(desired)
                    created_instances += 1
                elif existing != desired:
                    instances_to_update.append(desired)
                    updated_instances += 1

            marked_missing_instances = 0
            for inst in cur_instances:
                if id_canonical_text(inst.instance_id) in scanned_instance_keys:
                    continue
                if inst.presence == InstancePresence.MISSING:
                    continue
                marked_missing_instances += 1
                desired = Instance.create(
                    project_id,
                    inst.instance_id,
                    inst.material_id,
                    presence=InstancePresence.MISSING,
                    last_seen_at=inst.last_seen_at,
                )
                if inst != desired:
                    instances_to_update.append(desired)
                    updated_instances += 1

            # LearningObjectNode full replacement (filesystem authoritative).
            nodes_out: list[LearningObjectLeaf | LearningObjectContainer] = []

            # Leaves (no FS read in Phase 2 to avoid TOCTOU; derived from Phase 1 scan).
            for rel in file_rel:
                parent_rel = rel.parent
                parent_id = dir_id_by_dir.get(parent_rel)
                if parent_id is None:
                    raise PreconditionFailure("sync_learning_objects_from_fs: missing parent dir node")
                nodes_out.append(
                    LearningObjectLeaf(
                        source="FILESYSTEM",
                        project_id=project_id,
                        node_id=leaf_id_by_file[rel],
                        relative_path=rel,
                        parent_id=parent_id,
                        instance_id=instance_id_by_file[rel],
                        title=rel.name,
                    )
                )

            children_by_dir: dict[PurePosixPath, list[tuple[str, LearningObjectNodeId]]] = {d: [] for d in dir_rel}
            for d in dir_rel:
                if d.as_posix() == ".":
                    continue
                parent = d.parent
                children_by_dir[parent].append((d.as_posix(), dir_id_by_dir[d]))
            for rel in file_rel:
                parent = rel.parent
                children_by_dir[parent].append((rel.as_posix(), leaf_id_by_file[rel]))

            # Containers (derived from Phase 1 scan).
            for rel in dir_rel:
                children = children_by_dir.get(rel, [])
                children.sort(key=lambda x: x[0])
                child_ids = tuple(x[1] for x in children)

                if rel.as_posix() == ".":
                    parent_id = None
                    title = abs_root.name if abs_root.name else abs_root.as_posix()
                else:
                    parent_id = dir_id_by_dir.get(rel.parent)
                    title = rel.name
                    if parent_id is None:
                        raise PreconditionFailure("sync_learning_objects_from_fs: parent dir id missing")

                nodes_out.append(
                    LearningObjectContainer(
                        source="FILESYSTEM",
                        project_id=project_id,
                        node_id=dir_id_by_dir[rel],
                        relative_path=rel,
                        parent_id=parent_id,
                        children=child_ids,
                        title=title,
                    )
                )

            # ---- Writes (staged) ----
            for inst in instances_to_add:
                self.sys.instance_repo.add(s, inst)
            for inst in instances_to_update:
                self.sys.instance_repo.update(s, inst)

            replaced_nodes_count = 0
            cur_nodes = self.sys.learning_object_repo.all(s)
            cur_nodes_by_id = {id_canonical_text(n.node_id): n for n in cur_nodes}
            next_nodes_by_id = {id_canonical_text(n.node_id): n for n in nodes_out}
            if cur_nodes_by_id != next_nodes_by_id:
                self.sys.learning_object_repo.replace_all_from_fs(s, nodes_out)
                replaced_nodes_count = len(nodes_out)

            unchanged = created_instances == 0 and updated_instances == 0 and replaced_nodes_count == 0
            report: dict[str, object] = {
                "unchanged": bool(unchanged),
                "created_instances_count": int(created_instances),
                "marked_missing_count": int(marked_missing_instances),
                "replaced_learning_object_nodes_count": int(replaced_nodes_count),
                "warnings": tuple(),
            }

            if unchanged:
                self.sys.rollback(s)
                return report

            abs_root_hash = hashlib.sha256(str(abs_root).encode("utf-8")).hexdigest()[:16]
            self._append_audit_event(
                s,
                kind=AuditEventKind.SYNC_LEARNING_OBJECTS_FROM_FS,
                api_name="sync_learning_objects_from_fs",
                payload={
                    "absRootHash": abs_root_hash,
                    "filesCount": len(file_rel),
                    "dirsCount": len(dir_rel),
                    "createdInstancesCount": int(created_instances),
                    "markedMissingCount": int(marked_missing_instances),
                    "replacedLearningObjectNodesCount": int(replaced_nodes_count),
                    "unchanged": bool(unchanged),
                },
            )

            self.sys.commit(s)
            return report
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    def import_learning_objects_from_browser_scan(
        self,
        project_id: ProjectId,
        *,
        root_title: str | None,
        relative_file_paths: Sequence[str],
    ) -> dict[str, object]:
        allowed_exts = {".mp4", ".mov", ".mkv", ".webm", ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}

        def _normalize_rel_path(raw: str) -> PurePosixPath:
            normalized_raw = str(raw or "").replace("\\", "/").strip()
            if not normalized_raw:
                raise PreconditionFailure("import_learning_objects_from_browser_scan: relative path must be non-empty")
            if normalized_raw.startswith("/"):
                raise PreconditionFailure("import_learning_objects_from_browser_scan: absolute path is not allowed")
            if len(normalized_raw) >= 2 and normalized_raw[1] == ":" and normalized_raw[0].isalpha():
                raise PreconditionFailure("import_learning_objects_from_browser_scan: drive path is not allowed")
            rel = normalize_material_id_to_purepath(normalized_raw)
            if rel.as_posix() in {"", "."}:
                raise PreconditionFailure("import_learning_objects_from_browser_scan: relative path must not be empty")
            if rel.is_absolute():
                raise PreconditionFailure("import_learning_objects_from_browser_scan: absolute path is not allowed")
            if any(part in {"", ".", ".."} for part in rel.parts):
                raise PreconditionFailure("import_learning_objects_from_browser_scan: invalid relative path")
            if rel.suffix.lower() not in allowed_exts:
                raise PreconditionFailure(
                    f"import_learning_objects_from_browser_scan: unsupported media extension: {rel.suffix or '(none)'}"
                )
            return rel

        file_rel = sorted({_normalize_rel_path(item) for item in relative_file_paths}, key=lambda p: p.as_posix())
        if not file_rel:
            raise PreconditionFailure("当前已授权目录中没有找到可导入的媒体文件")

        dir_rel_set: set[PurePosixPath] = {PurePosixPath(".")}
        for rel in file_rel:
            parent = rel.parent
            while True:
                dir_rel_set.add(parent)
                if parent == PurePosixPath("."):
                    break
                parent = parent.parent
        dir_rel = sorted(dir_rel_set, key=lambda p: p.as_posix())

        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            cur_instances = self.sys.instance_repo.all(s)
            cur_instances_by_key = {id_canonical_text(i.instance_id): i for i in cur_instances}

            existing_instance_id_by_material: dict[str, InstanceId] = {}
            for inst in sorted(cur_instances, key=lambda x: id_canonical_text(x.instance_id)):
                existing_instance_id_by_material.setdefault(inst.material_id.as_posix(), inst.instance_id)

            used_instance_keys: set[str] = set()
            instance_id_by_file: dict[PurePosixPath, InstanceId] = {}
            for rel in file_rel:
                existing_iid = existing_instance_id_by_material.get(rel.as_posix())
                if existing_iid is not None and id_canonical_text(existing_iid) not in used_instance_keys:
                    iid = existing_iid
                else:
                    iid = id_from_rel_path(rel)
                instance_id_by_file[rel] = iid
                used_instance_keys.add(id_canonical_text(iid))

            leaf_id_by_file: dict[PurePosixPath, LearningObjectNodeId] = {rel: node_id_from_rel_path(rel, "LEAF") for rel in file_rel}
            dir_id_by_dir: dict[PurePosixPath, LearningObjectNodeId] = {rel: node_id_from_rel_path(rel, "DIR") for rel in dir_rel}

            now = now_utc_ms()
            scanned_instance_keys = {id_canonical_text(x) for x in instance_id_by_file.values()}

            instances_to_add: list[Instance] = []
            instances_to_update: list[Instance] = []
            created_instances = 0
            updated_instances = 0
            for rel in file_rel:
                iid = instance_id_by_file[rel]
                inst_key = id_canonical_text(iid)
                existing = cur_instances_by_key.get(inst_key)
                last_seen_at = (
                    existing.last_seen_at
                    if existing is not None
                    and existing.material_id == rel
                    and existing.presence == InstancePresence.PRESENT
                    else now
                )
                desired = Instance.create(
                    project_id,
                    iid,
                    rel,
                    presence=InstancePresence.PRESENT,
                    last_seen_at=last_seen_at,
                )
                if existing is None:
                    instances_to_add.append(desired)
                    created_instances += 1
                elif existing != desired:
                    instances_to_update.append(desired)
                    updated_instances += 1

            marked_missing_instances = 0
            for inst in cur_instances:
                if id_canonical_text(inst.instance_id) in scanned_instance_keys:
                    continue
                if inst.presence == InstancePresence.MISSING:
                    continue
                marked_missing_instances += 1
                desired = Instance.create(
                    project_id,
                    inst.instance_id,
                    inst.material_id,
                    presence=InstancePresence.MISSING,
                    last_seen_at=inst.last_seen_at,
                )
                if inst != desired:
                    instances_to_update.append(desired)
                    updated_instances += 1

            child_dirs_by_dir: dict[PurePosixPath, list[PurePosixPath]] = {rel: [] for rel in dir_rel}
            file_children_by_dir: dict[PurePosixPath, list[PurePosixPath]] = {rel: [] for rel in dir_rel}
            for rel in dir_rel:
                if rel == PurePosixPath("."):
                    continue
                child_dirs_by_dir[rel.parent].append(rel)
            for rel in file_rel:
                file_children_by_dir[rel.parent].append(rel)
            for rel in dir_rel:
                child_dirs_by_dir[rel].sort(key=lambda p: p.as_posix())
                file_children_by_dir[rel].sort(key=lambda p: p.as_posix())

            display_root_title = (root_title or "").strip() or "已授权目录"
            current_binding = self.sys.project_material_source_binding_repo.get(s)
            desired_binding = ProjectMaterialSourceBinding.create(
                project_id,
                source_kind=MaterialSourceKind.BROWSER_LOCAL,
                source_root_label=display_root_title,
                updated_at=now_utc_ms(),
            )
            binding_changed = current_binding != desired_binding
            nodes_out: list[LearningObjectLeaf | LearningObjectContainer] = []

            for rel in dir_rel:
                sub_dir_ids = tuple(dir_id_by_dir[path] for path in child_dirs_by_dir.get(rel, []))
                leaf_ids = tuple(leaf_id_by_file[path] for path in file_children_by_dir.get(rel, []))
                children = tuple(list(sub_dir_ids) + list(leaf_ids))
                if rel == PurePosixPath("."):
                    parent_id = None
                    title = display_root_title
                else:
                    parent_id = dir_id_by_dir[rel.parent]
                    title = rel.name

                nodes_out.append(
                    LearningObjectContainer(
                        source="FILESYSTEM",
                        project_id=project_id,
                        node_id=dir_id_by_dir[rel],
                        relative_path=rel,
                        parent_id=parent_id,
                        children=children,
                        title=title,
                    )
                )

            for rel in file_rel:
                nodes_out.append(
                    LearningObjectLeaf(
                        source="FILESYSTEM",
                        project_id=project_id,
                        node_id=leaf_id_by_file[rel],
                        relative_path=rel,
                        parent_id=dir_id_by_dir[rel.parent],
                        instance_id=instance_id_by_file[rel],
                        title=rel.name,
                    )
                )

            for inst in instances_to_add:
                self.sys.instance_repo.add(s, inst)
            for inst in instances_to_update:
                self.sys.instance_repo.update(s, inst)
            if binding_changed:
                self.sys.project_material_source_binding_repo.set(s, desired_binding)

            replaced_nodes_count = 0
            cur_nodes = self.sys.learning_object_repo.all(s)
            cur_nodes_by_id = {id_canonical_text(n.node_id): n for n in cur_nodes}
            next_nodes_by_id = {id_canonical_text(n.node_id): n for n in nodes_out}
            if cur_nodes_by_id != next_nodes_by_id:
                self.sys.learning_object_repo.replace_all_from_fs(s, nodes_out)
                replaced_nodes_count = len(nodes_out)

            unchanged = created_instances == 0 and updated_instances == 0 and replaced_nodes_count == 0 and not binding_changed
            report: dict[str, object] = {
                "unchanged": bool(unchanged),
                "created_instances_count": int(created_instances),
                "marked_missing_count": int(marked_missing_instances),
                "replaced_learning_object_nodes_count": int(replaced_nodes_count),
                "warnings": tuple(),
            }

            if unchanged:
                self._startup_fs_sync_done.add(id_canonical_text(project_id))
                self.sys.rollback(s)
                return report

            root_hash = hashlib.sha256(display_root_title.encode("utf-8")).hexdigest()[:16]
            self._append_audit_event(
                s,
                kind=AuditEventKind.SYNC_LEARNING_OBJECTS_FROM_FS,
                api_name="import_learning_objects_from_browser_scan",
                payload={
                    "browserRootHash": root_hash,
                    "filesCount": len(file_rel),
                    "dirsCount": len(dir_rel),
                    "createdInstancesCount": int(created_instances),
                    "markedMissingCount": int(marked_missing_instances),
                    "replacedLearningObjectNodesCount": int(replaced_nodes_count),
                    "unchanged": bool(unchanged),
                },
            )

            self.sys.commit(s)
            self._startup_fs_sync_done.add(id_canonical_text(project_id))
            return report
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    def _get_aggregation_cycle_state(self, s: MutationSession, layer_index: int) -> AggregationCycleState:
        layer = self.sys.layer_repo.get_by_index(s, layer_index)
        return layer.aggregation_cycle_state

    def _set_aggregation_cycle_state(self, s: MutationSession, layer_index: int, state: AggregationCycleState) -> None:
        s.assert_open()
        if s.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        layer = self.sys.layer_repo.get_by_index(s, layer_index)
        if layer.aggregation_cycle_state == state:
            return
        updated = replace(layer, aggregation_cycle_state=state)
        updated.validate_local_invariants()
        s._staged.layers[id_canonical_text(updated.layer_id)] = updated

    def _get_pending_roll_up_parent_node_id(self, s: MutationSession, layer_index: int) -> Optional[LearningTaskNodeId]:
        layer = self.sys.layer_repo.get_by_index(s, layer_index)
        return layer.pending_roll_up_parent_node_id

    def _set_pending_roll_up_parent_node_id(
        self, s: MutationSession, layer_index: int, parent_node_id: LearningTaskNodeId
    ) -> None:
        s.assert_open()
        if s.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        layer = self.sys.layer_repo.get_by_index(s, layer_index)
        if layer.pending_roll_up_parent_node_id == parent_node_id:
            return
        updated = replace(layer, pending_roll_up_parent_node_id=parent_node_id)
        updated.validate_local_invariants()
        s._staged.layers[id_canonical_text(updated.layer_id)] = updated

    def _clear_pending_roll_up_parent_node_id(self, s: MutationSession, layer_index: int) -> None:
        s.assert_open()
        if s.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        layer = self.sys.layer_repo.get_by_index(s, layer_index)
        if layer.pending_roll_up_parent_node_id is None:
            return
        updated = replace(layer, pending_roll_up_parent_node_id=None)
        updated.validate_local_invariants()
        s._staged.layers[id_canonical_text(updated.layer_id)] = updated

    def _get_normal_tick_quota_remaining(self, s: MutationSession, layer_index: int) -> int:
        layer = self.sys.layer_repo.get_by_index(s, layer_index)
        return int(layer.normal_tick_quota_remaining)

    def _set_normal_tick_quota_remaining(self, s: MutationSession, layer_index: int, v: int) -> None:
        if v not in (0, 1):
            raise PreconditionFailure("normal_tick_quota_remaining must be 0|1")
        s.assert_open()
        if s.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        layer = self.sys.layer_repo.get_by_index(s, layer_index)
        if int(layer.normal_tick_quota_remaining) == v:
            return
        updated = replace(layer, normal_tick_quota_remaining=v)
        updated.validate_local_invariants()
        s._staged.layers[id_canonical_text(updated.layer_id)] = updated

    def _next_default_aggregation_title(self, s: MutationSession, source_layer_index: int) -> str:
        base_title = f"聚合节点@L{int(source_layer_index)}"
        existing_titles = {
            str(node.title).strip()
            for node in self.sys.learning_task_node_repo.all(s)
            if isinstance(node, LearningTaskContainer)
        }
        if base_title not in existing_titles:
            return base_title

        suffix = 2
        while f"{base_title}-{suffix}" in existing_titles:
            suffix += 1
        return f"{base_title}-{suffix}"

    def _enter_clearing_if_threshold_met(self, s: MutationSession, layer_index: int) -> bool:
        """
        Spec 4.4.2 T1: if thresholds are met, enter/keep CLEARING.
        """
        if not self.sys.queue_repo.is_empty(s):
            return False
        cur = self._get_aggregation_cycle_state(s, layer_index)
        if cur != AggregationCycleState.DONE:
            return False
        if self._get_pending_roll_up_parent_node_id(s, layer_index) is not None:
            return False
        if self._aggregation_threshold_met(s, layer_index):
            auto_title = self._next_default_aggregation_title(s, layer_index)
            parent_node_id, candidates, created = self._roll_up_phase_a(
                s, target_layer_index=layer_index, title=auto_title
            )
            if created and parent_node_id is not None:
                self._append_aggregation_event(
                    s,
                    layer_index=layer_index,
                    parent_node_id=parent_node_id,
                    candidate_node_ids=candidates,
                    reason=AggregationEventReason.THRESHOLD_DRAIN,
                    title=auto_title,
                )
                return True
        return False

    def _append_aggregation_event(
        self,
        s: MutationSession,
        *,
        layer_index: int,
        parent_node_id: LearningTaskNodeId,
        candidate_node_ids: Tuple[LearningTaskNodeId, ...],
        reason: AggregationEventReason,
        title: Optional[str],
    ) -> None:
        ev = AggregationEvent(
            project_id=s.project_id,
            event_id=self.idgen.new_aggregation_event_id(s.project_id),
            created_at=now_utc_ms(),
            layer_index=layer_index,
            parent_node_id=parent_node_id,
            child_node_ids=tuple(candidate_node_ids),
            reason=reason,
            title=title,
        )
        ev.validate_local_invariants()
        self.sys.event_repo.append(s, ev)

    # 4.5.1
    def begin_session(self, project_id: ProjectId, mode: SessionMode) -> MutationSession:
        if mode == SessionMode.READ_WRITE:
            self._ensure_startup_fs_sync_done(project_id)
        return self.sys.begin_session(project_id, mode)

    # 4.5.2
    def create_project(
        self,
        title: str,
        project_root: str | None = None,
        *,
        initial_source_kind: MaterialSourceKind = MaterialSourceKind.SERVER_FS,
    ) -> ProjectId:
        sql_store = self._sql_store()
        if sql_store is not None:
            return self._create_project_sql_direct(
                sql_store,
                title,
                project_root,
                initial_source_kind=initial_source_kind,
            )
        return self.sys.create_project(title, project_root, initial_source_kind=initial_source_kind)

    def list_projects(self) -> Tuple:
        sql_store = self._sql_store()
        if sql_store is not None:
            return sql_store.list_projects_metadata(active_only=True)

        projects = [ps.project for ps in self.sys.g.projects.values() if ps.project is not None and ps.project.state == ProjectState.ACTIVE]
        projects.sort(key=lambda p: id_canonical_text(p.project_id))
        return tuple(projects)

    def edit_project(self, project_id: ProjectId, title: str) -> None:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            if title is None or not str(title).strip():
                raise PreconditionFailure("edit_project.title must be non-empty")

            project = self.sys.project_repo.get(s, project_id)
            updated_project = Project(
                project_id=project.project_id,
                title=title,
                state=project.state,
                created_at=project.created_at,
                deleted_at=project.deleted_at,
            )
            updated_project.validate_write_time()
            self.sys.project_repo.update(s, updated_project)
            self._append_audit_event(
                s,
                kind=AuditEventKind.EDIT_PROJECT,
                api_name="edit_project",
                payload={"projectId": str(project_id)},
            )
            self.sys.commit(s)
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    def delete_project(self, project_id: ProjectId) -> None:
        sql_store = self._sql_store()
        if sql_store is not None:
            self._delete_project_sql_direct(sql_store, project_id)
            return
        self._ensure_startup_fs_sync_done(project_id)
        self.sys.delete_project(project_id)

    # 4.5.2 (read)
    def get_project_config(self, project_id: ProjectId) -> ProjectConfig:
        sql_store = self._sql_store()
        if sql_store is not None:
            item = sql_store.get_project_config(str(project_id))
            if item is not None:
                return item
            raise NotFound("ProjectConfig missing")
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.project_config_repo.get(s)
        finally:
            self.sys.rollback(s)

    def get_project_storage_config(self, project_id: ProjectId) -> ProjectStorageConfig:
        sql_store = self._sql_store()
        if sql_store is not None:
            item = sql_store.get_project_storage_config(str(project_id))
            if item is not None:
                return item
            raise NotFound("ProjectStorageConfig missing")
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.project_storage_config_repo.get(s)
        finally:
            self.sys.rollback(s)

    def get_media_asset(self, project_id: ProjectId, asset_id: MediaAssetId) -> MediaAsset:
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.media_asset_repo.get(s, asset_id)
        finally:
            self.sys.rollback(s)

    def resolve_media_asset_file_path(self, project_id: ProjectId, asset_id: MediaAssetId) -> Path:
        asset = self.get_media_asset(project_id, asset_id)
        storage_cfg = self.get_project_storage_config(project_id)
        abs_project_root = Path(storage_cfg.project_root.as_posix()).resolve()
        file_path = (abs_project_root / Path(asset.relative_path.as_posix())).resolve()
        try:
            file_path.relative_to(abs_project_root)
        except Exception as exc:
            raise PreconditionFailure("media asset path escapes project_root") from exc
        return file_path

    def get_project_material_source_binding(self, project_id: ProjectId) -> ProjectMaterialSourceBinding:
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.project_material_source_binding_repo.get(s)
        finally:
            self.sys.rollback(s)

    def list_audit_log_events(self, project_id: ProjectId) -> Tuple[AuditLogEvent, ...]:
        sql_store = self._sql_store()
        if sql_store is not None:
            return sql_store.list_audit_log_events(str(project_id))
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.audit_log_repo.all(s)
        finally:
            self.sys.rollback(s)

    def list_instances(self, project_id: ProjectId) -> Tuple:
        self._ensure_startup_fs_sync_done(project_id)
        sql_store = self._sql_store()
        if sql_store is not None:
            return sql_store.list_instances(str(project_id))
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.instance_repo.all(s)
        finally:
            self.sys.rollback(s)

    def get_instance(self, project_id: ProjectId, instance_id: InstanceId) -> Instance:
        self._ensure_startup_fs_sync_done(project_id)
        sql_store = self._sql_store()
        if sql_store is not None:
            item = sql_store.get_instance(str(project_id), str(instance_id))
            if item is not None:
                return item
            raise NotFound(instance_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.instance_repo.get(s, instance_id)
        finally:
            self.sys.rollback(s)

    # 4.5.3
    def add_instance(self, project_id: ProjectId, material_id: str) -> InstanceId:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            cfg = self.sys.project_storage_config_repo.get(s)
            binding = self.sys.project_material_source_binding_repo.get(s)
            manual_materials_allowed = binding.source_kind == MaterialSourceKind.MANUAL or (
                binding.source_kind == MaterialSourceKind.SERVER_FS and cfg.fs_sync_policy == FsSyncPolicy.DISABLED
            )
            if not manual_materials_allowed:
                raise PreconditionFailure("add_instance is disabled when materials are managed by sync/import")

            iid = self.idgen.new_instance_id(project_id)
            instance = Instance.create(project_id, iid, material_id, presence=InstancePresence.PRESENT, last_seen_at=None)
            self.sys.instance_repo.add(s, instance)
            self._append_audit_event(
                s,
                kind=AuditEventKind.ADD_INSTANCE,
                api_name="add_instance",
                payload={"instanceId": str(iid), "materialId": instance.material_id.as_posix()},
            )
            self.sys.commit(s)
            return iid
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    def add_learning_object_leaf(
        self,
        project_id: ProjectId,
        parent_id: Optional[LearningObjectNodeId],
        instance_id: InstanceId,
        title: str,
    ) -> LearningObjectNodeId:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            storage_cfg = self.sys.project_storage_config_repo.get(s)
            binding = self.sys.project_material_source_binding_repo.get(s)
            manual_materials_allowed = binding.source_kind == MaterialSourceKind.MANUAL or (
                binding.source_kind == MaterialSourceKind.SERVER_FS and storage_cfg.fs_sync_policy == FsSyncPolicy.DISABLED
            )
            if not manual_materials_allowed:
                raise PreconditionFailure("add_learning_object_leaf is disabled when materials are managed by sync/import")

            if title is None or not str(title).strip():
                raise PreconditionFailure("add_learning_object_leaf.title must be non-empty")

            if parent_id is not None:
                parent = self.sys.learning_object_repo.get(s, parent_id)
                if not isinstance(parent, LearningObjectContainer):
                    raise PreconditionFailure("add_learning_object_leaf.parent_id must refer to a container")

            try:
                inst = self.sys.instance_repo.get(s, instance_id)
            except NotFound:
                raise PreconditionFailure("add_learning_object_leaf.instance_id not resolvable")

            nid = self.idgen.new_learning_object_node_id(project_id)
            leaf = LearningObjectLeaf(
                source="MANUAL",
                project_id=project_id,
                node_id=nid,
                relative_path=inst.material_id,
                parent_id=parent_id,
                instance_id=instance_id,
                title=title,
            )
            leaf.validate_write_time()

            self.sys.learning_object_repo.add(s, leaf)

            if parent_id is not None:
                parent = self.sys.learning_object_repo.get(s, parent_id)
                if not isinstance(parent, LearningObjectContainer):
                    raise PreconditionFailure("add_learning_object_leaf.parent_id must refer to a container")
                updated_parent = LearningObjectContainer(
                    source=parent.source,
                    project_id=parent.project_id,
                    node_id=parent.node_id,
                    relative_path=parent.relative_path,
                    parent_id=parent.parent_id,
                    children=tuple(parent.children) + (nid,),
                    title=parent.title,
                )
                updated_parent.validate_write_time()
                s._staged.learning_object_nodes[id_canonical_text(updated_parent.node_id)] = updated_parent

            self._append_audit_event(
                s,
                kind=AuditEventKind.ADD_LEARNING_OBJECT_LEAF,
                api_name="add_learning_object_leaf",
                payload={
                    "nodeId": str(nid),
                    "parentId": None if parent_id is None else str(parent_id),
                    "instanceId": str(instance_id),
                },
            )
            self.sys.commit(s)
            return nid
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    def add_learning_object_container(
        self,
        project_id: ProjectId,
        parent_id: Optional[LearningObjectNodeId],
        children: Sequence[LearningObjectNodeId],
        title: str,
    ) -> LearningObjectNodeId:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            storage_cfg = self.sys.project_storage_config_repo.get(s)
            binding = self.sys.project_material_source_binding_repo.get(s)
            manual_materials_allowed = binding.source_kind == MaterialSourceKind.MANUAL or (
                binding.source_kind == MaterialSourceKind.SERVER_FS and storage_cfg.fs_sync_policy == FsSyncPolicy.DISABLED
            )
            if not manual_materials_allowed:
                raise PreconditionFailure("add_learning_object_container is disabled when materials are managed by sync/import")

            if title is None or not str(title).strip():
                raise PreconditionFailure("add_learning_object_container.title must be non-empty")

            child_ids = tuple(children) if children is not None else tuple()
            child_keys = [id_canonical_text(x) for x in child_ids]
            if len(child_keys) != len(set(child_keys)):
                raise PreconditionFailure("add_learning_object_container.children must not contain duplicates")

            if parent_id is not None:
                parent = self.sys.learning_object_repo.get(s, parent_id)
                if not isinstance(parent, LearningObjectContainer):
                    raise PreconditionFailure("add_learning_object_container.parent_id must refer to a container")
                if id_canonical_text(parent_id) in set(child_keys):
                    raise PreconditionFailure("add_learning_object_container.parent_id must not be one of children")

            # ---- Read-set prechecks (no staged writes on failure) ----
            child_nodes = [self.sys.learning_object_repo.get(s, cid) for cid in child_ids]

            new_id = self.idgen.new_learning_object_node_id(project_id)

            # Compute updates: moved children + affected old parents + (optional) new parent
            moved_by_old_parent: dict[str, list[str]] = {}
            updated_children: dict[str, LearningObjectLeaf | LearningObjectContainer] = {}

            for cid, n in zip(child_ids, child_nodes):
                ck = id_canonical_text(cid)
                old_parent = getattr(n, "parent_id", None)
                if old_parent is not None:
                    moved_by_old_parent.setdefault(id_canonical_text(old_parent), []).append(ck)

                if isinstance(n, LearningObjectLeaf):
                    updated = LearningObjectLeaf(
                        source=n.source,
                        project_id=n.project_id,
                        node_id=n.node_id,
                        relative_path=n.relative_path,
                        parent_id=new_id,
                        instance_id=n.instance_id,
                        title=n.title,
                    )
                else:
                    assert isinstance(n, LearningObjectContainer)
                    updated = LearningObjectContainer(
                        source=n.source,
                        project_id=n.project_id,
                        node_id=n.node_id,
                        relative_path=n.relative_path,
                        parent_id=new_id,
                        children=tuple(n.children),
                        title=n.title,
                    )
                updated.validate_write_time()
                updated_children[ck] = updated

            updated_old_parents: dict[str, LearningObjectContainer] = {}
            for pk, removed_child_keys in moved_by_old_parent.items():
                p = self.sys.learning_object_repo.get(s, LearningObjectNodeId(pk))
                if not isinstance(p, LearningObjectContainer):
                    raise PreconditionFailure("add_learning_object_container: child old parent must be container")
                removed = set(removed_child_keys)
                next_children = tuple(x for x in p.children if id_canonical_text(x) not in removed)
                updated_p = LearningObjectContainer(
                    source=p.source,
                    project_id=p.project_id,
                    node_id=p.node_id,
                    relative_path=p.relative_path,
                    parent_id=p.parent_id,
                    children=next_children,
                    title=p.title,
                )
                updated_p.validate_write_time()
                updated_old_parents[pk] = updated_p

            updated_new_parent: Optional[LearningObjectContainer] = None
            if parent_id is not None:
                parent = self.sys.learning_object_repo.get(s, parent_id)
                assert isinstance(parent, LearningObjectContainer)
                base_parent = updated_old_parents.get(id_canonical_text(parent_id), parent)
                updated_new_parent = LearningObjectContainer(
                    source=base_parent.source,
                    project_id=base_parent.project_id,
                    node_id=base_parent.node_id,
                    relative_path=base_parent.relative_path,
                    parent_id=base_parent.parent_id,
                    children=tuple(base_parent.children) + (new_id,),
                    title=base_parent.title,
                )
                updated_new_parent.validate_write_time()

            # ---- Writes (staged) ----
            container = LearningObjectContainer(
                source="MANUAL",
                project_id=project_id,
                node_id=new_id,
                relative_path=PurePosixPath(str(new_id)),
                parent_id=parent_id,
                children=tuple(child_ids),
                title=title,
            )
            container.validate_write_time()
            self.sys.learning_object_repo.add(s, container)

            for pk, p in updated_old_parents.items():
                s._staged.learning_object_nodes[pk] = p
            if updated_new_parent is not None:
                s._staged.learning_object_nodes[id_canonical_text(updated_new_parent.node_id)] = updated_new_parent
            for ck, n in updated_children.items():
                s._staged.learning_object_nodes[ck] = n

            self._append_audit_event(
                s,
                kind=AuditEventKind.ADD_LEARNING_OBJECT_CONTAINER,
                api_name="add_learning_object_container",
                payload={
                    "nodeId": str(new_id),
                    "parentId": None if parent_id is None else str(parent_id),
                    "childrenCount": len(child_ids),
                },
            )
            self.sys.commit(s)
            return new_id
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    # 4.5 3a
    def sync_learning_objects_from_fs(self, project_id: ProjectId) -> dict[str, object]:
        report = self._run_sync_learning_objects_from_fs(project_id)
        self._startup_fs_sync_done.add(id_canonical_text(project_id))
        return report

    # 4.5 3a
    def list_missing_instances(self, project_id: ProjectId) -> Tuple[InstanceId, ...]:
        sql_store = self._sql_store()
        if sql_store is not None:
            return sql_store.list_missing_instance_ids(str(project_id))
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            items = [i.instance_id for i in self.sys.instance_repo.all(s) if i.presence == InstancePresence.MISSING]
            items.sort(key=lambda x: id_canonical_text(x))
            return tuple(items)
        finally:
            self.sys.rollback(s)

    # 4.5 3a
    def list_recall_points_by_instance(
        self, project_id: ProjectId, instance_id: InstanceId
    ) -> Tuple[RecallPointId, ...]:
        sql_store = self._sql_store()
        if sql_store is not None:
            _ = self.get_instance(project_id, instance_id)
            return sql_store.list_recall_point_ids_by_instance(str(project_id), str(instance_id))
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            # Ensure instance_id is resolvable.
            self.sys.instance_repo.get(s, instance_id)
            want = id_canonical_text(instance_id)
            out = [
                rp.recall_point_id
                for rp in self.sys.recall_point_repo.all(s)
                if rp.state == RecallPointState.ACTIVE and id_canonical_text(rp.anchor.instance_id) == want
            ]
            out.sort(key=lambda x: id_canonical_text(x))
            return tuple(out)
        finally:
            self.sys.rollback(s)

    # 4.5 3a
    def bulk_remap_recall_points_instance(
        self,
        project_id: ProjectId,
        from_instance_id: InstanceId,
        to_instance_id: InstanceId,
        recall_point_ids: Optional[Sequence[RecallPointId]] = None,
    ) -> int:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            # ---- Precondition checks (no staged writes on failure) ----
            try:
                self.sys.instance_repo.get(s, from_instance_id)
            except NotFound:
                raise PreconditionFailure("bulk_remap_recall_points_instance.from_instance_id not resolvable")
            try:
                to_inst = self.sys.instance_repo.get(s, to_instance_id)
            except NotFound:
                raise PreconditionFailure("bulk_remap_recall_points_instance.to_instance_id not resolvable")
            _ = to_inst

            targets: list[RecallPoint] = []
            want_from = id_canonical_text(from_instance_id)
            if recall_point_ids is None:
                for rp in self.sys.recall_point_repo.all(s):
                    if (
                        rp.state == RecallPointState.ACTIVE
                        and id_canonical_text(rp.anchor.instance_id) == want_from
                    ):
                        targets.append(rp)
            else:
                for rp_id in tuple(recall_point_ids):
                    try:
                        rp = self.sys.recall_point_repo.get(s, rp_id)
                    except NotFound:
                        raise PreconditionFailure("bulk_remap_recall_points_instance.recall_point_ids contains non-resolvable id")
                    if rp.state != RecallPointState.ACTIVE:
                        raise PreconditionFailure("bulk_remap_recall_points_instance.recall_point_ids must all be ACTIVE")
                    if id_canonical_text(rp.anchor.instance_id) != want_from:
                        raise PreconditionFailure("bulk_remap_recall_points_instance.recall_point_ids must all belong to from_instance_id")
                    targets.append(rp)

            # ---- Writes (staged) ----
            changed = 0
            for rp in targets:
                updated = RecallPoint(
                    project_id=rp.project_id,
                    recall_point_id=rp.recall_point_id,
                    created_at=rp.created_at,
                    question=rp.question,
                    answer=rp.answer,
                    anchor=Anchor(instance_id=to_instance_id, position=rp.anchor.position),
                    insights=tuple(rp.insights),
                )
                updated.validate_write_time()
                self.sys.recall_point_repo.update(s, updated)
                changed += 1

            scope = "ALL_BY_FROM_INSTANCE" if recall_point_ids is None else "EXPLICIT_IDS"
            self._append_audit_event(
                s,
                kind=AuditEventKind.BULK_REMAP_RECALL_POINTS_INSTANCE,
                api_name="bulk_remap_recall_points_instance",
                payload={
                    "fromInstanceId": str(from_instance_id),
                    "toInstanceId": str(to_instance_id),
                    "movedCount": int(changed),
                    "scope": scope,
                    "explicitIdsCount": None if recall_point_ids is None else len(tuple(recall_point_ids)),
                },
            )

            self.sys.commit(s)
            return changed
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    # Deprecated (disabled): sync_material_tree
    def sync_material_tree(
        self,
        project_id: ProjectId,
        media_exts: Tuple[str, ...] = ("mp4",),
        allow_empty: bool = False,
        instance_id_remap: Optional[Tuple[Tuple[InstanceId, InstanceId], ...]] = None,
    ) -> None:
        """
        Deprecated / disabled.

        原 sync_material_tree 不在最新 spec 的 4.5 白名单内（且会产生持久化变更），因此下架。
        请使用：add_instance / add_learning_object_leaf / add_learning_object_container。
        """
        raise PreconditionFailure("sync_material_tree is disabled (not in spec whitelist)")

        # ---------- Phase 0: READ_ONLY plan inputs ----------
        s_ro = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            try:
                scan_root = self.sys.project_scan_config_repo.get(s_ro).scan_root
            except NotFound:
                raise PreconditionFailure("ProjectScanConfig not found (project bootstrap incomplete)")
            cur_instances = self.sys.instance_repo.all(s_ro)
            cur_recall_points = self.sys.recall_point_repo.all(s_ro)
        finally:
            self.sys.rollback(s_ro)

        # ---------- Phase 1: DirSnapshot scan (explicit I/O; no repo writes) ----------
        try:
            root_fs = Path(str(scan_root))
            if not root_fs.exists():
                raise PreconditionFailure(f"scan_root not found: {scan_root}")
            if not root_fs.is_dir():
                raise PreconditionFailure(f"scan_root is not a directory: {scan_root}")
        except PreconditionFailure:
            raise
        except Exception as e:
            raise PreconditionFailure(f"scan_root scan failed: {e}")

        exts_set = set(media_exts)
        rel_files: list[PurePosixPath] = []
        try:
            # Scanning policy: recursive scan (write it down to avoid implementation divergence).
            for p in root_fs.rglob("*"):
                if not p.is_file():
                    continue
                suffix = p.suffix[1:] if p.suffix.startswith(".") else p.suffix
                if suffix not in exts_set:
                    continue
                rel = p.relative_to(root_fs)
                rel_files.append(PurePosixPath(rel.as_posix()))
        except Exception as e:
            raise PreconditionFailure(f"scan_root scan failed: {e}")

        # Canonical leaf material set (dedup + sort by Unicode code point lexicographic order)
        rel_files = sorted(set(rel_files), key=lambda rp: rp.as_posix())
        target_material_ids: Tuple[PurePosixPath, ...] = tuple(scan_root / rf for rf in rel_files)

        if len(target_material_ids) == 0 and not allow_empty:
            raise PreconditionFailure("No matching media files found under scan_root")

        # Tree shape (for rebuild); if empty, we intentionally replace to an empty forest.
        dirs: set[PurePosixPath] = set()
        children_dirs: dict[PurePosixPath, list[PurePosixPath]] = defaultdict(list)
        files_in_dir: dict[PurePosixPath, list[PurePosixPath]] = defaultdict(list)
        if rel_files:
            dirs.add(PurePosixPath("."))
            for rf in rel_files:
                parent = rf.parent
                while True:
                    dirs.add(parent)
                    if parent == PurePosixPath("."):
                        break
                    parent = parent.parent
            dir_list = sorted(dirs, key=lambda d: d.as_posix())

            for d in dir_list:
                if d == PurePosixPath("."):
                    continue
                children_dirs[d.parent].append(d)
            for k in list(children_dirs.keys()):
                children_dirs[k].sort(key=lambda d: d.as_posix())

            for rf in rel_files:
                files_in_dir[rf.parent].append(rf)
            for k in list(files_in_dir.keys()):
                files_in_dir[k].sort(key=lambda rp: rp.as_posix())
        else:
            dir_list = []

        # ---------- Phase 2: Plan computation (pure; deterministic) ----------
        existing_by_material: dict[str, InstanceId] = {}
        for inst in cur_instances:
            mk = inst.material_id.as_posix()
            if mk in existing_by_material and id_canonical_text(existing_by_material[mk]) != id_canonical_text(inst.instance_id):
                raise PreconditionFailure("Instance.material_id uniqueness violated in current state")
            existing_by_material[mk] = inst.instance_id

        target_set = {mid.as_posix() for mid in target_material_ids}

        to_remove_instance_ids: list[InstanceId] = []
        for inst in cur_instances:
            if inst.material_id.as_posix() not in target_set:
                to_remove_instance_ids.append(inst.instance_id)
        to_remove_instance_ids.sort(key=lambda x: id_canonical_text(x))

        def stable_new_instance_id(material_id: PurePosixPath) -> InstanceId:
            # Deterministic, stable across calls (needed for NEEDS_MAPPING -> APPLY).
            seed = f"{id_canonical_text(project_id)}:{material_id.as_posix()}".encode("utf-8")
            h = hashlib.sha256(seed).hexdigest()[:32]
            return InstanceId(f"instm_{h}")

        target_instance_id_by_material: list[Tuple[PurePosixPath, InstanceId]] = []
        to_add_instances: list[Tuple[InstanceId, PurePosixPath]] = []
        for mid in target_material_ids:
            mk = mid.as_posix()
            if mk in existing_by_material:
                iid = existing_by_material[mk]
            else:
                iid = stable_new_instance_id(mid)
                to_add_instances.append((iid, mid))
            target_instance_id_by_material.append((mid, iid))

        target_instance_ids = sorted({id_canonical_text(iid) for _, iid in target_instance_id_by_material})

        plan = MaterialTreeSyncPlan(
            scan_root=PurePosixPath(scan_root.as_posix()),
            target_material_ids=tuple(target_material_ids),
            target_instance_id_by_material_id=tuple(target_instance_id_by_material),
            to_remove_instance_ids=tuple(to_remove_instance_ids),
            to_add_instances=tuple(to_add_instances),
            target_instance_ids=tuple(InstanceId(x) for x in target_instance_ids),
        )

        # blocked = to_remove instances referenced by any RecallPoint.anchor.instance_id
        to_remove_keys = {id_canonical_text(x) for x in plan.to_remove_instance_ids}
        blocked_keys: set[str] = set()
        affected_rp_ids: set[str] = set()
        for rp in cur_recall_points:
            ik = id_canonical_text(rp.anchor.instance_id)
            if ik in to_remove_keys:
                blocked_keys.add(ik)
                affected_rp_ids.add(id_canonical_text(rp.recall_point_id))

        blocked_instance_ids = tuple(InstanceId(x) for x in sorted(blocked_keys))
        affected_recall_point_ids = tuple(RecallPointId(x) for x in sorted(affected_rp_ids))

        # ---------- Phase 3: Mapping gate ----------
        remap_dict: dict[str, str] = {}
        if blocked_instance_ids:
            target_instance_id_set = {id_canonical_text(x) for x in plan.target_instance_ids}
            blocked_old_set = {id_canonical_text(x) for x in blocked_instance_ids}

            mapping_ok = instance_id_remap is not None and len(instance_id_remap) > 0
            if mapping_ok and instance_id_remap is not None:
                seen_old: set[str] = set()
                for old, new in instance_id_remap:
                    ok_old = id_canonical_text(old)
                    ok_new = id_canonical_text(new)
                    if ok_old not in blocked_old_set:
                        mapping_ok = False
                        break
                    if ok_old in seen_old:
                        mapping_ok = False
                        break
                    if ok_new not in target_instance_id_set:
                        mapping_ok = False
                        break
                    seen_old.add(ok_old)
                    remap_dict[ok_old] = ok_new

            if mapping_ok:
                for ok_old in blocked_old_set:
                    if ok_old not in remap_dict:
                        mapping_ok = False
                        break

            if not mapping_ok:
                return MaterialTreeSyncResult(
                    kind=MaterialTreeSyncResultKind.SYNC_PLAN_NEEDS_MAPPING,
                    plan=plan,
                    blocked_instance_ids=blocked_instance_ids,
                    affected_recall_point_ids=affected_recall_point_ids,
                )

        # ---------- Phase 4: Apply (READ_WRITE; one transaction) ----------
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            # (1) Add missing instances
            for iid, mid in plan.to_add_instances:
                inst = Instance.create(project_id, iid, mid)
                self.sys.instance_repo.add(s, inst)

            # (2) Migrate RecallPoints (user mapping)
            if remap_dict:
                for rp in self.sys.recall_point_repo.all(s):
                    if rp.state != RecallPointState.ACTIVE:
                        continue
                    old_key = id_canonical_text(rp.anchor.instance_id)
                    new_key = remap_dict.get(old_key)
                    if new_key is None:
                        continue
                    updated = RecallPoint(
                        project_id=rp.project_id,
                        recall_point_id=rp.recall_point_id,
                        created_at=rp.created_at,
                        question=rp.question,
                        answer=rp.answer,
                        anchor=Anchor(instance_id=InstanceId(new_key), position=rp.anchor.position),
                    )
                    self.sys.recall_point_repo.update(s, updated)

            # (3) Replace LearningObject forest (directory authoritative)
            nodes_out: list[LearningObjectContainer | LearningObjectLeaf] = []

            # material_id (absolute) -> instance_id
            iid_by_material: dict[str, InstanceId] = {mid.as_posix(): iid for mid, iid in plan.target_instance_id_by_material_id}

            def node_id(kind: str, rel_path: PurePosixPath) -> LearningObjectNodeId:
                seed = f"{id_canonical_text(project_id)}:{kind}:{rel_path.as_posix()}".encode("utf-8")
                h = hashlib.sha256(seed).hexdigest()[:32]
                return LearningObjectNodeId(f"lonm_{kind.lower()}_{h}")

            if rel_files:
                dir_node_id: dict[PurePosixPath, LearningObjectNodeId] = {d: node_id("DIR", d) for d in dir_list}
                files_node_id: dict[PurePosixPath, LearningObjectNodeId] = {d: node_id("FILES", d) for d in dir_list}
                leaf_node_id: dict[PurePosixPath, LearningObjectNodeId] = {rf: node_id("LEAF", rf) for rf in rel_files}

                # Files(D)
                for d in dir_list:
                    children_leaf_ids = tuple(leaf_node_id[rf] for rf in files_in_dir.get(d, []))
                    nodes_out.append(
                        LearningObjectContainer(
                            project_id=project_id,
                            node_id=files_node_id[d],
                            parent_id=dir_node_id[d],
                            children=children_leaf_ids,
                            title="Files",
                        )
                    )

                # Dir(D)
                for d in dir_list:
                    sub_dir_ids = tuple(dir_node_id[ch] for ch in children_dirs.get(d, []))
                    children = tuple(list(sub_dir_ids) + [files_node_id[d]])

                    if d == PurePosixPath("."):
                        dir_title = scan_root.name if scan_root.name else scan_root.as_posix()
                        parent_id = None
                    else:
                        dir_title = d.name
                        parent_id = dir_node_id[d.parent]

                    nodes_out.append(
                        LearningObjectContainer(
                            project_id=project_id,
                            node_id=dir_node_id[d],
                            parent_id=parent_id,
                            children=children,
                            title=dir_title,
                        )
                    )

                # Leaves (parent is Files(D))
                for rf in rel_files:
                    mid = (scan_root / rf).as_posix()
                    nodes_out.append(
                        LearningObjectLeaf(
                            project_id=project_id,
                            node_id=leaf_node_id[rf],
                            parent_id=files_node_id[rf.parent],
                            instance_id=iid_by_material[mid],
                            title=rf.name,
                        )
                    )

            self.sys.learning_object_repo.replace_forest(s, tuple(nodes_out))

            # (4) Update MaterialAllowlist (in same transaction)
            self.sys.material_allowlist_repo.replace(s, plan.target_material_ids)

            # (5) Physical delete old Instances (must happen after anchor migration)
            for iid in plan.to_remove_instance_ids:
                self.sys.instance_repo.delete(s, iid)

            self.sys.commit(s)
            return MaterialTreeSyncResult(kind=MaterialTreeSyncResultKind.SYNC_PLAN_OK, plan=plan)
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    # -------------------------
    # Internal protocols (4.3.x)
    # -------------------------
    def _next_registration_seq(self, s: MutationSession, target_layer_index: int) -> int:
        current = [
            int(reg.registration_seq)
            for reg in self.sys.entry_repo.all(s)
            if int(reg.target_layer_index) == int(target_layer_index)
        ]
        return max(current, default=0) + 1

    def _get_entry_registration_for_review_chain(self, s: MutationSession, review_chain_id: ReviewChainId) -> EntryRegistration:
        for reg in self.sys.entry_repo.all(s):
            if id_canonical_text(reg.review_chain_id) == id_canonical_text(review_chain_id):
                return reg
        raise PreconditionFailure("ReviewChainStep: review_chain_id not registered by any entry")

    def _ordered_managed_review_chain_ids(self, s: MutationSession, layer_index: int) -> Tuple[ReviewChainId, ...]:
        layer = self.sys.layer_repo.get_by_index(s, layer_index)
        managed_keys = {id_canonical_text(cid) for cid in layer.orchestrator_managed_review_chain_ids}
        ordered_regs = [
            reg
            for reg in self.sys.entry_repo.all(s)
            if int(reg.target_layer_index) == int(layer_index) and id_canonical_text(reg.review_chain_id) in managed_keys
        ]
        ordered_regs.sort(key=lambda reg: (int(reg.registration_seq), id_canonical_text(reg.entry_node)))
        return tuple(reg.review_chain_id for reg in ordered_regs)

    def _task_register(self, s: MutationSession, entry_node: LearningTaskNodeId, target_layer_index: int) -> ReviewChainId:
        seed_rp_ids = self.sys.learning_task_node_repo.covered_rp_ids(s, entry_node)
        if not seed_rp_ids:
            raise PreconditionFailure("TaskRegister: covered_rp_ids must be non-empty")
        seed_range_id = self.sys.range_repo.intern(s, tuple(seed_rp_ids))

        cfg = self.sys.project_config_repo.get(s)
        layer_cfg = cfg.layer_configs.get(int(target_layer_index), default_layer_config())

        queue_items: list[ReviewChainItem] = []

        # Spec 4.3.2: template is interpreted as a sequence of object instantiations at seed_range_id.
        for item in layer_cfg.review_chain_template:
            if item.kind == ReviewChainTemplateItemKind.CONVERGENCE:
                conv_id = self.idgen.new_convergence_id(s.project_id)
                conv = Convergence(
                    project_id=s.project_id,
                    convergence_id=conv_id,
                    seed_range_id=seed_range_id,
                    rule_id=ConvergenceRuleId("DEFAULT_RULE"),
                    review_task_ids=tuple(),
                    state=ConvergenceState.IN_PROGRESS,
                )
                conv.validate_local_invariants()
                self.sys.convergence_repo.add(s, conv)
                queue_items.append(ReviewChainItem(kind=ReviewChainItemKind.CONVERGENCE, id=conv_id))
                continue

            if item.kind == ReviewChainTemplateItemKind.REVIEW_TASK:
                n = item.effective_count()
                if n < 1:
                    raise PreconditionFailure("TaskRegister: REVIEW_TASK(count) must be >= 1")
                for _ in range(n):
                    rt_id = self.idgen.new_review_task_id(s.project_id)
                    rt = ReviewTask(
                        project_id=s.project_id,
                        review_task_id=rt_id,
                        input_range_id=seed_range_id,
                        created_at=now_utc_ms(),
                        state=ReviewTaskState.PENDING,
                        executed_at=None,
                        result_range_id=None,
                    )
                    rt.validate_local_invariants()
                    self.sys.review_task_repo.add(s, rt)
                    queue_items.append(ReviewChainItem(kind=ReviewChainItemKind.REVIEW_TASK, id=rt_id))
                continue

            raise PreconditionFailure(f"TaskRegister: unknown template item kind: {item.kind}")

        if not queue_items:
            raise PreconditionFailure("TaskRegister: review_chain_template must be non-empty")

        chain_id = self.idgen.new_review_chain_id(s.project_id)
        chain = ReviewChain(
            project_id=s.project_id,
            review_chain_id=chain_id,
            queue=tuple(queue_items),
            head_index=0,
            state=ReviewChainState.IN_PROGRESS,
        )
        chain.validate_local_invariants()
        self.sys.review_chain_repo.add(s, chain)

        registration_seq = self._next_registration_seq(s, target_layer_index)

        reg = EntryRegistration(
            project_id=s.project_id,
            entry_node=entry_node,
            target_layer_index=target_layer_index,
            review_chain_id=chain_id,
            registration_seq=registration_seq,
        )
        reg.validate_local_invariants()
        self.sys.entry_repo.add(s, reg)
        self.sys.layer_repo.upsert_managed_chain(s, target_layer_index, chain_id)
        self.sys.aggq_repo.enqueue(s, target_layer_index, entry_node)
        # Spec 4.2.4 quota reset: any successful Task Register producing a new entry in this layer resets quota to 1.
        self._set_normal_tick_quota_remaining(s, target_layer_index, 1)
        return chain_id

    def _convergence_step(self, s: MutationSession, convergence_id, entry_node: LearningTaskNodeId) -> Tuple[str, Optional[ReviewTaskId]]:
        c = self.sys.convergence_repo.get(s, convergence_id)
        if c.state == ConvergenceState.TERMINATED:
            return ("TERMINATED", None)

        if not c.review_task_ids:
            # Round 1: strictly use seed_range_id (4.3.6).
            input_range = c.seed_range_id
        else:
            last = self.sys.review_task_repo.get(s, c.review_task_ids[-1])
            if last.state == ReviewTaskState.PENDING:
                return ("BLOCKED", None)
            if last.result_range_id is None:
                self.sys.convergence_repo.update_state(s, convergence_id, ConvergenceState.TERMINATED)
                return ("TERMINATED", None)

            # last DONE and has result_range_id: derive next input based on latest covered_rp_ids.
            seed_snap = self.sys.range_repo.get(s, c.seed_range_id)
            S0 = tuple(seed_snap.recall_point_ids)

            C = self.sys.learning_task_node_repo.covered_rp_ids(s, entry_node)

            focus_snap = self.sys.range_repo.get(s, last.result_range_id)
            F = tuple(focus_snap.recall_point_ids)

            C_set = {id_canonical_text(x) for x in C}
            S0_set = {id_canonical_text(x) for x in S0}

            F_keep: list[RecallPointId] = [rp for rp in F if id_canonical_text(rp) in C_set]
            F_keep_set = {id_canonical_text(x) for x in F_keep}

            A: list[RecallPointId] = [
                rp
                for rp in C
                if id_canonical_text(rp) not in S0_set and id_canonical_text(rp) not in F_keep_set
            ]

            N: list[RecallPointId] = list(F_keep) + list(A)

            if len(N) == 0:
                self.sys.convergence_repo.update_state(s, convergence_id, ConvergenceState.TERMINATED)
                return ("TERMINATED", None)

            # Pre-resolve RecallPointIds in N before any staged writes (4.3.6).
            for rp_id in N:
                try:
                    self.sys.recall_point_repo.get(s, rp_id)
                except NotFound:
                    raise PreconditionFailure(f"ConvergenceStep: RecallPointId not resolvable: {rp_id}")

            input_range = self.sys.range_repo.intern(s, tuple(N))

        rt_id = self.idgen.new_review_task_id(s.project_id)
        rt = ReviewTask(
            project_id=s.project_id,
            review_task_id=rt_id,
            input_range_id=input_range,
            created_at=now_utc_ms(),
            state=ReviewTaskState.PENDING,
            executed_at=None,
            result_range_id=None,
        )
        rt.validate_local_invariants()
        self.sys.review_task_repo.add(s, rt)
        self.sys.convergence_repo.append_review_task_id(s, convergence_id, rt_id)
        return ("PRODUCED", rt_id)

    def _review_chain_step(self, s: MutationSession, layer_index: int, review_chain_id: ReviewChainId) -> Tuple[str, Optional[ReviewTaskId]]:
        while True:
            chain = self.sys.review_chain_repo.get(s, review_chain_id)
            head = chain.head_item()
            if head is None:
                self.sys.layer_repo.remove_managed_chain(s, layer_index, review_chain_id)
                return ("NO_EFFECT", None)

            if head.kind == ReviewChainItemKind.REVIEW_TASK:
                t = self.sys.review_task_repo.get(s, head.id)  # type: ignore[arg-type]
                if t.state == ReviewTaskState.PENDING:
                    return ("READY_EXISTING", t.review_task_id)
                self.sys.review_chain_repo.advance_head(s, review_chain_id)
                continue

            reg = self._get_entry_registration_for_review_chain(s, review_chain_id)
            kind, rt_id = self._convergence_step(s, head.id, reg.entry_node)  # type: ignore[arg-type]
            if kind == "PRODUCED" and rt_id is not None:
                return ("PRODUCED_NEW", rt_id)
            if kind == "TERMINATED":
                self.sys.review_chain_repo.advance_head(s, review_chain_id)
                continue
            if kind == "BLOCKED":
                return ("BLOCKED", None)
            return ("NO_EFFECT", None)

    def _orchestrator_gate_ok(self, s: MutationSession, layer_index: int) -> bool:
        if not self.sys.queue_repo.is_empty(s):
            return False

        layer = self.sys.layer_repo.get_by_index(s, layer_index)
        for cid in layer.orchestrator_managed_review_chain_ids:
            chain = self.sys.review_chain_repo.get(s, cid)
            if chain.state == ReviewChainState.TERMINATED:
                continue
            head = chain.head_item()
            if head is None:
                continue
            if head.kind == ReviewChainItemKind.REVIEW_TASK:
                t = self.sys.review_task_repo.get(s, head.id)  # type: ignore[arg-type]
                continue

            c = self.sys.convergence_repo.get(s, head.id)  # type: ignore[arg-type]
            if c.state == ConvergenceState.TERMINATED:
                continue
            if c.review_task_ids:
                last = self.sys.review_task_repo.get(s, c.review_task_ids[-1])
                if last.state == ReviewTaskState.PENDING:
                    return False

        return True

    def _orchestrator_tick_once(self, s: MutationSession, layer_index: int) -> TickAttemptResult:
        if not self._orchestrator_gate_ok(s, layer_index):
            return TickAttemptResult.GATE_BLOCKED

        produced_batch: list[ReviewTaskId] = []
        for cid in self._ordered_managed_review_chain_ids(s, layer_index):
            result, review_task_id = self._review_chain_step(s, layer_index, cid)
            if result in {"READY_EXISTING", "PRODUCED_NEW"} and review_task_id is not None:
                produced_batch.append(review_task_id)

        for review_task_id in produced_batch:
            self.sys.queue_repo.enqueue_if_absent(s, review_task_id)

        return TickAttemptResult.EMPTY if not produced_batch else TickAttemptResult.PRODUCED

    def _get_aggregation_thresholds(self, s: MutationSession, layer_index: int) -> tuple[int, int]:
        layer = self.sys.layer_repo.get_by_index(s, layer_index)
        k_node = int(layer.aggregation_k_node)
        k_point = int(layer.aggregation_k_point)
        if k_node <= 0:
            k_node = DEFAULT_AGGREGATION_K_NODE
        if k_point <= 0:
            k_point = DEFAULT_AGGREGATION_K_POINT
        return (k_node, k_point)

    def _aggregation_threshold_met(self, s: MutationSession, layer_index: int) -> bool:
        candidates = self.sys.aggq_repo.current_ids(s, layer_index)
        if not candidates:
            return False
        k_node, k_point = self._get_aggregation_thresholds(s, layer_index)
        if len(candidates) >= k_node:
            return True

        covered: set[str] = set()
        for nid in candidates:
            for rp in self.sys.learning_task_node_repo.covered_rp_ids(s, nid):
                covered.add(str(rp))
                if len(covered) >= k_point:
                    return True
        return False

    def _roll_up_phase_a(
        self, s: MutationSession, target_layer_index: int, title: str
    ) -> tuple[Optional[LearningTaskNodeId], Tuple[LearningTaskNodeId, ...], bool]:
        """
        Spec 4.4.4 Phase A: freeze candidate set, clear aggq current, create parent node, write pending pointer,
        and enter/keep CLEARING. This phase MUST NOT perform upper registration.
        """
        self.sys.layer_repo.get_by_index(s, target_layer_index)

        pending = self._get_pending_roll_up_parent_node_id(s, target_layer_index)
        if pending is not None:
            return (pending, tuple(), False)

        candidates = self.sys.aggq_repo.current_ids(s, target_layer_index)
        if not candidates:
            return (None, tuple(), False)

        candidate_set = set(candidates)
        for nid in candidates:
            cur = self.sys.learning_task_node_repo.get(s, nid)
            while cur.parent_id is not None:
                pid = cur.parent_id
                if pid in candidate_set:
                    raise PreconditionFailure("candidate_node_ids contains ancestor/descendant mix")
                cur = self.sys.learning_task_node_repo.get(s, pid)

        self.sys.aggq_repo.clear_current(s, target_layer_index)

        parent_title = title.strip() if title and title.strip() else self._next_default_aggregation_title(s, target_layer_index)
        parent_node_id = self.sys.learning_task_node_repo.push_up(
            s, candidate_child_ids=tuple(candidates), title=parent_title
        )

        self._set_pending_roll_up_parent_node_id(s, target_layer_index, parent_node_id)
        self._set_aggregation_cycle_state(s, target_layer_index, AggregationCycleState.CLEARING)
        return (parent_node_id, tuple(candidates), True)

    def _roll_up_phase_b(self, s: MutationSession, layer_index: int) -> None:
        """
        Spec 4.4.3 ROLL_UP Phase B: register pending parent node to upper layer,
        clear pending pointer, and mark this layer DONE.

        IMPORTANT: This phase MUST NOT call Orchestrator Tick (4.3.4) or any step-like progression.
        """
        parent_node_id = self._get_pending_roll_up_parent_node_id(s, layer_index)
        if parent_node_id is None:
            # Defensive: treat as no-op and end the cycle.
            self._set_aggregation_cycle_state(s, layer_index, AggregationCycleState.DONE)
            return

        upper = layer_index + 1
        if self.sys.layer_repo.maybe_get_by_index(s, upper) is None:
            # When a new upper layer is created by roll-up, default its mode to match the current layer.
            inherited_mode = self.sys.layer_repo.get_by_index(s, layer_index).layer_mode
            cfg = self.sys.project_config_repo.get(s)
            upper_cfg = cfg.layer_configs.get(int(upper), default_layer_config())
            layer = Layer(
                project_id=s.project_id,
                layer_id=self.idgen.new_layer_id(s.project_id),
                layer_index=upper,
                layer_mode=inherited_mode,
                orchestrator_managed_review_chain_ids=tuple(),
                aggregation_k_node=int(upper_cfg.aggregation_k_node),
                aggregation_k_point=int(upper_cfg.aggregation_k_point),
            )
            layer.validate_local_invariants()
            self.sys.layer_repo.add(s, layer)

        self._task_register(s, parent_node_id, upper)
        # Spec 4.4.2: enqueue to upper does NOT implicitly trigger upper CLEARING.
        self._enter_clearing_if_threshold_met(s, upper)

        self._clear_pending_roll_up_parent_node_id(s, layer_index)
        self._set_aggregation_cycle_state(s, layer_index, AggregationCycleState.DONE)

    def _trigger_a_tick_once(self, s: MutationSession) -> bool:
        """
        Spec 4.2.4 Trigger A (entry-triggered learning-period Tick; cross-layer):

        - Only applies when layer is not in CLEARING (CLEARING is driven by Trigger B).
        - When layer_mode is AUTO and normal_tick_quota_remaining==1, attempt one Orchestrator Tick and consume
          quota (set to 0) regardless of output.

        IMPORTANT: This must run in its own scheduling transaction (i.e. not in the same mutation session that
        performed the Task Register that reset the quota).
        """
        if not self.sys.queue_repo.is_empty(s):
            return False

        for layer in self.sys.layer_repo.all(s):
            st = self._get_aggregation_cycle_state(s, layer.layer_index)
            if st in (AggregationCycleState.CLEARING, AggregationCycleState.ROLL_UP):
                continue
            if layer.layer_mode != LayerMode.AUTO_TICK_ON_ENTRY:
                continue
            if self._get_normal_tick_quota_remaining(s, layer.layer_index) != 1:
                continue

            self._orchestrator_tick_once(s, layer.layer_index)
            self._set_normal_tick_quota_remaining(s, layer.layer_index, 0)
            return True

        return False

    def _clearing_cycle(self, s: MutationSession, *, allow_roll_up_phase_b: bool = True) -> None:
        """
        Spec 4.2.4 Trigger B / 4.4.3:

        - If any layer is in ROLL_UP, execute exactly one Phase B (no Tick in this transaction).
        - Otherwise, while the global queue is empty, pick the lowest-index CLEARING layer whose Orchestrator gate
          is satisfied and attempt one Tick.
            - PRODUCED => stop (execution phase begins; global queue becomes non-empty).
            - EMPTY => end this layer's CLEARING cycle:
                - pending exists => enter ROLL_UP and stop (Phase B must happen in a separate transaction).
                - pending empty => mark DONE and continue scanning.
        """

        if not self.sys.queue_repo.is_empty(s):
            return

        # Phase B has a strict "no Tick in the same transaction" constraint; only run it when the caller
        # guarantees no Orchestrator Tick has occurred (and will occur) in this transaction.
        if allow_roll_up_phase_b:
            for layer in self.sys.layer_repo.all(s):
                if self._get_aggregation_cycle_state(s, layer.layer_index) != AggregationCycleState.ROLL_UP:
                    continue
                self._roll_up_phase_b(s, layer.layer_index)
                return

        while self.sys.queue_repo.is_empty(s):
            chosen_layer_index: Optional[int] = None

            # Choose the first CLEARING layer (lowest layer_index) that is eligible for Tick.
            for layer in self.sys.layer_repo.all(s):
                if self._get_aggregation_cycle_state(s, layer.layer_index) != AggregationCycleState.CLEARING:
                    continue
                if not self._orchestrator_gate_ok(s, layer.layer_index):
                    continue
                chosen_layer_index = layer.layer_index
                break

            if chosen_layer_index is None:
                return

            tick_res = self._orchestrator_tick_once(s, chosen_layer_index)
            if tick_res == TickAttemptResult.PRODUCED:
                return
            if tick_res == TickAttemptResult.GATE_BLOCKED:
                # Gate should have been satisfied by selection; keep state unchanged.
                return

            # Tick returned EMPTY => end this layer's CLEARING cycle.
            if self._get_pending_roll_up_parent_node_id(s, chosen_layer_index) is not None:
                self._set_aggregation_cycle_state(s, chosen_layer_index, AggregationCycleState.ROLL_UP)
                return
            self._set_aggregation_cycle_state(s, chosen_layer_index, AggregationCycleState.DONE)

    def _best_effort_drive_idle_orchestration(self, project_id: ProjectId, *, max_iterations: int = 64) -> None:
        """
        Best-effort scheduling driver across transaction boundaries.

        Runs additional mutation sessions while:
        - global ReviewTaskQueue is empty; and
        - there exists eligible scheduling work (Trigger A, Trigger B CLEARING, or ROLL_UP Phase B).

        This is required because:
        - Trigger A Ticks must not run in the same transaction as the entry Task Register that triggered them; and
        - Phase B (ROLL_UP) must not run in the same transaction as any Tick.
        """
        for _ in range(max_iterations):
            s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
            try:
                if not self.sys.queue_repo.is_empty(s):
                    self.sys.rollback(s)
                    return

                has_roll_up = any(
                    self._get_aggregation_cycle_state(s, layer.layer_index) == AggregationCycleState.ROLL_UP
                    for layer in self.sys.layer_repo.all(s)
                )
                if has_roll_up:
                    self._clearing_cycle(s, allow_roll_up_phase_b=True)
                    self.sys.commit(s)
                    continue

                did_trigger_a = self._trigger_a_tick_once(s)
                if did_trigger_a:
                    self.sys.commit(s)
                    continue

                # Trigger B / CLEARING
                has_clearing = any(
                    self._get_aggregation_cycle_state(s, layer.layer_index) == AggregationCycleState.CLEARING
                    and self._orchestrator_gate_ok(s, layer.layer_index)
                    for layer in self.sys.layer_repo.all(s)
                )
                if not has_clearing:
                    self.sys.rollback(s)
                    return

                self._clearing_cycle(s, allow_roll_up_phase_b=True)
                self.sys.commit(s)
            except Exception:
                if s.state == SessionState.OPEN:
                    self.sys.rollback(s)
                return

    # 4.5.4
    def submit_learning_task(
        self,
        project_id: ProjectId,
        items: Sequence[tuple[RichContent, RichContent, Anchor]],
        title: str,
    ) -> LearningTaskNodeId:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            if not self.sys.queue_repo.is_empty(s):
                raise PreconditionFailure("Gate: queue not empty; submit_learning_task forbidden")
            target_layer_index = 0

            li = [LearningItem(question=q, answer=a, anchor=anc) for (q, a, anc) in items]
            res = learning_task_submit(
                session=s,
                id_gen=self.idgen,
                instance_repo=self.sys.instance_repo,
                recall_point_repo=self.sys.recall_point_repo,
                learning_task_repo=self.sys.learning_task_repo,
                learning_task_node_repo=self.sys.learning_task_node_repo,
                items=li,
                title=title,
                entry_node_title=title,
            )
            entry_node_id = res.entry_node_id

            self.sys.layer_repo.get_by_index(s, target_layer_index)
            self._task_register(s, entry_node_id, target_layer_index)

            # Spec 4.4.2 T1: threshold satisfaction enters/keeps CLEARING.
            self._enter_clearing_if_threshold_met(s, target_layer_index)

            self._append_audit_event(
                s,
                kind=AuditEventKind.SUBMIT_LEARNING_TASK,
                api_name="submit_learning_task",
                payload={"itemsCount": len(items), "entryNodeId": str(entry_node_id)},
            )
            self.sys.commit(s)
            self._best_effort_drive_idle_orchestration(project_id)
            return entry_node_id
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    def create_media_asset(
        self,
        project_id: ProjectId,
        *,
        content: bytes,
        mime_type: str,
        filename: str | None = None,
    ) -> MediaAsset:
        if not content:
            raise PreconditionFailure("media asset content must be non-empty")

        ext = self._image_extension_for_upload(mime_type, filename)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        temp_path: Path | None = None
        file_path: Path | None = None
        try:
            storage_cfg = self.sys.project_storage_config_repo.get(s)
            asset_id = self.idgen.new_media_asset_id(project_id)
            relative_path = PurePosixPath(f"media/{asset_id}{ext}")
            asset = MediaAsset(
                project_id=project_id,
                asset_id=asset_id,
                kind=MediaAssetKind.IMAGE,
                relative_path=relative_path,
                created_at=now_utc_ms(),
                mime_type=str(mime_type or "").strip().lower() or None,
            )

            abs_project_root = Path(storage_cfg.project_root.as_posix()).resolve()
            file_path = (abs_project_root / Path(relative_path.as_posix())).resolve()
            try:
                file_path.relative_to(abs_project_root)
            except Exception as exc:
                raise PreconditionFailure("media asset path escapes project_root") from exc

            file_path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_name = tempfile.mkstemp(prefix=f"{asset_id}_", suffix=ext, dir=str(file_path.parent))
            temp_path = Path(temp_name)
            with os.fdopen(fd, "wb") as fh:
                fh.write(content)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(str(temp_path), str(file_path))
            temp_path = None

            self.sys.media_asset_repo.add(s, asset)
            self.sys.commit(s)
            return asset
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except Exception:
                    pass
            if file_path is not None and file_path.exists():
                try:
                    file_path.unlink()
                except Exception:
                    pass
            raise

    # 4.5.5
    def edit_recall_point(
        self,
        project_id: ProjectId,
        recall_point_id: RecallPointId,
        question: RichContent,
        answer: RichContent,
        anchor: Anchor,
    ) -> None:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            cur = self.sys.recall_point_repo.get(s, recall_point_id)
            rp = RecallPoint(
                project_id=project_id,
                recall_point_id=recall_point_id,
                created_at=cur.created_at,
                question=question,
                answer=answer,
                anchor=anchor,
            )
            self.sys.recall_point_repo.update(s, rp)
            self._append_audit_event(
                s,
                kind=AuditEventKind.EDIT_RECALL_POINT,
                api_name="edit_recall_point",
                payload={"recallPointId": str(recall_point_id)},
            )
            self.sys.commit(s)
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    def delete_recall_point(self, project_id: ProjectId, recall_point_id: RecallPointId) -> None:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            deleted_at = now_utc_ms()
            self.sys.recall_point_repo.mark_deleted(s, recall_point_id, deleted_at)
            self._append_audit_event(
                s,
                kind=AuditEventKind.DELETE_RECALL_POINT,
                api_name="delete_recall_point",
                payload={"recallPointId": str(recall_point_id)},
            )
            self.sys.commit(s)
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    def edit_learning_task(self, project_id: ProjectId, learning_task_id: LearningTaskId, title: str) -> None:
        """
        4.5：编辑 LearningTask（不产生调度副作用）

        最小规格：只允许更新 title；recall_point_ids 不可变（由仓库 update 强约束）。
        """
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            if title is None or not str(title).strip():
                raise PreconditionFailure("edit_learning_task.title must be non-empty")

            # ---- Precondition checks (must happen before any staged writes) ----
            t = self.sys.learning_task_repo.get(s, learning_task_id)

            updated_task = LearningTask(
                project_id=project_id,
                learning_task_id=learning_task_id,
                recall_point_ids=tuple(t.recall_point_ids),
                title=title,
            )
            updated_task.validate_write_time()

            # ---- Writes (staged) ----
            self.sys.learning_task_repo.update(s, updated_task)

            # Keep node title in sync when possible (best-effort).
            try:
                leaf_id = self.sys.learning_task_node_repo.find_leaf_by_learning_task_id(s, learning_task_id)
            except NotFound:
                leaf_id = None

            if leaf_id is not None:
                leaf = self.sys.learning_task_node_repo.get(s, leaf_id)
                if not isinstance(leaf, LearningTaskLeaf):
                    raise PreconditionFailure("find_leaf_by_learning_task_id returned non-leaf node")
                updated_leaf = LearningTaskLeaf(
                    project_id=leaf.project_id,
                    node_id=leaf.node_id,
                    parent_id=leaf.parent_id,
                    bound_learning_task_id=leaf.bound_learning_task_id,
                    title=title,
                )
                updated_leaf.validate_write_time()
                s._staged.learning_task_nodes[id_canonical_text(updated_leaf.node_id)] = updated_leaf

            self._append_audit_event(
                s,
                kind=AuditEventKind.EDIT_LEARNING_TASK,
                api_name="edit_learning_task",
                payload={"learningTaskId": str(learning_task_id)},
            )
            self.sys.commit(s)
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    def set_layer_config(
        self,
        project_id: ProjectId,
        layer_index: int,
        review_chain_template: Optional[ReviewChainTemplate],
        K_node: Optional[int],
        K_point: Optional[int],
    ) -> None:
        """
        Spec 4.5: update ProjectConfig + (if exists) Layer thresholds.
        SCHEDULING_EFFECT = NONE: must not call Task Register / Tick / any step-like protocol.
        """
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            if int(layer_index) < 0:
                raise PreconditionFailure("set_layer_config.layer_index must be >= 0")

            cfg = self.sys.project_config_repo.get(s)
            cur_layer_cfg = cfg.layer_configs.get(int(layer_index), default_layer_config())

            next_layer_cfg = LayerConfig(
                review_chain_template=review_chain_template
                if review_chain_template is not None
                else cur_layer_cfg.review_chain_template,
                aggregation_k_node=int(K_node) if K_node is not None else int(cur_layer_cfg.aggregation_k_node),
                aggregation_k_point=int(K_point) if K_point is not None else int(cur_layer_cfg.aggregation_k_point),
            )
            next_layer_cfg.validate_write_time()

            layer_configs = dict(cfg.layer_configs)
            layer_configs[int(layer_index)] = next_layer_cfg
            next_cfg = ProjectConfig(
                project_id=cfg.project_id,
                layer_configs=layer_configs,
                push_config=cfg.push_config,
                updated_at=now_utc_ms(),
            )
            next_cfg.validate_write_time()

            # ---- Writes (staged) ----
            self.sys.project_config_repo.set(s, next_cfg)

            # If Layer exists, update its control fields in the same transaction (immediate effect for future).
            if self.sys.layer_repo.maybe_get_by_index(s, int(layer_index)) is not None:
                self.sys.layer_repo.update_threshold(
                    s, int(layer_index), next_layer_cfg.aggregation_k_node, next_layer_cfg.aggregation_k_point
                )

            self._append_audit_event(
                s,
                kind=AuditEventKind.EDIT_PROJECT_CONFIG,
                api_name="set_layer_config",
                payload={"layerIndex": int(layer_index)},
            )

            self.sys.commit(s)
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    def set_project_material_source_binding(
        self,
        project_id: ProjectId,
        *,
        source_kind: MaterialSourceKind,
        source_root_label: str | None = None,
    ) -> None:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            binding = ProjectMaterialSourceBinding.create(
                project_id,
                source_kind=source_kind,
                source_root_label=source_root_label,
                updated_at=now_utc_ms(),
            )
            self.sys.project_material_source_binding_repo.set(s, binding)
            self._append_audit_event(
                s,
                kind=(
                    AuditEventKind.BIND_NATIVE_LOCAL_ROOT
                    if binding.source_kind == MaterialSourceKind.NATIVE_LOCAL
                    else AuditEventKind.SET_PROJECT_MATERIAL_SOURCE_BINDING
                ),
                api_name="set_project_material_source_binding",
                payload={
                    "sourceKind": binding.source_kind.value,
                    "sourceRootLabel": binding.source_root_label,
                },
            )
            self.sys.commit(s)
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    # 4.5.6
    def executor_commit_review_task(
        self,
        project_id: ProjectId,
        review_task_id: ReviewTaskId,
        can_recall: Sequence[int],
        appended_insights: Optional[Sequence[tuple[RecallPointId, RichContent]]] = None,
    ) -> None:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            # 4.3.3 idempotency: if already DONE, treat as success (retry-safe) and do not rewrite/dequeue.
            try:
                rt = self.sys.review_task_repo.get(s, review_task_id)
            except NotFound:
                raise PreconditionFailure(f"ExecutorCommit: review_task_id not resolvable: {review_task_id}")
            if rt.state == ReviewTaskState.DONE:
                self.sys.rollback(s)
                return

            head = self.sys.queue_repo.peek_head(s)
            if head is None:
                raise PreconditionFailure("ExecutorCommit: queue empty")
            if head != review_task_id:
                raise PreconditionFailure("ExecutorCommit: must commit queue head only (strict FIFO)")

            # ---- Resolve input range (NotFound -> PreconditionFailure) ----
            try:
                input_snap = self.sys.range_repo.get(s, rt.input_range_id)
            except NotFound:
                raise PreconditionFailure(f"ExecutorCommit: input_range_id not resolvable: {rt.input_range_id}")
            rp_ids = tuple(input_snap.recall_point_ids)

            # ---- Precondition checks for appended_insights (MUST happen before any staged writes) ----
            insights = tuple(appended_insights) if appended_insights is not None else tuple()
            if insights:
                allowed = {id_canonical_text(x) for x in rp_ids}

                for rp_id, ins in insights:
                    if id_canonical_text(rp_id) not in allowed:
                        raise PreconditionFailure("appended_insights.recall_point_id must belong to input_range_id")

                    # Pre-validate RichContent (avoid partial staged writes on failure).
                    validate_rich_content_write_time(ins)
                    for b in ins:
                        if b.kind.value != "IMAGE":
                            continue
                        try:
                            self.sys.media_asset_repo.get(s, b.asset_id)
                        except NotFound:
                            raise PreconditionFailure("appended_insights contains non-resolvable asset_id")

                    # RecallPoint must be resolvable
                    try:
                        self.sys.recall_point_repo.get(s, rp_id)
                    except NotFound:
                        raise PreconditionFailure("appended_insights.recall_point_id not resolvable")

            # ---- Protocol (may stage writes) ----
            derived = review_submit_binary(
                session=s,
                review_task_repo=self.sys.review_task_repo,
                range_snapshot_repo=self.sys.range_repo,
                recall_point_repo=self.sys.recall_point_repo,
                review_task_id=review_task_id,
                can_recall=can_recall,
            )

            executed_at = now_utc_ms()

            # ---- Writes (staged) ----
            if insights:
                for rp_id, ins in insights:
                    self.sys.recall_point_repo.append_insight(s, rp_id, ins)

            # 4.5.6 review records (append-only, strict order alignment with input_range_id.recall_point_ids).
            for i, rp_id in enumerate(rp_ids):
                res = RecallPointReviewResult.CAN_RECALL if can_recall[i] == 1 else RecallPointReviewResult.CANNOT_RECALL
                rec = RecallPointReviewRecord(
                    project_id=project_id,
                    record_id=self.idgen.new_recall_point_review_record_id(project_id),
                    recall_point_id=rp_id,
                    review_task_id=review_task_id,
                    occurred_at=executed_at,
                    result=res,
                )
                self.sys.recall_point_review_record_repo.append(s, rec)

            self.sys.review_task_repo.commit_done(s, review_task_id, executed_at, derived.result_range_id)
            self.sys.queue_repo.remove_by_id(s, review_task_id)

            # Spec 4.2.4 Trigger B / 4.4.3: if queue becomes empty and any layer is in CLEARING, drive CLEARING.
            self._clearing_cycle(s)

            self._append_audit_event(
                s,
                kind=AuditEventKind.EXECUTOR_COMMIT_REVIEW_TASK,
                api_name="executor_commit_review_task",
                payload={
                    "reviewTaskId": str(review_task_id),
                    "canRecallLen": len(can_recall),
                    "appendedInsightsCount": len(insights),
                    "resultRangeId": None if derived.result_range_id is None else str(derived.result_range_id),
                },
            )
            self.sys.commit(s)
            self._best_effort_drive_idle_orchestration(project_id)
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    # 4.5.7
    def manual_roll_up(
        self, project_id: ProjectId, target_layer_index: int, title: Optional[str]
    ) -> Optional[LearningTaskNodeId]:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            if not self.sys.queue_repo.is_empty(s):
                raise PreconditionFailure("manual_roll_up gate: queue not empty")

            try:
                parent_node_id, candidates, created = self._roll_up_phase_a(
                    s,
                    target_layer_index=target_layer_index,
                    title=title or "",
                )
            except NotFound:
                raise PreconditionFailure(f"manual_roll_up precondition failed: target_layer_index={target_layer_index}")
            if not created:
                self.sys.rollback(s)
                return parent_node_id
            if parent_node_id is None:
                # created implies non-empty candidates; this should not happen.
                raise PreconditionFailure("manual_roll_up: Phase A produced no parent_node_id")

            self._append_aggregation_event(
                s,
                layer_index=target_layer_index,
                parent_node_id=parent_node_id,
                candidate_node_ids=candidates,
                reason=AggregationEventReason.MANUAL_DRAIN,
                title=self.sys.learning_task_node_repo.get(s, parent_node_id).title,
            )

            self._append_audit_event(
                s,
                kind=AuditEventKind.MANUAL_ROLL_UP,
                api_name="manual_roll_up",
                payload={
                    "targetLayerIndex": int(target_layer_index),
                    "parentNodeId": str(parent_node_id),
                    "candidateCount": len(candidates),
                },
            )
            self.sys.commit(s)
            # Spec 4.4.5: manual_roll_up must not Tick in the same transaction, but may trigger CLEARING afterwards.
            self._best_effort_drive_idle_orchestration(project_id)

            return parent_node_id
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    # 4.5.8
    def get_push_candidates(self, project_id: ProjectId, max_results: int) -> Tuple[RecallPointId, ...]:
        """
        Spec 4.7: read-only push candidates view.

        Strong constraints:
        - Pure read (READ_ONLY); must not write any persistent state.
        - Threshold gate: if N < T, must return empty and must not call local model service.
        - If recommender config is None, model calling is disabled; return deterministic fallback.
        """
        if int(max_results) <= 0:
            raise PreconditionFailure("get_push_candidates.max_results must be >= 1")

        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            cfg = self.sys.project_config_repo.get(s)

            rps = tuple(rp for rp in self.sys.recall_point_repo.all(s) if rp.state == RecallPointState.ACTIVE)
            N = len(rps)
            T = int(cfg.push_config.min_recall_points_to_enable)
            if N < T:
                return tuple()

            max_history_len = int(cfg.push_config.max_history_len)

            rec_cfg = current_native_runtime_config(
                runtime_kind=s.runtime_kind,
                runtime_capabilities=s.runtime_capabilities,
            ).local_models.recommender

            # Deterministic fallback (spec allows as fallback / disabled-model behavior).
            scored: list[tuple[tuple[int, object, str], RecallPointId]] = []
            feature_rows: list[dict[str, object]] = []
            known: set[str] = set()
            for rp in rps:
                rp_id = rp.recall_point_id
                known.add(id_canonical_text(rp_id))
                recs = self.sys.recall_point_review_record_repo.all_by_recall_point(s, rp_id)
                if max_history_len == 0:
                    recs = tuple()
                elif max_history_len > 0 and len(recs) > max_history_len:
                    recs = recs[-max_history_len:]

                # 4.7.2 features encoding (internal; deterministic).
                features: list[dict[str, int]] = []
                if recs:
                    t0 = rp.created_at
                    dt0 = int((recs[0].occurred_at - t0).total_seconds() * 1000)
                    y0 = 1 if recs[0].result.value == "CAN_RECALL" else 0
                    features.append({"dt_ms": dt0, "y": y0})
                    for i in range(1, len(recs)):
                        dti = int((recs[i].occurred_at - recs[i - 1].occurred_at).total_seconds() * 1000)
                        yi = 1 if recs[i].result.value == "CAN_RECALL" else 0
                        features.append({"dt_ms": dti, "y": yi})

                feature_rows.append({"recallPointId": str(rp_id), "features": features})

                if not recs:
                    group = 0
                    last_time = rp.created_at
                else:
                    last = recs[-1]
                    group = 1 if last.result.value == "CANNOT_RECALL" else 2
                    last_time = last.occurred_at

                key = (group, last_time, id_canonical_text(rp_id))
                scored.append((key, rp_id))

            scored.sort(key=lambda x: x[0])
            fallback_ids = [rp_id for _, rp_id in scored][: int(max_results)]

            if rec_cfg is None:
                return tuple(fallback_ids)

            # Best-effort external recommender call (4.7.3); on any failure fall back deterministically.
            try:
                url = self._resolve_local_service_url(rec_cfg, default_path="/recommender/push-candidates")
                resp = self._http_post_json(
                    url=url,
                    payload={"maxResults": int(max_results), "items": feature_rows},
                    api_key=rec_cfg.api_key,
                    timeout_sec=3.0,
                )
                ids_raw = resp.get("recallPointIds")
                if not isinstance(ids_raw, list):
                    return tuple(fallback_ids)

                out: list[RecallPointId] = []
                seen: set[str] = set()
                for x in ids_raw:
                    sid = str(x).strip()
                    if not sid or sid not in known:
                        continue
                    if sid in seen:
                        continue
                    seen.add(sid)
                    out.append(RecallPointId(sid))
                    if len(out) >= int(max_results):
                        break
                return tuple(out) if out else tuple(fallback_ids)
            except Exception:
                return tuple(fallback_ids)
        finally:
            self.sys.rollback(s)

    # -------------------------
    # 2.9 ASR
    # -------------------------
    def _request_asr_in_session(
        self,
        s: MutationSession,
        *,
        recall_point_id: RecallPointId,
        center_ms: int,
        pre_ms: int,
        post_ms: int,
        provider: AsrProvider,
    ) -> AsrArtifactId:
        s.assert_open()
        if s.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("request_asr requires READ_WRITE session")

        if int(pre_ms) < 0 or int(post_ms) < 0:
            raise PreconditionFailure("request_asr precondition failed: pre_ms/post_ms must be >= 0")
        if int(pre_ms) + int(post_ms) > MAX_ASR_WINDOW_MS:
            raise PreconditionFailure(f"request_asr window too large (max {MAX_ASR_WINDOW_MS}ms)")

        self._require_runtime_capability(
            s,
            capability=RuntimeCapability.LOCAL_ASR,
            api_name="request_asr",
        )

        rp = self.sys.recall_point_repo.get(s, recall_point_id)  # may raise NotFound
        if rp.state != RecallPointState.ACTIVE:
            raise PreconditionFailure("request_asr precondition failed: recall_point_id must resolve to ACTIVE RecallPoint")
        source_instance_id = rp.anchor.instance_id
        if not str(source_instance_id):
            raise PreconditionFailure("request_asr precondition failed: source_instance_id missing")

        runtime_cfg = current_native_runtime_config(
            runtime_kind=s.runtime_kind,
            runtime_capabilities=s.runtime_capabilities,
        )
        asr_cfg = runtime_cfg.local_models.asr
        if asr_cfg is None:
            raise PreconditionFailure("request_asr runtime is unavailable")

        hit = self.sys.asr_artifact_repo.maybe_get_by_cache_key(s, recall_point_id, provider, int(center_ms), int(pre_ms), int(post_ms))
        if hit is not None:
            return hit.asr_artifact_id

        try:
            inst = self.sys.instance_repo.get(s, source_instance_id)
        except NotFound:
            raise PreconditionFailure("request_asr precondition failed: source_instance_id not resolvable")

        storage = self.sys.project_storage_config_repo.get(s)
        binding = self.sys.project_material_source_binding_repo.get(s)
        try:
            file_path = resolve_material_file_path(storage, inst.material_id, source_kind=binding.source_kind)
        except PreconditionFailure as exc:
            raise PreconditionFailure(f"request_asr precondition failed: {exc}") from exc

        if not file_path.exists() or not file_path.is_file():
            raise PreconditionFailure("request_asr precondition failed: material file not found")

        ext = file_path.suffix.lower()
        allowed = {".mp4", ".mov", ".mkv", ".webm", ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
        if ext not in allowed:
            raise PreconditionFailure(f"request_asr precondition failed: unsupported material type: {ext or '(no ext)'}")

        use_local_whisper = False
        if is_builtin_whisper_base_url(asr_cfg.base_url):
            url = f"{ensure_local_whisper_runtime()}/asr/request"
            api_key = None
            model_name = asr_cfg.model
            use_local_whisper = True
        else:
            url = self._resolve_local_service_url(asr_cfg, default_path="/asr/request")
            api_key = asr_cfg.api_key
            model_name = asr_cfg.model

        try:
            resp = self._http_post_json(
                url=url,
                payload={
                    "provider": provider.value,
                    "source": {"filePath": str(file_path), "instanceId": str(source_instance_id), "materialId": inst.material_id.as_posix()},
                    "window": {"centerMs": int(center_ms), "preMs": int(pre_ms), "postMs": int(post_ms)},
                    "model": model_name,
                },
                api_key=api_key,
                timeout_sec=600.0 if use_local_whisper else 60.0,
            )
        except ExternalServiceError as e:
            raise ExternalServiceError(f"ASR service error: {e}") from e

        segs_raw = resp.get("segments", [])
        if segs_raw is None:
            segs_raw = []
        if not isinstance(segs_raw, list):
            raise ExternalServiceError("ASR output invalid: segments must be a list")

        segments: list[AsrSegment] = []
        for it in segs_raw:
            if not isinstance(it, dict):
                raise ExternalServiceError("ASR output invalid: segment must be an object")
            seg = AsrSegment(
                start_ms=int(it.get("startMs", it.get("start_ms", 0))),
                end_ms=int(it.get("endMs", it.get("end_ms", 0))),
                text=str(it.get("text", "")),
                confidence=None if it.get("confidence") is None else float(it.get("confidence")),
            )
            try:
                seg.validate_write_time()
            except PreconditionFailure as e:
                raise ExternalServiceError(f"ASR output invalid: {e}") from e
            segments.append(seg)

        artifact = AsrArtifact(
            project_id=s.project_id,
            asr_artifact_id=self.idgen.new_asr_artifact_id(s.project_id),
            created_at=now_utc_ms(),
            provider=provider,
            producer_runtime_kind=s.runtime_kind,
            recall_point_id=recall_point_id,
            source_instance_id=source_instance_id,
            center_ms=int(center_ms),
            pre_ms=int(pre_ms),
            post_ms=int(post_ms),
            segments=tuple(segments),
        )
        try:
            artifact.validate_write_time()
        except PreconditionFailure as e:
            raise ExternalServiceError(f"ASR output invalid: {e}") from e
        return self.sys.asr_artifact_repo.upsert_by_cache_key(s, artifact)

    def request_asr(
        self,
        project_id: ProjectId,
        recall_point_id: RecallPointId,
        center_ms: int,
        pre_ms: int,
        post_ms: int,
        provider: AsrProvider = AsrProvider.WHISPER,
    ) -> AsrArtifactId:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            prov = provider if isinstance(provider, AsrProvider) else AsrProvider(str(provider))
            aid = self._request_asr_in_session(
                s,
                recall_point_id=RecallPointId(str(recall_point_id)),
                center_ms=int(center_ms),
                pre_ms=int(pre_ms),
                post_ms=int(post_ms),
                provider=prov,
            )
            self._append_audit_event(
                s,
                kind=AuditEventKind.REQUEST_ASR,
                api_name="request_asr",
                payload={
                    "asrArtifactId": str(aid),
                    "recallPointId": str(recall_point_id),
                    "provider": prov.value,
                    "producerRuntimeKind": s.runtime_kind.value,
                    "centerMs": int(center_ms),
                    "preMs": int(pre_ms),
                    "postMs": int(post_ms),
                },
            )
            self.sys.commit(s)
            return aid
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    # -------------------------
    # Read APIs (adapter-facing)
    # -------------------------
    def get_asr_artifact(self, project_id: ProjectId, asr_artifact_id: AsrArtifactId) -> AsrArtifact:
        sql_store = self._sql_store()
        if sql_store is not None:
            item = sql_store.get_asr_artifact(str(project_id), str(asr_artifact_id))
            if item is not None:
                return item
            raise NotFound(asr_artifact_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.asr_artifact_repo.get(s, asr_artifact_id)
        finally:
            self.sys.rollback(s)

    def list_review_recommendations(self, project_id: ProjectId, max_results: int) -> Tuple[RecallPointId, ...]:
        return self.get_push_candidates(project_id, max_results)

    def export_recall_points_by_learning_object_node(
        self, project_id: ProjectId, node_id: LearningObjectNodeId
    ) -> Tuple[RecallPoint, ...]:
        return self.list_recall_points_by_learning_object_node(project_id, node_id)

    def export_recall_points_by_learning_task_node(
        self, project_id: ProjectId, node_id: LearningTaskNodeId
    ) -> Tuple[RecallPoint, ...]:
        return self.list_recall_points_by_learning_task_node(project_id, node_id)

    def export_asr_by_learning_object_node(self, project_id: ProjectId, node_id: LearningObjectNodeId) -> Tuple[AsrArtifact, ...]:
        sql_store = self._sql_store()
        if sql_store is not None:
            _ = self.get_learning_object_node(project_id, node_id)
            return sql_store.export_asr_by_learning_object_node(str(project_id), str(node_id))
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            inst_ids = self.sys.learning_object_repo.covered_instance_id_sequence(s, node_id)
            inst_set = {id_canonical_text(x) for x in inst_ids}
            recall_point_key_set = {
                id_canonical_text(rp.recall_point_id)
                for rp in self.sys.recall_point_repo.all(s)
                if rp.state == RecallPointState.ACTIVE and id_canonical_text(rp.anchor.instance_id) in inst_set
            }
            items = [
                art
                for art in self.sys.asr_artifact_repo.all(s)
                if id_canonical_text(art.recall_point_id) in recall_point_key_set
            ]
            items.sort(
                key=lambda art: (
                    id_canonical_text(art.recall_point_id),
                    str(art.provider.value),
                    int(art.center_ms),
                    int(art.pre_ms),
                    int(art.post_ms),
                    id_canonical_text(art.asr_artifact_id),
                )
            )
            return tuple(items)
        finally:
            self.sys.rollback(s)

    def export_asr_by_learning_task_node(self, project_id: ProjectId, node_id: LearningTaskNodeId) -> Tuple[AsrArtifact, ...]:
        sql_store = self._sql_store()
        if sql_store is not None:
            _ = self.get_learning_task_node(project_id, node_id)
            return sql_store.export_asr_by_learning_task_node(str(project_id), str(node_id))
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            recall_point_ids = tuple(self.sys.learning_task_node_repo.covered_rp_ids(s, node_id))
            order = {id_canonical_text(rp_id): i for i, rp_id in enumerate(recall_point_ids)}
            items = [
                art
                for art in self.sys.asr_artifact_repo.all(s)
                if id_canonical_text(art.recall_point_id) in order
            ]
            items.sort(
                key=lambda art: (
                    int(order[id_canonical_text(art.recall_point_id)]),
                    str(art.provider.value),
                    int(art.center_ms),
                    int(art.pre_ms),
                    int(art.post_ms),
                    id_canonical_text(art.asr_artifact_id),
                )
            )
            return tuple(items)
        finally:
            self.sys.rollback(s)

    def get_learning_object_node(self, project_id: ProjectId, node_id: LearningObjectNodeId) -> object:
        self._ensure_startup_fs_sync_done(project_id)
        sql_store = self._sql_store()
        if sql_store is not None:
            item = sql_store.get_learning_object_node(str(project_id), str(node_id))
            if item is not None:
                return item
            raise NotFound(node_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.learning_object_repo.get(s, node_id)
        finally:
            self.sys.rollback(s)

    def list_learning_object_nodes(self, project_id: ProjectId) -> Tuple[object, ...]:
        self._ensure_startup_fs_sync_done(project_id)
        sql_store = self._sql_store()
        if sql_store is not None:
            return sql_store.list_learning_object_nodes(str(project_id))
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.learning_object_repo.all(s)
        finally:
            self.sys.rollback(s)

    def list_learning_object_roots(self, project_id: ProjectId) -> Tuple[LearningObjectNodeId, ...]:
        self._ensure_startup_fs_sync_done(project_id)
        sql_store = self._sql_store()
        if sql_store is not None:
            return sql_store.list_learning_object_root_ids(str(project_id))
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            roots: list[LearningObjectNodeId] = []
            for n in self.sys.learning_object_repo.all(s):
                if getattr(n, "parent_id", None) is None:
                    roots.append(n.node_id)
            roots.sort(key=lambda x: id_canonical_text(x))
            return tuple(roots)
        finally:
            self.sys.rollback(s)

    def get_learning_task_node(self, project_id: ProjectId, node_id: LearningTaskNodeId) -> LearningTaskNode:
        sql_store = self._sql_store()
        if sql_store is not None:
            item = sql_store.get_learning_task_node(str(project_id), str(node_id))
            if item is not None:
                return item
            raise NotFound(node_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.learning_task_node_repo.get(s, node_id)
        finally:
            self.sys.rollback(s)

    def get_learning_task(self, project_id: ProjectId, learning_task_id: LearningTaskId) -> LearningTask:
        sql_store = self._sql_store()
        if sql_store is not None:
            item = sql_store.get_learning_task(str(project_id), str(learning_task_id))
            if item is not None:
                return item
            raise NotFound(learning_task_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.learning_task_repo.get(s, learning_task_id)
        finally:
            self.sys.rollback(s)

    def get_learning_task_entry_registration(
        self, project_id: ProjectId, learning_task_id: LearningTaskId
    ) -> EntryRegistration:
        sql_store = self._sql_store()
        if sql_store is not None:
            item = sql_store.get_learning_task_entry_registration(str(project_id), str(learning_task_id))
            if item is not None:
                return item
            raise NotFound(learning_task_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            entry_node_id = self.sys.learning_task_node_repo.find_leaf_by_learning_task_id(s, learning_task_id)
            return self.sys.entry_repo.get(s, entry_node_id)
        finally:
            self.sys.rollback(s)

    def get_learning_task_node_entry_registration(
        self, project_id: ProjectId, node_id: LearningTaskNodeId
    ) -> EntryRegistration:
        sql_store = self._sql_store()
        if sql_store is not None:
            item = sql_store.get_learning_task_node_entry_registration(str(project_id), str(node_id))
            if item is not None:
                return item
            raise NotFound(node_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.entry_repo.get(s, node_id)
        finally:
            self.sys.rollback(s)

    def get_review_chain_entry_registration(self, project_id: ProjectId, review_chain_id: ReviewChainId) -> EntryRegistration:
        sql_store = self._sql_store()
        if sql_store is not None:
            item = sql_store.get_review_chain_entry_registration(str(project_id), str(review_chain_id))
            if item is not None:
                return item
            raise NotFound(review_chain_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            for reg in self.sys.entry_repo.all(s):
                if id_canonical_text(reg.review_chain_id) == id_canonical_text(review_chain_id):
                    return reg
            raise NotFound(review_chain_id)
        finally:
            self.sys.rollback(s)

    def list_learning_task_nodes(self, project_id: ProjectId) -> Tuple[LearningTaskNode, ...]:
        sql_store = self._sql_store()
        if sql_store is not None:
            return sql_store.list_learning_task_nodes(str(project_id))
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.learning_task_node_repo.all(s)
        finally:
            self.sys.rollback(s)

    def list_recall_points_by_learning_task_node(self, project_id: ProjectId, node_id: LearningTaskNodeId) -> Tuple[RecallPoint, ...]:
        sql_store = self._sql_store()
        if sql_store is not None:
            _ = self.get_learning_task_node(project_id, node_id)
            return sql_store.list_recall_points_by_learning_task_node(str(project_id), str(node_id))
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            rp_ids = self.sys.learning_task_node_repo.covered_rp_ids(s, node_id)
            return tuple(self.sys.recall_point_repo.get(s, rp_id) for rp_id in rp_ids)
        finally:
            self.sys.rollback(s)

    def list_recall_points_by_learning_object_node(
        self, project_id: ProjectId, node_id: LearningObjectNodeId
    ) -> Tuple[RecallPoint, ...]:
        self._ensure_startup_fs_sync_done(project_id)
        sql_store = self._sql_store()
        if sql_store is not None:
            _ = self.get_learning_object_node(project_id, node_id)
            return sql_store.list_recall_points_by_learning_object_node(str(project_id), str(node_id))
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            inst_ids = self.sys.learning_object_repo.covered_instance_id_sequence(s, node_id)
            inst_set = {id_canonical_text(x) for x in inst_ids}
            items: list[RecallPoint] = []
            for rp in self.sys.recall_point_repo.all(s):
                if rp.state == RecallPointState.ACTIVE and id_canonical_text(rp.anchor.instance_id) in inst_set:
                    items.append(rp)
            items.sort(key=lambda r: id_canonical_text(r.recall_point_id))
            return tuple(items)
        finally:
            self.sys.rollback(s)

    def get_queue(self, project_id: ProjectId) -> Tuple[Optional[ReviewTaskId], Tuple[ReviewTaskId, ...]]:
        sql_store = self._sql_store()
        if sql_store is not None:
            item = sql_store.get_review_task_queue(str(project_id))
            if item is not None:
                return item
            raise NotFound("GLOBAL_QUEUE missing (project bootstrap not done)")
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            head = self.sys.queue_repo.peek_head(s)
            ids = self.sys.queue_repo.current_ids(s)
            return (head, ids)
        finally:
            self.sys.rollback(s)

    def get_review_task(self, project_id: ProjectId, review_task_id: ReviewTaskId) -> ReviewTask:
        sql_store = self._sql_store()
        if sql_store is not None:
            item = sql_store.get_review_task(str(project_id), str(review_task_id))
            if item is not None:
                return item
            raise NotFound(review_task_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.review_task_repo.get(s, review_task_id)
        finally:
            self.sys.rollback(s)

    def get_convergence(self, project_id: ProjectId, convergence_id: ConvergenceId) -> Convergence:
        sql_store = self._sql_store()
        if sql_store is not None:
            item = sql_store.get_convergence(str(project_id), str(convergence_id))
            if item is not None:
                return item
            raise NotFound(convergence_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.convergence_repo.get(s, convergence_id)
        finally:
            self.sys.rollback(s)

    def get_review_chain(self, project_id: ProjectId, review_chain_id: ReviewChainId) -> ReviewChain:
        sql_store = self._sql_store()
        if sql_store is not None:
            item = sql_store.get_review_chain(str(project_id), str(review_chain_id))
            if item is not None:
                return item
            raise NotFound(review_chain_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.review_chain_repo.get(s, review_chain_id)
        finally:
            self.sys.rollback(s)

    def get_range_snapshot(self, project_id: ProjectId, range_id: RangeId) -> object:
        sql_store = self._sql_store()
        if sql_store is not None:
            item = sql_store.get_range_snapshot(str(project_id), str(range_id))
            if item is not None:
                return item
            raise NotFound(range_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.range_repo.get(s, range_id)
        finally:
            self.sys.rollback(s)

    def get_recall_point(self, project_id: ProjectId, recall_point_id: RecallPointId) -> RecallPoint:
        sql_store = self._sql_store()
        if sql_store is not None:
            item = sql_store.get_recall_point(str(project_id), str(recall_point_id))
            if item is not None:
                return item
            raise NotFound(recall_point_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.recall_point_repo.get(s, recall_point_id)
        finally:
            self.sys.rollback(s)

    def list_layers(self, project_id: ProjectId) -> Tuple[Layer, ...]:
        sql_store = self._sql_store()
        if sql_store is not None:
            return sql_store.list_layers(str(project_id))
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.layer_repo.all(s)
        finally:
            self.sys.rollback(s)

    def get_aggregation_queue_current(self, project_id: ProjectId, layer_index: int) -> Tuple[LearningTaskNodeId, ...]:
        sql_store = self._sql_store()
        if sql_store is not None:
            item = sql_store.get_aggregation_queue_current(str(project_id), layer_index)
            if item is not None:
                return item
            raise NotFound(f"AggregationQueue missing for layer_index={layer_index}")
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.aggq_repo.current_ids(s, layer_index)
        finally:
            self.sys.rollback(s)

    def list_aggregation_events(self, project_id: ProjectId) -> Tuple[AggregationEvent, ...]:
        sql_store = self._sql_store()
        if sql_store is not None:
            return sql_store.list_aggregation_events(str(project_id))
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return self.sys.event_repo.all(s)
        finally:
            self.sys.rollback(s)

    # 4.5.8
    def validate_material_reachable(self, project_id: ProjectId, instance_id: InstanceId) -> ValidationResult:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            inst = self.sys.instance_repo.get(s, instance_id)
            if getattr(inst, "presence", None) == InstancePresence.MISSING:
                return ValidationResult.unreachable("material is MISSING")
            binding = self.sys.project_material_source_binding_repo.get(s)
            if binding.source_kind == MaterialSourceKind.MANUAL:
                return ValidationResult.ok()
            storage_cfg = self.sys.project_storage_config_repo.get(s)
            try:
                p = resolve_material_file_path(storage_cfg, inst.material_id, source_kind=binding.source_kind)
                if not p.exists():
                    return ValidationResult.unreachable(f"material not found: {p}")
                if not p.is_file():
                    return ValidationResult.unreachable(f"material is not a file: {p}")
            except Exception as e:
                return ValidationResult.unreachable(f"material unreachable: {e}")
            return ValidationResult.ok()
        except NotFound:
            return ValidationResult.not_found("Instance not found")
        finally:
            self.sys.rollback(s)

    def validate_recall_point_ids_resolvable(self, project_id: ProjectId, range_id: RangeId) -> ValidationResult:
        sql_store = self._sql_store()
        if sql_store is not None:
            try:
                snap = self.get_range_snapshot(project_id, range_id)
                for rp_id in snap.recall_point_ids:
                    self.get_recall_point(project_id, rp_id)
                return ValidationResult.ok()
            except NotFound as e:
                return ValidationResult.not_found(str(e))
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            snap = self.sys.range_repo.get(s, range_id)
            for rp_id in snap.recall_point_ids:
                self.sys.recall_point_repo.get(s, rp_id)
            return ValidationResult.ok()
        except NotFound as e:
            return ValidationResult.not_found(str(e))
        finally:
            self.sys.rollback(s)


class SchedulingEffect(str, Enum):
    NONE = "NONE"
    ORCHESTRATION_MUTATING = "ORCHESTRATION_MUTATING"


API_WHITELIST: dict[str, SchedulingEffect] = {
    "System.begin_session": SchedulingEffect.NONE,
    "create_project": SchedulingEffect.NONE,
    "list_projects": SchedulingEffect.NONE,
    "edit_project": SchedulingEffect.NONE,
    "get_project_config": SchedulingEffect.NONE,
    "get_project_storage_config": SchedulingEffect.NONE,
    "get_project_material_source_binding": SchedulingEffect.NONE,
    "list_audit_log_events": SchedulingEffect.NONE,
    "delete_project": SchedulingEffect.NONE,
    "add_instance": SchedulingEffect.NONE,
    "add_learning_object_leaf": SchedulingEffect.NONE,
    "add_learning_object_container": SchedulingEffect.NONE,
    "sync_learning_objects_from_fs": SchedulingEffect.NONE,
    "set_project_material_source_binding": SchedulingEffect.NONE,
    "list_missing_instances": SchedulingEffect.NONE,
    "list_recall_points_by_instance": SchedulingEffect.NONE,
    "bulk_remap_recall_points_instance": SchedulingEffect.NONE,
    "submit_learning_task": SchedulingEffect.ORCHESTRATION_MUTATING,
    "get_learning_task": SchedulingEffect.NONE,
    "get_learning_task_entry_registration": SchedulingEffect.NONE,
    "get_learning_task_node_entry_registration": SchedulingEffect.NONE,
    "get_convergence": SchedulingEffect.NONE,
    "get_review_chain": SchedulingEffect.NONE,
    "get_review_chain_entry_registration": SchedulingEffect.NONE,
    "edit_recall_point": SchedulingEffect.NONE,
    "delete_recall_point": SchedulingEffect.NONE,
    "edit_learning_task": SchedulingEffect.NONE,
    "set_layer_config": SchedulingEffect.NONE,
    "executor_commit_review_task": SchedulingEffect.ORCHESTRATION_MUTATING,
    "manual_roll_up": SchedulingEffect.ORCHESTRATION_MUTATING,
    "export_recall_points_by_learning_object_node": SchedulingEffect.NONE,
    "export_recall_points_by_learning_task_node": SchedulingEffect.NONE,
    "export_asr_by_learning_object_node": SchedulingEffect.NONE,
    "export_asr_by_learning_task_node": SchedulingEffect.NONE,
    "request_asr": SchedulingEffect.NONE,
    "list_review_recommendations": SchedulingEffect.NONE,
    "get_push_candidates": SchedulingEffect.NONE,
    "validate_material_reachable": SchedulingEffect.NONE,
    "validate_recall_point_ids_resolvable": SchedulingEffect.NONE,
}

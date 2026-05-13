import json
import hashlib
import math
import os
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Optional, Sequence, Tuple
from urllib.parse import quote, urlparse, urlunparse

import requests

from backend.models.aggregation_event import AggregationEvent
from backend.models.aggregation_queue import AggregationQueue
from backend.models.asr_artifact import AsrArtifact, AsrSegment, AsrTranscriptResult, InstanceAsrTranscriptResult
from backend.models.audit_log_event import AuditLogEvent
from backend.models.convergence import Convergence
from backend.models.global_settings import (
    DEFAULT_GLOBAL_LLM_BASE_URL,
    DEFAULT_GLOBAL_LLM_MODEL_NAME,
    DEFAULT_LLM_PROMPT_ASSEMBLY_MODE,
    GlobalLlmSettings,
    normalize_llm_prompt_assembly_mode,
)
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
    ProjectType,
    RecallPointState,
    RecallPointReviewResult,
    ReviewChainTemplateItemKind,
    ReviewChainState,
    ReviewTaskState,
    RollUpStrategy,
    RuntimeCapability,
    SessionMode,
)
from backend.models.constants import GLOBAL_QUEUE
from backend.models.errors import DirectoryStructureCorruptedError, ExternalServiceError, NotFound, PreconditionFailure
from backend.models.instance import Instance
from backend.models.instance_media_binding import InstanceMediaBinding
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
from backend.models.review_recommendation import (
    RecallPointReviewHistoryItem,
    RecallPointReviewProjection,
    RecallPointReviewRecommendation,
    RecallPointReviewRecommendationPage,
)
from backend.models.recall_point_review_record import RecallPointReviewRecord
from backend.models.rich_content import RichContent, validate_rich_content_write_time
from backend.models.review_chain import ReviewChain, ReviewChainItem, ReviewChainItemKind
from backend.models.review_task import ReviewTask
from backend.models.review_task_queue import ReviewTaskQueue
from backend.models.study_material import StudyMaterial, StudyMaterialType
from backend.models.subject_material_link import SubjectMaterialLink
from backend.models.video_watch_progress import VideoWatchProgress
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
    Timestamp,
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
from backend.repositories.persistence_interfaces import ProjectSnapshotRecord, SystemStateRecord
from backend.system.local_whisper import ensure_local_whisper_runtime, is_builtin_whisper_base_url
from backend.system.material_paths import resolve_material_file_path
from backend.system.auth_store import AuthStore, encrypt_secret_value
from backend.system.baidu_netdisk_client import BAIDU_NETDISK_PROVIDER, BaiduNetdiskApiError, BaiduNetdiskClient
from backend.system.http_runtime_config import current_http_runtime_config
from backend.system.instance_media import InstanceMediaService
from backend.system.persistence_json import (
    SCHEMA_VERSION,
    encode_project_payload,
    encode_project_payload_record,
    encode_project_shell_payload,
    encode_timestamp_ms,
)
from backend.system.persistence_store import SqlStore
from backend.system.project_paths import allocate_project_root
from backend.system.subtitle_files import find_sibling_subtitle_file, parse_subtitle_file
from backend.system.runtime_features import (
    current_env_asr_service_config,
    current_env_llm_qa_service_config,
    current_env_story_generator_service_config,
    current_runtime_features,
)
from backend.system.data_safety import collect_data_safety_status, collect_post_deploy_data_safety_status
from backend.system.inmemory_system import (
    DEFAULT_AGGREGATION_K_NODE,
    DEFAULT_AGGREGATION_K_POINT,
    ConcurrencyConflictError,
    InMemorySystem,
    MutationSession,
    ProjectStore,
    SessionState,
)


class TickAttemptResult(str, Enum):
    PRODUCED = "PRODUCED"
    EMPTY = "EMPTY"
    GATE_BLOCKED = "GATE_BLOCKED"

MAX_ASR_WINDOW_MS: int = 5 * 60 * 1000


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return max(int(default), minimum)
    try:
        return max(int(str(raw).strip()), minimum)
    except Exception:
        return max(int(default), minimum)


MAX_ASR_UPLOAD_BYTES: int = _env_int("LEARNINGPYRAMID_ASR_UPLOAD_MAX_BYTES", 25 * 1024 * 1024)
ASR_SERVER_FFMPEG_MAX_CONCURRENCY: int = _env_int("LEARNINGPYRAMID_ASR_SERVER_FFMPEG_MAX_CONCURRENCY", 2)
ASR_SERVER_FFMPEG_ACQUIRE_TIMEOUT_SEC: int = _env_int("LEARNINGPYRAMID_ASR_SERVER_FFMPEG_ACQUIRE_TIMEOUT_SEC", 15)
ASR_SERVER_FFMPEG_EXEC_TIMEOUT_SEC: int = _env_int("LEARNINGPYRAMID_ASR_SERVER_FFMPEG_EXEC_TIMEOUT_SEC", 120)
ASR_PUBLIC_BRIDGE_TTL_SEC: int = _env_int("LEARNINGPYRAMID_ASR_PUBLIC_BRIDGE_TTL_SEC", 15 * 60)
DASHSCOPE_ASR_TASK_TIMEOUT_SEC: int = _env_int("LEARNINGPYRAMID_DASHSCOPE_ASR_TASK_TIMEOUT_SEC", 10 * 60)
DASHSCOPE_ASR_TASK_POLL_INTERVAL_SEC: int = _env_int("LEARNINGPYRAMID_DASHSCOPE_ASR_TASK_POLL_INTERVAL_SEC", 2)
_ASR_SERVER_FFMPEG_SEMAPHORE = threading.BoundedSemaphore(ASR_SERVER_FFMPEG_MAX_CONCURRENCY)

_MEMORY_MASTERY_FLOOR = 0.03
_MEMORY_FALSE_POSITIVE = 0.12
_MEMORY_FALSE_NEGATIVE = 0.08
_MEMORY_LEARN_KNOWN = 0.04
_MEMORY_LEARN_UNKNOWN = 0.35
_MEMORY_HALFLIFE_GROW = 0.8
_MEMORY_HALFLIFE_SHRINK = 0.65
_MEMORY_MIN_HALFLIFE_DAYS = 0.1
_MEMORY_MAX_HALFLIFE_DAYS = 365.0
_MEMORY_INITIAL_MASTERY = 0.55
_MEMORY_INITIAL_HALFLIFE_DAYS = 1.0


@dataclass(frozen=True, slots=True)
class InstanceMediaSummary:
    instance: Instance
    media_source_kind: str
    playback_kind: str
    duration_ms: int | None


def _is_resolvable_course_anchor_position(position: str) -> bool:
    raw = str(position or "").strip()
    return raw.startswith("t=") and raw[2:].isdigit()


def _sanitize_manual_outline_segment(title: str) -> str:
    normalized = " ".join(str(title or "").replace("\\", "-").replace("/", "-").split()).strip()
    return normalized or "未命名"


@contextmanager
def _asr_server_ffmpeg_slot(api_name: str = "request_asr") -> Iterator[None]:
    acquired = _ASR_SERVER_FFMPEG_SEMAPHORE.acquire(timeout=float(ASR_SERVER_FFMPEG_ACQUIRE_TIMEOUT_SEC))
    if not acquired:
        raise PreconditionFailure(f"{api_name} server-side media extraction is busy; please retry later")
    try:
        yield
    finally:
        _ASR_SERVER_FFMPEG_SEMAPHORE.release()

class SystemAPI:
    """
    4.5 对外入口白名单（最小可运行内存实现）
    """

    def __init__(self, sys: InMemorySystem) -> None:
        self.sys = sys
        self.idgen = sys.g.idgen
        self._startup_fs_sync_done: set[str] = set()
        self._public_asr_temp_assets_lock = threading.Lock()
        self._public_asr_temp_assets: dict[str, dict[str, object]] = {}
        self._project_llm_debug_lock = threading.Lock()
        self._latest_project_llm_debug_by_project: dict[str, dict[str, Any]] = {}
        self._baidu_netdisk_client = BaiduNetdiskClient()
        self._cloud_oauth_state_lock = threading.Lock()
        self._cloud_oauth_states: dict[str, dict[str, str]] = {}

    def _sql_store(self) -> SqlStore | None:
        store = getattr(self.sys, "_persist_store", None)
        return store if isinstance(store, SqlStore) else None

    def get_store_health(self) -> dict[str, object]:
        store = getattr(self.sys, "_persist_store", None)
        if store is None or not hasattr(store, "healthcheck"):
            return {"ok": False, "error": "Persistence store is not initialized"}
        return dict(store.healthcheck())

    def _instance_media_service(self) -> InstanceMediaService:
        return InstanceMediaService(
            sys=self.sys,
            sql_store=self._sql_store(),
            baidu_client=self._baidu_netdisk_client,
        )

    def _reload_sql_state(self) -> None:
        self.sys.g.projects.clear()
        self.sys._load_persisted()

    def get_data_safety_status(self) -> dict[str, object]:
        return collect_data_safety_status(environment=current_runtime_features().app_mode).to_api_dict()

    def get_post_deploy_data_safety_status(self, *, validated: dict[str, int] | None = None) -> dict[str, object]:
        return collect_post_deploy_data_safety_status(validated=validated, environment=current_runtime_features().app_mode)

    @staticmethod
    def _sql_updated_at_text() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    def _new_cloud_oauth_state(self, *, user_id: str, provider: str) -> str:
        token = secrets.token_urlsafe(24)
        with self._cloud_oauth_state_lock:
            self._cloud_oauth_states[token] = {
                "user_id": str(user_id),
                "provider": str(provider),
                "created_at": str(time.time()),
            }
        return token

    def _consume_cloud_oauth_state(self, state: str) -> dict[str, str]:
        token = str(state or "").strip()
        if not token:
            raise PreconditionFailure("缺少云账号授权状态")
        with self._cloud_oauth_state_lock:
            payload = self._cloud_oauth_states.pop(token, None)
        if payload is None:
            raise PreconditionFailure("云账号授权状态无效或已过期")
        return payload

    def _raise_baidu_netdisk_error(self, exc: BaiduNetdiskApiError) -> None:
        if exc.kind == "unauthorized":
            raise PreconditionFailure("百度网盘授权已过期，请重新连接") from exc
        if exc.kind == "not_found":
            raise PreconditionFailure("百度网盘中的视频已不存在或无权限访问") from exc
        if exc.kind == "transcode_failed":
            raise PreconditionFailure("百度网盘视频转码失败，请稍后重试") from exc
        raise PreconditionFailure(str(exc) or "百度网盘服务暂时不可用") from exc

    @staticmethod
    def _normalize_anchor_failure_prefix(api_name: str, field_name: str) -> str:
        return f"{api_name}.{field_name}"

    def _project_type_in_session(self, session: MutationSession) -> ProjectType:
        return self.sys.project_config_repo.get(session).project_type

    def _validate_anchor_for_project_type(
        self,
        session: MutationSession,
        *,
        anchor: Anchor | None,
        api_name: str,
        field_name: str = "anchor",
    ) -> ProjectType:
        project_type = self._project_type_in_session(session)
        prefix = self._normalize_anchor_failure_prefix(api_name, field_name)

        if project_type == ProjectType.COURSE:
            if anchor is None:
                raise PreconditionFailure(f"{prefix} must be provided for COURSE projects")
            anchor.validate_write_time()
            if not _is_resolvable_course_anchor_position(anchor.position):
                raise PreconditionFailure(f"{prefix}.position must be a resolvable course anchor like t=<ms>")
            try:
                self.sys.instance_repo.get(session, anchor.instance_id)
            except NotFound:
                raise PreconditionFailure(f"{prefix}.instance_id not resolvable")
            return project_type

        if project_type == ProjectType.BOOK:
            if anchor is None:
                raise PreconditionFailure(f"{prefix} must be provided for BOOK projects")
            anchor.validate_write_time()
            if _is_resolvable_course_anchor_position(anchor.position):
                raise PreconditionFailure(f"{prefix}.position must be a non-resolvable text anchor for BOOK projects")
            try:
                self.sys.instance_repo.get(session, anchor.instance_id)
            except NotFound:
                raise PreconditionFailure(f"{prefix}.instance_id not resolvable")
            return project_type

        if project_type == ProjectType.LOOSE_POINTS:
            if anchor is not None:
                raise PreconditionFailure(f"{prefix} must be omitted for LOOSE_POINTS projects")
            return project_type

        raise PreconditionFailure(f"{api_name} project_type is unsupported")

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
        initial_project_type: ProjectType,
        project_id: ProjectId | None = None,
    ) -> ProjectId:
        pid, project_store = self._build_project_store_for_create_project(
            title,
            project_root,
            initial_source_kind=initial_source_kind,
            initial_project_type=initial_project_type,
            project_id=project_id,
        )
        project = project_store.project
        storage_config = project_store.project_storage_config
        material_source_binding = project_store.project_material_source_binding
        project_config = project_store.project_config
        review_task_queue = project_store.review_task_queue
        if (
            project is None
            or storage_config is None
            or material_source_binding is None
            or project_config is None
            or review_task_queue is None
        ):
            raise PreconditionFailure("project bootstrap incomplete")

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
                project_material_source_binding=material_source_binding,
                project_config=project_config,
                review_task_queue=review_task_queue,
                layers=tuple(project_store.layers.values()),
                aggregation_queues=tuple(project_store.aggregation_queues.values()),
                audit_events=tuple(project_store.audit_log_events.values()),
                updated_at=updated_at,
            )

        self._reload_sql_state()
        return pid

    def _build_project_store_for_create_project(
        self,
        title: str,
        project_root: str | None,
        *,
        initial_source_kind: MaterialSourceKind,
        initial_project_type: ProjectType,
        project_id: ProjectId | None = None,
        subject_id: ProjectId | None = None,
        scoped_project_id: ProjectId | None = None,
        subject_material_link: SubjectMaterialLink | None = None,
    ) -> tuple[ProjectId, ProjectStore]:
        if not isinstance(initial_source_kind, MaterialSourceKind):
            raise PreconditionFailure("create_project.initial_source_kind must be MaterialSourceKind")
        if not isinstance(initial_project_type, ProjectType):
            raise PreconditionFailure("create_project.initial_project_type must be ProjectType")
        if initial_project_type in {ProjectType.BOOK, ProjectType.LOOSE_POINTS} and initial_source_kind != MaterialSourceKind.MANUAL:
            raise PreconditionFailure("create_project for BOOK/LOOSE_POINTS must use MANUAL source kind")
        if (subject_id is None) != (scoped_project_id is None):
            raise PreconditionFailure("scoped project identity requires both subject_id and scoped_project_id")

        pid = project_id or self.idgen.new_project_id()
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
            subject_id=subject_id,
            scoped_project_id=scoped_project_id,
        )
        project.validate_write_time()

        review_task_queue = ReviewTaskQueue(
            project_id=pid,
            queue_id=GLOBAL_QUEUE,
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
        project_config = default_project_config(project_id=pid, updated_at=now_utc_ms(), project_type=initial_project_type)

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
            payload=json.dumps({"projectId": str(pid), "projectType": initial_project_type.value}, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        )
        audit_event.validate_write_time()

        project_store = ProjectStore(project=project)
        project_store.project_storage_config = storage_config
        project_store.project_material_source_binding = material_source_binding
        project_store.project_config = project_config
        project_store.subject_material_link = subject_material_link
        project_store.review_task_queue = review_task_queue
        project_store.layers = {id_canonical_text(layer0.layer_id): layer0}
        project_store.layers_by_index = {0: id_canonical_text(layer0.layer_id)}
        project_store.aggregation_queues = {0: aggregation_queue}
        project_store.audit_log_events = {id_canonical_text(audit_event.event_id): audit_event}
        return pid, project_store

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
            subject_id=project_store.project.subject_id,
            scoped_project_id=project_store.project.scoped_project_id,
            project_sequence=project_store.project.project_sequence,
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

    def _persist_project_store_sql_direct(self, sql_store: SqlStore, project_id: ProjectId) -> None:
        project_store = self.sys.g.projects.get(id_canonical_text(project_id))
        if project_store is None or project_store.project is None:
            raise NotFound(project_id)

        payload = encode_project_payload(project_store)
        project = project_store.project
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
            uow.project_snapshots.upsert(
                uow.session,
                ProjectSnapshotRecord(
                    project_id=str(project.project_id),
                    project_title=str(project.title),
                    project_state=str(project.state.value),
                    created_at_ms=encode_timestamp_ms(project.created_at),
                    deleted_at_ms=None if project.deleted_at is None else encode_timestamp_ms(project.deleted_at),
                    subject_id=None if project.subject_id is None else str(project.subject_id),
                    scoped_project_id=None if project.scoped_project_id is None else str(project.scoped_project_id),
                    project_sequence=int(project.project_sequence),
                    updated_at=updated_at,
                ),
            )
            refresh_project_indexes = getattr(sql_store, "_refresh_project_entity_indexes", None)
            if refresh_project_indexes is None:
                raise RuntimeError("SQL store does not support project entity index refresh")
            refresh_project_indexes(uow.connection, project_id=str(project_id), project_payload=payload)

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
        if not default_path.startswith("/"):
            raise ValueError("default_path must start with '/'")
        normalized_default_path = default_path.rstrip("/") or "/"
        normalized_path = (u.path or "").rstrip("/") or "/"
        if normalized_path == "/":
            return urlunparse((u.scheme, u.netloc, normalized_default_path, "", "", ""))
        if normalized_path.endswith(normalized_default_path):
            return base
        return urlunparse((u.scheme, u.netloc, normalized_path + normalized_default_path, "", "", ""))

    @staticmethod
    def _is_dashscope_host(hostname: str | None) -> bool:
        host = str(hostname or "").strip().lower()
        return bool(host) and host.startswith("dashscope") and host.endswith(".aliyuncs.com")

    @classmethod
    def _looks_like_dashscope_native_asr_service(cls, cfg: LocalServiceConfig) -> bool:
        parsed = urlparse(str(cfg.base_url or "").strip())
        model_name = str(cfg.model or "").strip().lower()
        if not cls._is_dashscope_host(parsed.hostname):
            return False
        return (
            model_name.startswith("fun-asr")
            or model_name.startswith("paraformer")
            or model_name.startswith("sensevoice")
            or model_name.startswith("qwen3-asr-flash-filetrans")
        )

    @classmethod
    def _resolve_dashscope_api_base_url(cls, cfg: LocalServiceConfig) -> str:
        parsed = urlparse(str(cfg.base_url or "").strip())
        if not parsed.scheme or not parsed.netloc or not cls._is_dashscope_host(parsed.hostname):
            raise PreconditionFailure("DashScope ASR requires a valid dashscope.aliyuncs.com base URL")
        return urlunparse((parsed.scheme, parsed.netloc, "/api/v1", "", "", ""))

    @staticmethod
    def _dashscope_asr_uses_single_file_input(model_name: str) -> bool:
        text = str(model_name or "").strip().lower()
        return text.startswith("qwen3-asr-flash-filetrans")

    def _prune_public_asr_temp_assets(self) -> None:
        now_ts = time.time()
        with self._public_asr_temp_assets_lock:
            expired_tokens = [
                token
                for token, item in self._public_asr_temp_assets.items()
                if float(item.get("expires_at", 0.0)) <= now_ts or not Path(str(item.get("path", ""))).exists()
            ]
            for token in expired_tokens:
                self._public_asr_temp_assets.pop(token, None)

    def _register_public_asr_temp_asset(
        self,
        *,
        file_path: Path,
        content_type: str,
        file_name: str,
    ) -> tuple[str, str]:
        self._prune_public_asr_temp_assets()
        http_cfg = current_http_runtime_config()
        public_origin = str(http_cfg.public_origin or "").strip().rstrip("/")
        if not public_origin:
            raise PreconditionFailure("DashScope native ASR requires LEARNINGPYRAMID_PUBLIC_ORIGIN to point to the external site origin")
        if not file_path.exists() or not file_path.is_file():
            raise PreconditionFailure("DashScope native ASR bridge file is unavailable")

        safe_name = Path(str(file_name or "clip.bin")).name or "clip.bin"
        token_seed = f"{time.time_ns()}:{file_path.resolve()}:{os.urandom(16).hex()}".encode("utf-8", errors="ignore")
        token = hashlib.sha256(token_seed).hexdigest()
        with self._public_asr_temp_assets_lock:
            self._public_asr_temp_assets[token] = {
                "path": str(file_path.resolve()),
                "content_type": str(content_type or "application/octet-stream").strip() or "application/octet-stream",
                "file_name": safe_name,
                "expires_at": time.time() + float(ASR_PUBLIC_BRIDGE_TTL_SEC),
            }
        return token, f"{public_origin}/api/public/asr-bridge/{token}/{quote(safe_name)}"

    def _unregister_public_asr_temp_asset(self, token: str) -> None:
        with self._public_asr_temp_assets_lock:
            self._public_asr_temp_assets.pop(str(token), None)

    def get_public_asr_temp_asset(self, token: str) -> tuple[Path, str, str] | None:
        self._prune_public_asr_temp_assets()
        with self._public_asr_temp_assets_lock:
            item = self._public_asr_temp_assets.get(str(token))
            if item is None:
                return None
            path = Path(str(item.get("path", "")))
            if not path.exists() or not path.is_file():
                self._public_asr_temp_assets.pop(str(token), None)
                return None
            return (
                path,
                str(item.get("content_type", "application/octet-stream")),
                str(item.get("file_name", path.name or "clip.bin")),
            )

    @staticmethod
    def _stable_json_dumps(payload: object) -> bytes:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")

    @classmethod
    def _http_post_json(
        cls,
        *,
        url: str,
        payload: dict[str, object] | None,
        api_key: Optional[str],
        timeout_sec: float,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        body = None if payload is None else cls._stable_json_dumps(payload)
        req = urllib.request.Request(url, data=body, method="POST")
        if payload is not None:
            req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        if api_key is not None and str(api_key).strip():
            req.add_header("Authorization", f"Bearer {api_key}")
        for key, value in (extra_headers or {}).items():
            if str(key).strip() and value is not None:
                req.add_header(str(key), str(value))

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

    @classmethod
    def _http_get_json(
        cls,
        *,
        url: str,
        api_key: Optional[str],
        timeout_sec: float,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/json")
        if api_key is not None and str(api_key).strip():
            req.add_header("Authorization", f"Bearer {api_key}")
        for key, value in (extra_headers or {}).items():
            if str(key).strip() and value is not None:
                req.add_header(str(key), str(value))

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

    @classmethod
    def _http_post_multipart_json(
        cls,
        *,
        url: str,
        form_fields: dict[str, object],
        file_field_name: str,
        file_path: Path,
        file_name: str,
        file_content_type: str,
        api_key: Optional[str],
        timeout_sec: float,
    ) -> dict[str, Any]:
        headers = {"Accept": "application/json"}
        if api_key is not None and str(api_key).strip():
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            with file_path.open("rb") as stream:
                resp = requests.post(
                    url,
                    data={key: str(value) for key, value in form_fields.items() if value is not None},
                    files={file_field_name: (file_name, stream, file_content_type)},
                    headers=headers,
                    timeout=float(timeout_sec),
                )
                body_text = resp.text
        except requests.RequestException as e:
            raise ExternalServiceError(f"External service unavailable: {e}") from e

        if resp.status_code >= 400:
            detail = f" body={body_text[:400]}" if body_text.strip() else ""
            raise ExternalServiceError(f"External service unavailable: HTTP {resp.status_code} {resp.reason}{detail}")

        try:
            decoded: Any = resp.json()
        except Exception as e:
            raise ExternalServiceError(f"External service returned invalid JSON: {e}") from e
        if not isinstance(decoded, dict):
            raise ExternalServiceError("External service returned non-object JSON")
        return decoded

    @staticmethod
    def _extract_audio_clip(
        *,
        ffmpeg_bin: str,
        source_path: Path,
        start_ms: int,
        duration_ms: int,
        out_path: Path,
        timeout_sec: float | None = None,
    ) -> None:
        cmd = [
            ffmpeg_bin,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source_path),
            "-ss",
            f"{start_ms / 1000:.3f}",
            "-t",
            f"{duration_ms / 1000:.3f}",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-acodec",
            "pcm_s16le",
            str(out_path),
        ]
        subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=None if timeout_sec is None else float(timeout_sec),
        )

    @staticmethod
    def _coerce_service_config(service_config: LocalServiceConfig | dict[str, object] | None) -> LocalServiceConfig | None:
        if service_config is None:
            return None
        if isinstance(service_config, LocalServiceConfig):
            service_config.validate_write_time()
            return service_config
        if isinstance(service_config, dict):
            cfg = LocalServiceConfig(
                base_url=str(service_config.get("base_url") or service_config.get("baseUrl") or "").strip(),
                model_name=None
                if service_config.get("model_name", service_config.get("modelName")) is None
                else str(service_config.get("model_name", service_config.get("modelName"))).strip() or None,
                api_key=None
                if service_config.get("api_key", service_config.get("apiKey")) is None
                else str(service_config.get("api_key", service_config.get("apiKey"))).strip() or None,
            )
            cfg.validate_write_time()
            return cfg
        raise PreconditionFailure("request_asr service_config must be LocalServiceConfig or dict")

    def _resolve_effective_asr_service_config(
        self,
        *,
        service_config: LocalServiceConfig | dict[str, object] | None,
        auth_store: AuthStore | None = None,
        user_id: str | None = None,
    ) -> tuple[LocalServiceConfig | None, str]:
        request_cfg = self._coerce_service_config(service_config)
        if self._service_config_is_available(request_cfg):
            return request_cfg, "request"
        user_cfg = self._get_saved_user_service_config(auth_store=auth_store, user_id=user_id, service_kind="asr")
        if self._service_config_is_available(user_cfg):
            return user_cfg, "user"
        env_cfg = current_env_asr_service_config()
        if self._service_config_is_available(env_cfg):
            return env_cfg, "env"
        return None, "none"

    @staticmethod
    def _parse_asr_response_segments(
        response: dict[str, Any],
        *,
        clip_start_ms: int,
        clip_duration_ms: int,
    ) -> tuple[AsrSegment, ...]:
        segs_raw = response.get("segments")
        segments: list[AsrSegment] = []

        if isinstance(segs_raw, list):
            for item in segs_raw:
                if not isinstance(item, dict):
                    raise ExternalServiceError("ASR output invalid: segment must be an object")

                if item.get("startMs") is not None or item.get("start_ms") is not None:
                    start_ms = int(round(float(item.get("startMs", item.get("start_ms", 0)))))
                else:
                    start_ms = clip_start_ms + int(round(float(item.get("start", 0.0)) * 1000))

                if item.get("endMs") is not None or item.get("end_ms") is not None:
                    end_ms = int(round(float(item.get("endMs", item.get("end_ms", start_ms)))))
                else:
                    end_ms = clip_start_ms + int(round(float(item.get("end", item.get("start", 0.0))) * 1000))

                seg = AsrSegment(
                    start_ms=start_ms,
                    end_ms=max(end_ms, start_ms),
                    text=str(item.get("text", "")),
                    confidence=None if item.get("confidence") is None else float(item.get("confidence")),
                )
                try:
                    seg.validate_write_time()
                except PreconditionFailure as e:
                    raise ExternalServiceError(f"ASR output invalid: {e}") from e
                segments.append(seg)
            return tuple(segments)

        if segs_raw is not None:
            raise ExternalServiceError("ASR output invalid: segments must be a list")

        text = str(response.get("text", "") or "").strip()
        if not text:
            return tuple()

        seg = AsrSegment(
            start_ms=clip_start_ms,
            end_ms=clip_start_ms + max(int(clip_duration_ms), 0),
            text=text,
            confidence=None,
        )
        seg.validate_write_time()
        return (seg,)

    @staticmethod
    def _parse_dashscope_transcription_segments(
        response: dict[str, Any],
        *,
        clip_start_ms: int,
        clip_duration_ms: int,
    ) -> tuple[AsrSegment, ...]:
        transcripts = response.get("transcripts")
        if not isinstance(transcripts, list):
            raise ExternalServiceError("ASR output invalid: DashScope transcripts must be a list")

        clip_end_ms = clip_start_ms + max(int(clip_duration_ms), 0)
        segments: list[AsrSegment] = []
        for transcript in transcripts:
            if not isinstance(transcript, dict):
                continue
            sentences = transcript.get("sentences")
            if not isinstance(sentences, list):
                continue
            for item in sentences:
                if not isinstance(item, dict):
                    continue
                text = str(item.get("text", "") or "").strip()
                if not text:
                    continue
                start_ms = clip_start_ms + int(item.get("begin_time", 0))
                end_ms = clip_start_ms + int(item.get("end_time", max(int(item.get("begin_time", 0)), 0)))
                start_ms = max(clip_start_ms, start_ms)
                end_ms = min(clip_end_ms, end_ms)
                if end_ms <= start_ms:
                    continue
                seg = AsrSegment(
                    start_ms=start_ms,
                    end_ms=end_ms,
                    text=text,
                    confidence=None,
                )
                try:
                    seg.validate_write_time()
                except PreconditionFailure as e:
                    raise ExternalServiceError(f"ASR output invalid: {e}") from e
                segments.append(seg)

        if segments:
            return tuple(segments)

        text_fragments = [str(item.get("text", "") or "").strip() for item in transcripts if isinstance(item, dict)]
        merged_text = " ".join(fragment for fragment in text_fragments if fragment).strip()
        if not merged_text:
            return tuple()
        seg = AsrSegment(
            start_ms=clip_start_ms,
            end_ms=clip_end_ms,
            text=merged_text,
            confidence=None,
        )
        seg.validate_write_time()
        return (seg,)

    def _request_dashscope_native_asr_segments_from_audio_file(
        self,
        *,
        audio_path: Path,
        audio_file_name: str,
        audio_content_type: str,
        clip_start_ms: int,
        clip_duration_ms: int,
        service_config: LocalServiceConfig,
    ) -> tuple[AsrSegment, ...]:
        model_name = str(service_config.model or "").strip()
        if not model_name:
            raise PreconditionFailure("DashScope ASR requires model_name to be configured")
        api_base_url = self._resolve_dashscope_api_base_url(service_config)
        token, public_audio_url = self._register_public_asr_temp_asset(
            file_path=audio_path,
            content_type=audio_content_type,
            file_name=audio_file_name,
        )
        try:
            input_payload: dict[str, object]
            if self._dashscope_asr_uses_single_file_input(model_name):
                input_payload = {"file_url": public_audio_url}
            else:
                input_payload = {"file_urls": [public_audio_url]}

            submit_resp = self._http_post_json(
                url=f"{api_base_url}/services/audio/asr/transcription",
                payload={
                    "model": model_name,
                    "input": input_payload,
                },
                api_key=service_config.api_key,
                timeout_sec=120.0,
                extra_headers={"X-DashScope-Async": "enable"},
            )
            output = submit_resp.get("output")
            if not isinstance(output, dict) or not str(output.get("task_id", "")).strip():
                raise ExternalServiceError("ASR service error: DashScope task_id is missing")
            task_id = str(output.get("task_id")).strip()

            deadline = time.monotonic() + float(DASHSCOPE_ASR_TASK_TIMEOUT_SEC)
            task_output: dict[str, Any] | None = None
            while time.monotonic() < deadline:
                task_resp = self._http_get_json(
                    url=f"{api_base_url}/tasks/{task_id}",
                    api_key=service_config.api_key,
                    timeout_sec=60.0,
                )
                current_output = task_resp.get("output")
                if not isinstance(current_output, dict):
                    raise ExternalServiceError("ASR service error: DashScope task output is invalid")
                task_status = str(current_output.get("task_status", "")).strip().upper()
                if task_status == "SUCCEEDED":
                    task_output = current_output
                    break
                if task_status in {"FAILED", "CANCELED", "CANCELLED"}:
                    message = str(current_output.get("message", "") or task_resp.get("message", "")).strip()
                    raise ExternalServiceError(
                        f"ASR service error: DashScope task {task_status.lower()}{f' - {message}' if message else ''}"
                    )
                time.sleep(float(DASHSCOPE_ASR_TASK_POLL_INTERVAL_SEC))

            if task_output is None:
                raise ExternalServiceError("ASR service error: DashScope task timed out")

            results = task_output.get("results")
            if not isinstance(results, list) or not results:
                raise ExternalServiceError("ASR service error: DashScope task results are missing")

            transcription_url: str | None = None
            for item in results:
                if not isinstance(item, dict):
                    continue
                subtask_status = str(item.get("subtask_status", "")).strip().upper()
                if subtask_status == "SUCCEEDED" and str(item.get("transcription_url", "")).strip():
                    transcription_url = str(item.get("transcription_url")).strip()
                    break
                if subtask_status in {"FAILED", "CANCELED", "CANCELLED"}:
                    message = str(item.get("message", "")).strip()
                    raise ExternalServiceError(
                        f"ASR service error: DashScope subtask {subtask_status.lower()}{f' - {message}' if message else ''}"
                    )

            if not transcription_url:
                raise ExternalServiceError("ASR service error: DashScope transcription_url is missing")

            transcription_payload = self._http_get_json(
                url=transcription_url,
                api_key=None,
                timeout_sec=60.0,
            )
            return self._parse_dashscope_transcription_segments(
                transcription_payload,
                clip_start_ms=clip_start_ms,
                clip_duration_ms=clip_duration_ms,
            )
        finally:
            self._unregister_public_asr_temp_asset(token)

    def _resolve_request_asr_context(
        self,
        s: MutationSession,
        *,
        recall_point_id: RecallPointId,
    ) -> tuple[RecallPoint, Instance]:
        rp = self.sys.recall_point_repo.get(s, recall_point_id)  # may raise NotFound
        if rp.state != RecallPointState.ACTIVE:
            raise PreconditionFailure("request_asr precondition failed: recall_point_id must resolve to ACTIVE RecallPoint")
        if rp.anchor is None:
            raise PreconditionFailure("request_asr precondition failed: recall_point must have an anchor")
        source_instance_id = rp.anchor.instance_id
        if not str(source_instance_id):
            raise PreconditionFailure("request_asr precondition failed: source_instance_id missing")

        try:
            inst = self.sys.instance_repo.get(s, source_instance_id)
        except NotFound:
            raise PreconditionFailure("request_asr precondition failed: source_instance_id not resolvable")
        return rp, inst

    def _resolve_instance_asr_context(
        self,
        s: MutationSession,
        *,
        instance_id: InstanceId,
    ) -> Instance:
        return self.sys.instance_repo.get(s, instance_id)

    @staticmethod
    def _validate_instance_asr_window(*, api_name: str, start_ms: int, end_ms: int) -> tuple[int, int]:
        if int(start_ms) < 0 or int(end_ms) < 0:
            raise PreconditionFailure(f"{api_name} precondition failed: start_ms/end_ms must be >= 0")
        if int(end_ms) <= int(start_ms):
            raise PreconditionFailure(f"{api_name} precondition failed: end_ms must be > start_ms")
        if int(end_ms) - int(start_ms) > MAX_ASR_WINDOW_MS:
            raise PreconditionFailure(f"{api_name} window too large (max {MAX_ASR_WINDOW_MS}ms)")
        return int(start_ms), int(end_ms)

    def _request_asr_segments_from_audio_file(
        self,
        *,
        audio_path: Path,
        audio_file_name: str,
        audio_content_type: str,
        clip_start_ms: int,
        clip_duration_ms: int,
        center_ms: int,
        pre_ms: int,
        post_ms: int,
        provider: AsrProvider,
        service_config: LocalServiceConfig,
        builtin_source: dict[str, object] | None = None,
    ) -> tuple[AsrSegment, ...]:
        if clip_duration_ms <= 0:
            return tuple()

        if self._looks_like_dashscope_native_asr_service(service_config):
            try:
                return self._request_dashscope_native_asr_segments_from_audio_file(
                    audio_path=audio_path,
                    audio_file_name=audio_file_name,
                    audio_content_type=audio_content_type,
                    clip_start_ms=clip_start_ms,
                    clip_duration_ms=clip_duration_ms,
                    service_config=service_config,
                )
            except ExternalServiceError as e:
                raise ExternalServiceError(f"ASR service error: {e}") from e

        if is_builtin_whisper_base_url(service_config.base_url):
            if builtin_source is None:
                raise PreconditionFailure(
                    "request_asr uploaded audio clips do not support builtin://whisper; configure an HTTP ASR base URL instead"
                )
            try:
                resp = self._http_post_json(
                    url=f"{ensure_local_whisper_runtime()}/asr/request",
                    payload={
                        "provider": provider.value,
                        "source": builtin_source,
                        "window": {"centerMs": int(center_ms), "preMs": int(pre_ms), "postMs": int(post_ms)},
                        "model": service_config.model,
                    },
                    api_key=None,
                    timeout_sec=600.0,
                )
            except ExternalServiceError as e:
                raise ExternalServiceError(f"ASR service error: {e}") from e
            return self._parse_asr_response_segments(resp, clip_start_ms=clip_start_ms, clip_duration_ms=clip_duration_ms)

        try:
            resp = self._http_post_multipart_json(
                url=self._resolve_local_service_url(service_config, default_path="/audio/transcriptions"),
                form_fields={
                    "model": service_config.model or "whisper-1",
                    "response_format": "verbose_json",
                    "timestamp_granularities[]": "segment",
                },
                file_field_name="file",
                file_path=audio_path,
                file_name=audio_file_name,
                file_content_type=audio_content_type,
                api_key=service_config.api_key,
                timeout_sec=120.0,
            )
        except ExternalServiceError as e:
            raise ExternalServiceError(f"ASR service error: {e}") from e
        return self._parse_asr_response_segments(resp, clip_start_ms=clip_start_ms, clip_duration_ms=clip_duration_ms)

    @staticmethod
    def _build_asr_result(
        *,
        project_id: ProjectId,
        provider: AsrProvider,
        recall_point_id: RecallPointId,
        source_instance_id: InstanceId,
        center_ms: int,
        pre_ms: int,
        post_ms: int,
        segments: tuple[AsrSegment, ...],
    ) -> AsrTranscriptResult:
        return AsrTranscriptResult(
            project_id=project_id,
            provider=provider,
            recall_point_id=recall_point_id,
            source_instance_id=source_instance_id,
            center_ms=int(center_ms),
            pre_ms=int(pre_ms),
            post_ms=int(post_ms),
            segments=segments,
        )

    @staticmethod
    def _build_instance_asr_result(
        *,
        project_id: ProjectId,
        provider: AsrProvider,
        source_instance_id: InstanceId,
        start_ms: int,
        end_ms: int,
        segments: tuple[AsrSegment, ...],
    ) -> InstanceAsrTranscriptResult:
        return InstanceAsrTranscriptResult(
            project_id=project_id,
            provider=provider,
            source_instance_id=source_instance_id,
            start_ms=int(start_ms),
            end_ms=int(end_ms),
            segments=segments,
        )

    @staticmethod
    def _extract_llm_content_fragments(content: Any) -> list[str]:
        if isinstance(content, str):
            return [content]
        if not isinstance(content, list):
            return []

        fragments: list[str] = []
        for item in content:
            if isinstance(item, str):
                fragments.append(item)
                continue
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str):
                fragments.append(text)
                continue
            value = item.get("value")
            if isinstance(value, str) and str(item.get("type", "")).strip().lower() == "text":
                fragments.append(value)
        return fragments

    @classmethod
    def _extract_chat_choice_text(cls, choice: dict[str, Any], *, prefer_delta: bool = False) -> str:
        candidate_keys = ("delta", "message") if prefer_delta else ("message", "delta")
        for key in candidate_keys:
            payload = choice.get(key)
            if not isinstance(payload, dict):
                continue
            fragments = cls._extract_llm_content_fragments(payload.get("content"))
            if fragments:
                return "".join(fragments)
            text = payload.get("text")
            if isinstance(text, str):
                return text

        text = choice.get("text")
        if isinstance(text, str):
            return text
        return ""

    @classmethod
    def _extract_chat_completion_text(cls, response: dict[str, Any]) -> str:
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ExternalServiceError("LLM service returned no choices")
        first = choices[0]
        if not isinstance(first, dict):
            raise ExternalServiceError("LLM service returned an invalid choice payload")
        content = cls._extract_chat_choice_text(first)
        normalized = str(content or "").strip()
        if not normalized:
            raise ExternalServiceError("LLM service returned empty content")
        return normalized

    @staticmethod
    def _iter_sse_data_payloads(resp) -> Iterator[str]:
        data_lines: list[str] = []
        while True:
            raw_line = resp.readline()
            if not raw_line:
                break
            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
            if not line:
                if data_lines:
                    yield "\n".join(data_lines)
                    data_lines.clear()
                continue
            if line.startswith(":"):
                continue
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        if data_lines:
            yield "\n".join(data_lines)

    @classmethod
    def _http_post_json_stream_text_chunks(
        cls,
        *,
        url: str,
        payload: dict[str, object],
        api_key: Optional[str],
        timeout_sec: float,
    ) -> Iterator[str]:
        body = cls._stable_json_dumps(payload)
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "text/event-stream, application/json")
        if api_key is not None and str(api_key).strip():
            req.add_header("Authorization", f"Bearer {api_key}")

        try:
            with urllib.request.urlopen(req, timeout=float(timeout_sec)) as resp:
                content_type = str(resp.headers.get_content_type() or "").strip().lower()
                if content_type != "text/event-stream":
                    raw = resp.read()
                    try:
                        decoded: Any = json.loads(raw.decode("utf-8"))
                    except Exception as e:
                        raise ExternalServiceError(f"External service returned invalid JSON: {e}") from e
                    if not isinstance(decoded, dict):
                        raise ExternalServiceError("External service returned non-object JSON")
                    text = cls._extract_chat_completion_text(decoded)
                    if text:
                        yield text
                    return

                for payload_text in cls._iter_sse_data_payloads(resp):
                    if not payload_text or payload_text == "[DONE]":
                        if payload_text == "[DONE]":
                            break
                        continue
                    try:
                        decoded = json.loads(payload_text)
                    except Exception as e:
                        raise ExternalServiceError(f"External service returned invalid stream JSON: {e}") from e
                    if not isinstance(decoded, dict):
                        raise ExternalServiceError("External service returned non-object stream JSON")
                    error_payload = decoded.get("error")
                    if isinstance(error_payload, dict):
                        message = str(error_payload.get("message") or "LLM service returned an error").strip()
                        raise ExternalServiceError(message or "LLM service returned an error")
                    choices = decoded.get("choices")
                    if not isinstance(choices, list):
                        continue
                    for choice in choices:
                        if not isinstance(choice, dict):
                            continue
                        text = cls._extract_chat_choice_text(choice, prefer_delta=True)
                        if text:
                            yield text
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                raw_body = e.read().decode("utf-8", errors="replace").strip()
                if raw_body:
                    detail = f" body={raw_body[:400]}"
            except Exception:
                detail = ""
            raise ExternalServiceError(f"External service unavailable: HTTP {e.code} {e.reason}{detail}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise ExternalServiceError(f"External service unavailable: {e}") from e

    @staticmethod
    def _normalize_llm_messages(messages: Sequence[dict[str, str]]) -> list[dict[str, str]]:
        if not messages:
            raise PreconditionFailure("LLM request must include at least one message")

        normalized_messages: list[dict[str, str]] = []
        for message in messages:
            if not isinstance(message, dict):
                raise PreconditionFailure("LLM message must be an object")
            role = str(message.get("role", "")).strip()
            content = str(message.get("content", "")).strip()
            if role not in {"system", "user", "assistant"}:
                raise PreconditionFailure("LLM message.role must be one of system/user/assistant")
            if not content:
                raise PreconditionFailure("LLM message.content must be non-empty")
            normalized_messages.append({"role": role, "content": content})
        return normalized_messages

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

    @staticmethod
    def _default_global_llm_base_url() -> str:
        value = str(os.getenv("LEARNINGPYRAMID_DEFAULT_LLM_BASE_URL") or DEFAULT_GLOBAL_LLM_BASE_URL).strip()
        return value or DEFAULT_GLOBAL_LLM_BASE_URL

    @staticmethod
    def _default_global_llm_model_name() -> str:
        value = str(os.getenv("LEARNINGPYRAMID_DEFAULT_LLM_MODEL") or DEFAULT_GLOBAL_LLM_MODEL_NAME).strip()
        return value or DEFAULT_GLOBAL_LLM_MODEL_NAME

    @staticmethod
    def _mask_api_key(value: str | None) -> str | None:
        text = str(value or "").strip()
        if not text:
            return None
        if len(text) <= 8:
            return "*" * len(text)
        return f"{text[:4]}...{text[-4:]}"

    @staticmethod
    def _service_config_is_available(cfg: LocalServiceConfig | None) -> bool:
        return cfg is not None and bool(str(cfg.base_url or "").strip())

    @staticmethod
    def _saved_service_config(
        *,
        base_url: str | None,
        model_name: str | None,
        api_key: str | None,
    ) -> LocalServiceConfig | None:
        text = str(base_url or "").strip()
        if not text:
            return None
        cfg = LocalServiceConfig(
            base_url=text,
            api_key=None if api_key is None else str(api_key).strip() or None,
            model_name=None if model_name is None else str(model_name).strip() or None,
        )
        cfg.validate_write_time()
        return cfg

    def _get_saved_user_service_config(
        self,
        *,
        auth_store: AuthStore | None,
        user_id: str | None,
        service_kind: str,
    ) -> LocalServiceConfig | None:
        if auth_store is None or not str(user_id or "").strip():
            return None
        saved = auth_store.get_user_service_config(str(user_id), service_kind=service_kind)
        if saved is None:
            return None
        return self._saved_service_config(base_url=saved.base_url, model_name=saved.model_name, api_key=saved.api_key)

    @staticmethod
    def _llm_status_payload(
        *,
        base_url: str,
        model_name: str,
        prompt_assembly_mode: str,
        saved_api_key_configured: bool,
        saved_api_key_preview: str | None,
        llm_configured: bool,
        story_generation_configured: bool,
        llm_source: str,
    ) -> dict[str, Any]:
        return {
            "baseUrl": base_url,
            "modelName": model_name,
            "promptAssemblyMode": normalize_llm_prompt_assembly_mode(prompt_assembly_mode),
            "savedApiKeyConfigured": bool(saved_api_key_configured),
            "savedApiKeyPreview": saved_api_key_preview,
            "llmConfigured": bool(llm_configured),
            "storyGenerationConfigured": bool(story_generation_configured),
            "llmSource": llm_source,
        }

    def get_effective_llm_service_config(
        self,
        *,
        auth_store: AuthStore | None = None,
        user_id: str | None = None,
    ) -> LocalServiceConfig | None:
        user_cfg = self._get_saved_user_service_config(auth_store=auth_store, user_id=user_id, service_kind="llm")
        if self._service_config_is_available(user_cfg):
            return user_cfg
        if current_runtime_features().auth_enabled:
            return None
        saved = self.sys.g.global_llm_settings
        global_cfg = None if saved is None else self._saved_service_config(base_url=saved.base_url, model_name=saved.model_name, api_key=saved.api_key)
        if self._service_config_is_available(global_cfg):
            return global_cfg
        return current_env_llm_qa_service_config()

    def get_effective_story_generator_service_config(
        self,
        *,
        auth_store: AuthStore | None = None,
        user_id: str | None = None,
    ) -> LocalServiceConfig | None:
        user_cfg = self._get_saved_user_service_config(auth_store=auth_store, user_id=user_id, service_kind="llm")
        if self._service_config_is_available(user_cfg):
            return user_cfg
        if current_runtime_features().auth_enabled:
            return None
        saved = self.sys.g.global_llm_settings
        global_cfg = None if saved is None else self._saved_service_config(base_url=saved.base_url, model_name=saved.model_name, api_key=saved.api_key)
        if self._service_config_is_available(global_cfg):
            return global_cfg
        return current_env_story_generator_service_config() or current_env_llm_qa_service_config()

    def get_effective_llm_prompt_assembly_mode(
        self,
        *,
        auth_store: AuthStore | None = None,
        user_id: str | None = None,
    ) -> str:
        if auth_store is not None and str(user_id or "").strip():
            saved = auth_store.get_user_service_config(str(user_id), service_kind="llm")
            if saved is not None:
                return normalize_llm_prompt_assembly_mode(saved.prompt_assembly_mode)
        if current_runtime_features().auth_enabled:
            return DEFAULT_LLM_PROMPT_ASSEMBLY_MODE
        saved = self.sys.g.global_llm_settings
        if saved is not None:
            return normalize_llm_prompt_assembly_mode(saved.prompt_assembly_mode)
        return DEFAULT_LLM_PROMPT_ASSEMBLY_MODE

    @staticmethod
    def _build_user_concat_message(
        *,
        prompt: str,
        sections: Sequence[tuple[str, str | None]],
    ) -> str:
        normalized_sections = [
            (str(title).strip(), str(content).strip())
            for title, content in sections
            if str(title).strip() and str(content or "").strip()
        ]
        if not normalized_sections:
            return str(prompt).strip()

        parts = [
            "以下内容是系统规则与上下文，请把它们和用户问题一起视为本次输入，严格依据这些信息回答。",
        ]
        for title, content in normalized_sections:
            parts.append(f"[{title}]")
            parts.append(content)
        parts.append("[用户问题]")
        parts.append(str(prompt).strip())
        return "\n".join(parts).strip()

    def _build_single_turn_llm_messages(
        self,
        *,
        user_prompt: str,
        system_prompt: str | None = None,
        prompt_assembly_mode: str,
    ) -> list[dict[str, str]]:
        prompt = str(user_prompt or "").strip()
        if not prompt:
            raise PreconditionFailure("LLM user_prompt must be non-empty")

        resolved_mode = normalize_llm_prompt_assembly_mode(prompt_assembly_mode)
        if resolved_mode == "user_concat":
            return [
                {
                    "role": "user",
                    "content": self._build_user_concat_message(
                        prompt=prompt,
                        sections=[("系统信息", system_prompt)],
                    ),
                }
            ]

        messages: list[dict[str, str]] = []
        if str(system_prompt or "").strip():
            messages.append({"role": "system", "content": str(system_prompt).strip()})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _build_project_llm_messages(
        self,
        *,
        user_prompt: str,
        context_text: str,
        system_prompt: str | None = None,
        supplemental_context: str | None = None,
        prompt_assembly_mode: str,
    ) -> list[dict[str, str]]:
        prompt = str(user_prompt or "").strip()
        if not prompt:
            raise PreconditionFailure("LLM user_prompt must be non-empty")

        resolved_mode = normalize_llm_prompt_assembly_mode(prompt_assembly_mode)
        if resolved_mode == "user_concat":
            return [
                {
                    "role": "user",
                    "content": self._build_user_concat_message(
                        prompt=prompt,
                        sections=[
                            ("系统信息", self._project_llm_system_instruction()),
                            ("项目上下文", context_text),
                            ("补充上下文", supplemental_context),
                            ("页面附加规则", system_prompt),
                        ],
                    ),
                }
            ]

        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": self._project_llm_system_instruction(),
            },
            {"role": "system", "content": context_text},
        ]
        if str(supplemental_context or "").strip():
            messages.append({"role": "system", "content": str(supplemental_context).strip()})
        if str(system_prompt or "").strip():
            messages.append({"role": "system", "content": str(system_prompt).strip()})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _build_llm_chat_completion_transport(
        self,
        *,
        messages: Sequence[dict[str, str]],
        model_name: str | None = None,
        temperature: float | None = None,
        stream: bool = False,
        auth_store: AuthStore | None = None,
        user_id: str | None = None,
    ) -> tuple[str, dict[str, object], str | None]:
        cfg = self.get_effective_llm_service_config(auth_store=auth_store, user_id=user_id)
        if cfg is None:
            raise PreconditionFailure("LLM service is not configured")

        normalized_messages = self._normalize_llm_messages(messages)
        url = self._resolve_local_service_url(cfg, default_path="/chat/completions")
        payload: dict[str, object] = {
            "model": str(model_name or cfg.model or self._default_global_llm_model_name()).strip(),
            "messages": normalized_messages,
        }
        if stream:
            payload["stream"] = True
        if temperature is not None:
            payload["temperature"] = float(temperature)
        return url, payload, cfg.api_key

    @staticmethod
    def _project_llm_debug_target(
        *,
        recall_point_id: RecallPointId | None,
        learning_task_node_id: LearningTaskNodeId | None,
        learning_object_node_id: LearningObjectNodeId | None,
    ) -> tuple[str, str | None]:
        if recall_point_id is not None:
            return "recall", str(recall_point_id)
        if learning_task_node_id is not None:
            return "task", str(learning_task_node_id)
        if learning_object_node_id is not None:
            return "object", str(learning_object_node_id)
        return "project", None

    def _record_project_llm_debug(
        self,
        *,
        project_id: ProjectId,
        request_model_name: str | None,
        url: str,
        payload: dict[str, object],
        response_content: str,
        error_message: str | None,
        recall_point_id: RecallPointId | None,
        learning_task_node_id: LearningTaskNodeId | None,
        learning_object_node_id: LearningObjectNodeId | None,
    ) -> None:
        target_kind, target_id = self._project_llm_debug_target(
            recall_point_id=recall_point_id,
            learning_task_node_id=learning_task_node_id,
            learning_object_node_id=learning_object_node_id,
        )
        raw_messages = payload.get("messages")
        messages: list[dict[str, str]] = []
        if isinstance(raw_messages, list):
            for item in raw_messages:
                if not isinstance(item, dict):
                    continue
                role = str(item.get("role") or "").strip()
                if not role:
                    continue
                messages.append(
                    {
                        "role": role,
                        "content": str(item.get("content") or ""),
                    }
                )

        entry = {
            "recordedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "projectId": str(project_id),
            "requestModelName": None if request_model_name is None else str(request_model_name).strip() or None,
            "resolvedModelName": str(payload.get("model") or "").strip(),
            "temperature": None if payload.get("temperature") is None else float(payload["temperature"]),
            "stream": bool(payload.get("stream", False)),
            "serviceUrl": str(url),
            "contextTargetKind": target_kind,
            "contextTargetId": target_id,
            "messages": messages,
            "responseContent": str(response_content or ""),
            "errorMessage": None if error_message is None else str(error_message),
        }
        with self._project_llm_debug_lock:
            self._latest_project_llm_debug_by_project[id_canonical_text(project_id)] = entry

    def get_latest_project_llm_debug(self, project_id: ProjectId) -> dict[str, Any] | None:
        self._get_project_title(project_id)
        with self._project_llm_debug_lock:
            entry = self._latest_project_llm_debug_by_project.get(id_canonical_text(project_id))
            return None if entry is None else dict(entry)

    def request_llm_chat_completion(
        self,
        *,
        messages: Sequence[dict[str, str]],
        model_name: str | None = None,
        temperature: float | None = None,
        timeout_sec: float = 60.0,
        auth_store: AuthStore | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        url, payload, api_key = self._build_llm_chat_completion_transport(
            messages=messages,
            model_name=model_name,
            temperature=temperature,
            stream=False,
            auth_store=auth_store,
            user_id=user_id,
        )
        return self._http_post_json(
            url=url,
            payload=payload,
            api_key=api_key,
            timeout_sec=float(timeout_sec),
        )

    def request_llm_chat_completion_raw(
        self,
        *,
        messages: Sequence[dict[str, Any]],
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: object | None = None,
        parallel_tool_calls: bool | None = None,
        response_format: dict[str, Any] | None = None,
        model_name: str | None = None,
        temperature: float | None = None,
        timeout_sec: float = 60.0,
        auth_store: AuthStore | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        cfg = self.get_effective_llm_service_config(auth_store=auth_store, user_id=user_id)
        if cfg is None:
            raise PreconditionFailure("LLM service is not configured")

        if not messages:
            raise PreconditionFailure("LLM request must include at least one message")

        normalized_messages: list[dict[str, Any]] = []
        for message in messages:
            if not isinstance(message, dict):
                raise PreconditionFailure("LLM message must be an object")
            role = str(message.get("role", "")).strip()
            if role not in {"system", "user", "assistant", "tool"}:
                raise PreconditionFailure("LLM message.role must be one of system/user/assistant/tool")
            normalized_messages.append(dict(message))

        url = self._resolve_local_service_url(cfg, default_path="/chat/completions")
        payload: dict[str, object] = {
            "model": str(model_name or cfg.model or self._default_global_llm_model_name()).strip(),
            "messages": normalized_messages,
        }
        if tools is not None:
            payload["tools"] = list(tools)
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if parallel_tool_calls is not None:
            payload["parallel_tool_calls"] = bool(parallel_tool_calls)
        if response_format is not None:
            payload["response_format"] = dict(response_format)
        if temperature is not None:
            payload["temperature"] = float(temperature)

        return self._http_post_json(
            url=url,
            payload=payload,
            api_key=cfg.api_key,
            timeout_sec=float(timeout_sec),
        )

    def request_llm_chat_completion_stream_text(
        self,
        *,
        messages: Sequence[dict[str, str]],
        model_name: str | None = None,
        temperature: float | None = None,
        timeout_sec: float = 60.0,
        auth_store: AuthStore | None = None,
        user_id: str | None = None,
    ) -> Iterator[str]:
        url, payload, api_key = self._build_llm_chat_completion_transport(
            messages=messages,
            model_name=model_name,
            temperature=temperature,
            stream=False,
            auth_store=auth_store,
            user_id=user_id,
        )
        yield from self._http_post_json_stream_text_chunks(
            url=url,
            payload=payload,
            api_key=api_key,
            timeout_sec=float(timeout_sec),
        )

    def request_llm_text(
        self,
        *,
        user_prompt: str,
        system_prompt: str | None = None,
        model_name: str | None = None,
        temperature: float | None = None,
        timeout_sec: float = 60.0,
        auth_store: AuthStore | None = None,
        user_id: str | None = None,
    ) -> str:
        messages = self._build_single_turn_llm_messages(
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            prompt_assembly_mode=self.get_effective_llm_prompt_assembly_mode(
                auth_store=auth_store,
                user_id=user_id,
            ),
        )
        response = self.request_llm_chat_completion(
            messages=messages,
            model_name=model_name,
            temperature=temperature,
            timeout_sec=timeout_sec,
            auth_store=auth_store,
            user_id=user_id,
        )
        return self._extract_chat_completion_text(response)

    @staticmethod
    def _rich_content_to_plain_text(content: RichContent) -> str:
        parts: list[str] = []
        for block in content:
            if getattr(block, "text", None):
                parts.append(str(block.text).strip())
                continue
            asset_id = getattr(block, "asset_id", None)
            if asset_id is not None:
                parts.append(f"[image:{asset_id}]")
        return "\n".join(part for part in parts if part).strip()

    @staticmethod
    def _truncate_for_llm_context(text: str, *, max_chars: int = 800) -> str:
        normalized = str(text or "").strip()
        if len(normalized) <= max_chars:
            return normalized
        return normalized[: max_chars - 1].rstrip() + "…"

    def _get_project_title(self, project_id: ProjectId) -> str:
        sql_store = self._sql_store()
        if sql_store is not None:
            for project in sql_store.list_projects_metadata(active_only=False):
                if id_canonical_text(project.project_id) == id_canonical_text(project_id):
                    return str(project.title)
            raise NotFound(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            return str(self.sys.project_repo.get(s, project_id).title)
        finally:
            self.sys.rollback(s)

    def _get_active_project_metadata(self, project_id: ProjectId) -> Project:
        sql_store = self._sql_store()
        if sql_store is not None:
            for project in sql_store.list_projects_metadata(active_only=True):
                if id_canonical_text(project.project_id) == id_canonical_text(project_id):
                    return project
            raise NotFound(project_id)

        project_store = self.sys.g.projects.get(id_canonical_text(project_id))
        if project_store is None or project_store.project is None or project_store.project.state != ProjectState.ACTIVE:
            raise NotFound(project_id)
        return project_store.project

    def _get_project_store(self, project_id: ProjectId):
        project_store = self.sys.g.projects.get(id_canonical_text(project_id))
        if project_store is None or project_store.project is None:
            raise NotFound(project_id)
        return project_store

    @staticmethod
    def _copy_project_store(project_store: ProjectStore) -> ProjectStore:
        copied = ProjectStore(project=project_store.project)
        copied.project_storage_config = project_store.project_storage_config
        copied.project_material_source_binding = project_store.project_material_source_binding
        copied.project_config = project_store.project_config
        copied.material_allowlist = project_store.material_allowlist
        copied.study_materials = dict(project_store.study_materials)
        copied.study_materials_initialized = bool(project_store.study_materials_initialized)
        copied.subject_material_link = project_store.subject_material_link
        copied.media_assets = dict(project_store.media_assets)
        copied.audit_log_events = dict(project_store.audit_log_events)
        copied.instances = dict(project_store.instances)
        copied.instance_media_bindings = dict(project_store.instance_media_bindings)
        copied.video_watch_progress = dict(project_store.video_watch_progress)
        copied.learning_object_nodes = dict(project_store.learning_object_nodes)
        copied.recall_points = dict(project_store.recall_points)
        copied.recall_point_review_records = dict(project_store.recall_point_review_records)
        copied.learning_tasks = dict(project_store.learning_tasks)
        copied.learning_task_nodes = dict(project_store.learning_task_nodes)
        copied.range_snapshots = dict(project_store.range_snapshots)
        copied.asr_artifacts = dict(project_store.asr_artifacts)
        copied.review_tasks = dict(project_store.review_tasks)
        copied.convergences = dict(project_store.convergences)
        copied.review_chains = dict(project_store.review_chains)
        copied.review_task_queue = project_store.review_task_queue
        copied.layers = dict(project_store.layers)
        copied.layers_by_index = dict(project_store.layers_by_index)
        copied.entry_regs = dict(project_store.entry_regs)
        copied.aggregation_queues = dict(project_store.aggregation_queues)
        copied.aggregation_events = dict(project_store.aggregation_events)
        return copied

    def _new_audit_event(
        self,
        project_id: ProjectId,
        *,
        kind: AuditEventKind,
        api_name: str,
        payload: dict[str, object],
        occurred_at: Timestamp | None = None,
    ) -> AuditLogEvent:
        event = AuditLogEvent(
            project_id=project_id,
            event_id=self.idgen.new_audit_event_id(project_id),
            occurred_at=occurred_at or now_utc_ms(),
            kind=kind,
            api_name=api_name,
            result=AuditResultCode.OK,
            payload=json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        )
        event.validate_write_time()
        return event

    def _deleted_project_store(self, project_store: ProjectStore) -> ProjectStore:
        project = project_store.project
        if project is None:
            raise NotFound("project")
        if project.state != ProjectState.ACTIVE:
            raise PreconditionFailure("Project must be ACTIVE to delete")
        deleted_at = now_utc_ms()
        deleted_project = replace(project, state=ProjectState.DELETED, deleted_at=deleted_at)
        deleted_project.validate_write_time()
        next_store = ProjectStore(project=deleted_project)
        event = self._new_audit_event(
            project.project_id,
            kind=AuditEventKind.PROJECT_DELETED,
            api_name="delete_project",
            payload={"projectId": str(project.project_id)},
            occurred_at=deleted_at,
        )
        next_store.audit_log_events = {id_canonical_text(event.event_id): event}
        return next_store

    def _get_subject_material_link(self, project_id: ProjectId) -> SubjectMaterialLink | None:
        project_store = self._get_project_store(project_id)
        return getattr(project_store, "subject_material_link", None)

    @staticmethod
    def _material_internal_project_key(material: StudyMaterial) -> ProjectId | None:
        return material.internal_project_id

    @staticmethod
    def _scoped_project_id_for_sequence(n: int) -> ProjectId:
        return ProjectId(f"proj_{int(n):06d}")

    @staticmethod
    def _parse_scoped_project_sequence(project_id: ProjectId | None) -> int:
        raw = str(project_id or "")
        if not raw.startswith("proj_"):
            return 0
        suffix = raw[5:]
        return int(suffix) if suffix.isdigit() else 0

    def _next_scoped_project_id(self, subject: Project, materials: Sequence[StudyMaterial]) -> tuple[ProjectId, int]:
        current = int(getattr(subject, "project_sequence", 0) or 0)
        current = max(current, self._parse_scoped_project_sequence(subject.project_id))
        for material in materials:
            current = max(current, self._parse_scoped_project_sequence(material.scoped_project_id))
        next_sequence = current + 1
        return self._scoped_project_id_for_sequence(next_sequence), next_sequence

    def resolve_scoped_project_internal_key(self, subject_id: ProjectId, scoped_project_id: ProjectId) -> ProjectId:
        self._require_subject_root_project(subject_id)
        for material in self._list_subject_materials_from_store(subject_id):
            if material.scoped_project_id is None:
                continue
            if id_canonical_text(material.scoped_project_id) != id_canonical_text(scoped_project_id):
                continue
            internal_key = self._material_internal_project_key(material)
            if internal_key is None:
                raise PreconditionFailure("scoped project missing internal storage key")
            return internal_key
        raise NotFound(scoped_project_id)

    def get_scoped_subject_context_for_project(self, project_id: ProjectId, *, public_project_id: ProjectId) -> dict[str, object]:
        payload = self.get_subject_context(project_id)
        payload["current_scoped_project_id"] = public_project_id
        payload["current_internal_project_id"] = project_id
        return payload

    def _resolve_subject_id(self, project_id: ProjectId) -> ProjectId:
        link = self._get_subject_material_link(project_id)
        return link.subject_id if link is not None else project_id

    def is_subject_root_project(self, project_id: ProjectId) -> bool:
        try:
            project_store = self._get_project_store(project_id)
        except NotFound:
            return False
        return (
            self._get_subject_material_link(project_id) is None
            and (
                bool(getattr(project_store, "study_materials_initialized", False))
                or bool(getattr(project_store, "study_materials", {}))
            )
        )

    def require_material_project(self, project_id: ProjectId) -> None:
        if self.is_subject_root_project(project_id):
            raise PreconditionFailure("subject id is not a project id")

    def _require_subject_root_project(self, project_id: ProjectId) -> None:
        self._get_active_project_metadata(project_id)
        if not self.is_subject_root_project(project_id):
            raise PreconditionFailure("project id is not a subject")

    def _list_subject_materials_from_store(self, subject_id: ProjectId) -> Tuple[StudyMaterial, ...]:
        project_store = self._get_project_store(subject_id)
        study_materials = tuple(getattr(project_store, "study_materials", {}).values())
        if study_materials or getattr(project_store, "study_materials_initialized", False):
            return tuple(
                sorted(
                    study_materials,
                    key=lambda item: (
                        item.created_at,
                        item.material_id,
                    ),
                )
            )
        return tuple()

    def _find_subject_material(self, subject_id: ProjectId, material_id: str) -> StudyMaterial:
        normalized_material_id = str(material_id or "").strip()
        if not normalized_material_id:
            raise NotFound("material")
        for item in self._list_subject_materials_from_store(subject_id):
            if item.material_id == normalized_material_id:
                return item
        raise NotFound("material")

    def _resolve_current_material_for_project(self, project_id: ProjectId, subject_id: ProjectId) -> StudyMaterial:
        material_link = self._get_subject_material_link(project_id)
        if material_link is None:
            raise PreconditionFailure("project id is not a subject material project")
        for item in self._list_subject_materials_from_store(subject_id):
            if item.material_id == material_link.material_id:
                return item
        raise NotFound("subject material")

    @staticmethod
    def _default_material_title_for_type(material_type: StudyMaterialType) -> str:
        if material_type == StudyMaterialType.BOOK:
            return "书本材料"
        if material_type == StudyMaterialType.LOOSE_POINTS:
            return "零散知识"
        return "网课材料"

    @staticmethod
    def _project_options_for_material_type(
        material_type: StudyMaterialType,
    ) -> tuple[MaterialSourceKind, ProjectType]:
        if material_type == StudyMaterialType.BOOK:
            return MaterialSourceKind.MANUAL, ProjectType.BOOK
        if material_type == StudyMaterialType.LOOSE_POINTS:
            return MaterialSourceKind.MANUAL, ProjectType.LOOSE_POINTS
        return MaterialSourceKind.SERVER_FS, ProjectType.COURSE

    @staticmethod
    def _new_study_material_id(material_type: StudyMaterialType) -> str:
        return f"{material_type.value.lower()}_{secrets.token_hex(4)}"

    def _format_recall_point_for_llm_context(self, recall_point: RecallPoint, *, index: int | None = None) -> str:
        header = f"Recall Point {index}" if index is not None else "Recall Point"
        anchor_line = (
            "Anchor: none"
            if recall_point.anchor is None
            else f"Anchor: instance={recall_point.anchor.instance_id}, position={recall_point.anchor.position}"
        )
        lines = [
            f"{header}: {recall_point.recall_point_id}",
            f"Question: {self._truncate_for_llm_context(self._rich_content_to_plain_text(recall_point.question))}",
            f"Answer: {self._truncate_for_llm_context(self._rich_content_to_plain_text(recall_point.answer))}",
            anchor_line,
        ]
        if recall_point.insights:
            for insight_index, insight in enumerate(recall_point.insights, start=1):
                insight_text = self._truncate_for_llm_context(self._rich_content_to_plain_text(insight), max_chars=400)
                if insight_text:
                    lines.append(f"Insight {insight_index}: {insight_text}")
        return "\n".join(lines)

    def _build_project_llm_context_text(
        self,
        *,
        project_id: ProjectId,
        recall_point_id: RecallPointId | None = None,
        learning_task_node_id: LearningTaskNodeId | None = None,
        learning_object_node_id: LearningObjectNodeId | None = None,
        max_recall_points: int = 8,
    ) -> str:
        supplied_targets = [
            recall_point_id is not None,
            learning_task_node_id is not None,
            learning_object_node_id is not None,
        ]
        if sum(1 for item in supplied_targets if item) > 1:
            raise PreconditionFailure("Only one of recallPointId, learningTaskNodeId, learningObjectNodeId may be provided")

        project_title = self._get_project_title(project_id)
        lines = [
            "Project Context",
            f"Project title: {project_title}",
        ]

        if recall_point_id is not None:
            recall_point = self.get_recall_point(project_id, recall_point_id)
            lines.append("Context target: recall point")
            lines.append(self._format_recall_point_for_llm_context(recall_point))
            return "\n".join(lines)

        if learning_task_node_id is not None:
            node = self.get_learning_task_node(project_id, learning_task_node_id)
            recall_points = [
                item for item in self.list_recall_points_by_learning_task_node(project_id, learning_task_node_id) if item.state == RecallPointState.ACTIVE
            ]
            limited = recall_points[: max_recall_points]
            lines.append("Context target: learning task node")
            lines.append(f"Node title: {getattr(node, 'title', '')}")
            lines.append(f"Node id: {learning_task_node_id}")
            lines.append(f"Active recall points included: {len(limited)} / {len(recall_points)}")
            if limited:
                lines.append(
                    "Context availability: current node content is available through the included recall points. "
                    "Answer from these recall points first and do not claim the current node content is missing."
                )
                lines.append(
                    "Important instruction: treat the included recall points as the current node's concrete content. "
                    "Do not ask the user to provide the topic, keywords, or summary again."
                )
            else:
                lines.append(
                    "Context availability: no active recall points are currently attached to this learning task node."
                )
            for index, recall_point in enumerate(limited, start=1):
                lines.append(self._format_recall_point_for_llm_context(recall_point, index=index))
            return "\n".join(lines)

        if learning_object_node_id is not None:
            node = self.get_learning_object_node(project_id, learning_object_node_id)
            recall_points = [
                item for item in self.list_recall_points_by_learning_object_node(project_id, learning_object_node_id) if item.state == RecallPointState.ACTIVE
            ]
            limited = recall_points[: max_recall_points]
            lines.append("Context target: learning object node")
            lines.append(f"Node title: {getattr(node, 'title', '')}")
            lines.append(f"Node id: {learning_object_node_id}")
            relative_path = getattr(node, "relative_path", None)
            if relative_path is not None:
                lines.append(f"Relative path: {relative_path}")
            lines.append(f"Active recall points included: {len(limited)} / {len(recall_points)}")
            if limited:
                lines.append(
                    "Context availability: current node content is available through the included recall points. "
                    "Answer from these recall points first and do not claim the current node content is missing."
                )
                lines.append(
                    "Important instruction: treat the included recall points as the current node's concrete content. "
                    "Do not ask the user to provide the topic, keywords, or summary again."
                )
            else:
                lines.append(
                    "Context availability: no active recall points are currently attached to this learning object node."
                )
            for index, recall_point in enumerate(limited, start=1):
                lines.append(self._format_recall_point_for_llm_context(recall_point, index=index))
            return "\n".join(lines)

        lines.append("Context target: project only")
        return "\n".join(lines)

    @staticmethod
    def _project_llm_system_instruction() -> str:
        return (
            "你是 LearningPyramid 项目里的 AI 学习助手。"
            "请优先使用系统消息中提供的项目上下文、当前节点标题、复述点问答、理解记录和字幕片段作答。"
            "只要系统消息里已经给出了当前节点标题、复述点或字幕内容，就视为用户已经提供了当前节点内容；"
            "不要回答“未提供当前节点内容/主题/关键词”，也不要要求用户重复粘贴这些信息。"
            "只有当系统明确说明当前节点没有任何复述点或其他上下文时，才可以向用户索取补充信息。"
            "如果当前节点已有复述点，那么这些复述点就是当前节点的具体内容，应直接据此完成总结、出题、助记等请求。"
            "不要编造项目内不存在的事实。请优先使用简体中文回答。"
        )

    def request_project_llm_text(
        self,
        *,
        project_id: ProjectId,
        user_prompt: str,
        system_prompt: str | None = None,
        supplemental_context: str | None = None,
        model_name: str | None = None,
        temperature: float | None = None,
        recall_point_id: RecallPointId | None = None,
        learning_task_node_id: LearningTaskNodeId | None = None,
        learning_object_node_id: LearningObjectNodeId | None = None,
        timeout_sec: float = 60.0,
        auth_store: AuthStore | None = None,
        user_id: str | None = None,
    ) -> str:
        prompt = str(user_prompt or "").strip()
        if not prompt:
            raise PreconditionFailure("LLM user_prompt must be non-empty")

        context_text = self._build_project_llm_context_text(
            project_id=project_id,
            recall_point_id=recall_point_id,
            learning_task_node_id=learning_task_node_id,
            learning_object_node_id=learning_object_node_id,
        )
        messages = self._build_project_llm_messages(
            user_prompt=prompt,
            context_text=context_text,
            system_prompt=system_prompt,
            supplemental_context=supplemental_context,
            prompt_assembly_mode=self.get_effective_llm_prompt_assembly_mode(
                auth_store=auth_store,
                user_id=user_id,
            ),
        )

        url, payload, api_key = self._build_llm_chat_completion_transport(
            messages=messages,
            model_name=model_name,
            temperature=temperature,
            stream=False,
            auth_store=auth_store,
            user_id=user_id,
        )
        response_content = ""
        error_message: str | None = None
        try:
            response = self._http_post_json(
                url=url,
                payload=payload,
                api_key=api_key,
                timeout_sec=float(timeout_sec),
            )
            response_content = self._extract_chat_completion_text(response)
            return response_content
        except BaseException as exc:
            error_message = str(exc)
            raise
        finally:
            self._record_project_llm_debug(
                project_id=project_id,
                request_model_name=model_name,
                url=url,
                payload=payload,
                response_content=response_content,
                error_message=error_message,
                recall_point_id=recall_point_id,
                learning_task_node_id=learning_task_node_id,
                learning_object_node_id=learning_object_node_id,
            )

    def request_project_llm_text_stream(
        self,
        *,
        project_id: ProjectId,
        user_prompt: str,
        system_prompt: str | None = None,
        supplemental_context: str | None = None,
        model_name: str | None = None,
        temperature: float | None = None,
        recall_point_id: RecallPointId | None = None,
        learning_task_node_id: LearningTaskNodeId | None = None,
        learning_object_node_id: LearningObjectNodeId | None = None,
        timeout_sec: float = 60.0,
        auth_store: AuthStore | None = None,
        user_id: str | None = None,
    ) -> Iterator[str]:
        prompt = str(user_prompt or "").strip()
        if not prompt:
            raise PreconditionFailure("LLM user_prompt must be non-empty")

        context_text = self._build_project_llm_context_text(
            project_id=project_id,
            recall_point_id=recall_point_id,
            learning_task_node_id=learning_task_node_id,
            learning_object_node_id=learning_object_node_id,
        )
        messages = self._build_project_llm_messages(
            user_prompt=prompt,
            context_text=context_text,
            system_prompt=system_prompt,
            supplemental_context=supplemental_context,
            prompt_assembly_mode=self.get_effective_llm_prompt_assembly_mode(
                auth_store=auth_store,
                user_id=user_id,
            ),
        )

        url, payload, api_key = self._build_llm_chat_completion_transport(
            messages=messages,
            model_name=model_name,
            temperature=temperature,
            stream=True,
            auth_store=auth_store,
            user_id=user_id,
        )
        chunks: list[str] = []
        error_message: str | None = None
        try:
            for chunk in self._http_post_json_stream_text_chunks(
                url=url,
                payload=payload,
                api_key=api_key,
                timeout_sec=float(timeout_sec),
            ):
                if chunk:
                    chunks.append(chunk)
                    yield chunk
        except BaseException as exc:
            error_message = str(exc)
            raise
        finally:
            self._record_project_llm_debug(
                project_id=project_id,
                request_model_name=model_name,
                url=url,
                payload=payload,
                response_content="".join(chunks),
                error_message=error_message,
                recall_point_id=recall_point_id,
                learning_task_node_id=learning_task_node_id,
                learning_object_node_id=learning_object_node_id,
            )

    def get_global_llm_status(self) -> dict[str, Any]:
        saved = self.sys.g.global_llm_settings
        env_llm_cfg = current_env_llm_qa_service_config()
        effective_llm_cfg = self.get_effective_llm_service_config()
        effective_story_cfg = self.get_effective_story_generator_service_config()

        if saved is not None:
            base_url = saved.base_url
            model_name = saved.model_name
        elif env_llm_cfg is not None:
            base_url = env_llm_cfg.base_url
            model_name = env_llm_cfg.model_name or self._default_global_llm_model_name()
        else:
            base_url = self._default_global_llm_base_url()
            model_name = self._default_global_llm_model_name()

        llm_source = "none"
        if saved is not None and self._service_config_is_available(
            self._saved_service_config(base_url=saved.base_url, model_name=saved.model_name, api_key=saved.api_key)
        ):
            llm_source = "global"
        elif self._service_config_is_available(env_llm_cfg):
            llm_source = "env"

        return {
            "baseUrl": base_url,
            "modelName": model_name,
            "promptAssemblyMode": (
                normalize_llm_prompt_assembly_mode(saved.prompt_assembly_mode)
                if saved is not None
                else DEFAULT_LLM_PROMPT_ASSEMBLY_MODE
            ),
            "savedApiKeyConfigured": bool(saved is not None and str(saved.api_key or "").strip()),
            "savedApiKeyPreview": self._mask_api_key(None if saved is None else saved.api_key),
            "llmConfigured": self._service_config_is_available(effective_llm_cfg),
            "storyGenerationConfigured": self._service_config_is_available(effective_story_cfg),
            "llmSource": llm_source,
        }

    def get_user_llm_status(
        self,
        *,
        auth_store: AuthStore | None,
        user_id: str | None,
    ) -> dict[str, Any]:
        auth_enabled = current_runtime_features().auth_enabled
        if auth_enabled and (auth_store is None or not str(user_id or "").strip()):
            return self._llm_status_payload(
                base_url="",
                model_name="",
                prompt_assembly_mode=DEFAULT_LLM_PROMPT_ASSEMBLY_MODE,
                saved_api_key_configured=False,
                saved_api_key_preview=None,
                llm_configured=False,
                story_generation_configured=False,
                llm_source="none",
            )
        if auth_store is None or not str(user_id or "").strip():
            return self.get_global_llm_status()

        saved = auth_store.get_user_service_config(str(user_id), service_kind="llm")
        saved_cfg = None if saved is None else self._saved_service_config(base_url=saved.base_url, model_name=saved.model_name, api_key=saved.api_key)
        if auth_enabled:
            return self._llm_status_payload(
                base_url="" if saved is None else saved.base_url,
                model_name="" if saved is None else saved.model_name,
                prompt_assembly_mode=DEFAULT_LLM_PROMPT_ASSEMBLY_MODE if saved is None else saved.prompt_assembly_mode,
                saved_api_key_configured=bool(saved is not None and str(saved.api_key or "").strip()),
                saved_api_key_preview=self._mask_api_key(None if saved is None else saved.api_key),
                llm_configured=self._service_config_is_available(saved_cfg),
                story_generation_configured=self._service_config_is_available(saved_cfg),
                llm_source="user" if self._service_config_is_available(saved_cfg) else "none",
            )

        global_saved = self.sys.g.global_llm_settings
        global_cfg = (
            None
            if global_saved is None
            else self._saved_service_config(base_url=global_saved.base_url, model_name=global_saved.model_name, api_key=global_saved.api_key)
        )
        env_llm_cfg = current_env_llm_qa_service_config()

        if saved is not None:
            base_url = saved.base_url
            model_name = saved.model_name
        elif self._service_config_is_available(global_cfg):
            assert global_saved is not None
            base_url = global_saved.base_url
            model_name = global_saved.model_name
        elif env_llm_cfg is not None:
            base_url = env_llm_cfg.base_url
            model_name = env_llm_cfg.model_name or self._default_global_llm_model_name()
        else:
            base_url = self._default_global_llm_base_url()
            model_name = self._default_global_llm_model_name()

        llm_source = "none"
        if self._service_config_is_available(saved_cfg):
            llm_source = "user"
        elif self._service_config_is_available(global_cfg):
            llm_source = "global"
        elif self._service_config_is_available(env_llm_cfg):
            llm_source = "env"

        return self._llm_status_payload(
            base_url=base_url,
            model_name=model_name,
            prompt_assembly_mode=(
                normalize_llm_prompt_assembly_mode(saved.prompt_assembly_mode)
                if saved is not None
                else (
                    normalize_llm_prompt_assembly_mode(global_saved.prompt_assembly_mode)
                    if global_saved is not None
                    else DEFAULT_LLM_PROMPT_ASSEMBLY_MODE
                )
            ),
            saved_api_key_configured=bool(saved is not None and str(saved.api_key or "").strip()),
            saved_api_key_preview=self._mask_api_key(None if saved is None else saved.api_key),
            llm_configured=self._service_config_is_available(
                self.get_effective_llm_service_config(auth_store=auth_store, user_id=user_id)
            ),
            story_generation_configured=self._service_config_is_available(
                self.get_effective_story_generator_service_config(auth_store=auth_store, user_id=user_id)
            ),
            llm_source=llm_source,
        )

    def get_user_asr_status(
        self,
        *,
        auth_store: AuthStore | None,
        user_id: str | None,
    ) -> dict[str, Any]:
        saved = None if auth_store is None or not str(user_id or "").strip() else auth_store.get_user_service_config(str(user_id), service_kind="asr")
        saved_cfg = None if saved is None else self._saved_service_config(base_url=saved.base_url, model_name=saved.model_name, api_key=saved.api_key)
        env_cfg = current_env_asr_service_config()

        if saved is not None:
            base_url = saved.base_url
            model_name = saved.model_name
        elif env_cfg is not None:
            base_url = env_cfg.base_url
            model_name = env_cfg.model_name or ""
        else:
            base_url = ""
            model_name = ""

        asr_source = "none"
        if self._service_config_is_available(saved_cfg):
            asr_source = "user"
        elif self._service_config_is_available(env_cfg):
            asr_source = "env"

        return {
            "baseUrl": base_url,
            "modelName": model_name,
            "savedApiKeyConfigured": bool(saved is not None and str(saved.api_key or "").strip()),
            "savedApiKeyPreview": self._mask_api_key(None if saved is None else saved.api_key),
            "asrConfigured": self._service_config_is_available(
                saved_cfg if self._service_config_is_available(saved_cfg) else env_cfg
            ),
            "asrSource": asr_source,
        }

    def update_global_llm_settings(
        self,
        *,
        base_url: str | None = None,
        model_name: str | None = None,
        api_key: str | None = None,
        prompt_assembly_mode: str | None = None,
        clear_api_key: bool = False,
    ) -> dict[str, Any]:
        if self.sys.g._write_lock_held:
            raise PreconditionFailure("Cannot update global LLM settings while another READ_WRITE session is open")

        self.sys.g._write_lock_held = True
        try:
            current = self.sys.g.global_llm_settings
            env_llm_cfg = current_env_llm_qa_service_config()

            resolved_base_url = str(base_url or "").strip()
            if not resolved_base_url:
                if current is not None:
                    resolved_base_url = current.base_url
                elif env_llm_cfg is not None:
                    resolved_base_url = env_llm_cfg.base_url
                else:
                    resolved_base_url = self._default_global_llm_base_url()

            resolved_model_name = str(model_name or "").strip()
            if not resolved_model_name:
                if current is not None:
                    resolved_model_name = current.model_name
                elif env_llm_cfg is not None and str(env_llm_cfg.model_name or "").strip():
                    resolved_model_name = str(env_llm_cfg.model_name).strip()
                else:
                    resolved_model_name = self._default_global_llm_model_name()

            incoming_api_key = str(api_key or "").strip()
            if clear_api_key:
                resolved_api_key: str | None = None
            elif incoming_api_key:
                resolved_api_key = incoming_api_key
            elif current is not None:
                resolved_api_key = current.api_key
            else:
                resolved_api_key = None

            current_prompt_assembly_mode = None if current is None else current.prompt_assembly_mode
            resolved_prompt_assembly_mode = normalize_llm_prompt_assembly_mode(
                current_prompt_assembly_mode if prompt_assembly_mode is None else prompt_assembly_mode
            )

            settings = GlobalLlmSettings(
                base_url=resolved_base_url,
                model_name=resolved_model_name,
                api_key=resolved_api_key,
                prompt_assembly_mode=resolved_prompt_assembly_mode,
                updated_at=now_utc_ms(),
            )
            settings.validate_write_time()
            self.sys.g.global_llm_settings = settings
            self.sys._persist_to_disk()
            return self.get_global_llm_status()
        finally:
            self.sys.g._write_lock_held = False

    def update_user_llm_settings(
        self,
        *,
        auth_store: AuthStore,
        user_id: str,
        base_url: str | None = None,
        model_name: str | None = None,
        api_key: str | None = None,
        prompt_assembly_mode: str | None = None,
        clear_api_key: bool = False,
    ) -> dict[str, Any]:
        current = auth_store.get_user_service_config(user_id, service_kind="llm")
        auth_enabled = current_runtime_features().auth_enabled
        global_saved = None if auth_enabled else self.sys.g.global_llm_settings
        env_llm_cfg = None if auth_enabled else current_env_llm_qa_service_config()

        resolved_base_url = str(base_url or "").strip()
        if not resolved_base_url:
            if current is not None:
                resolved_base_url = current.base_url
            elif global_saved is not None:
                resolved_base_url = global_saved.base_url
            elif env_llm_cfg is not None:
                resolved_base_url = env_llm_cfg.base_url
            else:
                raise PreconditionFailure("LLM base_url must be provided")

        resolved_model_name = str(model_name or "").strip()
        if not resolved_model_name:
            if current is not None and str(current.model_name or "").strip():
                resolved_model_name = current.model_name
            elif global_saved is not None and str(global_saved.model_name or "").strip():
                resolved_model_name = global_saved.model_name
            elif env_llm_cfg is not None and str(env_llm_cfg.model_name or "").strip():
                resolved_model_name = str(env_llm_cfg.model_name).strip()
            else:
                raise PreconditionFailure("LLM model_name must be provided")

        resolved_prompt_assembly_mode = normalize_llm_prompt_assembly_mode(
            prompt_assembly_mode
            if prompt_assembly_mode is not None
            else (
                current.prompt_assembly_mode
                if current is not None
                else (
                    global_saved.prompt_assembly_mode if global_saved is not None else DEFAULT_LLM_PROMPT_ASSEMBLY_MODE
                )
            )
        )

        auth_store.upsert_user_service_config(
            user_id,
            service_kind="llm",
            base_url=resolved_base_url,
            model_name=resolved_model_name,
            api_key=api_key,
            prompt_assembly_mode=resolved_prompt_assembly_mode,
            clear_api_key=clear_api_key,
        )
        return self.get_user_llm_status(auth_store=auth_store, user_id=user_id)

    def update_user_asr_settings(
        self,
        *,
        auth_store: AuthStore,
        user_id: str,
        base_url: str | None = None,
        model_name: str | None = None,
        api_key: str | None = None,
        clear_api_key: bool = False,
    ) -> dict[str, Any]:
        current = auth_store.get_user_service_config(user_id, service_kind="asr")
        env_cfg = current_env_asr_service_config()

        resolved_base_url = str(base_url or "").strip()
        if not resolved_base_url:
            if current is not None:
                resolved_base_url = current.base_url
            elif env_cfg is not None:
                resolved_base_url = env_cfg.base_url
            else:
                raise PreconditionFailure("ASR base_url must be provided")

        resolved_model_name = str(model_name or "").strip()
        if not resolved_model_name:
            if current is not None and str(current.model_name or "").strip():
                resolved_model_name = current.model_name
            elif env_cfg is not None and str(env_cfg.model_name or "").strip():
                resolved_model_name = str(env_cfg.model_name).strip()
            else:
                resolved_model_name = ""

        auth_store.upsert_user_service_config(
            user_id,
            service_kind="asr",
            base_url=resolved_base_url,
            model_name=resolved_model_name,
            api_key=api_key,
            clear_api_key=clear_api_key,
        )
        return self.get_user_asr_status(auth_store=auth_store, user_id=user_id)

    @staticmethod
    def _cloud_account_to_dto(account) -> dict[str, Any]:
        return {
            "accountId": account.account_id,
            "provider": account.provider,
            "providerUserId": account.provider_user_id,
            "displayName": account.display_name,
            "avatarUrl": account.avatar_url,
            "expiresAt": account.expires_at,
            "scope": account.scope,
            "meta": dict(account.meta),
            "createdAt": account.created_at,
            "updatedAt": account.updated_at,
            "disabledAt": account.disabled_at,
        }

    def list_user_cloud_accounts(
        self,
        *,
        auth_store: AuthStore,
        user_id: str,
        provider: str = BAIDU_NETDISK_PROVIDER,
    ) -> list[dict[str, Any]]:
        return [
            self._cloud_account_to_dto(item)
            for item in auth_store.list_user_cloud_accounts(user_id, provider=provider, include_disabled=False)
        ]

    def begin_baidu_netdisk_connect(self, *, user_id: str) -> dict[str, str]:
        self._baidu_netdisk_client.require_enabled()
        state = self._new_cloud_oauth_state(user_id=str(user_id), provider=BAIDU_NETDISK_PROVIDER)
        return {
            "provider": BAIDU_NETDISK_PROVIDER,
            "authorizeUrl": self._baidu_netdisk_client.build_authorize_url(state=state),
            "state": state,
        }

    def complete_baidu_netdisk_connect(
        self,
        *,
        auth_store: AuthStore,
        user_id: str,
        code: str,
        state: str,
    ) -> dict[str, Any]:
        payload = self._consume_cloud_oauth_state(state)
        if payload.get("provider") != BAIDU_NETDISK_PROVIDER or payload.get("user_id") != str(user_id):
            raise PreconditionFailure("云账号授权状态与当前用户不匹配")
        try:
            token_bundle = self._baidu_netdisk_client.exchange_code(code)
            profile = self._baidu_netdisk_client.get_account_profile(token_bundle.access_token)
        except BaiduNetdiskApiError as exc:
            self._raise_baidu_netdisk_error(exc)
        account = auth_store.upsert_user_cloud_account(
            user_id=str(user_id),
            provider=BAIDU_NETDISK_PROVIDER,
            provider_user_id=profile.provider_user_id,
            display_name=profile.display_name,
            avatar_url=profile.avatar_url,
            access_token_ciphertext=encrypt_secret_value(token_bundle.access_token),
            refresh_token_ciphertext=encrypt_secret_value(token_bundle.refresh_token),
            expires_at=token_bundle.expires_at,
            scope=token_bundle.scope,
            meta=profile.meta,
        )
        return self._cloud_account_to_dto(account)

    def disable_baidu_netdisk_account(
        self,
        *,
        auth_store: AuthStore,
        user_id: str,
        account_id: str,
    ) -> None:
        auth_store.disable_user_cloud_account(user_id, account_id=account_id, provider=BAIDU_NETDISK_PROVIDER)

    def list_baidu_netdisk_files(
        self,
        *,
        auth_store: AuthStore,
        user_id: str,
        account_id: str,
        dir_path: str = "/",
        page: int = 1,
        limit: int = 200,
    ) -> dict[str, Any]:
        auth_store.get_user_cloud_account(user_id, account_id=account_id, provider=BAIDU_NETDISK_PROVIDER)
        try:
            items, has_more = self._instance_media_service().list_baidu_files(
                auth_store=auth_store,
                account_id=account_id,
                dir_path=dir_path,
                page=page,
                limit=limit,
            )
        except BaiduNetdiskApiError as exc:
            self._raise_baidu_netdisk_error(exc)
        return {
            "accountId": account_id,
            "dirPath": dir_path,
            "page": int(page),
            "limit": int(limit),
            "hasMore": bool(has_more),
            "items": [
                {
                    "fileId": item.file_id,
                    "path": item.path,
                    "name": item.name,
                    "isDir": item.is_dir,
                    "sizeBytes": item.size_bytes,
                    "mimeType": item.mime_type,
                    "durationMs": item.duration_ms,
                    "category": item.category,
                }
                for item in items
            ],
        }

    def import_learning_objects_from_baidu_netdisk(
        self,
        project_id: ProjectId,
        *,
        auth_store: AuthStore,
        user_id: str,
        account_id: str,
        items: Sequence[dict[str, Any]],
    ) -> dict[str, object]:
        account = auth_store.get_user_cloud_account(user_id, account_id=account_id, provider=BAIDU_NETDISK_PROVIDER)
        normalized_items: list[dict[str, Any]] = []
        for raw_item in items:
            row = dict(raw_item)
            remote_path = str(row.get("path") or "").strip()
            if not remote_path or not remote_path.startswith("/"):
                raise PreconditionFailure("百度网盘导入项缺少合法 path")
            if bool(row.get("isDir")):
                raise PreconditionFailure("一期仅支持导入百度网盘视频文件，不支持直接导入文件夹")
            file_id = str(row.get("fileId") or "").strip()
            if not file_id:
                raise PreconditionFailure("百度网盘导入项缺少 fileId")
            normalized_items.append(
                {
                    "fileId": file_id,
                    "path": remote_path,
                    "name": str(row.get("name") or PurePosixPath(remote_path).name).strip() or file_id,
                    "mimeType": None if row.get("mimeType") is None else str(row.get("mimeType")),
                    "sizeBytes": None if row.get("sizeBytes") is None else int(row.get("sizeBytes")),
                    "durationMs": None if row.get("durationMs") is None else int(row.get("durationMs")),
                }
            )
        if not normalized_items:
            raise PreconditionFailure("请选择至少一个百度网盘视频文件")

        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            if self._project_type_in_session(s) != ProjectType.COURSE:
                raise PreconditionFailure("import_learning_objects_from_baidu_netdisk is only available for COURSE projects")

            existing_instances = list(self.sys.instance_repo.all(s))
            existing_bindings = list(self.sys.instance_media_binding_repo.all(s))
            existing_instance_by_remote_path = {
                str(binding.remote_path): binding.instance_id
                for binding in existing_bindings
                if binding.source_kind == MaterialSourceKind.BAIDU_NETDISK and binding.remote_path
            }
            leaf_by_instance_id = {
                id_canonical_text(node.instance_id): node
                for node in self.sys.learning_object_repo.all(s)
                if isinstance(node, LearningObjectLeaf)
            }
            instances_by_id = {id_canonical_text(item.instance_id): item for item in existing_instances}

            parent_paths = [PurePosixPath(item["path"]).parent.as_posix() for item in normalized_items]
            common_parent = PurePosixPath(os.path.commonpath(parent_paths) if parent_paths else "/")
            root_title = common_parent.name or account.display_name or "百度网盘导入"

            container_id_by_rel_dir: dict[str, LearningObjectNodeId] = {}
            new_nodes: list[LearningObjectContainer | LearningObjectLeaf] = []
            created_instances = 0
            created_leaf_nodes = 0
            reused_instances = 0

            root_id = self.idgen.new_learning_object_node_id(project_id)
            container_id_by_rel_dir["."] = root_id
            child_ids_by_container: dict[str, list[LearningObjectNodeId]] = {"." : []}

            def ensure_container(rel_dir: PurePosixPath) -> LearningObjectNodeId:
                rel_key = rel_dir.as_posix() or "."
                existing = container_id_by_rel_dir.get(rel_key)
                if existing is not None:
                    return existing
                parent_rel = rel_dir.parent if rel_dir.parent != rel_dir else PurePosixPath(".")
                parent_id = ensure_container(parent_rel)
                current_id = self.idgen.new_learning_object_node_id(project_id)
                container_id_by_rel_dir[rel_key] = current_id
                child_ids_by_container.setdefault(rel_key, [])
                child_ids_by_container.setdefault(parent_rel.as_posix() or ".", []).append(current_id)
                return current_id

            imported_instance_ids: list[InstanceId] = []
            binding_by_instance_id: dict[str, InstanceMediaBinding] = {}

            for item in normalized_items:
                remote_path = PurePosixPath(item["path"])
                existing_iid = existing_instance_by_remote_path.get(remote_path.as_posix())
                if existing_iid is None:
                    iid = self.idgen.new_instance_id(project_id)
                    created_instances += 1
                else:
                    iid = existing_iid
                    reused_instances += 1
                imported_instance_ids.append(iid)
                desired_instance = Instance.create(
                    project_id,
                    iid,
                    remote_path.as_posix(),
                    presence=InstancePresence.PRESENT,
                    last_seen_at=now_utc_ms(),
                )
                if id_canonical_text(iid) in instances_by_id:
                    self.sys.instance_repo.update(s, desired_instance)
                else:
                    self.sys.instance_repo.add(s, desired_instance)
                binding_by_instance_id[id_canonical_text(iid)] = InstanceMediaBinding.create(
                    project_id,
                    iid,
                    source_kind=MaterialSourceKind.BAIDU_NETDISK,
                    playback_kind="HLS",
                    account_id=account_id,
                    remote_file_id=item["fileId"],
                    remote_path=remote_path.as_posix(),
                    mime_type=item["mimeType"],
                    size_bytes=item["sizeBytes"],
                    duration_ms=item["durationMs"],
                    source_payload={"provider": BAIDU_NETDISK_PROVIDER},
                )

                if id_canonical_text(iid) in leaf_by_instance_id:
                    continue
                rel_dir = PurePosixPath(".")
                try:
                    rel_dir = remote_path.parent.relative_to(common_parent)
                except Exception:
                    rel_dir = PurePosixPath(".")
                parent_id = ensure_container(rel_dir)
                leaf_id = self.idgen.new_learning_object_node_id(project_id)
                child_ids_by_container.setdefault(rel_dir.as_posix() or ".", []).append(leaf_id)
                new_nodes.append(
                    LearningObjectLeaf(
                        source="BAIDU_NETDISK",
                        project_id=project_id,
                        node_id=leaf_id,
                        relative_path=remote_path,
                        parent_id=parent_id,
                        instance_id=iid,
                        title=item["name"],
                    )
                )
                created_leaf_nodes += 1

            if created_leaf_nodes > 0:
                for rel_key, node_id in list(container_id_by_rel_dir.items()):
                    if rel_key == ".":
                        parent_id = None
                        title = root_title
                        relative_path = common_parent
                    else:
                        rel_dir = PurePosixPath(rel_key)
                        parent_rel = rel_dir.parent if rel_dir.parent != rel_dir else PurePosixPath(".")
                        parent_id = container_id_by_rel_dir[parent_rel.as_posix() or "."]
                        title = rel_dir.name
                        relative_path = common_parent / rel_dir
                    children = tuple(child_ids_by_container.get(rel_key, []))
                    new_nodes.insert(
                        0,
                        LearningObjectContainer(
                            source="BAIDU_NETDISK",
                            project_id=project_id,
                            node_id=node_id,
                            relative_path=relative_path,
                            parent_id=parent_id,
                            children=children,
                            title=title,
                        ),
                    )
            created_nodes = len(new_nodes)

            for binding in binding_by_instance_id.values():
                self.sys.instance_media_binding_repo.set(s, binding)
            for node in new_nodes:
                self.sys.learning_object_repo.add(s, node)

            self._append_audit_event(
                s,
                kind=AuditEventKind.ADD_INSTANCE,
                api_name="import_learning_objects_from_baidu_netdisk",
                payload={
                    "provider": BAIDU_NETDISK_PROVIDER,
                    "accountId": account_id,
                    "itemsCount": len(normalized_items),
                    "createdInstancesCount": int(created_instances),
                    "reusedInstancesCount": int(reused_instances),
                    "createdLearningObjectNodesCount": int(created_nodes),
                },
            )
            self.sys.commit(s)
            result = {
                "created_instances_count": int(created_instances),
                "reused_instances_count": int(reused_instances),
                "created_learning_object_nodes_count": int(created_nodes),
                "imported_count": int(len(normalized_items)),
            }
            self._best_effort_drive_idle_orchestration(project_id)
            return result
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    def get_instance_playback_descriptor(self, project_id: ProjectId, instance_id: InstanceId, *, media_base_path: str) -> dict[str, Any]:
        return self._instance_media_service().build_playback_descriptor(
            str(project_id),
            str(instance_id),
            media_base_path=media_base_path,
        ).to_dict()

    def get_instance_hls_playlist(
        self,
        project_id: ProjectId,
        instance_id: InstanceId,
        *,
        auth_store: AuthStore,
        media_base_path: str,
    ) -> str:
        try:
            return self._instance_media_service().build_baidu_hls_playlist(
                str(project_id),
                str(instance_id),
                auth_store=auth_store,
                media_base_path=media_base_path,
            )
        except BaiduNetdiskApiError as exc:
            self._raise_baidu_netdisk_error(exc)
        return ""

    def stream_instance_hls_segment(
        self,
        project_id: ProjectId,
        instance_id: InstanceId,
        *,
        auth_store: AuthStore,
        upstream_url: str,
    ) -> requests.Response:
        if not str(upstream_url or "").strip():
            raise PreconditionFailure("缺少百度网盘媒体片段地址")
        try:
            return self._instance_media_service().stream_baidu_segment(
                str(project_id),
                str(instance_id),
                auth_store=auth_store,
                upstream_url=upstream_url,
            )
        except BaiduNetdiskApiError as exc:
            self._raise_baidu_netdisk_error(exc)
        raise PreconditionFailure("百度网盘媒体片段读取失败")

    def _run_sync_learning_objects_from_fs(self, project_id: ProjectId) -> dict[str, object]:
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            if self._project_type_in_session(s) != ProjectType.COURSE:
                raise PreconditionFailure("sync_learning_objects_from_fs is only available for COURSE projects")
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
                """
                stack: list[Path] = [d_os]
                while stack:
                    cur = stack.pop()
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
                                    child = Path(ent.path)
                                    rel = PurePosixPath(child.relative_to(abs_root).as_posix())
                                    dir_rel_set.add(rel)
                                    stack.append(child)
                                elif ent.is_file(follow_symlinks=False):
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
            if self._project_type_in_session(s) != ProjectType.COURSE:
                raise PreconditionFailure("import_learning_objects_from_browser_scan is only available for COURSE projects")
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

            children_by_dir: dict[PurePosixPath, list[tuple[str, LearningObjectNodeId]]] = {rel: [] for rel in dir_rel}
            for rel in dir_rel:
                if rel == PurePosixPath("."):
                    continue
                children_by_dir[rel.parent].append((rel.as_posix(), dir_id_by_dir[rel]))
            for rel in file_rel:
                children_by_dir[rel.parent].append((rel.as_posix(), leaf_id_by_file[rel]))
            for rel in dir_rel:
                children_by_dir[rel].sort(key=lambda item: item[0])

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
                child_ids = tuple(item[1] for item in children_by_dir.get(rel, []))
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
                        children=child_ids,
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
            self._best_effort_drive_idle_orchestration(project_id)
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

    def _roll_up_strategy(self, s: MutationSession) -> RollUpStrategy:
        return self.sys.project_config_repo.get(s).roll_up_strategy

    def _is_learning_object_isomorphic_roll_up_enabled(self, s: MutationSession) -> bool:
        cfg = self.sys.project_config_repo.get(s)
        return (
            cfg.roll_up_strategy == RollUpStrategy.LEARNING_OBJECT_ISOMORPHIC
            and cfg.project_type in {ProjectType.COURSE, ProjectType.BOOK}
        )

    @staticmethod
    def _is_synthetic_files_container_node(node: LearningObjectContainer) -> bool:
        relative_path = node.relative_path.as_posix().strip()
        return str(node.title).strip() == "Files" and (
            relative_path == "__files__" or relative_path.endswith("/__files__")
        )

    def _actionable_missing_instance_ids(self, s: MutationSession) -> Tuple[InstanceId, ...]:
        missing_keys = {
            id_canonical_text(instance.instance_id)
            for instance in self.sys.instance_repo.all(s)
            if instance.presence == InstancePresence.MISSING
        }
        if not missing_keys:
            return tuple()
        actionable_keys = {
            id_canonical_text(rp.anchor.instance_id)
            for rp in self.sys.recall_point_repo.all(s)
            if rp.state == RecallPointState.ACTIVE
            and rp.anchor is not None
            and id_canonical_text(rp.anchor.instance_id) in missing_keys
        }
        ordered = sorted(actionable_keys, key=id_canonical_text)
        return tuple(InstanceId(item) for item in ordered)

    def _raise_if_actionable_missing_instances(self, s: MutationSession) -> None:
        if self._actionable_missing_instance_ids(s):
            raise PreconditionFailure("Gate: actionable missing instances exist; fix missing instance mappings before progressing")

    def _ensure_layers_through(self, s: MutationSession, target_layer_index: int) -> None:
        if int(target_layer_index) < 0:
            raise PreconditionFailure("target_layer_index must be >= 0")
        cfg = self.sys.project_config_repo.get(s)
        existing_layers = list(self.sys.layer_repo.all(s))
        last_mode = existing_layers[-1].layer_mode if existing_layers else LayerMode.AUTO
        for layer_index in range(0, int(target_layer_index) + 1):
            current = self.sys.layer_repo.maybe_get_by_index(s, layer_index)
            if current is not None:
                last_mode = current.layer_mode
                continue
            layer_cfg = cfg.layer_configs.get(int(layer_index), default_layer_config())
            layer = Layer(
                project_id=s.project_id,
                layer_id=self.idgen.new_layer_id(s.project_id),
                layer_index=int(layer_index),
                layer_mode=last_mode,
                orchestrator_managed_review_chain_ids=tuple(),
                aggregation_k_node=int(layer_cfg.aggregation_k_node),
                aggregation_k_point=int(layer_cfg.aggregation_k_point),
            )
            layer.validate_local_invariants()
            self.sys.layer_repo.add(s, layer)
            last_mode = layer.layer_mode

    def _detect_learning_object_isomorphic_roll_up_once(
        self, s: MutationSession
    ) -> Optional[tuple[int, Tuple[LearningTaskNodeId, ...], str]]:
        if not self._is_learning_object_isomorphic_roll_up_enabled(s):
            return None
        if not self.sys.queue_repo.is_empty(s):
            return None
        if self._actionable_missing_instance_ids(s):
            return None

        object_nodes = {
            id_canonical_text(node.node_id): node
            for node in self.sys.learning_object_repo.all(s)
        }
        if not object_nodes:
            return None

        active_instance_keys = {
            id_canonical_text(rp.anchor.instance_id)
            for rp in self.sys.recall_point_repo.all(s)
            if rp.state == RecallPointState.ACTIVE and rp.anchor is not None
        }

        covered_instance_cache: dict[str, Tuple[str, ...]] = {}
        logical_level_cache: dict[str, int] = {}
        eligible_cache: dict[str, bool] = {}

        def covered_instance_keys(node_key: str) -> Tuple[str, ...]:
            cached = covered_instance_cache.get(node_key)
            if cached is not None:
                return cached
            node = object_nodes[node_key]
            if isinstance(node, LearningObjectLeaf):
                result = (id_canonical_text(node.instance_id),)
            else:
                items: list[str] = []
                for child_id in node.children:
                    child_key = id_canonical_text(child_id)
                    if child_key in object_nodes:
                        items.extend(covered_instance_keys(child_key))
                result = tuple(items)
            covered_instance_cache[node_key] = result
            return result

        def logical_level(node_key: str) -> int:
            cached = logical_level_cache.get(node_key)
            if cached is not None:
                return cached
            node = object_nodes[node_key]
            if isinstance(node, LearningObjectLeaf):
                logical_level_cache[node_key] = 0
                return 0
            child_levels = [
                logical_level(id_canonical_text(child_id))
                for child_id in node.children
                if id_canonical_text(child_id) in object_nodes
            ]
            if self._is_synthetic_files_container_node(node):
                result = max(child_levels, default=0)
            else:
                result = 1 + max(child_levels, default=0) if covered_instance_keys(node_key) else 0
            logical_level_cache[node_key] = result
            return result

        def is_eligible(node_key: str) -> bool:
            cached = eligible_cache.get(node_key)
            if cached is not None:
                return cached
            node = object_nodes[node_key]
            if isinstance(node, LearningObjectLeaf):
                eligible_cache[node_key] = False
                return False
            if self._is_synthetic_files_container_node(node):
                eligible_cache[node_key] = False
                return False
            inst_keys = covered_instance_keys(node_key)
            result = bool(inst_keys) and all(item in active_instance_keys for item in inst_keys)
            eligible_cache[node_key] = result
            return result

        eligible_object_keys = sorted(
            [
                node_key
                for node_key, node in object_nodes.items()
                if isinstance(node, LearningObjectContainer) and is_eligible(node_key)
            ],
            key=lambda node_key: (logical_level(node_key), str(object_nodes[node_key].relative_path), node_key),
        )

        def source_queue_candidate_ids_for_object_node(
            node_key: str, target_layer_index: int
        ) -> Tuple[LearningTaskNodeId, ...]:
            source_layer_index = int(target_layer_index) - 1
            if source_layer_index < 0:
                return tuple()
            target_instance_keys = set(covered_instance_keys(node_key))
            if not target_instance_keys:
                return tuple()
            try:
                queue = self.sys.aggq_repo.get(s, source_layer_index)
            except NotFound:
                return tuple()
            current_ids = queue.current_ids()
            if not current_ids:
                return tuple()

            selected: list[LearningTaskNodeId] = []
            for candidate_id in current_ids:
                if self.sys.learning_task_node_repo.get(s, candidate_id).parent_id is not None:
                    continue
                candidate_instance_keys: set[str] = set()
                for rp_id in self.sys.learning_task_node_repo.covered_rp_ids(s, candidate_id):
                    try:
                        rp = self.sys.recall_point_repo.get(s, rp_id)
                    except NotFound:
                        continue
                    if rp.anchor is not None:
                        candidate_instance_keys.add(id_canonical_text(rp.anchor.instance_id))
                if candidate_instance_keys and candidate_instance_keys.issubset(target_instance_keys):
                    selected.append(candidate_id)
            return tuple(selected)

        for node_key in eligible_object_keys:
            node = object_nodes[node_key]
            target_layer_index = logical_level(node_key)
            if int(target_layer_index) <= 0:
                continue
            candidate_ids = source_queue_candidate_ids_for_object_node(node_key, int(target_layer_index))
            if candidate_ids:
                return int(target_layer_index) - 1, candidate_ids, node.title

        return None

    def _threshold_roll_up_enabled(self, s: MutationSession, layer_index: int) -> bool:
        cfg = self.sys.project_config_repo.get(s)
        if cfg.roll_up_strategy != RollUpStrategy.THRESHOLD_AUTO:
            return False
        layer_cfg = cfg.layer_configs.get(int(layer_index), default_layer_config())
        return bool(layer_cfg.threshold_roll_up_enabled)

    def _enter_clearing_if_threshold_met(self, s: MutationSession, layer_index: int) -> bool:
        """
        Spec 4.4.2 T1: if thresholds are met, enter/keep CLEARING.
        """
        if not self._threshold_roll_up_enabled(s, layer_index):
            return False
        return self._enter_clearing_if_auto_roll_up_available(s, layer_index)

    def _enter_clearing_if_auto_roll_up_available(self, s: MutationSession, layer_index: int) -> bool:
        if not self.sys.queue_repo.is_empty(s):
            return False
        if self._actionable_missing_instance_ids(s):
            return False
        if self._get_aggregation_cycle_state(s, layer_index) != AggregationCycleState.DONE:
            return False
        if self._get_pending_roll_up_parent_node_id(s, layer_index) is not None:
            return False

        if self._threshold_roll_up_enabled(s, layer_index) and self._aggregation_threshold_met(s, layer_index):
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

        detected = self._detect_learning_object_isomorphic_roll_up_once(s)
        if detected is None:
            return False
        source_layer_index, candidate_ids, title = detected
        if int(source_layer_index) != int(layer_index):
            return False

        parent_node_id, candidates, created = self._roll_up_phase_a_for_candidates(
            s,
            source_layer_index=source_layer_index,
            candidate_node_ids=candidate_ids,
            title=title,
        )
        if not created or parent_node_id is None:
            return False
        self._append_aggregation_event(
            s,
            layer_index=source_layer_index,
            parent_node_id=parent_node_id,
            candidate_node_ids=candidates,
            reason=AggregationEventReason.THRESHOLD_DRAIN,
            title=title,
        )
        return True

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
        initial_project_type: ProjectType = ProjectType.COURSE,
        project_id: ProjectId | None = None,
    ) -> ProjectId:
        sql_store = self._sql_store()
        if sql_store is not None:
            return self._create_project_sql_direct(
                sql_store,
                title,
                project_root,
                initial_source_kind=initial_source_kind,
                initial_project_type=initial_project_type,
                project_id=project_id,
            )
        return self.sys.create_project(
            title,
            project_root,
            initial_source_kind=initial_source_kind,
            initial_project_type=initial_project_type,
            project_id=project_id,
        )

    def create_subject(self, title: str) -> ProjectId:
        if self.sys.g._write_lock_held:
            raise ConcurrencyConflictError("Another READ_WRITE session is OPEN")
        idgen_counters_before = dict(self.idgen._counters)
        subject_id = ProjectId(str(self.idgen.new_subject_id()))
        self.sys.g._write_lock_held = True
        try:
            subject_id, subject_store = self._build_project_store_for_create_project(
                title,
                None,
                initial_source_kind=MaterialSourceKind.SERVER_FS,
                initial_project_type=ProjectType.COURSE,
                project_id=subject_id,
            )
            subject = subject_store.project
            if subject is None:
                raise PreconditionFailure("subject bootstrap incomplete")

            material_type = StudyMaterialType.COURSE
            material_title = "网课材料"
            material_id = self._new_study_material_id(material_type)
            scoped_project_id, next_sequence = self._next_scoped_project_id(subject, tuple())
            source_kind, project_type = self._project_options_for_material_type(material_type)
            material_project_id, material_store = self._build_project_store_for_create_project(
                material_title,
                None,
                initial_source_kind=source_kind,
                initial_project_type=project_type,
                subject_id=subject_id,
                scoped_project_id=scoped_project_id,
                subject_material_link=SubjectMaterialLink(
                    subject_id=subject_id,
                    material_id=material_id,
                    material_type=material_type,
                    scoped_project_id=scoped_project_id,
                ),
            )
            material = StudyMaterial(
                subject_id=subject_id,
                material_id=material_id,
                material_type=material_type,
                title=material_title,
                created_at=now_utc_ms(),
                scoped_project_id=scoped_project_id,
                internal_project_id=material_project_id,
            )
            subject_store.project = replace(subject, project_sequence=next_sequence)
            subject_store.study_materials = {material.material_id: material}
            subject_store.study_materials_initialized = True

            next_projects = dict(self.sys.g.projects)
            subject_key = id_canonical_text(subject_id)
            material_key = id_canonical_text(material_project_id)
            if subject_key in next_projects or material_key in next_projects:
                raise PreconditionFailure("project_id already exists")
            next_projects[subject_key] = subject_store
            next_projects[material_key] = material_store
            self.sys._persist_to_disk(projects_override=next_projects)
            self.sys.g.projects = next_projects
            return subject_id
        except Exception:
            self.idgen._counters = idgen_counters_before
            raise
        finally:
            self.sys.g._write_lock_held = False

    def get_subject_context(self, project_id: ProjectId) -> dict[str, object]:
        if self.is_subject_root_project(project_id):
            raise PreconditionFailure("subject id is not a project id")
        resolved_subject_id = self._resolve_subject_id(project_id)
        self._require_subject_root_project(resolved_subject_id)
        subject = self._get_active_project_metadata(resolved_subject_id)
        materials = self._list_subject_materials_from_store(resolved_subject_id)
        current_material = self._resolve_current_material_for_project(project_id, resolved_subject_id)
        return {
            "subject": subject,
            "current_material": current_material,
            "materials": materials,
            "current_internal_project_id": project_id,
        }

    def edit_subject(self, subject_id: ProjectId, title: str) -> None:
        self._require_subject_root_project(subject_id)
        self.edit_project(subject_id, title)

    def delete_subject(self, subject_id: ProjectId) -> None:
        self._delete_subject_project_atomically(subject_id)

    def _delete_subject_project_atomically(self, subject_id: ProjectId) -> None:
        resolved_subject_id = subject_id
        self._require_subject_root_project(resolved_subject_id)
        if self.sys.g._write_lock_held:
            raise ConcurrencyConflictError("Another READ_WRITE session is OPEN")
        idgen_counters_before = dict(self.idgen._counters)
        self.sys.g._write_lock_held = True
        try:
            related_project_ids = [resolved_subject_id]
            for material in self._list_subject_materials_from_store(resolved_subject_id):
                internal_key = self._material_internal_project_key(material)
                if internal_key is not None and id_canonical_text(internal_key) != id_canonical_text(resolved_subject_id):
                    related_project_ids.append(internal_key)

            next_projects = dict(self.sys.g.projects)
            for related_project_id in related_project_ids:
                project_store = self._get_project_store(related_project_id)
                next_projects[id_canonical_text(related_project_id)] = self._deleted_project_store(project_store)

            self.sys._persist_to_disk(projects_override=next_projects)
            self.sys.g.projects = next_projects
            for related_project_id in related_project_ids:
                self._startup_fs_sync_done.discard(id_canonical_text(related_project_id))
        except Exception:
            self.idgen._counters = idgen_counters_before
            raise
        finally:
            self.sys.g._write_lock_held = False

    def list_projects(self) -> Tuple:
        sql_store = self._sql_store()
        if sql_store is not None:
            return tuple(
                project
                for project in sql_store.list_projects_metadata(active_only=True)
                if not self.is_subject_root_project(project.project_id)
            )

        projects = [ps.project for ps in self.sys.g.projects.values() if ps.project is not None and ps.project.state == ProjectState.ACTIVE]
        projects = [project for project in projects if not self.is_subject_root_project(project.project_id)]
        projects.sort(key=lambda p: id_canonical_text(p.project_id))
        return tuple(projects)

    def list_subjects(self) -> Tuple[Project, ...]:
        sql_store = self._sql_store()
        if sql_store is not None:
            return tuple(
                project
                for project in sql_store.list_projects_metadata(active_only=True)
                if self.is_subject_root_project(project.project_id)
            )
        return tuple(
            ps.project
            for ps in self.sys.g.projects.values()
            if ps.project is not None
            and ps.project.state == ProjectState.ACTIVE
            and self.is_subject_root_project(ps.project.project_id)
        )

    def list_subject_materials(self, subject_id: ProjectId) -> Tuple[StudyMaterial, ...]:
        self._require_subject_root_project(subject_id)
        return self._list_subject_materials_from_store(subject_id)

    def create_subject_material(
        self,
        subject_id: ProjectId,
        *,
        material_type: StudyMaterialType,
        title: str | None = None,
    ) -> StudyMaterial:
        resolved_subject_id = subject_id
        self._require_subject_root_project(resolved_subject_id)
        if self.sys.g._write_lock_held:
            raise ConcurrencyConflictError("Another READ_WRITE session is OPEN")
        idgen_counters_before = dict(self.idgen._counters)
        self.sys.g._write_lock_held = True
        try:
            subject_store = self._get_project_store(resolved_subject_id)
            subject = subject_store.project
            if subject is None or subject.state != ProjectState.ACTIVE:
                raise NotFound(resolved_subject_id)
            normalized_title = str(title or "").strip() or self._default_material_title_for_type(material_type)
            material_id = self._new_study_material_id(material_type)
            source_kind, project_type = self._project_options_for_material_type(material_type)
            existing_materials = self._list_subject_materials_from_store(resolved_subject_id)
            scoped_project_id, next_sequence = self._next_scoped_project_id(subject, existing_materials)
            material_project_id, child_store = self._build_project_store_for_create_project(
                normalized_title if normalized_title else f"{subject.title}·{self._default_material_title_for_type(material_type)}",
                None,
                initial_source_kind=source_kind,
                initial_project_type=project_type,
                subject_id=resolved_subject_id,
                scoped_project_id=scoped_project_id,
                subject_material_link=SubjectMaterialLink(
                    subject_id=resolved_subject_id,
                    material_id=material_id,
                    material_type=material_type,
                    scoped_project_id=scoped_project_id,
                ),
            )
            material = StudyMaterial(
                subject_id=subject.project_id,
                material_id=material_id,
                material_type=material_type,
                title=normalized_title,
                created_at=now_utc_ms(),
                scoped_project_id=scoped_project_id,
                internal_project_id=material_project_id,
            )
            if id_canonical_text(material_project_id) in self.sys.g.projects:
                raise PreconditionFailure("project_id already exists")

            next_subject_store = self._copy_project_store(subject_store)
            next_subject_store.project = replace(subject, project_sequence=next_sequence)
            next_subject_store.study_materials = {item.material_id: item for item in existing_materials}
            next_subject_store.study_materials[material.material_id] = material
            next_subject_store.study_materials_initialized = True

            next_projects = dict(self.sys.g.projects)
            next_projects[id_canonical_text(resolved_subject_id)] = next_subject_store
            next_projects[id_canonical_text(material_project_id)] = child_store
            self.sys._persist_to_disk(projects_override=next_projects)
            self.sys.g.projects = next_projects
            return material
        except Exception:
            self.idgen._counters = idgen_counters_before
            raise
        finally:
            self.sys.g._write_lock_held = False

    def edit_subject_material(self, subject_id: ProjectId, material_id: str, *, title: str) -> StudyMaterial:
        resolved_subject_id = subject_id
        self._require_subject_root_project(resolved_subject_id)
        material = self._find_subject_material(resolved_subject_id, material_id)
        return self._edit_subject_material_atomically(resolved_subject_id, material, title=title)

    def _edit_subject_material_atomically(
        self,
        subject_id: ProjectId,
        material: StudyMaterial,
        *,
        title: str,
    ) -> StudyMaterial:
        resolved_subject_id = subject_id
        material_project_id = self._material_internal_project_key(material)
        if material_project_id is None:
            raise PreconditionFailure("当前项目缺少可重命名的项目标识")
        normalized_title = str(title or "").strip()
        if not normalized_title:
            raise PreconditionFailure("edit_project.title must be non-empty")
        if self.sys.g._write_lock_held:
            raise ConcurrencyConflictError("Another READ_WRITE session is OPEN")
        idgen_counters_before = dict(self.idgen._counters)
        self.sys.g._write_lock_held = True
        try:
            subject_store = self._get_project_store(resolved_subject_id)
            material_store = self._get_project_store(material_project_id)
            material_project = material_store.project
            if material_project is None or material_project.state != ProjectState.ACTIVE:
                raise NotFound(material_project_id)
            updated_material = replace(material, title=normalized_title)
            next_subject_store = self._copy_project_store(subject_store)
            next_materials = {item.material_id: item for item in self._list_subject_materials_from_store(resolved_subject_id)}
            next_materials[material.material_id] = updated_material
            next_subject_store.study_materials = next_materials
            next_subject_store.study_materials_initialized = True

            next_projects = dict(self.sys.g.projects)
            next_projects[id_canonical_text(resolved_subject_id)] = next_subject_store
            if id_canonical_text(material_project_id) != id_canonical_text(resolved_subject_id):
                next_material_store = self._copy_project_store(material_store)
                next_material_store.project = replace(material_project, title=normalized_title)
                next_material_store.project.validate_write_time()
                event = self._new_audit_event(
                    material_project_id,
                    kind=AuditEventKind.EDIT_PROJECT,
                    api_name="edit_project",
                    payload={"projectId": str(material_project_id)},
                )
                next_material_store.audit_log_events[id_canonical_text(event.event_id)] = event
                next_projects[id_canonical_text(material_project_id)] = next_material_store
            self.sys._persist_to_disk(projects_override=next_projects)
            self.sys.g.projects = next_projects
            return updated_material
        except Exception:
            self.idgen._counters = idgen_counters_before
            raise
        finally:
            self.sys.g._write_lock_held = False

    def delete_subject_material(self, subject_id: ProjectId, material_id: str) -> None:
        resolved_subject_id = subject_id
        self._require_subject_root_project(resolved_subject_id)
        material = self._find_subject_material(resolved_subject_id, material_id)
        self._delete_subject_material_atomically(resolved_subject_id, material)

    def _delete_subject_material_atomically(self, subject_id: ProjectId, material: StudyMaterial) -> None:
        resolved_subject_id = subject_id
        material_project_id = self._material_internal_project_key(material)
        if material_project_id is None:
            raise PreconditionFailure("当前项目缺少可删除的项目标识")
        if self.sys.g._write_lock_held:
            raise ConcurrencyConflictError("Another READ_WRITE session is OPEN")
        idgen_counters_before = dict(self.idgen._counters)
        self.sys.g._write_lock_held = True
        try:
            subject_store = self._get_project_store(resolved_subject_id)
            material_store = self._get_project_store(material_project_id)
            next_subject_store = self._copy_project_store(subject_store)
            next_materials = {item.material_id: item for item in self._list_subject_materials_from_store(resolved_subject_id)}
            next_materials.pop(material.material_id, None)
            next_subject_store.study_materials = next_materials
            next_subject_store.study_materials_initialized = True

            next_projects = dict(self.sys.g.projects)
            next_projects[id_canonical_text(resolved_subject_id)] = next_subject_store
            if id_canonical_text(material_project_id) == id_canonical_text(resolved_subject_id):
                next_projects[id_canonical_text(material_project_id)] = next_subject_store
            else:
                next_projects[id_canonical_text(material_project_id)] = self._deleted_project_store(material_store)
            self.sys._persist_to_disk(projects_override=next_projects)
            self.sys.g.projects = next_projects
        except Exception:
            self.idgen._counters = idgen_counters_before
            raise
        finally:
            self.sys.g._write_lock_held = False

    def list_membership_cleanup_project_ids(self, project_id: ProjectId) -> Tuple[ProjectId, ...]:
        material_link = self._get_subject_material_link(project_id)
        if material_link is not None:
            return (project_id,)
        related_project_ids = {id_canonical_text(project_id): project_id}
        for material in self._list_subject_materials_from_store(project_id):
            if material.scoped_project_id is None:
                continue
            internal_key = self._material_internal_project_key(material)
            if internal_key is not None:
                related_project_ids[id_canonical_text(internal_key)] = internal_key
        return tuple(related_project_ids[key] for key in sorted(related_project_ids.keys()))

    def edit_project(self, project_id: ProjectId, title: str) -> None:
        material_link = self._get_subject_material_link(project_id)
        if material_link is not None:
            self._require_subject_root_project(material_link.subject_id)
            material = self._find_subject_material(material_link.subject_id, material_link.material_id)
            self._edit_subject_material_atomically(material_link.subject_id, material, title=title)
            return
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
                subject_id=project.subject_id,
                scoped_project_id=project.scoped_project_id,
                project_sequence=project.project_sequence,
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
        material_link = self._get_subject_material_link(project_id)
        if material_link is not None:
            self._require_subject_root_project(material_link.subject_id)
            material = self._find_subject_material(material_link.subject_id, material_link.material_id)
            self._delete_subject_material_atomically(material_link.subject_id, material)
            return
        if self.is_subject_root_project(project_id):
            self._delete_subject_project_atomically(project_id)
            return
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

    def list_instances_with_media_summary(self, project_id: ProjectId) -> Tuple[InstanceMediaSummary, ...]:
        self._ensure_startup_fs_sync_done(project_id)
        project_binding = self.get_project_material_source_binding(project_id)
        media_service = self._instance_media_service()
        items: list[InstanceMediaSummary] = []
        for instance in self.list_instances(project_id):
            media_binding = media_service.get_instance_media_binding(str(project_id), str(instance.instance_id))
            source_kind = media_binding.source_kind if media_binding is not None else project_binding.source_kind
            items.append(
                InstanceMediaSummary(
                    instance=instance,
                    media_source_kind=source_kind.value,
                    playback_kind="FILE" if media_binding is None else media_binding.playback_kind,
                    duration_ms=None if media_binding is None else media_binding.duration_ms,
                )
            )
        return tuple(items)

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

    def list_video_watch_progress(
        self,
        project_id: ProjectId,
        *,
        instance_ids: Sequence[InstanceId] | None = None,
    ) -> Tuple[VideoWatchProgress, ...]:
        self._ensure_startup_fs_sync_done(project_id)
        requested = None if instance_ids is None else {id_canonical_text(instance_id) for instance_id in instance_ids}
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            items = self.sys.video_watch_progress_repo.all(s)
            if requested is not None:
                items = tuple(item for item in items if id_canonical_text(item.instance_id) in requested)
            return items
        finally:
            self.sys.rollback(s)

    def record_video_watch_progress_range(
        self,
        project_id: ProjectId,
        instance_id: InstanceId,
        *,
        start_ms: int,
        end_ms: int,
        duration_ms: int | None = None,
    ) -> VideoWatchProgress:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            self.sys.instance_repo.get(s, instance_id)
            now = now_utc_ms()
            current = self.sys.video_watch_progress_repo.maybe_get(s, instance_id)
            if current is None:
                current = VideoWatchProgress.create(
                    project_id,
                    instance_id,
                    duration_ms=duration_ms,
                    updated_at=now,
                )
            progress = current.with_range(
                start_ms=int(start_ms),
                end_ms=int(end_ms),
                duration_ms=duration_ms,
                updated_at=now,
            )
            self.sys.video_watch_progress_repo.set(s, progress)
            self.sys.commit(s)
            return progress
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    def mark_video_watch_progress_completed(
        self,
        project_id: ProjectId,
        instance_id: InstanceId,
        *,
        duration_ms: int,
    ) -> VideoWatchProgress:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            self.sys.instance_repo.get(s, instance_id)
            now = now_utc_ms()
            current = self.sys.video_watch_progress_repo.maybe_get(s, instance_id)
            if current is None:
                current = VideoWatchProgress.create(project_id, instance_id, duration_ms=duration_ms, updated_at=now)
            progress = current.with_completed(duration_ms=int(duration_ms), completed_at=now)
            self.sys.video_watch_progress_repo.set(s, progress)
            self.sys.commit(s)
            return progress
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

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

    def resolve_instance_media_file_path(self, project_id: ProjectId, instance_id: InstanceId) -> Path:
        self._ensure_startup_fs_sync_done(project_id)
        source_kind = self._instance_media_service().get_effective_source_kind(str(project_id), str(instance_id))
        if source_kind == MaterialSourceKind.BAIDU_NETDISK:
            raise PreconditionFailure("Baidu Netdisk instances must be played via the playback descriptor")
        instance = self.get_instance(project_id, instance_id)
        if getattr(instance, "presence", None) == InstancePresence.MISSING:
            raise PreconditionFailure("material is MISSING")
        return self._instance_media_service().resolve_local_material_path(str(project_id), str(instance_id))

    def get_instance_subtitle_file(self, project_id: ProjectId, instance_id: InstanceId) -> dict[str, object]:
        return self.get_instance_subtitle_file_for_user(project_id, instance_id, auth_store=None)

    def get_instance_subtitle_file_for_user(
        self,
        project_id: ProjectId,
        instance_id: InstanceId,
        *,
        auth_store: AuthStore | None = None,
    ) -> dict[str, object]:
        self._ensure_startup_fs_sync_done(project_id)
        return self._instance_media_service().get_instance_subtitle_file(
            str(project_id),
            str(instance_id),
            auth_store=auth_store,
        )

    # 4.5.3
    def add_instance(self, project_id: ProjectId, material_id: str) -> InstanceId:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            if self._project_type_in_session(s) == ProjectType.LOOSE_POINTS:
                raise PreconditionFailure("add_instance is disabled for LOOSE_POINTS projects")
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

    def initialize_book_learning_objects(
        self,
        project_id: ProjectId,
        *,
        outline_items: Sequence[tuple[int, str]],
        api_name: str = "initialize_book_learning_objects",
    ) -> dict[str, object]:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            if self._project_type_in_session(s) != ProjectType.BOOK:
                raise PreconditionFailure("initialize_book_learning_objects is only available for BOOK projects")
            binding = self.sys.project_material_source_binding_repo.get(s)
            if binding.source_kind != MaterialSourceKind.MANUAL:
                raise PreconditionFailure("initialize_book_learning_objects requires MANUAL source kind")
            if self.sys.instance_repo.all(s) or self.sys.learning_object_repo.all(s):
                raise PreconditionFailure("initialize_book_learning_objects requires an empty manual tree")
            if not outline_items:
                raise PreconditionFailure("initialize_book_learning_objects.outline_items must be non-empty")

            normalized: list[tuple[int, str]] = []
            for index, item in enumerate(outline_items):
                depth_raw, title_raw = item
                depth = int(depth_raw)
                title = str(title_raw or "").strip()
                if depth < 0:
                    raise PreconditionFailure(f"initialize_book_learning_objects.outline_items[{index}].depth must be >= 0")
                if not title:
                    raise PreconditionFailure(f"initialize_book_learning_objects.outline_items[{index}].title must be non-empty")
                normalized.append((depth, title))

            if normalized[0][0] != 0:
                raise PreconditionFailure("initialize_book_learning_objects first outline item must start at depth 0")

            normalized_nodes: list[tuple[int, str, bool]] = []
            for index, (depth, title) in enumerate(normalized):
                if index > 0:
                    prev_depth = normalized[index - 1][0]
                    if depth > prev_depth + 1:
                        raise PreconditionFailure("initialize_book_learning_objects outline depth may increase by at most 1")
                next_depth = normalized[index + 1][0] if index + 1 < len(normalized) else -1
                if next_depth > depth + 1:
                    raise PreconditionFailure("initialize_book_learning_objects outline depth may increase by at most 1")
                normalized_nodes.append((depth, title, next_depth > depth))

            sibling_counts_by_parent_path: dict[tuple[str, ...], dict[str, int]] = {}
            node_id_by_depth: dict[int, LearningObjectNodeId] = {}
            path_by_depth: dict[int, tuple[str, ...]] = {}
            created_instances = 0
            created_nodes = 0
            root_count = 0

            def append_child(parent_id: LearningObjectNodeId, child_id: LearningObjectNodeId) -> None:
                parent = self.sys.learning_object_repo.get(s, parent_id)
                if not isinstance(parent, LearningObjectContainer):
                    raise PreconditionFailure("initialize_book_learning_objects parent must be container")
                updated_parent = LearningObjectContainer(
                    source=parent.source,
                    project_id=parent.project_id,
                    node_id=parent.node_id,
                    relative_path=parent.relative_path,
                    parent_id=parent.parent_id,
                    children=tuple(parent.children) + (child_id,),
                    title=parent.title,
                )
                updated_parent.validate_write_time()
                s._staged.learning_object_nodes[id_canonical_text(updated_parent.node_id)] = updated_parent

            for depth, title, has_children in normalized_nodes:
                parent_id = None if depth == 0 else node_id_by_depth.get(depth - 1)
                if depth > 0 and parent_id is None:
                    raise PreconditionFailure("initialize_book_learning_objects outline parent missing")
                parent_path = tuple() if depth == 0 else path_by_depth.get(depth - 1, tuple())
                counts = sibling_counts_by_parent_path.setdefault(parent_path, {})
                base_segment = _sanitize_manual_outline_segment(title)
                next_count = counts.get(base_segment, 0) + 1
                counts[base_segment] = next_count
                segment = base_segment if next_count == 1 else f"{base_segment} ({next_count})"
                node_path = parent_path + (segment,)
                relative_path = PurePosixPath("/".join(node_path))

                for stale_depth in list(node_id_by_depth.keys()):
                    if stale_depth >= depth + 1:
                        node_id_by_depth.pop(stale_depth, None)
                        path_by_depth.pop(stale_depth, None)

                if has_children:
                    node_id = self.idgen.new_learning_object_node_id(project_id)
                    container = LearningObjectContainer(
                        source="MANUAL",
                        project_id=project_id,
                        node_id=node_id,
                        relative_path=relative_path,
                        parent_id=parent_id,
                        children=tuple(),
                        title=title,
                    )
                    container.validate_write_time()
                    self.sys.learning_object_repo.add(s, container)
                    if parent_id is not None:
                        append_child(parent_id, node_id)
                    else:
                        root_count += 1
                    node_id_by_depth[depth] = node_id
                    path_by_depth[depth] = node_path
                    created_nodes += 1
                    continue

                instance_id = self.idgen.new_instance_id(project_id)
                instance = Instance.create(
                    project_id,
                    instance_id,
                    relative_path,
                    presence=InstancePresence.PRESENT,
                    last_seen_at=None,
                )
                self.sys.instance_repo.add(s, instance)
                leaf_id = self.idgen.new_learning_object_node_id(project_id)
                leaf = LearningObjectLeaf(
                    source="MANUAL",
                    project_id=project_id,
                    node_id=leaf_id,
                    relative_path=instance.material_id,
                    parent_id=parent_id,
                    instance_id=instance_id,
                    title=title,
                )
                leaf.validate_write_time()
                self.sys.learning_object_repo.add(s, leaf)
                if parent_id is not None:
                    append_child(parent_id, leaf_id)
                else:
                    root_count += 1
                node_id_by_depth[depth] = leaf_id
                path_by_depth[depth] = node_path
                created_instances += 1
                created_nodes += 1

            self._append_audit_event(
                s,
                kind=AuditEventKind.ADD_LEARNING_OBJECT_CONTAINER,
                api_name=api_name,
                payload={
                    "createdInstancesCount": created_instances,
                    "createdLearningObjectNodesCount": created_nodes,
                    "rootCount": root_count,
                },
            )
            self.sys.commit(s)
            result = {
                "created_instances_count": int(created_instances),
                "created_learning_object_nodes_count": int(created_nodes),
                "root_count": int(root_count),
            }
            self._best_effort_drive_idle_orchestration(project_id)
            return result
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    def _build_outline_items_from_learning_object_tree(self, project_id: ProjectId) -> Tuple[tuple[int, str], ...]:
        self._ensure_startup_fs_sync_done(project_id)
        sql_store = self._sql_store()
        if sql_store is not None:
            nodes = tuple(sql_store.list_learning_object_nodes(str(project_id)))
        else:
            s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
            try:
                nodes = tuple(self.sys.learning_object_repo.all(s))
            finally:
                self.sys.rollback(s)

        if not nodes:
            raise PreconditionFailure("source material has no learning object tree")

        node_by_id = {id_canonical_text(node.node_id): node for node in nodes}
        root_ids = [
            node.node_id
            for node in nodes
            if getattr(node, "parent_id", None) is None
        ]
        if not root_ids:
            raise PreconditionFailure("source learning object tree has no roots")

        def sort_key(node_id: LearningObjectNodeId) -> tuple[int, str, str, str]:
            node = node_by_id[id_canonical_text(node_id)]
            kind_rank = 0 if isinstance(node, LearningObjectContainer) else 1
            relative_path = getattr(node, "relative_path", PurePosixPath(".")).as_posix()
            return (
                kind_rank,
                relative_path,
                str(getattr(node, "title", "")).strip(),
                id_canonical_text(node_id),
            )

        outline_items: list[tuple[int, str]] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node_id: LearningObjectNodeId, depth: int) -> None:
            key = id_canonical_text(node_id)
            node = node_by_id.get(key)
            if node is None:
                raise PreconditionFailure("source learning object tree contains a missing child reference")
            if key in visiting:
                raise PreconditionFailure("source learning object tree contains a cycle")
            visiting.add(key)
            try:
                if isinstance(node, LearningObjectContainer) and self._is_synthetic_files_container_node(node):
                    for child_id in node.children:
                        visit(child_id, depth)
                    return

                title = str(getattr(node, "title", "") or "").strip()
                if not title:
                    raise PreconditionFailure("source learning object tree contains an untitled node")
                outline_items.append((depth, title))

                if isinstance(node, LearningObjectContainer):
                    for child_id in node.children:
                        visit(child_id, depth + 1)
            finally:
                visiting.discard(key)
                visited.add(key)

        for root_id in sorted(root_ids, key=sort_key):
            visit(root_id, 0)

        unvisited = [
            node.node_id
            for node in nodes
            if id_canonical_text(node.node_id) not in visited
        ]
        if unvisited:
            raise PreconditionFailure("source learning object tree contains orphaned nodes")

        if not outline_items:
            raise PreconditionFailure("source material has no reusable learning object nodes")
        return tuple(outline_items)

    def initialize_book_learning_objects_from_subject_material(
        self,
        project_id: ProjectId,
        *,
        source_material_id: str,
    ) -> dict[str, object]:
        resolved_subject_id = self._resolve_subject_id(project_id)
        target_material_link = self._get_subject_material_link(project_id)
        if target_material_link is None:
            raise PreconditionFailure(
                "initialize_book_learning_objects_from_subject_material requires a subject-bound book material"
            )
        target_material = self._find_subject_material(resolved_subject_id, target_material_link.material_id)
        if target_material.material_type != StudyMaterialType.BOOK:
            raise PreconditionFailure("initialize_book_learning_objects_from_subject_material is only available for BOOK materials")

        source_material = self._find_subject_material(resolved_subject_id, source_material_id)
        allowed_source_types = {StudyMaterialType.COURSE}
        if source_material.material_type not in allowed_source_types:
            raise PreconditionFailure(
                "initialize_book_learning_objects_from_subject_material source material type is unsupported"
            )
        source_project_id = source_material.internal_project_id
        if source_project_id is None:
            raise PreconditionFailure("source material has no project")

        outline_items = self._build_outline_items_from_learning_object_tree(source_project_id)
        return self.initialize_book_learning_objects(
            project_id,
            outline_items=outline_items,
            api_name="initialize_book_learning_objects_from_subject_material",
        )

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
            if self._project_type_in_session(s) == ProjectType.LOOSE_POINTS:
                raise PreconditionFailure("add_learning_object_leaf is disabled for LOOSE_POINTS projects")
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
            if self._project_type_in_session(s) == ProjectType.LOOSE_POINTS:
                raise PreconditionFailure("add_learning_object_container is disabled for LOOSE_POINTS projects")
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
        self._best_effort_drive_idle_orchestration(project_id)
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
                if rp.state == RecallPointState.ACTIVE
                and rp.anchor is not None
                and id_canonical_text(rp.anchor.instance_id) == want
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
                from_inst = self.sys.instance_repo.get(s, from_instance_id)
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
                        and rp.anchor is not None
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
                    if rp.anchor is None:
                        raise PreconditionFailure("bulk_remap_recall_points_instance.recall_point_ids must all have anchors")
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
                    references=tuple(rp.references),
                    insights=tuple(rp.insights),
                    state=rp.state,
                    deleted_at=rp.deleted_at,
                )
                updated.validate_write_time()
                self.sys.recall_point_repo.update(s, updated)
                changed += 1

            pruned_missing_source_instance = False
            if from_inst.presence == InstancePresence.MISSING:
                has_active_source_refs = any(
                    rp.state == RecallPointState.ACTIVE
                    and rp.anchor is not None
                    and id_canonical_text(rp.anchor.instance_id) == want_from
                    for rp in self.sys.recall_point_repo.all(s)
                )
                if not has_active_source_refs:
                    try:
                        self.sys.instance_repo.delete(s, from_instance_id)
                    except PreconditionFailure:
                        # Tombstoned or historical references can still retain the old anchor.
                        # In that case we keep the instance record, but the UI can stop treating it
                        # as actionable once no ACTIVE recall points remain.
                        pass
                    else:
                        pruned_missing_source_instance = True

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
                    "prunedMissingSourceInstance": pruned_missing_source_instance,
                },
            )

            self.sys.commit(s)
            self._best_effort_drive_idle_orchestration(project_id)
            return changed
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    def sync_material_tree(
        self,
        project_id: ProjectId,
        media_exts: Tuple[str, ...] = ("mp4",),
        allow_empty: bool = False,
        instance_id_remap: Optional[Tuple[Tuple[InstanceId, InstanceId], ...]] = None,
    ) -> None:
        raise PreconditionFailure("sync_material_tree is disabled (not in spec whitelist)")

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
        return self._roll_up_phase_a_for_candidates(
            s,
            source_layer_index=target_layer_index,
            candidate_node_ids=tuple(candidates),
            title=title,
        )

    def _roll_up_phase_a_for_candidates(
        self,
        s: MutationSession,
        source_layer_index: int,
        candidate_node_ids: Tuple[LearningTaskNodeId, ...],
        title: str,
    ) -> tuple[Optional[LearningTaskNodeId], Tuple[LearningTaskNodeId, ...], bool]:
        self.sys.layer_repo.get_by_index(s, source_layer_index)

        pending = self._get_pending_roll_up_parent_node_id(s, source_layer_index)
        if pending is not None:
            return (pending, tuple(), False)

        if not candidate_node_ids:
            return (None, tuple(), False)

        current_ids = self.sys.aggq_repo.current_ids(s, source_layer_index)
        current_keys = {id_canonical_text(nid) for nid in current_ids}
        candidate_keys = [id_canonical_text(nid) for nid in candidate_node_ids]
        if len(candidate_keys) != len(set(candidate_keys)):
            raise PreconditionFailure("candidate_node_ids must not contain duplicates")
        if not set(candidate_keys).issubset(current_keys):
            raise PreconditionFailure("candidate_node_ids must be subset of source aggregation queue current ids")

        candidate_set = set(candidate_node_ids)
        for nid in candidate_node_ids:
            cur = self.sys.learning_task_node_repo.get(s, nid)
            while cur.parent_id is not None:
                pid = cur.parent_id
                if pid in candidate_set:
                    raise PreconditionFailure("candidate_node_ids contains ancestor/descendant mix")
                cur = self.sys.learning_task_node_repo.get(s, pid)

        queue = self.sys.aggq_repo.get(s, source_layer_index)
        historical_ids = tuple(queue.node_ids[: queue.head_index])
        remaining_current_ids = tuple(
            node_id for node_id in current_ids if id_canonical_text(node_id) not in set(candidate_keys)
        )
        updated_queue = AggregationQueue(
            project_id=queue.project_id,
            layer_index=queue.layer_index,
            node_ids=historical_ids + remaining_current_ids,
            head_index=queue.head_index,
        )
        updated_queue.validate_local_invariants()
        s._staged.aggregation_queues[source_layer_index] = updated_queue

        parent_title = title.strip() if title and title.strip() else self._next_default_aggregation_title(s, source_layer_index)
        parent_node_id = self.sys.learning_task_node_repo.push_up(
            s, candidate_child_ids=tuple(candidate_node_ids), title=parent_title
        )

        self._set_pending_roll_up_parent_node_id(s, source_layer_index, parent_node_id)
        self._set_aggregation_cycle_state(s, source_layer_index, AggregationCycleState.CLEARING)
        return (parent_node_id, tuple(candidate_node_ids), True)

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
            for layer in self.sys.layer_repo.all(s):
                if self._get_aggregation_cycle_state(s, layer.layer_index) != AggregationCycleState.CLEARING:
                    continue
                if self._get_pending_roll_up_parent_node_id(s, layer.layer_index) is not None:
                    self._set_aggregation_cycle_state(s, layer.layer_index, AggregationCycleState.ROLL_UP)
                    return

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

                did_auto_roll_up = False
                for layer in self.sys.layer_repo.all(s):
                    if self._enter_clearing_if_auto_roll_up_available(s, layer.layer_index):
                        did_auto_roll_up = True
                        break
                if did_auto_roll_up:
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
        items: Sequence[
            tuple[RichContent, RichContent, Anchor | None]
            | tuple[RichContent, RichContent, Anchor | None, tuple[RecallPointId, ...]]
        ],
        title: str,
    ) -> LearningTaskNodeId:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            if not self.sys.queue_repo.is_empty(s):
                raise PreconditionFailure("Gate: queue not empty; submit_learning_task forbidden")
            self._raise_if_actionable_missing_instances(s)
            target_layer_index = 0

            normalized_items: list[tuple[RichContent, RichContent, Anchor | None, tuple[RecallPointId, ...]]] = []
            for raw_item in items:
                if len(raw_item) == 3:
                    question, answer, anchor = raw_item
                    references = tuple()
                else:
                    question, answer, anchor, references = raw_item
                normalized_items.append((question, answer, anchor, tuple(references)))

            for index, (_, _, anchor, _) in enumerate(normalized_items):
                self._validate_anchor_for_project_type(
                    s,
                    anchor=anchor,
                    api_name="submit_learning_task",
                    field_name=f"items[{index}].anchor",
                )

            li = [
                LearningItem(question=q, answer=a, anchor=anc, references=references)
                for (q, a, anc, references) in normalized_items
            ]
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
                payload={"itemsCount": len(normalized_items), "entryNodeId": str(entry_node_id)},
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
        anchor: Anchor | None,
    ) -> None:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            cur = self.sys.recall_point_repo.get(s, recall_point_id)
            self._validate_anchor_for_project_type(s, anchor=anchor, api_name="edit_recall_point")
            rp = RecallPoint(
                project_id=project_id,
                recall_point_id=recall_point_id,
                created_at=cur.created_at,
                question=question,
                answer=answer,
                anchor=anchor,
                references=tuple(cur.references),
                insights=tuple(cur.insights),
                state=cur.state,
                deleted_at=cur.deleted_at,
            )
            self.sys.recall_point_repo.update(s, rp)
            self._append_audit_event(
                s,
                kind=AuditEventKind.EDIT_RECALL_POINT,
                api_name="edit_recall_point",
                payload={"recallPointId": str(recall_point_id)},
            )
            self.sys.commit(s)
            self._best_effort_drive_idle_orchestration(project_id)
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
            self._best_effort_drive_idle_orchestration(project_id)
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

    def edit_learning_task_node_title(self, project_id: ProjectId, node_id: LearningTaskNodeId, title: str) -> None:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            if title is None or not str(title).strip():
                raise PreconditionFailure("edit_learning_task_node_title.title must be non-empty")

            node = self.sys.learning_task_node_repo.get(s, node_id)
            if isinstance(node, LearningTaskLeaf):
                raise PreconditionFailure("Leaf learning task nodes must be renamed through edit_learning_task")

            updated_node = LearningTaskContainer(
                project_id=node.project_id,
                node_id=node.node_id,
                parent_id=node.parent_id,
                children=tuple(node.children),
                title=str(title).strip(),
                node_origin=node.node_origin,
            )
            updated_node.validate_write_time()

            self.sys.learning_task_node_repo.update(s, updated_node)

            self._append_audit_event(
                s,
                kind=AuditEventKind.EDIT_LEARNING_TASK_NODE,
                api_name="edit_learning_task_node_title",
                payload={"nodeId": str(node_id)},
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
        threshold_roll_up_enabled: Optional[bool] = None,
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
                threshold_roll_up_enabled=(
                    threshold_roll_up_enabled
                    if threshold_roll_up_enabled is not None
                    else bool(cur_layer_cfg.threshold_roll_up_enabled)
                ),
            )
            next_layer_cfg.validate_write_time()

            layer_configs = dict(cfg.layer_configs)
            layer_configs[int(layer_index)] = next_layer_cfg
            next_cfg = ProjectConfig(
                project_id=cfg.project_id,
                project_type=cfg.project_type,
                layer_configs=layer_configs,
                push_config=cfg.push_config,
                roll_up_strategy=cfg.roll_up_strategy,
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

    def set_project_roll_up_strategy(self, project_id: ProjectId, roll_up_strategy: RollUpStrategy) -> None:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            cfg = self.sys.project_config_repo.get(s)
            next_cfg = ProjectConfig(
                project_id=cfg.project_id,
                project_type=cfg.project_type,
                layer_configs=dict(cfg.layer_configs),
                push_config=cfg.push_config,
                roll_up_strategy=roll_up_strategy,
                updated_at=now_utc_ms(),
            )
            next_cfg.validate_write_time()
            self.sys.project_config_repo.set(s, next_cfg)
            self._append_audit_event(
                s,
                kind=AuditEventKind.EDIT_PROJECT_CONFIG,
                api_name="set_project_roll_up_strategy",
                payload={"rollUpStrategy": roll_up_strategy.value},
            )
            self.sys.commit(s)
            self._best_effort_drive_idle_orchestration(project_id)
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    def set_review_recommendation_config(
        self,
        project_id: ProjectId,
        *,
        min_recall_points_to_enable: Optional[int] = None,
        max_history_len: Optional[int] = None,
        recommended_batch_size: Optional[int] = None,
        forgetting_curve_decay_per_day: Optional[float] = None,
    ) -> None:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            cfg = self.sys.project_config_repo.get(s)
            cur_push_cfg = cfg.push_config
            next_push_cfg = type(cur_push_cfg)(
                min_recall_points_to_enable=(
                    int(min_recall_points_to_enable)
                    if min_recall_points_to_enable is not None
                    else int(cur_push_cfg.min_recall_points_to_enable)
                ),
                max_history_len=int(max_history_len) if max_history_len is not None else int(cur_push_cfg.max_history_len),
                recommended_batch_size=(
                    int(recommended_batch_size)
                    if recommended_batch_size is not None
                    else int(cur_push_cfg.recommended_batch_size)
                ),
                forgetting_curve_decay_per_day=(
                    float(forgetting_curve_decay_per_day)
                    if forgetting_curve_decay_per_day is not None
                    else float(cur_push_cfg.forgetting_curve_decay_per_day)
                ),
            )
            next_push_cfg.validate_write_time()

            next_cfg = ProjectConfig(
                project_id=cfg.project_id,
                project_type=cfg.project_type,
                layer_configs=dict(cfg.layer_configs),
                push_config=next_push_cfg,
                roll_up_strategy=cfg.roll_up_strategy,
                updated_at=now_utc_ms(),
            )
            next_cfg.validate_write_time()

            self.sys.project_config_repo.set(s, next_cfg)
            self._append_audit_event(
                s,
                kind=AuditEventKind.EDIT_PROJECT_CONFIG,
                api_name="set_review_recommendation_config",
                payload={
                    "minRecallPointsToEnable": int(next_push_cfg.min_recall_points_to_enable),
                    "maxHistoryLen": int(next_push_cfg.max_history_len),
                    "recommendedBatchSize": int(next_push_cfg.recommended_batch_size),
                    "forgettingCurveDecayPerDay": float(next_push_cfg.forgetting_curve_decay_per_day),
                },
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
            self._raise_if_actionable_missing_instances(s)
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

    @staticmethod
    def _truncate_review_history(
        records: Sequence[RecallPointReviewRecord], max_history_len: int
    ) -> Tuple[RecallPointReviewRecord, ...]:
        if int(max_history_len) <= 0:
            return tuple()
        if len(records) <= int(max_history_len):
            return tuple(records)
        return tuple(records[-int(max_history_len) :])

    @staticmethod
    def _age_days(from_ts: datetime, to_ts: datetime) -> float:
        seconds = (to_ts - from_ts).total_seconds()
        if seconds <= 0:
            return 0.0
        return float(seconds) / 86400.0

    @staticmethod
    def _clamp_probability(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
        return max(float(minimum), min(float(maximum), float(value)))

    @staticmethod
    def _mastery_at(*, mastery_after_review: float, half_life_days: float, last_reviewed_at: datetime, now: datetime) -> float:
        dt_days = SystemAPI._age_days(last_reviewed_at, now)
        decay = math.pow(0.5, dt_days / max(float(half_life_days), _MEMORY_MIN_HALFLIFE_DAYS))
        return SystemAPI._clamp_probability(
            _MEMORY_MASTERY_FLOOR + (float(mastery_after_review) - _MEMORY_MASTERY_FLOOR) * decay
        )

    @staticmethod
    def _bayes_update(prior: float, *, can_recall: bool) -> float:
        prior = SystemAPI._clamp_probability(prior)
        if can_recall:
            numerator = prior * (1.0 - _MEMORY_FALSE_NEGATIVE)
            denominator = numerator + (1.0 - prior) * _MEMORY_FALSE_POSITIVE
        else:
            numerator = prior * _MEMORY_FALSE_NEGATIVE
            denominator = numerator + (1.0 - prior) * (1.0 - _MEMORY_FALSE_POSITIVE)
        if denominator <= 0:
            return prior
        return SystemAPI._clamp_probability(numerator / denominator)

    def _compute_probabilistic_memory_metrics(
        self,
        *,
        records: Sequence[RecallPointReviewRecord],
        calculated_at: datetime,
    ) -> tuple[float, float]:
        if not records:
            return 0.0, 0.0

        mastery_after_review = float(_MEMORY_INITIAL_MASTERY)
        half_life_days = float(_MEMORY_INITIAL_HALFLIFE_DAYS)
        previous_at = records[0].occurred_at
        known_count = 0

        for record in records:
            recall_before_review = self._mastery_at(
                mastery_after_review=mastery_after_review,
                half_life_days=half_life_days,
                last_reviewed_at=previous_at,
                now=record.occurred_at,
            )
            can_recall = record.result == RecallPointReviewResult.CAN_RECALL
            post_observation = self._bayes_update(recall_before_review, can_recall=can_recall)
            learning_gain = _MEMORY_LEARN_KNOWN if can_recall else _MEMORY_LEARN_UNKNOWN
            mastery_after_review = self._clamp_probability(
                post_observation + (1.0 - post_observation) * learning_gain,
                _MEMORY_MASTERY_FLOOR,
                0.99,
            )

            if can_recall:
                known_count += 1
                half_life_days *= 1.0 + _MEMORY_HALFLIFE_GROW * (1.0 - recall_before_review)
            else:
                half_life_days *= 1.0 - _MEMORY_HALFLIFE_SHRINK * recall_before_review
            half_life_days = max(_MEMORY_MIN_HALFLIFE_DAYS, min(_MEMORY_MAX_HALFLIFE_DAYS, half_life_days))
            previous_at = record.occurred_at

        estimated_memory_strength = self._mastery_at(
            mastery_after_review=mastery_after_review,
            half_life_days=half_life_days,
            last_reviewed_at=previous_at,
            now=calculated_at,
        )
        weighted_success_ratio = float(known_count) / float(len(records))
        return float(weighted_success_ratio), float(estimated_memory_strength)

    def _compute_recall_point_review_metrics(
        self,
        s: MutationSession,
        *,
        rp: RecallPoint,
        cfg: ProjectConfig,
        calculated_at: datetime,
    ) -> tuple[
        float,
        float,
        Optional[datetime],
        Optional[RecallPointReviewResult],
        int,
        Tuple[RecallPointReviewRecord, ...],
    ]:
        all_records = self.sys.recall_point_review_record_repo.all_by_recall_point(s, rp.recall_point_id)
        history_window_size = int(cfg.push_config.max_history_len)
        records = self._truncate_review_history(all_records, history_window_size)
        total_review_count = len(all_records)
        if not records:
            return 0.0, 0.0, None, None, total_review_count, tuple()

        weighted_success_ratio, estimated_memory_strength = self._compute_probabilistic_memory_metrics(
            records=records,
            calculated_at=calculated_at,
        )
        last_record = records[-1]
        return (
            float(weighted_success_ratio),
            float(estimated_memory_strength),
            last_record.occurred_at,
            last_record.result,
            total_review_count,
            tuple(records),
        )

    @staticmethod
    def _recommendation_sort_key(item: RecallPointReviewRecommendation) -> tuple[float, datetime, str]:
        last_reviewed_at = item.last_reviewed_at
        if last_reviewed_at is None:
            last_reviewed_at = datetime.min.replace(tzinfo=timezone.utc)
        return (
            -float(item.review_recommendation_index),
            last_reviewed_at,
            id_canonical_text(item.recall_point.recall_point_id),
        )

    def _build_recall_point_review_recommendation(
        self,
        s: MutationSession,
        *,
        rp: RecallPoint,
        cfg: ProjectConfig,
        calculated_at: datetime,
    ) -> RecallPointReviewRecommendation:
        (
            weighted_success_ratio,
            estimated_memory_strength,
            last_reviewed_at,
            last_review_result,
            total_review_count,
            _,
        ) = self._compute_recall_point_review_metrics(s, rp=rp, cfg=cfg, calculated_at=calculated_at)
        review_recommendation_index = 100.0 * (1.0 - estimated_memory_strength)
        return RecallPointReviewRecommendation(
            recall_point=rp,
            review_recommendation_index=float(review_recommendation_index),
            estimated_memory_strength=float(estimated_memory_strength),
            weighted_success_ratio=float(weighted_success_ratio),
            last_reviewed_at=last_reviewed_at,
            last_review_result=last_review_result,
            review_count=int(total_review_count),
        )

    # 4.5.8
    def get_push_candidates(self, project_id: ProjectId, max_results: int) -> Tuple[RecallPointId, ...]:
        if int(max_results) <= 0:
            raise PreconditionFailure("get_push_candidates.max_results must be >= 1")
        page = self.list_review_recommendations(project_id, offset=0, limit=int(max_results))
        return tuple(item.recall_point.recall_point_id for item in page.items)

    def list_review_recommendations(
        self,
        project_id: ProjectId,
        offset: int = 0,
        limit: Optional[int] = None,
    ) -> RecallPointReviewRecommendationPage:
        if int(offset) < 0:
            raise PreconditionFailure("list_review_recommendations.offset must be >= 0")

        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            cfg = self.sys.project_config_repo.get(s)
            page_limit = int(cfg.push_config.recommended_batch_size) if limit is None else int(limit)
            if page_limit <= 0:
                raise PreconditionFailure("list_review_recommendations.limit must be >= 1")

            rps = tuple(rp for rp in self.sys.recall_point_repo.all(s) if rp.state == RecallPointState.ACTIVE)
            if len(rps) < int(cfg.push_config.min_recall_points_to_enable):
                return RecallPointReviewRecommendationPage(
                    items=tuple(),
                    total_count=0,
                    offset=int(offset),
                    limit=page_limit,
                    next_offset=None,
                )

            calculated_at = now_utc_ms()
            items = tuple(
                self._build_recall_point_review_recommendation(s, rp=rp, cfg=cfg, calculated_at=calculated_at)
                for rp in rps
            )
            sorted_items = tuple(sorted(items, key=self._recommendation_sort_key))
            total_count = len(sorted_items)
            start = min(int(offset), total_count)
            end = min(start + page_limit, total_count)
            next_offset = end if end < total_count else None
            return RecallPointReviewRecommendationPage(
                items=sorted_items[start:end],
                total_count=total_count,
                offset=start,
                limit=page_limit,
                next_offset=next_offset,
            )
        finally:
            self.sys.rollback(s)

    def get_recall_point_review_projection(
        self,
        project_id: ProjectId,
        recall_point_id: RecallPointId,
    ) -> RecallPointReviewProjection:
        s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
        try:
            cfg = self.sys.project_config_repo.get(s)
            rp = self.sys.recall_point_repo.get(s, recall_point_id)
            calculated_at = now_utc_ms()
            (
                weighted_success_ratio,
                estimated_memory_strength,
                last_reviewed_at,
                last_review_result,
                total_review_count,
                records,
            ) = self._compute_recall_point_review_metrics(s, rp=rp, cfg=cfg, calculated_at=calculated_at)
            history = tuple(
                RecallPointReviewHistoryItem(
                    review_task_id=record.review_task_id,
                    occurred_at=record.occurred_at,
                    result=record.result,
                )
                for record in records
            )
            return RecallPointReviewProjection(
                recall_point_id=rp.recall_point_id,
                calculated_at=calculated_at,
                review_recommendation_index=float(100.0 * (1.0 - estimated_memory_strength)),
                estimated_memory_strength=float(estimated_memory_strength),
                weighted_success_ratio=float(weighted_success_ratio),
                forgetting_curve_decay_per_day=float(cfg.push_config.forgetting_curve_decay_per_day),
                history_window_size=int(cfg.push_config.max_history_len),
                last_reviewed_at=last_reviewed_at,
                last_review_result=last_review_result,
                review_count=int(total_review_count),
                history=history,
            )
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
        service_config: LocalServiceConfig | dict[str, object] | None = None,
        auth_store: AuthStore | None = None,
        user_id: str | None = None,
    ) -> AsrTranscriptResult:
        s.assert_open()
        if s.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("request_asr requires READ_WRITE session")

        if int(pre_ms) < 0 or int(post_ms) < 0:
            raise PreconditionFailure("request_asr precondition failed: pre_ms/post_ms must be >= 0")
        if int(pre_ms) + int(post_ms) > MAX_ASR_WINDOW_MS:
            raise PreconditionFailure(f"request_asr window too large (max {MAX_ASR_WINDOW_MS}ms)")

        rp, inst = self._resolve_request_asr_context(s, recall_point_id=recall_point_id)
        storage = self.sys.project_storage_config_repo.get(s)
        binding = self.sys.project_material_source_binding_repo.get(s)
        if binding.source_kind == MaterialSourceKind.BROWSER_LOCAL:
            raise PreconditionFailure("request_asr server extraction is unavailable for BROWSER_LOCAL materials; upload an audio clip instead")
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

        resolved_service_config, _ = self._resolve_effective_asr_service_config(
            service_config=service_config,
            auth_store=auth_store,
            user_id=user_id,
        )
        if resolved_service_config is None:
            raise PreconditionFailure("request_asr service_config is unavailable")

        clip_start_ms = max(int(center_ms) - int(pre_ms), 0)
        clip_duration_ms = int(pre_ms) + int(post_ms)
        if is_builtin_whisper_base_url(resolved_service_config.base_url):
            segments = self._request_asr_segments_from_audio_file(
                audio_path=file_path,
                audio_file_name=file_path.name,
                audio_content_type="application/octet-stream",
                clip_start_ms=clip_start_ms,
                clip_duration_ms=clip_duration_ms,
                center_ms=int(center_ms),
                pre_ms=int(pre_ms),
                post_ms=int(post_ms),
                provider=provider,
                service_config=resolved_service_config,
                builtin_source={
                    "filePath": str(file_path),
                    "instanceId": str(inst.instance_id),
                    "materialId": inst.material_id.as_posix(),
                },
            )
            result = self._build_asr_result(
                project_id=s.project_id,
                provider=provider,
                recall_point_id=recall_point_id,
                source_instance_id=rp.anchor.instance_id,
                center_ms=int(center_ms),
                pre_ms=int(pre_ms),
                post_ms=int(post_ms),
                segments=segments,
            )
            try:
                result.validate_write_time()
            except PreconditionFailure as e:
                raise ExternalServiceError(f"ASR output invalid: {e}") from e
            return result

        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            raise PreconditionFailure("request_asr precondition failed: ffmpeg not found in PATH")

        with _asr_server_ffmpeg_slot():
            with tempfile.TemporaryDirectory(prefix="learningpyramid-asr-") as tmpdir:
                audio_path = Path(tmpdir) / "clip.wav"
                try:
                    self._extract_audio_clip(
                        ffmpeg_bin=ffmpeg_bin,
                        source_path=file_path,
                        start_ms=clip_start_ms,
                        duration_ms=clip_duration_ms,
                        out_path=audio_path,
                        timeout_sec=float(ASR_SERVER_FFMPEG_EXEC_TIMEOUT_SEC),
                    )
                except subprocess.TimeoutExpired as exc:
                    raise PreconditionFailure("request_asr precondition failed: server-side ffmpeg timed out") from exc
                except subprocess.CalledProcessError as exc:
                    detail = (exc.stderr or exc.stdout or "ffmpeg failed").strip()
                    raise PreconditionFailure(f"request_asr precondition failed: failed to extract audio clip: {detail[:400]}") from exc

                segments = self._request_asr_segments_from_audio_file(
                    audio_path=audio_path,
                    audio_file_name="clip.wav",
                    audio_content_type="audio/wav",
                    clip_start_ms=clip_start_ms,
                    clip_duration_ms=clip_duration_ms,
                    center_ms=int(center_ms),
                    pre_ms=int(pre_ms),
                    post_ms=int(post_ms),
                    provider=provider,
                    service_config=resolved_service_config,
                    builtin_source={
                        "filePath": str(file_path),
                        "instanceId": str(inst.instance_id),
                        "materialId": inst.material_id.as_posix(),
                    },
                )

        result = self._build_asr_result(
            project_id=s.project_id,
            provider=provider,
            recall_point_id=recall_point_id,
            source_instance_id=rp.anchor.instance_id,
            center_ms=int(center_ms),
            pre_ms=int(pre_ms),
            post_ms=int(post_ms),
            segments=segments,
        )
        try:
            result.validate_write_time()
        except PreconditionFailure as e:
            raise ExternalServiceError(f"ASR output invalid: {e}") from e
        return result

    def _request_asr_from_audio_upload_in_session(
        self,
        s: MutationSession,
        *,
        recall_point_id: RecallPointId,
        center_ms: int,
        pre_ms: int,
        post_ms: int,
        provider: AsrProvider,
        audio_bytes: bytes,
        audio_filename: str | None = None,
        audio_content_type: str | None = None,
        service_config: LocalServiceConfig | dict[str, object] | None = None,
        auth_store: AuthStore | None = None,
        user_id: str | None = None,
    ) -> AsrTranscriptResult:
        s.assert_open()
        if s.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("request_asr requires READ_WRITE session")
        if int(pre_ms) < 0 or int(post_ms) < 0:
            raise PreconditionFailure("request_asr precondition failed: pre_ms/post_ms must be >= 0")
        if int(pre_ms) + int(post_ms) > MAX_ASR_WINDOW_MS:
            raise PreconditionFailure(f"request_asr window too large (max {MAX_ASR_WINDOW_MS}ms)")

        payload = bytes(audio_bytes or b"")
        if not payload:
            raise PreconditionFailure("request_asr audio clip must be non-empty")
        if len(payload) > MAX_ASR_UPLOAD_BYTES:
            raise PreconditionFailure(f"request_asr audio clip is too large (max {MAX_ASR_UPLOAD_BYTES} bytes)")

        rp, _ = self._resolve_request_asr_context(s, recall_point_id=recall_point_id)
        resolved_service_config, _ = self._resolve_effective_asr_service_config(
            service_config=service_config,
            auth_store=auth_store,
            user_id=user_id,
        )
        if resolved_service_config is None:
            raise PreconditionFailure("request_asr service_config is unavailable")

        clip_start_ms = max(int(center_ms) - int(pre_ms), 0)
        clip_duration_ms = int(pre_ms) + int(post_ms)
        safe_name = Path(str(audio_filename or "clip.wav")).name or "clip.wav"
        content_type = str(audio_content_type or "application/octet-stream").strip() or "application/octet-stream"
        suffix = Path(safe_name).suffix or ".bin"

        with tempfile.TemporaryDirectory(prefix="learningpyramid-asr-upload-") as tmpdir:
            audio_path = Path(tmpdir) / f"upload{suffix}"
            audio_path.write_bytes(payload)
            segments = self._request_asr_segments_from_audio_file(
                audio_path=audio_path,
                audio_file_name=safe_name,
                audio_content_type=content_type,
                clip_start_ms=clip_start_ms,
                clip_duration_ms=clip_duration_ms,
                center_ms=int(center_ms),
                pre_ms=int(pre_ms),
                post_ms=int(post_ms),
                provider=provider,
                service_config=resolved_service_config,
                builtin_source=None,
            )

        result = self._build_asr_result(
            project_id=s.project_id,
            provider=provider,
            recall_point_id=recall_point_id,
            source_instance_id=rp.anchor.instance_id,
            center_ms=int(center_ms),
            pre_ms=int(pre_ms),
            post_ms=int(post_ms),
            segments=segments,
        )
        try:
            result.validate_write_time()
        except PreconditionFailure as e:
            raise ExternalServiceError(f"ASR output invalid: {e}") from e
        return result

    def _request_instance_asr_in_session(
        self,
        s: MutationSession,
        *,
        instance_id: InstanceId,
        start_ms: int,
        end_ms: int,
        provider: AsrProvider,
        service_config: LocalServiceConfig | dict[str, object] | None = None,
        auth_store: AuthStore | None = None,
        user_id: str | None = None,
    ) -> InstanceAsrTranscriptResult:
        s.assert_open()
        if s.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("request_instance_asr requires READ_WRITE session")

        start_ms, end_ms = self._validate_instance_asr_window(
            api_name="request_instance_asr",
            start_ms=int(start_ms),
            end_ms=int(end_ms),
        )

        inst = self._resolve_instance_asr_context(s, instance_id=instance_id)
        storage = self.sys.project_storage_config_repo.get(s)
        binding = self.sys.project_material_source_binding_repo.get(s)
        if binding.source_kind == MaterialSourceKind.BROWSER_LOCAL:
            raise PreconditionFailure(
                "request_instance_asr server extraction is unavailable for BROWSER_LOCAL materials; upload an audio clip instead"
            )
        try:
            file_path = resolve_material_file_path(storage, inst.material_id, source_kind=binding.source_kind)
        except PreconditionFailure as exc:
            raise PreconditionFailure(f"request_instance_asr precondition failed: {exc}") from exc

        if not file_path.exists() or not file_path.is_file():
            raise PreconditionFailure("request_instance_asr precondition failed: material file not found")

        ext = file_path.suffix.lower()
        allowed = {".mp4", ".mov", ".mkv", ".webm", ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
        if ext not in allowed:
            raise PreconditionFailure(
                f"request_instance_asr precondition failed: unsupported material type: {ext or '(no ext)'}"
            )

        resolved_service_config, _ = self._resolve_effective_asr_service_config(
            service_config=service_config,
            auth_store=auth_store,
            user_id=user_id,
        )
        if resolved_service_config is None:
            raise PreconditionFailure("request_instance_asr service_config is unavailable")

        clip_start_ms = int(start_ms)
        clip_duration_ms = int(end_ms) - int(start_ms)
        if is_builtin_whisper_base_url(resolved_service_config.base_url):
            segments = self._request_asr_segments_from_audio_file(
                audio_path=file_path,
                audio_file_name=file_path.name,
                audio_content_type="application/octet-stream",
                clip_start_ms=clip_start_ms,
                clip_duration_ms=clip_duration_ms,
                center_ms=clip_start_ms,
                pre_ms=0,
                post_ms=clip_duration_ms,
                provider=provider,
                service_config=resolved_service_config,
                builtin_source={
                    "filePath": str(file_path),
                    "instanceId": str(inst.instance_id),
                    "materialId": inst.material_id.as_posix(),
                },
            )
            result = self._build_instance_asr_result(
                project_id=s.project_id,
                provider=provider,
                source_instance_id=inst.instance_id,
                start_ms=start_ms,
                end_ms=end_ms,
                segments=segments,
            )
            try:
                result.validate_write_time()
            except PreconditionFailure as e:
                raise ExternalServiceError(f"ASR output invalid: {e}") from e
            return result

        ffmpeg_bin = shutil.which("ffmpeg")
        if not ffmpeg_bin:
            raise PreconditionFailure("request_instance_asr precondition failed: ffmpeg not found in PATH")

        with _asr_server_ffmpeg_slot("request_instance_asr"):
            with tempfile.TemporaryDirectory(prefix="learningpyramid-instance-asr-") as tmpdir:
                audio_path = Path(tmpdir) / "clip.wav"
                try:
                    self._extract_audio_clip(
                        ffmpeg_bin=ffmpeg_bin,
                        source_path=file_path,
                        start_ms=clip_start_ms,
                        duration_ms=clip_duration_ms,
                        out_path=audio_path,
                        timeout_sec=float(ASR_SERVER_FFMPEG_EXEC_TIMEOUT_SEC),
                    )
                except subprocess.TimeoutExpired as exc:
                    raise PreconditionFailure("request_instance_asr precondition failed: server-side ffmpeg timed out") from exc
                except subprocess.CalledProcessError as exc:
                    detail = (exc.stderr or exc.stdout or "ffmpeg failed").strip()
                    raise PreconditionFailure(
                        f"request_instance_asr precondition failed: failed to extract audio clip: {detail[:400]}"
                    ) from exc

                segments = self._request_asr_segments_from_audio_file(
                    audio_path=audio_path,
                    audio_file_name="clip.wav",
                    audio_content_type="audio/wav",
                    clip_start_ms=clip_start_ms,
                    clip_duration_ms=clip_duration_ms,
                    center_ms=clip_start_ms,
                    pre_ms=0,
                    post_ms=clip_duration_ms,
                    provider=provider,
                    service_config=resolved_service_config,
                    builtin_source={
                        "filePath": str(file_path),
                        "instanceId": str(inst.instance_id),
                        "materialId": inst.material_id.as_posix(),
                    },
                )

        result = self._build_instance_asr_result(
            project_id=s.project_id,
            provider=provider,
            source_instance_id=inst.instance_id,
            start_ms=start_ms,
            end_ms=end_ms,
            segments=segments,
        )
        try:
            result.validate_write_time()
        except PreconditionFailure as e:
            raise ExternalServiceError(f"ASR output invalid: {e}") from e
        return result

    def _request_instance_asr_from_audio_upload_in_session(
        self,
        s: MutationSession,
        *,
        instance_id: InstanceId,
        start_ms: int,
        end_ms: int,
        provider: AsrProvider,
        audio_bytes: bytes,
        audio_filename: str | None = None,
        audio_content_type: str | None = None,
        service_config: LocalServiceConfig | dict[str, object] | None = None,
        auth_store: AuthStore | None = None,
        user_id: str | None = None,
    ) -> InstanceAsrTranscriptResult:
        s.assert_open()
        if s.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("request_instance_asr requires READ_WRITE session")

        start_ms, end_ms = self._validate_instance_asr_window(
            api_name="request_instance_asr",
            start_ms=int(start_ms),
            end_ms=int(end_ms),
        )

        payload = bytes(audio_bytes or b"")
        if not payload:
            raise PreconditionFailure("request_instance_asr audio clip must be non-empty")
        if len(payload) > MAX_ASR_UPLOAD_BYTES:
            raise PreconditionFailure(f"request_instance_asr audio clip is too large (max {MAX_ASR_UPLOAD_BYTES} bytes)")

        inst = self._resolve_instance_asr_context(s, instance_id=instance_id)
        resolved_service_config, _ = self._resolve_effective_asr_service_config(
            service_config=service_config,
            auth_store=auth_store,
            user_id=user_id,
        )
        if resolved_service_config is None:
            raise PreconditionFailure("request_instance_asr service_config is unavailable")

        clip_start_ms = int(start_ms)
        clip_duration_ms = int(end_ms) - int(start_ms)
        safe_name = Path(str(audio_filename or "chunk.wav")).name or "chunk.wav"
        content_type = str(audio_content_type or "application/octet-stream").strip() or "application/octet-stream"
        suffix = Path(safe_name).suffix or ".bin"

        with tempfile.TemporaryDirectory(prefix="learningpyramid-instance-asr-upload-") as tmpdir:
            audio_path = Path(tmpdir) / f"upload{suffix}"
            audio_path.write_bytes(payload)
            segments = self._request_asr_segments_from_audio_file(
                audio_path=audio_path,
                audio_file_name=safe_name,
                audio_content_type=content_type,
                clip_start_ms=clip_start_ms,
                clip_duration_ms=clip_duration_ms,
                center_ms=clip_start_ms,
                pre_ms=0,
                post_ms=clip_duration_ms,
                provider=provider,
                service_config=resolved_service_config,
                builtin_source=None,
            )

        result = self._build_instance_asr_result(
            project_id=s.project_id,
            provider=provider,
            source_instance_id=inst.instance_id,
            start_ms=start_ms,
            end_ms=end_ms,
            segments=segments,
        )
        try:
            result.validate_write_time()
        except PreconditionFailure as e:
            raise ExternalServiceError(f"ASR output invalid: {e}") from e
        return result

    def request_asr(
        self,
        project_id: ProjectId,
        recall_point_id: RecallPointId,
        center_ms: int,
        pre_ms: int,
        post_ms: int,
        provider: AsrProvider = AsrProvider.WHISPER,
        service_config: LocalServiceConfig | dict[str, object] | None = None,
        auth_store: AuthStore | None = None,
        user_id: str | None = None,
    ) -> AsrTranscriptResult:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            prov = provider if isinstance(provider, AsrProvider) else AsrProvider(str(provider))
            _, service_config_source = self._resolve_effective_asr_service_config(
                service_config=service_config,
                auth_store=auth_store,
                user_id=user_id,
            )
            result = self._request_asr_in_session(
                s,
                recall_point_id=RecallPointId(str(recall_point_id)),
                center_ms=int(center_ms),
                pre_ms=int(pre_ms),
                post_ms=int(post_ms),
                provider=prov,
                service_config=service_config,
                auth_store=auth_store,
                user_id=user_id,
            )
            self._append_audit_event(
                s,
                kind=AuditEventKind.REQUEST_ASR,
                api_name="request_asr",
                payload={
                    "recallPointId": str(recall_point_id),
                    "provider": prov.value,
                    "producerRuntimeKind": s.runtime_kind.value,
                    "sourceInstanceId": str(result.source_instance_id),
                    "centerMs": int(center_ms),
                    "preMs": int(pre_ms),
                    "postMs": int(post_ms),
                    "segmentCount": len(result.segments),
                    "clipSource": "server_extract",
                    "serviceConfigSource": service_config_source,
                },
            )
            self.sys.commit(s)
            return result
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    def request_asr_from_audio_upload(
        self,
        project_id: ProjectId,
        recall_point_id: RecallPointId,
        center_ms: int,
        pre_ms: int,
        post_ms: int,
        audio_bytes: bytes,
        *,
        audio_filename: str | None = None,
        audio_content_type: str | None = None,
        provider: AsrProvider = AsrProvider.WHISPER,
        service_config: LocalServiceConfig | dict[str, object] | None = None,
        auth_store: AuthStore | None = None,
        user_id: str | None = None,
    ) -> AsrTranscriptResult:
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            prov = provider if isinstance(provider, AsrProvider) else AsrProvider(str(provider))
            payload = bytes(audio_bytes or b"")
            _, service_config_source = self._resolve_effective_asr_service_config(
                service_config=service_config,
                auth_store=auth_store,
                user_id=user_id,
            )
            result = self._request_asr_from_audio_upload_in_session(
                s,
                recall_point_id=RecallPointId(str(recall_point_id)),
                center_ms=int(center_ms),
                pre_ms=int(pre_ms),
                post_ms=int(post_ms),
                provider=prov,
                audio_bytes=payload,
                audio_filename=audio_filename,
                audio_content_type=audio_content_type,
                service_config=service_config,
                auth_store=auth_store,
                user_id=user_id,
            )
            self._append_audit_event(
                s,
                kind=AuditEventKind.REQUEST_ASR,
                api_name="request_asr_from_audio_upload",
                payload={
                    "recallPointId": str(recall_point_id),
                    "provider": prov.value,
                    "producerRuntimeKind": s.runtime_kind.value,
                    "sourceInstanceId": str(result.source_instance_id),
                    "centerMs": int(center_ms),
                    "preMs": int(pre_ms),
                    "postMs": int(post_ms),
                    "segmentCount": len(result.segments),
                    "clipSource": "browser_upload",
                    "uploadedBytes": len(payload),
                    "serviceConfigSource": service_config_source,
                },
            )
            self.sys.commit(s)
            return result
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    def request_instance_asr(
        self,
        project_id: ProjectId,
        instance_id: InstanceId,
        start_ms: int,
        end_ms: int,
        provider: AsrProvider = AsrProvider.WHISPER,
        service_config: LocalServiceConfig | dict[str, object] | None = None,
        auth_store: AuthStore | None = None,
        user_id: str | None = None,
    ) -> InstanceAsrTranscriptResult:
        self._ensure_startup_fs_sync_done(project_id)
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            prov = provider if isinstance(provider, AsrProvider) else AsrProvider(str(provider))
            _, service_config_source = self._resolve_effective_asr_service_config(
                service_config=service_config,
                auth_store=auth_store,
                user_id=user_id,
            )
            result = self._request_instance_asr_in_session(
                s,
                instance_id=InstanceId(str(instance_id)),
                start_ms=int(start_ms),
                end_ms=int(end_ms),
                provider=prov,
                service_config=service_config,
                auth_store=auth_store,
                user_id=user_id,
            )
            self._append_audit_event(
                s,
                kind=AuditEventKind.REQUEST_ASR,
                api_name="request_instance_asr",
                payload={
                    "instanceId": str(instance_id),
                    "provider": prov.value,
                    "producerRuntimeKind": s.runtime_kind.value,
                    "sourceInstanceId": str(result.source_instance_id),
                    "startMs": int(start_ms),
                    "endMs": int(end_ms),
                    "segmentCount": len(result.segments),
                    "clipSource": "server_extract",
                    "serviceConfigSource": service_config_source,
                },
            )
            self.sys.commit(s)
            return result
        except Exception:
            if s.state == SessionState.OPEN:
                self.sys.rollback(s)
            raise

    def request_instance_asr_from_audio_upload(
        self,
        project_id: ProjectId,
        instance_id: InstanceId,
        start_ms: int,
        end_ms: int,
        audio_bytes: bytes,
        *,
        audio_filename: str | None = None,
        audio_content_type: str | None = None,
        provider: AsrProvider = AsrProvider.WHISPER,
        service_config: LocalServiceConfig | dict[str, object] | None = None,
        auth_store: AuthStore | None = None,
        user_id: str | None = None,
    ) -> InstanceAsrTranscriptResult:
        s = self.sys.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            prov = provider if isinstance(provider, AsrProvider) else AsrProvider(str(provider))
            payload = bytes(audio_bytes or b"")
            _, service_config_source = self._resolve_effective_asr_service_config(
                service_config=service_config,
                auth_store=auth_store,
                user_id=user_id,
            )
            result = self._request_instance_asr_from_audio_upload_in_session(
                s,
                instance_id=InstanceId(str(instance_id)),
                start_ms=int(start_ms),
                end_ms=int(end_ms),
                provider=prov,
                audio_bytes=payload,
                audio_filename=audio_filename,
                audio_content_type=audio_content_type,
                service_config=service_config,
                auth_store=auth_store,
                user_id=user_id,
            )
            self._append_audit_event(
                s,
                kind=AuditEventKind.REQUEST_ASR,
                api_name="request_instance_asr_from_audio_upload",
                payload={
                    "instanceId": str(instance_id),
                    "provider": prov.value,
                    "producerRuntimeKind": s.runtime_kind.value,
                    "sourceInstanceId": str(result.source_instance_id),
                    "startMs": int(start_ms),
                    "endMs": int(end_ms),
                    "segmentCount": len(result.segments),
                    "clipSource": "browser_upload",
                    "uploadedBytes": len(payload),
                    "serviceConfigSource": service_config_source,
                },
            )
            self.sys.commit(s)
            return result
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
                if rp.state == RecallPointState.ACTIVE and rp.anchor is not None and id_canonical_text(rp.anchor.instance_id) in inst_set
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
                if rp.state == RecallPointState.ACTIVE and rp.anchor is not None and id_canonical_text(rp.anchor.instance_id) in inst_set:
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

    def list_recall_points(self, project_id: ProjectId) -> Tuple[RecallPoint, ...]:
        sql_store = self._sql_store()
        if sql_store is not None:
            items = sql_store.list_recall_points(str(project_id))
        else:
            s = self.sys.begin_session(project_id, SessionMode.READ_ONLY)
            try:
                items = self.sys.recall_point_repo.all(s)
            finally:
                self.sys.rollback(s)
        return tuple(
            sorted(
                (item for item in items if item.state == RecallPointState.ACTIVE),
                key=lambda item: (
                    int(item.created_at.timestamp() * 1000) if item.created_at is not None else 0,
                    id_canonical_text(item.recall_point_id),
                ),
            )
        )

    def search_recall_points(
        self,
        project_id: ProjectId,
        *,
        query: str | None = None,
        limit: int = 20,
    ) -> Tuple[RecallPoint, ...]:
        normalized_query = str(query or "").strip().lower()
        resolved_limit = max(1, min(int(limit), 50))
        sql_store = self._sql_store()
        if sql_store is not None:
            return sql_store.search_recall_points(str(project_id), query=normalized_query or None, limit=resolved_limit)
        out: list[RecallPoint] = []
        for item in reversed(self.list_recall_points(project_id)):
            if normalized_query:
                search_text = (
                    f"{item.recall_point_id} "
                    f"{self._rich_content_to_plain_text(item.question)} "
                    f"{self._rich_content_to_plain_text(item.answer)}"
                ).lower()
                if normalized_query not in search_text:
                    continue
            out.append(item)
            if len(out) >= resolved_limit:
                break
        return tuple(out)

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
    "initialize_book_learning_objects": SchedulingEffect.NONE,
    "initialize_book_learning_objects_from_subject_material": SchedulingEffect.NONE,
    "add_learning_object_leaf": SchedulingEffect.NONE,
    "add_learning_object_container": SchedulingEffect.NONE,
    "sync_learning_objects_from_fs": SchedulingEffect.NONE,
    "list_user_cloud_accounts": SchedulingEffect.NONE,
    "begin_baidu_netdisk_connect": SchedulingEffect.NONE,
    "complete_baidu_netdisk_connect": SchedulingEffect.NONE,
    "disable_baidu_netdisk_account": SchedulingEffect.NONE,
    "list_baidu_netdisk_files": SchedulingEffect.NONE,
    "import_learning_objects_from_baidu_netdisk": SchedulingEffect.NONE,
    "set_project_material_source_binding": SchedulingEffect.NONE,
    "list_missing_instances": SchedulingEffect.NONE,
    "list_recall_points_by_instance": SchedulingEffect.NONE,
    "get_instance_playback_descriptor": SchedulingEffect.NONE,
    "get_instance_hls_playlist": SchedulingEffect.NONE,
    "stream_instance_hls_segment": SchedulingEffect.NONE,
    "get_instance_subtitle_file_for_user": SchedulingEffect.NONE,
    "bulk_remap_recall_points_instance": SchedulingEffect.NONE,
    "submit_learning_task": SchedulingEffect.ORCHESTRATION_MUTATING,
    "get_learning_task": SchedulingEffect.NONE,
    "get_learning_task_entry_registration": SchedulingEffect.NONE,
    "get_learning_task_node_entry_registration": SchedulingEffect.NONE,
    "get_convergence": SchedulingEffect.NONE,
    "get_review_chain": SchedulingEffect.NONE,
    "get_review_chain_entry_registration": SchedulingEffect.NONE,
    "list_recall_points": SchedulingEffect.NONE,
    "search_recall_points": SchedulingEffect.NONE,
    "edit_recall_point": SchedulingEffect.NONE,
    "delete_recall_point": SchedulingEffect.NONE,
    "edit_learning_task": SchedulingEffect.NONE,
    "set_layer_config": SchedulingEffect.NONE,
    "set_project_roll_up_strategy": SchedulingEffect.ORCHESTRATION_MUTATING,
    "set_review_recommendation_config": SchedulingEffect.NONE,
    "executor_commit_review_task": SchedulingEffect.ORCHESTRATION_MUTATING,
    "manual_roll_up": SchedulingEffect.ORCHESTRATION_MUTATING,
    "export_recall_points_by_learning_object_node": SchedulingEffect.NONE,
    "export_recall_points_by_learning_task_node": SchedulingEffect.NONE,
    "export_asr_by_learning_object_node": SchedulingEffect.NONE,
    "export_asr_by_learning_task_node": SchedulingEffect.NONE,
    "request_asr": SchedulingEffect.NONE,
    "request_asr_from_audio_upload": SchedulingEffect.NONE,
    "request_instance_asr": SchedulingEffect.NONE,
    "request_instance_asr_from_audio_upload": SchedulingEffect.NONE,
    "list_review_recommendations": SchedulingEffect.NONE,
    "get_recall_point_review_projection": SchedulingEffect.NONE,
    "get_push_candidates": SchedulingEffect.NONE,
    "validate_material_reachable": SchedulingEffect.NONE,
    "validate_recall_point_ids_resolvable": SchedulingEffect.NONE,
}

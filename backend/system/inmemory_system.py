import json
import os
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Set, Tuple, TypeVar

from backend.models.aggregation_event import AggregationEvent
from backend.models.aggregation_queue import AggregationQueue
from backend.models.asr_artifact import AsrArtifact
from backend.models.constants import GLOBAL_QUEUE, MATERIAL_ALLOWLIST_V1
from backend.models.convergence import Convergence
from backend.models.audit_log_event import AuditLogEvent
from backend.models.entry_registration import EntryRegistration
from backend.models.enums import (
    AggregationCycleState,
    AuditEventKind,
    AuditResultCode,
    AsrProvider,
    ClientRuntimeKind,
    ConvergenceState,
    FsSyncPolicy,
    InstancePresence,
    LayerMode,
    LearningTaskNodeOrigin,
    MaterialSourceKind,
    ProjectState,
    ProjectType,
    RecallPointState,
    ReviewChainState,
    ReviewTaskState,
    RuntimeCapability,
    SessionMode,
)
from backend.models.errors import (
    CommitTimeValidationFailure,
    ConcurrencyConflictError,
    NotFound,
    PreconditionFailure,
    StructuralInconsistencyError,
    SessionClosedError,
)
from backend.models.global_settings import GlobalLlmSettings
from backend.models.idgen import InMemoryIdGenerator
from backend.models.instance import Instance
from backend.models.instance_media_binding import InstanceMediaBinding
from backend.models.instance_subtitle_file import InstanceSubtitleFile
from backend.models.layer import Layer
from backend.models.learning_object_node import LearningObjectContainer, LearningObjectLeaf, LearningObjectNode
from backend.models.learning_task import LearningTask
from backend.models.learning_task_node import LearningTaskContainer, LearningTaskLeaf, LearningTaskNode
from backend.models.material_allowlist import MaterialAllowlist
from backend.models.media_asset import MediaAsset
from backend.models.project import Project
from backend.models.project_config import (
    DEFAULT_AGGREGATION_K_NODE,
    DEFAULT_AGGREGATION_K_POINT,
    LayerConfig,
    ProjectConfig,
    default_layer_config,
    default_project_config,
    default_push_config,
)
from backend.models.project_material_source_binding import ProjectMaterialSourceBinding
from backend.models.project_storage_config import ProjectStorageConfig
from backend.models.range_snapshot import RangeSnapshot
from backend.models.recall_point import RecallPoint
from backend.models.recall_point_review_record import RecallPointReviewRecord
from backend.models.rich_content import RichContent, validate_rich_content_write_time
from backend.models.review_chain import ReviewChain
from backend.models.review_task import ReviewTask
from backend.models.review_task_queue import ReviewTaskQueue
from backend.models.study_material import StudyMaterial
from backend.models.subject_material_link import SubjectMaterialLink
from backend.system.persistence_json import SCHEMA_VERSION, decode_snapshot, encode_project_payload, encode_snapshot
from backend.system.persistence_store import JsonSnapshotStore, SnapshotStore
from backend.system.project_paths import allocate_project_root
from backend.system.runtime_features import default_client_runtime_kind, default_runtime_capabilities
from backend.models.types import (
    AsrArtifactId,
    ConvergenceId,
    InstanceId,
    LayerId,
    LearningObjectNodeId,
    LearningTaskId,
    LearningTaskNodeId,
    MediaAssetId,
    ProjectId,
    PurePath,
    RangeId,
    RecallPointId,
    ReviewChainId,
    ReviewTaskId,
    ReviewTaskQueueId,
    Timestamp,
    id_canonical_text,
    now_utc_ms,
)
from backend.models.video_watch_progress import VideoWatchProgress


@dataclass
class ProjectStore:
    project: Optional[Project] = None
    project_storage_config: Optional[ProjectStorageConfig] = None
    project_material_source_binding: Optional[ProjectMaterialSourceBinding] = None
    project_config: Optional[ProjectConfig] = None
    material_allowlist: Optional[MaterialAllowlist] = None
    study_materials: Dict[str, StudyMaterial] = field(default_factory=dict)
    study_materials_initialized: bool = False
    subject_material_link: Optional[SubjectMaterialLink] = None
    media_assets: Dict[str, MediaAsset] = field(default_factory=dict)
    audit_log_events: Dict[str, AuditLogEvent] = field(default_factory=dict)

    instances: Dict[str, Instance] = field(default_factory=dict)
    instance_media_bindings: Dict[str, InstanceMediaBinding] = field(default_factory=dict)
    instance_subtitle_files: Dict[str, InstanceSubtitleFile] = field(default_factory=dict)
    video_watch_progress: Dict[str, VideoWatchProgress] = field(default_factory=dict)
    learning_object_nodes: Dict[str, LearningObjectNode] = field(default_factory=dict)
    recall_points: Dict[str, RecallPoint] = field(default_factory=dict)
    recall_point_review_records: Dict[str, RecallPointReviewRecord] = field(default_factory=dict)
    learning_tasks: Dict[str, LearningTask] = field(default_factory=dict)
    learning_task_nodes: Dict[str, LearningTaskNode] = field(default_factory=dict)
    range_snapshots: Dict[str, RangeSnapshot] = field(default_factory=dict)
    asr_artifacts: Dict[str, AsrArtifact] = field(default_factory=dict)

    review_tasks: Dict[str, ReviewTask] = field(default_factory=dict)
    convergences: Dict[str, Convergence] = field(default_factory=dict)
    review_chains: Dict[str, ReviewChain] = field(default_factory=dict)
    review_task_queue: Optional[ReviewTaskQueue] = None

    layers: Dict[str, Layer] = field(default_factory=dict)  # by layer_id
    layers_by_index: Dict[int, str] = field(default_factory=dict)  # layer_index -> layer_id
    entry_regs: Dict[str, EntryRegistration] = field(default_factory=dict)  # by entry_node canonical
    aggregation_queues: Dict[int, AggregationQueue] = field(default_factory=dict)
    aggregation_events: Dict[str, AggregationEvent] = field(default_factory=dict)  # by event_id


@dataclass
class ProjectStaged:
    # Project object (system-level within this project_id scope)
    project: Optional[Project] = None  # staged replacement/creation
    delete_project: bool = False  # system-level delete marker (4.1.7)
    project_storage_config: Optional[ProjectStorageConfig] = None
    project_material_source_binding: Optional[ProjectMaterialSourceBinding] = None
    project_config: Optional[ProjectConfig] = None
    material_allowlist: Optional[MaterialAllowlist] = None
    study_materials: Dict[str, StudyMaterial] = field(default_factory=dict)
    study_materials_replaced: bool = False
    subject_material_link: Optional[SubjectMaterialLink] = None
    subject_material_link_replaced: bool = False
    media_assets: Dict[str, MediaAsset] = field(default_factory=dict)
    audit_log_events: Dict[str, AuditLogEvent] = field(default_factory=dict)

    instances: Dict[str, Instance] = field(default_factory=dict)
    instances_deleted: Set[str] = field(default_factory=set)
    instance_media_bindings: Dict[str, InstanceMediaBinding] = field(default_factory=dict)
    instance_media_bindings_deleted: Set[str] = field(default_factory=set)
    instance_subtitle_files: Dict[str, InstanceSubtitleFile] = field(default_factory=dict)
    instance_subtitle_files_deleted: Set[str] = field(default_factory=set)
    video_watch_progress: Dict[str, VideoWatchProgress] = field(default_factory=dict)
    video_watch_progress_deleted: Set[str] = field(default_factory=set)
    learning_object_nodes: Dict[str, LearningObjectNode] = field(default_factory=dict)
    learning_object_nodes_replaced: bool = False
    recall_points: Dict[str, RecallPoint] = field(default_factory=dict)
    recall_point_review_records: Dict[str, RecallPointReviewRecord] = field(default_factory=dict)
    learning_tasks: Dict[str, LearningTask] = field(default_factory=dict)
    learning_task_nodes: Dict[str, LearningTaskNode] = field(default_factory=dict)
    range_snapshots: Dict[str, RangeSnapshot] = field(default_factory=dict)
    asr_artifacts: Dict[str, AsrArtifact] = field(default_factory=dict)

    review_tasks: Dict[str, ReviewTask] = field(default_factory=dict)
    convergences: Dict[str, Convergence] = field(default_factory=dict)
    review_chains: Dict[str, ReviewChain] = field(default_factory=dict)
    review_task_queue: Optional[ReviewTaskQueue] = None  # staged replacement when not None

    layers: Dict[str, Layer] = field(default_factory=dict)
    layers_by_index: Dict[int, str] = field(default_factory=dict)
    entry_regs: Dict[str, EntryRegistration] = field(default_factory=dict)
    aggregation_queues: Dict[int, AggregationQueue] = field(default_factory=dict)
    aggregation_events: Dict[str, AggregationEvent] = field(default_factory=dict)


@dataclass
class GlobalStore:
    projects: Dict[str, ProjectStore] = field(default_factory=dict)
    global_llm_settings: GlobalLlmSettings | None = None
    idgen: InMemoryIdGenerator = field(default_factory=InMemoryIdGenerator)
    _write_lock_held: bool = False


class SessionState:
    OPEN = "OPEN"
    COMMITTED = "COMMITTED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"


@dataclass
class MutationSession:
    project_id: ProjectId
    mode: SessionMode
    runtime_kind: ClientRuntimeKind = ClientRuntimeKind.DESKTOP_WEB
    runtime_capabilities: frozenset[RuntimeCapability] = field(default_factory=frozenset)
    state: str = SessionState.OPEN
    _baseline: ProjectStore = field(default=None)
    _staged: ProjectStaged = field(default_factory=ProjectStaged)

    def assert_open(self) -> None:
        if self.state != SessionState.OPEN:
            raise SessionClosedError(f"Session is closed: state={self.state}")


T = TypeVar("T")


def _ensure_project_active(g: GlobalStore, project_id: ProjectId) -> ProjectStore:
    ps = g.projects.get(str(project_id))
    if ps is None or ps.project is None or ps.project.state != ProjectState.ACTIVE:
        raise NotFound(f"Project not found or not ACTIVE: {project_id}")
    return ps


def _merge_dict(ps_dict: Dict[str, T], st_dict: Dict[str, T]) -> Dict[str, T]:
    merged = dict(ps_dict)
    merged.update(st_dict)
    return merged


def _overlay_get(baseline: Dict[str, T], staged: Dict[str, T], key: str) -> T:
    if key in staged:
        return staged[key]
    if key in baseline:
        return baseline[key]
    raise NotFound(key)


def _overlay_maybe_get(baseline: Dict[str, T], staged: Dict[str, T], key: str) -> Optional[T]:
    if key in staged:
        return staged[key]
    return baseline.get(key)


def _overlay_all_sorted(baseline: Dict[str, T], staged: Dict[str, T]) -> Tuple[T, ...]:
    merged = dict(baseline)
    merged.update(staged)
    return tuple(merged[k] for k in sorted(merged.keys()))


def _overlay_instances(ps: ProjectStore, st: ProjectStaged) -> Dict[str, Instance]:
    merged = dict(ps.instances)
    for k in getattr(st, "instances_deleted", set()):
        merged.pop(k, None)
    merged.update(st.instances)
    return merged


def _overlay_media_assets(ps: ProjectStore, st: ProjectStaged) -> Dict[str, MediaAsset]:
    return _merge_dict(ps.media_assets, st.media_assets)

def _overlay_instance_media_bindings(ps: ProjectStore, st: ProjectStaged) -> Dict[str, InstanceMediaBinding]:
    merged = dict(getattr(ps, "instance_media_bindings", {}))
    for k in getattr(st, "instance_media_bindings_deleted", set()):
        merged.pop(k, None)
    merged.update(getattr(st, "instance_media_bindings", {}))
    return merged

def _overlay_instance_subtitle_files(ps: ProjectStore, st: ProjectStaged) -> Dict[str, InstanceSubtitleFile]:
    merged = dict(getattr(ps, "instance_subtitle_files", {}))
    for k in getattr(st, "instance_subtitle_files_deleted", set()):
        merged.pop(k, None)
    merged.update(getattr(st, "instance_subtitle_files", {}))
    return merged

def _overlay_video_watch_progress(ps: ProjectStore, st: ProjectStaged) -> Dict[str, VideoWatchProgress]:
    merged = dict(getattr(ps, "video_watch_progress", {}))
    for k in getattr(st, "video_watch_progress_deleted", set()):
        merged.pop(k, None)
    merged.update(getattr(st, "video_watch_progress", {}))
    return merged

def _overlay_audit_log_events(ps: ProjectStore, st: ProjectStaged) -> Dict[str, AuditLogEvent]:
    return _merge_dict(getattr(ps, "audit_log_events", {}), getattr(st, "audit_log_events", {}))

def _overlay_recall_point_review_records(ps: ProjectStore, st: ProjectStaged) -> Dict[str, RecallPointReviewRecord]:
    return _merge_dict(getattr(ps, "recall_point_review_records", {}), getattr(st, "recall_point_review_records", {}))

def _overlay_asr_artifacts(ps: ProjectStore, st: ProjectStaged) -> Dict[str, AsrArtifact]:
    return _merge_dict(getattr(ps, "asr_artifacts", {}), getattr(st, "asr_artifacts", {}))


def _overlay_learning_object_nodes(ps: ProjectStore, st: ProjectStaged) -> Dict[str, LearningObjectNode]:
    if getattr(st, "learning_object_nodes_replaced", False):
        return dict(st.learning_object_nodes)
    return _merge_dict(ps.learning_object_nodes, st.learning_object_nodes)


def _overlay_study_materials(ps: ProjectStore, st: ProjectStaged) -> Dict[str, StudyMaterial]:
    if getattr(st, "study_materials_replaced", False):
        return dict(st.study_materials)
    return _merge_dict(getattr(ps, "study_materials", {}), getattr(st, "study_materials", {}))


def _overlay_queue(ps: ProjectStore, st: ProjectStaged) -> ReviewTaskQueue:
    if st.review_task_queue is not None:
        return st.review_task_queue
    if ps.review_task_queue is None:
        raise NotFound("GLOBAL_QUEUE missing (project bootstrap not done)")
    return ps.review_task_queue


def _overlay_layers(ps: ProjectStore, st: ProjectStaged) -> Dict[str, Layer]:
    return _merge_dict(ps.layers, st.layers)


def _overlay_layers_by_index(ps: ProjectStore, st: ProjectStaged) -> Dict[int, str]:
    merged = dict(ps.layers_by_index)
    merged.update(st.layers_by_index)
    return merged


def _overlay_entry_regs(ps: ProjectStore, st: ProjectStaged) -> Dict[str, EntryRegistration]:
    return _merge_dict(ps.entry_regs, st.entry_regs)


def _overlay_aggqs(ps: ProjectStore, st: ProjectStaged) -> Dict[int, AggregationQueue]:
    merged = dict(ps.aggregation_queues)
    merged.update(st.aggregation_queues)
    return merged


def _overlay_aggregation_events(ps: ProjectStore, st: ProjectStaged) -> Dict[str, AggregationEvent]:
    return _merge_dict(ps.aggregation_events, st.aggregation_events)


# -------------------------
# Repositories (in-memory)
# -------------------------
class ProjectRepository:
    def __init__(self, g: GlobalStore) -> None:
        self.g = g

    def add(self, session: MutationSession, project: Project) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        if project.project_id != session.project_id:
            raise PreconditionFailure("ProjectRepository.add must use matching session.project_id")
        if str(project.project_id) in self.g.projects:
            raise PreconditionFailure("project_id already exists")
        if session._baseline.project is not None or session._staged.project is not None:
            raise PreconditionFailure("Project already exists in session scope")
        project.validate_write_time()
        session._staged.project = project

    def get(self, session: MutationSession, project_id: ProjectId) -> Project:
        session.assert_open()
        if project_id == session.project_id:
            if session._staged.project is not None:
                return session._staged.project
            if session._baseline.project is not None:
                return session._baseline.project

        ps = self.g.projects.get(str(project_id))
        if ps is None or ps.project is None:
            raise NotFound(project_id)
        return ps.project

    def maybe_get(self, session: MutationSession, project_id: ProjectId) -> Optional[Project]:
        session.assert_open()
        if project_id == session.project_id:
            if session._staged.project is not None:
                return session._staged.project
            return session._baseline.project

        ps = self.g.projects.get(str(project_id))
        return None if ps is None else ps.project

    def update(self, session: MutationSession, project: Project) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        if project.project_id != session.project_id:
            raise PreconditionFailure("ProjectRepository.update must use matching session.project_id")
        existed = self.maybe_get(session, project.project_id)
        if existed is None:
            raise NotFound(project.project_id)
        project.validate_write_time()
        session._staged.project = project

    def mark_deleted(self, session: MutationSession, project_id: ProjectId, deleted_at: Timestamp) -> None:
        """
        1.0.2 可选接口：软删除标记。
        本 in-memory 实现不依赖该接口（delete_project 走物理删除），但提供最小语义便于对齐 spec。
        """
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        if project_id != session.project_id:
            raise PreconditionFailure("mark_deleted must use matching session.project_id")

        p = self.get(session, project_id)
        updated = Project(
            project_id=p.project_id,
            title=p.title,
            state=ProjectState.DELETED,
            created_at=p.created_at,
            deleted_at=deleted_at,
        )
        updated.validate_write_time()
        session._staged.project = updated

    def all(self, session: MutationSession) -> Tuple[Project, ...]:
        session.assert_open()
        projs = [ps.project for ps in self.g.projects.values() if ps.project is not None]
        # Include staged project for read-your-writes in bootstrap sessions.
        if session._staged.project is not None and str(session.project_id) not in self.g.projects:
            projs.append(session._staged.project)
        projs.sort(key=lambda p: id_canonical_text(p.project_id))
        return tuple(projs)


class ProjectStorageConfigRepository:
    def __init__(self, g: GlobalStore) -> None:
        self.g = g

    def get(self, session: MutationSession) -> ProjectStorageConfig:
        session.assert_open()
        if session._staged.project_storage_config is not None:
            return session._staged.project_storage_config
        if session._baseline.project_storage_config is not None:
            return session._baseline.project_storage_config
        raise NotFound("ProjectStorageConfig missing")

    def set(self, session: MutationSession, config: ProjectStorageConfig) -> None:
        """
        1.0.4 upsert
        写前条件：project_root 非空（由 model.validate_write_time() 兜底）
        """
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        if config.project_id != session.project_id:
            raise PreconditionFailure("ProjectStorageConfigRepository.set must use matching session.project_id")
        config.validate_write_time()
        session._staged.project_storage_config = config


class ProjectConfigRepository:
    def __init__(self, g: GlobalStore) -> None:
        self.g = g

    def get(self, session: MutationSession) -> ProjectConfig:
        session.assert_open()
        if session._staged.project_config is not None:
            return session._staged.project_config
        if session._baseline.project_config is not None:
            return session._baseline.project_config
        raise NotFound("ProjectConfig missing")

    def set(self, session: MutationSession, config: ProjectConfig) -> None:
        """
        1.0.5 upsert
        """
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        if config.project_id != session.project_id:
            raise PreconditionFailure("ProjectConfigRepository.set must use matching session.project_id")
        config.validate_write_time()
        session._staged.project_config = config


class ProjectMaterialSourceBindingRepository:
    def __init__(self, g: GlobalStore) -> None:
        self.g = g

    def get(self, session: MutationSession) -> ProjectMaterialSourceBinding:
        session.assert_open()
        if session._staged.project_material_source_binding is not None:
            return session._staged.project_material_source_binding
        if session._baseline.project_material_source_binding is not None:
            return session._baseline.project_material_source_binding
        raise NotFound("ProjectMaterialSourceBinding missing")

    def set(self, session: MutationSession, binding: ProjectMaterialSourceBinding) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        if binding.project_id != session.project_id:
            raise PreconditionFailure("ProjectMaterialSourceBindingRepository.set must use matching session.project_id")
        binding.validate_write_time()
        session._staged.project_material_source_binding = binding


class MaterialAllowlistRepository:
    def __init__(self, g: GlobalStore) -> None:
        self.g = g

    def get(self, session: MutationSession) -> MaterialAllowlist:
        session.assert_open()
        if session._staged.material_allowlist is not None:
            return session._staged.material_allowlist
        if session._baseline.material_allowlist is not None:
            return session._baseline.material_allowlist
        raise NotFound("MaterialAllowlist missing")

    def replace(self, session: MutationSession, material_ids: Tuple[PurePath, ...]) -> None:
        """
        1.8.2：整表替换（不是增量）

        写前条件：
        - 去重（不允许重复 material_id）
        - 按 material_id.as_posix() Unicode code point 升序写死排序
        """
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")

        # Dedup check first (0b.5: fail => no staged writes)
        seen: Set[str] = set()
        for mid in material_ids:
            k = id_canonical_text(mid.as_posix())
            if k in seen:
                raise PreconditionFailure("MaterialAllowlistRepository.replace: material_ids contains duplicates")
            seen.add(k)

        # Canonical order
        ordered = tuple(sorted(material_ids, key=lambda p: p.as_posix()))
        allowlist = MaterialAllowlist(project_id=session.project_id, allowlist_id=MATERIAL_ALLOWLIST_V1, material_ids=ordered)
        allowlist.validate_write_time()
        session._staged.material_allowlist = allowlist


class MediaAssetRepository:
    def __init__(self, g: GlobalStore) -> None:
        self.g = g

    def add(self, session: MutationSession, asset: MediaAsset) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        ps = session._baseline
        st = session._staged
        k = id_canonical_text(asset.asset_id)
        assets = _overlay_media_assets(ps, st)
        if k in assets:
            raise PreconditionFailure("asset_id already exists")
        asset.validate_write_time()
        st.media_assets[k] = asset

    def get(self, session: MutationSession, asset_id: MediaAssetId) -> MediaAsset:
        session.assert_open()
        ps = session._baseline
        k = id_canonical_text(asset_id)
        return _overlay_get(ps.media_assets, session._staged.media_assets, k)

    def maybe_get(self, session: MutationSession, asset_id: MediaAssetId) -> Optional[MediaAsset]:
        session.assert_open()
        ps = session._baseline
        k = id_canonical_text(asset_id)
        return _overlay_maybe_get(ps.media_assets, session._staged.media_assets, k)

    def all(self, session: MutationSession) -> Tuple[MediaAsset, ...]:
        session.assert_open()
        ps = session._baseline
        return _overlay_all_sorted(ps.media_assets, session._staged.media_assets)


class InstanceRepository:
    def __init__(self, g: GlobalStore) -> None:
        self.g = g

    def add(self, session: MutationSession, instance: Instance) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        ps = session._baseline
        st = session._staged
        k = id_canonical_text(instance.instance_id)
        instance.validate_write_time()

        # If previously deleted in-session, treat add as "re-create" by cancelling the delete marker.
        if k in st.instances_deleted:
            st.instances_deleted.remove(k)

        instances = _overlay_instances(ps, st)
        if k in instances:
            raise PreconditionFailure("instance_id already exists")

        st.instances[k] = instance

    def update(self, session: MutationSession, instance: Instance) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        ps = session._baseline
        st = session._staged
        k = id_canonical_text(instance.instance_id)
        instance.validate_write_time()

        if k in st.instances_deleted:
            raise NotFound(instance.instance_id)
        existed = _overlay_maybe_get(ps.instances, st.instances, k)
        if existed is None:
            raise NotFound(instance.instance_id)

        st.instances[k] = instance

    def get(self, session: MutationSession, instance_id: InstanceId) -> Instance:
        session.assert_open()
        ps = session._baseline
        st = session._staged
        k = id_canonical_text(instance_id)
        if k in st.instances_deleted:
            raise NotFound(instance_id)
        return _overlay_get(ps.instances, st.instances, k)

    def maybe_get(self, session: MutationSession, instance_id: InstanceId) -> Optional[Instance]:
        session.assert_open()
        ps = session._baseline
        st = session._staged
        k = id_canonical_text(instance_id)
        if k in st.instances_deleted:
            return None
        return _overlay_maybe_get(ps.instances, st.instances, k)

    def all(self, session: MutationSession) -> Tuple[Instance, ...]:
        session.assert_open()
        ps = session._baseline
        merged = _overlay_instances(ps, session._staged)
        return tuple(merged[k] for k in sorted(merged.keys()))

    def delete(self, session: MutationSession, instance_id: InstanceId) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")

        ps = session._baseline
        st = session._staged
        k = id_canonical_text(instance_id)

        if k in st.instances_deleted:
            raise NotFound(instance_id)

        inst = self.maybe_get(session, instance_id)
        if inst is None:
            raise NotFound(instance_id)

        # 写前条件：不得被任何 RecallPoint.anchor.instance_id 引用；否则 PreconditionFailure
        recall_points = _merge_dict(ps.recall_points, st.recall_points)
        for rp in recall_points.values():
            if rp.anchor is not None and id_canonical_text(rp.anchor.instance_id) == k:
                raise PreconditionFailure("InstanceRepository.delete: instance_id is referenced by RecallPoint.anchor.instance_id")

        st.instances_deleted.add(k)
        # If the instance was created/updated in this session, drop it from staged writes.
        st.instances.pop(k, None)
        st.instance_media_bindings.pop(k, None)
        st.instance_media_bindings_deleted.add(k)
        st.instance_subtitle_files.pop(k, None)
        st.instance_subtitle_files_deleted.add(k)
        st.video_watch_progress.pop(k, None)
        st.video_watch_progress_deleted.add(k)


class InstanceMediaBindingRepository:
    def __init__(self, g: GlobalStore) -> None:
        self.g = g

    def get(self, session: MutationSession, instance_id: InstanceId) -> InstanceMediaBinding:
        session.assert_open()
        ps = session._baseline
        k = id_canonical_text(instance_id)
        if k in session._staged.instance_media_bindings_deleted:
            raise NotFound(instance_id)
        return _overlay_get(getattr(ps, "instance_media_bindings", {}), session._staged.instance_media_bindings, k)

    def maybe_get(self, session: MutationSession, instance_id: InstanceId) -> Optional[InstanceMediaBinding]:
        session.assert_open()
        ps = session._baseline
        k = id_canonical_text(instance_id)
        if k in session._staged.instance_media_bindings_deleted:
            return None
        return _overlay_maybe_get(getattr(ps, "instance_media_bindings", {}), session._staged.instance_media_bindings, k)

    def all(self, session: MutationSession) -> Tuple[InstanceMediaBinding, ...]:
        session.assert_open()
        ps = session._baseline
        return _overlay_all_sorted(getattr(ps, "instance_media_bindings", {}), session._staged.instance_media_bindings)

    def set(self, session: MutationSession, binding: InstanceMediaBinding) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        if binding.project_id != session.project_id:
            raise PreconditionFailure("InstanceMediaBindingRepository.set must use matching session.project_id")
        binding.validate_write_time()
        session._staged.instance_media_bindings_deleted.discard(id_canonical_text(binding.instance_id))
        session._staged.instance_media_bindings[id_canonical_text(binding.instance_id)] = binding

    def delete(self, session: MutationSession, instance_id: InstanceId) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        k = id_canonical_text(instance_id)
        if self.maybe_get(session, instance_id) is None:
            raise NotFound(instance_id)
        session._staged.instance_media_bindings.pop(k, None)
        session._staged.instance_media_bindings_deleted.add(k)


class InstanceSubtitleFileRepository:
    def __init__(self, g: GlobalStore, instance_repo: InstanceRepository) -> None:
        self.g = g
        self.instance_repo = instance_repo

    def get(self, session: MutationSession, instance_id: InstanceId) -> InstanceSubtitleFile:
        session.assert_open()
        ps = session._baseline
        k = id_canonical_text(instance_id)
        if k in session._staged.instance_subtitle_files_deleted:
            raise NotFound(instance_id)
        return _overlay_get(getattr(ps, "instance_subtitle_files", {}), session._staged.instance_subtitle_files, k)

    def maybe_get(self, session: MutationSession, instance_id: InstanceId) -> Optional[InstanceSubtitleFile]:
        session.assert_open()
        ps = session._baseline
        k = id_canonical_text(instance_id)
        if k in session._staged.instance_subtitle_files_deleted:
            return None
        return _overlay_maybe_get(getattr(ps, "instance_subtitle_files", {}), session._staged.instance_subtitle_files, k)

    def set(self, session: MutationSession, subtitle_file: InstanceSubtitleFile) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        if subtitle_file.project_id != session.project_id:
            raise PreconditionFailure("InstanceSubtitleFileRepository.set must use matching session.project_id")
        self.instance_repo.get(session, subtitle_file.instance_id)
        subtitle_file.validate_write_time()
        k = id_canonical_text(subtitle_file.instance_id)
        session._staged.instance_subtitle_files_deleted.discard(k)
        session._staged.instance_subtitle_files[k] = subtitle_file

    def delete(self, session: MutationSession, instance_id: InstanceId) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        k = id_canonical_text(instance_id)
        if self.maybe_get(session, instance_id) is None:
            raise NotFound(instance_id)
        session._staged.instance_subtitle_files.pop(k, None)
        session._staged.instance_subtitle_files_deleted.add(k)


class VideoWatchProgressRepository:
    def __init__(self, g: GlobalStore) -> None:
        self.g = g

    def set(self, session: MutationSession, progress: VideoWatchProgress) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        if str(progress.project_id) != str(session.project_id):
            raise PreconditionFailure("VideoWatchProgressRepository.set must use matching session.project_id")
        progress.validate_write_time()
        key = id_canonical_text(progress.instance_id)
        session._staged.video_watch_progress_deleted.discard(key)
        session._staged.video_watch_progress[key] = progress

    def maybe_get(self, session: MutationSession, instance_id: InstanceId) -> Optional[VideoWatchProgress]:
        session.assert_open()
        merged = _overlay_video_watch_progress(session._baseline, session._staged)
        return merged.get(id_canonical_text(instance_id))

    def all(self, session: MutationSession) -> Tuple[VideoWatchProgress, ...]:
        session.assert_open()
        merged = _overlay_video_watch_progress(session._baseline, session._staged)
        return tuple(merged[k] for k in sorted(merged.keys()))


class LearningObjectNodeRepository:
    def __init__(self, g: GlobalStore) -> None:
        self.g = g

    def _assert_tree_consistent_for_query(self, session: MutationSession) -> None:
        ps = session._baseline
        try:
            _validate_learning_object_tree_consistency(ps, session._staged)
        except CommitTimeValidationFailure as e:
            raise StructuralInconsistencyError(str(e)) from e

    def add(self, session: MutationSession, node: LearningObjectNode) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        ps = session._baseline
        st = session._staged
        nid = id_canonical_text(node.node_id)
        node.validate_write_time()

        nodes = _overlay_learning_object_nodes(ps, st)
        if nid in nodes:
            raise PreconditionFailure("node_id already exists")

        if isinstance(node, LearningObjectLeaf):
            inst_k = id_canonical_text(node.instance_id)
            for n in nodes.values():
                if isinstance(n, LearningObjectLeaf) and id_canonical_text(n.instance_id) == inst_k:
                    raise PreconditionFailure("InstanceId already bound by another LearningObjectLeaf")
        st.learning_object_nodes[nid] = node

    def get(self, session: MutationSession, node_id: LearningObjectNodeId) -> LearningObjectNode:
        session.assert_open()
        ps = session._baseline
        st = session._staged
        k = id_canonical_text(node_id)
        nodes = _overlay_learning_object_nodes(ps, st)
        if k not in nodes:
            raise NotFound(node_id)
        return nodes[k]

    def maybe_get(self, session: MutationSession, node_id: LearningObjectNodeId) -> Optional[LearningObjectNode]:
        session.assert_open()
        ps = session._baseline
        st = session._staged
        k = id_canonical_text(node_id)
        nodes = _overlay_learning_object_nodes(ps, st)
        return nodes.get(k)

    def all(self, session: MutationSession) -> Tuple[LearningObjectNode, ...]:
        session.assert_open()
        ps = session._baseline
        st = session._staged
        nodes = _overlay_learning_object_nodes(ps, st)
        return tuple(nodes[k] for k in sorted(nodes.keys()))

    def replace_forest(self, session: MutationSession, nodes: Sequence[LearningObjectNode]) -> None:
        """
        1.2.2：整树替换（forest scope）

        强约束：必须在同一 mutation session 内完成“清空旧集合 + 写入新集合”的 staged 写入。
        """
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")

        # ---- Validate (no staged writes on failure) ----
        next_nodes: Dict[str, LearningObjectNode] = {}
        bound_instance_ids: Set[str] = set()
        for n in nodes:
            n.validate_write_time()
            if n.project_id != session.project_id:
                raise PreconditionFailure("replace_forest must use matching project_id")
            k = id_canonical_text(n.node_id)
            if k in next_nodes:
                raise PreconditionFailure("Duplicate node_id in replace_forest")
            next_nodes[k] = n
            if isinstance(n, LearningObjectLeaf):
                ik = id_canonical_text(n.instance_id)
                if ik in bound_instance_ids:
                    raise PreconditionFailure("InstanceId already bound by another LearningObjectLeaf")
                bound_instance_ids.add(ik)

        # ---- Writes (staged) ----
        session._staged.learning_object_nodes = next_nodes
        session._staged.learning_object_nodes_replaced = True

    def replace_all_from_fs(self, session: MutationSession, nodes: Sequence[LearningObjectNode]) -> None:
        """
        1.2.2 replace_all_from_fs: filesystem authoritative full replacement.
        """
        self.replace_forest(session, nodes)

    def path_ids(self, session: MutationSession, node_id: LearningObjectNodeId) -> Tuple[LearningObjectNodeId, ...]:
        """
        1.2 派生：path_ids(node_id) = root -> ... -> self

        Failure semantics (1.2.2):
        - NotFound: node_id not resolvable
        - StructuralInconsistencyError: in-session overlay violates 1.2.3 commit-time constraints
        """
        session.assert_open()
        n = self.maybe_get(session, node_id)
        if n is None:
            raise NotFound(node_id)
        self._assert_tree_consistent_for_query(session)
        path: list[LearningObjectNodeId] = []
        cur: LearningObjectNode = n
        while True:
            path.append(cur.node_id)
            pid = cur.parent_id
            if pid is None:
                break
            cur = self.get(session, pid)
        path.reverse()
        return tuple(path)

    def depth(self, session: MutationSession, node_id: LearningObjectNodeId) -> int:
        """
        1.2 派生：depth(root)=0
        """
        return len(self.path_ids(session, node_id)) - 1

    def covered_instance_id_sequence(
        self, session: MutationSession, node_id: LearningObjectNodeId
    ) -> Tuple[InstanceId, ...]:
        """
        1.2 派生：按 children 顺序 DFS 拼接覆盖实例序列；Leaf -> [instance_id]
        """
        session.assert_open()
        n = self.maybe_get(session, node_id)
        if n is None:
            raise NotFound(node_id)
        self._assert_tree_consistent_for_query(session)
        return self._covered_instance_id_sequence_no_validate(session, node_id)

    def _covered_instance_id_sequence_no_validate(
        self, session: MutationSession, node_id: LearningObjectNodeId
    ) -> Tuple[InstanceId, ...]:
        n = self.get(session, node_id)
        if isinstance(n, LearningObjectLeaf):
            return (n.instance_id,)
        out: list[InstanceId] = []
        for cid in n.children:
            out.extend(self._covered_instance_id_sequence_no_validate(session, cid))
        return tuple(out)


class RecallPointRepository:
    def __init__(self, g: GlobalStore, instance_repo: InstanceRepository, media_asset_repo: MediaAssetRepository) -> None:
        self.g = g
        self.instance_repo = instance_repo
        self.media_asset_repo = media_asset_repo

    def _assert_rich_content_assets_resolvable(self, session: MutationSession, content) -> None:
        for b in content:
            if getattr(b, "kind", None) is None:
                continue
            if b.kind.value != "IMAGE":
                continue
            try:
                self.media_asset_repo.get(session, b.asset_id)
            except NotFound:
                raise PreconditionFailure("RichContent IMAGE asset_id not resolvable")

    def _assert_references_resolvable(
        self,
        session: MutationSession,
        references: tuple[RecallPointId, ...],
        *,
        self_recall_point_id: RecallPointId | None = None,
    ) -> None:
        seen: set[str] = set()
        self_key = None if self_recall_point_id is None else id_canonical_text(self_recall_point_id)
        for reference in references:
            ref_key = id_canonical_text(reference)
            if ref_key in seen:
                raise PreconditionFailure("RecallPoint.references must not contain duplicates")
            if self_key is not None and ref_key == self_key:
                raise PreconditionFailure("RecallPoint.references must not contain self")
            seen.add(ref_key)
            try:
                target = self.get(session, reference)
            except NotFound:
                raise PreconditionFailure("RecallPoint.references recall_point_id not resolvable")
            if target.state != RecallPointState.ACTIVE:
                raise PreconditionFailure("RecallPoint.references recall_point_id must resolve to ACTIVE RecallPoint")

    def add(self, session: MutationSession, rp: RecallPoint) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        ps = session._baseline
        k = id_canonical_text(rp.recall_point_id)
        if k in ps.recall_points or k in session._staged.recall_points:
            raise PreconditionFailure("recall_point_id already exists")
        if rp.project_id != session.project_id:
            raise PreconditionFailure("RecallPoint.project_id must match session.project_id")
        rp.validate_write_time()
        if rp.anchor is not None:
            try:
                self.instance_repo.get(session, rp.anchor.instance_id)
            except NotFound:
                raise PreconditionFailure("anchor.instance_id not resolvable")

        # RichContent IMAGE blocks must be resolvable (0a.12)
        self._assert_rich_content_assets_resolvable(session, rp.question)
        self._assert_rich_content_assets_resolvable(session, rp.answer)
        self._assert_references_resolvable(session, tuple(rp.references))
        for ins in rp.insights:
            self._assert_rich_content_assets_resolvable(session, ins)

        session._staged.recall_points[k] = rp

    def update(self, session: MutationSession, rp: RecallPoint) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        ps = session._baseline
        k = id_canonical_text(rp.recall_point_id)
        existed = _overlay_maybe_get(ps.recall_points, session._staged.recall_points, k)
        if existed is None:
            raise NotFound(rp.recall_point_id)
        if existed.state != RecallPointState.ACTIVE:
            raise PreconditionFailure("RecallPointRepository.update only allows ACTIVE RecallPoint")
        if rp.project_id != session.project_id:
            raise PreconditionFailure("RecallPoint.project_id must match session.project_id")
        rp.validate_write_time()
        if rp.anchor is not None:
            try:
                self.instance_repo.get(session, rp.anchor.instance_id)
            except NotFound:
                raise PreconditionFailure("anchor.instance_id not resolvable")

        # RichContent IMAGE blocks must be resolvable (0a.12)
        self._assert_rich_content_assets_resolvable(session, rp.question)
        self._assert_rich_content_assets_resolvable(session, rp.answer)
        self._assert_references_resolvable(session, tuple(rp.references), self_recall_point_id=rp.recall_point_id)

        # Strong constraint: insights are append-only; update must not overwrite/rollback them.
        updated = RecallPoint(
            project_id=rp.project_id,
            recall_point_id=rp.recall_point_id,
            created_at=existed.created_at,
            question=rp.question,
            answer=rp.answer,
            anchor=rp.anchor,
            references=tuple(rp.references),
            insights=tuple(existed.insights),
            state=existed.state,
            deleted_at=existed.deleted_at,
        )
        session._staged.recall_points[k] = updated

    def append_insight(self, session: MutationSession, recall_point_id: RecallPointId, insight: RichContent) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        rp = self.get(session, recall_point_id)
        if rp.state != RecallPointState.ACTIVE:
            raise PreconditionFailure("RecallPointRepository.append_insight only allows ACTIVE RecallPoint")

        validate_rich_content_write_time(insight)
        self._assert_rich_content_assets_resolvable(session, insight)

        updated = RecallPoint(
            project_id=rp.project_id,
            recall_point_id=rp.recall_point_id,
            created_at=rp.created_at,
            question=rp.question,
            answer=rp.answer,
            anchor=rp.anchor,
            references=tuple(rp.references),
            insights=tuple(rp.insights) + (insight,),
            state=rp.state,
            deleted_at=rp.deleted_at,
        )
        session._staged.recall_points[id_canonical_text(recall_point_id)] = updated

    def mark_deleted(self, session: MutationSession, recall_point_id: RecallPointId, deleted_at: Timestamp) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        rp = self.get(session, recall_point_id)
        if rp.state == RecallPointState.DELETED:
            return
        updated = RecallPoint(
            project_id=rp.project_id,
            recall_point_id=rp.recall_point_id,
            created_at=rp.created_at,
            question=rp.question,
            answer=rp.answer,
            anchor=rp.anchor,
            references=tuple(rp.references),
            insights=tuple(rp.insights),
            state=RecallPointState.DELETED,
            deleted_at=deleted_at,
        )
        session._staged.recall_points[id_canonical_text(recall_point_id)] = updated

    def get(self, session: MutationSession, recall_point_id: RecallPointId) -> RecallPoint:
        session.assert_open()
        ps = session._baseline
        k = id_canonical_text(recall_point_id)
        return _overlay_get(ps.recall_points, session._staged.recall_points, k)

    def maybe_get(self, session: MutationSession, recall_point_id: RecallPointId) -> Optional[RecallPoint]:
        session.assert_open()
        ps = session._baseline
        k = id_canonical_text(recall_point_id)
        return _overlay_maybe_get(ps.recall_points, session._staged.recall_points, k)

    def all(self, session: MutationSession) -> Tuple[RecallPoint, ...]:
        session.assert_open()
        ps = session._baseline
        return _overlay_all_sorted(ps.recall_points, session._staged.recall_points)


class RecallPointReviewRecordRepository:
    def __init__(
        self, g: GlobalStore, recall_point_repo: RecallPointRepository, review_task_repo: "ReviewTaskRepository"
    ) -> None:
        self.g = g
        self.recall_point_repo = recall_point_repo
        self.review_task_repo = review_task_repo

    def append(self, session: MutationSession, record: RecallPointReviewRecord) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        if record.project_id != session.project_id:
            raise PreconditionFailure("RecallPointReviewRecord.project_id must match session.project_id")
        record.validate_write_time()

        ps = session._baseline
        st = session._staged
        records = _overlay_recall_point_review_records(ps, st)
        k = id_canonical_text(record.record_id)
        if k in records:
            raise PreconditionFailure("RecallPointReviewRecord.record_id already exists")

        # Map NotFound to PreconditionFailure (1.10.2).
        try:
            self.recall_point_repo.get(session, record.recall_point_id)
        except NotFound:
            raise PreconditionFailure("RecallPointReviewRecord.recall_point_id not resolvable")
        try:
            self.review_task_repo.get(session, record.review_task_id)
        except NotFound:
            raise PreconditionFailure("RecallPointReviewRecord.review_task_id not resolvable")

        st.recall_point_review_records[k] = record

    def all_by_recall_point(
        self, session: MutationSession, recall_point_id: RecallPointId
    ) -> Tuple[RecallPointReviewRecord, ...]:
        session.assert_open()
        ps = session._baseline
        records = _overlay_recall_point_review_records(ps, session._staged)
        want = id_canonical_text(recall_point_id)
        items = [r for r in records.values() if id_canonical_text(r.recall_point_id) == want]
        items.sort(key=lambda r: (r.occurred_at, id_canonical_text(r.record_id)))
        return tuple(items)

    def all(self, session: MutationSession) -> Tuple[RecallPointReviewRecord, ...]:
        session.assert_open()
        ps = session._baseline
        records = _overlay_recall_point_review_records(ps, session._staged)
        items = list(records.values())
        items.sort(key=lambda r: (r.occurred_at, id_canonical_text(r.record_id)))
        return tuple(items)


class LearningTaskRepository:
    def __init__(self, g: GlobalStore, recall_point_repo: RecallPointRepository) -> None:
        self.g = g
        self.recall_point_repo = recall_point_repo

    def _assert_recall_point_ownership_unique(
        self, session: MutationSession, learning_task_id_key: str, recall_point_ids: Tuple[RecallPointId, ...]
    ) -> None:
        """
        4.1.6 写前门禁：复述点归属唯一（跨 LearningTask）

        语义：任一 RecallPointId 不得同时出现在其他 LearningTask.recall_point_ids 中。
        """
        ps = session._baseline
        tasks = _merge_dict(ps.learning_tasks, session._staged.learning_tasks)
        want = {id_canonical_text(x) for x in recall_point_ids}
        for tid, t in tasks.items():
            if tid == learning_task_id_key:
                continue
            for rp_id in t.recall_point_ids:
                if id_canonical_text(rp_id) in want:
                    raise PreconditionFailure("RecallPointId already belongs to another LearningTask")

    def _assert_recall_points_resolvable_and_active(
        self, session: MutationSession, recall_point_ids: Tuple[RecallPointId, ...]
    ) -> None:
        for rp_id in recall_point_ids:
            try:
                rp = self.recall_point_repo.get(session, rp_id)
            except NotFound:
                raise PreconditionFailure("LearningTask.recall_point_ids contains non-resolvable id")
            if rp.state != RecallPointState.ACTIVE:
                raise PreconditionFailure("LearningTask.recall_point_ids must all be ACTIVE")

    def add(self, session: MutationSession, task: LearningTask) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        ps = session._baseline
        k = id_canonical_text(task.learning_task_id)
        if k in ps.learning_tasks or k in session._staged.learning_tasks:
            raise PreconditionFailure("learning_task_id already exists")
        task.validate_write_time()
        self._assert_recall_points_resolvable_and_active(session, task.recall_point_ids)
        # 4.1.6 写前门禁（在产生 staged 写入前判定）
        self._assert_recall_point_ownership_unique(session, k, task.recall_point_ids)
        session._staged.learning_tasks[k] = task

    def update(self, session: MutationSession, task: LearningTask) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        ps = session._baseline
        k = id_canonical_text(task.learning_task_id)
        existed = _overlay_maybe_get(ps.learning_tasks, session._staged.learning_tasks, k)
        if existed is None:
            raise NotFound(task.learning_task_id)
        # 1.5.2 最小规格：update 仅允许更新 title；其它字段视为不可变。
        if tuple(task.recall_point_ids) != tuple(existed.recall_point_ids):
            raise PreconditionFailure("LearningTaskRepository.update only allows updating title")
        task.validate_write_time()
        # 4.1.6 写前门禁（在产生 staged 写入前判定）
        self._assert_recall_point_ownership_unique(session, k, task.recall_point_ids)
        session._staged.learning_tasks[k] = task

    def get(self, session: MutationSession, learning_task_id: LearningTaskId) -> LearningTask:
        session.assert_open()
        ps = session._baseline
        k = id_canonical_text(learning_task_id)
        return _overlay_get(ps.learning_tasks, session._staged.learning_tasks, k)

    def maybe_get(self, session: MutationSession, learning_task_id: LearningTaskId) -> Optional[LearningTask]:
        session.assert_open()
        ps = session._baseline
        k = id_canonical_text(learning_task_id)
        return _overlay_maybe_get(ps.learning_tasks, session._staged.learning_tasks, k)

    def all(self, session: MutationSession) -> Tuple[LearningTask, ...]:
        session.assert_open()
        ps = session._baseline
        return _overlay_all_sorted(ps.learning_tasks, session._staged.learning_tasks)

    def covered_instance_id_set(
        self,
        session: MutationSession,
        learning_task_id: LearningTaskId,
        recall_points_repo: "RecallPointRepository",
    ) -> Set[InstanceId]:
        """
        1.5 派生：遍历 recall_point_ids，取 anchor.instance_id 去重。
        """
        session.assert_open()
        t = self.get(session, learning_task_id)
        out: Set[InstanceId] = set()
        for rp_id in t.recall_point_ids:
            rp = recall_points_repo.get(session, rp_id)
            if rp.anchor is not None:
                out.add(rp.anchor.instance_id)
        return out


class LearningTaskNodeRepository:
    def __init__(
        self,
        g: GlobalStore,
        learning_task_repo: LearningTaskRepository,
        recall_point_repo: RecallPointRepository,
        learning_object_repo: "LearningObjectNodeRepository",
    ) -> None:
        self.g = g
        self.learning_task_repo = learning_task_repo
        self.recall_point_repo = recall_point_repo
        self.learning_object_repo = learning_object_repo

    def _assert_tree_consistent_for_query(self, session: MutationSession) -> None:
        ps = session._baseline
        try:
            _validate_learning_task_tree_consistency(ps, session._staged)
        except CommitTimeValidationFailure as e:
            raise StructuralInconsistencyError(str(e)) from e

    def add(self, session: MutationSession, node: LearningTaskNode) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        ps = session._baseline
        k = id_canonical_text(node.node_id)
        if k in ps.learning_task_nodes or k in session._staged.learning_task_nodes:
            raise PreconditionFailure("node_id already exists")
        node.validate_write_time()
        if isinstance(node, LearningTaskLeaf):
            b = id_canonical_text(node.bound_learning_task_id)
            for n in list(ps.learning_task_nodes.values()) + list(session._staged.learning_task_nodes.values()):
                if isinstance(n, LearningTaskLeaf) and id_canonical_text(n.bound_learning_task_id) == b:
                    raise PreconditionFailure("LearningTaskId already bound by another LearningTaskLeaf")
        session._staged.learning_task_nodes[k] = node

    def update(self, session: MutationSession, node: LearningTaskNode) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        ps = session._baseline
        k = id_canonical_text(node.node_id)
        current = _overlay_maybe_get(ps.learning_task_nodes, session._staged.learning_task_nodes, k)
        if current is None:
            raise NotFound(node.node_id)
        if isinstance(current, LearningTaskLeaf) != isinstance(node, LearningTaskLeaf):
            raise PreconditionFailure("LearningTaskNode kind cannot change")
        node.validate_write_time()
        if isinstance(node, LearningTaskLeaf):
            b = id_canonical_text(node.bound_learning_task_id)
            for existing_key, existing in _merge_dict(ps.learning_task_nodes, session._staged.learning_task_nodes).items():
                if existing_key == k:
                    continue
                if isinstance(existing, LearningTaskLeaf) and id_canonical_text(existing.bound_learning_task_id) == b:
                    raise PreconditionFailure("LearningTaskId already bound by another LearningTaskLeaf")
        session._staged.learning_task_nodes[k] = node

    def get(self, session: MutationSession, node_id: LearningTaskNodeId) -> LearningTaskNode:
        session.assert_open()
        ps = session._baseline
        k = id_canonical_text(node_id)
        return _overlay_get(ps.learning_task_nodes, session._staged.learning_task_nodes, k)

    def maybe_get(self, session: MutationSession, node_id: LearningTaskNodeId) -> Optional[LearningTaskNode]:
        session.assert_open()
        ps = session._baseline
        k = id_canonical_text(node_id)
        return _overlay_maybe_get(ps.learning_task_nodes, session._staged.learning_task_nodes, k)

    def all(self, session: MutationSession) -> Tuple[LearningTaskNode, ...]:
        session.assert_open()
        ps = session._baseline
        return _overlay_all_sorted(ps.learning_task_nodes, session._staged.learning_task_nodes)

    def find_leaf_by_learning_task_id(
        self, session: MutationSession, learning_task_id: LearningTaskId
    ) -> LearningTaskNodeId:
        """
        1.6.2 查询：从 LearningTaskId 找到绑定叶子节点（用于同步 title，避免双源不一致）
        """
        session.assert_open()
        ps = session._baseline
        nodes = _merge_dict(ps.learning_task_nodes, session._staged.learning_task_nodes)
        want = id_canonical_text(learning_task_id)
        for n in nodes.values():
            if isinstance(n, LearningTaskLeaf) and id_canonical_text(n.bound_learning_task_id) == want:
                return n.node_id
        raise NotFound(learning_task_id)

    def path_ids(self, session: MutationSession, node_id: LearningTaskNodeId) -> Tuple[LearningTaskNodeId, ...]:
        """
        1.6 派生：path_ids(node_id) = root -> ... -> self
        """
        session.assert_open()
        n = self.maybe_get(session, node_id)
        if n is None:
            raise NotFound(node_id)
        self._assert_tree_consistent_for_query(session)
        path: list[LearningTaskNodeId] = []
        cur: LearningTaskNode = n
        while True:
            path.append(cur.node_id)
            pid = cur.parent_id
            if pid is None:
                break
            cur = self.get(session, pid)
        path.reverse()
        return tuple(path)

    def depth(self, session: MutationSession, node_id: LearningTaskNodeId) -> int:
        """
        1.6 派生：depth(root)=0
        """
        return len(self.path_ids(session, node_id)) - 1

    def covered_rp_ids(self, session: MutationSession, node_id: LearningTaskNodeId) -> Tuple[RecallPointId, ...]:
        session.assert_open()
        n = self.maybe_get(session, node_id)
        if n is None:
            raise NotFound(node_id)
        self._assert_tree_consistent_for_query(session)
        return self._covered_rp_ids_no_validate(session, node_id)

    def _covered_rp_ids_no_validate(self, session: MutationSession, node_id: LearningTaskNodeId) -> Tuple[RecallPointId, ...]:
        n = self.get(session, node_id)
        if isinstance(n, LearningTaskLeaf):
            t = self.learning_task_repo.get(session, n.bound_learning_task_id)
            out: list[RecallPointId] = []
            for rp_id in t.recall_point_ids:
                rp = self.recall_point_repo.get(session, rp_id)
                if rp.state == RecallPointState.ACTIVE:
                    out.append(rp_id)
            return tuple(out)
        out: list[RecallPointId] = []
        for cid in n.children:
            out.extend(self._covered_rp_ids_no_validate(session, cid))
        return tuple(out)

    def push_up(
        self,
        session: MutationSession,
        candidate_child_ids: Tuple[LearningTaskNodeId, ...],
        title: str,
        new_parent_id: Optional[LearningTaskNodeId] = None,
        grand_parent_id: Optional[LearningTaskNodeId] = None,
    ) -> LearningTaskNodeId:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        if not candidate_child_ids:
            raise PreconditionFailure("candidate_child_ids must be non-empty")

        parent_id = new_parent_id or self.g.idgen.new_learning_task_node_id(session.project_id)
        children = [self.get(session, cid) for cid in candidate_child_ids]

        # ---- Precondition checks (must not leave staged writes on failure; 0b.5) ----
        updated_gp: Optional[LearningTaskContainer] = None
        if grand_parent_id is None:
            # Without grand_parent_id, this operation can only remain structurally consistent if all candidates are roots.
            for ch in children:
                if ch.parent_id is not None:
                    raise PreconditionFailure("grand_parent_id is required when candidates have an existing parent")
        else:
            gp = self.get(session, grand_parent_id)
            if not isinstance(gp, LearningTaskContainer):
                raise PreconditionFailure("grand_parent_id must be container")
            candidate_set = {id_canonical_text(x) for x in candidate_child_ids}
            gp_child_keys = [id_canonical_text(x) for x in gp.children]
            if not candidate_set.issubset(set(gp_child_keys)):
                raise PreconditionFailure("candidate_child_ids must be subset of grand_parent.children")
            for ch in children:
                if ch.parent_id != grand_parent_id:
                    raise PreconditionFailure("candidate_child_ids must have parent_id == grand_parent_id")

            first_idx = next(i for i, k in enumerate(gp_child_keys) if k in candidate_set)
            next_children: list[LearningTaskNodeId] = []
            next_children.extend(gp.children[:first_idx])
            next_children.append(parent_id)
            for x in gp.children[first_idx:]:
                if id_canonical_text(x) in candidate_set:
                    continue
                next_children.append(x)
            updated_gp = LearningTaskContainer(
                project_id=gp.project_id,
                node_id=gp.node_id,
                parent_id=gp.parent_id,
                children=tuple(next_children),
                title=gp.title,
                node_origin=gp.node_origin,
            )

        parent = LearningTaskContainer(
            project_id=session.project_id,
            node_id=parent_id,
            parent_id=grand_parent_id,
            children=tuple(candidate_child_ids),
            title=title,
        )
        parent.validate_write_time()

        updated_children: list[LearningTaskNode] = []
        for ch in children:
            if isinstance(ch, LearningTaskLeaf):
                updated = LearningTaskLeaf(
                    project_id=ch.project_id,
                    node_id=ch.node_id,
                    parent_id=parent_id,
                    bound_learning_task_id=ch.bound_learning_task_id,
                    title=ch.title,
                )
            else:
                updated = LearningTaskContainer(
                    project_id=ch.project_id,
                    node_id=ch.node_id,
                    parent_id=parent_id,
                    children=ch.children,
                    title=ch.title,
                    node_origin=ch.node_origin,
                )
            updated_children.append(updated)

        # Validate all derived writes before staging anything.
        for n in updated_children:
            n.validate_write_time()
        if updated_gp is not None:
            updated_gp.validate_write_time()

        # ---- Writes (staged) ----
        self.add(session, parent)
        for n in updated_children:
            session._staged.learning_task_nodes[id_canonical_text(n.node_id)] = n
        if updated_gp is not None:
            session._staged.learning_task_nodes[id_canonical_text(updated_gp.node_id)] = updated_gp

        return parent_id


class RangeSnapshotRepository:
    def __init__(self, g: GlobalStore) -> None:
        self.g = g

    def add(self, session: MutationSession, snapshot: RangeSnapshot) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        ps = session._baseline
        k = id_canonical_text(snapshot.range_id)
        if k in ps.range_snapshots or k in session._staged.range_snapshots:
            raise PreconditionFailure("range_id already exists")
        snapshot.validate_write_time()
        session._staged.range_snapshots[k] = snapshot

    def get(self, session: MutationSession, range_id: RangeId) -> RangeSnapshot:
        session.assert_open()
        ps = session._baseline
        k = id_canonical_text(range_id)
        return _overlay_get(ps.range_snapshots, session._staged.range_snapshots, k)

    def maybe_get(self, session: MutationSession, range_id: RangeId) -> Optional[RangeSnapshot]:
        session.assert_open()
        ps = session._baseline
        k = id_canonical_text(range_id)
        return _overlay_maybe_get(ps.range_snapshots, session._staged.range_snapshots, k)

    def all(self, session: MutationSession) -> Tuple[RangeSnapshot, ...]:
        session.assert_open()
        ps = session._baseline
        return _overlay_all_sorted(ps.range_snapshots, session._staged.range_snapshots)

    def intern(self, session: MutationSession, recall_point_ids: Tuple[RecallPointId, ...]) -> RangeId:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        if not recall_point_ids:
            raise PreconditionFailure("intern recall_point_ids must be non-empty")
        ps = session._baseline

        def key_of(t: Tuple[RecallPointId, ...]) -> Tuple[str, ...]:
            return tuple(id_canonical_text(x) for x in t)

        want = key_of(recall_point_ids)
        snaps = _merge_dict(ps.range_snapshots, session._staged.range_snapshots)
        for snap in snaps.values():
            if key_of(tuple(snap.recall_point_ids)) == want:
                return snap.range_id

        rid = self.g.idgen.new_range_id(session.project_id)
        snap = RangeSnapshot(project_id=session.project_id, range_id=rid, recall_point_ids=tuple(recall_point_ids))
        snap.validate_write_time()
        session._staged.range_snapshots[id_canonical_text(rid)] = snap
        return rid


class ReviewTaskRepository:
    def __init__(self, g: GlobalStore) -> None:
        self.g = g

    def add(self, session: MutationSession, review_task: ReviewTask) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        ps = session._baseline
        k = id_canonical_text(review_task.review_task_id)
        if k in ps.review_tasks or k in session._staged.review_tasks:
            raise PreconditionFailure("review_task_id already exists")
        review_task.validate_local_invariants()
        session._staged.review_tasks[k] = review_task

    def get(self, session: MutationSession, review_task_id: ReviewTaskId) -> ReviewTask:
        session.assert_open()
        ps = session._baseline
        k = id_canonical_text(review_task_id)
        return _overlay_get(ps.review_tasks, session._staged.review_tasks, k)

    def commit_done(
        self,
        session: MutationSession,
        review_task_id: ReviewTaskId,
        executed_at: Timestamp,
        result_range_id: Optional[RangeId],
    ) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        rt = self.get(session, review_task_id)
        if rt.state == ReviewTaskState.DONE:
            return
        if rt.state != ReviewTaskState.PENDING:
            raise PreconditionFailure("commit_done only allowed from PENDING")
        updated = ReviewTask(
            project_id=rt.project_id,
            review_task_id=rt.review_task_id,
            input_range_id=rt.input_range_id,
            created_at=rt.created_at,
            state=ReviewTaskState.DONE,
            executed_at=executed_at,
            result_range_id=result_range_id,
        )
        updated.validate_local_invariants()
        session._staged.review_tasks[id_canonical_text(review_task_id)] = updated


class ConvergenceRepository:
    def __init__(self, g: GlobalStore) -> None:
        self.g = g

    def add(self, session: MutationSession, convergence: Convergence) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        ps = session._baseline
        k = id_canonical_text(convergence.convergence_id)
        if k in ps.convergences or k in session._staged.convergences:
            raise PreconditionFailure("convergence_id already exists")
        convergence.validate_local_invariants()
        session._staged.convergences[k] = convergence

    def get(self, session: MutationSession, convergence_id: ConvergenceId) -> Convergence:
        session.assert_open()
        ps = session._baseline
        k = id_canonical_text(convergence_id)
        return _overlay_get(ps.convergences, session._staged.convergences, k)

    def append_review_task_id(self, session: MutationSession, convergence_id: ConvergenceId, review_task_id: ReviewTaskId) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        c = self.get(session, convergence_id)
        updated = Convergence(
            project_id=c.project_id,
            convergence_id=c.convergence_id,
            seed_range_id=c.seed_range_id,
            rule_id=c.rule_id,
            review_task_ids=tuple(list(c.review_task_ids) + [review_task_id]),
            state=c.state,
        )
        updated.validate_local_invariants()
        session._staged.convergences[id_canonical_text(convergence_id)] = updated

    def update_state(self, session: MutationSession, convergence_id: ConvergenceId, state: ConvergenceState) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        c = self.get(session, convergence_id)
        updated = Convergence(
            project_id=c.project_id,
            convergence_id=c.convergence_id,
            seed_range_id=c.seed_range_id,
            rule_id=c.rule_id,
            review_task_ids=c.review_task_ids,
            state=state,
        )
        updated.validate_local_invariants()
        session._staged.convergences[id_canonical_text(convergence_id)] = updated

    def all(self, session: MutationSession) -> Tuple[Convergence, ...]:
        session.assert_open()
        ps = session._baseline
        items = dict(ps.convergences)
        items.update(session._staged.convergences)
        return tuple(items[k] for k in sorted(items.keys()))


class ReviewChainRepository:
    def __init__(self, g: GlobalStore) -> None:
        self.g = g

    def add(self, session: MutationSession, chain: ReviewChain) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        ps = session._baseline
        k = id_canonical_text(chain.review_chain_id)
        if k in ps.review_chains or k in session._staged.review_chains:
            raise PreconditionFailure("review_chain_id already exists")
        chain.validate_local_invariants()
        session._staged.review_chains[k] = chain

    def get(self, session: MutationSession, review_chain_id: ReviewChainId) -> ReviewChain:
        session.assert_open()
        ps = session._baseline
        k = id_canonical_text(review_chain_id)
        return _overlay_get(ps.review_chains, session._staged.review_chains, k)

    def all(self, session: MutationSession) -> Tuple[ReviewChain, ...]:
        session.assert_open()
        ps = session._baseline
        items = dict(ps.review_chains)
        items.update(session._staged.review_chains)
        return tuple(items[k] for k in sorted(items.keys()))

    def advance_head(self, session: MutationSession, review_chain_id: ReviewChainId) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        c = self.get(session, review_chain_id)
        if c.head_index >= len(c.queue):
            return
        updated = ReviewChain(
            project_id=c.project_id,
            review_chain_id=c.review_chain_id,
            queue=c.queue,
            head_index=c.head_index + 1,
            state=c.state,
        )
        updated.validate_local_invariants()
        session._staged.review_chains[id_canonical_text(review_chain_id)] = updated


class ReviewTaskQueueRepository:
    def __init__(self, g: GlobalStore) -> None:
        self.g = g

    def enqueue_if_absent(self, session: MutationSession, review_task_id: ReviewTaskId) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        ps = session._baseline
        q = _overlay_queue(ps, session._staged)
        tail = list(q.review_task_ids[q.head_index :])
        if review_task_id in tail:
            return
        updated = ReviewTaskQueue(
            project_id=q.project_id,
            queue_id=q.queue_id,
            review_task_ids=tuple(list(q.review_task_ids) + [review_task_id]),
            head_index=q.head_index,
        )
        updated.validate_local_invariants()
        session._staged.review_task_queue = updated

    def remove_by_id(self, session: MutationSession, review_task_id: ReviewTaskId) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        ps = session._baseline
        q = _overlay_queue(ps, session._staged)
        start = q.head_index
        tail = list(q.review_task_ids[start:])
        if review_task_id not in tail:
            return
        new_tail = [x for x in tail if x != review_task_id]
        updated = ReviewTaskQueue(
            project_id=q.project_id,
            queue_id=q.queue_id,
            review_task_ids=tuple(list(q.review_task_ids[:start]) + new_tail),
            head_index=q.head_index,
        )
        updated.validate_local_invariants()
        session._staged.review_task_queue = updated

    def peek_head(self, session: MutationSession) -> Optional[ReviewTaskId]:
        session.assert_open()
        ps = session._baseline
        q = _overlay_queue(ps, session._staged)
        cur = q.current_ids()
        return cur[0] if cur else None

    def is_empty(self, session: MutationSession) -> bool:
        return self.peek_head(session) is None

    def current_ids(self, session: MutationSession) -> Tuple[ReviewTaskId, ...]:
        session.assert_open()
        ps = session._baseline
        q = _overlay_queue(ps, session._staged)
        return q.current_ids()

    def all_queue_ids_for_commit_validation(self, session: MutationSession) -> Tuple[ReviewTaskQueueId, ...]:
        session.assert_open()
        ps = session._baseline
        q = _overlay_queue(ps, session._staged)
        return (q.queue_id,)


class LayerRepository:
    def __init__(self, g: GlobalStore) -> None:
        self.g = g

    def add(self, session: MutationSession, layer: Layer) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        ps = session._baseline
        lid = id_canonical_text(layer.layer_id)
        layers = _overlay_layers(ps, session._staged)
        if lid in layers:
            raise PreconditionFailure("layer_id already exists")
        by_index = _overlay_layers_by_index(ps, session._staged)
        if layer.layer_index in by_index:
            raise PreconditionFailure("layer_index already exists")
        layer.validate_local_invariants()
        session._staged.layers[lid] = layer
        session._staged.layers_by_index[layer.layer_index] = lid

        aggqs = _overlay_aggqs(ps, session._staged)
        if layer.layer_index not in aggqs:
            session._staged.aggregation_queues[layer.layer_index] = AggregationQueue(
                project_id=session.project_id,
                layer_index=layer.layer_index,
                node_ids=tuple(),
                head_index=0,
            )

    def get_by_index(self, session: MutationSession, layer_index: int) -> Layer:
        session.assert_open()
        ps = session._baseline
        by_index = _overlay_layers_by_index(ps, session._staged)
        lid = by_index.get(layer_index)
        if lid is None:
            raise NotFound(f"layer_index={layer_index}")
        layers = _overlay_layers(ps, session._staged)
        if lid not in layers:
            raise NotFound(f"layer_id={lid}")
        return layers[lid]

    def get(self, session: MutationSession, layer_id: LayerId) -> Layer:
        session.assert_open()
        ps = session._baseline
        k = id_canonical_text(layer_id)
        return _overlay_get(ps.layers, session._staged.layers, k)

    def maybe_get_by_index(self, session: MutationSession, layer_index: int) -> Optional[Layer]:
        try:
            return self.get_by_index(session, layer_index)
        except NotFound:
            return None

    def all(self, session: MutationSession) -> Tuple[Layer, ...]:
        session.assert_open()
        ps = session._baseline
        layers = _overlay_layers(ps, session._staged)
        items = list(layers.values())
        items.sort(key=lambda l: l.layer_index)
        return tuple(items)

    def update_threshold(self, session: MutationSession, layer_index: int, K_node: int, K_point: int) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        if int(K_node) <= 0:
            raise PreconditionFailure("K_node must be >= 1")
        if int(K_point) <= 0:
            raise PreconditionFailure("K_point must be >= 1")

        layer = self.get_by_index(session, layer_index)
        if int(layer.aggregation_k_node) == int(K_node) and int(layer.aggregation_k_point) == int(K_point):
            return

        updated = Layer(
            project_id=layer.project_id,
            layer_id=layer.layer_id,
            layer_index=layer.layer_index,
            layer_mode=layer.layer_mode,
            orchestrator_managed_review_chain_ids=layer.orchestrator_managed_review_chain_ids,
            aggregation_k_node=int(K_node),
            aggregation_k_point=int(K_point),
            aggregation_cycle_state=layer.aggregation_cycle_state,
            pending_roll_up_parent_node_id=layer.pending_roll_up_parent_node_id,
            normal_tick_quota_remaining=layer.normal_tick_quota_remaining,
        )
        updated.validate_local_invariants()
        session._staged.layers[id_canonical_text(updated.layer_id)] = updated

    def upsert_managed_chain(self, session: MutationSession, layer_index: int, review_chain_id: ReviewChainId) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        layer = self.get_by_index(session, layer_index)
        merged = tuple(list(layer.orchestrator_managed_review_chain_ids) + [review_chain_id])
        norm = tuple(sorted(set(merged), key=id_canonical_text))
        updated = Layer(
            project_id=layer.project_id,
            layer_id=layer.layer_id,
            layer_index=layer.layer_index,
            layer_mode=layer.layer_mode,
            orchestrator_managed_review_chain_ids=norm,
            aggregation_k_node=layer.aggregation_k_node,
            aggregation_k_point=layer.aggregation_k_point,
            aggregation_cycle_state=layer.aggregation_cycle_state,
            pending_roll_up_parent_node_id=layer.pending_roll_up_parent_node_id,
            normal_tick_quota_remaining=layer.normal_tick_quota_remaining,
        )
        updated.validate_local_invariants()
        session._staged.layers[id_canonical_text(updated.layer_id)] = updated

    def remove_managed_chain(self, session: MutationSession, layer_index: int, review_chain_id: ReviewChainId) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        layer = self.get_by_index(session, layer_index)
        next_ids = tuple(cid for cid in layer.orchestrator_managed_review_chain_ids if cid != review_chain_id)
        if next_ids == layer.orchestrator_managed_review_chain_ids:
            return
        updated = Layer(
            project_id=layer.project_id,
            layer_id=layer.layer_id,
            layer_index=layer.layer_index,
            layer_mode=layer.layer_mode,
            orchestrator_managed_review_chain_ids=next_ids,
            aggregation_k_node=layer.aggregation_k_node,
            aggregation_k_point=layer.aggregation_k_point,
            aggregation_cycle_state=layer.aggregation_cycle_state,
            pending_roll_up_parent_node_id=layer.pending_roll_up_parent_node_id,
            normal_tick_quota_remaining=layer.normal_tick_quota_remaining,
        )
        updated.validate_local_invariants()
        session._staged.layers[id_canonical_text(updated.layer_id)] = updated


class EntryRegistryRepository:
    def __init__(self, g: GlobalStore) -> None:
        self.g = g

    def add(self, session: MutationSession, reg: EntryRegistration) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        ps = session._baseline
        reg.validate_local_invariants()
        k = id_canonical_text(reg.entry_node)
        regs = _overlay_entry_regs(ps, session._staged)
        if k in regs:
            raise PreconditionFailure("entry_node already registered")
        for existing in regs.values():
            if id_canonical_text(existing.review_chain_id) == id_canonical_text(reg.review_chain_id):
                raise PreconditionFailure("review_chain_id already registered by another entry")
            if (
                int(existing.registration_seq) > 0
                and int(reg.registration_seq) > 0
                and existing.target_layer_index == reg.target_layer_index
                and int(existing.registration_seq) == int(reg.registration_seq)
            ):
                raise PreconditionFailure("registration_seq already registered in target layer")
        session._staged.entry_regs[k] = reg

    def get(self, session: MutationSession, entry_node: LearningTaskNodeId) -> EntryRegistration:
        session.assert_open()
        ps = session._baseline
        k = id_canonical_text(entry_node)
        return _overlay_get(ps.entry_regs, session._staged.entry_regs, k)

    def maybe_get(self, session: MutationSession, entry_node: LearningTaskNodeId) -> Optional[EntryRegistration]:
        session.assert_open()
        ps = session._baseline
        k = id_canonical_text(entry_node)
        return _overlay_maybe_get(ps.entry_regs, session._staged.entry_regs, k)

    def all(self, session: MutationSession) -> Tuple[EntryRegistration, ...]:
        session.assert_open()
        ps = session._baseline
        regs = _overlay_entry_regs(ps, session._staged)
        items = list(regs.values())
        items.sort(key=lambda r: (int(r.target_layer_index), int(r.registration_seq), id_canonical_text(r.entry_node)))
        return tuple(items)


class AggregationQueueRepository:
    def __init__(self, g: GlobalStore) -> None:
        self.g = g

    def _get(self, session: MutationSession, layer_index: int) -> AggregationQueue:
        session.assert_open()
        ps = session._baseline
        aggqs = _overlay_aggqs(ps, session._staged)
        if layer_index not in aggqs:
            raise NotFound(f"AggregationQueue missing for layer_index={layer_index}")
        return aggqs[layer_index]

    def get(self, session: MutationSession, layer_index: int) -> AggregationQueue:
        return self._get(session, layer_index)

    def enqueue(self, session: MutationSession, layer_index: int, node_id: LearningTaskNodeId) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        q = self._get(session, layer_index)
        updated = AggregationQueue(
            project_id=q.project_id,
            layer_index=q.layer_index,
            node_ids=tuple(list(q.node_ids) + [node_id]),
            head_index=q.head_index,
        )
        updated.validate_local_invariants()
        session._staged.aggregation_queues[layer_index] = updated

    def current_ids(self, session: MutationSession, layer_index: int) -> Tuple[LearningTaskNodeId, ...]:
        q = self._get(session, layer_index)
        return q.current_ids()

    def is_empty(self, session: MutationSession, layer_index: int) -> bool:
        return len(self.current_ids(session, layer_index)) == 0

    def clear_current(self, session: MutationSession, layer_index: int) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        q = self._get(session, layer_index)
        updated = AggregationQueue(
            project_id=q.project_id,
            layer_index=q.layer_index,
            node_ids=q.node_ids,
            head_index=len(q.node_ids),
        )
        updated.validate_local_invariants()
        session._staged.aggregation_queues[layer_index] = updated


class AggregationEventRepository:
    def __init__(self, g: GlobalStore) -> None:
        self.g = g

    def append(self, session: MutationSession, event: AggregationEvent) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        ps = session._baseline
        events = _overlay_aggregation_events(ps, session._staged)
        k = id_canonical_text(event.event_id)
        if k in events:
            raise PreconditionFailure("event_id already exists")
        event.validate_local_invariants()
        session._staged.aggregation_events[k] = event

    def all(self, session: MutationSession) -> Tuple[AggregationEvent, ...]:
        session.assert_open()
        ps = session._baseline
        events = _overlay_aggregation_events(ps, session._staged)
        items = list(events.values())
        items.sort(key=lambda e: id_canonical_text(e.event_id))
        return tuple(items)


class AuditLogRepository:
    def __init__(self, g: GlobalStore) -> None:
        self.g = g

    def append(self, session: MutationSession, event: AuditLogEvent) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        if event.project_id != session.project_id:
            raise PreconditionFailure("AuditLogEvent.project_id must match session.project_id")
        event.validate_write_time()

        ps = session._baseline
        events = _overlay_audit_log_events(ps, session._staged)
        k = id_canonical_text(event.event_id)
        if k in events:
            raise PreconditionFailure("AuditLogEvent.event_id already exists")
        session._staged.audit_log_events[k] = event

    def all(self, session: MutationSession) -> Tuple[AuditLogEvent, ...]:
        session.assert_open()
        ps = session._baseline
        events = _overlay_audit_log_events(ps, session._staged)
        items = list(events.values())
        items.sort(key=lambda e: (e.occurred_at, id_canonical_text(e.event_id)))
        return tuple(items)

class AsrArtifactRepository:
    def __init__(self, g: GlobalStore, recall_point_repo: RecallPointRepository, instance_repo: InstanceRepository) -> None:
        self.g = g
        self.recall_point_repo = recall_point_repo
        self.instance_repo = instance_repo

    def add(self, session: MutationSession, artifact: AsrArtifact) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        if artifact.project_id != session.project_id:
            raise PreconditionFailure("AsrArtifact.project_id must match session.project_id")
        artifact.validate_write_time()
        try:
            rp = self.recall_point_repo.get(session, artifact.recall_point_id)
        except NotFound:
            raise PreconditionFailure("AsrArtifact.recall_point_id not resolvable")
        if rp.state != RecallPointState.ACTIVE:
            raise PreconditionFailure("AsrArtifact.recall_point_id must resolve to ACTIVE RecallPoint")
        try:
            self.instance_repo.get(session, artifact.source_instance_id)
        except NotFound:
            raise PreconditionFailure("AsrArtifact.source_instance_id not resolvable")

        ps = session._baseline
        arts = _overlay_asr_artifacts(ps, session._staged)
        k = id_canonical_text(artifact.asr_artifact_id)
        if k in arts:
            raise PreconditionFailure("AsrArtifact.asr_artifact_id already exists")
        session._staged.asr_artifacts[k] = artifact

    def maybe_get_by_cache_key(
        self,
        session: MutationSession,
        recall_point_id: RecallPointId,
        provider: AsrProvider,
        center_ms: int,
        pre_ms: int,
        post_ms: int,
    ) -> Optional[AsrArtifact]:
        session.assert_open()
        ps = session._baseline
        arts = _overlay_asr_artifacts(ps, session._staged)
        for a in arts.values():
            if (
                id_canonical_text(a.recall_point_id) == id_canonical_text(recall_point_id)
                and a.provider == provider
                and int(a.center_ms) == int(center_ms)
                and int(a.pre_ms) == int(pre_ms)
                and int(a.post_ms) == int(post_ms)
            ):
                return a
        return None

    def upsert_by_cache_key(self, session: MutationSession, artifact: AsrArtifact) -> AsrArtifactId:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            raise PreconditionFailure("READ_ONLY session cannot write")
        artifact.validate_write_time()

        hit = self.maybe_get_by_cache_key(
            session,
            artifact.recall_point_id,
            artifact.provider,
            artifact.center_ms,
            artifact.pre_ms,
            artifact.post_ms,
        )
        if hit is not None:
            return hit.asr_artifact_id

        self.add(session, artifact)
        return artifact.asr_artifact_id

    def get(self, session: MutationSession, asr_artifact_id: AsrArtifactId) -> AsrArtifact:
        session.assert_open()
        ps = session._baseline
        arts = _overlay_asr_artifacts(ps, session._staged)
        k = id_canonical_text(asr_artifact_id)
        return _overlay_get(getattr(ps, "asr_artifacts", {}), getattr(session._staged, "asr_artifacts", {}), k)

    def all(self, session: MutationSession) -> Tuple[AsrArtifact, ...]:
        session.assert_open()
        ps = session._baseline
        arts = _overlay_asr_artifacts(ps, session._staged)
        items = list(arts.values())
        items.sort(key=lambda x: id_canonical_text(x.asr_artifact_id))
        return tuple(items)


# -------------------------
# Commit-time validators (0b.7.1 closure)
# -------------------------
def _validate_learning_task_task_dedup(ps: ProjectStore, st: ProjectStaged) -> None:
    tasks = _merge_dict(ps.learning_tasks, st.learning_tasks)
    for t in tasks.values():
        ids = [id_canonical_text(x) for x in t.recall_point_ids]
        if len(ids) != len(set(ids)):
            raise CommitTimeValidationFailure(f"LearningTask recall_point_ids has duplicates: {t.learning_task_id}")


def _validate_range_snapshot_content_addressing(ps: ProjectStore, st: ProjectStaged) -> None:
    snaps = _merge_dict(ps.range_snapshots, st.range_snapshots)

    def key_of(s: RangeSnapshot) -> Tuple[str, ...]:
        return tuple(id_canonical_text(x) for x in s.recall_point_ids)

    seen: Dict[Tuple[str, ...], str] = {}
    for rid, snap in snaps.items():
        k = key_of(snap)
        if k in seen and seen[k] != rid:
            raise CommitTimeValidationFailure("RangeSnapshot content-address uniqueness violated")
        seen[k] = rid


def _validate_learning_object_tree_consistency(ps: ProjectStore, st: ProjectStaged) -> None:
    nodes = _overlay_learning_object_nodes(ps, st)

    def get(nid: str) -> LearningObjectNode:
        if nid not in nodes:
            raise CommitTimeValidationFailure(f"LearningObjectNode not resolvable: {nid}")
        return nodes[nid]

    parent_of: Dict[str, str] = {}
    for nid, n in nodes.items():
        if isinstance(n, LearningObjectContainer):
            seen: Set[str] = set()
            for cid in n.children:
                ck = id_canonical_text(cid)
                if ck in seen:
                    raise CommitTimeValidationFailure("Duplicate child in LearningObjectContainer.children")
                seen.add(ck)
                ch = get(ck)
                if ch.parent_id is None or id_canonical_text(ch.parent_id) != nid:
                    raise CommitTimeValidationFailure("Bidirectional inconsistency (child.parent_id)")
                if ck in parent_of and parent_of[ck] != nid:
                    raise CommitTimeValidationFailure("No multiple parents violated")
                parent_of[ck] = nid

    for nid, n in nodes.items():
        if n.parent_id is not None:
            pk = id_canonical_text(n.parent_id)
            p = get(pk)
            if not isinstance(p, LearningObjectContainer):
                raise CommitTimeValidationFailure("parent must be container")
            if nid not in {id_canonical_text(x) for x in p.children}:
                raise CommitTimeValidationFailure("Bidirectional inconsistency (parent.children)")

    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {nid: WHITE for nid in nodes.keys()}

    def dfs(u: str) -> None:
        color[u] = GRAY
        nu = nodes[u]
        if isinstance(nu, LearningObjectContainer):
            for cid in nu.children:
                v = id_canonical_text(cid)
                if v not in nodes:
                    raise CommitTimeValidationFailure("Dangling child id")
                if color[v] == GRAY:
                    raise CommitTimeValidationFailure("Cycle detected")
                if color[v] == WHITE:
                    dfs(v)
        color[u] = BLACK

    for nid in nodes.keys():
        if color[nid] == WHITE:
            dfs(nid)


def _validate_learning_task_tree_consistency(ps: ProjectStore, st: ProjectStaged) -> None:
    nodes = _merge_dict(ps.learning_task_nodes, st.learning_task_nodes)

    def get(nid: str) -> LearningTaskNode:
        if nid not in nodes:
            raise CommitTimeValidationFailure(f"LearningTaskNode not resolvable: {nid}")
        return nodes[nid]

    parent_of: Dict[str, str] = {}
    for nid, n in nodes.items():
        if isinstance(n, LearningTaskContainer):
            seen: Set[str] = set()
            child_types: Set[type] = set()
            for cid in n.children:
                ck = id_canonical_text(cid)
                if ck in seen:
                    raise CommitTimeValidationFailure("Duplicate child in LearningTaskContainer.children")
                seen.add(ck)
                ch = get(ck)
                child_types.add(type(ch))
                if ch.parent_id is None or id_canonical_text(ch.parent_id) != nid:
                    raise CommitTimeValidationFailure("Bidirectional inconsistency (child.parent_id)")
                if ck in parent_of and parent_of[ck] != nid:
                    raise CommitTimeValidationFailure("No multiple parents violated")
                parent_of[ck] = nid
            if len(child_types) > 1:
                raise CommitTimeValidationFailure("Homogeneous children violated")

    for nid, n in nodes.items():
        if n.parent_id is not None:
            pk = id_canonical_text(n.parent_id)
            p = get(pk)
            if not isinstance(p, LearningTaskContainer):
                raise CommitTimeValidationFailure("parent must be container")
            if nid not in {id_canonical_text(x) for x in p.children}:
                raise CommitTimeValidationFailure("Bidirectional inconsistency (parent.children)")

    WHITE, GRAY, BLACK = 0, 1, 2
    color: Dict[str, int] = {nid: WHITE for nid in nodes.keys()}

    def dfs(u: str) -> None:
        color[u] = GRAY
        nu = nodes[u]
        if isinstance(nu, LearningTaskContainer):
            for cid in nu.children:
                v = id_canonical_text(cid)
                if v not in nodes:
                    raise CommitTimeValidationFailure("Dangling child id")
                if color[v] == GRAY:
                    raise CommitTimeValidationFailure("Cycle detected")
                if color[v] == WHITE:
                    dfs(v)
        color[u] = BLACK

    for nid in nodes.keys():
        if color[nid] == WHITE:
            dfs(nid)


def _validate_commit_q1_q2(ps: ProjectStore, st: ProjectStaged) -> None:
    q = st.review_task_queue if st.review_task_queue is not None else ps.review_task_queue
    if q is None:
        raise CommitTimeValidationFailure("GLOBAL_QUEUE singleton violated (missing)")
    if q.queue_id != GLOBAL_QUEUE:
        raise CommitTimeValidationFailure("GLOBAL_QUEUE singleton violated (wrong id)")

    current = q.current_ids()
    seen: Set[str] = set()
    tasks = _merge_dict(ps.review_tasks, st.review_tasks)
    for t in current:
        k = id_canonical_text(t)
        if k in seen:
            raise CommitTimeValidationFailure("Duplicate ReviewTaskId in queue")
        seen.add(k)
        rt = tasks.get(k)
        if rt is None:
            raise CommitTimeValidationFailure("Queued ReviewTaskId not resolvable")
        if rt.state != ReviewTaskState.PENDING:
            raise CommitTimeValidationFailure("Queued ReviewTask must be PENDING")


def _validate_commit_entry_registry_and_management(ps: ProjectStore, st: ProjectStaged) -> None:
    layers = _overlay_layers(ps, st)
    layers_by_index = _overlay_layers_by_index(ps, st)
    regs = _overlay_entry_regs(ps, st)
    task_nodes = _merge_dict(ps.learning_task_nodes, st.learning_task_nodes)
    chains = _merge_dict(ps.review_chains, st.review_chains)

    seen: Set[str] = set()
    for reg in regs.values():
        k = id_canonical_text(reg.review_chain_id)
        if k in seen:
            raise CommitTimeValidationFailure("EntryRegistry has duplicate review_chain_id")
        seen.add(k)

    seen_registration_seq: Set[Tuple[int, int]] = set()
    for reg in regs.values():
        if int(reg.registration_seq) <= 0:
            continue
        key = (int(reg.target_layer_index), int(reg.registration_seq))
        if key in seen_registration_seq:
            raise CommitTimeValidationFailure("EntryRegistry has duplicate registration_seq in target layer")
        seen_registration_seq.add(key)

    for reg in regs.values():
        if id_canonical_text(reg.entry_node) not in task_nodes:
            raise CommitTimeValidationFailure("Entry node not resolvable")
        chain_key = id_canonical_text(reg.review_chain_id)
        if chain_key not in chains:
            raise CommitTimeValidationFailure("ReviewChain not resolvable")
        chain = chains[chain_key]
        lid = layers_by_index.get(reg.target_layer_index)
        if lid is None or lid not in layers:
            raise CommitTimeValidationFailure("Layer index not resolvable")
        layer = layers[lid]
        if chain.state != ReviewChainState.TERMINATED and chain.head_index < len(chain.queue):
            if reg.review_chain_id not in layer.orchestrator_managed_review_chain_ids:
                raise CommitTimeValidationFailure("Chain not managed by target layer")

    reg_index: Dict[Tuple[int, str], int] = {}
    for reg in regs.values():
        key = (reg.target_layer_index, id_canonical_text(reg.review_chain_id))
        reg_index[key] = reg_index.get(key, 0) + 1
    for layer in layers.values():
        for cid in layer.orchestrator_managed_review_chain_ids:
            key = (layer.layer_index, id_canonical_text(cid))
            if reg_index.get(key, 0) != 1:
                raise CommitTimeValidationFailure("Managed chain must map to exactly one registration in same layer")


# -------------------------
# Transaction Manager / System
# -------------------------
class InMemorySystem:
    def __init__(
        self,
        persist_path: str | Path | None = None,
        *,
        persist_store: SnapshotStore | None = None,
    ) -> None:
        self.g = GlobalStore()
        self._persist_store: SnapshotStore | None = persist_store
        if self._persist_store is None and persist_path is not None:
            self._persist_store = JsonSnapshotStore(persist_path)
        self._persist_path: Optional[Path] = self._persist_store.location if self._persist_store is not None else None
        needs_persist_after_load = False
        if self._persist_store is not None:
            needs_persist_after_load = self._load_persisted()
        if needs_persist_after_load:
            self._persist_to_disk()

        self.project_repo = ProjectRepository(self.g)
        self.project_storage_config_repo = ProjectStorageConfigRepository(self.g)
        self.project_material_source_binding_repo = ProjectMaterialSourceBindingRepository(self.g)
        self.project_config_repo = ProjectConfigRepository(self.g)
        self.material_allowlist_repo = MaterialAllowlistRepository(self.g)
        self.media_asset_repo = MediaAssetRepository(self.g)
        self.instance_repo = InstanceRepository(self.g)
        self.instance_media_binding_repo = InstanceMediaBindingRepository(self.g)
        self.instance_subtitle_file_repo = InstanceSubtitleFileRepository(self.g, self.instance_repo)
        self.video_watch_progress_repo = VideoWatchProgressRepository(self.g)
        self.learning_object_repo = LearningObjectNodeRepository(self.g)
        self.recall_point_repo = RecallPointRepository(self.g, self.instance_repo, self.media_asset_repo)
        self.learning_task_repo = LearningTaskRepository(self.g, self.recall_point_repo)
        self.learning_task_node_repo = LearningTaskNodeRepository(
            self.g,
            self.learning_task_repo,
            self.recall_point_repo,
            self.learning_object_repo,
        )
        self.range_repo = RangeSnapshotRepository(self.g)

        self.review_task_repo = ReviewTaskRepository(self.g)
        self.recall_point_review_record_repo = RecallPointReviewRecordRepository(
            self.g, self.recall_point_repo, self.review_task_repo
        )
        self.convergence_repo = ConvergenceRepository(self.g)
        self.review_chain_repo = ReviewChainRepository(self.g)
        self.queue_repo = ReviewTaskQueueRepository(self.g)

        self.layer_repo = LayerRepository(self.g)
        self.entry_repo = EntryRegistryRepository(self.g)
        self.aggq_repo = AggregationQueueRepository(self.g)
        self.event_repo = AggregationEventRepository(self.g)
        self.audit_log_repo = AuditLogRepository(self.g)
        self.asr_artifact_repo = AsrArtifactRepository(self.g, self.recall_point_repo, self.instance_repo)

    def _begin_project_bootstrap_session(self, project_id: ProjectId) -> MutationSession:
        """
        Internal helper for create_project (0b.1.5a):
        begin a READ_WRITE mutation session for a project that does not yet exist.
        """
        if self.g._write_lock_held:
            raise ConcurrencyConflictError("Another READ_WRITE session is OPEN")
        self.g._write_lock_held = True
        ps = ProjectStore(project=None)
        runtime_kind = default_client_runtime_kind()
        return MutationSession(
            project_id=project_id,
            mode=SessionMode.READ_WRITE,
            runtime_kind=runtime_kind,
            runtime_capabilities=default_runtime_capabilities(runtime_kind),
            _baseline=ps,
        )

    def _require_system_project_id_seq(self) -> None:
        counters = self.g.idgen._counters
        if "__system__:proj" not in counters:
            raise PreconditionFailure("idgenCounters.__system__:proj is required")
        if "__system__:subj" not in counters:
            raise PreconditionFailure("idgenCounters.__system__:subj is required")

    def _require_project_audit_event_seq(self) -> None:
        def parse_seq_num(s: str, prefix: str) -> Optional[int]:
            marker = f"{prefix}_"
            if not s.startswith(marker):
                return None
            suffix = s.removeprefix(marker)
            return int(suffix) if suffix.isdigit() else None

        for project_id, project_store in self.g.projects.items():
            max_audit_n = 0
            for item in getattr(project_store, "audit_log_events", {}).values():
                n = parse_seq_num(str(getattr(item, "event_id", "")), "audit")
                if n is not None and n > max_audit_n:
                    max_audit_n = n
            if max_audit_n > 0:
                counter = int(self.g.idgen._counters.get(f"{project_id}:audit", 0))
                if counter < max_audit_n:
                    raise PreconditionFailure(f"idgenCounters.{project_id}:audit is required")

    def _load_persisted(self) -> bool:
        if self._persist_store is None:
            return False
        data = self._persist_store.load_snapshot()
        if data is None:
            return False
        projects_data, idgen_counters, global_llm_settings = decode_snapshot(data)
        self.g.global_llm_settings = global_llm_settings
        self.g.idgen._counters = dict(idgen_counters)
        self._require_system_project_id_seq()

        for pid, d in projects_data.items():
            ps = ProjectStore(project=d["project"])
            if ps.project is not None and ps.project.state == ProjectState.DELETED:
                ps.project_storage_config = d.get("project_storage_config")
                ps.project_material_source_binding = d.get("project_material_source_binding")
                ps.project_config = d.get("project_config")
                ps.material_allowlist = d.get("material_allowlist")
                ps.study_materials = d.get("study_materials", {})
                ps.study_materials_initialized = bool(
                    d.get("study_materials_initialized", bool(ps.study_materials))
                )
                ps.subject_material_link = d.get("subject_material_link")
                ps.audit_log_events = d.get("audit_log_events", {})
                ps.instances = d["instances"]
                ps.instance_media_bindings = d.get("instance_media_bindings", {})
                ps.instance_subtitle_files = d.get("instance_subtitle_files", {})
                ps.video_watch_progress = d.get("video_watch_progress", {})
                ps.learning_object_nodes = d["learning_object_nodes"]
                ps.recall_points = d["recall_points"]
                ps.recall_point_review_records = d.get("recall_point_review_records", {})
                ps.media_assets = d.get("media_assets", {})
                ps.learning_tasks = d["learning_tasks"]
                ps.learning_task_nodes = d["learning_task_nodes"]
                ps.range_snapshots = d["range_snapshots"]
                ps.asr_artifacts = d.get("asr_artifacts", {})
                ps.review_tasks = d["review_tasks"]
                ps.convergences = d["convergences"]
                ps.review_chains = d["review_chains"]
                ps.review_task_queue = d["review_task_queue"]
                ps.layers = d["layers"]
                ps.layers_by_index = d["layers_by_index"]
                ps.entry_regs = d["entry_regs"]
                ps.aggregation_queues = d["aggregation_queues"]
                ps.aggregation_events = d["aggregation_events"]
                self.g.projects[str(ProjectId(pid))] = ps
                continue
            ps.project_storage_config = d.get("project_storage_config")
            ps.project_material_source_binding = d.get("project_material_source_binding")
            ps.project_config = d.get("project_config")
            ps.material_allowlist = d.get("material_allowlist")
            ps.study_materials = d.get("study_materials", {})
            ps.study_materials_initialized = bool(d.get("study_materials_initialized", bool(ps.study_materials)))
            ps.subject_material_link = d.get("subject_material_link")
            ps.audit_log_events = d.get("audit_log_events", {})
            ps.instances = d["instances"]
            ps.instance_media_bindings = d.get("instance_media_bindings", {})
            ps.instance_subtitle_files = d.get("instance_subtitle_files", {})
            ps.video_watch_progress = d.get("video_watch_progress", {})
            ps.learning_object_nodes = d["learning_object_nodes"]
            ps.recall_points = d["recall_points"]
            ps.recall_point_review_records = d.get("recall_point_review_records", {})
            ps.media_assets = d.get("media_assets", {})
            ps.learning_tasks = d["learning_tasks"]
            ps.learning_task_nodes = d["learning_task_nodes"]
            ps.range_snapshots = d["range_snapshots"]
            ps.asr_artifacts = d.get("asr_artifacts", {})
            ps.review_tasks = d["review_tasks"]
            ps.convergences = d["convergences"]
            ps.review_chains = d["review_chains"]
            ps.review_task_queue = d["review_task_queue"]
            ps.layers = d["layers"]
            ps.layers_by_index = d["layers_by_index"]
            ps.entry_regs = d["entry_regs"]
            ps.aggregation_queues = d["aggregation_queues"]
            ps.aggregation_events = d["aggregation_events"]

            if ps.project is None:
                raise PreconditionFailure("Project missing")
            if ps.project_storage_config is None:
                raise PreconditionFailure("ProjectStorageConfig missing")
            if ps.project_storage_config.project_id != ps.project.project_id:
                raise PreconditionFailure("ProjectStorageConfig.project_id mismatch")
            ps.project_storage_config.validate_write_time()
            if ps.project_material_source_binding is None:
                raise PreconditionFailure("ProjectMaterialSourceBinding missing")
            if ps.project_material_source_binding.project_id != ps.project.project_id:
                raise PreconditionFailure("ProjectMaterialSourceBinding.project_id mismatch")
            ps.project_material_source_binding.validate_write_time()

            # The persisted snapshot format stores per-layer control fields as layer_index-keyed maps,
            # while the domain model stores them on Layer. Hydrate the model from that persisted shape.
            k_node_by_idx: Dict[int, int] = dict(d.get("aggregation_k_node", {}))
            k_point_by_idx: Dict[int, int] = dict(d.get("aggregation_k_point", {}))
            cycle_by_idx: Dict[int, AggregationCycleState] = dict(d.get("aggregation_cycle_state", {}))
            pending_by_idx: Dict[int, Optional[str]] = dict(d.get("pending_roll_up_parent_node_id", {}))
            quota_by_idx: Dict[int, int] = dict(d.get("normal_tick_quota_remaining", {}))

            hydrated_layers: Dict[str, Layer] = {}
            for lid, layer in ps.layers.items():
                layer_index = int(layer.layer_index)

                cycle = cycle_by_idx.get(layer_index, AggregationCycleState.DONE)

                raw_pending = pending_by_idx.get(layer_index)
                if raw_pending is None:
                    pending: Optional[LearningTaskNodeId] = None
                else:
                    s_pending = str(raw_pending).strip()
                    pending = LearningTaskNodeId(s_pending) if s_pending else None

                try:
                    quota_raw = int(quota_by_idx.get(layer_index, 1))
                except Exception:
                    quota_raw = 1
                quota = 1 if quota_raw != 0 else 0

                try:
                    k_node_raw = int(k_node_by_idx.get(layer_index, 0))
                except Exception:
                    k_node_raw = 0
                k_node = k_node_raw if k_node_raw > 0 else DEFAULT_AGGREGATION_K_NODE

                try:
                    k_point_raw = int(k_point_by_idx.get(layer_index, 0))
                except Exception:
                    k_point_raw = 0
                k_point = k_point_raw if k_point_raw > 0 else DEFAULT_AGGREGATION_K_POINT

                updated = Layer(
                    project_id=layer.project_id,
                    layer_id=layer.layer_id,
                    layer_index=layer.layer_index,
                    layer_mode=layer.layer_mode,
                    orchestrator_managed_review_chain_ids=layer.orchestrator_managed_review_chain_ids,
                    aggregation_k_node=k_node,
                    aggregation_k_point=k_point,
                    aggregation_cycle_state=cycle,
                    pending_roll_up_parent_node_id=pending,
                    normal_tick_quota_remaining=quota,
                )
                updated.validate_local_invariants()
                hydrated_layers[lid] = updated
            ps.layers = hydrated_layers

            if ps.project_config is None:
                raise PreconditionFailure("ProjectConfig missing")
            else:
                if ps.project_config.project_id != ps.project.project_id:
                    raise PreconditionFailure("ProjectConfig.project_id mismatch")
                ps.project_config.validate_write_time()

            st = ProjectStaged()
            _validate_learning_object_tree_consistency(ps, st)
            _validate_learning_task_tree_consistency(ps, st)
            _validate_learning_task_task_dedup(ps, st)
            _validate_range_snapshot_content_addressing(ps, st)
            _validate_commit_q1_q2(ps, st)
            _validate_commit_entry_registry_and_management(ps, st)

            self.g.projects[str(ProjectId(pid))] = ps

        self._require_project_audit_event_seq()
        return False

    def _persist_to_disk(self, projects_override: Optional[Dict[str, ProjectStore]] = None) -> None:
        if self._persist_store is None:
            return
        projects = projects_override if projects_override is not None else self.g.projects
        snapshot = encode_snapshot(
            projects=projects,
            idgen_counters=self.g.idgen._counters,
            global_llm_settings=self.g.global_llm_settings,
        )
        self._persist_store.save_snapshot(snapshot)

    def _persist_project_to_disk(self, project_id: ProjectId, project_store: ProjectStore) -> None:
        if self._persist_store is None:
            return
        self._persist_store.save_project_snapshot(
            project_id=str(project_id),
            project_snapshot=encode_project_payload(project_store),
            idgen_counters=self.g.idgen._counters,
            schema_version=SCHEMA_VERSION,
        )

    def begin_session(
        self,
        project_id: ProjectId,
        mode: SessionMode,
        *,
        runtime_kind: ClientRuntimeKind | None = None,
        runtime_capabilities: frozenset[RuntimeCapability] | None = None,
    ) -> MutationSession:
        _ensure_project_active(self.g, project_id)
        if mode == SessionMode.READ_WRITE:
            if self.g._write_lock_held:
                raise ConcurrencyConflictError("Another READ_WRITE session is OPEN")
            self.g._write_lock_held = True
        ps = self.g.projects[str(project_id)]
        resolved_runtime_kind = runtime_kind or default_client_runtime_kind()
        resolved_runtime_capabilities = runtime_capabilities or default_runtime_capabilities(resolved_runtime_kind)
        return MutationSession(
            project_id=project_id,
            mode=mode,
            runtime_kind=resolved_runtime_kind,
            runtime_capabilities=resolved_runtime_capabilities,
            _baseline=ps,
        )

    def commit(self, session: MutationSession) -> None:
        session.assert_open()
        if session.mode != SessionMode.READ_WRITE:
            session.state = SessionState.FAILED
            self._release_lock_if_needed(session)
            raise PreconditionFailure("READ_ONLY session cannot commit")

        st = session._staged
        try:
            # 4.1.7 Project Delete (physical deletion)
            if st.delete_project:
                ps = self.g.projects.get(str(session.project_id))
                if ps is None or ps.project is None:
                    raise NotFound(session.project_id)
                if ps.project.state != ProjectState.ACTIVE:
                    raise PreconditionFailure("Project must be ACTIVE to delete")

                # Soft-delete/tombstone in store: clear all project-scoped objects, keep a DELETED Project record
                # (so the delete action can still be audited deterministically).
                proj = st.project if st.project is not None else ps.project
                if proj is None:
                    raise CommitTimeValidationFailure("Project missing in delete path")
                if proj.state != ProjectState.DELETED:
                    raise CommitTimeValidationFailure("Delete path must stage Project(state=DELETED)")

                next_ps = ProjectStore(project=proj)
                # Keep only staged audit events (baseline events are cleared as part of delete).
                next_ps.audit_log_events = dict(st.audit_log_events)

                self._persist_project_to_disk(session.project_id, next_ps)
                self.g.projects[str(session.project_id)] = next_ps
                session.state = SessionState.COMMITTED
                return

            # Normal commit path (update or create)
            if str(session.project_id) in self.g.projects:
                # Existing project must still be ACTIVE when committing.
                _ensure_project_active(self.g, session.project_id)
            elif session._baseline.project is not None:
                raise PreconditionFailure("Project baseline exists but is not registered in global store")

            ps = session._baseline

            _validate_learning_object_tree_consistency(ps, st)
            _validate_learning_task_tree_consistency(ps, st)
            _validate_learning_task_task_dedup(ps, st)
            _validate_range_snapshot_content_addressing(ps, st)
            _validate_commit_q1_q2(ps, st)
            _validate_commit_entry_registry_and_management(ps, st)

            proj = st.project if st.project is not None else ps.project
            if proj is None:
                raise CommitTimeValidationFailure("Project missing in final state")

            next_ps = ProjectStore(project=proj)
            next_ps.project_storage_config = (
                st.project_storage_config if st.project_storage_config is not None else ps.project_storage_config
            )
            next_ps.project_material_source_binding = (
                st.project_material_source_binding
                if st.project_material_source_binding is not None
                else ps.project_material_source_binding
            )
            next_ps.project_config = st.project_config if st.project_config is not None else ps.project_config
            next_ps.material_allowlist = st.material_allowlist if st.material_allowlist is not None else ps.material_allowlist
            next_ps.study_materials = dict(_overlay_study_materials(ps, st))
            next_ps.study_materials_initialized = (
                True if st.study_materials_replaced else getattr(ps, "study_materials_initialized", bool(ps.study_materials))
            )
            next_ps.subject_material_link = (
                st.subject_material_link if st.subject_material_link_replaced else ps.subject_material_link
            )
            next_ps.media_assets = dict(_overlay_media_assets(ps, st))
            next_ps.audit_log_events = dict(_overlay_audit_log_events(ps, st))

            next_ps.instances = dict(_overlay_instances(ps, st))
            next_ps.instance_media_bindings = dict(_overlay_instance_media_bindings(ps, st))
            next_ps.instance_subtitle_files = dict(_overlay_instance_subtitle_files(ps, st))
            next_ps.video_watch_progress = dict(_overlay_video_watch_progress(ps, st))
            next_ps.learning_object_nodes = dict(_overlay_learning_object_nodes(ps, st))
            next_ps.recall_points = dict(ps.recall_points)
            next_ps.recall_points.update(st.recall_points)
            next_ps.recall_point_review_records = dict(_overlay_recall_point_review_records(ps, st))
            next_ps.learning_tasks = dict(ps.learning_tasks)
            next_ps.learning_tasks.update(st.learning_tasks)
            next_ps.learning_task_nodes = dict(ps.learning_task_nodes)
            next_ps.learning_task_nodes.update(st.learning_task_nodes)
            next_ps.range_snapshots = dict(ps.range_snapshots)
            next_ps.range_snapshots.update(st.range_snapshots)
            next_ps.asr_artifacts = dict(getattr(ps, "asr_artifacts", {}))
            next_ps.asr_artifacts.update(getattr(st, "asr_artifacts", {}))

            next_ps.review_tasks = dict(ps.review_tasks)
            next_ps.review_tasks.update(st.review_tasks)
            next_ps.convergences = dict(ps.convergences)
            next_ps.convergences.update(st.convergences)
            next_ps.review_chains = dict(ps.review_chains)
            next_ps.review_chains.update(st.review_chains)
            next_ps.review_task_queue = st.review_task_queue if st.review_task_queue is not None else ps.review_task_queue

            next_ps.layers = dict(ps.layers)
            next_ps.layers.update(st.layers)
            next_ps.layers_by_index = dict(ps.layers_by_index)
            next_ps.layers_by_index.update(st.layers_by_index)
            next_ps.entry_regs = dict(ps.entry_regs)
            next_ps.entry_regs.update(st.entry_regs)
            next_ps.aggregation_queues = dict(ps.aggregation_queues)
            next_ps.aggregation_queues.update(st.aggregation_queues)
            next_ps.aggregation_events = dict(ps.aggregation_events)
            next_ps.aggregation_events.update(st.aggregation_events)

            self._persist_project_to_disk(session.project_id, next_ps)
            self.g.projects[str(session.project_id)] = next_ps

            session.state = SessionState.COMMITTED
        except Exception:
            session.state = SessionState.FAILED
            raise
        finally:
            self._release_lock_if_needed(session)

    def rollback(self, session: MutationSession) -> None:
        session.assert_open()
        session.state = SessionState.ROLLED_BACK
        self._release_lock_if_needed(session)

    def _release_lock_if_needed(self, session: MutationSession) -> None:
        if session.mode == SessionMode.READ_WRITE and session.state in (
            SessionState.COMMITTED,
            SessionState.ROLLED_BACK,
            SessionState.FAILED,
        ):
            self.g._write_lock_held = False

    def create_project(
        self,
        title: str,
        project_root: str | None = None,
        *,
        initial_source_kind: MaterialSourceKind = MaterialSourceKind.SERVER_FS,
        initial_project_type: ProjectType = ProjectType.COURSE,
        project_id: ProjectId | None = None,
    ) -> ProjectId:
        pid = project_id or self.g.idgen.new_project_id()
        s = self._begin_project_bootstrap_session(pid)
        try:
            if not isinstance(initial_source_kind, MaterialSourceKind):
                raise PreconditionFailure("create_project.initial_source_kind must be MaterialSourceKind")
            if not isinstance(initial_project_type, ProjectType):
                raise PreconditionFailure("create_project.initial_project_type must be ProjectType")
            if initial_project_type in {ProjectType.BOOK, ProjectType.LOOSE_POINTS} and initial_source_kind != MaterialSourceKind.MANUAL:
                raise PreconditionFailure("create_project for BOOK/LOOSE_POINTS must use MANUAL source kind")
            resolved_project_root = project_root
            if resolved_project_root is None:
                auto_project_root, _ = allocate_project_root(title)
                resolved_project_root = auto_project_root.as_posix()

            # Project object
            proj = Project(
                project_id=pid,
                title=title,
                state=ProjectState.ACTIVE,
                created_at=now_utc_ms(),
                deleted_at=None,
            )
            self.project_repo.add(s, proj)

            # Minimal project bootstrap (0b.1.5a): GLOBAL_QUEUE singleton
            q = ReviewTaskQueue(project_id=pid, queue_id=GLOBAL_QUEUE, review_task_ids=tuple(), head_index=0)
            q.validate_local_invariants()
            s._staged.review_task_queue = q

            # Minimal project bootstrap (0b.1.5a): ProjectStorageConfig singleton
            cfg = ProjectStorageConfig.create(
                pid,
                resolved_project_root,
                learning_object_root="learning_objects",
                fs_sync_policy=FsSyncPolicy.STARTUP_SYNC,
                updated_at=now_utc_ms(),
            )
            self.project_storage_config_repo.set(s, cfg)

            binding = ProjectMaterialSourceBinding.create(
                pid,
                source_kind=initial_source_kind,
                updated_at=now_utc_ms(),
            )
            self.project_material_source_binding_repo.set(s, binding)

            # Minimal project bootstrap (0b.1.5a): ProjectConfig singleton (defaults are fixed by spec).
            pcfg = default_project_config(project_id=pid, updated_at=now_utc_ms(), project_type=initial_project_type)
            self.project_config_repo.set(s, pcfg)

            # Project bootstrap (0b.1.5a): layer 0 + its AggregationQueue
            layer0 = Layer(
                project_id=pid,
                layer_id=self.g.idgen.new_layer_id(pid),
                layer_index=0,
                layer_mode=LayerMode.AUTO_TICK_ON_ENTRY,
                orchestrator_managed_review_chain_ids=tuple(),
                aggregation_k_node=DEFAULT_AGGREGATION_K_NODE,
                aggregation_k_point=DEFAULT_AGGREGATION_K_POINT,
                aggregation_cycle_state=AggregationCycleState.DONE,
            )
            layer0.validate_local_invariants()
            self.layer_repo.add(s, layer0)

            self.audit_log_repo.append(
                s,
                AuditLogEvent(
                    project_id=pid,
                    event_id=self.g.idgen.new_audit_event_id(pid),
                    occurred_at=now_utc_ms(),
                    kind=AuditEventKind.PROJECT_CREATED,
                    api_name="create_project",
                    result=AuditResultCode.OK,
                    payload=json.dumps({"projectId": str(pid), "projectType": initial_project_type.value}, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
                ),
            )

            self.commit(s)
            return pid
        except Exception:
            if s.state == SessionState.OPEN:
                self.rollback(s)
            raise

    def delete_project(self, project_id: ProjectId) -> None:
        s = self.begin_session(project_id, SessionMode.READ_WRITE)
        try:
            deleted_at = now_utc_ms()
            # Mark deleted first (tombstone) so commit() delete path can enforce DELETED final state.
            self.project_repo.mark_deleted(s, project_id, deleted_at)

            self.audit_log_repo.append(
                s,
                AuditLogEvent(
                    project_id=project_id,
                    event_id=self.g.idgen.new_audit_event_id(project_id),
                    occurred_at=deleted_at,
                    kind=AuditEventKind.PROJECT_DELETED,
                    api_name="delete_project",
                    result=AuditResultCode.OK,
                    payload=json.dumps(
                        {"projectId": str(project_id)}, ensure_ascii=False, separators=(",", ":"), sort_keys=True
                    ),
                ),
            )
            s._staged.delete_project = True
            self.commit(s)
        except Exception:
            if s.state == SessionState.OPEN:
                self.rollback(s)
            raise

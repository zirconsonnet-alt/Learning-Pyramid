from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import PurePosixPath
from typing import Any, Dict, Optional, Tuple

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
    ContentBlockKind,
    ConvergenceState,
    FsSyncPolicy,
    InstancePresence,
    LayerMode,
    MaterialSourceKind,
    MediaAssetKind,
    ProjectState,
    RecallPointReviewResult,
    ReviewChainTemplateItemKind,
    ReviewChainState,
    ReviewTaskState,
)
from backend.models.instance import Instance
from backend.models.layer import Layer
from backend.models.learning_object_node import LearningObjectContainer, LearningObjectLeaf, LearningObjectNode
from backend.models.learning_task import LearningTask
from backend.models.learning_task_node import LearningTaskContainer, LearningTaskLeaf, LearningTaskNode
from backend.models.material_allowlist import MaterialAllowlist
from backend.models.media_asset import MediaAsset
from backend.models.project import Project
from backend.models.project_config import (
    LayerConfig,
    LocalServiceConfig,
    ProjectConfig,
    ProjectExternalServicesConfig,
    RecallPointPushConfig,
    ReviewChainTemplateItem,
    default_layer_config,
    default_external_services_config,
    default_push_config,
)
from backend.models.project_material_source_binding import ProjectMaterialSourceBinding
from backend.models.project_storage_config import ProjectStorageConfig
from backend.models.range_snapshot import RangeSnapshot
from backend.models.recall_point import Anchor, RecallPoint
from backend.models.recall_point_review_record import RecallPointReviewRecord
from backend.models.rich_content import ContentBlock, RichContent
from backend.models.review_chain import ReviewChain, ReviewChainItem, ReviewChainItemKind
from backend.models.review_task import ReviewTask
from backend.models.review_task_queue import ReviewTaskQueue
from backend.models.types import (
    AggregationEventId,
    AsrArtifactId,
    ConvergenceId,
    ConvergenceRuleId,
    InstanceId,
    LayerId,
    LearningObjectNodeId,
    LearningTaskId,
    LearningTaskNodeId,
    MediaAssetId,
    ProjectId,
    RangeId,
    RecallPointId,
    ReviewChainId,
    ReviewTaskId,
    ReviewTaskQueueId,
)


SCHEMA_VERSION = 1


def _ts_to_ms(ts: datetime) -> int:
    """
    Spec 0a.10:
    - Timestamps are UTC semantics.
    - Externally observable at millisecond precision.

    Avoid float-rounding drift by using pure integer arithmetic.
    """
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    ts = ts.astimezone(timezone.utc)
    delta = ts - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return (delta.days * 86400 + delta.seconds) * 1000 + (delta.microseconds // 1000)


def _ms_to_ts(ms: int) -> datetime:
    """
    Inverse of _ts_to_ms, exact to ms (microseconds always multiple of 1000).
    """
    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=int(ms))


def _encode_project(p: Project) -> dict[str, Any]:
    return {
        "projectId": str(p.project_id),
        "title": p.title,
        "state": p.state.value,
        "createdAtMs": _ts_to_ms(p.created_at),
        "deletedAtMs": None if p.deleted_at is None else _ts_to_ms(p.deleted_at),
    }


def _decode_project(d: dict[str, Any]) -> Project:
    return Project(
        project_id=ProjectId(d["projectId"]),
        title=d["title"],
        state=ProjectState(d["state"]),
        created_at=_ms_to_ts(int(d["createdAtMs"])),
        deleted_at=None if d.get("deletedAtMs") is None else _ms_to_ts(int(d["deletedAtMs"])),
    )


def encode_timestamp_ms(ts: datetime) -> int:
    return _ts_to_ms(ts)


def encode_project_payload_record(project: Project) -> dict[str, Any]:
    return _encode_project(project)


def encode_project_shell_payload(
    *,
    project: Project,
    project_storage_config: ProjectStorageConfig | None = None,
    project_material_source_binding: ProjectMaterialSourceBinding | None = None,
    project_config: ProjectConfig | None = None,
) -> dict[str, Any]:
    return {
        "project": _encode_project(project),
        "projectStorageConfig": None
        if project_storage_config is None
        else _encode_project_storage_config(project_storage_config),
        "projectMaterialSourceBinding": None
        if project_material_source_binding is None
        else _encode_project_material_source_binding(project_material_source_binding),
        "projectConfig": None if project_config is None else _encode_project_config(project_config),
    }


def _encode_review_chain_template_item(it: ReviewChainTemplateItem) -> dict[str, Any]:
    out: dict[str, Any] = {"kind": it.kind.value}
    if it.count is not None:
        out["count"] = int(it.count)
    return out


def _decode_review_chain_template_item(d: dict[str, Any]) -> ReviewChainTemplateItem:
    return ReviewChainTemplateItem(
        kind=ReviewChainTemplateItemKind(str(d["kind"])),
        count=None if d.get("count") is None else int(d["count"]),
    )


def _encode_layer_config(c: LayerConfig) -> dict[str, Any]:
    return {
        "reviewChainTemplate": [_encode_review_chain_template_item(it) for it in c.review_chain_template],
        "aggregationKNode": int(c.aggregation_k_node),
        "aggregationKPoint": int(c.aggregation_k_point),
    }


def _decode_layer_config(d: dict[str, Any]) -> LayerConfig:
    base = default_layer_config()
    raw_template = d.get("reviewChainTemplate")
    if raw_template is None:
        tmpl = base.review_chain_template
    else:
        tmpl = tuple(_decode_review_chain_template_item(dict(it)) for it in list(raw_template))
    return LayerConfig(
        review_chain_template=tmpl,
        aggregation_k_node=int(d.get("aggregationKNode", base.aggregation_k_node)),
        aggregation_k_point=int(d.get("aggregationKPoint", base.aggregation_k_point)),
    )


def _encode_local_service_config(c: LocalServiceConfig) -> dict[str, Any]:
    out: dict[str, Any] = {"baseUrl": c.base_url}
    if c.api_key is not None:
        out["apiKey"] = c.api_key
    if c.model is not None:
        out["model"] = c.model
    return out


def _decode_local_service_config(d: dict[str, Any]) -> LocalServiceConfig:
    return LocalServiceConfig(
        base_url=str(d.get("baseUrl", "")),
        api_key=None if d.get("apiKey") is None else str(d["apiKey"]),
        model=None if d.get("model") is None else str(d["model"]),
    )


def _encode_external_services(c: ProjectExternalServicesConfig) -> dict[str, Any]:
    return {
        "asr": None if c.asr is None else _encode_local_service_config(c.asr),
        "recommender": None if c.recommender is None else _encode_local_service_config(c.recommender),
    }


def _decode_external_services(d: dict[str, Any]) -> ProjectExternalServicesConfig:
    if not d:
        return default_external_services_config()
    asr = None if d.get("asr") is None else _decode_local_service_config(dict(d["asr"]))
    rec = None if d.get("recommender") is None else _decode_local_service_config(dict(d["recommender"]))
    return ProjectExternalServicesConfig(asr=asr, recommender=rec)


def _encode_push_config(c: RecallPointPushConfig) -> dict[str, Any]:
    return {
        "minRecallPointsToEnable": int(c.min_recall_points_to_enable),
        "maxHistoryLen": int(c.max_history_len),
    }


def _decode_push_config(d: dict[str, Any]) -> RecallPointPushConfig:
    if not d:
        return default_push_config()
    default = default_push_config()
    return RecallPointPushConfig(
        min_recall_points_to_enable=int(d.get("minRecallPointsToEnable", default.min_recall_points_to_enable)),
        max_history_len=int(d.get("maxHistoryLen", default.max_history_len)),
    )


def _encode_project_config(c: ProjectConfig) -> dict[str, Any]:
    return {
        "projectId": str(c.project_id),
        "layerConfigs": {str(int(k)): _encode_layer_config(v) for k, v in c.layer_configs.items()},
        "externalServices": _encode_external_services(c.external_services),
        "pushConfig": _encode_push_config(c.push_config),
        "updatedAtMs": _ts_to_ms(c.updated_at),
    }


def _decode_project_config(d: dict[str, Any]) -> ProjectConfig:
    raw_layer_cfgs = dict(d.get("layerConfigs", {}))
    layer_cfgs: dict[int, LayerConfig] = {}
    for k, v in raw_layer_cfgs.items():
        layer_cfgs[int(k)] = _decode_layer_config(dict(v))
    return ProjectConfig(
        project_id=ProjectId(d["projectId"]),
        layer_configs=layer_cfgs,
        external_services=_decode_external_services(dict(d.get("externalServices", {}))),
        push_config=_decode_push_config(dict(d.get("pushConfig", {}))),
        updated_at=_ms_to_ts(int(d["updatedAtMs"])),
    )


def encode_project_config_payload(config: ProjectConfig) -> dict[str, Any]:
    return _encode_project_config(config)


def decode_project_config_payload(payload: dict[str, Any]) -> ProjectConfig:
    return _decode_project_config(dict(payload))


def _encode_instance(i: Instance) -> dict[str, Any]:
    return {
        "projectId": str(i.project_id),
        "instanceId": str(i.instance_id),
        "materialId": i.material_id.as_posix(),
        "presence": i.presence.value,
        "lastSeenAtMs": None if i.last_seen_at is None else _ts_to_ms(i.last_seen_at),
    }


def _decode_instance(d: dict[str, Any]) -> Instance:
    return Instance(
        project_id=ProjectId(d["projectId"]),
        instance_id=InstanceId(d["instanceId"]),
        material_id=PurePosixPath(d["materialId"]),
        presence=InstancePresence(str(d.get("presence") or "PRESENT")),
        last_seen_at=None if d.get("lastSeenAtMs") is None else _ms_to_ts(int(d["lastSeenAtMs"])),
    )


def _encode_project_storage_config(c: ProjectStorageConfig) -> dict[str, Any]:
    return {
        "projectId": str(c.project_id),
        "projectRoot": c.project_root.as_posix(),
        "learningObjectRoot": c.learning_object_root.as_posix(),
        "fsSyncPolicy": c.fs_sync_policy.value,
        "updatedAtMs": _ts_to_ms(c.updated_at),
    }


def _decode_project_storage_config(d: dict[str, Any]) -> ProjectStorageConfig:
    project_id = ProjectId(d["projectId"])
    updated_at = _ms_to_ts(int(d["updatedAtMs"]))
    if "projectRoot" in d:
        return ProjectStorageConfig(
            project_id=project_id,
            project_root=PurePosixPath(d["projectRoot"]),
            learning_object_root=PurePosixPath(str(d.get("learningObjectRoot") or "learning_objects")),
            fs_sync_policy=FsSyncPolicy(str(d.get("fsSyncPolicy") or "STARTUP_SYNC")),
            updated_at=updated_at,
        )
    return ProjectStorageConfig.from_legacy_scan_root(
        project_id,
        PurePosixPath(d["scanRoot"]),
        updated_at=updated_at,
    )


def _encode_project_material_source_binding(binding: ProjectMaterialSourceBinding) -> dict[str, Any]:
    return {
        "projectId": str(binding.project_id),
        "sourceKind": binding.source_kind.value,
        "sourceRootLabel": binding.source_root_label,
        "updatedAtMs": _ts_to_ms(binding.updated_at),
    }


def _decode_project_material_source_binding(d: dict[str, Any]) -> ProjectMaterialSourceBinding:
    return ProjectMaterialSourceBinding.create(
        ProjectId(d["projectId"]),
        source_kind=MaterialSourceKind(str(d.get("sourceKind") or MaterialSourceKind.SERVER_FS.value)),
        source_root_label=None if d.get("sourceRootLabel") is None else str(d.get("sourceRootLabel")),
        updated_at=_ms_to_ts(int(d["updatedAtMs"])),
    )


def encode_project_storage_config_payload(config: ProjectStorageConfig) -> dict[str, Any]:
    return _encode_project_storage_config(config)


def decode_project_storage_config_payload(payload: dict[str, Any]) -> ProjectStorageConfig:
    return _decode_project_storage_config(dict(payload))


def _encode_material_allowlist(a: MaterialAllowlist) -> dict[str, Any]:
    return {
        "projectId": str(a.project_id),
        "allowlistId": str(a.allowlist_id),
        "materialIds": [x.as_posix() for x in a.material_ids],
    }


def _decode_material_allowlist(d: dict[str, Any]) -> MaterialAllowlist:
    return MaterialAllowlist(
        project_id=ProjectId(d["projectId"]),
        allowlist_id=str(d["allowlistId"]),
        material_ids=tuple(PurePosixPath(x) for x in d.get("materialIds", [])),
    )


def _encode_media_asset(a: MediaAsset) -> dict[str, Any]:
    return {
        "projectId": str(a.project_id),
        "assetId": str(a.asset_id),
        "kind": a.kind.value,
        "relativePath": a.relative_path.as_posix(),
        "createdAtMs": _ts_to_ms(a.created_at),
        "mimeType": a.mime_type,
    }


def _decode_media_asset(d: dict[str, Any]) -> MediaAsset:
    return MediaAsset(
        project_id=ProjectId(d["projectId"]),
        asset_id=MediaAssetId(d["assetId"]),
        kind=MediaAssetKind(d["kind"]),
        relative_path=PurePosixPath(d["relativePath"]),
        created_at=_ms_to_ts(int(d["createdAtMs"])),
        mime_type=None if d.get("mimeType") is None else str(d.get("mimeType")),
    )

def _encode_audit_log_event(ev: AuditLogEvent) -> dict[str, Any]:
    return {
        "projectId": str(ev.project_id),
        "eventId": str(ev.event_id),
        "occurredAtMs": _ts_to_ms(ev.occurred_at),
        "kind": ev.kind.value,
        "apiName": ev.api_name,
        "result": ev.result.value,
        "payload": ev.payload,
    }


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


def _decode_audit_log_event(d: dict[str, Any]) -> AuditLogEvent:
    return AuditLogEvent(
        project_id=ProjectId(d["projectId"]),
        event_id=str(d["eventId"]),
        occurred_at=_ms_to_ts(int(d["occurredAtMs"])),
        kind=_decode_audit_event_kind(d["kind"]),
        api_name=str(d["apiName"]),
        result=AuditResultCode(d["result"]),
        payload=str(d.get("payload", "")),
    )


def _encode_learning_object_node(n: LearningObjectNode) -> dict[str, Any]:
    if isinstance(n, LearningObjectLeaf):
        return {
            "kind": "LEAF",
            "source": n.source,
            "projectId": str(n.project_id),
            "nodeId": str(n.node_id),
            "relativePath": n.relative_path.as_posix(),
            "parentId": None if n.parent_id is None else str(n.parent_id),
            "instanceId": str(n.instance_id),
            "title": n.title,
        }
    return {
        "kind": "CONTAINER",
        "source": n.source,
        "projectId": str(n.project_id),
        "nodeId": str(n.node_id),
        "relativePath": n.relative_path.as_posix(),
        "parentId": None if n.parent_id is None else str(n.parent_id),
        "children": [str(x) for x in n.children],
        "title": n.title,
    }


def _decode_learning_object_node(d: dict[str, Any]) -> LearningObjectNode:
    kind = d["kind"]
    if kind == "LEAF":
        return LearningObjectLeaf(
            source=str(d.get("source") or "FILESYSTEM"),
            project_id=ProjectId(d["projectId"]),
            node_id=LearningObjectNodeId(d["nodeId"]),
            relative_path=PurePosixPath(str(d.get("relativePath") or d.get("nodeId"))),
            parent_id=None if d.get("parentId") is None else LearningObjectNodeId(d["parentId"]),
            instance_id=InstanceId(d["instanceId"]),
            title=d["title"],
        )
    if kind == "CONTAINER":
        return LearningObjectContainer(
            source=str(d.get("source") or "FILESYSTEM"),
            project_id=ProjectId(d["projectId"]),
            node_id=LearningObjectNodeId(d["nodeId"]),
            relative_path=PurePosixPath(str(d.get("relativePath") or d.get("nodeId"))),
            parent_id=None if d.get("parentId") is None else LearningObjectNodeId(d["parentId"]),
            children=tuple(LearningObjectNodeId(x) for x in d.get("children", [])),
            title=d["title"],
        )
    raise ValueError(f"Unknown LearningObjectNode kind: {kind}")


def _encode_anchor(a: Anchor) -> dict[str, Any]:
    return {"instanceId": str(a.instance_id), "position": a.position}


def _decode_anchor(d: dict[str, Any]) -> Anchor:
    return Anchor(instance_id=InstanceId(d["instanceId"]), position=d["position"])


def _encode_content_block(b: ContentBlock) -> dict[str, Any]:
    if b.kind == ContentBlockKind.TEXT:
        return {"kind": b.kind.value, "text": b.text}
    if b.kind == ContentBlockKind.IMAGE:
        return {"kind": b.kind.value, "assetId": None if b.asset_id is None else str(b.asset_id)}
    raise ValueError(f"Unknown ContentBlockKind: {b.kind}")


def _decode_content_block(d: dict[str, Any]) -> ContentBlock:
    kind = ContentBlockKind(d["kind"])
    if kind == ContentBlockKind.TEXT:
        return ContentBlock(kind=kind, text=str(d.get("text", "")))
    if kind == ContentBlockKind.IMAGE:
        raw = d.get("assetId")
        return ContentBlock(kind=kind, asset_id=None if raw is None else MediaAssetId(str(raw)))
    raise ValueError(f"Unknown ContentBlockKind: {kind}")


def _encode_rich_content(rc: RichContent) -> list[dict[str, Any]]:
    return [_encode_content_block(b) for b in rc]


def _decode_rich_content(raw: Any) -> RichContent:
    xs = list(raw) if raw is not None else []
    return tuple(_decode_content_block(dict(x)) for x in xs)


def _encode_recall_point(rp: RecallPoint) -> dict[str, Any]:
    return {
        "projectId": str(rp.project_id),
        "recallPointId": str(rp.recall_point_id),
        "createdAtMs": _ts_to_ms(rp.created_at),
        "question": _encode_rich_content(rp.question),
        "answer": _encode_rich_content(rp.answer),
        "anchor": _encode_anchor(rp.anchor),
        "insights": [_encode_rich_content(x) for x in rp.insights],
    }


def _decode_recall_point(d: dict[str, Any]) -> RecallPoint:
    if "question" in d:
        question = _decode_rich_content(d.get("question"))
    elif "questionText" in d:
        question = (ContentBlock(kind=ContentBlockKind.TEXT, text=str(d.get("questionText", ""))),)
    else:
        raise ValueError("RecallPoint missing question")

    if "answer" in d:
        answer = _decode_rich_content(d.get("answer"))
    elif "answerText" in d:
        answer = (ContentBlock(kind=ContentBlockKind.TEXT, text=str(d.get("answerText", ""))),)
    else:
        raise ValueError("RecallPoint missing answer")

    return RecallPoint(
        project_id=ProjectId(d["projectId"]),
        recall_point_id=RecallPointId(d["recallPointId"]),
        created_at=_ms_to_ts(int(d.get("createdAtMs", 0))),
        question=question,
        answer=answer,
        anchor=_decode_anchor(d["anchor"]),
        insights=tuple(_decode_rich_content(x) for x in d.get("insights", [])),
    )


def _encode_recall_point_review_record(r: RecallPointReviewRecord) -> dict[str, Any]:
    return {
        "projectId": str(r.project_id),
        "recordId": str(r.record_id),
        "recallPointId": str(r.recall_point_id),
        "reviewTaskId": str(r.review_task_id),
        "occurredAtMs": _ts_to_ms(r.occurred_at),
        "result": r.result.value,
    }


def _decode_recall_point_review_record(d: dict[str, Any]) -> RecallPointReviewRecord:
    return RecallPointReviewRecord(
        project_id=ProjectId(d["projectId"]),
        record_id=str(d["recordId"]),
        recall_point_id=RecallPointId(d["recallPointId"]),
        review_task_id=ReviewTaskId(d["reviewTaskId"]),
        occurred_at=_ms_to_ts(int(d["occurredAtMs"])),
        result=RecallPointReviewResult(str(d["result"])),
    )

def _encode_asr_segment(s: AsrSegment) -> dict[str, Any]:
    return {
        "startMs": int(s.start_ms),
        "endMs": int(s.end_ms),
        "text": s.text,
        "confidence": None if s.confidence is None else float(s.confidence),
    }


def _decode_asr_segment(d: dict[str, Any]) -> AsrSegment:
    return AsrSegment(
        start_ms=int(d.get("startMs", 0)),
        end_ms=int(d.get("endMs", 0)),
        text=str(d.get("text", "")),
        confidence=None if d.get("confidence") is None else float(d["confidence"]),
    )


def _encode_asr_artifact(a: AsrArtifact) -> dict[str, Any]:
    return {
        "projectId": str(a.project_id),
        "asrArtifactId": str(a.asr_artifact_id),
        "createdAtMs": _ts_to_ms(a.created_at),
        "provider": a.provider.value,
        "recallPointId": str(a.recall_point_id),
        "sourceInstanceId": str(a.source_instance_id),
        "centerMs": int(a.center_ms),
        "preMs": int(a.pre_ms),
        "postMs": int(a.post_ms),
        "segments": [_encode_asr_segment(s) for s in a.segments],
    }


def _decode_asr_artifact(d: dict[str, Any]) -> AsrArtifact:
    return AsrArtifact(
        project_id=ProjectId(d["projectId"]),
        asr_artifact_id=AsrArtifactId(d["asrArtifactId"]),
        created_at=_ms_to_ts(int(d.get("createdAtMs", 0))),
        provider=AsrProvider(str(d.get("provider", AsrProvider.WHISPER.value))),
        recall_point_id=RecallPointId(d["recallPointId"]),
        source_instance_id=InstanceId(d["sourceInstanceId"]),
        center_ms=int(d.get("centerMs", 0)),
        pre_ms=int(d.get("preMs", 0)),
        post_ms=int(d.get("postMs", 0)),
        segments=tuple(_decode_asr_segment(dict(x)) for x in d.get("segments", [])),
    )


def _encode_learning_task(t: LearningTask) -> dict[str, Any]:
    return {
        "projectId": str(t.project_id),
        "learningTaskId": str(t.learning_task_id),
        "recallPointIds": [str(x) for x in t.recall_point_ids],
        "title": t.title,
    }


def _decode_learning_task(d: dict[str, Any]) -> LearningTask:
    return LearningTask(
        project_id=ProjectId(d["projectId"]),
        learning_task_id=LearningTaskId(d["learningTaskId"]),
        recall_point_ids=tuple(RecallPointId(x) for x in d["recallPointIds"]),
        title=d["title"],
    )


def _encode_learning_task_node(n: LearningTaskNode) -> dict[str, Any]:
    if isinstance(n, LearningTaskLeaf):
        return {
            "kind": "LEAF",
            "projectId": str(n.project_id),
            "nodeId": str(n.node_id),
            "parentId": None if n.parent_id is None else str(n.parent_id),
            "boundLearningTaskId": str(n.bound_learning_task_id),
            "title": n.title,
        }
    return {
        "kind": "CONTAINER",
        "projectId": str(n.project_id),
        "nodeId": str(n.node_id),
        "parentId": None if n.parent_id is None else str(n.parent_id),
        "children": [str(x) for x in n.children],
        "title": n.title,
    }


def _decode_learning_task_node(d: dict[str, Any]) -> LearningTaskNode:
    kind = d["kind"]
    if kind == "LEAF":
        return LearningTaskLeaf(
            project_id=ProjectId(d["projectId"]),
            node_id=LearningTaskNodeId(d["nodeId"]),
            parent_id=None if d.get("parentId") is None else LearningTaskNodeId(d["parentId"]),
            bound_learning_task_id=LearningTaskId(d["boundLearningTaskId"]),
            title=d["title"],
        )
    if kind == "CONTAINER":
        return LearningTaskContainer(
            project_id=ProjectId(d["projectId"]),
            node_id=LearningTaskNodeId(d["nodeId"]),
            parent_id=None if d.get("parentId") is None else LearningTaskNodeId(d["parentId"]),
            children=tuple(LearningTaskNodeId(x) for x in d.get("children", [])),
            title=d["title"],
        )
    raise ValueError(f"Unknown LearningTaskNode kind: {kind}")


def _encode_range_snapshot(s: RangeSnapshot) -> dict[str, Any]:
    return {
        "projectId": str(s.project_id),
        "rangeId": str(s.range_id),
        "recallPointIds": [str(x) for x in s.recall_point_ids],
    }


def _decode_range_snapshot(d: dict[str, Any]) -> RangeSnapshot:
    return RangeSnapshot(
        project_id=ProjectId(d["projectId"]),
        range_id=RangeId(d["rangeId"]),
        recall_point_ids=tuple(RecallPointId(x) for x in d["recallPointIds"]),
    )


def _encode_review_task(t: ReviewTask) -> dict[str, Any]:
    return {
        "projectId": str(t.project_id),
        "reviewTaskId": str(t.review_task_id),
        "inputRangeId": str(t.input_range_id),
        "createdAtMs": _ts_to_ms(t.created_at),
        "state": t.state.value,
        "executedAtMs": None if t.executed_at is None else _ts_to_ms(t.executed_at),
        "resultRangeId": None if t.result_range_id is None else str(t.result_range_id),
    }


def _decode_review_task(d: dict[str, Any]) -> ReviewTask:
    return ReviewTask(
        project_id=ProjectId(d["projectId"]),
        review_task_id=ReviewTaskId(d["reviewTaskId"]),
        input_range_id=RangeId(d["inputRangeId"]),
        created_at=_ms_to_ts(int(d["createdAtMs"])),
        state=ReviewTaskState(d["state"]),
        executed_at=None if d.get("executedAtMs") is None else _ms_to_ts(int(d["executedAtMs"])),
        result_range_id=None if d.get("resultRangeId") is None else RangeId(d["resultRangeId"]),
    )


def _encode_convergence(c: Convergence) -> dict[str, Any]:
    return {
        "projectId": str(c.project_id),
        "convergenceId": str(c.convergence_id),
        "seedRangeId": str(c.seed_range_id),
        "ruleId": str(c.rule_id),
        "reviewTaskIds": [str(x) for x in c.review_task_ids],
        "state": c.state.value,
    }


def _decode_convergence(d: dict[str, Any]) -> Convergence:
    return Convergence(
        project_id=ProjectId(d["projectId"]),
        convergence_id=ConvergenceId(d["convergenceId"]),
        seed_range_id=RangeId(d["seedRangeId"]),
        rule_id=ConvergenceRuleId(d["ruleId"]),
        review_task_ids=tuple(ReviewTaskId(x) for x in d.get("reviewTaskIds", [])),
        state=ConvergenceState(d["state"]),
    )


def _encode_review_chain_item(it: ReviewChainItem) -> dict[str, Any]:
    return {"kind": it.kind.value, "id": str(it.id)}


def _decode_review_chain_item(d: dict[str, Any]) -> ReviewChainItem:
    kind = ReviewChainItemKind(d["kind"])
    if kind == ReviewChainItemKind.CONVERGENCE:
        cid: ConvergenceId | ReviewTaskId = ConvergenceId(d["id"])
    else:
        cid = ReviewTaskId(d["id"])
    return ReviewChainItem(kind=kind, id=cid)


def _encode_review_chain(c: ReviewChain) -> dict[str, Any]:
    return {
        "projectId": str(c.project_id),
        "reviewChainId": str(c.review_chain_id),
        "queue": [_encode_review_chain_item(x) for x in c.queue],
        "headIndex": c.head_index,
        "state": c.state.value,
    }


def _decode_review_chain(d: dict[str, Any]) -> ReviewChain:
    return ReviewChain(
        project_id=ProjectId(d["projectId"]),
        review_chain_id=ReviewChainId(d["reviewChainId"]),
        queue=tuple(_decode_review_chain_item(x) for x in d.get("queue", [])),
        head_index=int(d["headIndex"]),
        state=ReviewChainState(d["state"]),
    )


def _encode_review_task_queue(q: ReviewTaskQueue) -> dict[str, Any]:
    return {
        "projectId": str(q.project_id),
        "queueId": str(q.queue_id),
        "reviewTaskIds": [str(x) for x in q.review_task_ids],
        "headIndex": q.head_index,
    }


def _decode_review_task_queue(d: dict[str, Any]) -> ReviewTaskQueue:
    return ReviewTaskQueue(
        project_id=ProjectId(d["projectId"]),
        queue_id=ReviewTaskQueueId(d["queueId"]),
        review_task_ids=tuple(ReviewTaskId(x) for x in d.get("reviewTaskIds", [])),
        head_index=int(d["headIndex"]),
    )


def _encode_layer(l: Layer) -> dict[str, Any]:
    return {
        "projectId": str(l.project_id),
        "layerId": str(l.layer_id),
        "layerIndex": l.layer_index,
        "layerMode": l.layer_mode.value,
        "orchestratorManagedReviewChainIds": [str(x) for x in l.orchestrator_managed_review_chain_ids],
    }


def _decode_layer(d: dict[str, Any]) -> Layer:
    return Layer(
        project_id=ProjectId(d["projectId"]),
        layer_id=LayerId(d["layerId"]),
        layer_index=int(d["layerIndex"]),
        layer_mode=LayerMode(d["layerMode"]),
        orchestrator_managed_review_chain_ids=tuple(ReviewChainId(x) for x in d.get("orchestratorManagedReviewChainIds", [])),
    )


def _encode_entry_reg(r: EntryRegistration) -> dict[str, Any]:
    return {
        "projectId": str(r.project_id),
        "entryNode": str(r.entry_node),
        "targetLayerIndex": r.target_layer_index,
        "reviewChainId": str(r.review_chain_id),
    }


def _decode_entry_reg(d: dict[str, Any]) -> EntryRegistration:
    return EntryRegistration(
        project_id=ProjectId(d["projectId"]),
        entry_node=LearningTaskNodeId(d["entryNode"]),
        target_layer_index=int(d["targetLayerIndex"]),
        review_chain_id=ReviewChainId(d["reviewChainId"]),
    )


def _encode_aggq(q: AggregationQueue) -> dict[str, Any]:
    return {
        "projectId": str(q.project_id),
        "layerIndex": q.layer_index,
        "nodeIds": [str(x) for x in q.node_ids],
        "headIndex": q.head_index,
    }


def _decode_aggq(d: dict[str, Any]) -> AggregationQueue:
    return AggregationQueue(
        project_id=ProjectId(d["projectId"]),
        layer_index=int(d["layerIndex"]),
        node_ids=tuple(LearningTaskNodeId(x) for x in d.get("nodeIds", [])),
        head_index=int(d["headIndex"]),
    )


def _encode_event(ev: AggregationEvent) -> dict[str, Any]:
    return {
        "projectId": str(ev.project_id),
        "eventId": str(ev.event_id),
        "createdAtMs": _ts_to_ms(ev.created_at),
        "layerIndex": ev.layer_index,
        "parentNodeId": str(ev.parent_node_id),
        "childNodeIds": [str(x) for x in ev.child_node_ids],
        "reason": ev.reason.value,
        "title": ev.title,
    }


def _decode_event(d: dict[str, Any]) -> AggregationEvent:
    return AggregationEvent(
        project_id=ProjectId(d["projectId"]),
        event_id=AggregationEventId(d["eventId"]),
        created_at=_ms_to_ts(int(d["createdAtMs"])),
        layer_index=int(d["layerIndex"]),
        parent_node_id=LearningTaskNodeId(d["parentNodeId"]),
        child_node_ids=tuple(LearningTaskNodeId(x) for x in d.get("childNodeIds", [])),
        reason=AggregationEventReason(d["reason"]),
        title=d.get("title"),
    )


def encode_project_payload(project_store: Any) -> dict[str, Any]:
    if getattr(project_store, "project", None) is None:
        raise ValueError("ProjectStore.project must be present")
    proj: Project = project_store.project  # type: ignore[assignment]

    # Compatibility: per-layer control fields are persisted as layer_index-keyed maps.
    # The domain model stores them on Layer, so derive the maps from Layer objects here.
    layers = tuple(getattr(project_store, "layers", {}).values())
    aggregation_k_node: dict[str, int] = {}
    aggregation_k_point: dict[str, int] = {}
    aggregation_cycle_state: dict[str, str] = {}
    pending_roll_up_parent_node_id: dict[str, Optional[str]] = {}
    normal_tick_quota_remaining: dict[str, int] = {}
    for layer in layers:
        idx = str(int(layer.layer_index))
        aggregation_k_node[idx] = int(layer.aggregation_k_node)
        aggregation_k_point[idx] = int(layer.aggregation_k_point)
        aggregation_cycle_state[idx] = layer.aggregation_cycle_state.value
        pending_roll_up_parent_node_id[idx] = (
            None if layer.pending_roll_up_parent_node_id is None else str(layer.pending_roll_up_parent_node_id)
        )
        normal_tick_quota_remaining[idx] = int(layer.normal_tick_quota_remaining)

    return {
        "project": _encode_project(proj),
        "projectStorageConfig": None
        if getattr(project_store, "project_storage_config", None) is None
        else _encode_project_storage_config(project_store.project_storage_config),
        "projectMaterialSourceBinding": None
        if getattr(project_store, "project_material_source_binding", None) is None
        else _encode_project_material_source_binding(project_store.project_material_source_binding),
        "projectConfig": None
        if getattr(project_store, "project_config", None) is None
        else _encode_project_config(project_store.project_config),
        "materialAllowlist": None
        if getattr(project_store, "material_allowlist", None) is None
        else _encode_material_allowlist(project_store.material_allowlist),
        "auditLogEvents": {
            k: _encode_audit_log_event(v) for k, v in getattr(project_store, "audit_log_events", {}).items()
        },
        "instances": {k: _encode_instance(v) for k, v in getattr(project_store, "instances", {}).items()},
        "learningObjectNodes": {
            k: _encode_learning_object_node(v) for k, v in getattr(project_store, "learning_object_nodes", {}).items()
        },
        "recallPoints": {k: _encode_recall_point(v) for k, v in getattr(project_store, "recall_points", {}).items()},
        "recallPointReviewRecords": {
            k: _encode_recall_point_review_record(v)
            for k, v in getattr(project_store, "recall_point_review_records", {}).items()
        },
        "mediaAssets": {k: _encode_media_asset(v) for k, v in getattr(project_store, "media_assets", {}).items()},
        "learningTasks": {k: _encode_learning_task(v) for k, v in getattr(project_store, "learning_tasks", {}).items()},
        "learningTaskNodes": {
            k: _encode_learning_task_node(v) for k, v in getattr(project_store, "learning_task_nodes", {}).items()
        },
        "rangeSnapshots": {k: _encode_range_snapshot(v) for k, v in getattr(project_store, "range_snapshots", {}).items()},
        "asrArtifacts": {k: _encode_asr_artifact(v) for k, v in getattr(project_store, "asr_artifacts", {}).items()},
        "reviewTasks": {k: _encode_review_task(v) for k, v in getattr(project_store, "review_tasks", {}).items()},
        "convergences": {k: _encode_convergence(v) for k, v in getattr(project_store, "convergences", {}).items()},
        "reviewChains": {k: _encode_review_chain(v) for k, v in getattr(project_store, "review_chains", {}).items()},
        "reviewTaskQueue": None
        if getattr(project_store, "review_task_queue", None) is None
        else _encode_review_task_queue(project_store.review_task_queue),
        "layers": {k: _encode_layer(v) for k, v in getattr(project_store, "layers", {}).items()},
        "layersByIndex": {str(k): v for k, v in getattr(project_store, "layers_by_index", {}).items()},
        "entryRegs": {k: _encode_entry_reg(v) for k, v in getattr(project_store, "entry_regs", {}).items()},
        "aggregationQueues": {
            str(k): _encode_aggq(v) for k, v in getattr(project_store, "aggregation_queues", {}).items()
        },
        "aggregationKNode": dict(aggregation_k_node),
        "aggregationKPoint": dict(aggregation_k_point),
        "aggregationCycleState": dict(aggregation_cycle_state),
        "pendingRollUpParentNodeId": dict(pending_roll_up_parent_node_id),
        "normalTickQuotaRemaining": dict(normal_tick_quota_remaining),
        "aggregationEvents": {k: _encode_event(v) for k, v in getattr(project_store, "aggregation_events", {}).items()},
    }


def decode_project_payload(project_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    d = dict(raw)
    project = _decode_project(dict(d["project"]))
    raw_storage_cfg = d.get("projectStorageConfig")
    if raw_storage_cfg is None:
        raw_storage_cfg = d.get("projectScanConfig")
    raw_material_source_binding = d.get("projectMaterialSourceBinding")
    return {
        "project": project,
        "project_storage_config": None if raw_storage_cfg is None else _decode_project_storage_config(dict(raw_storage_cfg)),
        "project_material_source_binding": None
        if raw_material_source_binding is None
        else _decode_project_material_source_binding(dict(raw_material_source_binding)),
        "project_config": None if d.get("projectConfig") is None else _decode_project_config(dict(d["projectConfig"])),
        "material_allowlist": None
        if d.get("materialAllowlist") is None
        else _decode_material_allowlist(dict(d["materialAllowlist"])),
        "audit_log_events": {k: _decode_audit_log_event(v) for k, v in dict(d.get("auditLogEvents", {})).items()},
        "instances": {k: _decode_instance(v) for k, v in dict(d.get("instances", {})).items()},
        "learning_object_nodes": {
            k: _decode_learning_object_node(v) for k, v in dict(d.get("learningObjectNodes", {})).items()
        },
        "recall_points": {k: _decode_recall_point(v) for k, v in dict(d.get("recallPoints", {})).items()},
        "recall_point_review_records": {
            k: _decode_recall_point_review_record(v)
            for k, v in dict(d.get("recallPointReviewRecords", {})).items()
        },
        "media_assets": {k: _decode_media_asset(v) for k, v in dict(d.get("mediaAssets", {})).items()},
        "learning_tasks": {k: _decode_learning_task(v) for k, v in dict(d.get("learningTasks", {})).items()},
        "learning_task_nodes": {
            k: _decode_learning_task_node(v) for k, v in dict(d.get("learningTaskNodes", {})).items()
        },
        "range_snapshots": {k: _decode_range_snapshot(v) for k, v in dict(d.get("rangeSnapshots", {})).items()},
        "asr_artifacts": {k: _decode_asr_artifact(v) for k, v in dict(d.get("asrArtifacts", {})).items()},
        "review_tasks": {k: _decode_review_task(v) for k, v in dict(d.get("reviewTasks", {})).items()},
        "convergences": {k: _decode_convergence(v) for k, v in dict(d.get("convergences", {})).items()},
        "review_chains": {k: _decode_review_chain(v) for k, v in dict(d.get("reviewChains", {})).items()},
        "review_task_queue": None
        if d.get("reviewTaskQueue") is None
        else _decode_review_task_queue(dict(d["reviewTaskQueue"])),
        "layers": {k: _decode_layer(v) for k, v in dict(d.get("layers", {})).items()},
        "layers_by_index": {int(k): str(v) for k, v in dict(d.get("layersByIndex", {})).items()},
        "entry_regs": {k: _decode_entry_reg(v) for k, v in dict(d.get("entryRegs", {})).items()},
        "aggregation_queues": {int(k): _decode_aggq(v) for k, v in dict(d.get("aggregationQueues", {})).items()},
        "aggregation_k_node": {int(k): int(v) for k, v in dict(d.get("aggregationKNode", {})).items()},
        "aggregation_k_point": {int(k): int(v) for k, v in dict(d.get("aggregationKPoint", {})).items()},
        "aggregation_cycle_state": {
            int(k): AggregationCycleState(v) for k, v in dict(d.get("aggregationCycleState", {})).items()
        },
        "pending_roll_up_parent_node_id": {
            int(k): (None if v is None else str(v)) for k, v in dict(d.get("pendingRollUpParentNodeId", {})).items()
        },
        "normal_tick_quota_remaining": {
            int(k): int(v) for k, v in dict(d.get("normalTickQuotaRemaining", {})).items()
        },
        "aggregation_events": {k: _decode_event(v) for k, v in dict(d.get("aggregationEvents", {})).items()},
    }


def encode_snapshot(*, projects: Dict[str, Any], idgen_counters: Dict[str, int]) -> dict[str, Any]:
    out: dict[str, Any] = {"schemaVersion": SCHEMA_VERSION, "idgenCounters": dict(idgen_counters), "projects": {}}
    for pid, ps in projects.items():
        if getattr(ps, "project", None) is None:
            continue
        out["projects"][pid] = encode_project_payload(ps)
    return out


def decode_snapshot(data: dict[str, Any]) -> Tuple[Dict[str, dict[str, Any]], Dict[str, int]]:
    if int(data.get("schemaVersion", 0)) != SCHEMA_VERSION:
        raise ValueError(f"Unsupported schemaVersion: {data.get('schemaVersion')}")
    idgen_counters = {str(k): int(v) for k, v in dict(data.get("idgenCounters", {})).items()}

    projects_out: Dict[str, dict[str, Any]] = {}
    projects = dict(data.get("projects", {}))
    for pid, raw in projects.items():
        projects_out[str(pid)] = decode_project_payload(str(pid), dict(raw))

    return projects_out, idgen_counters

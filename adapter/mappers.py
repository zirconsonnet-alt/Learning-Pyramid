from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Dict, Sequence

from backend.models.asr_artifact import AsrArtifact, AsrSegment, AsrTranscriptResult, InstanceAsrTranscriptResult
from backend.models.convergence import Convergence
from backend.models.entry_registration import EntryRegistration
from backend.models.instance import Instance
from backend.models.layer import Layer
from backend.models.learning_object_node import LearningObjectContainer, LearningObjectLeaf, LearningObjectNode
from backend.models.learning_task import LearningTask
from backend.models.learning_task_node import LearningTaskContainer, LearningTaskLeaf, LearningTaskNode
from backend.models.project import Project
from backend.models.project_config import LayerConfig, ProjectConfig, ReviewChainTemplateItem
from backend.models.project_material_source_binding import ProjectMaterialSourceBinding
from backend.models.project_storage_config import ProjectStorageConfig
from backend.models.range_snapshot import RangeSnapshot
from backend.models.recall_point import RecallPoint
from backend.models.study_material import StudyMaterial
from backend.models.review_recommendation import (
    RecallPointReviewProjection,
    RecallPointReviewRecommendation,
    RecallPointReviewRecommendationPage,
)
from backend.models.rich_content import ContentBlock, RichContent
from backend.models.review_chain import ReviewChain
from backend.models.review_task import ReviewTask
from backend.models.aggregation_event import AggregationEvent
from backend.models.audit_log_event import AuditLogEvent
from backend.models.video_watch_progress import VideoWatchProgress


def _jsonable(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, datetime):
        # Spec 0a.10: timestamps are UTC semantics and externally observable at ms precision.
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        else:
            v = v.astimezone(timezone.utc)
        return v.isoformat(timespec="milliseconds")
    if isinstance(v, PurePosixPath):
        return v.as_posix()
    if isinstance(v, Enum):
        return v.value
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(val) for k, val in v.items()}
    if is_dataclass(v):
        return {k: _jsonable(val) for k, val in asdict(v).items()}
    return v


def project_to_dto(p: Project) -> Dict[str, Any]:
    return {
        "subjectId": None if p.subject_id is None else str(p.subject_id),
        "projectId": str(p.public_project_id),
        "title": p.title,
        "state": _jsonable(p.state),
        "createdAt": _jsonable(p.created_at),
        "deletedAt": _jsonable(p.deleted_at),
    }


def subject_to_dto(p: Project) -> Dict[str, Any]:
    return {
        "subjectId": str(p.project_id),
        "title": p.title,
        "state": _jsonable(p.state),
        "createdAt": _jsonable(p.created_at),
        "deletedAt": _jsonable(p.deleted_at),
    }


def study_material_to_dto(m: StudyMaterial) -> Dict[str, Any]:
    return {
        "subjectId": str(m.subject_id),
        "materialId": m.material_id,
        "materialType": _jsonable(m.material_type),
        "title": m.title,
        "createdAt": _jsonable(m.created_at),
        "projectId": None if m.project_id is None else str(m.project_id),
    }


def subject_context_to_dto(payload: Dict[str, Any]) -> Dict[str, Any]:
    subject = payload["subject"]
    current_material = payload["current_material"]
    materials = payload["materials"]
    return {
        "subject": subject_to_dto(subject),
        "currentMaterial": study_material_to_dto(current_material),
        "materials": [study_material_to_dto(item) for item in materials],
        "currentProjectId": str(payload["current_project_id"]),
    }


def with_project_reference(dto: Dict[str, Any], *, subject_id: str, project_id: str) -> Dict[str, Any]:
    out = dict(dto)
    out["subjectId"] = str(subject_id)
    out["projectId"] = str(project_id)
    return out


def _project_id(value: Any, public_project_id: str | None = None) -> str:
    return str(public_project_id if public_project_id is not None else value)


def project_storage_config_to_dto(c: ProjectStorageConfig) -> Dict[str, Any]:
    return {
        "projectId": str(c.project_id),
        "projectRoot": _jsonable(c.project_root),
        "learningObjectRoot": _jsonable(c.learning_object_root),
        "fsSyncPolicy": _jsonable(c.fs_sync_policy),
        "updatedAt": _jsonable(c.updated_at),
    }


def project_material_source_binding_to_dto(binding: ProjectMaterialSourceBinding) -> Dict[str, Any]:
    return {
        "projectId": str(binding.project_id),
        "sourceKind": _jsonable(binding.source_kind),
        "sourceRootLabel": binding.source_root_label,
        "updatedAt": _jsonable(binding.updated_at),
    }


def instance_to_dto(
    i: Instance,
    *,
    media_source_kind: str | None = None,
    playback_kind: str | None = None,
    duration_ms: int | None = None,
) -> Dict[str, Any]:
    return {
        "instanceId": str(i.instance_id),
        "materialId": _jsonable(i.material_id),
        "materialDisplayName": i.material_display_name,
        "presence": _jsonable(getattr(i, "presence", None)),
        "lastSeenAt": _jsonable(getattr(i, "last_seen_at", None)),
        "mediaSourceKind": media_source_kind,
        "playbackKind": playback_kind,
        "durationMs": duration_ms,
    }


def video_watch_progress_to_dto(item: VideoWatchProgress, *, public_project_id: str | None = None) -> Dict[str, Any]:
    return {
        "projectId": _project_id(item.project_id, public_project_id),
        "instanceId": str(item.instance_id),
        "durationMs": item.duration_ms,
        "watchedMs": item.watched_ms,
        "ranges": [{"startMs": int(start_ms), "endMs": int(end_ms)} for start_ms, end_ms in item.ranges],
        "completedAt": _jsonable(item.completed_at),
        "updatedAt": _jsonable(item.updated_at),
    }


def _content_block_to_dto(b: ContentBlock) -> Dict[str, Any]:
    out: Dict[str, Any] = {"kind": _jsonable(b.kind)}
    if b.text is not None:
        out["text"] = b.text
    if b.asset_id is not None:
        out["assetId"] = str(b.asset_id)
    return out


def _rich_content_to_dto(rc: RichContent) -> list[Dict[str, Any]]:
    return [_content_block_to_dto(b) for b in rc]


def recall_point_to_dto(rp: RecallPoint, *, public_project_id: str | None = None) -> Dict[str, Any]:
    return {
        "projectId": _project_id(rp.project_id, public_project_id),
        "recallPointId": str(rp.recall_point_id),
        "createdAt": _jsonable(rp.created_at),
        "state": _jsonable(rp.state),
        "deletedAt": _jsonable(rp.deleted_at),
        "question": _rich_content_to_dto(rp.question),
        "answer": _rich_content_to_dto(rp.answer),
        "anchor": None if rp.anchor is None else {"instanceId": str(rp.anchor.instance_id), "position": rp.anchor.position},
        "references": [str(x) for x in rp.references],
        "insights": [_rich_content_to_dto(x) for x in rp.insights],
    }


def review_recommendation_to_dto(item: RecallPointReviewRecommendation, *, public_project_id: str | None = None) -> Dict[str, Any]:
    return {
        "recallPoint": recall_point_to_dto(item.recall_point, public_project_id=public_project_id),
        "reviewRecommendationIndex": float(item.review_recommendation_index),
        "estimatedMemoryStrength": float(item.estimated_memory_strength),
        "weightedSuccessRatio": float(item.weighted_success_ratio),
        "lastReviewedAt": _jsonable(item.last_reviewed_at),
        "lastReviewResult": _jsonable(item.last_review_result),
        "reviewCount": int(item.review_count),
    }


def review_recommendation_page_to_dto(page: RecallPointReviewRecommendationPage, *, public_project_id: str | None = None) -> Dict[str, Any]:
    return {
        "items": [review_recommendation_to_dto(item, public_project_id=public_project_id) for item in page.items],
        "totalCount": int(page.total_count),
        "offset": int(page.offset),
        "limit": int(page.limit),
        "nextOffset": None if page.next_offset is None else int(page.next_offset),
    }


def recall_point_review_projection_to_dto(item: RecallPointReviewProjection) -> Dict[str, Any]:
    return {
        "recallPointId": str(item.recall_point_id),
        "calculatedAt": _jsonable(item.calculated_at),
        "reviewRecommendationIndex": float(item.review_recommendation_index),
        "estimatedMemoryStrength": float(item.estimated_memory_strength),
        "weightedSuccessRatio": float(item.weighted_success_ratio),
        "forgettingCurveDecayPerDay": float(item.forgetting_curve_decay_per_day),
        "historyWindowSize": int(item.history_window_size),
        "lastReviewedAt": _jsonable(item.last_reviewed_at),
        "lastReviewResult": _jsonable(item.last_review_result),
        "reviewCount": int(item.review_count),
        "history": [
            {
                "reviewTaskId": str(history_item.review_task_id),
                "occurredAt": _jsonable(history_item.occurred_at),
                "result": _jsonable(history_item.result),
            }
            for history_item in item.history
        ],
    }


def range_snapshot_to_dto(snap: RangeSnapshot, *, public_project_id: str | None = None) -> Dict[str, Any]:
    return {
        "projectId": _project_id(snap.project_id, public_project_id),
        "rangeId": str(snap.range_id),
        "recallPointIds": [str(x) for x in snap.recall_point_ids],
    }


def review_task_to_dto(rt: ReviewTask, *, public_project_id: str | None = None) -> Dict[str, Any]:
    return {
        "projectId": _project_id(rt.project_id, public_project_id),
        "reviewTaskId": str(rt.review_task_id),
        "inputRangeId": str(rt.input_range_id),
        "createdAt": _jsonable(rt.created_at),
        "state": _jsonable(rt.state),
        "executedAt": _jsonable(rt.executed_at),
        "resultRangeId": None if rt.result_range_id is None else str(rt.result_range_id),
    }


def convergence_to_dto(c: Convergence, *, public_project_id: str | None = None) -> Dict[str, Any]:
    return {
        "projectId": _project_id(c.project_id, public_project_id),
        "convergenceId": str(c.convergence_id),
        "seedRangeId": str(c.seed_range_id),
        "ruleId": str(c.rule_id),
        "reviewTaskIds": [str(x) for x in c.review_task_ids],
        "state": _jsonable(c.state),
        "roundCount": int(c.round_count),
    }


def review_chain_to_dto(c: ReviewChain, *, public_project_id: str | None = None) -> Dict[str, Any]:
    return {
        "projectId": _project_id(c.project_id, public_project_id),
        "reviewChainId": str(c.review_chain_id),
        "headIndex": int(c.head_index),
        "state": _jsonable(c.state),
        "queue": [{"kind": _jsonable(it.kind), "id": str(it.id)} for it in c.queue],
    }


def layer_to_dto(l: Layer, *, public_project_id: str | None = None) -> Dict[str, Any]:
    return {
        "projectId": _project_id(l.project_id, public_project_id),
        "layerId": str(l.layer_id),
        "layerIndex": l.layer_index,
        "layerMode": _jsonable(l.layer_mode),
        "orchestratorManagedReviewChainIds": [str(x) for x in l.orchestrator_managed_review_chain_ids],
    }


def _review_chain_template_item_to_dto(it: ReviewChainTemplateItem) -> Dict[str, Any]:
    out: Dict[str, Any] = {"kind": _jsonable(it.kind)}
    if it.count is not None:
        out["count"] = int(it.count)
    return out


def _layer_config_to_dto(c: LayerConfig) -> Dict[str, Any]:
    return {
        "reviewChainTemplate": [_review_chain_template_item_to_dto(it) for it in c.review_chain_template],
        "aggregationKNode": int(c.aggregation_k_node),
        "aggregationKPoint": int(c.aggregation_k_point),
        "thresholdRollUpEnabled": bool(c.threshold_roll_up_enabled),
    }


def project_config_to_dto(c: ProjectConfig) -> Dict[str, Any]:
    push = getattr(c, "push_config", None)
    return {
        "projectId": str(c.project_id),
        "projectType": _jsonable(c.project_type),
        "rollUpStrategy": _jsonable(c.roll_up_strategy),
        "updatedAt": _jsonable(c.updated_at),
        "layerConfigs": {str(int(k)): _layer_config_to_dto(v) for k, v in c.layer_configs.items()},
        "pushConfig": None
        if push is None
        else {
            "minRecallPointsToEnable": int(push.min_recall_points_to_enable),
            "maxHistoryLen": int(push.max_history_len),
            "recommendedBatchSize": int(push.recommended_batch_size),
            "forgettingCurveDecayPerDay": float(push.forgetting_curve_decay_per_day),
        },
    }


def aggregation_event_to_dto(ev: AggregationEvent, *, public_project_id: str | None = None) -> Dict[str, Any]:
    return {
        "projectId": _project_id(ev.project_id, public_project_id),
        "eventId": str(ev.event_id),
        "createdAt": _jsonable(ev.created_at),
        "layerIndex": ev.layer_index,
        "parentNodeId": str(ev.parent_node_id),
        "childNodeIds": [str(x) for x in ev.child_node_ids],
        "reason": _jsonable(ev.reason),
        "title": ev.title,
    }


def audit_log_event_to_dto(ev: AuditLogEvent, *, public_project_id: str | None = None) -> Dict[str, Any]:
    return {
        "projectId": _project_id(ev.project_id, public_project_id),
        "eventId": str(ev.event_id),
        "occurredAt": _jsonable(ev.occurred_at),
        "kind": _jsonable(ev.kind),
        "apiName": ev.api_name,
        "result": _jsonable(ev.result),
        "payload": ev.payload,
    }


def learning_object_node_to_dto(n: LearningObjectNode, *, public_project_id: str | None = None) -> Dict[str, Any]:
    if isinstance(n, LearningObjectLeaf):
        return {
            "kind": "leaf",
            "projectId": _project_id(n.project_id, public_project_id),
            "nodeId": str(n.node_id),
            "relativePath": _jsonable(n.relative_path),
            "source": _jsonable(getattr(n, "source", None)),
            "parentId": None if n.parent_id is None else str(n.parent_id),
            "instanceId": str(n.instance_id),
            "title": n.title,
        }
    if isinstance(n, LearningObjectContainer):
        return {
            "kind": "container",
            "projectId": _project_id(n.project_id, public_project_id),
            "nodeId": str(n.node_id),
            "relativePath": _jsonable(n.relative_path),
            "source": _jsonable(getattr(n, "source", None)),
            "parentId": None if n.parent_id is None else str(n.parent_id),
            "children": [str(x) for x in n.children],
            "title": n.title,
        }
    raise TypeError(f"Unknown LearningObjectNode type: {type(n)}")


def learning_task_node_to_dto(
    n: LearningTaskNode,
    *,
    target_layer_index: int | None = None,
    public_project_id: str | None = None,
) -> Dict[str, Any]:
    if isinstance(n, LearningTaskLeaf):
        return {
            "kind": "leaf",
            "projectId": _project_id(n.project_id, public_project_id),
            "nodeId": str(n.node_id),
            "parentId": None if n.parent_id is None else str(n.parent_id),
            "boundLearningTaskId": str(n.bound_learning_task_id),
            "title": n.title,
            "targetLayerIndex": target_layer_index,
        }
    if isinstance(n, LearningTaskContainer):
        return {
            "kind": "container",
            "projectId": _project_id(n.project_id, public_project_id),
            "nodeId": str(n.node_id),
            "parentId": None if n.parent_id is None else str(n.parent_id),
            "children": [str(x) for x in n.children],
            "title": n.title,
            "nodeOrigin": _jsonable(n.node_origin),
            "targetLayerIndex": target_layer_index,
        }
    raise TypeError(f"Unknown LearningTaskNode type: {type(n)}")


def learning_task_to_dto(
    t: LearningTask,
    *,
    entry_node_id: str | None = None,
    entry_node_title: str | None = None,
    review_chain_id: str | None = None,
    target_layer_index: int | None = None,
    public_project_id: str | None = None,
) -> Dict[str, Any]:
    return {
        "projectId": _project_id(t.project_id, public_project_id),
        "learningTaskId": str(t.learning_task_id),
        "title": t.title,
        "recallPointIds": [str(x) for x in t.recall_point_ids],
        "size": int(t.size),
        "entryNodeId": entry_node_id,
        "entryNodeTitle": entry_node_title,
        "reviewChainId": review_chain_id,
        "targetLayerIndex": target_layer_index,
    }


def review_chain_binding_to_dto(
    *,
    project_id: str,
    reg: EntryRegistration,
    entry_node: LearningTaskNode,
    learning_task: LearningTask | None = None,
) -> Dict[str, Any]:
    return {
        "projectId": project_id,
        "reviewChainId": str(reg.review_chain_id),
        "entryNodeId": str(reg.entry_node),
        "entryNodeTitle": entry_node.title,
        "entryNodeKind": "leaf" if isinstance(entry_node, LearningTaskLeaf) else "container",
        "learningTaskId": None if learning_task is None else str(learning_task.learning_task_id),
        "learningTaskTitle": None if learning_task is None else learning_task.title,
        "childCount": len(entry_node.children) if isinstance(entry_node, LearningTaskContainer) else None,
        "targetLayerIndex": int(reg.target_layer_index),
    }


def asr_segment_to_dto(s: AsrSegment) -> Dict[str, Any]:
    return {
        "startMs": int(s.start_ms),
        "endMs": int(s.end_ms),
        "text": s.text,
        "confidence": None if s.confidence is None else float(s.confidence),
    }


def asr_artifact_to_dto(a: AsrArtifact, *, public_project_id: str | None = None) -> Dict[str, Any]:
    return {
        "projectId": _project_id(a.project_id, public_project_id),
        "asrArtifactId": str(a.asr_artifact_id),
        "createdAt": _jsonable(a.created_at),
        "provider": _jsonable(a.provider),
        "producerRuntimeKind": _jsonable(a.producer_runtime_kind),
        "recallPointId": str(a.recall_point_id),
        "sourceInstanceId": str(a.source_instance_id),
        "centerMs": int(a.center_ms),
        "preMs": int(a.pre_ms),
        "postMs": int(a.post_ms),
        "segments": [asr_segment_to_dto(x) for x in a.segments],
    }


def asr_transcript_result_to_dto(result: AsrTranscriptResult, *, public_project_id: str | None = None) -> Dict[str, Any]:
    return {
        "projectId": _project_id(result.project_id, public_project_id),
        "provider": _jsonable(result.provider),
        "recallPointId": str(result.recall_point_id),
        "sourceInstanceId": str(result.source_instance_id),
        "centerMs": int(result.center_ms),
        "preMs": int(result.pre_ms),
        "postMs": int(result.post_ms),
        "segments": [asr_segment_to_dto(x) for x in result.segments],
    }


def instance_asr_transcript_result_to_dto(result: InstanceAsrTranscriptResult, *, public_project_id: str | None = None) -> Dict[str, Any]:
    return {
        "projectId": _project_id(result.project_id, public_project_id),
        "provider": _jsonable(result.provider),
        "sourceInstanceId": str(result.source_instance_id),
        "startMs": int(result.start_ms),
        "endMs": int(result.end_ms),
        "segments": [asr_segment_to_dto(x) for x in result.segments],
    }

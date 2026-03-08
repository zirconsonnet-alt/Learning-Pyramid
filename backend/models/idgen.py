from dataclasses import dataclass
from typing import Dict

from backend.models.types import (
    AggregationEventId,
    ConvergenceId,
    AsrArtifactId,
    InstanceId,
    LearningObjectNodeId,
    LearningTaskId,
    LearningTaskNodeId,
    LayerId,
    ProjectId,
    RangeId,
    RecallPointId,
    ReviewChainId,
    ReviewTaskId,
)


@dataclass
class InMemoryIdGenerator:
    _counters: Dict[str, int]
    _SYSTEM_PROJECT_SEQ_KEY = "__system__:proj"

    def __init__(self) -> None:
        self._counters = {}

    def ensure_project_id_seq_at_least(self, n: int) -> None:
        cur = int(self._counters.get(self._SYSTEM_PROJECT_SEQ_KEY, 0))
        if n > cur:
            self._counters[self._SYSTEM_PROJECT_SEQ_KEY] = n

    def new_project_id(self) -> ProjectId:
        """
        0a.11 强约束：Project.project_id 为系统级唯一标识（不得复用）。
        """
        n = int(self._counters.get(self._SYSTEM_PROJECT_SEQ_KEY, 0)) + 1
        self._counters[self._SYSTEM_PROJECT_SEQ_KEY] = n
        return ProjectId(f"proj_{n:06d}")

    def _next(self, project_id: ProjectId, prefix: str) -> str:
        key = f"{project_id}:{prefix}"
        n = self._counters.get(key, 0) + 1
        self._counters[key] = n
        return f"{prefix}_{n:08d}"

    def new_instance_id(self, project_id: ProjectId) -> InstanceId:
        return InstanceId(self._next(project_id, "inst"))

    def new_learning_object_node_id(self, project_id: ProjectId) -> LearningObjectNodeId:
        return LearningObjectNodeId(self._next(project_id, "lon"))

    def new_recall_point_id(self, project_id: ProjectId) -> RecallPointId:
        return RecallPointId(self._next(project_id, "rp"))

    def new_learning_task_id(self, project_id: ProjectId) -> LearningTaskId:
        return LearningTaskId(self._next(project_id, "lt"))

    def new_learning_task_node_id(self, project_id: ProjectId) -> LearningTaskNodeId:
        return LearningTaskNodeId(self._next(project_id, "ltn"))

    def new_range_id(self, project_id: ProjectId) -> RangeId:
        return RangeId(self._next(project_id, "range"))

    def new_review_task_id(self, project_id: ProjectId) -> ReviewTaskId:
        return ReviewTaskId(self._next(project_id, "rt"))

    def new_convergence_id(self, project_id: ProjectId) -> ConvergenceId:
        return ConvergenceId(self._next(project_id, "conv"))

    def new_review_chain_id(self, project_id: ProjectId) -> ReviewChainId:
        return ReviewChainId(self._next(project_id, "chain"))

    def new_layer_id(self, project_id: ProjectId) -> LayerId:
        return LayerId(self._next(project_id, "layer"))

    def new_aggregation_event_id(self, project_id: ProjectId) -> AggregationEventId:
        return AggregationEventId(self._next(project_id, "ae"))

    def new_recall_point_review_record_id(self, project_id: ProjectId) -> str:
        return self._next(project_id, "rprr")

    def new_audit_event_id(self, project_id: ProjectId) -> str:
        return self._next(project_id, "audit")

    def new_asr_artifact_id(self, project_id: ProjectId) -> AsrArtifactId:
        return AsrArtifactId(self._next(project_id, "asr"))

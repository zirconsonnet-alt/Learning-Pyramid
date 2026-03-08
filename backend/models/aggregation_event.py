from dataclasses import dataclass
from typing import Optional, Tuple

from backend.models.enums import AggregationEventReason
from backend.models.errors import PreconditionFailure
from backend.models.types import (
    AggregationEventId,
    LearningTaskNodeId,
    ProjectId,
    Timestamp,
)


@dataclass(frozen=True, slots=True)
class AggregationEvent:
    """
    4.4.5 聚合事件记录（必须持久化）
    """

    project_id: ProjectId
    event_id: AggregationEventId
    created_at: Timestamp
    layer_index: int
    parent_node_id: LearningTaskNodeId
    child_node_ids: Tuple[LearningTaskNodeId, ...]
    reason: AggregationEventReason
    title: Optional[str] = None

    def validate_local_invariants(self) -> None:
        if not str(self.event_id):
            raise PreconditionFailure("AggregationEvent.event_id must be non-empty")
        if self.layer_index < 0:
            raise PreconditionFailure("AggregationEvent.layer_index must be >= 0")
        if not str(self.parent_node_id):
            raise PreconditionFailure("AggregationEvent.parent_node_id must be non-empty")
        if not self.child_node_ids:
            raise PreconditionFailure("AggregationEvent.child_node_ids must be non-empty")
        for idx, nid in enumerate(self.child_node_ids):
            if not str(nid):
                raise PreconditionFailure(f"AggregationEvent.child_node_ids[{idx}] must be non-empty")


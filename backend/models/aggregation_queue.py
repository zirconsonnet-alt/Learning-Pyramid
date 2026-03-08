from dataclasses import dataclass
from typing import Optional, Tuple

from backend.models.errors import PreconditionFailure
from backend.models.types import LearningTaskNodeId, ProjectId


@dataclass(frozen=True, slots=True)
class AggregationQueue:
    """
    4.4.1 聚合队列（Layer-owned State）
    - 当前内容：node_ids[head_index:]（队首 -> 队尾）
    """

    project_id: ProjectId
    layer_index: int
    node_ids: Tuple[LearningTaskNodeId, ...]
    head_index: int

    def validate_local_invariants(self) -> None:
        if self.layer_index < 0:
            raise PreconditionFailure("AggregationQueue.layer_index must be >= 0")
        if self.head_index < 0:
            raise PreconditionFailure("AggregationQueue.head_index must be >= 0")
        if self.head_index > len(self.node_ids):
            raise PreconditionFailure("AggregationQueue.head_index must be <= len(node_ids)")
        for nid in self.node_ids:
            if not str(nid):
                raise PreconditionFailure("AggregationQueue.node_ids contains empty id")

    def current_ids(self) -> Tuple[LearningTaskNodeId, ...]:
        return self.node_ids[self.head_index :]

    def peek_head(self) -> Optional[LearningTaskNodeId]:
        cur = self.current_ids()
        return cur[0] if cur else None

    def is_empty(self) -> bool:
        return self.peek_head() is None


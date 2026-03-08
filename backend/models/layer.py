from dataclasses import dataclass
from typing import Optional, Tuple

from backend.models.enums import AggregationCycleState, LayerMode
from backend.models.errors import PreconditionFailure
from backend.models.types import LearningTaskNodeId, LayerId, ProjectId, ReviewChainId, id_canonical_text


@dataclass(frozen=True, slots=True)
class Layer:
    """
    4.1.4 / 4.2.5 最小可校验事实源：
    - layer_index 在 project 内唯一（由仓库写前条件保障）
    - orchestrator_managed_review_chain_ids 需去重并按 id_canonical_text 升序持久化

    4.2.2 / 4.2.5 持久化控制字段（用于跨重启确定性）：
    - aggregation_k_node / aggregation_k_point
    - aggregation_cycle_state
    - pending_roll_up_parent_node_id
    - normal_tick_quota_remaining
    """

    project_id: ProjectId
    layer_id: LayerId
    layer_index: int
    layer_mode: LayerMode
    orchestrator_managed_review_chain_ids: Tuple[ReviewChainId, ...]

    aggregation_k_node: int = 8
    aggregation_k_point: int = 64
    aggregation_cycle_state: AggregationCycleState = AggregationCycleState.DONE
    pending_roll_up_parent_node_id: Optional[LearningTaskNodeId] = None
    normal_tick_quota_remaining: int = 1

    def validate_local_invariants(self) -> None:
        if not str(self.layer_id):
            raise PreconditionFailure("Layer.layer_id must be non-empty")
        if self.layer_index < 0:
            raise PreconditionFailure("Layer.layer_index must be >= 0")
        if int(self.aggregation_k_node) <= 0:
            raise PreconditionFailure("Layer.aggregation_k_node must be > 0")
        if int(self.aggregation_k_point) <= 0:
            raise PreconditionFailure("Layer.aggregation_k_point must be > 0")
        if int(self.normal_tick_quota_remaining) not in (0, 1):
            raise PreconditionFailure("Layer.normal_tick_quota_remaining must be 0|1")
        if self.pending_roll_up_parent_node_id is not None and not str(self.pending_roll_up_parent_node_id).strip():
            raise PreconditionFailure("Layer.pending_roll_up_parent_node_id must be non-empty when set")
        for cid in self.orchestrator_managed_review_chain_ids:
            if not str(cid):
                raise PreconditionFailure("Layer.orchestrator_managed_review_chain_ids contains empty id")

        ids = tuple(self.orchestrator_managed_review_chain_ids)
        unique_sorted = tuple(sorted(set(ids), key=id_canonical_text))
        if ids != unique_sorted:
            raise PreconditionFailure(
                "Layer.orchestrator_managed_review_chain_ids must be de-duplicated and sorted by id_canonical_text"
            )

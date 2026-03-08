from typing import Optional, Protocol, Sequence, Tuple

from backend.models.aggregation_event import AggregationEvent
from backend.models.aggregation_queue import AggregationQueue
from backend.models.entry_registration import EntryRegistration
from backend.models.layer import Layer
from backend.models.types import LayerId, LearningTaskNodeId, ProjectId, ReviewChainId


class MutationSession(Protocol):
    project_id: ProjectId


class LayerRepository(Protocol):
    def add(self, session: MutationSession, layer: Layer) -> None:
        """
        强约束：
        - layer_id 已存在 -> PreconditionFailure
        - layer_index 在同 project_id 内唯一；冲突 -> PreconditionFailure
        """

    def get(self, session: MutationSession, layer_id: LayerId) -> Layer: ...

    def get_by_index(self, session: MutationSession, layer_index: int) -> Layer: ...

    def maybe_get_by_index(self, session: MutationSession, layer_index: int) -> Optional[Layer]: ...

    def all(self, session: MutationSession) -> Sequence[Layer]:
        """
        返回顺序：按 layer_index 升序（确定性）。
        """


class EntryRegistryRepository(Protocol):
    def add(self, session: MutationSession, reg: EntryRegistration) -> None:
        """
        强约束：
        - 同 project_id 下 entry_node 已存在 -> PreconditionFailure
        推荐写前条件：
        - 同 project_id 下 review_chain_id 已被其他 entry 登记 -> PreconditionFailure
        """

    def get(self, session: MutationSession, entry_node: LearningTaskNodeId) -> EntryRegistration: ...

    def maybe_get(self, session: MutationSession, entry_node: LearningTaskNodeId) -> Optional[EntryRegistration]: ...

    def all(self, session: MutationSession) -> Sequence[EntryRegistration]:
        """
        返回顺序：按 id_canonical_text(entry_node) 升序（确定性）。
        """


class AggregationQueueRepository(Protocol):
    def enqueue(self, session: MutationSession, layer_index: int, node_id: LearningTaskNodeId) -> None:
        """
        语义：追加到队尾（node_ids 末尾）。
        """

    def current_ids(self, session: MutationSession, layer_index: int) -> Tuple[LearningTaskNodeId, ...]:
        """
        语义：返回 node_ids[head_index:]（队首 -> 队尾），不得排序/去重/省略。
        """

    def is_empty(self, session: MutationSession, layer_index: int) -> bool: ...

    def clear_current(self, session: MutationSession, layer_index: int) -> None:
        """
        强约束：必须通过设置 head_index = len(node_ids) 实现；不得物理删除/重排。
        """

    # 可选：对象读接口（便于调试/校验），不属于最小强约束面
    def get(self, session: MutationSession, layer_index: int) -> AggregationQueue: ...


class AggregationEventRepository(Protocol):
    def append(self, session: MutationSession, event: AggregationEvent) -> None: ...


class OrchestratorManagedSetView(Protocol):
    """
    用于 4.1.4 提交期强制校验的最小事实源视图：
    - 由 Layer.orchestrator_managed_review_chain_ids 承载（LayerRepository 提供持久化访问）
    - 本 Protocol 仅用于类型占位，避免在控制面接口里绑定具体实现。
    """

    def managed_review_chain_ids(self, session: MutationSession, layer_index: int) -> Tuple[ReviewChainId, ...]: ...


from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple, Union

from backend.models.enums import ReviewChainState
from backend.models.errors import PreconditionFailure
from backend.models.types import ConvergenceId, ProjectId, ReviewChainId, ReviewTaskId


class ReviewChainItemKind(str, Enum):
    CONVERGENCE = "CONVERGENCE"
    REVIEW_TASK = "REVIEW_TASK"


@dataclass(frozen=True, slots=True)
class ReviewChainItem:
    kind: ReviewChainItemKind
    id: Union[ConvergenceId, ReviewTaskId]


@dataclass(frozen=True, slots=True)
class ReviewChain:
    """
    3.3 ReviewChain：混合队列（Convergence + ReviewTask）+ head 指针
    本地语义只定义“队首元素类型下的可推进/阻塞判定”；不绑定系统调度。
    """

    project_id: ProjectId
    review_chain_id: ReviewChainId
    queue: Tuple[ReviewChainItem, ...]
    head_index: int
    state: ReviewChainState

    def validate_local_invariants(self) -> None:
        if not str(self.review_chain_id):
            raise PreconditionFailure("ReviewChain.review_chain_id must be non-empty")
        if self.head_index < 0:
            raise PreconditionFailure("ReviewChain.head_index must be >= 0")
        if self.head_index > len(self.queue):
            raise PreconditionFailure("ReviewChain.head_index must be <= len(queue)")
        for it in self.queue:
            if it.kind not in (ReviewChainItemKind.CONVERGENCE, ReviewChainItemKind.REVIEW_TASK):
                raise PreconditionFailure(f"Unknown ReviewChainItem.kind: {it.kind}")
            if not str(it.id):
                raise PreconditionFailure("ReviewChain.queue contains empty id")
        if self.state not in (ReviewChainState.IN_PROGRESS, ReviewChainState.TERMINATED):
            raise PreconditionFailure(f"Unknown ReviewChain.state: {self.state}")

    def head_item(self) -> Optional[ReviewChainItem]:
        if self.head_index >= len(self.queue):
            return None
        return self.queue[self.head_index]

    def is_head_empty(self) -> bool:
        return self.head_item() is None


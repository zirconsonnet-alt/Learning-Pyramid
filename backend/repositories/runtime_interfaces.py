from typing import Optional, Protocol, Tuple

from backend.models.convergence import Convergence
from backend.models.enums import ClientRuntimeKind, ConvergenceState, RuntimeCapability
from backend.models.review_chain import ReviewChain
from backend.models.review_task import ReviewTask
from backend.models.review_task_queue import ReviewTaskQueue
from backend.models.types import (
    ConvergenceId,
    ProjectId,
    RangeId,
    ReviewChainId,
    ReviewTaskId,
    ReviewTaskQueueId,
    Timestamp,
)


class MutationSession(Protocol):
    project_id: ProjectId
    runtime_kind: ClientRuntimeKind
    runtime_capabilities: frozenset[RuntimeCapability]


class ReviewTaskRepository(Protocol):
    def add(self, session: MutationSession, review_task: ReviewTask) -> None: ...

    def get(self, session: MutationSession, review_task_id: ReviewTaskId) -> ReviewTask: ...

    def commit_done(
        self,
        session: MutationSession,
        review_task_id: ReviewTaskId,
        executed_at: Timestamp,
        result_range_id: Optional[RangeId],
    ) -> None:
        """
        强约束：
        - NotFound：ID 不存在必须抛 NotFound
        - 写前条件：
          - 仅允许 state==PENDING 时写入 DONE
          - 若 state==DONE：必须幂等成功返回且不得改写任何字段
          - 其余情形：PreconditionFailure
        """


class ConvergenceRepository(Protocol):
    def add(self, session: MutationSession, convergence: Convergence) -> None: ...

    def get(self, session: MutationSession, convergence_id: ConvergenceId) -> Convergence: ...

    def append_review_task_id(
        self, session: MutationSession, convergence_id: ConvergenceId, review_task_id: ReviewTaskId
    ) -> None: ...

    def update_state(self, session: MutationSession, convergence_id: ConvergenceId, state: ConvergenceState) -> None: ...


class ReviewChainRepository(Protocol):
    def add(self, session: MutationSession, chain: ReviewChain) -> None: ...

    def get(self, session: MutationSession, review_chain_id: ReviewChainId) -> ReviewChain: ...

    def advance_head(self, session: MutationSession, review_chain_id: ReviewChainId) -> None:
        """
        强约束：
        - 将 head_index 前进一格
        - 若队首为空（head_index 已越界），不得产生写入且不得报错
        """


class ReviewTaskQueueRepository(Protocol):
    """
    3.4.4 强约束：
    - 所有队列操作隐式作用于 session.project_id 且 queue_id == GLOBAL_QUEUE 的唯一队列实例
    - 不得暴露对其他 queue_id 的读写接口
    """

    def enqueue_if_absent(self, session: MutationSession, review_task_id: ReviewTaskId) -> None:
        """
        原子幂等入队：
        - 若已在队列当前/历史（实现定义，但按语义应是“逻辑队列内容”）中出现，则不得重复入队且不得改变位置
        """

    def remove_by_id(self, session: MutationSession, review_task_id: ReviewTaskId) -> None:
        """
        幂等移除：
        - 若该 id 不在队列当前内容中，则不得产生写入且不得报错
        """

    def peek_head(self, session: MutationSession) -> Optional[ReviewTaskId]: ...

    def is_empty(self, session: MutationSession) -> bool: ...

    def current_ids(self, session: MutationSession) -> Tuple[ReviewTaskId, ...]: ...

    def all_queue_ids_for_commit_validation(self, session: MutationSession) -> Tuple[ReviewTaskQueueId, ...]:
        """
        语义：返回 session.project_id 作用域内全部队列记录的 queue_id 主键集合，
        并按 id_canonical_text(queue_id) 升序。
        """

from dataclasses import dataclass
from typing import Optional, Tuple

from backend.models.errors import PreconditionFailure
from backend.models.types import ProjectId, ReviewTaskId, ReviewTaskQueueId


@dataclass(frozen=True, slots=True)
class ReviewTaskQueue:
    """
    3.4 ReviewTaskQueue：FIFO 暂存待执行 ReviewTaskId（只保存 ID）
    """

    project_id: ProjectId
    queue_id: ReviewTaskQueueId
    review_task_ids: Tuple[ReviewTaskId, ...]
    head_index: int

    def validate_local_invariants(self) -> None:
        if not str(self.queue_id):
            raise PreconditionFailure("ReviewTaskQueue.queue_id must be non-empty")
        if self.head_index < 0:
            raise PreconditionFailure("ReviewTaskQueue.head_index must be >= 0")
        if self.head_index > len(self.review_task_ids):
            raise PreconditionFailure("ReviewTaskQueue.head_index must be <= len(review_task_ids)")
        for rid in self.review_task_ids:
            if not str(rid):
                raise PreconditionFailure("ReviewTaskQueue.review_task_ids contains empty id")

    def current_ids(self) -> Tuple[ReviewTaskId, ...]:
        return self.review_task_ids[self.head_index :]

    def peek_head(self) -> Optional[ReviewTaskId]:
        cur = self.current_ids()
        return cur[0] if cur else None

    def is_empty(self) -> bool:
        return self.peek_head() is None


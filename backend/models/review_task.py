from dataclasses import dataclass
from typing import Optional

from backend.models.enums import ReviewTaskState
from backend.models.errors import PreconditionFailure
from backend.models.types import ProjectId, RangeId, ReviewTaskId, Timestamp


@dataclass(frozen=True, slots=True)
class ReviewTask:
    """
    3.1 ReviewTask：可被队列化/调度的最小执行单元
    """

    project_id: ProjectId
    review_task_id: ReviewTaskId
    input_range_id: RangeId
    created_at: Timestamp
    state: ReviewTaskState
    executed_at: Optional[Timestamp] = None
    result_range_id: Optional[RangeId] = None

    def validate_local_invariants(self) -> None:
        if not str(self.review_task_id):
            raise PreconditionFailure("ReviewTask.review_task_id must be non-empty")
        if not str(self.input_range_id):
            raise PreconditionFailure("ReviewTask.input_range_id must be non-empty")

        if self.state == ReviewTaskState.PENDING:
            if self.executed_at is not None:
                raise PreconditionFailure("PENDING ReviewTask.executed_at must be None")
            if self.result_range_id is not None:
                raise PreconditionFailure("PENDING ReviewTask.result_range_id must be None")
        elif self.state == ReviewTaskState.DONE:
            if self.executed_at is None:
                raise PreconditionFailure("DONE ReviewTask.executed_at must be not None")
        else:
            raise PreconditionFailure(f"Unknown ReviewTask.state: {self.state}")


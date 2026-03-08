from dataclasses import dataclass

from backend.models.enums import RecallPointReviewResult
from backend.models.errors import PreconditionFailure
from backend.models.types import ProjectId, RecallPointId, ReviewTaskId, Timestamp


@dataclass(frozen=True, slots=True)
class RecallPointReviewRecord:
    """
    1.10 RecallPointReviewRecord（复述点复习记录）

    业务事实（可被系统读取用于派生/推荐），append-only。
    """

    project_id: ProjectId
    record_id: str
    recall_point_id: RecallPointId
    review_task_id: ReviewTaskId
    occurred_at: Timestamp
    result: RecallPointReviewResult

    def validate_write_time(self) -> None:
        if not str(self.project_id).strip():
            raise PreconditionFailure("RecallPointReviewRecord.project_id must be non-empty")
        if self.record_id is None or not str(self.record_id).strip():
            raise PreconditionFailure("RecallPointReviewRecord.record_id must be non-empty")
        if not str(self.recall_point_id).strip():
            raise PreconditionFailure("RecallPointReviewRecord.recall_point_id must be non-empty")
        if not str(self.review_task_id).strip():
            raise PreconditionFailure("RecallPointReviewRecord.review_task_id must be non-empty")
        if self.occurred_at is None:
            raise PreconditionFailure("RecallPointReviewRecord.occurred_at must be provided")


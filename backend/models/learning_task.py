from dataclasses import dataclass
from typing import Tuple

from .errors import PreconditionFailure
from .types import LearningTaskId, ProjectId, RecallPointId


@dataclass(frozen=True, slots=True)
class LearningTask:
    project_id: ProjectId
    learning_task_id: LearningTaskId
    recall_point_ids: Tuple[RecallPointId, ...]  # 非空，有序
    title: str

    def validate_write_time(self) -> None:
        # 1.5.3 写前条件
        if not str(self.learning_task_id):
            raise PreconditionFailure("LearningTask.learning_task_id must be non-empty")
        if not self.recall_point_ids or len(self.recall_point_ids) == 0:
            raise PreconditionFailure("LearningTask.recall_point_ids must be non-empty")
        if not self.title or not self.title.strip():
            raise PreconditionFailure("LearningTask.title must be non-empty")
        for rp_id in self.recall_point_ids:
            if not str(rp_id):
                raise PreconditionFailure("LearningTask.recall_point_ids contains empty id")

    @property
    def size(self) -> int:
        return len(self.recall_point_ids)

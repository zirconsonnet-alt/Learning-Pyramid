from dataclasses import dataclass
from typing import Tuple

from .errors import PreconditionFailure
from .types import ProjectId, RangeId, RecallPointId


@dataclass(frozen=True, slots=True)
class RangeSnapshot:
    project_id: ProjectId
    range_id: RangeId
    recall_point_ids: Tuple[RecallPointId, ...]  # 非空，有序

    def validate_write_time(self) -> None:
        # 1.7.3 写前条件
        if not str(self.range_id):
            raise PreconditionFailure("RangeSnapshot.range_id must be non-empty")
        if not self.recall_point_ids or len(self.recall_point_ids) == 0:
            raise PreconditionFailure("RangeSnapshot.recall_point_ids must be non-empty")
        for rp_id in self.recall_point_ids:
            if not str(rp_id):
                raise PreconditionFailure("RangeSnapshot.recall_point_ids contains empty id")

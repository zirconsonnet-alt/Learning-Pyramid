from dataclasses import dataclass
from typing import Optional

from .enums import ProjectState
from .errors import PreconditionFailure
from .types import ProjectId, Timestamp


@dataclass(frozen=True, slots=True)
class Project:
    project_id: ProjectId
    title: str
    state: ProjectState
    created_at: Timestamp
    deleted_at: Optional[Timestamp] = None

    def validate_write_time(self) -> None:
        # 1.0.3：title 非空
        if not self.title or not self.title.strip():
            raise PreconditionFailure("Project.title must be non-empty")

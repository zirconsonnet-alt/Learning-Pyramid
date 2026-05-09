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
    subject_id: Optional[ProjectId] = None
    scoped_project_id: Optional[ProjectId] = None
    legacy_global_project_id: Optional[ProjectId] = None
    project_sequence: int = 0

    def validate_write_time(self) -> None:
        # 1.0.3：title 非空
        if not self.title or not self.title.strip():
            raise PreconditionFailure("Project.title must be non-empty")
        if (self.subject_id is None) != (self.scoped_project_id is None):
            raise PreconditionFailure("Project scoped identity requires both subject_id and scoped_project_id")

    @property
    def internal_project_key(self) -> ProjectId:
        return self.project_id

    @property
    def public_project_id(self) -> ProjectId:
        return self.scoped_project_id or self.project_id

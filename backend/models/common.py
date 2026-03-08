from dataclasses import dataclass
from typing import Optional
from .types import ProjectId, Timestamp


@dataclass(frozen=True, slots=True)
class ProjectScoped:
    project_id: ProjectId


@dataclass(frozen=True, slots=True)
class SoftDeletable:
    created_at: Timestamp
    deleted_at: Optional[Timestamp] = None

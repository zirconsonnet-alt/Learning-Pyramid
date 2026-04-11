from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend.models.types import ProjectId, Timestamp


class StudyMaterialType(str, Enum):
    COURSE = "COURSE"
    BOOK = "BOOK"
    LOOSE_POINTS = "LOOSE_POINTS"
    MISTAKE_BOOK = "MISTAKE_BOOK"


@dataclass(frozen=True, slots=True)
class StudyMaterial:
    subject_id: ProjectId
    material_id: str
    material_type: StudyMaterialType
    title: str
    created_at: Timestamp
    compatibility_project_id: ProjectId | None = None

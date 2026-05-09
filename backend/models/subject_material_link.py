from dataclasses import dataclass

from backend.models.study_material import StudyMaterialType
from backend.models.types import ProjectId


@dataclass(frozen=True, slots=True)
class SubjectMaterialLink:
    subject_id: ProjectId
    material_id: str
    material_type: StudyMaterialType
    project_id: ProjectId | None = None

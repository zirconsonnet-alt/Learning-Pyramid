from dataclasses import dataclass

from backend.models.enums import MaterialSourceKind
from backend.models.errors import PreconditionFailure
from backend.models.types import DesktopAgentId, ProjectId, Timestamp, now_utc_ms


@dataclass(frozen=True, slots=True)
class ProjectMaterialSourceBinding:
    """
    1.0.4a ProjectMaterialSourceBinding（项目材料源绑定）

    关键语义：
    - source_root_label 仅作显示用途，不参与路径、排序或 ID 计算。
    """

    project_id: ProjectId
    source_kind: MaterialSourceKind
    desktop_agent_id: DesktopAgentId | None
    source_root_label: str | None
    updated_at: Timestamp

    @staticmethod
    def create(
        project_id: ProjectId,
        *,
        source_kind: MaterialSourceKind = MaterialSourceKind.SERVER_FS,
        desktop_agent_id: DesktopAgentId | str | None = None,
        source_root_label: str | None = None,
        updated_at: Timestamp | None = None,
    ) -> "ProjectMaterialSourceBinding":
        normalized_agent_id: DesktopAgentId | None
        if desktop_agent_id is None:
            normalized_agent_id = None
        else:
            text = str(desktop_agent_id).strip()
            if not text:
                raise PreconditionFailure("ProjectMaterialSourceBinding.desktop_agent_id must be non-empty when provided")
            normalized_agent_id = DesktopAgentId(text)

        normalized_root_label = None if source_root_label is None else str(source_root_label).strip()
        if normalized_root_label == "":
            normalized_root_label = None

        binding = ProjectMaterialSourceBinding(
            project_id=project_id,
            source_kind=source_kind,
            desktop_agent_id=normalized_agent_id,
            source_root_label=normalized_root_label,
            updated_at=updated_at or now_utc_ms(),
        )
        binding.validate_write_time()
        return binding

    def validate_write_time(self) -> None:
        if not str(self.project_id).strip():
            raise PreconditionFailure("ProjectMaterialSourceBinding.project_id must be non-empty")
        if not isinstance(self.source_kind, MaterialSourceKind):
            raise PreconditionFailure("ProjectMaterialSourceBinding.source_kind must be MaterialSourceKind")
        if self.source_kind == MaterialSourceKind.SERVER_FS:
            if self.desktop_agent_id is not None:
                raise PreconditionFailure("ProjectMaterialSourceBinding.desktop_agent_id must be omitted for SERVER_FS")
        elif self.source_kind == MaterialSourceKind.DESKTOP_AGENT_MANIFEST:
            if self.desktop_agent_id is None or not str(self.desktop_agent_id).strip():
                raise PreconditionFailure(
                    "ProjectMaterialSourceBinding.desktop_agent_id must be provided for DESKTOP_AGENT_MANIFEST"
                )
        else:
            raise PreconditionFailure(f"Unknown MaterialSourceKind: {self.source_kind}")

        if self.source_root_label is not None and not str(self.source_root_label).strip():
            raise PreconditionFailure("ProjectMaterialSourceBinding.source_root_label must be non-empty when provided")
        if self.updated_at is None:
            raise PreconditionFailure("ProjectMaterialSourceBinding.updated_at must be provided")

from dataclasses import dataclass

from .errors import PreconditionFailure
from .types import ProjectId, PurePath, Timestamp, normalize_material_id_to_purepath, now_utc_ms


@dataclass(frozen=True, slots=True)
class ProjectScanConfig:
    """
    1.0.4 ProjectScanConfig（项目扫描配置）

    关键语义：
    - scan_root 仅做 '\\' -> '/' 与 PurePosixPath 归一；不得做可达性探测。
    """

    project_id: ProjectId
    scan_root: PurePath
    updated_at: Timestamp

    @staticmethod
    def create(project_id: ProjectId, scan_root: str | PurePath, updated_at: Timestamp | None = None) -> "ProjectScanConfig":
        root = normalize_material_id_to_purepath(scan_root)
        cfg = ProjectScanConfig(project_id=project_id, scan_root=root, updated_at=updated_at or now_utc_ms())
        cfg.validate_write_time()
        return cfg

    def validate_write_time(self) -> None:
        if not str(self.project_id):
            raise PreconditionFailure("ProjectScanConfig.project_id must be non-empty")
        if not self.scan_root.as_posix():
            raise PreconditionFailure("ProjectScanConfig.scan_root must be non-empty")
        if self.updated_at is None:
            raise PreconditionFailure("ProjectScanConfig.updated_at must be provided")


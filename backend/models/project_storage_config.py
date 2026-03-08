from dataclasses import dataclass

from backend.models.enums import FsSyncPolicy
from backend.models.errors import PreconditionFailure
from backend.models.types import ProjectId, PurePath, Timestamp, normalize_material_id_to_purepath, now_utc_ms


@dataclass(frozen=True, slots=True)
class ProjectStorageConfig:
    """
    1.0.4 ProjectStorageConfig（项目存储配置）

    关键语义：
    - project_root 仅做 '\\' -> '/' 与 PurePosixPath 归一；不得做可达性探测。
    """

    project_id: ProjectId
    project_root: PurePath
    learning_object_root: PurePath
    fs_sync_policy: FsSyncPolicy
    updated_at: Timestamp

    @staticmethod
    def create(
        project_id: ProjectId,
        project_root: str | PurePath,
        *,
        learning_object_root: str | PurePath = "learning_objects",
        fs_sync_policy: FsSyncPolicy = FsSyncPolicy.STARTUP_SYNC,
        updated_at: Timestamp | None = None,
    ) -> "ProjectStorageConfig":
        if isinstance(project_root, str):
            raw_root = str(project_root).strip()
            if not raw_root:
                raise PreconditionFailure("ProjectStorageConfig.project_root must be non-empty")
            root = normalize_material_id_to_purepath(raw_root)
        else:
            root = normalize_material_id_to_purepath(project_root)

        if isinstance(learning_object_root, str):
            raw_lor = str(learning_object_root).strip()
            if not raw_lor:
                raise PreconditionFailure("ProjectStorageConfig.learning_object_root must be non-empty")
            lor = normalize_material_id_to_purepath(raw_lor)
        else:
            lor = normalize_material_id_to_purepath(learning_object_root)
        cfg = ProjectStorageConfig(
            project_id=project_id,
            project_root=root,
            learning_object_root=lor,
            fs_sync_policy=fs_sync_policy,
            updated_at=updated_at or now_utc_ms(),
        )
        cfg.validate_write_time()
        return cfg

    @staticmethod
    def from_legacy_scan_root(
        project_id: ProjectId,
        scan_root: str | PurePath,
        *,
        updated_at: Timestamp | None = None,
    ) -> "ProjectStorageConfig":
        root = normalize_material_id_to_purepath(scan_root)
        relative_root = root.name
        if relative_root:
            project_root = root.parent
            learning_object_root = relative_root
        else:
            project_root = root
            learning_object_root = "learning_objects"
        return ProjectStorageConfig.create(
            project_id,
            project_root,
            learning_object_root=learning_object_root,
            fs_sync_policy=FsSyncPolicy.STARTUP_SYNC,
            updated_at=updated_at,
        )

    def validate_write_time(self) -> None:
        if not str(self.project_id):
            raise PreconditionFailure("ProjectStorageConfig.project_id must be non-empty")
        if not self.project_root.as_posix().strip():
            raise PreconditionFailure("ProjectStorageConfig.project_root must be non-empty")
        if not self.learning_object_root.as_posix().strip():
            raise PreconditionFailure("ProjectStorageConfig.learning_object_root must be non-empty")
        if self.learning_object_root.is_absolute():
            raise PreconditionFailure("ProjectStorageConfig.learning_object_root must be a relative path")
        if ".." in self.learning_object_root.parts:
            raise PreconditionFailure("ProjectStorageConfig.learning_object_root must not contain '..'")
        # Pure POSIX semantics: when learning_object_root is relative and contains no '..',
        # project_root / learning_object_root must stay under project_root.
        pr_parts = self.project_root.parts
        combined_parts = (self.project_root / self.learning_object_root).parts
        if pr_parts and combined_parts[: len(pr_parts)] != pr_parts:
            raise PreconditionFailure("ProjectStorageConfig.learning_object_root must be under project_root")
        if not isinstance(self.fs_sync_policy, FsSyncPolicy):
            raise PreconditionFailure("ProjectStorageConfig.fs_sync_policy must be FsSyncPolicy")
        if self.updated_at is None:
            raise PreconditionFailure("ProjectStorageConfig.updated_at must be provided")

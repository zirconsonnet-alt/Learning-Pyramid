from pathlib import Path, PurePath

from backend.models.enums import FsSyncPolicy, MaterialSourceKind
from backend.models.errors import PreconditionFailure
from backend.models.project_storage_config import ProjectStorageConfig


def resolve_material_file_path(
    storage_cfg: ProjectStorageConfig,
    material_id: PurePath,
    *,
    source_kind: MaterialSourceKind | None = None,
) -> Path:
    abs_project_root = Path(storage_cfg.project_root.as_posix()).resolve()
    raw_material_path = Path(material_id.as_posix())

    use_learning_object_root = source_kind != MaterialSourceKind.MANUAL and storage_cfg.fs_sync_policy != FsSyncPolicy.DISABLED
    if use_learning_object_root:
        abs_root = (abs_project_root / Path(storage_cfg.learning_object_root.as_posix())).resolve()
        file_path = (abs_root / raw_material_path).resolve()
        try:
            file_path.relative_to(abs_root)
        except Exception as exc:
            raise PreconditionFailure("material_id escapes learning_object_root") from exc
        return file_path

    if raw_material_path.is_absolute():
        return raw_material_path.resolve()

    file_path = (abs_project_root / raw_material_path).resolve()
    try:
        file_path.relative_to(abs_project_root)
    except Exception as exc:
        raise PreconditionFailure("relative material_id escapes project_root") from exc
    return file_path

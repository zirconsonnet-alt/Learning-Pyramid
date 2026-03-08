from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Optional

from backend.models.enums import MediaAssetKind
from backend.models.errors import PreconditionFailure
from backend.models.types import MediaAssetId, ProjectId, PurePath, Timestamp


@dataclass(frozen=True, slots=True)
class MediaAsset:
    """
    1.9 MediaAsset（项目富媒体资产）
    """

    project_id: ProjectId
    asset_id: MediaAssetId
    kind: MediaAssetKind
    relative_path: PurePath
    created_at: Timestamp
    mime_type: Optional[str] = None

    def validate_write_time(self) -> None:
        if not str(self.asset_id):
            raise PreconditionFailure("MediaAsset.asset_id must be non-empty")
        if self.kind != MediaAssetKind.IMAGE:
            raise PreconditionFailure(f"MediaAsset.kind must be IMAGE, got: {self.kind}")

        if not isinstance(self.relative_path, PurePosixPath):
            raise PreconditionFailure("MediaAsset.relative_path must be PurePosixPath")
        if self.relative_path.is_absolute():
            raise PreconditionFailure("MediaAsset.relative_path must be relative")
        if not self.relative_path.as_posix():
            raise PreconditionFailure("MediaAsset.relative_path must be non-empty")

        posix = self.relative_path.as_posix()
        if not posix.startswith("media/"):
            raise PreconditionFailure("MediaAsset.relative_path must be under media/ subtree")
        if ".." in self.relative_path.parts:
            raise PreconditionFailure("MediaAsset.relative_path must not contain '..'")

        if self.created_at is None:
            raise PreconditionFailure("MediaAsset.created_at must be provided")

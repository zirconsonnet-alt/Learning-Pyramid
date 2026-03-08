from dataclasses import dataclass
from typing import Tuple

from .errors import PreconditionFailure
from .types import ProjectId, PurePath, id_canonical_text


@dataclass(frozen=True, slots=True)
class MaterialAllowlist:
    """
    1.8 MaterialAllowlist（材料白名单）

    注意：这是数据面对象（材料集合），不是 4.5 的“系统对外入口白名单”。
    """

    project_id: ProjectId
    allowlist_id: str
    material_ids: Tuple[PurePath, ...]

    def validate_write_time(self) -> None:
        if not str(self.project_id):
            raise PreconditionFailure("MaterialAllowlist.project_id must be non-empty")
        if self.allowlist_id is None or not str(self.allowlist_id).strip():
            raise PreconditionFailure("MaterialAllowlist.allowlist_id must be non-empty")

        # 写前条件：去重（不允许重复 material_id）
        seen: set[str] = set()
        for mid in self.material_ids:
            if not mid.as_posix():
                raise PreconditionFailure("MaterialAllowlist.material_ids contains empty id")
            k = id_canonical_text(mid.as_posix())
            if k in seen:
                raise PreconditionFailure("MaterialAllowlist.material_ids contains duplicates")
            seen.add(k)


from dataclasses import dataclass

from .enums import InstancePresence
from .errors import PreconditionFailure
from .types import (
    InstanceId,
    ProjectId,
    PurePath,
    Timestamp,
    material_display_name,
    normalize_material_id_to_purepath,
)


@dataclass(frozen=True, slots=True)
class Instance:
    project_id: ProjectId
    instance_id: InstanceId
    material_id: PurePath
    presence: InstancePresence = InstancePresence.PRESENT
    last_seen_at: Timestamp | None = None

    @staticmethod
    def create(
        project_id: ProjectId,
        instance_id: InstanceId,
        material_id: str | PurePath,
        *,
        presence: InstancePresence = InstancePresence.PRESENT,
        last_seen_at: Timestamp | None = None,
    ) -> "Instance":
        mid = normalize_material_id_to_purepath(material_id)
        inst = Instance(
            project_id=project_id,
            instance_id=instance_id,
            material_id=mid,
            presence=presence,
            last_seen_at=last_seen_at,
        )
        inst.validate_write_time()
        return inst

    @property
    def material_display_name(self) -> str:
        return material_display_name(self.material_id)

    def validate_write_time(self) -> None:
        # 1.1.3 未规定 title 等，这里只做最基础非空检查（避免写出空 ID）
        if not str(self.instance_id):
            raise PreconditionFailure("Instance.instance_id must be non-empty")
        # material_id 允许各种形式，但 PurePosixPath(as_posix) 至少应非空字符串
        if not self.material_id.as_posix():
            raise PreconditionFailure("Instance.material_id must be non-empty")
        if not isinstance(self.presence, InstancePresence):
            raise PreconditionFailure("Instance.presence must be InstancePresence")

from dataclasses import dataclass, field
from typing import Optional, Sequence, Union

from .errors import PreconditionFailure
from .types import InstanceId, LearningObjectNodeId, ProjectId, PurePath

LEARNING_OBJECT_SOURCES = {"FILESYSTEM", "MANUAL", "BAIDU_NETDISK"}


@dataclass(frozen=True, slots=True)
class LearningObjectLeaf:
    source: str
    project_id: ProjectId
    node_id: LearningObjectNodeId
    relative_path: PurePath
    parent_id: Optional[LearningObjectNodeId]
    instance_id: InstanceId
    title: str

    def validate_write_time(self) -> None:
        if not str(self.node_id):
            raise PreconditionFailure("LearningObjectLeaf.node_id must be non-empty")
        if self.source not in LEARNING_OBJECT_SOURCES:
            raise PreconditionFailure("LearningObjectLeaf.source must be FILESYSTEM, MANUAL or BAIDU_NETDISK")
        if not self.relative_path.as_posix().strip():
            raise PreconditionFailure("LearningObjectLeaf.relative_path must be non-empty")
        if self.relative_path.is_absolute():
            raise PreconditionFailure("LearningObjectLeaf.relative_path must be a relative path")
        if ".." in self.relative_path.parts:
            raise PreconditionFailure("LearningObjectLeaf.relative_path must not contain '..'")
        if not str(self.instance_id):
            raise PreconditionFailure("LearningObjectLeaf.instance_id must be non-empty")
        if not self.title or not self.title.strip():
            raise PreconditionFailure("LearningObjectLeaf.title must be non-empty")


@dataclass(frozen=True, slots=True)
class LearningObjectContainer:
    source: str
    project_id: ProjectId
    node_id: LearningObjectNodeId
    relative_path: PurePath
    parent_id: Optional[LearningObjectNodeId]
    children: Sequence[LearningObjectNodeId] = field(default_factory=tuple)
    title: str = ""

    def validate_write_time(self) -> None:
        if not str(self.node_id):
            raise PreconditionFailure("LearningObjectContainer.node_id must be non-empty")
        if self.source not in LEARNING_OBJECT_SOURCES:
            raise PreconditionFailure("LearningObjectContainer.source must be FILESYSTEM, MANUAL or BAIDU_NETDISK")
        if not self.relative_path.as_posix().strip():
            raise PreconditionFailure("LearningObjectContainer.relative_path must be non-empty")
        if self.relative_path.is_absolute():
            raise PreconditionFailure("LearningObjectContainer.relative_path must be a relative path")
        if ".." in self.relative_path.parts:
            raise PreconditionFailure("LearningObjectContainer.relative_path must not contain '..'")
        if self.title is None or not str(self.title).strip():
            raise PreconditionFailure("LearningObjectContainer.title must be non-empty")
        # children 允许为空；重复/同质/双向一致/无环是提交期强制（1.2.3），不在这里做全量结构校验
        for cid in self.children:
            if not str(cid):
                raise PreconditionFailure("LearningObjectContainer.children contains empty child id")


LearningObjectNode = Union[LearningObjectLeaf, LearningObjectContainer]

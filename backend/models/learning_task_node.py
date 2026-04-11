from dataclasses import dataclass, field
from typing import Optional, Sequence, Union

from .enums import LearningTaskNodeOrigin, ObjectMirrorStatus
from .errors import PreconditionFailure
from .types import LearningObjectNodeId, LearningTaskId, LearningTaskNodeId, ProjectId


@dataclass(frozen=True, slots=True)
class LearningTaskLeaf:
    project_id: ProjectId
    node_id: LearningTaskNodeId
    parent_id: Optional[LearningTaskNodeId]
    bound_learning_task_id: LearningTaskId
    title: str

    def validate_write_time(self) -> None:
        if not str(self.node_id):
            raise PreconditionFailure("LearningTaskLeaf.node_id must be non-empty")
        if not str(self.bound_learning_task_id):
            raise PreconditionFailure("LearningTaskLeaf.bound_learning_task_id must be non-empty")
        if not self.title or not self.title.strip():
            raise PreconditionFailure("LearningTaskLeaf.title must be non-empty")


@dataclass(frozen=True, slots=True)
class LearningTaskContainer:
    project_id: ProjectId
    node_id: LearningTaskNodeId
    parent_id: Optional[LearningTaskNodeId]
    children: Sequence[LearningTaskNodeId] = field(default_factory=tuple)
    title: str = ""
    node_origin: LearningTaskNodeOrigin = LearningTaskNodeOrigin.AGGREGATION
    bound_learning_object_node_id: Optional[LearningObjectNodeId] = None
    object_mirror_status: Optional[ObjectMirrorStatus] = None

    def validate_write_time(self) -> None:
        if not str(self.node_id):
            raise PreconditionFailure("LearningTaskContainer.node_id must be non-empty")
        if self.title is None or not str(self.title).strip():
            raise PreconditionFailure("LearningTaskContainer.title must be non-empty")
        if not isinstance(self.node_origin, LearningTaskNodeOrigin):
            raise PreconditionFailure("LearningTaskContainer.node_origin must be LearningTaskNodeOrigin")
        if self.node_origin == LearningTaskNodeOrigin.OBJECT_MIRROR:
            if self.bound_learning_object_node_id is None or not str(self.bound_learning_object_node_id):
                raise PreconditionFailure("LearningTaskContainer.bound_learning_object_node_id must be provided for OBJECT_MIRROR")
            if self.object_mirror_status is None or not isinstance(self.object_mirror_status, ObjectMirrorStatus):
                raise PreconditionFailure("LearningTaskContainer.object_mirror_status must be provided for OBJECT_MIRROR")
        else:
            if self.bound_learning_object_node_id is not None:
                raise PreconditionFailure("LearningTaskContainer.bound_learning_object_node_id must be omitted for AGGREGATION")
            if self.object_mirror_status is not None:
                raise PreconditionFailure("LearningTaskContainer.object_mirror_status must be omitted for AGGREGATION")
        for cid in self.children:
            if not str(cid):
                raise PreconditionFailure("LearningTaskContainer.children contains empty child id")


LearningTaskNode = Union[LearningTaskLeaf, LearningTaskContainer]

from dataclasses import dataclass, field
from typing import Optional, Sequence, Union

from .errors import PreconditionFailure
from .types import LearningTaskId, LearningTaskNodeId, ProjectId


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

    def validate_write_time(self) -> None:
        if not str(self.node_id):
            raise PreconditionFailure("LearningTaskContainer.node_id must be non-empty")
        if self.title is None or not str(self.title).strip():
            raise PreconditionFailure("LearningTaskContainer.title must be non-empty")
        for cid in self.children:
            if not str(cid):
                raise PreconditionFailure("LearningTaskContainer.children contains empty child id")


LearningTaskNode = Union[LearningTaskLeaf, LearningTaskContainer]

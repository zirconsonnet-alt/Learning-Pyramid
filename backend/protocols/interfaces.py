from dataclasses import dataclass
from typing import Any, Optional, Protocol, Sequence, Tuple, runtime_checkable

from backend.models.enums import ClientRuntimeKind, RuntimeCapability
from backend.models.learning_task import LearningTask
from backend.models.learning_task_node import LearningTaskNode
from backend.models.range_snapshot import RangeSnapshot
from backend.models.recall_point import Anchor, RecallPoint
from backend.models.rich_content import RichContent
from backend.models.types import (
    InstanceId,
    LearningTaskId,
    LearningTaskNodeId,
    MediaAssetId,
    ProjectId,
    RangeId,
    RecallPointId,
    ReviewTaskId,
)


@runtime_checkable
class MutationSession(Protocol):
    project_id: ProjectId
    runtime_kind: ClientRuntimeKind
    runtime_capabilities: frozenset[RuntimeCapability]


class ProtocolIdGenerator(Protocol):
    def new_recall_point_id(self, project_id: ProjectId) -> RecallPointId: ...

    def new_media_asset_id(self, project_id: ProjectId) -> MediaAssetId: ...

    def new_learning_task_id(self, project_id: ProjectId) -> LearningTaskId: ...

    def new_learning_task_node_id(self, project_id: ProjectId) -> LearningTaskNodeId: ...


class InstanceRepository(Protocol):
    def add(self, session: MutationSession, instance: Any) -> None: ...

    def get(self, session: MutationSession, instance_id: InstanceId) -> Any: ...

    def all(self, session: MutationSession) -> Sequence[Any]: ...

    def delete(self, session: MutationSession, instance_id: InstanceId) -> None: ...


class RecallPointRepository(Protocol):
    def add(self, session: MutationSession, rp: RecallPoint) -> None: ...

    def update(self, session: MutationSession, rp: RecallPoint) -> None: ...

    def append_insight(self, session: MutationSession, recall_point_id: RecallPointId, insight: RichContent) -> None: ...

    def mark_deleted(self, session: MutationSession, recall_point_id: RecallPointId, deleted_at: Any) -> None: ...

    def get(self, session: MutationSession, recall_point_id: RecallPointId) -> RecallPoint: ...

    def all(self, session: MutationSession) -> Sequence[RecallPoint]: ...


class LearningTaskRepository(Protocol):
    def add(self, session: MutationSession, task: LearningTask) -> None: ...

    def update(self, session: MutationSession, task: LearningTask) -> None: ...

    def get(self, session: MutationSession, learning_task_id: LearningTaskId) -> LearningTask: ...


class LearningTaskNodeRepository(Protocol):
    def add(self, session: MutationSession, node: LearningTaskNode) -> None: ...

    def covered_rp_ids(self, session: MutationSession, node_id: LearningTaskNodeId) -> Tuple[RecallPointId, ...]: ...

    def find_leaf_by_learning_task_id(
        self, session: MutationSession, learning_task_id: LearningTaskId
    ) -> LearningTaskNodeId: ...


class RangeSnapshotRepository(Protocol):
    def get(self, session: MutationSession, range_id: RangeId) -> RangeSnapshot: ...

    def intern(self, session: MutationSession, recall_point_ids: Tuple[RecallPointId, ...]) -> RangeId: ...


class ReviewTaskRepository(Protocol):
    def get(self, session: MutationSession, review_task_id: ReviewTaskId) -> Any: ...


@dataclass(frozen=True, slots=True)
class LearningItem:
    question: RichContent
    answer: RichContent
    anchor: Anchor


@dataclass(frozen=True, slots=True)
class LearningTaskSubmitResult:
    learning_task_id: LearningTaskId
    entry_node_id: LearningTaskNodeId
    recall_point_ids: Tuple[RecallPointId, ...]


@dataclass(frozen=True, slots=True)
class ReviewSubmitBinaryResult:
    review_task_id: ReviewTaskId
    result_range_id: Optional[RangeId]
    focus_rp_ids: Tuple[RecallPointId, ...]

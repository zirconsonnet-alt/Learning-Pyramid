from dataclasses import dataclass

from backend.models.errors import PreconditionFailure
from backend.models.types import LearningTaskNodeId, ProjectId, ReviewChainId


@dataclass(frozen=True, slots=True)
class EntryRegistration:
    """
    4.1.4 entry_node -> ReviewChainId 登记索引（RegistryRepository）
    """

    project_id: ProjectId
    entry_node: LearningTaskNodeId
    target_layer_index: int
    review_chain_id: ReviewChainId

    def validate_local_invariants(self) -> None:
        if not str(self.entry_node):
            raise PreconditionFailure("EntryRegistration.entry_node must be non-empty")
        if not str(self.review_chain_id):
            raise PreconditionFailure("EntryRegistration.review_chain_id must be non-empty")
        if self.target_layer_index < 0:
            raise PreconditionFailure("EntryRegistration.target_layer_index must be >= 0")


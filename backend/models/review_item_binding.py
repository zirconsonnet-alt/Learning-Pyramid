from dataclasses import dataclass
from enum import Enum
from typing import Optional

from backend.models.errors import PreconditionFailure
from backend.models.types import ConvergenceId, ProjectId, ReviewChainId


class ReviewItemBindingKind(str, Enum):
    CONVERGENCE = "CONVERGENCE"
    REVIEW_CHAIN = "REVIEW_CHAIN"


@dataclass(frozen=True, slots=True)
class ReviewItemBinding:
    project_id: ProjectId
    kind: ReviewItemBindingKind
    review_chain_id: ReviewChainId
    convergence_id: Optional[ConvergenceId]

    def validate_local_invariants(self) -> None:
        if not str(self.review_chain_id):
            raise PreconditionFailure("ReviewItemBinding.review_chain_id must be non-empty")
        if self.kind == ReviewItemBindingKind.CONVERGENCE and self.convergence_id is None:
            raise PreconditionFailure("ReviewItemBinding.convergence_id is required for CONVERGENCE binding")
        if self.kind == ReviewItemBindingKind.REVIEW_CHAIN and self.convergence_id is not None:
            raise PreconditionFailure("ReviewItemBinding.convergence_id must be empty for REVIEW_CHAIN binding")
